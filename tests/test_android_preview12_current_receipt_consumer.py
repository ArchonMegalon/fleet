"""Guarded PR12 loader plus full current Android v3 eligibility verification.

Only RFC 8032 test signatures authorize test-loaded trust; no operational
approval, custody, APK replay, signing or release-build claim is made here.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

import test_android_preview12_external_rebuilder as fixture

COMMIT = "7cef6a715867cab8000483b08db9aad2e817f63d"
TREE = "534f6dc0cde043fb78475c35e9116a727a9e95f5"
RECEIPT_SHA = "ce3a64d3bebd9a51eb7c6528491d55f8082ba21948d5570bee61cb08abf964f2"
ELIGIBILITY_SHA = "02bf7c59adc83d66bd24e6081f4c760cbf3b1f7d751c85b7a0cf5357ee506768"
PROVENANCE_SHA = "d0e1938107a3794a44648286b8b97d1ac3db64daa30509f1e63fe78018d3f4c7"
RFC_DER = bytes.fromhex("302e020100300506032b657004220420" +
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def loaded_original():
    root_value = os.environ.get("CHUMMER_ANDROID_CURRENT_ROOT")
    receipt_value = os.environ.get("CHUMMER_ANDROID_CURRENT_TWO_GREEN_RECEIPT")
    if not root_value or not receipt_value:
        pytest.skip("exact current Android root and original qualified receipt are required")
    root, path = Path(root_value).resolve(strict=True), Path(receipt_value).resolve(strict=True)
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RECEIPT_SHA
    assert git(root, "rev-parse", "HEAD", "HEAD^{tree}").splitlines() == [COMMIT, TREE]
    assert git(root, "status", "--porcelain") == ""
    fleet = fixture.load_module()
    lock, _ = fleet.load_lock(fixture.LOCK)
    # Real pre/post Git-object closure, direct hashes, imports, public trust and
    # contract validation. This is not a direct import bypassing PR12's loader.
    android = fleet.validate_android_consumer(root, lock)
    assert android.CONTRACT == "chummer.android.release-build-attestation/v2"
    assert android.EXTERNAL_SIGNER_REQUEST_CONTRACT == fleet.REQUEST_CONTRACT
    assert fleet.EXTERNAL_SIGNER_ATTESTATION_CONTRACT == "chummer.android.external-release-signer-attestation/v1"
    assert hashlib.sha256(android.VERIFY.TWO_GREEN_PATH.read_bytes()).hexdigest() == PROVENANCE_SHA
    yield root, path, raw, json.loads(raw), android.VERIFY
    fleet._validate_android_consumer_inputs(root, COMMIT)
    assert git(root, "status", "--porcelain") == ""
    assert path.read_bytes() == raw


def synthetic_approval(tmp_path, monkeypatch, verifier, receipt, raw):
    """Build unchanged v1 bytes using the actual Android projection, RFC only."""
    now = datetime.fromisoformat(receipt["decisionTimeUtc"].replace("Z", "+00:00")) + timedelta(minutes=1)
    unsigned = verifier.release_approval_unsigned(
        raw, receipt, generated_at_utc=now.isoformat().replace("+00:00", "Z"),
        expires_at_utc=(now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        challenge_nonce="9" * 64, provenance_validator_sha256=PROVENANCE_SHA,
        provenance_replay_sha256=hashlib.sha256(b"TEST ONLY: not hosted provenance or protected approval").hexdigest(),
    )
    key_fd, message_fd = os.memfd_create("RFC8032-key"), os.memfd_create("test-approval")
    try:
        os.write(key_fd, RFC_DER)
        os.write(message_fd, verifier._canonical_json_bytes(unsigned))
        os.lseek(key_fd, 0, os.SEEK_SET)
        os.lseek(message_fd, 0, os.SEEK_SET)
        signature = subprocess.run(
            ["/usr/bin/openssl", "pkeyutl", "-sign", "-rawin", "-inkey", f"/proc/self/fd/{key_fd}",
             "-keyform", "DER", "-in", f"/proc/self/fd/{message_fd}"],
            pass_fds=(key_fd, message_fd), check=True, capture_output=True, timeout=10,
        ).stdout
    finally:
        os.close(key_fd)
        os.close(message_fd)
    public = subprocess.run(
        ["/usr/bin/openssl", "pkey", "-inform", "DER", "-pubout"],
        input=RFC_DER, check=True, capture_output=True, timeout=10,
    ).stdout
    public_path = tmp_path / "RFC8032-TEST-ONLY-public.pem"
    public_path.write_bytes(public)
    public_path.chmod(0o600)
    monkeypatch.setattr(verifier, "RELEASE_APPROVER_PUBLIC_KEY", public_path)
    monkeypatch.setattr(verifier, "RELEASE_APPROVER_PUBLIC_KEY_SHA256", hashlib.sha256(public).hexdigest())
    approval_path = tmp_path / "RFC8032-TEST-ONLY-approval.json"
    approval_path.write_bytes(verifier._canonical_json_bytes({**unsigned, "signatureBase64": base64.b64encode(signature).decode()}))
    approval_path.chmod(0o600)
    return approval_path, now


def verify(verifier, root, receipt_path, approval_path, now):
    return verifier.verify_release_eligibility(
        receipt_path, approval_path, android_root=root,
        expected_version_name="0.1.0-preview.12", expected_version_code=12,
        approval_effective_time=now,
    )


def test_original_v3_receipt_passes_full_consumer_through_guarded_loader(loaded_original, tmp_path, monkeypatch):
    root, path, raw, receipt, verifier = loaded_original
    approval_path, now = synthetic_approval(tmp_path, monkeypatch, verifier, receipt, raw)
    result = verify(verifier, root, path, approval_path, now)
    assert result["contractName"] == "chummer.android.api36-ordered-review-main-green-eligibility/v3"
    assert result["receiptSha256"] == RECEIPT_SHA
    assert result["eligibilitySha256"] == ELIGIBILITY_SHA
    assert (result["sourceCommit"], result["sourceTree"]) == (COMMIT, TREE)
    assert result["eligible"] is True and result["internalTestingEligible"] is True
    assert result["publicationAuthorized"] is False and result["googlePlayUploadAuthorized"] is False


@pytest.mark.parametrize("mutation", ["scope", "missing-journey", "runtime-content"])
def test_validly_resigned_original_drift_fails_full_current_consumer(loaded_original, tmp_path, monkeypatch, mutation):
    root, _, _, receipt, verifier = loaded_original
    common = receipt["commonAuthority"]
    if mutation == "scope":
        common["proofScope"] = "full_product"
    elif mutation == "missing-journey":
        common["requiredJourneys"].pop()
    else:
        graph = common["dependencyGraph"]
        graph["sources"]["core-content"] = dict(graph["sources"]["core-runtime"])
        graph["sha256"] = hashlib.sha256(verifier._canonical_json_bytes({k: v for k, v in graph.items() if k != "sha256"})).hexdigest()
    receipt.pop("eligibilitySha256")
    receipt["eligibilitySha256"] = hashlib.sha256(verifier._canonical_json_bytes(receipt)).hexdigest()
    raw = verifier._canonical_json_bytes(receipt)
    receipt_path = tmp_path / "changed-receipt.json"
    receipt_path.write_bytes(raw)
    receipt_path.chmod(0o600)
    approval_path, now = synthetic_approval(tmp_path, monkeypatch, verifier, receipt, raw)
    verifier._verify_release_approval(approval_path, receipt_raw=raw, receipt=receipt, now=now)
    with pytest.raises(ValueError):
        verify(verifier, root, receipt_path, approval_path, now)
