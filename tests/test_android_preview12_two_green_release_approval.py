from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import textwrap
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/android_preview12_two_green_release_approval.py"
POLICY = ROOT / "config/release/android-preview12-two-green-release-approval.json"
WORKFLOW = ROOT / ".github/workflows/android-preview12-two-green-release-approval.yml"
ANDROID_388_FIXTURE = ROOT / "tests/fixtures/android-388425ace/release-approval-contract.json"
ANDROID_388_PUBLIC_KEY = ROOT / "tests/fixtures/android-388425ace/local-release-builder-2026.public.pem"
spec = importlib.util.spec_from_file_location("preview12_approval", SCRIPT)
assert spec and spec.loader
approval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(approval)

# RFC 8032 test-vector seed wrapped in the standard Ed25519 PKCS#8 DER envelope.
TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
TEST_PRIVATE_DER = bytes.fromhex("302e020100300506032b657004220420") + TEST_SEED
LEDGER_TEST_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
LEDGER_TEST_PRIVATE_DER = bytes.fromhex("302e020100300506032b657004220420") + LEDGER_TEST_SEED
NOW = datetime(2026, 9, 6, 14, 10, tzinfo=timezone.utc)
REVIEWERS = [{"id": 17, "login": "reviewer"}]


def write_json(path: Path, value: object) -> bytes:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(data)
    return data


def _test_public_der() -> bytes:
    key_fd = os.memfd_create("test-ed25519")
    try:
        os.write(key_fd, TEST_PRIVATE_DER)
        os.lseek(key_fd, 0, os.SEEK_SET)
        return approval._openssl(
            ["pkey", "-inform", "DER", "-in", f"/proc/self/fd/{key_fd}", "-pubout", "-outform", "DER"],
            pass_fds=(key_fd,),
        )
    finally:
        os.close(key_fd)


def use_test_approval_key(monkeypatch: pytest.MonkeyPatch) -> str:
    public = _test_public_der()
    digest = hashlib.sha256(public).hexdigest()
    monkeypatch.setattr(
        approval, "RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64",
        base64.b64encode(public).decode(),
    )
    monkeypatch.setattr(
        approval, "RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256", digest
    )
    return digest


def active_policy(tmp_path: Path, *, durable: bool = False) -> tuple[dict, Path, str]:
    value = json.loads(POLICY.read_text())
    value["state"] = "ready"
    value["github_environment"]["configured"] = True
    value["github_environment"]["expected_human_user_reviewers"] = REVIEWERS
    value["external_ed25519_key"]["configured"] = True
    value["activation"]["enabled"] = True
    value["external_ed25519_key"]["public_key_spki_der_base64"] = (
        approval.RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64
    )
    value["external_ed25519_key"]["expected_public_key_spki_sha256"] = (
        approval.RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256
    )
    public_digest = approval.RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256
    if durable:
        key_fd = os.memfd_create("test-ledger-ed25519-public")
        try:
            os.write(key_fd, LEDGER_TEST_PRIVATE_DER)
            os.lseek(key_fd, 0, os.SEEK_SET)
            ledger_public = approval._openssl(
                ["pkey", "-inform", "DER", "-in", f"/proc/self/fd/{key_fd}", "-pubout", "-outform", "DER"],
                pass_fds=(key_fd,),
            )
        finally:
            os.close(key_fd)
        ledger_public_digest = hashlib.sha256(ledger_public).hexdigest()
        ledger = value["replay_protection"]["external_ledger"]
        ledger.update({
            "configured": True,
            "base_url": "https://approval-ledger.example.test",
            "allowed_hosts": ["approval-ledger.example.test"],
            "expected_service_identity": "chummer.preview12.approval-ledger",
            "receipt_public_key_spki_der_base64": base64.b64encode(ledger_public).decode(),
            "receipt_public_key_spki_sha256": ledger_public_digest,
        })
        value["replay_protection"]["durable_external_reservation_configured"] = True
        value["replay_protection"]["authority_complete"] = True
    path = tmp_path / "policy.json"
    write_json(path, value)
    return value, path, public_digest


def ledger_reservation(policy: dict, policy_path: Path, values: dict[str, object]) -> dict:
    ledger = approval.approval_ledger
    policy_sha256 = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    subject = ledger.make_subject(
        approval_request_nonce=str(values["approval_request_nonce"]),
        two_green_artifact_id=int(str(values["two_green_artifact_id"])),
        two_green_artifact_sha256=str(values["two_green_artifact_sha256"]),
        two_green_receipt_sha256=str(values["two_green_receipt_sha256"]),
        main_tree=str(values["main_tree"]),
        policy_sha256=policy_sha256,
        version_name=str(values["version_name"]),
        version_code=int(str(values["version_code"])),
    )
    request = ledger._request("reserve", subject)
    statement = {
        "contractName": ledger.RECEIPT_CONTRACT,
        "contractVersion": 1,
        "serviceIdentity": policy["replay_protection"]["external_ledger"]["expected_service_identity"],
        "requestId": request["requestId"],
        "operation": "reserve",
        "subject": subject,
        "subjectSha256": request["subjectSha256"],
        "reservationId": "rsv_abcdefghijklmnop",
        "state": "reserved",
        "revision": 1,
        "reservedAtUtc": "2026-09-06T14:01:00Z",
        "updatedAtUtc": "2026-09-06T14:01:00Z",
        "leaseExpiresAtUtc": "2026-09-06T14:16:00Z",
        "priorReservation": None,
        "uniquenessSubjects": ledger.UNIQUENESS_SUBJECTS,
        "durabilityClass": "external_durable",
        "exactlyOnce": True,
        "approval": None,
        "abort": None,
    }
    key_fd = os.memfd_create("test-ledger-ed25519")
    message_fd = os.memfd_create("test-ledger-message")
    try:
        os.write(key_fd, LEDGER_TEST_PRIVATE_DER)
        os.lseek(key_fd, 0, os.SEEK_SET)
        os.write(message_fd, ledger.canonical_bytes(statement))
        os.lseek(message_fd, 0, os.SEEK_SET)
        signature = approval._openssl(
            ["pkeyutl", "-sign", "-rawin", "-inkey", f"/proc/self/fd/{key_fd}",
             "-keyform", "DER", "-in", f"/proc/self/fd/{message_fd}"],
            pass_fds=(key_fd, message_fd),
        )
    finally:
        os.close(key_fd)
        os.close(message_fd)
    return {
        "contractName": ledger.RESPONSE_CONTRACT,
        "contractVersion": 1,
        "receipt": statement,
        "receiptSha256": ledger.canonical_sha256(statement),
        "signature": {
            "algorithm": "Ed25519",
            "publicKeySpkiSha256": policy["replay_protection"]["external_ledger"]["receipt_public_key_spki_sha256"],
            "signatureBase64": base64.b64encode(signature).decode(),
        },
    }


def inputs() -> dict[str, object]:
    return {
        "approval_request_nonce": "9" * 64,
        "two_green_run_id": "301",
        "two_green_run_attempt": "1",
        "two_green_artifact_id": "401",
        "two_green_artifact_sha256": "0" * 64,
        "two_green_receipt_sha256": "0" * 64,
        "review_run_id": "101",
        "review_pull_request_number": "45",
        "main_run_id": "201",
        "main_commit": approval.ANDROID_CONSUMER_COMMIT,
        "main_tree": approval.ANDROID_CONSUMER_TREE,
        "version_name": approval.VERSION_NAME,
        "version_code": str(approval.VERSION_CODE),
    }


def execution(**changes) -> dict[str, object]:
    value = {
        "execution_repository": approval.FLEET_REPOSITORY,
        "execution_ref": approval.FLEET_REF,
        "execution_ref_protected": "true",
        "execution_event": "workflow_dispatch",
        "execution_sha": "c" * 40,
        "workflow_repository": approval.FLEET_REPOSITORY,
        "workflow_ref": f"{approval.FLEET_REPOSITORY}/{approval.WORKFLOW_PATH}@refs/heads/main",
        "workflow_sha": "c" * 40,
        "execution_run_id": "501",
        "execution_run_attempt": "1",
        "execution_environment": approval.ENVIRONMENT_NAME,
    }
    value.update(changes)
    return value


def receipt() -> dict:
    value = {
        "schema": approval.TWO_GREEN_CONTRACT,
        "status": "pass",
        "eligibilityScope": "current_preview_internal_testing_candidate",
        "eligible": True,
        "internalTestingEligible": True,
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
        "policyAuthority": {},
        "sourceCommit": approval.ANDROID_CONSUMER_COMMIT,
        "sourceTree": approval.ANDROID_CONSUMER_TREE,
        "releaseIdentity": {
            "packageId": approval.PACKAGE_ID,
            "versionName": approval.VERSION_NAME,
            "versionCode": approval.VERSION_CODE,
            "intentAuthority": "android_project_at_exact_main_tree",
        },
        "commonAuthority": {
            "androidTree": approval.ANDROID_CONSUMER_TREE,
            "environmentCompatibilityStatus": "pass",
            "dependencyGraph": {"sha256": "6" * 64},
            "environmentPolicy": {"sha256": "7" * 64},
        },
        "reviewRun": {
            "run": {"id": 101, "status": "completed", "conclusion": "success"},
            "aggregateStatus": "pass",
        },
        "mainRun": {
            "run": {"id": 201, "headSha": approval.ANDROID_CONSUMER_COMMIT, "status": "completed", "conclusion": "success"},
            "p0EventSha": approval.ANDROID_CONSUMER_COMMIT,
            "aggregateStatus": "pass",
        },
        "decisionTimeUtc": "2026-09-06T14:02:00Z",
        "reviewPullRequest": {
            "repository": approval.ANDROID_REPOSITORY,
            "number": 45,
        },
        "doesNotAssert": ["google_play_upload", "release_signing", "publication_authority"],
    }
    value["policyAuthority"] = {
        "path": "eng/api36-two-consecutive-green-authority.json",
        "publicationAuthorized": False,
        "schema": "chummer.android.api36-ordered-review-main-green-policy/v2",
        "sha256": "8" * 64,
        "sizeBytes": 1024,
    }
    value["eligibilitySha256"] = approval.canonical_sha256(value)
    return value


def archive(path: Path, data: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(approval.RECEIPT_NAME, data)
    output = buffer.getvalue()
    path.write_bytes(output)
    return output


def full_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch | None = None):
    if monkeypatch is not None:
        use_test_approval_key(monkeypatch)
    policy_value, policy_path, public_digest = active_policy(
        tmp_path, durable=monkeypatch is not None
    )
    receipt_value = receipt()
    receipt_bytes = write_json(tmp_path / "receipt.json", receipt_value)
    archive_bytes = archive(tmp_path / "artifact.zip", receipt_bytes)
    values = inputs()
    values["two_green_artifact_sha256"] = hashlib.sha256(archive_bytes).hexdigest()
    values["two_green_receipt_sha256"] = hashlib.sha256(receipt_bytes).hexdigest()
    run = {
        "id": 301,
        "run_attempt": 1,
        "name": approval.TWO_GREEN_WORKFLOW_NAME,
        "path": approval.TWO_GREEN_WORKFLOW_PATH,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": approval.ANDROID_CONSUMER_COMMIT,
        "status": "completed",
        "conclusion": "success",
        "created_at": "2026-09-06T14:02:10Z",
        "run_started_at": "2026-09-06T14:02:11Z",
        "updated_at": "2026-09-06T14:02:30Z",
        "url": f"https://api.github.com/repos/{approval.ANDROID_REPOSITORY}/actions/runs/301",
        "html_url": f"https://github.com/{approval.ANDROID_REPOSITORY}/actions/runs/301",
        "repository": {"id": 1331626697, "full_name": approval.ANDROID_REPOSITORY},
        "head_repository": {"id": 1331626697, "full_name": approval.ANDROID_REPOSITORY},
    }
    artifact_value = {
        "id": 401,
        "name": "chummer-android-api36-two-green-eligibility-101-201",
        "expired": False,
        "digest": f"sha256:{values['two_green_artifact_sha256']}",
        "size_in_bytes": len(archive_bytes),
        "url": f"https://api.github.com/repos/{approval.ANDROID_REPOSITORY}/actions/artifacts/401",
        "archive_download_url": f"https://api.github.com/repos/{approval.ANDROID_REPOSITORY}/actions/artifacts/401/zip",
        "workflow_run": {"id": 301, "head_sha": approval.ANDROID_CONSUMER_COMMIT},
        "created_at": "2026-09-06T14:02:35Z",
        "expires_at": "2026-10-06T14:02:35Z",
    }
    environment_value = {
        "name": approval.ENVIRONMENT_NAME,
        "url": f"https://api.github.com/repos/{approval.FLEET_REPOSITORY}/environments/{approval.ENVIRONMENT_NAME}",
        "can_admins_bypass": False,
        "deployment_branch_policy": {"protected_branches": True, "custom_branch_policies": False},
        "protection_rules": [{
            "type": "required_reviewers",
            "prevent_self_review": True,
            "reviewers": [{"type": "User", "reviewer": REVIEWERS[0]}],
        }],
    }
    write_json(tmp_path / "run.json", run)
    write_json(tmp_path / "artifact.json", artifact_value)
    write_json(tmp_path / "environment.json", environment_value)
    write_json(tmp_path / "android-main-branch.json", {
        "name": "main",
        "protected": True,
        "commit": {"sha": approval.ANDROID_CONSUMER_COMMIT},
    })
    write_json(tmp_path / "android-main-commit.json", {
        "sha": approval.ANDROID_CONSUMER_COMMIT,
        "url": f"https://api.github.com/repos/{approval.ANDROID_REPOSITORY}/git/commits/{approval.ANDROID_CONSUMER_COMMIT}",
        "tree": {"sha": approval.ANDROID_CONSUMER_TREE},
    })
    write_json(tmp_path / "fleet-main-branch.json", {
        "name": "main",
        "protected": True,
        "commit": {"sha": "c" * 40},
    })
    write_json(tmp_path / "fleet-main-commit.json", {
        "sha": "c" * 40,
        "url": f"https://api.github.com/repos/{approval.FLEET_REPOSITORY}/git/commits/{'c' * 40}",
        "tree": {"sha": "f" * 40},
    })
    write_json(tmp_path / "approval-artifact-ledger.json", {
        "total_count": 0,
        "artifacts": [],
    })
    args = argparse.Namespace(
        policy=policy_path,
        **values,
        **execution(),
        environment_snapshot=(tmp_path / "environment.json").resolve(),
        ledger_reservation_snapshot=(tmp_path / "ledger-reservation.json").resolve(),
        run_snapshot=(tmp_path / "run.json").resolve(),
        artifact_snapshot=(tmp_path / "artifact.json").resolve(),
        artifact_archive=(tmp_path / "artifact.zip").resolve(),
        android_main_branch_snapshot=(tmp_path / "android-main-branch.json").resolve(),
        android_main_commit_snapshot=(tmp_path / "android-main-commit.json").resolve(),
        fleet_main_branch_snapshot=(tmp_path / "fleet-main-branch.json").resolve(),
        fleet_main_commit_snapshot=(tmp_path / "fleet-main-commit.json").resolve(),
        approval_artifact_ledger_snapshot=(tmp_path / "approval-artifact-ledger.json").resolve(),
        output=(tmp_path / approval.OUTPUT_NAME).resolve(),
        audit_output=(tmp_path / approval.AUDIT_OUTPUT_NAME).resolve(),
    )
    if monkeypatch is not None:
        write_json(
            args.ledger_reservation_snapshot,
            ledger_reservation(policy_value, policy_path, values),
        )
    environment = {approval.KEY_ENV_NAME: base64.b64encode(TEST_PRIVATE_DER).decode()}
    return policy_value, public_digest, receipt_value, args, environment


def test_checked_in_policy_is_exact_dormant_and_contains_no_key_material():
    value, data, _ = approval.load_policy(POLICY.resolve())
    assert value == approval.expected_policy()
    assert value["state"].startswith("dormant")
    assert value["activation"]["enabled"] is False
    assert value["github_environment"]["configured"] is False
    assert value["external_ed25519_key"]["configured"] is False
    assert value["external_ed25519_key"]["key_id"] == "local-release-builder-2026"
    assert value["external_ed25519_key"]["expected_public_key_spki_sha256"] == (
        approval.RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256
    )
    assert value["android_consumer"]["qualified_commit"] == approval.ANDROID_CONSUMER_COMMIT
    assert value["android_consumer"]["provenance_validator_sha256"] == (
        approval.PROVENANCE_VALIDATOR_SHA256
    )
    assert value["replay_protection"]["durable_external_reservation_required"] is True
    assert value["replay_protection"]["durable_reservation_subjects"] == [
        "two_green_artifact_id",
        "approval_request_nonce",
    ]
    assert value["replay_protection"]["durable_external_reservation_configured"] is False
    assert value["replay_protection"]["authority_complete"] is False
    assert value["replay_protection"]["mode"] == "durable_external_exactly_once"
    assert value["replay_protection"]["external_ledger"] == approval.approval_ledger.dormant_ledger_policy()
    assert value["replay_protection"]["external_ledger"]["base_url"] is None
    assert value["replay_protection"]["external_ledger"]["allowed_hosts"] == []
    assert b"PRIVATE KEY" not in data
    assert base64.b64encode(TEST_PRIVATE_DER) not in data


def test_dormant_preflight_fails_before_environment_or_key_access():
    value, _, _ = approval.load_policy(POLICY.resolve())
    args = argparse.Namespace(**inputs(), **{key: value for key, value in execution().items() if not key.startswith("execution_run") and key != "execution_environment"})
    with pytest.raises(approval.ApprovalError, match="policy state is dormant"):
        approval.validate_dispatch(value, args)


def test_environment_key_activation_still_fails_without_durable_replay(tmp_path: Path):
    policy, _, _ = active_policy(tmp_path)
    args = argparse.Namespace(
        **inputs(),
        **{
            key: value
            for key, value in execution().items()
            if not key.startswith("execution_run")
            and key != "execution_environment"
        },
    )
    with pytest.raises(approval.ApprovalError, match="durable external replay"):
        approval.validate_dispatch(policy, args)


def test_ready_policy_rejects_shared_approval_and_ledger_signing_key(tmp_path: Path):
    policy, policy_path, approval_digest = active_policy(tmp_path, durable=True)
    approval_public = base64.b64decode(
        policy["external_ed25519_key"]["public_key_spki_der_base64"], validate=True
    )
    ledger_policy = policy["replay_protection"]["external_ledger"]
    ledger_policy["receipt_public_key_spki_der_base64"] = base64.b64encode(
        approval_public
    ).decode()
    ledger_policy["receipt_public_key_spki_sha256"] = approval_digest
    write_json(policy_path, policy)
    with pytest.raises(approval.ApprovalError, match="must be distinct"):
        approval.load_policy(policy_path.resolve())
    with pytest.raises(approval.ApprovalError, match="not distinct"):
        approval._require_ready(policy)


@pytest.mark.parametrize("change", [
    {"execution_ref": "refs/heads/feature"},
    {"execution_ref_protected": "false"},
    {"execution_repository": approval.ANDROID_REPOSITORY},
    {"workflow_sha": "d" * 40},
    {"version_name": "0.1.0-preview.13"},
    {"version_code": "13"},
])
def test_active_preflight_rejects_context_or_release_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change
):
    policy, policy_path, _ = active_policy(tmp_path, durable=True)
    values = {**inputs(), **execution(), **change}
    values.pop("execution_run_id", None)
    values.pop("execution_run_attempt", None)
    values.pop("execution_environment", None)
    args = argparse.Namespace(**values)
    with pytest.raises(approval.ApprovalError):
        approval.validate_dispatch(policy, args)
    assert policy_path.exists()


def test_future_ready_preflight_accepts_exact_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    policy, _, _ = active_policy(tmp_path, durable=True)
    values = {**inputs(), **execution()}
    values.pop("execution_run_id")
    values.pop("execution_run_attempt")
    values.pop("execution_environment")
    assert approval.validate_dispatch(policy, argparse.Namespace(**values))["ok"] is True


def test_environment_requires_human_reviewer_self_review_prevention_and_protected_main(tmp_path: Path):
    policy, _, _ = active_policy(tmp_path)
    base = {
        "name": approval.ENVIRONMENT_NAME,
        "url": f"https://api.github.com/repos/{approval.FLEET_REPOSITORY}/environments/{approval.ENVIRONMENT_NAME}",
        "can_admins_bypass": False,
        "deployment_branch_policy": {"protected_branches": True, "custom_branch_policies": False},
        "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True,
                              "reviewers": [{"type": "User", "reviewer": REVIEWERS[0]}]}],
    }
    assert approval.validate_environment_snapshot(base, policy)["requiredReviewerCount"] == 1
    for mutation in (
        lambda value: value["protection_rules"].clear(),
        lambda value: value["protection_rules"][0].update(prevent_self_review=False),
        lambda value: value["deployment_branch_policy"].update(protected_branches=False),
        lambda value: value.update(can_admins_bypass=True),
        lambda value: value["protection_rules"][0].update(reviewers=[]),
        lambda value: value["protection_rules"][0].update(reviewers=[{"type": "Team", "reviewer": {"id": 7}}]),
        lambda value: value["protection_rules"][0].update(reviewers=[
            {"type": "User", "reviewer": REVIEWERS[0]},
            {"type": "Team", "reviewer": {"id": 8}},
        ]),
        lambda value: value["protection_rules"][0]["reviewers"][0]["reviewer"].update(id=18),
    ):
        changed = json.loads(json.dumps(base))
        mutation(changed)
        with pytest.raises(approval.ApprovalError):
            approval.validate_environment_snapshot(changed, policy)


def test_exact_two_green_receipt_emits_only_public_non_authorizing_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, public_digest, _, args, environment = full_case(tmp_path, monkeypatch)
    result, audit = approval.create_approval_bundle(args, environment, now=NOW)
    approval.validate_approval(
        result, policy=approval.load_policy(args.policy)[0],
        audit_receipt=audit, expected_challenge_nonce="9" * 64, now=NOW,
    )
    assert set(result) == {
        "contractName", "algorithm", "keyId", "role", "approvalScope",
        "generatedAtUtc", "expiresAtUtc", "challengeNonce",
        "provenanceValidatorSha256", "provenanceReplaySha256",
        "receiptSha256", "eligibilitySha256", "sourceCommit", "sourceTree",
        "versionName", "versionCode", "dependencyGraphSha256",
        "environmentPolicySha256", "signingAuthorized",
        "publicationAuthorized", "googlePlayUploadAuthorized", "signatureBase64",
    }
    assert result["contractName"] == "chummer.android.two-green-release-approval/v1"
    assert result["keyId"] == "local-release-builder-2026"
    assert result["role"] == "android_internal_release_approver"
    assert result["approvalScope"] == "android_internal_release_preparation"
    assert result["provenanceReplaySha256"] == approval.canonical_sha256(audit)
    assert public_digest == approval.RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256
    assert result["signingAuthorized"] is False
    assert result["publicationAuthorized"] is False
    assert result["googlePlayUploadAuthorized"] is False
    serialized = approval.pretty_bytes(result)
    assert base64.b64encode(TEST_PRIVATE_DER) not in serialized
    assert b"keystore" not in serialized.lower()
    assert b'"aab"' not in serialized.lower()
    assert b'"aabsha256"' not in serialized.lower()


def test_android_388_fixture_matches_fleet_policy_and_signed_byte_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fixture = json.loads(ANDROID_388_FIXTURE.read_text())
    pem = ANDROID_388_PUBLIC_KEY.read_bytes()
    assert hashlib.sha256(pem).hexdigest() == fixture["publicKeyPemSha256"]
    completed = subprocess.run(
        ["openssl", "pkey", "-pubin", "-outform", "DER"],
        input=pem, check=True, capture_output=True,
    )
    assert base64.b64encode(completed.stdout).decode() == fixture["publicKeySpkiDerBase64"]
    assert hashlib.sha256(completed.stdout).hexdigest() == fixture["publicKeySpkiDerSha256"]
    policy = approval.expected_policy()
    assert policy["android_consumer"]["qualified_commit"] == fixture["androidCommit"]
    assert policy["android_consumer"]["qualified_tree"] == fixture["androidTree"]
    assert policy["android_consumer"]["provenance_validator_sha256"] == fixture[
        "provenanceValidatorSha256"
    ]
    assert policy["external_ed25519_key"]["trusted_public_key_pem_sha256"] == fixture[
        "publicKeyPemSha256"
    ]
    assert policy["external_ed25519_key"]["expected_public_key_spki_sha256"] == fixture[
        "publicKeySpkiDerSha256"
    ]

    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    result, audit = approval.create_approval_bundle(args, environment, now=NOW)
    unsigned = {key: value for key, value in result.items() if key != "signatureBase64"}
    assert sorted(unsigned) == fixture["signedFields"]
    assert set(result) == {*fixture["signedFields"], fixture["signatureField"]}
    reference_bytes = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert approval.android_canonical_bytes(unsigned) == reference_bytes
    assert not reference_bytes.endswith(b"\n")
    approval.validate_approval(
        result,
        policy=approval.load_policy(args.policy)[0],
        audit_receipt=audit,
        expected_challenge_nonce="9" * 64,
        now=NOW,
    )


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda value: value.update(provenanceValidatorSha256="0" * 64), "source/version"),
        (lambda value: value.update(sourceCommit="0" * 40), "source/version"),
        (lambda value: value.update(versionCode=13), "source/version"),
        (lambda value: value.update(receiptSha256="0" * 64), "claims differ"),
        (lambda value: value.update(unexpected=True), "fields are not exact"),
    ],
)
def test_android_388_consumer_rejects_validly_resigned_contract_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate, match: str
):
    policy, _, _, args, environment = full_case(tmp_path, monkeypatch)
    result, audit = approval.create_approval_bundle(args, environment, now=NOW)
    mutate(result)
    unsigned = {key: value for key, value in result.items() if key != "signatureBase64"}
    result["signatureBase64"] = approval.sign_ed25519(
        approval.android_canonical_bytes(unsigned), policy, environment
    )["signatureBase64"]
    with pytest.raises(approval.ApprovalError, match=match):
        approval.validate_approval(
            result, policy=policy, audit_receipt=audit,
            expected_challenge_nonce="9" * 64, now=NOW,
        )


def test_android_388_consumer_rejects_replayed_challenge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    policy, _, _, args, environment = full_case(tmp_path, monkeypatch)
    result, audit = approval.create_approval_bundle(args, environment, now=NOW)
    with pytest.raises(approval.ApprovalError, match="replayed"):
        approval.validate_approval(
            result, policy=policy, audit_receipt=audit,
            expected_challenge_nonce="8" * 64, now=NOW,
        )


@pytest.mark.parametrize("mutate,match", [
    (lambda value: value.update(sourceTree="d" * 40), "Android identity differs"),
    (lambda value: value["releaseIdentity"].update(versionCode=13), "release identity differs"),
    (lambda value: value["mainRun"].update(aggregateStatus="fail"), "mainRun is not exact"),
    (lambda value: value.update(publicationAuthorized=True), "posture"),
])
def test_receipt_substitution_fails_closed(tmp_path: Path, mutate, match):
    policy, _, receipt_value, args, _ = full_case(tmp_path)
    mutate(receipt_value)
    with pytest.raises(approval.ApprovalError, match=match):
        approval.validate_receipt(
            receipt_value, approval.validate_inputs(args), now=NOW,
            policy=policy,
        )


def test_stale_or_future_evidence_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    run = json.loads(args.run_snapshot.read_text())
    run["updated_at"] = "2026-09-04T14:02:30Z"
    write_json(args.run_snapshot, run)
    with pytest.raises(approval.ApprovalError, match="stale"):
        approval.create_approval(args, environment, now=NOW)

    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    artifact_value = json.loads(args.artifact_snapshot.read_text())
    artifact_value["created_at"] = "2026-09-06T14:01:00Z"
    write_json(args.artifact_snapshot, artifact_value)
    with pytest.raises(approval.ApprovalError, match="exact run attempt"):
        approval.create_approval(args, environment, now=NOW)

    _, _, receipt_value, args, environment = full_case(tmp_path, monkeypatch)
    receipt_value["decisionTimeUtc"] = "2026-09-06T15:00:00Z"
    receipt_value["eligibilitySha256"] = approval.canonical_sha256(
        {key: value for key, value in receipt_value.items() if key != "eligibilitySha256"}
    )
    receipt_bytes = write_json(tmp_path / "receipt.json", receipt_value)
    archive_bytes = archive(args.artifact_archive, receipt_bytes)
    values = json.loads(args.artifact_snapshot.read_text())
    values["digest"] = f"sha256:{hashlib.sha256(archive_bytes).hexdigest()}"
    values["size_in_bytes"] = len(archive_bytes)
    write_json(args.artifact_snapshot, values)
    args.two_green_artifact_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    args.two_green_receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    with pytest.raises(approval.ApprovalError, match="future"):
        approval.create_approval(args, environment, now=NOW)


@pytest.mark.parametrize("snapshot,mutate,match", [
    ("android_main_branch_snapshot", lambda value: value["commit"].update(sha="d" * 40), "branch authority"),
    ("android_main_branch_snapshot", lambda value: value.update(protected=False), "branch authority"),
    ("android_main_commit_snapshot", lambda value: value["tree"].update(sha="d" * 40), "commit/tree authority"),
])
def test_current_protected_android_main_is_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot: str, mutate, match: str
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    path = getattr(args, snapshot)
    value = json.loads(path.read_text())
    mutate(value)
    write_json(path, value)
    with pytest.raises(approval.ApprovalError, match=match):
        approval.create_approval(args, environment, now=NOW)


def test_rerun_of_old_active_fleet_sha_fails_after_main_deactivation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    branch = json.loads(args.fleet_main_branch_snapshot.read_text())
    branch["commit"]["sha"] = "d" * 40
    write_json(args.fleet_main_branch_snapshot, branch)
    with pytest.raises(approval.ApprovalError, match="current Fleet main branch"):
        approval.create_approval(args, environment, now=NOW)


def test_prior_approval_artifact_blocks_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    expected_name = approval.approval_artifact_name(approval.validate_inputs(args))
    write_json(args.approval_artifact_ledger_snapshot, {
        "total_count": 1,
        "artifacts": [{"id": 9001, "name": expected_name, "expired": False}],
    })
    with pytest.raises(approval.ApprovalError, match="already approved"):
        approval.create_approval(args, environment, now=NOW)


def test_nonce_and_reviewed_pull_request_are_exact(tmp_path: Path):
    policy, _, receipt_value, args, _ = full_case(tmp_path)
    args.approval_request_nonce = "not-a-nonce"
    with pytest.raises(approval.ApprovalError, match="nonce"):
        approval.validate_inputs(args)
    args.approval_request_nonce = "9" * 64
    receipt_value["reviewPullRequest"]["number"] = 46
    receipt_value["eligibilitySha256"] = approval.canonical_sha256(
        {key: value for key, value in receipt_value.items() if key != "eligibilitySha256"}
    )
    with pytest.raises(approval.ApprovalError, match="reviewed pull request"):
        approval.validate_receipt(
            receipt_value, approval.validate_inputs(args), now=NOW, policy=policy
        )

    args.review_pull_request_number = "045"
    with pytest.raises(approval.ApprovalError, match="positive decimal"):
        approval.validate_inputs(args)


def test_public_approval_expires_for_consumers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    result = approval.create_approval(args, environment, now=NOW)
    with pytest.raises(approval.ApprovalError, match="stale"):
        approval.validate_approval(
            result, now=datetime(2026, 9, 8, 14, 10, tzinfo=timezone.utc)
        )


def test_wrong_external_key_is_rejected_against_reviewed_public_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    other_seed = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    environment[approval.KEY_ENV_NAME] = base64.b64encode(
        bytes.fromhex("302e020100300506032b657004220420") + other_seed
    ).decode()
    with pytest.raises(approval.ApprovalError, match="public key differs"):
        approval.create_approval(args, environment, now=NOW)


def test_artifact_metadata_size_must_match_downloaded_exact_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    value = json.loads(args.artifact_snapshot.read_text())
    value["size_in_bytes"] += 1
    write_json(args.artifact_snapshot, value)
    with pytest.raises(approval.ApprovalError, match="archive size differs"):
        approval.create_approval(args, environment, now=NOW)


def test_public_approval_tamper_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    result = approval.create_approval(args, environment, now=NOW)
    result["sourceTree"] = "e" * 40
    with pytest.raises(approval.ApprovalError, match="source/version authority differs"):
        approval.validate_approval(result, now=NOW)


def test_missing_or_tampered_durable_reservation_blocks_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    args.ledger_reservation_snapshot.unlink()
    with pytest.raises((approval.ApprovalError, FileNotFoundError)):
        approval.create_approval(args, environment, now=NOW)

    _, _, _, args, environment = full_case(tmp_path, monkeypatch)
    reservation = json.loads(args.ledger_reservation_snapshot.read_text())
    reservation["receipt"]["subject"]["mainTree"] = "e" * 40
    write_json(args.ledger_reservation_snapshot, reservation)
    with pytest.raises((approval.ApprovalError, approval.approval_ledger.LedgerError)):
        approval.create_approval(args, environment, now=NOW)


def test_workflow_is_dormant_separate_and_uploads_only_public_json():
    text = WORKFLOW.read_text()
    assert "dormant-contract" in text
    assert "environment: ${{ needs.dormant-contract.outputs.environment }}" in text
    assert "github.ref_protected" in text
    assert approval.KEY_ENV_NAME in text
    assert approval.approval_ledger.CREDENTIAL_ENV_NAME in text
    assert approval.OUTPUT_NAME in text
    assert approval.AUDIT_OUTPUT_NAME in text
    assert "ANDROID_PREVIEW12_UPLOAD_KEYSTORE" not in text
    assert "ANDROID_PREVIEW12_KEYSTORE_PASSWORD" not in text
    assert "deployments: read" in text
    assert "google-github-actions/auth" not in text
    assert "play" not in text.lower().replace("googleplayuploadauthorized", "")
    lines = text.splitlines()
    for index, line in enumerate(lines):
        marker = re.match(r"^(\s*)run:\s*\|\s*$", line)
        if marker is None:
            continue
        indentation = len(marker.group(1))
        body: list[str] = []
        for candidate in lines[index + 1:]:
            if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= indentation:
                break
            body.append(candidate)
        assert "${{ inputs." not in "\n".join(body)
    for name in (
        "APPROVAL_REQUEST_NONCE",
        "TWO_GREEN_RUN_ID",
        "TWO_GREEN_RUN_ATTEMPT",
        "TWO_GREEN_ARTIFACT_ID",
        "TWO_GREEN_ARTIFACT_SHA256",
        "TWO_GREEN_RECEIPT_SHA256",
        "REVIEW_RUN_ID",
        "REVIEW_PULL_REQUEST_NUMBER",
        "MAIN_RUN_ID",
        "MAIN_COMMIT",
        "MAIN_TREE",
        "VERSION_NAME",
        "VERSION_CODE",
    ):
        assert f'"${name}"' in text
    assert "approval-artifact-ledger.json" in text
    assert "fleet-main-branch.json" in text
    assert "fleet-main-commit.json" in text
    assert "ledger-reservation.json" in text
    assert "ledger-commit.json" in text
    assert "ledger-cleanup.json" in text
    assert "recovered-public-approval.json" in text
    assert "steps.reserve.outcome == 'success'" in text
    assert "steps.commit.outcome != 'success'" in text
    assert "--reason-code workflow_interrupted" in text
    assert "--reservation-snapshot \"$evidence/ledger-reservation.json\"" in text
    step_blocks = re.split(r"^      - (?:id:|name:|uses:)", text, flags=re.MULTILINE)[1:]
    secret_name = "ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64"
    ledger_name = "ANDROID_PREVIEW12_APPROVAL_LEDGER_BEARER_TOKEN"
    assert all(not (secret_name in block and ledger_name in block) for block in step_blocks)
    signer_block = next(
        block for block in step_blocks
        if "Emit only the public, non-authorizing approval JSON" in block
    )
    assert secret_name in signer_block
    assert ledger_name not in signer_block
    for name in (
        "Reserve exact approval subject in the durable external ledger",
        "Commit the exact public approval to the durable external ledger",
        "Abort an open reservation after an interrupted approval transaction",
    ):
        block = next(item for item in step_blocks if name in item)
        assert ledger_name in block
        assert secret_name not in block
    reserve_at = text.index("--policy \"$policy\" reserve")
    approve_at = text.index("--policy \"$policy\" approve")
    commit_at = text.index("--policy \"$policy\" commit")
    upload_at = text.index("- name: Upload the Android approval, Fleet audit, and signed commit receipt JSON")
    assert reserve_at < approve_at < commit_at < upload_at
    assert 'cmp --silent' in text
    assert (
        "group: preview12-two-green-release-approval-"
        "${{ inputs.two_green_artifact_id }}"
    ) in text
    assert (
        "name: android-preview12-two-green-release-approval-"
        "${{ inputs.two_green_artifact_id }}"
    ) in text
    upload_block = text.split("- name: Upload the Android approval, Fleet audit, and signed commit receipt JSON", 1)[1]
    assert approval.OUTPUT_NAME in upload_block
    assert "ANDROID_PREVIEW12_APPROVAL_LEDGER_COMMIT.public.json" in upload_block
    assert "preview12-approval-evidence" not in upload_block


def test_cleanup_workflow_shell_invokes_status_aware_cli_with_only_ledger_secret(tmp_path: Path):
    text = WORKFLOW.read_text()
    marker = "      - name: Abort an open reservation after an interrupted approval transaction"
    step = text.split(marker, 1)[1].split("      - name:", 1)[0]
    run = step.split("        run: |\n", 1)[1]
    shell = textwrap.dedent(run)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python3"
    fake_python.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$@\" >\"$CAPTURE_ARGS\"\n"
        "env >\"$CAPTURE_ENV\"\n"
    )
    fake_python.chmod(0o700)
    runner_temp = tmp_path / "runner"
    (runner_temp / "preview12-approval-evidence").mkdir(parents=True)
    environment = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_WORKSPACE": str(ROOT),
        "CAPTURE_ARGS": str(tmp_path / "args"),
        "CAPTURE_ENV": str(tmp_path / "env"),
        approval.approval_ledger.CREDENTIAL_ENV_NAME: "ledger-only-test-secret",
        "APPROVAL_REQUEST_NONCE": "1" * 64,
        "TWO_GREEN_ARTIFACT_ID": "9989938590",
        "TWO_GREEN_ARTIFACT_SHA256": "2" * 64,
        "TWO_GREEN_RECEIPT_SHA256": "3" * 64,
        "MAIN_TREE": "4" * 40,
        "VERSION_NAME": approval.VERSION_NAME,
        "VERSION_CODE": str(approval.VERSION_CODE),
    }
    completed = subprocess.run(
        ["/bin/bash", "-c", shell], cwd=ROOT, env=environment,
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    arguments = (tmp_path / "args").read_text().splitlines()
    assert "cleanup" in arguments
    assert "--reason-code" in arguments
    assert "workflow_interrupted" in arguments
    assert "--reservation-snapshot" in arguments
    captured_environment = (tmp_path / "env").read_text()
    assert f"{approval.approval_ledger.CREDENTIAL_ENV_NAME}=ledger-only-test-secret" in captured_environment
    assert approval.KEY_ENV_NAME not in captured_environment
