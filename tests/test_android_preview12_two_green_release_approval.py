from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/android_preview12_two_green_release_approval.py"
POLICY = ROOT / "config/release/android-preview12-two-green-release-approval.json"
WORKFLOW = ROOT / ".github/workflows/android-preview12-two-green-release-approval.yml"
spec = importlib.util.spec_from_file_location("preview12_approval", SCRIPT)
assert spec and spec.loader
approval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(approval)

# RFC 8032 test-vector seed wrapped in the standard Ed25519 PKCS#8 DER envelope.
TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
TEST_PRIVATE_DER = bytes.fromhex("302e020100300506032b657004220420") + TEST_SEED


def write_json(path: Path, value: object) -> bytes:
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(data)
    return data


def active_policy(tmp_path: Path) -> tuple[dict, Path, str]:
    value = json.loads(POLICY.read_text())
    value["state"] = "ready"
    value["github_environment"]["configured"] = True
    value["external_ed25519_key"]["configured"] = True
    value["activation"]["enabled"] = True
    key_fd = os.memfd_create("test-ed25519")
    try:
        os.write(key_fd, TEST_PRIVATE_DER)
        os.lseek(key_fd, 0, os.SEEK_SET)
        public = approval._openssl(
            ["pkey", "-inform", "DER", "-in", f"/proc/self/fd/{key_fd}", "-pubout", "-outform", "DER"],
            pass_fds=(key_fd,),
        )
    finally:
        os.close(key_fd)
    public_digest = hashlib.sha256(public).hexdigest()
    value["external_ed25519_key"]["expected_public_key_spki_sha256"] = public_digest
    path = tmp_path / "policy.json"
    write_json(path, value)
    return value, path, public_digest


def inputs() -> dict[str, object]:
    return {
        "two_green_run_id": "301",
        "two_green_run_attempt": "1",
        "two_green_artifact_id": "401",
        "two_green_artifact_sha256": "0" * 64,
        "two_green_receipt_sha256": "0" * 64,
        "review_run_id": "101",
        "main_run_id": "201",
        "main_commit": "a" * 40,
        "main_tree": "b" * 40,
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
        "sourceCommit": "a" * 40,
        "sourceTree": "b" * 40,
        "releaseIdentity": {
            "packageId": approval.PACKAGE_ID,
            "versionName": approval.VERSION_NAME,
            "versionCode": approval.VERSION_CODE,
            "intentAuthority": "android_project_at_exact_main_tree",
        },
        "commonAuthority": {
            "androidTree": "b" * 40,
            "environmentCompatibilityStatus": "pass",
        },
        "reviewRun": {
            "run": {"id": 101, "status": "completed", "conclusion": "success"},
            "aggregateStatus": "pass",
        },
        "mainRun": {
            "run": {"id": 201, "headSha": "a" * 40, "status": "completed", "conclusion": "success"},
            "p0EventSha": "a" * 40,
            "aggregateStatus": "pass",
        },
        "decisionTimeUtc": "2026-09-06T12:00:00Z",
        "reviewPullRequest": {},
        "doesNotAssert": ["google_play_upload", "release_signing", "publication_authority"],
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


def full_case(tmp_path: Path):
    policy_value, policy_path, public_digest = active_policy(tmp_path)
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
        "head_sha": "a" * 40,
        "status": "completed",
        "conclusion": "success",
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
        "workflow_run": {"id": 301, "head_sha": "a" * 40},
    }
    environment_value = {
        "name": approval.ENVIRONMENT_NAME,
        "url": f"https://api.github.com/repos/{approval.FLEET_REPOSITORY}/environments/{approval.ENVIRONMENT_NAME}",
        "deployment_branch_policy": {"protected_branches": True, "custom_branch_policies": False},
        "protection_rules": [{
            "type": "required_reviewers",
            "prevent_self_review": True,
            "reviewers": [{"type": "User", "reviewer": {"id": 17, "login": "reviewer"}}],
        }],
    }
    write_json(tmp_path / "run.json", run)
    write_json(tmp_path / "artifact.json", artifact_value)
    write_json(tmp_path / "environment.json", environment_value)
    args = argparse.Namespace(
        policy=policy_path,
        **values,
        **execution(),
        environment_snapshot=(tmp_path / "environment.json").resolve(),
        run_snapshot=(tmp_path / "run.json").resolve(),
        artifact_snapshot=(tmp_path / "artifact.json").resolve(),
        artifact_archive=(tmp_path / "artifact.zip").resolve(),
        output=(tmp_path / approval.OUTPUT_NAME).resolve(),
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
    assert value["external_ed25519_key"]["expected_public_key_spki_sha256"] is None
    assert b"PRIVATE KEY" not in data
    assert base64.b64encode(TEST_PRIVATE_DER) not in data


def test_dormant_preflight_fails_before_environment_or_key_access():
    value, _, _ = approval.load_policy(POLICY.resolve())
    args = argparse.Namespace(**inputs(), **{key: value for key, value in execution().items() if not key.startswith("execution_run") and key != "execution_environment"})
    with pytest.raises(approval.ApprovalError, match="policy state is dormant"):
        approval.validate_dispatch(value, args)


@pytest.mark.parametrize("change", [
    {"execution_ref": "refs/heads/feature"},
    {"execution_ref_protected": "false"},
    {"execution_repository": approval.ANDROID_REPOSITORY},
    {"workflow_sha": "d" * 40},
    {"version_name": "0.1.0-preview.13"},
    {"version_code": "13"},
])
def test_active_preflight_rejects_context_or_release_substitution(tmp_path: Path, change):
    policy, policy_path, _ = active_policy(tmp_path)
    values = {**inputs(), **execution(), **change}
    values.pop("execution_run_id", None)
    values.pop("execution_run_attempt", None)
    values.pop("execution_environment", None)
    args = argparse.Namespace(**values)
    with pytest.raises(approval.ApprovalError):
        approval.validate_dispatch(policy, args)
    assert policy_path.exists()


def test_environment_requires_human_reviewer_self_review_prevention_and_protected_main(tmp_path: Path):
    policy, _, _ = active_policy(tmp_path)
    base = {
        "name": approval.ENVIRONMENT_NAME,
        "url": f"https://api.github.com/repos/{approval.FLEET_REPOSITORY}/environments/{approval.ENVIRONMENT_NAME}",
        "deployment_branch_policy": {"protected_branches": True, "custom_branch_policies": False},
        "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True,
                              "reviewers": [{"type": "User", "reviewer": {"id": 7, "login": "human-reviewer"}}]}],
    }
    assert approval.validate_environment_snapshot(base, policy)["requiredReviewerCount"] == 1
    for mutation in (
        lambda value: value["protection_rules"].clear(),
        lambda value: value["protection_rules"][0].update(prevent_self_review=False),
        lambda value: value["deployment_branch_policy"].update(protected_branches=False),
        lambda value: value["protection_rules"][0].update(reviewers=[]),
        lambda value: value["protection_rules"][0].update(reviewers=[{"type": "Team", "reviewer": {"id": 7}}]),
    ):
        changed = json.loads(json.dumps(base))
        mutation(changed)
        with pytest.raises(approval.ApprovalError):
            approval.validate_environment_snapshot(changed, policy)


def test_exact_two_green_receipt_emits_only_public_non_authorizing_approval(tmp_path: Path):
    _, public_digest, _, args, environment = full_case(tmp_path)
    result = approval.create_approval(args, environment)
    approval.validate_approval(result)
    assert result["signature"]["publicKeySpkiSha256"] == public_digest
    assert result["twoGreenVerified"] is True
    assert result["signingAuthorized"] is False
    assert result["publicationAuthorized"] is False
    assert result["googlePlayUploadAuthorized"] is False
    serialized = approval.pretty_bytes(result)
    assert base64.b64encode(TEST_PRIVATE_DER) not in serialized
    assert b"keystore" not in serialized.lower()
    assert b"aab" not in serialized.lower()


@pytest.mark.parametrize("mutate,match", [
    (lambda value: value.update(sourceTree="d" * 40), "Android identity differs"),
    (lambda value: value["releaseIdentity"].update(versionCode=13), "release identity differs"),
    (lambda value: value["mainRun"].update(aggregateStatus="fail"), "mainRun is not exact"),
    (lambda value: value.update(publicationAuthorized=True), "posture"),
])
def test_receipt_substitution_fails_closed(tmp_path: Path, mutate, match):
    _, _, receipt_value, args, _ = full_case(tmp_path)
    mutate(receipt_value)
    with pytest.raises(approval.ApprovalError, match=match):
        approval.validate_receipt(receipt_value, approval.validate_inputs(args))


def test_wrong_external_key_is_rejected_against_reviewed_public_digest(tmp_path: Path):
    _, _, _, args, environment = full_case(tmp_path)
    other_seed = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
    environment[approval.KEY_ENV_NAME] = base64.b64encode(
        bytes.fromhex("302e020100300506032b657004220420") + other_seed
    ).decode()
    with pytest.raises(approval.ApprovalError, match="public key differs"):
        approval.create_approval(args, environment)


def test_artifact_metadata_size_must_match_downloaded_exact_archive(tmp_path: Path):
    _, _, _, args, environment = full_case(tmp_path)
    value = json.loads(args.artifact_snapshot.read_text())
    value["size_in_bytes"] += 1
    write_json(args.artifact_snapshot, value)
    with pytest.raises(approval.ApprovalError, match="archive size differs"):
        approval.create_approval(args, environment)


def test_public_approval_tamper_is_rejected(tmp_path: Path):
    _, _, _, args, environment = full_case(tmp_path)
    result = approval.create_approval(args, environment)
    result["androidSource"]["tree"] = "e" * 40
    with pytest.raises(approval.ApprovalError, match="digest is invalid"):
        approval.validate_approval(result)


def test_workflow_is_dormant_separate_and_uploads_only_public_json():
    text = WORKFLOW.read_text()
    assert "dormant-contract" in text
    assert "environment: ${{ needs.dormant-contract.outputs.environment }}" in text
    assert "github.ref_protected" in text
    assert approval.KEY_ENV_NAME in text
    assert approval.OUTPUT_NAME in text
    assert "ANDROID_PREVIEW12_UPLOAD_KEYSTORE" not in text
    assert "ANDROID_PREVIEW12_KEYSTORE_PASSWORD" not in text
    assert "deployments: read" in text
    assert "google-github-actions/auth" not in text
    assert "play" not in text.lower().replace("googleplayuploadauthorized", "")
    upload_block = text.split("- name: Upload only the public approval JSON", 1)[1]
    assert approval.OUTPUT_NAME in upload_block
    assert "preview12-approval-evidence" not in upload_block
