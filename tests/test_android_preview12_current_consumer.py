"""Current v3 compatibility, never operational approval or provenance reattestation."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest

import test_android_preview12_two_green_release_approval as fixture

approval = fixture.approval
EXTERNAL_INPUTS = (
    "CHUMMER_ANDROID_CURRENT_ROOT", "CHUMMER_ANDROID_CURRENT_TWO_GREEN_RECEIPT",
)
ORIGINAL_RECEIPT_SHA256 = "ce3a64d3bebd9a51eb7c6528491d55f8082ba21948d5570bee61cb08abf964f2"
CURRENT_CONSUMER_SHA256 = "0e20be838db3f99d961688a3f3ab382707ddba3a065916c7cf48b4e92164292e"


def reseal(value):
    value.pop("eligibilitySha256", None)
    value["eligibilitySha256"] = approval.canonical_sha256(value)


def change_source(value):
    graph = value["commonAuthority"]["dependencyGraph"]
    graph["sources"]["core-content"] = dict(graph["sources"]["core-runtime"])
    graph["sha256"] = approval.canonical_sha256({
        key: member for key, member in graph.items() if key != "sha256"
    })


HOSTILE_CASES = [
    ("old-v2", lambda v: v.update(schema="chummer.android.api36-ordered-review-main-green-eligibility/v2")),
    ("numeric-eligible", lambda v: v.update(eligible=1)),
    ("numeric-publication", lambda v: v.update(publicationAuthorized=0)),
    ("extra-common", lambda v: v["commonAuthority"].update(unreviewed=True)),
    ("scope", lambda v: v["commonAuthority"].update(proofScope="full_product")),
    ("class", lambda v: v["commonAuthority"].update(authorityClass="full_product")),
    ("aggregate", lambda v: v["commonAuthority"].update(aggregateSchema="unknown/v2")),
    ("missing-journey", lambda v: v["commonAuthority"]["requiredJourneys"].pop()),
    ("duplicate-journey", lambda v: v["commonAuthority"]["requiredJourneys"].append("before-run-edge")),
    ("numeric-gate-publication", lambda v: v["commonAuthority"]["wizardGate"].update(publicationAuthorized=0)),
    ("gate-count", lambda v: v["commonAuthority"]["wizardGate"].update(requiredJourneyCount=6)),
    ("gate-source", lambda v: v["commonAuthority"]["wizardGate"].update(contractSha256="0" * 64)),
    ("workflow", lambda v: v["commonAuthority"]["workflow"].update(sha256="0" * 64)),
    ("environment", lambda v: v["commonAuthority"]["environmentPolicy"].update(sha256="0" * 64)),
    ("numeric-policy-publication", lambda v: v["policyAuthority"].update(publicationAuthorized=0)),
    ("old-policy", lambda v: v["policyAuthority"].update(schema="chummer.android.api36-ordered-review-main-green-policy/v2")),
    ("graph-spoof", lambda v: v["commonAuthority"]["dependencyGraph"]["sources"]["core-content"].update(commit="0" * 40)),
    ("resealed-runtime-content-substitution", change_source),
    ("numeric-graph-mode", lambda v: v["commonAuthority"]["dependencyGraph"]["mode"].update(packageOnly=0)),
    ("missing-exclusion", lambda v: v["doesNotAssert"].pop()),
]


@pytest.mark.parametrize("name,mutate", HOSTILE_CASES, ids=[name for name, _ in HOSTILE_CASES])
def test_adapter_rejects_resealed_v3_authority_substitution(name, mutate):
    value = fixture.receipt()
    mutate(value)
    reseal(value)  # Rejection must not depend on an obsolete outer digest.
    with pytest.raises(approval.ApprovalError):
        approval.validate_receipt(
            value, approval.validate_inputs(argparse.Namespace(**fixture.inputs())),
            now=fixture.NOW, policy=approval.expected_policy(),
        )


@pytest.fixture
def current_original(monkeypatch):
    if not all(os.environ.get(name) for name in EXTERNAL_INPUTS):
        pytest.skip("exact current Android source and original qualified receipt not supplied")
    root = Path(os.environ[EXTERNAL_INPUTS[0]]).resolve(strict=True)
    receipt_path = Path(os.environ[EXTERNAL_INPUTS[1]]).resolve(strict=True)
    raw = receipt_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_RECEIPT_SHA256
    identity = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD", "HEAD^{tree}"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert identity == [approval.ANDROID_CONSUMER_COMMIT, approval.ANDROID_CONSUMER_TREE]
    assert subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout == ""
    path = root / "scripts/verify_api36_two_green_release_eligibility.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == CURRENT_CONSUMER_SHA256
    assert hashlib.sha256((root / approval.PROVENANCE_VALIDATOR_PATH).read_bytes()).hexdigest() == approval.PROVENANCE_VALIDATOR_SHA256
    assert (root / approval.RELEASE_APPROVER_PUBLIC_KEY_PATH).read_bytes() == fixture.ANDROID_388_PUBLIC_KEY.read_bytes()
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("current_android_full_consumer_test", path)
    assert spec and spec.loader
    consumer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer)
    yield root, receipt_path, raw, json.loads(raw), consumer
    assert receipt_path.read_bytes() == raw


def synthetic_approval(tmp_path, monkeypatch, raw, receipt, consumer):
    """Only published RFC material; this audit is explicitly not hosted provenance."""
    fixture.use_test_approval_key(monkeypatch)
    policy, _, _ = fixture.active_policy(tmp_path)
    now = datetime.fromisoformat(receipt["decisionTimeUtc"].replace("Z", "+00:00")) + timedelta(minutes=1)
    audit = {
        "testOnly": "RFC8032 compatibility; not protected approval or provenance replay",
        "androidSource": {"commit": receipt["sourceCommit"], "tree": receipt["sourceTree"]},
        "release": receipt["releaseIdentity"],
        "twoGreen": {
            "receiptSha256": hashlib.sha256(raw).hexdigest(),
            "receipt": {
                "eligibilitySha256": receipt["eligibilitySha256"],
                "dependencyGraphSha256": receipt["commonAuthority"]["dependencyGraph"]["sha256"],
                "environmentPolicySha256": receipt["commonAuthority"]["environmentPolicy"]["sha256"],
            },
        },
    }
    times = {
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "expires_at_utc": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "challenge_nonce": "9" * 64,
    }
    unsigned = approval.release_approval_unsigned(audit, **times)
    assert unsigned == consumer.release_approval_unsigned(
        raw, receipt, **times, provenance_validator_sha256=approval.PROVENANCE_VALIDATOR_SHA256,
        provenance_replay_sha256=approval.canonical_sha256(audit),
    )
    signed = dict(unsigned)
    signed["signatureBase64"] = approval.sign_ed25519(
        approval.android_canonical_bytes(unsigned), policy,
        {approval.KEY_ENV_NAME: base64.b64encode(fixture.TEST_PRIVATE_DER).decode()},
    )["signatureBase64"]
    approval_path = tmp_path / "RFC8032-TEST-ONLY-approval.json"
    fixture.write_json(approval_path, signed)
    approval_path.chmod(0o600)
    public = subprocess.run(
        ["openssl", "pkey", "-inform", "DER", "-pubout"],
        input=fixture.TEST_PRIVATE_DER, check=True, capture_output=True,
    ).stdout
    public_path = tmp_path / "RFC8032-TEST-ONLY-public.pem"
    public_path.write_bytes(public)
    public_path.chmod(0o600)
    # Only the in-memory test trust pin is substituted, never consumer validation.
    monkeypatch.setattr(consumer, "RELEASE_APPROVER_PUBLIC_KEY", public_path)
    monkeypatch.setattr(consumer, "RELEASE_APPROVER_PUBLIC_KEY_SHA256", hashlib.sha256(public).hexdigest())
    return approval_path, now


def verify_full(consumer, root, receipt_path, approval_path, now):
    return consumer.verify_release_eligibility(
        receipt_path, approval_path, android_root=root,
        expected_version_name=approval.VERSION_NAME, expected_version_code=approval.VERSION_CODE,
        approval_effective_time=now,
    )


def test_original_qualified_receipt_passes_full_current_android_consumer(current_original, tmp_path, monkeypatch):
    root, path, raw, receipt, consumer = current_original
    inputs = fixture.inputs()
    inputs.update(
        review_run_id=str(receipt["reviewRun"]["run"]["id"]),
        main_run_id=str(receipt["mainRun"]["run"]["id"]),
        review_pull_request_number=str(receipt["reviewPullRequest"]["number"]),
    )
    approval_path, now = synthetic_approval(tmp_path, monkeypatch, raw, receipt, consumer)
    adapter = approval.validate_receipt(
        receipt, approval.validate_inputs(argparse.Namespace(**inputs)),
        now=now, policy=approval.expected_policy(),
    )
    result = verify_full(consumer, root, path, approval_path, now)
    assert result["contractName"] == approval.TWO_GREEN_CONTRACT
    assert result["eligibilitySha256"] == adapter["eligibilitySha256"]
    assert result["receiptSha256"] == ORIGINAL_RECEIPT_SHA256
    assert result["eligible"] is True and result["internalTestingEligible"] is True
    assert result["publicationAuthorized"] is False and result["googlePlayUploadAuthorized"] is False
    assert result["sourceCommit"] == approval.ANDROID_CONSUMER_COMMIT
    assert result["sourceTree"] == approval.ANDROID_CONSUMER_TREE


@pytest.mark.parametrize("mutate", [HOSTILE_CASES[4][1], HOSTILE_CASES[7][1], change_source], ids=["scope", "missing-journey", "runtime-content"])
def test_full_current_consumer_rejects_resealed_resigned_original_drift(current_original, tmp_path, monkeypatch, mutate):
    root, _, _, receipt, consumer = current_original
    mutate(receipt)
    reseal(receipt)
    path = tmp_path / "mutated-receipt.json"
    raw = fixture.write_json(path, receipt)
    path.chmod(0o600)
    approval_path, now = synthetic_approval(tmp_path, monkeypatch, raw, receipt, consumer)
    # First prove the signature/byte binding is valid; then exercise the full gate.
    consumer._verify_release_approval(approval_path, receipt_raw=raw, receipt=receipt, now=now)
    with pytest.raises(ValueError):
        verify_full(consumer, root, path, approval_path, now)
