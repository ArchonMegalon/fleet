"""Exact qualified v3 receipt interoperability; RFC signatures, no activation."""
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
# Original run 34871784422 / artifact 10359371457, reviewed against exact main.
# Original evidence stays external and byte-immutable; RFC signatures are test-only.
ORIGINAL_RECEIPT_SHA256 = "fe805b88d4eb2d6359f4b78b7b156894ac05c3ed99474a1ebedc93e1489b9410"
CURRENT_CONSUMER_SHA256 = "3217d44a653c21e604de6383b7b200e36749865c5e343fd1c1983be7261ee07c"


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
def current_source(monkeypatch):
    if not os.environ.get(EXTERNAL_INPUTS[0]):
        pytest.skip("exact bound Android checkout not supplied for compatibility")
    root = Path(os.environ[EXTERNAL_INPUTS[0]]).resolve(strict=True)
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
    pinned = {
        path: CURRENT_CONSUMER_SHA256,
        root / approval.PROVENANCE_VALIDATOR_PATH: approval.PROVENANCE_VALIDATOR_SHA256,
        root / "scripts/materialize-android-p0-pr-authority.py": "a6f943e199c8572fe02e9663e58bbb81b7cdc21dfd4f1cf78cd8d0778066d4c7",
        root / "scripts/materialize-api36-hosted-arm64-candidate.py": "8fa8669f4c9c0dc901a853f3675dd14d8e8eb08b82ed0fb90e266537b7500f6a",
        root / approval.QUALIFIED_WORKFLOW["path"]: approval.QUALIFIED_WORKFLOW["sha256"],
        root / approval.QUALIFIED_TWO_GREEN_POLICY["path"]: approval.QUALIFIED_TWO_GREEN_POLICY["sha256"],
        root / "eng/api36-proof-environment-authority.json": approval.QUALIFIED_ENVIRONMENT_POLICY["sha256"],
        root / approval.QUALIFIED_WIZARD_GATE["contractPath"]: approval.QUALIFIED_WIZARD_GATE["contractSha256"],
        root / approval.RELEASE_APPROVER_PUBLIC_KEY_PATH: approval.RELEASE_APPROVER_PUBLIC_KEY_PEM_SHA256,
    }
    before = {file: file.read_bytes() for file in pinned}
    assert {file: hashlib.sha256(raw).hexdigest() for file, raw in before.items()} == pinned
    assert len(before[root / approval.QUALIFIED_WORKFLOW["path"]]) == approval.QUALIFIED_WORKFLOW["sizeBytes"]
    assert (root / approval.RELEASE_APPROVER_PUBLIC_KEY_PATH).read_bytes() != fixture.ANDROID_388_PUBLIC_KEY.read_bytes()
    monkeypatch.syspath_prepend(str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("current_android_full_consumer_test", path)
    assert spec and spec.loader
    consumer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer)
    # Verify the production public pin before any in-memory RFC substitution.
    public_path, pem_sha256 = consumer._release_approval_key(approval.RELEASE_APPROVER_KEY_ID)
    assert public_path == root / approval.RELEASE_APPROVER_PUBLIC_KEY_PATH
    assert pem_sha256 == approval.RELEASE_APPROVER_PUBLIC_KEY_PEM_SHA256
    public_der = subprocess.run(
        ["/usr/bin/openssl", "pkey", "-pubin", "-outform", "DER"],
        input=before[public_path], check=True, capture_output=True,
    ).stdout
    assert base64.b64encode(public_der).decode() == approval.RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64
    assert hashlib.sha256(public_der).hexdigest() == approval.RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256
    yield root, consumer
    assert {file: file.read_bytes() for file in before} == before
    assert subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD", "HEAD^{tree}"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines() == identity
    assert subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=True, capture_output=True, text=True,
    ).stdout == ""


@pytest.fixture
def current_original(current_source):
    if not os.environ.get(EXTERNAL_INPUTS[1]):
        pytest.skip("exact original qualified Two-Green receipt not supplied")
    root, consumer = current_source
    receipt_path = Path(os.environ[EXTERNAL_INPUTS[1]]).resolve(strict=True)
    raw = receipt_path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_RECEIPT_SHA256
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
        key_id=approval.RELEASE_APPROVER_KEY_ID,
    )
    signed = dict(unsigned)
    assert signed["keyId"] == "fleet-release-approver-2026-09"
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
    monkeypatch.setitem(consumer.RELEASE_APPROVAL_ONLY_KEYS, approval.RELEASE_APPROVER_KEY_ID,
                        (public_path, hashlib.sha256(public).hexdigest()))
    return approval_path, now


def verify_full(consumer, root, receipt_path, approval_path, now):
    return consumer.verify_release_eligibility(
        receipt_path, approval_path, android_root=root,
        expected_version_name=approval.VERSION_NAME, expected_version_code=approval.VERSION_CODE,
        approval_effective_time=now,
    )


def test_qualified_consumer_policy_stays_dormant_before_evidence_or_key_access(monkeypatch):
    class NoKeyAccess(dict):
        def get(self, *args, **kwargs):
            pytest.fail("dormant issuance accessed the key environment")

    def no_sign(*args, **kwargs):
        pytest.fail("dormant issuance reached signing")

    monkeypatch.setattr(approval, "sign_ed25519", no_sign)
    args = argparse.Namespace(policy=fixture.POLICY, **fixture.inputs())
    with pytest.raises(approval.ApprovalError, match="policy state is dormant"):
        approval.create_approval_bundle(args, NoKeyAccess(), now=fixture.NOW)


def test_qualified_commit_cannot_substitute_a_different_main_with_same_tree():
    inputs = fixture.inputs()
    inputs["main_commit"] = "d" * 40
    assert inputs["main_tree"] == approval.ANDROID_CONSUMER_TREE
    with pytest.raises(approval.ApprovalError, match="exactly bound consumer"):
        approval.validate_inputs(argparse.Namespace(**inputs))


def test_qualified_source_must_still_equal_observed_protected_main(tmp_path, monkeypatch):
    _, _, _, args, environment = fixture.full_case(tmp_path, monkeypatch)
    branch = json.loads(args.android_main_branch_snapshot.read_bytes())
    branch["commit"]["sha"] = "d" * 40
    fixture.write_json(args.android_main_branch_snapshot, branch)
    monkeypatch.setattr(approval, "sign_ed25519", lambda *a, **k: pytest.fail("unexpected signing"))
    with pytest.raises(approval.ApprovalError, match="current Android main branch"):
        approval.create_approval_bundle(args, environment, now=fixture.NOW)


def test_bound_graph_is_derived_by_actual_android_producers(current_source):
    root, consumer = current_source
    producer = consumer.TWO_GREEN
    expected = fixture.qualified_dependency_graph()
    android = producer.P0.git_identity(root)
    sources = dict(expected["sources"], android=android)
    candidate = {"sources": sources, "dependencyMode": expected["mode"]}
    # Reuse the actual P0 commit constraints and Two-Green normalization, not
    # Fleet's own hash function. This does not remeasure sibling source trees.
    graph = producer.P0.validate_dependency_graph(candidate)
    result = producer.normalized_dependency_authority(
        p0={
            "dependencyGraph": graph,
            "githubRun": {"eventSha": android["commit"]},
            "androidSource": {
                "checkedOutHead": android["commit"], "checkedOutTree": android["tree"],
                "repository": android["repository"],
            },
        },
        local_tree=android["tree"], role="synthetic-compatibility",
    )
    assert result == expected
    assert result["sha256"] == approval.QUALIFIED_DEPENDENCY_GRAPH_SHA256


def test_synthetic_current_signature_is_compatible_but_not_hosted_eligibility(current_source, tmp_path, monkeypatch):
    root, consumer = current_source
    receipt = fixture.receipt()  # Deliberately incomplete synthetic CI metadata.
    path = tmp_path / "SYNTHETIC-NOT-HOSTED-receipt.json"
    raw = fixture.write_json(path, receipt)
    path.chmod(0o600)
    approval_path, now = synthetic_approval(tmp_path, monkeypatch, raw, receipt, consumer)
    result = consumer._verify_release_approval(approval_path, receipt_raw=raw, receipt=receipt, now=now)
    assert result["contractName"] == approval.OUTPUT_CONTRACT
    assert result["keyId"] == approval.RELEASE_APPROVER_KEY_ID
    for name in ("signingAuthorized", "publicationAuthorized", "googlePlayUploadAuthorized"):
        assert json.loads(approval_path.read_bytes())[name] is False
    with pytest.raises(ValueError):
        verify_full(consumer, root, path, approval_path, now)


@pytest.mark.parametrize("field,value", [
    ("keyId", "unknown-approver"),
    ("keyId", "fleet-release-builder-2026-09"),
    ("role", "android_internal_release_builder"),
    ("approvalScope", "android_internal_release_artifact_binding"),
    ("sourceCommit", "d" * 40),
    ("sourceTree", fixture.OLD_CONSUMER_TREE),
    ("receiptSha256", "0" * 64),
    ("provenanceValidatorSha256", "0" * 64),
    ("publicationAuthorized", True),
    ("unexpected", True),
])
def test_actual_current_signature_consumer_rejects_resigned_drift(current_source, tmp_path, monkeypatch, field, value):
    _, consumer = current_source
    receipt = fixture.receipt()
    raw = approval.canonical_bytes(receipt)
    path, now = synthetic_approval(tmp_path, monkeypatch, raw, receipt, consumer)
    signed = json.loads(path.read_bytes())
    signed[field] = value
    unsigned = {key: member for key, member in signed.items() if key != "signatureBase64"}
    signed["signatureBase64"] = approval.sign_ed25519(
        approval.android_canonical_bytes(unsigned), approval.expected_policy(),
        {approval.KEY_ENV_NAME: base64.b64encode(fixture.TEST_PRIVATE_DER).decode()},
    )["signatureBase64"]
    fixture.write_json(path, signed)
    key_reads = []
    public_paths = {consumer.RELEASE_APPROVER_PUBLIC_KEY,
                    *(binding[0] for binding in consumer.RELEASE_APPROVAL_ONLY_KEYS.values())}
    stable_bytes = consumer._stable_bytes

    def tracked_bytes(path, **kwargs):
        if path in public_paths:
            key_reads.append(path)
        return stable_bytes(path, **kwargs)

    monkeypatch.setattr(consumer, "_stable_bytes", tracked_bytes)
    with pytest.raises(ValueError):
        consumer._verify_release_approval(path, receipt_raw=raw, receipt=receipt, now=now)
    assert key_reads == []


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
