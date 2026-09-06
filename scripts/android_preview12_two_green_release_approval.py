#!/usr/bin/env python3
"""Verify Preview12 Two-Green evidence and emit Android's exact approval JSON.

This lane never accepts an AAB, upload keystore, Play credential, or publication
target.  Its Ed25519 key is accepted only from the protected GitHub environment
variable named by the reviewed policy.  The checked-in policy is dormant.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
from typing import Any, Mapping
import zipfile

try:
    from scripts import android_preview12_approval_ledger as approval_ledger
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    import android_preview12_approval_ledger as approval_ledger


POLICY_CONTRACT = "fleet.android_preview12_two_green_release_approval_policy.v1"
FLEET_AUDIT_CONTRACT = "fleet.android_preview12_two_green_release_approval.v1"
OUTPUT_CONTRACT = "chummer.android.two-green-release-approval/v1"
TWO_GREEN_CONTRACT = "chummer.android.api36-ordered-review-main-green-eligibility/v2"
FLEET_REPOSITORY = "ArchonMegalon/fleet"
ANDROID_REPOSITORY = "ArchonMegalon/chummer-android"
FLEET_REF = "refs/heads/main"
ANDROID_REF = "refs/heads/main"
WORKFLOW_PATH = ".github/workflows/android-preview12-two-green-release-approval.yml"
TWO_GREEN_WORKFLOW_NAME = "API 36 ordered review-to-main green eligibility"
TWO_GREEN_WORKFLOW_PATH = ".github/workflows/api36-two-consecutive-green.yml"
RECEIPT_NAME = "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json"
OUTPUT_NAME = "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json"
AUDIT_OUTPUT_NAME = "FLEET_ANDROID_PREVIEW12_APPROVAL_AUDIT.generated.json"
ENVIRONMENT_NAME = "android-preview12-release-approval"
KEY_ENV_NAME = "ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64"
PACKAGE_ID = "com.myexternalbrain.chummer"
VERSION_NAME = "0.1.0-preview.12"
VERSION_CODE = 12
ANDROID_CONSUMER_COMMIT = "388425aceac266e06265e4c0c73a4058b052d316"
ANDROID_CONSUMER_TREE = "175da843cfc2df3489d87dc153c186b9c8e4d803"
RELEASE_APPROVER_KEY_ID = "local-release-builder-2026"
RELEASE_APPROVER_ROLE = "android_internal_release_approver"
RELEASE_APPROVAL_SCOPE = "android_internal_release_preparation"
RELEASE_APPROVER_PUBLIC_KEY_PATH = (
    "eng/trusted-release-approvers/local-release-builder-2026.public.pem"
)
RELEASE_APPROVER_PUBLIC_KEY_PEM_SHA256 = (
    "ed1fbe95fc7713bfc6d9d0fea21726c1ba3193533fc2d5523e054ad8fb86184c"
)
RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64 = (
    "MCowBQYDK2VwAyEAB105wcYguHU3a/phMkbbRjhZ+Qhj8cdDTAvw/7t14sk="
)
RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256 = (
    "c46a4e9a224c8c77a4038bca83f7d9ed66146318d8b5c2c9fc81cd19fdd18ea7"
)
PROVENANCE_VALIDATOR_PATH = "scripts/materialize-api36-two-green-eligibility.py"
PROVENANCE_VALIDATOR_SHA256 = (
    "6129faf8f1cac0e540126a39cb46e16352387c370dbbd003e1fe5ace1edf4492"
)
APPROVAL_LIFETIME_SECONDS = 6 * 60 * 60
MAX_APPROVAL_LIFETIME_SECONDS = 12 * 60 * 60
APPROVAL_CLOCK_SKEW_SECONDS = 2 * 60
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
SPKI_ED25519_PREFIX = bytes.fromhex("302a300506032b6570032100")
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_RECEIPT_BYTES = 16 * 1024 * 1024
MAX_EVIDENCE_AGE_SECONDS = 24 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5 * 60
DOES_NOT_AUTHORIZE = """android_artifact_signing play_upload_key_access
google_play_upload google_play_processing tester_distribution tester_installation
registry_publication github_release public_release""".split()


class ApprovalError(RuntimeError):
    """One fail-closed approval contract violation."""


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def android_canonical_bytes(value: object) -> bytes:
    """Canonical bytes consumed by Android 388425ace (no trailing newline)."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def pretty_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _strict_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ApprovalError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def strict_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_strict_object_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ApprovalError(f"non-finite JSON value in {label}: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApprovalError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ApprovalError(f"{label} must contain one JSON object")
    return value


def stable_file(path: Path, label: str, limit: int) -> tuple[bytes, str]:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or path.resolve(strict=True) != path
    ):
        raise ApprovalError(f"{label} must be an absolute canonical non-symlink file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0 or before.st_size > limit:
            raise ApprovalError(f"{label} is not one bounded regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, min(1024 * 1024, limit + 1)):
            chunks.append(chunk)
            if sum(map(len, chunks)) > limit:
                raise ApprovalError(f"{label} exceeds its byte limit")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity = lambda value: (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    if identity(before) != identity(after):
        raise ApprovalError(f"{label} changed during capture")
    data = b"".join(chunks)
    if len(data) != before.st_size:
        raise ApprovalError(f"{label} size changed during capture")
    return data, hashlib.sha256(data).hexdigest()


def _exact_keys(value: Mapping[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise ApprovalError(f"{label} fields are not exact")


def _sha40(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA40.fullmatch(value) is None:
        raise ApprovalError(f"{label} must be a lowercase SHA-40")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ApprovalError(f"{label} must be a lowercase SHA-256")
    return value


def _positive(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ApprovalError(f"{label} must be a positive integer")
    return value


def _positive_decimal(value: object, label: str) -> int:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[1-9][0-9]*", value, flags=re.ASCII) is None
    ):
        raise ApprovalError(f"{label} must be a positive decimal integer")
    return _positive(int(value), label)


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ApprovalError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ApprovalError(f"{label} must be a UTC timestamp") from error
    if parsed.tzinfo != timezone.utc:
        raise ApprovalError(f"{label} must be a UTC timestamp")
    return parsed


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _fresh_timestamp(
    value: object, label: str, *, now: datetime, policy: Mapping[str, Any]
) -> tuple[datetime, str]:
    parsed = _timestamp(value, label)
    freshness = policy["freshness"]
    if parsed > now + timedelta(seconds=freshness["maximum_future_skew_seconds"]):
        raise ApprovalError(f"{label} is unacceptably in the future")
    if now - parsed > timedelta(seconds=freshness["maximum_evidence_age_seconds"]):
        raise ApprovalError(f"{label} is stale")
    return parsed, str(value)


def _reviewer_list(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ApprovalError(f"{label} must be a list")
    output: list[dict[str, object]] = []
    for row in value:
        if not isinstance(row, dict) or set(row) != {"id", "login"}:
            raise ApprovalError(f"{label} contains a malformed identity")
        reviewer_id = row.get("id")
        login = row.get("login")
        if (
            type(reviewer_id) is not int
            or reviewer_id <= 0
            or not isinstance(login, str)
            or not login
            or login != login.strip()
            or login.casefold().endswith("[bot]")
        ):
            raise ApprovalError(f"{label} contains a non-human identity")
        output.append({"id": reviewer_id, "login": login})
    ordered = sorted(output, key=lambda row: (row["id"], row["login"]))
    if output != ordered or len({row["id"] for row in output}) != len(output):
        raise ApprovalError(f"{label} must be unique and canonically ordered")
    return output


def expected_policy() -> dict[str, Any]:
    return {
        "contract_name": POLICY_CONTRACT,
        "contract_version": 1,
        "state": "dormant_pending_environment_signer_and_ledger_service",
        "release": {"package_id": PACKAGE_ID, "version_name": VERSION_NAME,
                    "version_code": VERSION_CODE},
        "android_source": {"repository": ANDROID_REPOSITORY,
                           "repository_id": 1331626697, "ref": ANDROID_REF},
        "two_green": {
            "workflow_name": TWO_GREEN_WORKFLOW_NAME,
            "workflow_path": TWO_GREEN_WORKFLOW_PATH,
            "receipt_contract": TWO_GREEN_CONTRACT,
            "receipt_file_name": RECEIPT_NAME,
        },
        "fleet_execution": {"repository": FLEET_REPOSITORY,
                            "repository_id": 1176287728, "ref": FLEET_REF,
                            "protected_ref_required": True,
                            "current_main_snapshot_required": True,
                            "event": "workflow_dispatch",
                            "workflow_path": WORKFLOW_PATH},
        "github_environment": {
            "name": ENVIRONMENT_NAME,
            "configured": False,
            "required_reviewers_required": True,
            "minimum_required_reviewers": 1,
            "human_user_reviewer_required": True,
            "expected_human_user_reviewers": [],
            "prevent_self_review_required": True,
            "administrators_can_bypass_allowed": False,
            "protected_branches_only": True,
        },
        "external_ed25519_key": {
            "configured": False,
            "source": "github_environment_secret_only",
            "secret_name": KEY_ENV_NAME,
            "algorithm": "ed25519",
            "key_id": RELEASE_APPROVER_KEY_ID,
            "role": RELEASE_APPROVER_ROLE,
            "approval_scope": RELEASE_APPROVAL_SCOPE,
            "trusted_public_key_path": RELEASE_APPROVER_PUBLIC_KEY_PATH,
            "trusted_public_key_pem_sha256": RELEASE_APPROVER_PUBLIC_KEY_PEM_SHA256,
            "public_key_spki_der_base64": RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64,
            "expected_public_key_spki_sha256": RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256,
            "private_key_persistence_allowed": False,
        },
        "android_consumer": {
            "qualified_commit": ANDROID_CONSUMER_COMMIT,
            "qualified_tree": ANDROID_CONSUMER_TREE,
            "verifier_path": "scripts/verify_api36_two_green_release_eligibility.py",
            "contract_name": OUTPUT_CONTRACT,
            "canonical_json": "utf8_sort_keys_compact_no_trailing_newline",
            "provenance_validator_path": PROVENANCE_VALIDATOR_PATH,
            "provenance_validator_sha256": PROVENANCE_VALIDATOR_SHA256,
            "maximum_approval_lifetime_seconds": MAX_APPROVAL_LIFETIME_SECONDS,
            "approval_clock_skew_seconds": APPROVAL_CLOCK_SKEW_SECONDS,
        },
        "freshness": {
            "maximum_evidence_age_seconds": MAX_EVIDENCE_AGE_SECONDS,
            "maximum_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
        },
        "replay_protection": {
            "mode": "durable_external_exactly_once",
            "approval_request_nonce_required": True,
            "artifact_ledger_required": True,
            "durable_external_reservation_required": True,
            "durable_reservation_subjects": [
                "two_green_artifact_id", "approval_request_nonce"
            ],
            "durable_external_reservation_configured": False,
            "authority_complete": False,
            "external_ledger": approval_ledger.dormant_ledger_policy(),
        },
        "activation": {"enabled": False,
                       "requires_separate_reviewed_contract_change": True},
        "output": {
            "contract_name": OUTPUT_CONTRACT,
            "key_id": RELEASE_APPROVER_KEY_ID,
            "role": RELEASE_APPROVER_ROLE,
            "approval_scope": RELEASE_APPROVAL_SCOPE,
            "file_name": OUTPUT_NAME,
            "fleet_audit_contract_name": FLEET_AUDIT_CONTRACT,
            "fleet_audit_file_name": AUDIT_OUTPUT_NAME,
            "public_json_only": True,
            "signing_authorized": False,
            "publication_authorized": False,
            "google_play_upload_authorized": False,
        },
        "separation": {
            "play_aab_signer": "strictly_separate",
            "accepts_aab_bytes": False,
            "accepts_play_credentials": False,
            "accepts_upload_keystore": False,
            "performs_artifact_signing": False,
            "performs_play_upload": False,
            "performs_publication": False,
        },
    }


def load_policy(path: Path) -> tuple[dict[str, Any], bytes, str]:
    data, digest = stable_file(path, "approval policy", MAX_RECEIPT_BYTES)
    value = strict_json_bytes(data, "approval policy")
    expected = expected_policy()
    if value != expected:
        # Activation is deliberately the only accepted deviation from the dormant template.
        active = json.loads(json.dumps(expected))
        active["state"] = "ready"
        active["github_environment"]["configured"] = True
        active["external_ed25519_key"]["configured"] = True
        active["activation"]["enabled"] = True
        replay = value.get("replay_protection")
        observed_ledger = replay.get("external_ledger") if isinstance(replay, dict) else None
        try:
            approval_ledger.validate_ledger_policy(
                observed_ledger, require_configured=True
            )
        except approval_ledger.LedgerError:
            observed_ledger = None
        if observed_ledger is not None:
            active["replay_protection"]["durable_external_reservation_configured"] = True
            active["replay_protection"]["authority_complete"] = True
            active["replay_protection"]["external_ledger"] = observed_ledger
        observed_key_digest = value.get("external_ed25519_key", {}).get(
            "expected_public_key_spki_sha256"
        ) if isinstance(value.get("external_ed25519_key"), dict) else None
        if (
            observed_ledger is not None
            and observed_key_digest
            == observed_ledger.get("receipt_public_key_spki_sha256")
        ):
            raise ApprovalError(
                "approval and durable-ledger receipt keys must be distinct"
            )
        observed_reviewers = value.get("github_environment", {}).get(
            "expected_human_user_reviewers"
        ) if isinstance(value.get("github_environment"), dict) else None
        try:
            reviewed_users = _reviewer_list(
                observed_reviewers, "reviewed human user identities"
            )
        except ApprovalError:
            reviewed_users = []
        if reviewed_users:
            active["github_environment"]["expected_human_user_reviewers"] = reviewed_users
        if value != active:
            raise ApprovalError("approval policy differs from the closed dormant/ready contract")
    return value, data, digest


def _require_ready(policy: Mapping[str, Any]) -> None:
    blockers: list[str] = []
    if policy.get("state") != "ready":
        blockers.append("policy state is dormant")
    environment = policy.get("github_environment", {})
    key = policy.get("external_ed25519_key", {})
    activation = policy.get("activation", {})
    if not isinstance(environment, dict) or environment.get("configured") is not True:
        blockers.append("reviewed GitHub environment is not configured")
    if not isinstance(key, dict) or key.get("configured") is not True:
        blockers.append("external Ed25519 key is not configured")
    if not isinstance(activation, dict) or activation.get("enabled") is not True:
        blockers.append("approval activation is disabled")
    if not isinstance(key, dict) or SHA256.fullmatch(
        str(key.get("expected_public_key_spki_sha256") or "")
    ) is None:
        blockers.append("external Ed25519 public-key digest is not pinned")
    elif (
        key.get("algorithm") != "ed25519"
        or key.get("key_id") != RELEASE_APPROVER_KEY_ID
        or key.get("role") != RELEASE_APPROVER_ROLE
        or key.get("approval_scope") != RELEASE_APPROVAL_SCOPE
        or key.get("trusted_public_key_path") != RELEASE_APPROVER_PUBLIC_KEY_PATH
        or key.get("trusted_public_key_pem_sha256")
        != RELEASE_APPROVER_PUBLIC_KEY_PEM_SHA256
        or key.get("public_key_spki_der_base64")
        != RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64
        or key.get("expected_public_key_spki_sha256")
        != RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256
    ):
        blockers.append("external Ed25519 key differs from Android's pinned approver")
    try:
        reviewed_users = _reviewer_list(
            environment.get("expected_human_user_reviewers")
            if isinstance(environment, dict) else None,
            "reviewed human user identities",
        )
    except ApprovalError:
        reviewed_users = []
    if not reviewed_users:
        blockers.append("human user reviewer identities are not pinned")
    replay = policy.get("replay_protection", {})
    if (
        not isinstance(replay, dict)
        or replay.get("mode") != "durable_external_exactly_once"
        or replay.get("durable_external_reservation_required") is not True
        or replay.get("durable_reservation_subjects")
        != ["two_green_artifact_id", "approval_request_nonce"]
        or replay.get("durable_external_reservation_configured") is not True
        or replay.get("authority_complete") is not True
    ):
        blockers.append("durable external replay reservation authority is incomplete")
    else:
        try:
            ledger_policy = approval_ledger.validate_ledger_policy(
                replay.get("external_ledger"), require_configured=True
            )
            if (
                isinstance(key, dict)
                and key.get("expected_public_key_spki_sha256")
                == ledger_policy.get("receipt_public_key_spki_sha256")
            ):
                blockers.append(
                    "approval and durable-ledger receipt keys are not distinct"
                )
        except approval_ledger.LedgerError:
            blockers.append("durable external ledger authority is unavailable")
    if blockers:
        raise ApprovalError("; ".join(blockers))


def validate_dispatch(policy: Mapping[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    _require_ready(policy)
    expected = {
        "execution_repository": FLEET_REPOSITORY,
        "execution_ref": FLEET_REF,
        "execution_ref_protected": "true",
        "execution_event": "workflow_dispatch",
        "workflow_repository": FLEET_REPOSITORY,
        "workflow_ref": f"{FLEET_REPOSITORY}/{WORKFLOW_PATH}@refs/heads/main",
    }
    for field, value in expected.items():
        if getattr(args, field) != value:
            raise ApprovalError(f"{field} differs from protected Fleet main authority")
    execution_sha = _sha40(args.execution_sha, "Fleet execution SHA")
    if _sha40(args.workflow_sha, "Fleet workflow SHA") != execution_sha:
        raise ApprovalError("workflow SHA differs from the exact Fleet execution SHA")
    inputs = validate_inputs(args)
    return {
        "ok": True,
        "environment": policy["github_environment"]["name"],
        "inputSha256": canonical_sha256(inputs),
        "signingAuthorized": False,
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
    }


def validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    values = {
        "approvalRequestNonce": _sha256(
            args.approval_request_nonce, "approval request nonce"
        ),
        "twoGreenRunId": _positive_decimal(args.two_green_run_id, "Two-Green run ID"),
        "twoGreenRunAttempt": _positive_decimal(args.two_green_run_attempt, "Two-Green run attempt"),
        "twoGreenArtifactId": _positive_decimal(args.two_green_artifact_id, "Two-Green artifact ID"),
        "twoGreenArtifactSha256": _sha256(args.two_green_artifact_sha256, "Two-Green artifact SHA-256"),
        "twoGreenReceiptSha256": _sha256(args.two_green_receipt_sha256, "Two-Green receipt SHA-256"),
        "reviewRunId": _positive_decimal(args.review_run_id, "review run ID"),
        "reviewPullRequestNumber": _positive_decimal(
            args.review_pull_request_number, "review pull request number"
        ),
        "mainRunId": _positive_decimal(args.main_run_id, "main run ID"),
        "mainCommit": _sha40(args.main_commit, "Android main commit"),
        "mainTree": _sha40(args.main_tree, "Android main tree"),
        "versionName": args.version_name,
        "versionCode": _positive_decimal(args.version_code, "version code"),
    }
    if (values["versionName"], values["versionCode"]) != (VERSION_NAME, VERSION_CODE):
        raise ApprovalError("release identity is not exact Preview12/code12")
    if (
        values["mainCommit"] != ANDROID_CONSUMER_COMMIT
        or values["mainTree"] != ANDROID_CONSUMER_TREE
    ):
        raise ApprovalError("Android source is not the qualified 388425ace consumer")
    if values["reviewRunId"] == values["mainRunId"]:
        raise ApprovalError("review and main run IDs must be distinct")
    return values


def validate_environment_snapshot(value: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    expected_url = f"https://api.github.com/repos/{FLEET_REPOSITORY}/environments/{ENVIRONMENT_NAME}"
    if value.get("name") != ENVIRONMENT_NAME or value.get("url") != expected_url:
        raise ApprovalError("GitHub environment identity differs")
    if value.get("can_admins_bypass") is not False:
        raise ApprovalError("approval environment permits administrator bypass")
    branch = value.get("deployment_branch_policy")
    if not isinstance(branch, dict) or branch.get("protected_branches") is not True or branch.get("custom_branch_policies") is not False:
        raise ApprovalError("approval environment is not restricted to protected branches")
    rules = value.get("protection_rules")
    if not isinstance(rules, list):
        raise ApprovalError("approval environment protection rules are missing")
    reviewer_rules = [row for row in rules if isinstance(row, dict) and row.get("type") == "required_reviewers"]
    if len(reviewer_rules) != 1:
        raise ApprovalError("approval environment must have exactly one required-reviewer rule")
    rule = reviewer_rules[0]
    reviewers = rule.get("reviewers")
    minimum = policy["github_environment"]["minimum_required_reviewers"]
    if rule.get("prevent_self_review") is not True or not isinstance(reviewers, list) or len(reviewers) < minimum:
        raise ApprovalError("approval environment lacks human review or self-review prevention")
    reviewer_types: list[str] = []
    human_users: list[dict[str, object]] = []
    for row in reviewers:
        if not isinstance(row, dict) or row.get("type") != "User":
            raise ApprovalError("approval environment reviewer is not an explicit User")
        reviewer = row.get("reviewer")
        if not isinstance(reviewer, dict) or type(reviewer.get("id")) is not int or reviewer["id"] <= 0:
            raise ApprovalError("approval environment reviewer identity is malformed")
        reviewer_types.append(row["type"])
        login = reviewer.get("login")
        if (
            not isinstance(login, str)
            or not login
            or login.casefold().endswith("[bot]")
        ):
            raise ApprovalError("approval environment user reviewer is not a human account")
        human_users.append({"id": reviewer["id"], "login": login})
    human_users = sorted(human_users, key=lambda row: (row["id"], row["login"]))
    if len(human_users) < 1:
        raise ApprovalError("approval environment has no explicit human user reviewer")
    expected_users = _reviewer_list(
        policy["github_environment"]["expected_human_user_reviewers"],
        "reviewed human user identities",
    )
    if human_users != expected_users:
        raise ApprovalError("approval environment reviewer identities differ from policy")
    return {
        "name": ENVIRONMENT_NAME,
        "requiredReviewerCount": len(reviewers),
        "reviewerTypes": sorted(reviewer_types),
        "humanUserReviewerCount": len(human_users),
        "reviewerIdentitySetSha256": canonical_sha256(human_users),
        "configuredHumanReviewerSetPinned": True,
        "preventSelfReview": True,
        "administratorsCanBypass": False,
        "protectedBranchesOnly": True,
        "actualApprovalActorRecorded": False,
    }


def validate_run(
    value: Mapping[str, Any], inputs: Mapping[str, Any], *, now: datetime,
    policy: Mapping[str, Any]
) -> dict[str, Any]:
    repository = value.get("repository")
    head_repository = value.get("head_repository")
    expected_api = f"https://api.github.com/repos/{ANDROID_REPOSITORY}"
    if not isinstance(repository, dict) or repository.get("id") != 1331626697 or repository.get("full_name") != ANDROID_REPOSITORY:
        raise ApprovalError("Two-Green run repository differs")
    if not isinstance(head_repository, dict) or head_repository.get("id") != 1331626697 or head_repository.get("full_name") != ANDROID_REPOSITORY:
        raise ApprovalError("Two-Green run head repository differs")
    run_id = inputs["twoGreenRunId"]
    if (
        value.get("id") != run_id
        or value.get("run_attempt") != inputs["twoGreenRunAttempt"]
        or value.get("name") != TWO_GREEN_WORKFLOW_NAME
        or value.get("path") != TWO_GREEN_WORKFLOW_PATH
        or value.get("event") != "workflow_dispatch"
        or value.get("head_branch") != "main"
        or value.get("head_sha") != inputs["mainCommit"]
        or value.get("status") != "completed"
        or value.get("conclusion") != "success"
        or value.get("url") != f"{expected_api}/actions/runs/{run_id}"
        or value.get("html_url") != f"https://github.com/{ANDROID_REPOSITORY}/actions/runs/{run_id}"
    ):
        raise ApprovalError("Two-Green workflow run is not the exact successful main authority")
    created, created_text = _fresh_timestamp(
        value.get("created_at"), "Two-Green run creation", now=now, policy=policy
    )
    started, started_text = _fresh_timestamp(
        value.get("run_started_at"), "Two-Green run attempt start", now=now,
        policy=policy,
    )
    updated, updated_text = _fresh_timestamp(
        value.get("updated_at"), "Two-Green run completion", now=now, policy=policy
    )
    if not created <= started <= updated:
        raise ApprovalError("Two-Green run timestamps are out of order")
    return {
        "id": run_id,
        "attempt": inputs["twoGreenRunAttempt"],
        "workflowName": TWO_GREEN_WORKFLOW_NAME,
        "workflowPath": TWO_GREEN_WORKFLOW_PATH,
        "event": "workflow_dispatch",
        "ref": ANDROID_REF,
        "headSha": inputs["mainCommit"],
        "status": "completed",
        "conclusion": "success",
        "createdAtUtc": created_text,
        "attemptStartedAtUtc": started_text,
        "completedAtUtc": updated_text,
        "detailsUrl": value["html_url"],
    }


def validate_artifact(
    value: Mapping[str, Any], inputs: Mapping[str, Any], *, now: datetime,
    policy: Mapping[str, Any]
) -> dict[str, Any]:
    run = value.get("workflow_run")
    expected_name = f"chummer-android-api36-two-green-eligibility-{inputs['reviewRunId']}-{inputs['mainRunId']}"
    digest = value.get("digest")
    if (
        value.get("id") != inputs["twoGreenArtifactId"]
        or value.get("name") != expected_name
        or value.get("expired") is not False
        or digest != f"sha256:{inputs['twoGreenArtifactSha256']}"
        or ARTIFACT_DIGEST.fullmatch(str(digest or "")) is None
        or type(value.get("size_in_bytes")) is not int
        or value["size_in_bytes"] <= 0
        or value["size_in_bytes"] > MAX_ARCHIVE_BYTES
        or value.get("url")
        != f"https://api.github.com/repos/{ANDROID_REPOSITORY}/actions/artifacts/{inputs['twoGreenArtifactId']}"
        or value.get("archive_download_url")
        != f"https://api.github.com/repos/{ANDROID_REPOSITORY}/actions/artifacts/{inputs['twoGreenArtifactId']}/zip"
        or not isinstance(run, dict)
        or run.get("id") != inputs["twoGreenRunId"]
        or run.get("head_sha") != inputs["mainCommit"]
    ):
        raise ApprovalError("Two-Green artifact authority differs")
    created, created_text = _fresh_timestamp(
        value.get("created_at"), "Two-Green artifact creation", now=now, policy=policy
    )
    expires = _timestamp(value.get("expires_at"), "Two-Green artifact expiry")
    if expires <= now or expires <= created:
        raise ApprovalError("Two-Green artifact expiry is not current")
    return {
        "id": inputs["twoGreenArtifactId"],
        "name": expected_name,
        "archiveSha256": inputs["twoGreenArtifactSha256"],
        "archiveSizeBytes": value["size_in_bytes"],
        "createdAtUtc": created_text,
        "expiresAtUtc": str(value["expires_at"]),
    }


def approval_artifact_name(inputs: Mapping[str, Any]) -> str:
    return (
        "android-preview12-two-green-release-approval-"
        f"{inputs['twoGreenArtifactId']}"
    )


def validate_android_main_snapshots(
    branch: Mapping[str, Any], commit: Mapping[str, Any], inputs: Mapping[str, Any]
) -> dict[str, Any]:
    branch_commit = branch.get("commit")
    if (
        branch.get("name") != "main"
        or branch.get("protected") is not True
        or not isinstance(branch_commit, dict)
        or branch_commit.get("sha") != inputs["mainCommit"]
    ):
        raise ApprovalError("current Android main branch authority differs")
    tree = commit.get("tree")
    expected_commit_url = (
        f"https://api.github.com/repos/{ANDROID_REPOSITORY}/git/commits/"
        f"{inputs['mainCommit']}"
    )
    if (
        commit.get("sha") != inputs["mainCommit"]
        or commit.get("url") != expected_commit_url
        or not isinstance(tree, dict)
        or tree.get("sha") != inputs["mainTree"]
    ):
        raise ApprovalError("current Android main commit/tree authority differs")
    return {
        "protected": True,
        "commit": inputs["mainCommit"],
        "tree": inputs["mainTree"],
    }


def validate_fleet_main_snapshots(
    branch: Mapping[str, Any], commit: Mapping[str, Any], execution_sha: str
) -> dict[str, Any]:
    execution_sha = _sha40(execution_sha, "Fleet execution SHA")
    branch_commit = branch.get("commit")
    if (
        branch.get("name") != "main"
        or branch.get("protected") is not True
        or not isinstance(branch_commit, dict)
        or branch_commit.get("sha") != execution_sha
    ):
        raise ApprovalError("current Fleet main branch authority differs")
    tree = commit.get("tree")
    expected_commit_url = (
        f"https://api.github.com/repos/{FLEET_REPOSITORY}/git/commits/"
        f"{execution_sha}"
    )
    if (
        commit.get("sha") != execution_sha
        or commit.get("url") != expected_commit_url
        or not isinstance(tree, dict)
    ):
        raise ApprovalError("current Fleet main commit/tree authority differs")
    tree_sha = _sha40(tree.get("sha"), "current Fleet main tree")
    return {"protected": True, "commit": execution_sha, "tree": tree_sha}


def validate_replay_snapshot(
    value: Mapping[str, Any], inputs: Mapping[str, Any]
) -> dict[str, Any]:
    total = value.get("total_count")
    artifacts = value.get("artifacts")
    if type(total) is not int or total < 0 or not isinstance(artifacts, list):
        raise ApprovalError("approval artifact ledger snapshot is malformed")
    expected_name = approval_artifact_name(inputs)
    matching = [
        row for row in artifacts
        if isinstance(row, dict) and row.get("name") == expected_name
    ]
    if total != len(artifacts) or total != len(matching):
        raise ApprovalError("approval artifact ledger response is not exact")
    if matching:
        raise ApprovalError("Two-Green artifact was already approved")
    return {
        "mode": "artifact_observation_only_incomplete",
        "artifactName": expected_name,
        "priorApprovalArtifactCount": 0,
    }


def validate_external_reservation_snapshot(
    path: Path, policy: Mapping[str, Any], inputs: Mapping[str, Any],
    policy_sha256: str, *, now: datetime,
) -> dict[str, Any]:
    data, snapshot_sha256 = stable_file(
        path, "durable external reservation receipt", MAX_RECEIPT_BYTES
    )
    subject = approval_ledger.make_subject(
        approval_request_nonce=inputs["approvalRequestNonce"],
        two_green_artifact_id=inputs["twoGreenArtifactId"],
        two_green_artifact_sha256=inputs["twoGreenArtifactSha256"],
        two_green_receipt_sha256=inputs["twoGreenReceiptSha256"],
        main_tree=inputs["mainTree"],
        policy_sha256=policy_sha256,
        version_name=inputs["versionName"],
        version_code=inputs["versionCode"],
    )
    request = approval_ledger._request("reserve", subject)
    response = approval_ledger.validate_response(
        approval_ledger.strict_json_bytes(
            data, "durable external reservation receipt", MAX_RECEIPT_BYTES
        ),
        request=request,
        policy=policy["replay_protection"]["external_ledger"],
        now=now,
    )
    receipt = response["receipt"]
    if receipt["state"] != "reserved":
        raise ApprovalError("durable external reservation is not open for approval")
    return {
        "mode": "durable_external_exactly_once",
        "serviceIdentity": receipt["serviceIdentity"],
        "reservationId": receipt["reservationId"],
        "reservationState": "reserved",
        "reservationRevision": receipt["revision"],
        "reservationCreatedAtUtc": receipt["reservedAtUtc"],
        "reservationLeaseExpiresAtUtc": receipt["leaseExpiresAtUtc"],
        "reservationRequestId": receipt["requestId"],
        "reservationSubjectSha256": receipt["subjectSha256"],
        "reservationReceiptSha256": response["receiptSha256"],
        "reservationSnapshotSha256": snapshot_sha256,
        "uniquenessSubjects": approval_ledger.UNIQUENESS_SUBJECTS,
        "durabilityClass": "external_durable",
        "exactlyOnce": True,
        "receiptPublicKeySpkiSha256": response["signature"]["publicKeySpkiSha256"],
    }


def extract_receipt(
    archive_path: Path, inputs: Mapping[str, Any]
) -> tuple[dict[str, Any], bytes, int]:
    data, digest = stable_file(archive_path, "Two-Green artifact archive", MAX_ARCHIVE_BYTES)
    if digest != inputs["twoGreenArtifactSha256"]:
        raise ApprovalError("Two-Green artifact archive SHA-256 differs")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != RECEIPT_NAME:
                raise ApprovalError(f"Two-Green archive must contain exactly {RECEIPT_NAME}")
            member = members[0]
            mode = (member.external_attr >> 16) & 0xFFFF
            if member.is_dir() or member.flag_bits & 1 or stat.S_IFMT(mode) == stat.S_IFLNK or member.file_size <= 0 or member.file_size > MAX_RECEIPT_BYTES:
                raise ApprovalError("Two-Green receipt member is unsafe")
            receipt_bytes = archive.read(member)
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise ApprovalError("Two-Green artifact archive is invalid") from error
    if hashlib.sha256(receipt_bytes).hexdigest() != inputs["twoGreenReceiptSha256"]:
        raise ApprovalError("Two-Green receipt SHA-256 differs")
    return strict_json_bytes(receipt_bytes, "Two-Green receipt"), receipt_bytes, len(data)


def validate_receipt(
    value: Mapping[str, Any], inputs: Mapping[str, Any], *, now: datetime,
    policy: Mapping[str, Any]
) -> dict[str, Any]:
    required = {
        "schema", "status", "eligibilityScope", "eligible", "internalTestingEligible",
        "publicationAuthorized", "googlePlayUploadAuthorized", "policyAuthority",
        "sourceCommit", "sourceTree", "releaseIdentity", "commonAuthority",
        "reviewRun", "mainRun", "decisionTimeUtc", "reviewPullRequest",
        "doesNotAssert", "eligibilitySha256",
    }
    _exact_keys(value, required, "Two-Green receipt")
    if (
        value.get("schema") != TWO_GREEN_CONTRACT
        or value.get("status") != "pass"
        or value.get("eligibilityScope") != "current_preview_internal_testing_candidate"
        or value.get("eligible") is not True
        or value.get("internalTestingEligible") is not True
        or value.get("publicationAuthorized") is not False
        or value.get("googlePlayUploadAuthorized") is not False
        or value.get("sourceCommit") != inputs["mainCommit"]
        or value.get("sourceTree") != inputs["mainTree"]
    ):
        raise ApprovalError("Two-Green receipt posture or Android identity differs")
    _, decision_time = _fresh_timestamp(
        value.get("decisionTimeUtc"), "Two-Green receipt decision", now=now,
        policy=policy,
    )
    release = value.get("releaseIdentity")
    if not isinstance(release, dict) or release != {
        "packageId": PACKAGE_ID,
        "versionName": VERSION_NAME,
        "versionCode": VERSION_CODE,
        "intentAuthority": "android_project_at_exact_main_tree",
    }:
        raise ApprovalError("Two-Green receipt release identity differs")
    for role, expected_id in (("reviewRun", inputs["reviewRunId"]), ("mainRun", inputs["mainRunId"])):
        block = value.get(role)
        run = block.get("run") if isinstance(block, dict) else None
        if not isinstance(run, dict) or run.get("id") != expected_id or run.get("status") != "completed" or run.get("conclusion") != "success" or block.get("aggregateStatus") != "pass":
            raise ApprovalError(f"Two-Green {role} is not exact and successful")
    review_pull_request = value.get("reviewPullRequest")
    if (
        not isinstance(review_pull_request, dict)
        or review_pull_request.get("repository") != ANDROID_REPOSITORY
        or review_pull_request.get("number") != inputs["reviewPullRequestNumber"]
    ):
        raise ApprovalError("Two-Green reviewed pull request differs")
    main = value["mainRun"]["run"]
    if main.get("headSha") != inputs["mainCommit"] or value["mainRun"].get("p0EventSha") != inputs["mainCommit"]:
        raise ApprovalError("Two-Green main source commit differs")
    common = value.get("commonAuthority")
    if not isinstance(common, dict) or common.get("androidTree") != inputs["mainTree"] or common.get("environmentCompatibilityStatus") != "pass":
        raise ApprovalError("Two-Green common tree/environment authority differs")
    dependency_graph = common.get("dependencyGraph")
    environment_policy = common.get("environmentPolicy")
    if not isinstance(dependency_graph, dict) or not isinstance(environment_policy, dict):
        raise ApprovalError("Two-Green receipt omits Android consumer authority")
    dependency_graph_sha256 = _sha256(
        dependency_graph.get("sha256"), "Two-Green dependency graph digest"
    )
    environment_policy_sha256 = _sha256(
        environment_policy.get("sha256"), "Two-Green environment policy digest"
    )
    policy_authority = value.get("policyAuthority")
    if (
        not isinstance(policy_authority, dict)
        or policy_authority.get("schema")
        != "chummer.android.api36-ordered-review-main-green-policy/v2"
        or policy_authority.get("path")
        != "eng/api36-two-consecutive-green-authority.json"
        or policy_authority.get("publicationAuthorized") is not False
    ):
        raise ApprovalError("Two-Green policy authority differs")
    _sha256(policy_authority.get("sha256"), "Two-Green policy digest")
    _positive(policy_authority.get("sizeBytes"), "Two-Green policy size")
    does_not_assert = value.get("doesNotAssert")
    for required_exclusion in ("google_play_upload", "release_signing", "publication_authority"):
        if not isinstance(does_not_assert, list) or required_exclusion not in does_not_assert:
            raise ApprovalError("Two-Green receipt omits a required non-authority boundary")
    unsigned = {key: member for key, member in value.items() if key != "eligibilitySha256"}
    if value.get("eligibilitySha256") != canonical_sha256(unsigned):
        raise ApprovalError("Two-Green eligibility digest is invalid")
    return {
        "contract": TWO_GREEN_CONTRACT,
        "eligibilitySha256": value["eligibilitySha256"],
        "decisionTimeUtc": decision_time,
        "reviewPullRequestNumber": inputs["reviewPullRequestNumber"],
        "reviewRunId": inputs["reviewRunId"],
        "mainRunId": inputs["mainRunId"],
        "dependencyGraphSha256": dependency_graph_sha256,
        "environmentPolicySha256": environment_policy_sha256,
        "status": "pass",
        "eligible": True,
        "internalTestingEligible": True,
    }


def _openssl(arguments: list[str], *, input_bytes: bytes | None = None, pass_fds: tuple[int, ...] = ()) -> bytes:
    try:
        completed = subprocess.run(
            ["/usr/bin/openssl", *arguments],
            input=input_bytes,
            check=False,
            capture_output=True,
            timeout=10,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            pass_fds=pass_fds,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ApprovalError("Ed25519 provider is unavailable") from error
    if completed.returncode != 0:
        raise ApprovalError("Ed25519 operation failed")
    return completed.stdout


def sign_ed25519(message: bytes, policy: Mapping[str, Any], environment: Mapping[str, str]) -> dict[str, str]:
    encoded = environment.get(KEY_ENV_NAME)
    if environment is os.environ:
        os.environ.pop(KEY_ENV_NAME, None)
    if not encoded:
        raise ApprovalError("external Ed25519 environment key is missing")
    if len(encoded) > 16384:
        raise ApprovalError("external Ed25519 environment key is oversized")
    try:
        private_der = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ApprovalError("external Ed25519 environment key is not strict Base64") from error
    if not 32 <= len(private_der) <= 4096:
        raise ApprovalError("external Ed25519 PKCS#8 key has an invalid size")
    key_fd = os.memfd_create("preview12-approval-key", flags=getattr(os, "MFD_CLOEXEC", 0))
    message_fd = os.memfd_create("preview12-approval-message", flags=getattr(os, "MFD_CLOEXEC", 0))
    try:
        os.write(key_fd, private_der)
        os.lseek(key_fd, 0, os.SEEK_SET)
        os.write(message_fd, message)
        os.lseek(message_fd, 0, os.SEEK_SET)
        key_path = f"/proc/self/fd/{key_fd}"
        public_der = _openssl(
            ["pkey", "-inform", "DER", "-in", key_path, "-pubout", "-outform", "DER"],
            pass_fds=(key_fd,),
        )
        if len(public_der) != len(SPKI_ED25519_PREFIX) + 32 or not public_der.startswith(SPKI_ED25519_PREFIX):
            raise ApprovalError("external key is not Ed25519")
        public_digest = hashlib.sha256(public_der).hexdigest()
        expected = policy["external_ed25519_key"]["expected_public_key_spki_sha256"]
        if public_digest != expected:
            raise ApprovalError("external Ed25519 public key differs from reviewed policy")
        os.lseek(key_fd, 0, os.SEEK_SET)
        signature = _openssl(
            ["pkeyutl", "-sign", "-rawin", "-inkey", key_path, "-keyform", "DER", "-in", f"/proc/self/fd/{message_fd}"],
            pass_fds=(key_fd, message_fd),
        )
    finally:
        os.close(key_fd)
        os.close(message_fd)
        private_der = b""
    if len(signature) != 64:
        raise ApprovalError("Ed25519 signature size differs")
    verify_ed25519(public_der, message, signature)
    return {
        "algorithm": "Ed25519",
        "encoding": "base64",
        "publicKeySpkiDerBase64": base64.b64encode(public_der).decode("ascii"),
        "publicKeySpkiSha256": public_digest,
        "signatureBase64": base64.b64encode(signature).decode("ascii"),
    }


def verify_ed25519(public_der: bytes, message: bytes, signature: bytes) -> None:
    public_fd = os.memfd_create("preview12-approval-public-key", flags=getattr(os, "MFD_CLOEXEC", 0))
    message_fd = os.memfd_create("preview12-approval-message", flags=getattr(os, "MFD_CLOEXEC", 0))
    signature_fd = os.memfd_create("preview12-approval-signature", flags=getattr(os, "MFD_CLOEXEC", 0))
    try:
        os.write(public_fd, public_der)
        os.lseek(public_fd, 0, os.SEEK_SET)
        os.write(message_fd, message)
        os.lseek(message_fd, 0, os.SEEK_SET)
        os.write(signature_fd, signature)
        os.lseek(signature_fd, 0, os.SEEK_SET)
        _openssl(
            ["pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", f"/proc/self/fd/{public_fd}", "-keyform", "DER", "-in", f"/proc/self/fd/{message_fd}", "-sigfile", f"/proc/self/fd/{signature_fd}"],
            pass_fds=(public_fd, message_fd, signature_fd),
        )
    finally:
        os.close(public_fd)
        os.close(message_fd)
        os.close(signature_fd)


def _create_fleet_audit_receipt(
    args: argparse.Namespace, environment: Mapping[str, str], *,
    now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo != timezone.utc:
        raise ApprovalError("approval clock must be UTC")
    policy, policy_bytes, policy_sha256 = load_policy(args.policy)
    _require_ready(policy)
    inputs = validate_inputs(args)
    environment_bytes, environment_sha256 = stable_file(args.environment_snapshot, "GitHub environment snapshot", MAX_RECEIPT_BYTES)
    environment_value = strict_json_bytes(environment_bytes, "GitHub environment snapshot")
    environment_authority = validate_environment_snapshot(environment_value, policy)
    run_bytes, run_sha256 = stable_file(args.run_snapshot, "Two-Green run snapshot", MAX_RECEIPT_BYTES)
    run_authority = validate_run(
        strict_json_bytes(run_bytes, "Two-Green run snapshot"), inputs,
        now=now, policy=policy,
    )
    artifact_bytes, artifact_metadata_sha256 = stable_file(args.artifact_snapshot, "Two-Green artifact snapshot", MAX_RECEIPT_BYTES)
    artifact_authority = validate_artifact(
        strict_json_bytes(artifact_bytes, "Two-Green artifact snapshot"), inputs,
        now=now, policy=policy,
    )
    artifact_created = _timestamp(
        artifact_authority["createdAtUtc"], "Two-Green artifact creation"
    )
    attempt_started = _timestamp(
        run_authority["attemptStartedAtUtc"], "Two-Green run attempt start"
    )
    run_completed = _timestamp(
        run_authority["completedAtUtc"], "Two-Green run completion"
    )
    if not attempt_started <= artifact_created <= (
        run_completed
        + timedelta(seconds=policy["freshness"]["maximum_future_skew_seconds"])
    ):
        raise ApprovalError("Two-Green artifact is not bound to the exact run attempt")
    receipt, receipt_bytes, archive_size = extract_receipt(args.artifact_archive, inputs)
    if archive_size != artifact_authority["archiveSizeBytes"]:
        raise ApprovalError("Two-Green artifact archive size differs")
    receipt_authority = validate_receipt(receipt, inputs, now=now, policy=policy)
    branch_bytes, branch_sha256 = stable_file(
        args.android_main_branch_snapshot, "Android main branch snapshot",
        MAX_RECEIPT_BYTES,
    )
    commit_bytes, commit_sha256 = stable_file(
        args.android_main_commit_snapshot, "Android main commit snapshot",
        MAX_RECEIPT_BYTES,
    )
    android_main_authority = validate_android_main_snapshots(
        strict_json_bytes(branch_bytes, "Android main branch snapshot"),
        strict_json_bytes(commit_bytes, "Android main commit snapshot"),
        inputs,
    )
    fleet_branch_bytes, fleet_branch_sha256 = stable_file(
        args.fleet_main_branch_snapshot, "Fleet main branch snapshot",
        MAX_RECEIPT_BYTES,
    )
    fleet_commit_bytes, fleet_commit_sha256 = stable_file(
        args.fleet_main_commit_snapshot, "Fleet main commit snapshot",
        MAX_RECEIPT_BYTES,
    )
    fleet_main_authority = validate_fleet_main_snapshots(
        strict_json_bytes(fleet_branch_bytes, "Fleet main branch snapshot"),
        strict_json_bytes(fleet_commit_bytes, "Fleet main commit snapshot"),
        args.execution_sha,
    )
    replay_bytes, replay_sha256 = stable_file(
        args.approval_artifact_ledger_snapshot,
        "approval artifact ledger snapshot", MAX_RECEIPT_BYTES,
    )
    replay_authority = validate_replay_snapshot(
        strict_json_bytes(replay_bytes, "approval artifact ledger snapshot"), inputs
    )
    durable_replay_authority = validate_external_reservation_snapshot(
        args.ledger_reservation_snapshot, policy, inputs, policy_sha256, now=now
    )
    if args.execution_environment != ENVIRONMENT_NAME:
        raise ApprovalError("approval job did not run in the reviewed GitHub environment")
    execution = {
        "repository": FLEET_REPOSITORY,
        "ref": FLEET_REF,
        "protectedRef": args.execution_ref_protected == "true",
        "event": args.execution_event,
        "commit": _sha40(args.execution_sha, "Fleet execution SHA"),
        "workflowRepository": args.workflow_repository,
        "workflowRef": args.workflow_ref,
        "workflowSha": _sha40(args.workflow_sha, "Fleet workflow SHA"),
        "runId": _positive_decimal(args.execution_run_id, "Fleet run ID"),
        "runAttempt": _positive_decimal(args.execution_run_attempt, "Fleet run attempt"),
        "environment": ENVIRONMENT_NAME,
        "currentMainAuthority": {
            **fleet_main_authority,
            "branchApiSnapshotSha256": fleet_branch_sha256,
            "commitApiSnapshotSha256": fleet_commit_sha256,
        },
    }
    if (
        execution["ref"] != args.execution_ref
        or execution["protectedRef"] is not True
        or execution["event"] != "workflow_dispatch"
        or execution["workflowRepository"] != FLEET_REPOSITORY
        or execution["workflowRef"] != f"{FLEET_REPOSITORY}/{WORKFLOW_PATH}@refs/heads/main"
        or execution["workflowSha"] != execution["commit"]
    ):
        raise ApprovalError("Fleet approval execution is not exact protected main")
    statement = {
        "contractName": FLEET_AUDIT_CONTRACT,
        "contractVersion": 1,
        "status": "approved",
        "approvalScope": "preview12_two_green_evidence_only",
        "approvalRequestNonce": inputs["approvalRequestNonce"],
        "approvedAtUtc": _iso(now),
        "release": {"packageId": PACKAGE_ID, "versionName": VERSION_NAME, "versionCode": VERSION_CODE},
        "androidSource": {
            "repository": ANDROID_REPOSITORY,
            "ref": ANDROID_REF,
            "commit": inputs["mainCommit"],
            "tree": inputs["mainTree"],
            "currentMainAuthority": {
                **android_main_authority,
                "branchApiSnapshotSha256": branch_sha256,
                "commitApiSnapshotSha256": commit_sha256,
            },
        },
        "twoGreen": {
            "workflowRun": run_authority,
            "artifact": artifact_authority,
            "receipt": receipt_authority,
            "receiptSha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "runSnapshotSha256": run_sha256,
            "artifactMetadataSnapshotSha256": artifact_metadata_sha256,
        },
        "fleetExecution": execution,
        "environmentAuthority": {
            **environment_authority,
            "apiSnapshotSha256": environment_sha256,
        },
        "freshnessAuthority": {
            "maximumEvidenceAgeSeconds": policy["freshness"]["maximum_evidence_age_seconds"],
            "maximumFutureSkewSeconds": policy["freshness"]["maximum_future_skew_seconds"],
            "checkedAtUtc": _iso(now),
        },
        "replayProtection": {
            **durable_replay_authority,
            "approvalRequestNonce": inputs["approvalRequestNonce"],
            "githubArtifactObservation": {
                **replay_authority,
                "ledgerApiSnapshotSha256": replay_sha256,
                "authoritative": False,
            },
        },
        "policyAuthority": {
            "contract": POLICY_CONTRACT,
            "sha256": policy_sha256,
            "sizeBytes": len(policy_bytes),
            "activationWasReady": True,
        },
        "twoGreenVerified": True,
        "humanEnvironmentReviewRequired": True,
        "configuredHumanReviewerSetPinned": True,
        "protectedEnvironmentGatePassed": True,
        "actualApprovalActorRecorded": False,
        "signingAuthorized": False,
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
        "doesNotAuthorize": DOES_NOT_AUTHORIZE,
    }
    return statement


def release_approval_unsigned(
    audit_receipt: Mapping[str, Any],
    *,
    generated_at_utc: str,
    expires_at_utc: str,
    challenge_nonce: str,
) -> dict[str, Any]:
    """Project Fleet evidence into Android 388425ace's exact signed fields."""
    source = audit_receipt.get("androidSource")
    release = audit_receipt.get("release")
    two_green = audit_receipt.get("twoGreen")
    receipt = two_green.get("receipt") if isinstance(two_green, dict) else None
    if not all(isinstance(value, dict) for value in (source, release, two_green, receipt)):
        raise ApprovalError("Fleet audit receipt cannot project Android approval authority")
    return {
        "contractName": OUTPUT_CONTRACT,
        "algorithm": "ed25519",
        "keyId": RELEASE_APPROVER_KEY_ID,
        "role": RELEASE_APPROVER_ROLE,
        "approvalScope": RELEASE_APPROVAL_SCOPE,
        "generatedAtUtc": generated_at_utc,
        "expiresAtUtc": expires_at_utc,
        "challengeNonce": _sha256(challenge_nonce, "release approval challenge nonce"),
        "provenanceValidatorSha256": PROVENANCE_VALIDATOR_SHA256,
        "provenanceReplaySha256": canonical_sha256(audit_receipt),
        "receiptSha256": _sha256(
            two_green.get("receiptSha256"), "Two-Green receipt digest"
        ),
        "eligibilitySha256": _sha256(
            receipt.get("eligibilitySha256"), "Two-Green eligibility digest"
        ),
        "sourceCommit": _sha40(source.get("commit"), "Android source commit"),
        "sourceTree": _sha40(source.get("tree"), "Android source tree"),
        "versionName": release.get("versionName"),
        "versionCode": release.get("versionCode"),
        "dependencyGraphSha256": _sha256(
            receipt.get("dependencyGraphSha256"), "Two-Green dependency graph digest"
        ),
        "environmentPolicySha256": _sha256(
            receipt.get("environmentPolicySha256"), "Two-Green environment policy digest"
        ),
        "signingAuthorized": False,
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
    }


def create_approval_bundle(
    args: argparse.Namespace,
    environment: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    audit_receipt = _create_fleet_audit_receipt(args, environment, now=now)
    generated_at_utc = _iso(now)
    expires_at_utc = _iso(now + timedelta(seconds=APPROVAL_LIFETIME_SECONDS))
    unsigned = release_approval_unsigned(
        audit_receipt,
        generated_at_utc=generated_at_utc,
        expires_at_utc=expires_at_utc,
        challenge_nonce=audit_receipt["approvalRequestNonce"],
    )
    policy, _, _ = load_policy(args.policy)
    signature = sign_ed25519(android_canonical_bytes(unsigned), policy, environment)
    approval = {**unsigned, "signatureBase64": signature["signatureBase64"]}
    validate_approval(
        approval,
        policy=policy,
        audit_receipt=audit_receipt,
        expected_challenge_nonce=audit_receipt["approvalRequestNonce"],
        now=now,
    )
    return approval, audit_receipt


def create_approval(
    args: argparse.Namespace,
    environment: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    approval, _ = create_approval_bundle(args, environment, now=now)
    return approval


def validate_approval(
    value: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
    *,
    audit_receipt: Mapping[str, Any] | None = None,
    expected_challenge_nonce: str | None = None,
    now: datetime | None = None,
) -> None:
    """Validate exactly the approval accepted by Android at 388425ace."""
    fields = {
        "contractName", "algorithm", "keyId", "role", "approvalScope",
        "generatedAtUtc", "expiresAtUtc", "challengeNonce",
        "provenanceValidatorSha256", "provenanceReplaySha256",
        "receiptSha256", "eligibilitySha256", "sourceCommit", "sourceTree",
        "versionName", "versionCode", "dependencyGraphSha256",
        "environmentPolicySha256", "signingAuthorized",
        "publicationAuthorized", "googlePlayUploadAuthorized", "signatureBase64",
    }
    _exact_keys(value, fields, "Android release approval")
    if (
        value.get("contractName") != OUTPUT_CONTRACT
        or value.get("algorithm") != "ed25519"
        or value.get("keyId") != RELEASE_APPROVER_KEY_ID
        or value.get("role") != RELEASE_APPROVER_ROLE
        or value.get("approvalScope") != RELEASE_APPROVAL_SCOPE
        or value.get("signingAuthorized") is not False
        or value.get("publicationAuthorized") is not False
        or value.get("googlePlayUploadAuthorized") is not False
    ):
        raise ApprovalError("Android release approval posture is invalid")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo != timezone.utc:
        raise ApprovalError("approval verification clock must be UTC")
    generated = _timestamp(value.get("generatedAtUtc"), "release approval generation")
    expires = _timestamp(value.get("expiresAtUtc"), "release approval expiry")
    if (
        generated > current + timedelta(seconds=APPROVAL_CLOCK_SKEW_SECONDS)
        or expires <= generated
        or expires - generated > timedelta(seconds=MAX_APPROVAL_LIFETIME_SECONDS)
        or current >= expires
    ):
        raise ApprovalError("Android release approval is stale or outside its lifetime")
    if (
        value.get("sourceCommit") != ANDROID_CONSUMER_COMMIT
        or value.get("sourceTree") != ANDROID_CONSUMER_TREE
        or value.get("versionName") != VERSION_NAME
        or value.get("versionCode") != VERSION_CODE
        or value.get("provenanceValidatorSha256") != PROVENANCE_VALIDATOR_SHA256
    ):
        raise ApprovalError("Android release approval source/version authority differs")
    for field in (
        "challengeNonce", "provenanceReplaySha256", "receiptSha256",
        "eligibilitySha256", "dependencyGraphSha256", "environmentPolicySha256",
    ):
        _sha256(value.get(field), f"Android release approval {field}")
    if (
        expected_challenge_nonce is not None
        and value.get("challengeNonce") != expected_challenge_nonce
    ):
        raise ApprovalError("Android release approval challenge nonce was replayed")
    if (
        audit_receipt is not None
        and value.get("provenanceReplaySha256") != canonical_sha256(audit_receipt)
    ):
        raise ApprovalError("Android release approval replay provenance differs")
    if audit_receipt is not None:
        expected_unsigned = release_approval_unsigned(
            audit_receipt,
            generated_at_utc=value["generatedAtUtc"],
            expires_at_utc=value["expiresAtUtc"],
            challenge_nonce=value["challengeNonce"],
        )
        if any(value.get(field) != member for field, member in expected_unsigned.items()):
            raise ApprovalError("Android release approval claims differ from Fleet evidence")
    effective_policy = policy or expected_policy()
    key = effective_policy.get("external_ed25519_key")
    if not isinstance(key, dict):
        raise ApprovalError("Android release approver key policy is missing")
    if (
        key.get("key_id") != RELEASE_APPROVER_KEY_ID
        or key.get("public_key_spki_der_base64")
        != RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64
        or key.get("expected_public_key_spki_sha256")
        != RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256
    ):
        raise ApprovalError("Android release approver public-key pin differs")
    try:
        public_der = base64.b64decode(
            key["public_key_spki_der_base64"], validate=True
        )
        signature = base64.b64decode(value.get("signatureBase64"), validate=True)
    except (binascii.Error, TypeError, ValueError) as error:
        raise ApprovalError("Android release approval signature is not strict Base64") from error
    if (
        len(public_der) != len(SPKI_ED25519_PREFIX) + 32
        or not public_der.startswith(SPKI_ED25519_PREFIX)
        or hashlib.sha256(public_der).hexdigest()
        != key["expected_public_key_spki_sha256"]
        or len(signature) != 64
    ):
        raise ApprovalError("Android release approval Ed25519 authority differs")
    unsigned = {key: member for key, member in value.items() if key != "signatureBase64"}
    verify_ed25519(public_der, android_canonical_bytes(unsigned), signature)


def write_output(path: Path, value: Mapping[str, Any], *, expected_name: str = OUTPUT_NAME) -> None:
    if path.name != expected_name or not path.is_absolute() or path.is_symlink():
        raise ApprovalError(f"output must be an absolute non-symlink {expected_name}")
    parent = path.parent
    if parent.is_symlink() or parent.resolve(strict=True) != parent:
        raise ApprovalError("output parent must be canonical and non-symlinked")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=parent, prefix=f".{expected_name}.", delete=False) as stream:
            temporary = stream.name
            os.fchmod(stream.fileno(), 0o600)
            stream.write(pretty_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)


def _input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--approval-request-nonce", required=True)
    parser.add_argument("--two-green-run-id", required=True)
    parser.add_argument("--two-green-run-attempt", required=True)
    parser.add_argument("--two-green-artifact-id", required=True)
    parser.add_argument("--two-green-artifact-sha256", required=True)
    parser.add_argument("--two-green-receipt-sha256", required=True)
    parser.add_argument("--review-run-id", required=True)
    parser.add_argument("--review-pull-request-number", required=True)
    parser.add_argument("--main-run-id", required=True)
    parser.add_argument("--main-commit", required=True)
    parser.add_argument("--main-tree", required=True)
    parser.add_argument("--version-name", required=True)
    parser.add_argument("--version-code", required=True)


def _execution_arguments(parser: argparse.ArgumentParser, *, environment: bool) -> None:
    parser.add_argument("--execution-repository", required=True)
    parser.add_argument("--execution-ref", required=True)
    parser.add_argument("--execution-ref-protected", required=True)
    parser.add_argument("--execution-event", required=True)
    parser.add_argument("--execution-sha", required=True)
    parser.add_argument("--workflow-repository", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--workflow-sha", required=True)
    if environment:
        parser.add_argument("--execution-run-id", required=True)
        parser.add_argument("--execution-run-attempt", required=True)
        parser.add_argument("--execution-environment", required=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    _input_arguments(preflight)
    _execution_arguments(preflight, environment=False)
    approve = subparsers.add_parser("approve")
    _input_arguments(approve)
    _execution_arguments(approve, environment=True)
    approve.add_argument("--environment-snapshot", type=Path, required=True)
    approve.add_argument("--ledger-reservation-snapshot", type=Path, required=True)
    approve.add_argument("--run-snapshot", type=Path, required=True)
    approve.add_argument("--artifact-snapshot", type=Path, required=True)
    approve.add_argument("--artifact-archive", type=Path, required=True)
    approve.add_argument("--android-main-branch-snapshot", type=Path, required=True)
    approve.add_argument("--android-main-commit-snapshot", type=Path, required=True)
    approve.add_argument("--fleet-main-branch-snapshot", type=Path, required=True)
    approve.add_argument("--fleet-main-commit-snapshot", type=Path, required=True)
    approve.add_argument(
        "--approval-artifact-ledger-snapshot", type=Path, required=True
    )
    approve.add_argument("--output", type=Path, required=True)
    approve.add_argument("--audit-output", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--approval", type=Path, required=True)
    verify.add_argument("--audit-receipt", type=Path)
    verify.add_argument("--expected-challenge-nonce")
    args = parser.parse_args(argv)
    if args.command == "verify":
        policy, _, _ = load_policy(args.policy)
        data, _ = stable_file(args.approval, "public approval", MAX_RECEIPT_BYTES)
        value = strict_json_bytes(data, "public approval")
        audit_receipt = None
        if args.audit_receipt is not None:
            audit_data, _ = stable_file(
                args.audit_receipt, "Fleet approval audit receipt", MAX_RECEIPT_BYTES
            )
            audit_receipt = strict_json_bytes(
                audit_data, "Fleet approval audit receipt"
            )
        validate_approval(
            value,
            policy,
            audit_receipt=audit_receipt,
            expected_challenge_nonce=args.expected_challenge_nonce,
        )
        print("preview12_release_approval=verified signing_authorized=false publication_authorized=false google_play_upload_authorized=false")
        return 0
    policy, _, _ = load_policy(args.policy)
    if args.command == "preflight":
        result = validate_dispatch(policy, args)
        print(json.dumps(result, sort_keys=True))
        return 0
    result, audit_receipt = create_approval_bundle(args, os.environ)
    validate_approval(
        result,
        policy,
        audit_receipt=audit_receipt,
        expected_challenge_nonce=result["challengeNonce"],
    )
    write_output(args.output, result)
    write_output(args.audit_output, audit_receipt, expected_name=AUDIT_OUTPUT_NAME)
    print("preview12_release_approval=approved signing_authorized=false publication_authorized=false google_play_upload_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
