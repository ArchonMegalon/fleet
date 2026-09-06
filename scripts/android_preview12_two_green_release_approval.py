#!/usr/bin/env python3
"""Verify Preview12 Two-Green evidence and sign only a public approval JSON.

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


POLICY_CONTRACT = "fleet.android_preview12_two_green_release_approval_policy.v1"
OUTPUT_CONTRACT = "fleet.android_preview12_two_green_release_approval.v1"
TWO_GREEN_CONTRACT = "chummer.android.api36-ordered-review-main-green-eligibility/v2"
FLEET_REPOSITORY = "ArchonMegalon/fleet"
ANDROID_REPOSITORY = "ArchonMegalon/chummer-android"
FLEET_REF = "refs/heads/main"
ANDROID_REF = "refs/heads/main"
WORKFLOW_PATH = ".github/workflows/android-preview12-two-green-release-approval.yml"
TWO_GREEN_WORKFLOW_NAME = "API 36 ordered review-to-main green eligibility"
TWO_GREEN_WORKFLOW_PATH = ".github/workflows/api36-two-consecutive-green.yml"
RECEIPT_NAME = "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json"
OUTPUT_NAME = "ANDROID_PREVIEW12_TWO_GREEN_RELEASE_APPROVAL.public.json"
ENVIRONMENT_NAME = "android-preview12-release-approval"
KEY_ENV_NAME = "ANDROID_PREVIEW12_RELEASE_APPROVAL_ED25519_PRIVATE_KEY_PKCS8_B64"
PACKAGE_ID = "com.myexternalbrain.chummer"
VERSION_NAME = "0.1.0-preview.12"
VERSION_CODE = 12
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
        "state": "dormant_pending_environment_external_key_and_durable_replay",
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
            "expected_public_key_spki_sha256": None,
            "private_key_persistence_allowed": False,
        },
        "freshness": {
            "maximum_evidence_age_seconds": MAX_EVIDENCE_AGE_SECONDS,
            "maximum_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
        },
        "replay_protection": {
            "mode": "artifact_observation_only_incomplete",
            "approval_request_nonce_required": True,
            "artifact_ledger_required": True,
            "durable_external_reservation_required": True,
            "durable_reservation_subjects": [
                "two_green_artifact_id", "approval_request_nonce"
            ],
            "durable_external_reservation_configured": False,
            "authority_complete": False,
        },
        "activation": {"enabled": False,
                       "requires_separate_reviewed_contract_change": True},
        "output": {
            "contract_name": OUTPUT_CONTRACT,
            "approval_scope": "preview12_two_green_evidence_only",
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
        observed_key_digest = value.get("external_ed25519_key", {}).get(
            "expected_public_key_spki_sha256"
        ) if isinstance(value.get("external_ed25519_key"), dict) else None
        if SHA256.fullmatch(str(observed_key_digest or "")):
            active["external_ed25519_key"]["expected_public_key_spki_sha256"] = observed_key_digest
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
        or replay.get("durable_external_reservation_required") is not True
        or replay.get("durable_reservation_subjects")
        != ["two_green_artifact_id", "approval_request_nonce"]
        or replay.get("durable_external_reservation_configured") is not True
        or replay.get("authority_complete") is not True
    ):
        blockers.append("durable external replay reservation authority is incomplete")
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


def create_approval(
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
        "contractName": OUTPUT_CONTRACT,
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
            **replay_authority,
            "ledgerApiSnapshotSha256": replay_sha256,
            "approvalRequestNonce": inputs["approvalRequestNonce"],
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
    approval_sha256 = canonical_sha256(statement)
    signature = sign_ed25519(canonical_bytes(statement), policy, environment)
    return {**statement, "approvalSha256": approval_sha256, "signature": signature}


def validate_approval(
    value: Mapping[str, Any], policy: Mapping[str, Any] | None = None, *,
    now: datetime | None = None
) -> None:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo != timezone.utc:
        raise ApprovalError("approval verification clock must be UTC")
    required = {
        "contractName", "contractVersion", "status", "approvalScope",
        "approvalRequestNonce", "approvedAtUtc", "release",
        "androidSource", "twoGreen", "fleetExecution", "environmentAuthority",
        "freshnessAuthority", "replayProtection", "policyAuthority",
        "twoGreenVerified", "humanEnvironmentReviewRequired",
        "configuredHumanReviewerSetPinned", "protectedEnvironmentGatePassed",
        "actualApprovalActorRecorded", "signingAuthorized",
        "publicationAuthorized", "googlePlayUploadAuthorized", "doesNotAuthorize",
        "approvalSha256", "signature",
    }
    _exact_keys(value, required, "public approval")
    if (
        value.get("contractName") != OUTPUT_CONTRACT
        or value.get("contractVersion") != 1
        or value.get("status") != "approved"
        or value.get("approvalScope") != "preview12_two_green_evidence_only"
        or SHA256.fullmatch(str(value.get("approvalRequestNonce") or "")) is None
        or value.get("twoGreenVerified") is not True
        or value.get("humanEnvironmentReviewRequired") is not True
        or value.get("configuredHumanReviewerSetPinned") is not True
        or value.get("protectedEnvironmentGatePassed") is not True
        or value.get("actualApprovalActorRecorded") is not False
        or value.get("signingAuthorized") is not False
        or value.get("publicationAuthorized") is not False
        or value.get("googlePlayUploadAuthorized") is not False
        or value.get("doesNotAuthorize") != DOES_NOT_AUTHORIZE
    ):
        raise ApprovalError("public approval posture is invalid")
    effective_policy = policy or expected_policy()
    _fresh_timestamp(
        value.get("approvedAtUtc"), "public approval time", now=now,
        policy=effective_policy,
    )
    release = value.get("release")
    if release != {
        "packageId": PACKAGE_ID,
        "versionName": VERSION_NAME,
        "versionCode": VERSION_CODE,
    }:
        raise ApprovalError("public approval release identity differs")
    source = value.get("androidSource")
    if (
        not isinstance(source, dict)
        or set(source) != {"repository", "ref", "commit", "tree", "currentMainAuthority"}
        or source.get("repository") != ANDROID_REPOSITORY
        or source.get("ref") != ANDROID_REF
    ):
        raise ApprovalError("public approval Android source identity differs")
    source_commit = _sha40(source.get("commit"), "public approval Android commit")
    source_tree = _sha40(source.get("tree"), "public approval Android tree")
    current_main = source.get("currentMainAuthority")
    if (
        not isinstance(current_main, dict)
        or set(current_main) != {
            "protected", "commit", "tree", "branchApiSnapshotSha256",
            "commitApiSnapshotSha256",
        }
        or current_main.get("protected") is not True
        or current_main.get("commit") != source_commit
        or current_main.get("tree") != source_tree
    ):
        raise ApprovalError("public approval current Android main authority differs")
    _sha256(
        current_main.get("branchApiSnapshotSha256"),
        "public approval Android branch snapshot",
    )
    _sha256(
        current_main.get("commitApiSnapshotSha256"),
        "public approval Android commit snapshot",
    )
    two_green = value.get("twoGreen")
    if not isinstance(two_green, dict) or set(two_green) != {
        "workflowRun", "artifact", "receipt", "receiptSha256",
        "runSnapshotSha256", "artifactMetadataSnapshotSha256",
    }:
        raise ApprovalError("public approval Two-Green fields differ")
    run = two_green.get("workflowRun")
    artifact = two_green.get("artifact")
    receipt = two_green.get("receipt")
    if (
        not isinstance(run, dict)
        or run.get("workflowName") != TWO_GREEN_WORKFLOW_NAME
        or run.get("workflowPath") != TWO_GREEN_WORKFLOW_PATH
        or run.get("event") != "workflow_dispatch"
        or run.get("ref") != ANDROID_REF
        or run.get("headSha") != source_commit
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
        or not isinstance(artifact, dict)
        or not isinstance(receipt, dict)
        or receipt.get("contract") != TWO_GREEN_CONTRACT
        or receipt.get("status") != "pass"
        or receipt.get("eligible") is not True
        or receipt.get("internalTestingEligible") is not True
        or receipt.get("reviewPullRequestNumber") is None
        or not SHA256.fullmatch(str(two_green.get("receiptSha256") or ""))
        or not SHA256.fullmatch(str(two_green.get("runSnapshotSha256") or ""))
        or not SHA256.fullmatch(str(two_green.get("artifactMetadataSnapshotSha256") or ""))
    ):
        raise ApprovalError("public approval Two-Green authority differs")
    _positive(run.get("id"), "public approval Two-Green run ID")
    _positive(run.get("attempt"), "public approval Two-Green run attempt")
    _positive(artifact.get("id"), "public approval Two-Green artifact ID")
    _sha256(artifact.get("archiveSha256"), "public approval Two-Green archive")
    _sha256(receipt.get("eligibilitySha256"), "public approval eligibility")
    _positive(receipt.get("reviewRunId"), "public approval review run ID")
    _positive(receipt.get("mainRunId"), "public approval main run ID")
    _positive(
        receipt.get("reviewPullRequestNumber"),
        "public approval review pull request number",
    )
    expected_artifact_name = (
        "chummer-android-api36-two-green-eligibility-"
        f"{receipt['reviewRunId']}-{receipt['mainRunId']}"
    )
    if artifact.get("name") != expected_artifact_name:
        raise ApprovalError("public approval Two-Green artifact name differs")
    execution = value.get("fleetExecution")
    if (
        not isinstance(execution, dict)
        or set(execution) != {
            "repository", "ref", "protectedRef", "event", "commit",
            "workflowRepository", "workflowRef", "workflowSha", "runId",
            "runAttempt", "environment", "currentMainAuthority",
        }
        or execution.get("repository") != FLEET_REPOSITORY
        or execution.get("ref") != FLEET_REF
        or execution.get("protectedRef") is not True
        or execution.get("event") != "workflow_dispatch"
        or execution.get("workflowRepository") != FLEET_REPOSITORY
        or execution.get("workflowRef")
        != f"{FLEET_REPOSITORY}/{WORKFLOW_PATH}@refs/heads/main"
        or execution.get("workflowSha") != execution.get("commit")
        or execution.get("environment") != ENVIRONMENT_NAME
    ):
        raise ApprovalError("public approval Fleet execution authority differs")
    _sha40(execution.get("commit"), "public approval Fleet commit")
    fleet_current_main = execution.get("currentMainAuthority")
    if (
        not isinstance(fleet_current_main, dict)
        or set(fleet_current_main) != {
            "protected", "commit", "tree", "branchApiSnapshotSha256",
            "commitApiSnapshotSha256",
        }
        or fleet_current_main.get("protected") is not True
        or fleet_current_main.get("commit") != execution.get("commit")
    ):
        raise ApprovalError("public approval current Fleet main authority differs")
    _sha40(fleet_current_main.get("tree"), "public approval Fleet main tree")
    _sha256(
        fleet_current_main.get("branchApiSnapshotSha256"),
        "public approval Fleet branch snapshot",
    )
    _sha256(
        fleet_current_main.get("commitApiSnapshotSha256"),
        "public approval Fleet commit snapshot",
    )
    _positive(execution.get("runId"), "public approval Fleet run ID")
    _positive(execution.get("runAttempt"), "public approval Fleet run attempt")
    environment_authority = value.get("environmentAuthority")
    if (
        not isinstance(environment_authority, dict)
        or environment_authority.get("name") != ENVIRONMENT_NAME
        or environment_authority.get("preventSelfReview") is not True
        or environment_authority.get("administratorsCanBypass") is not False
        or environment_authority.get("protectedBranchesOnly") is not True
        or environment_authority.get("configuredHumanReviewerSetPinned") is not True
        or environment_authority.get("actualApprovalActorRecorded") is not False
        or type(environment_authority.get("requiredReviewerCount")) is not int
        or environment_authority["requiredReviewerCount"] < 1
        or type(environment_authority.get("humanUserReviewerCount")) is not int
        or environment_authority["humanUserReviewerCount"] < 1
    ):
        raise ApprovalError("public approval environment authority differs")
    _sha256(
        environment_authority.get("reviewerIdentitySetSha256"),
        "public approval reviewer identity set",
    )
    _sha256(
        environment_authority.get("apiSnapshotSha256"),
        "public approval environment snapshot",
    )
    freshness = value.get("freshnessAuthority")
    if freshness != {
        "maximumEvidenceAgeSeconds": effective_policy["freshness"]["maximum_evidence_age_seconds"],
        "maximumFutureSkewSeconds": effective_policy["freshness"]["maximum_future_skew_seconds"],
        "checkedAtUtc": value.get("approvedAtUtc"),
    }:
        raise ApprovalError("public approval freshness authority differs")
    replay = value.get("replayProtection")
    if (
        not isinstance(replay, dict)
        or set(replay) != {
            "mode", "artifactName", "priorApprovalArtifactCount",
            "ledgerApiSnapshotSha256", "approvalRequestNonce",
        }
        or replay.get("mode") != "artifact_observation_only_incomplete"
        or replay.get("artifactName")
        != approval_artifact_name({"twoGreenArtifactId": artifact["id"]})
        or replay.get("priorApprovalArtifactCount") != 0
        or replay.get("approvalRequestNonce") != value.get("approvalRequestNonce")
    ):
        raise ApprovalError("public approval replay protection differs")
    _sha256(
        replay.get("ledgerApiSnapshotSha256"),
        "public approval artifact ledger snapshot",
    )
    policy_authority = value.get("policyAuthority")
    if (
        not isinstance(policy_authority, dict)
        or policy_authority.get("contract") != POLICY_CONTRACT
        or policy_authority.get("activationWasReady") is not True
    ):
        raise ApprovalError("public approval policy authority differs")
    _sha256(policy_authority.get("sha256"), "public approval policy digest")
    _positive(policy_authority.get("sizeBytes"), "public approval policy size")
    statement = {key: member for key, member in value.items() if key not in {"approvalSha256", "signature"}}
    if value.get("approvalSha256") != canonical_sha256(statement):
        raise ApprovalError("public approval digest is invalid")
    signature = value.get("signature")
    if not isinstance(signature, dict) or set(signature) != {
        "algorithm", "encoding", "publicKeySpkiDerBase64", "publicKeySpkiSha256", "signatureBase64"
    } or signature.get("algorithm") != "Ed25519" or signature.get("encoding") != "base64":
        raise ApprovalError("public approval signature fields are invalid")
    try:
        public_der = base64.b64decode(signature["publicKeySpkiDerBase64"], validate=True)
        signature_bytes = base64.b64decode(signature["signatureBase64"], validate=True)
    except (binascii.Error, ValueError, TypeError) as error:
        raise ApprovalError("public approval signature is not strict Base64") from error
    if hashlib.sha256(public_der).hexdigest() != signature.get("publicKeySpkiSha256"):
        raise ApprovalError("public approval key digest differs")
    if policy is not None:
        _require_ready(policy)
        if (
            signature.get("publicKeySpkiSha256")
            != policy["external_ed25519_key"]["expected_public_key_spki_sha256"]
        ):
            raise ApprovalError("public approval key differs from reviewed policy")
    if len(public_der) != len(SPKI_ED25519_PREFIX) + 32 or not public_der.startswith(SPKI_ED25519_PREFIX) or len(signature_bytes) != 64:
        raise ApprovalError("public approval is not an Ed25519 signature")
    verify_ed25519(public_der, canonical_bytes(statement), signature_bytes)


def write_output(path: Path, value: Mapping[str, Any]) -> None:
    if path.name != OUTPUT_NAME or not path.is_absolute() or path.is_symlink():
        raise ApprovalError(f"output must be an absolute non-symlink {OUTPUT_NAME}")
    parent = path.parent
    if parent.is_symlink() or parent.resolve(strict=True) != parent:
        raise ApprovalError("output parent must be canonical and non-symlinked")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=parent, prefix=f".{OUTPUT_NAME}.", delete=False) as stream:
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
    verify = subparsers.add_parser("verify")
    verify.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "verify":
        policy, _, policy_sha256 = load_policy(args.policy)
        data, _ = stable_file(args.approval, "public approval", MAX_RECEIPT_BYTES)
        value = strict_json_bytes(data, "public approval")
        validate_approval(value, policy)
        if value["policyAuthority"]["sha256"] != policy_sha256:
            raise ApprovalError("public approval does not bind the reviewed policy bytes")
        print("preview12_release_approval=verified signing_authorized=false publication_authorized=false google_play_upload_authorized=false")
        return 0
    policy, _, _ = load_policy(args.policy)
    if args.command == "preflight":
        result = validate_dispatch(policy, args)
        print(json.dumps(result, sort_keys=True))
        return 0
    result = create_approval(args, os.environ)
    validate_approval(result)
    write_output(args.output, result)
    print("preview12_release_approval=approved signing_authorized=false publication_authorized=false google_play_upload_authorized=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
