#!/usr/bin/env python3
"""Dormant external Preview12 rebuilder and Android-v2 attestation adapter.

The privileged command is intentionally unusable with the checked-in lock.  A
future protected Fleet environment must supply every authority and secret path.
This module never authorizes Play upload or publication.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from collections import deque
from contextlib import contextmanager
import configparser
from datetime import UTC, datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import types
from typing import Any, Callable, Mapping


LOCK_CONTRACT = "fleet.android_preview12_external_rebuilder_lock.v1"
REQUEST_CONTRACT = "chummer.android.external-release-signer-request/v1"
ANDROID_ATTESTATION_CONTRACT = "chummer.android.release-build-attestation/v2"
FLEET_AUDIT_CONTRACT = "fleet.android_preview12_external_rebuild_audit.v3"
SOURCE_GRAPH_CONTRACT = "chummer.android.release-source-graph/v3"
LEDGER_POLICY_CONTRACT = "fleet.android_preview12_approval_ledger_policy.v1"
SIGNING_LEDGER_POLICY_CONTRACT = "fleet.android_preview12_binary_signing_ledger_policy.v1"
SIGNING_LEDGER_POLICY_PATH = "config/release/android-preview12-binary-signing-ledger.json"
APPROVAL_LEDGER_POLICY_PATH = "config/release/android-preview12-two-green-release-approval.json"
SIGNING_LEDGER_CREDENTIAL_INPUT = "ANDROID_PREVIEW12_BINARY_SIGNING_LEDGER_BEARER_TOKEN"
EXTERNAL_SIGNER_ATTESTATION_CONTRACT = "chummer.android.external-release-signer-attestation/v1"
BUILDER_KEY_IDS = ("local-release-builder-2026", "fleet-release-builder-2026-09")
# Only this already-qualified consumer predates Android's explicit builder
# selector. A missing selector on any successor is not permission to use the
# approval verifier's default key. This is compatibility, not new authority.
LEGACY_BUILDER_BINDING = (
    "8ea0da6092ede167c65b7e059df40fe88ac6f026",
    "dba9e14fe892a9794df60eeff254d1f907c926b8",
    "scripts/sign_android_release_build_attestation.py",
    "b31bec9cfd198214250a645c346f4bb46f7c4d4f5b0856ca618862f24cfabe93",
    "local-release-builder-2026",
    "eng/trusted-release-approvers/local-release-builder-2026.public.pem",
    "ed1fbe95fc7713bfc6d9d0fea21726c1ba3193533fc2d5523e054ad8fb86184c",
    "c46a4e9a224c8c77a4038bca83f7d9ed66146318d8b5c2c9fc81cd19fdd18ea7",
)
REBUILD_HANDOFF_CONTRACT = "fleet.android_preview12_external_rebuild_handoff.v1"
RECOVERY_CONTRACT = "fleet.android_preview12_external_signer_recovery.v1"
PACKAGE_ID = "com.myexternalbrain.chummer"
VERSION_NAME = "0.1.0-preview.12"
VERSION_CODE = 12
MINIMUM_SDK = 24
TARGET_SDK = 36
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OCI_DIGEST_IMAGE = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*(?::[1-9][0-9]{0,4})?/)?"
    r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
    r"(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*@sha256:[0-9a-f]{64}"
)
UPLOAD_CERTIFICATE_SHA256 = "d9c4b635121544d5522abf1ec2dfda3c1938aab93d6726bb93c9871ec9ed1d15"
REPOSITORIES = {
    "chummer-android": ("app", "chummer-android", "https://github.com/ArchonMegalon/chummer-android.git"),
    "chummer6-ui": ("runtime", "chummer-presentation", "https://github.com/ArchonMegalon/chummer6-ui.git"),
    "chummer6-core": ("runtime", "chummer-core-engine", "https://github.com/ArchonMegalon/chummer6-core.git"),
    "chummer6-ui-kit": ("runtime", "chummer-ui-kit", "https://github.com/ArchonMegalon/chummer6-ui-kit.git"),
    "chummer6-hub": ("contracts_and_validation", "chummer.run-services", "https://github.com/ArchonMegalon/chummer6-hub.git"),
    "chummer6-hub-registry": ("contracts", "chummer-hub-registry", "https://github.com/ArchonMegalon/chummer6-hub-registry.git"),
    "chummer6-media-factory": ("contracts", "fleet/repos/chummer-media-factory", "https://github.com/ArchonMegalon/chummer6-media-factory.git"),
    "chummer6-design": ("validation", "chummer-design", "https://github.com/ArchonMegalon/chummer6-design.git"),
}
REVISION_VARIABLES = {
    "chummer-android": "CHUMMER_ANDROID_REVISION",
    "chummer6-ui": "CHUMMER_PRESENTATION_REVISION",
    "chummer6-core": "CHUMMER_CORE_ENGINE_REVISION",
    "chummer6-ui-kit": "CHUMMER_UI_KIT_REVISION",
    "chummer6-hub": "CHUMMER_RUN_SERVICES_REVISION",
    "chummer6-hub-registry": "CHUMMER_HUB_REGISTRY_REVISION",
    "chummer6-media-factory": "CHUMMER_MEDIA_FACTORY_REVISION",
    "chummer6-design": "CHUMMER_DESIGN_REVISION",
}
# Transport limits only. Pack/object expansion and checkout disk usage still
# require an external filesystem quota; these do not bound expanded source.
OFFLINE_MANIFEST_BYTES = 64 * 1024
# Selected Hub history occupies about 4.47 GB of local compressed Git objects.
# Export representation may differ: retain finite streamed limits and reject
# overflow rather than treating that planning measurement as a guaranteed bound.
OFFLINE_BUNDLE_BYTES = 5 * 1024 * 1024 * 1024
OFFLINE_TOTAL_BUNDLE_BYTES = 6 * 1024 * 1024 * 1024
# Test-oracle custody has a separate scope. Do not widen it when admitting a
# larger product-repository bundle (including its historical Git objects).
OFFLINE_ORACLE_FILE_BYTES = 512 * 1024 * 1024
# Retained full-oracle candidate (checkout plus Git storage) measured
# 2,589,350,023 bytes; see docs/android-release-test-inputs.md for evidence and
# separate transport/staging quota requirements. This is a logical-byte limit,
# not a filesystem-capacity admission or a relaxation of object integrity.
OFFLINE_ORACLE_TOTAL_BYTES = 3 * 1024 * 1024 * 1024
OFFLINE_GIT_OUTPUT_BYTES = 8 * 1024 * 1024
OFFLINE_GIT_TIMEOUT_SECONDS = 900


class RebuilderError(RuntimeError):
    """One deliberately sanitized fail-closed external-rebuilder failure."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _pretty_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RebuilderError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                RebuilderError(f"non-finite JSON value in {label}: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RebuilderError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise RebuilderError(f"{label} must contain one JSON object")
    return value


def _stable_bytes(path: Path, label: str, limit: int, *, owner_only: bool = False) -> bytes:
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or limit < 1:
        raise RebuilderError(f"{label} must be one absolute regular file")
    resolved = path.resolve(strict=True)
    before = resolved.stat()
    if resolved != path or before.st_uid != os.getuid() or (owner_only and stat.S_IMODE(before.st_mode) & 0o077):
        raise RebuilderError(f"{label} is not canonical and owner-bound")
    with resolved.open("rb") as stream:
        raw = stream.read(limit + 1)
    after = resolved.stat()
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    if len(raw) > limit or identity(before) != identity(after):
        raise RebuilderError(f"{label} is oversized or changed while being read")
    return raw


def _sha256_file(path: Path, label: str, limit: int, *, owner_only: bool = False) -> str:
    return hashlib.sha256(_stable_bytes(path, label, limit, owner_only=owner_only)).hexdigest()


def _json_file(path: Path, label: str, limit: int, *, owner_only: bool = False) -> tuple[dict[str, Any], bytes]:
    raw = _stable_bytes(path, label, limit, owner_only=owner_only)
    return _strict_json(raw, label), raw


def _sha40(value: object, label: str) -> str:
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise RebuilderError(f"{label} must be lowercase 40-character hex")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise RebuilderError(f"{label} must be lowercase 64-character hex")
    return value


def _safe_name(value: object, suffix: str, label: str) -> str:
    if not isinstance(value, str) or not value.endswith(suffix) or PurePosixPath(value).name != value \
            or "\\" in value or value in ("", ".", ".."):
        raise RebuilderError(f"{label} is not one safe file name")
    return value


def _write_exclusive(path: Path, raw: bytes) -> None:
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir() \
            or path.parent.is_symlink() or path.parent.resolve(strict=True) != path.parent \
            or path.parent.stat().st_uid != os.getuid() or stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise RebuilderError("output must be new below one owner-only directory")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def load_lock(path: Path) -> tuple[dict[str, Any], bytes]:
    value, raw = _json_file(path, "external rebuilder lock", 1024 * 1024)
    if value.get("contract_name") != LOCK_CONTRACT:
        raise RebuilderError("external rebuilder lock contract is not exact")
    return value, raw


def validate_lock(lock: Mapping[str, Any], lock_bytes: bytes, builder_image: str | None = None) -> list[str]:
    """Validate full protected signing readiness; preserve every existing gate."""
    return _validate_lock_configuration(lock, lock_bytes, builder_image, protected_signer=True)


def validate_unsigned_rebuild_lock(
    lock: Mapping[str, Any], lock_bytes: bytes, builder_image: str | None = None,
) -> list[str]:
    """Admit enabled unsigned work using the existing lock's public bindings.

    Ready state, enabled rebuilding, isolation and all public build authority
    remain required. Downstream signer/credential/ledger activation is separate.
    This neither activates a dormant lock nor grants signing or publication.
    """
    return _validate_lock_configuration(lock, lock_bytes, builder_image, protected_signer=False)


def _validate_lock_configuration(
    lock: Mapping[str, Any], lock_bytes: bytes, builder_image: str | None, *, protected_signer: bool,
) -> list[str]:
    failures: list[str] = []
    expected_top = {
        "contract_name", "contract_version", "state", "release", "android_authority",
        "toolchain", "approval_authority", "upload_key", "rebuild", "reservation", "outputs", "limits",
    }
    if set(lock) != expected_top or lock.get("contract_name") != LOCK_CONTRACT \
            or type(lock.get("contract_version")) is not int or lock["contract_version"] != 1:
        return ["external rebuilder lock fields or version are not exact"]
    release = lock.get("release", {})
    if release != {
        "package_id": PACKAGE_ID, "version_name": VERSION_NAME, "version_code": VERSION_CODE,
        "minimum_sdk": MINIMUM_SDK, "target_sdk": TARGET_SDK,
    }:
        failures.append("Preview12 release identity is not exact")
    android = lock.get("android_authority", {})
    if android.get("repository") != REPOSITORIES["chummer-android"][2] \
            or not HEX40.fullmatch(str(android.get("commit") or "")) \
            or not HEX40.fullmatch(str(android.get("tree") or "")):
        failures.append("qualified Android authority is incomplete")
    for label in ("build_script", "attestation_consumer", "two_green_verifier", "source_graph_verifier"):
        binding = android.get(label, {})
        if not isinstance(binding, dict) or not isinstance(binding.get("path"), str) \
                or PurePosixPath(binding["path"]).is_absolute() or ".." in PurePosixPath(binding["path"]).parts \
                or not HEX64.fullmatch(str(binding.get("sha256") or "")):
            failures.append(f"Android {label} authority is incomplete")
    if android.get("attestation_consumer", {}).get("contract_name") != ANDROID_ATTESTATION_CONTRACT:
        failures.append("Android attestation consumer contract drifted")
    toolchain = lock.get("toolchain", {})
    expected_tools = {
        "dotnet": ("10.0.111", 9258, 4276188988),
        "java": ("17.0.20.1", 246, 332109578),
    }
    for name, (version, count, size) in expected_tools.items():
        row = toolchain.get(name, {})
        if type(row.get("version")) is not str or row.get("version") != version \
                or type(row.get("file_count")) is not int or row.get("file_count") != count \
                or type(row.get("size_bytes")) is not int or row.get("size_bytes") != size \
                or type(row.get("tree_sha256")) is not str \
                or not HEX64.fullmatch(row.get("tree_sha256") or ""):
            failures.append(f"{name} closure is not exact")
    sdk = toolchain.get("android_sdk", {})
    if type(sdk.get("api_level")) is not int or sdk.get("api_level") != 36 \
            or type(sdk.get("build_tools_version")) is not str or sdk.get("build_tools_version") != "36.0.0" \
            or type(sdk.get("file_count")) is not int or sdk.get("file_count") != 11523 \
            or type(sdk.get("size_bytes")) is not int or sdk.get("size_bytes") != 314037662 \
            or type(sdk.get("tree_sha256")) is not str \
            or not HEX64.fullmatch(sdk.get("tree_sha256") or ""):
        failures.append("Android API/build-tools 36 closure is not exact")
    if toolchain.get("platform") != "linux/amd64" \
            or toolchain.get("bundletool_sha256") != "a099cfa1543f55593bc2ed16a70a7c67fe54b1747bb7301f37fdfd6d91028e29":
        failures.append("external rebuilder platform or bundletool drifted")
    approval = lock.get("approval_authority", {})
    if approval.get("role") != "android_internal_release_builder" \
            or approval.get("scope") != "android_internal_release_artifact_binding" \
            or approval.get("rotation_requires_android_merge_and_requalification") is not True \
            or not HEX64.fullmatch(str(approval.get("public_key_sha256") or "")) \
            or not HEX64.fullmatch(str(approval.get("public_key_spki_sha256") or "")):
        failures.append("Android v2 attestation authority is incomplete")
    upload = lock.get("upload_key", {})
    if upload.get("expected_certificate_sha256") != UPLOAD_CERTIFICATE_SHA256 \
            or upload.get("signature_algorithm") != "SHA256withRSA" \
            or upload.get("digest_algorithm") != "SHA-256":
        failures.append("legacy Play upload certificate identity drifted")
    outputs = lock.get("outputs", {})
    if outputs.get("android_attestation_contract") != ANDROID_ATTESTATION_CONTRACT \
            or outputs.get("fleet_audit_contract") != FLEET_AUDIT_CONTRACT \
            or outputs.get("signed_content_handoff_required") is not True \
            or outputs.get("publication_authorized") is not False \
            or outputs.get("google_play_upload_authorized") is not False:
        failures.append("external rebuilder output authority escalates or drifted")
    if protected_signer and outputs.get("signed_content_handoff_enabled") is not True:
        failures.append("private immutable signed-content handoff is not configured")
    if lock.get("state") != "ready":
        failures.append("external rebuilder lock is dormant")
    rebuild = lock.get("rebuild", {})
    if rebuild.get("enabled") is not True or rebuild.get("ambient_siblings_allowed") is not False \
            or rebuild.get("builder_credential_mounts_allowed") is not False \
            or rebuild.get("builder_runs_in_separate_job") is not True \
            or rebuild.get("deterministic_unsigned_digest_match_required") is not True \
            or rebuild.get("full_test_suite_required") is not True:
        failures.append("independent rebuild is disabled or weakened")
    if protected_signer:
        reservation = lock.get("reservation", {})
        expected_reservation_fields = {
            "adapter_contract", "adapter_path", "adapter_sha256", "configured", "policy_path",
            "policy_sha256", "protocol_source", "signed_receipts_required",
        }
        if set(reservation) != expected_reservation_fields \
                or reservation.get("adapter_contract") != LEDGER_POLICY_CONTRACT \
                or reservation.get("configured") is not True \
                or reservation.get("protocol_source") != "merged_reviewed_fleet_authority" \
                or reservation.get("signed_receipts_required") is not True \
                or not HEX64.fullmatch(str(reservation.get("adapter_sha256") or "")) \
                or not HEX64.fullmatch(str(reservation.get("policy_sha256") or "")):
            failures.append("reviewed durable approval-ledger adapter is not configured")
        for name in ("adapter_path", "policy_path"):
            value = reservation.get(name)
            if not isinstance(value, str) or PurePosixPath(value).is_absolute() \
                    or ".." in PurePosixPath(value).parts or "\\" in value:
                failures.append(f"reservation.{name} is not one safe Fleet-relative path")
        if reservation.get("policy_path") != SIGNING_LEDGER_POLICY_PATH:
            failures.append("binary signing must select its separate ledger policy")
    for name in (("builder_image", "signer_image") if protected_signer else ("builder_image",)):
        image = toolchain.get(name)
        if not isinstance(image, str) or OCI_DIGEST_IMAGE.fullmatch(image) is None:
            failures.append(f"toolchain.{name} is not one digest-pinned OCI repository")
        elif ":" in image.split("/", 1)[0] and "/" in image \
                and int(image.split("/", 1)[0].rsplit(":", 1)[1]) > 65535:
            failures.append(f"toolchain.{name} registry port is invalid")
    receipt_digest = toolchain.get("installed_closure_receipt_sha256")
    if not isinstance(receipt_digest, str) or HEX64.fullmatch(receipt_digest) is None:
        failures.append("toolchain.installed_closure_receipt_sha256 is not a lowercase SHA-256")
    if toolchain.get("builder_image") and builder_image is not None \
            and builder_image != toolchain.get("builder_image"):
        failures.append("reported builder image differs from lock")
    if protected_signer:
        for name in ("key_alias", "keystore_secret", "store_password_secret", "key_password_secret"):
            if not upload.get(name):
                failures.append(f"upload_key.{name} is not configured")
        if not approval.get("private_key_secret"):
            failures.append("approval attestation private-key secret is not configured")
    limits = lock.get("limits", {})
    bound_names = ("json_bytes", "aab_bytes", "git_timeout_seconds", "build_timeout_seconds")
    if protected_signer:
        bound_names += ("reservation_timeout_seconds",)
    for name in bound_names:
        if type(limits.get(name)) is not int or limits[name] < 1:
            failures.append(f"limits.{name} is invalid")
    if not lock_bytes or len(lock_bytes) > 1024 * 1024:
        failures.append("external rebuilder lock bytes are invalid")
    return failures


def validate_source_graph(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if value.get("contractName") != SOURCE_GRAPH_CONTRACT:
        raise RebuilderError("source graph contract is not exact")
    identity = value.get("releaseIdentity")
    if identity != {
        "packageId": PACKAGE_ID,
        "versionName": VERSION_NAME,
        "versionCode": VERSION_CODE,
        "intentAuthority": "explicit_build_input",
        "minimumExclusiveVersionCode": 11,
    }:
        raise RebuilderError("source graph release identity is not Preview12")
    rows = value.get("repositories")
    if not isinstance(rows, list) or len(rows) != len(REPOSITORIES):
        raise RebuilderError("source graph repository inventory is incomplete")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "role", "commit", "tree", "tree_sha256", "repository"}:
            raise RebuilderError("source graph repository row fields are not exact")
        name = row.get("name")
        if name not in REPOSITORIES or name in result:
            raise RebuilderError("source graph repository name is missing, extra, or duplicated")
        role, _relative, repository = REPOSITORIES[name]
        if row.get("role") != role or row.get("repository") != repository:
            raise RebuilderError(f"source graph authority drifted for {name}")
        _sha40(row.get("commit"), f"{name} commit")
        _sha40(row.get("tree"), f"{name} tree")
        _sha256(row.get("tree_sha256"), f"{name} tree listing")
        result[name] = dict(row)
    if set(result) != set(REPOSITORIES):
        raise RebuilderError("source graph repository inventory is not closed")
    return result


def validate_external_request(request_path: Path, source_graph_path: Path, json_limit: int = 8 * 1024 * 1024) \
        -> tuple[dict[str, Any], dict[str, Any]]:
    request, _ = _json_file(request_path, "external signer request", json_limit, owner_only=True)
    graph, graph_raw = _json_file(source_graph_path, "producer source graph", json_limit, owner_only=True)
    expected_fields = {
        "contractName", "requestAuthority", "releaseIdentity", "unsignedAab", "sourceGraph",
        "buildSidecar", "expectedUploadCertificateSha256", "requiredExternalSigner",
        "expectedExternalSignerOutput", "signingAuthorized", "publicationAuthorized", "googlePlayUploadAuthorized",
    }
    if set(request) != expected_fields or request.get("contractName") != REQUEST_CONTRACT \
            or request.get("requestAuthority") != "none" \
            or any(request.get(name) is not False for name in (
                "signingAuthorized", "publicationAuthorized", "googlePlayUploadAuthorized"
            )):
        raise RebuilderError("external signer request fields or posture are not exact")
    identity = request.get("releaseIdentity")
    if identity != {"packageId": PACKAGE_ID, "versionName": VERSION_NAME, "versionCode": VERSION_CODE,
                    "intentAuthority": "explicit_build_input", "minimumExclusiveVersionCode": 11}:
        raise RebuilderError("external signer request release identity is not exact Preview12")
    unsigned = request.get("unsignedAab")
    graph_claim = request.get("sourceGraph")
    sidecar = request.get("buildSidecar")
    if not isinstance(unsigned, dict) or set(unsigned) != {"fileName", "sha256", "sizeBytes"} \
            or not isinstance(graph_claim, dict) or set(graph_claim) != {"fileName", "sha256", "sizeBytes"} \
            or not isinstance(sidecar, dict) or set(sidecar) != {"fileName", "sha256"}:
        raise RebuilderError("external signer request artifact bindings are incomplete")
    _safe_name(unsigned.get("fileName"), ".aab", "unsigned AAB")
    _safe_name(graph_claim.get("fileName"), "-source-graph.json", "source graph")
    _safe_name(sidecar.get("fileName"), ".sha256", "build sidecar")
    if unsigned.get("fileName") != f"chummer-android-{VERSION_NAME}-unsigned.aab" \
            or graph_claim.get("fileName") != f"chummer-android-{VERSION_NAME}-source-graph.json" \
            or sidecar.get("fileName") != f"chummer-android-{VERSION_NAME}-unsigned.aab.sha256":
        raise RebuilderError("external signer request artifact names are not exact Preview12 outputs")
    for row, label in ((unsigned, "unsigned AAB"), (graph_claim, "source graph"), (sidecar, "build sidecar")):
        _sha256(row.get("sha256"), f"{label} digest")
    if type(unsigned.get("sizeBytes")) is not int or unsigned["sizeBytes"] < 1 \
            or type(graph_claim.get("sizeBytes")) is not int or graph_claim["sizeBytes"] != len(graph_raw) \
            or graph_claim["sha256"] != hashlib.sha256(graph_raw).hexdigest():
        raise RebuilderError("external signer request artifact size or source-graph digest differs")
    required = request.get("requiredExternalSigner")
    required_true = {
        "mustRehashInputs", "mustRebuildAndMatchUnsignedAab", "mustReplayTwoGreenAndSourceGraph",
        "mustBindFullJdkDotnetAndroidSdkClosure", "mustValidatePackageVersionAbiAndProofExclusion",
        "mustVerifyOutputCertificate", "mustEmitDetachedAttestation", "outputMustBindUnsignedAabSha256",
        "outputMustBindSignedAabSha256", "outputMustBindSourceGraphSha256", "outputMustBindReleaseIdentity",
    }
    required_fields = required_true | {"implementedByThisRepository", "inputTransport"}
    if not isinstance(required, dict) or set(required) != required_fields \
            or required.get("implementedByThisRepository") is not False \
            or required.get("inputTransport") != "authenticated_descriptor_or_immutable_artifact" \
            or any(required.get(name) is not True for name in required_true):
        raise RebuilderError("external signer request weakens required independent checks")
    expected = request.get("expectedExternalSignerOutput")
    expected_fields = {
        "contractName", "mustBindUnsignedAabSha256", "mustBindSourceGraphSha256",
        "mustBindExpectedUploadCertificateSha256", "mustBindReleaseIdentity",
        "mustReportSignedAabSha256", "mustReportFullToolchainClosureSha256",
        "mustContainDetachedAuthoritySignature", "publicationAuthorized", "googlePlayUploadAuthorized",
    }
    if not isinstance(expected, dict) or set(expected) != expected_fields \
            or expected.get("contractName") != EXTERNAL_SIGNER_ATTESTATION_CONTRACT \
            or expected.get("mustBindUnsignedAabSha256") != unsigned["sha256"] \
            or expected.get("mustBindSourceGraphSha256") != graph_claim["sha256"] \
            or expected.get("mustBindExpectedUploadCertificateSha256") != request.get("expectedUploadCertificateSha256") \
            or expected.get("mustBindReleaseIdentity") != identity \
            or expected.get("mustContainDetachedAuthoritySignature") is not True \
            or expected.get("mustReportSignedAabSha256") is not True \
            or expected.get("mustReportFullToolchainClosureSha256") is not True \
            or expected.get("publicationAuthorized") is not False \
            or expected.get("googlePlayUploadAuthorized") is not False:
        raise RebuilderError("expected external signer output is not exact")
    if request.get("expectedUploadCertificateSha256").replace(":", "").lower() != UPLOAD_CERTIFICATE_SHA256:
        raise RebuilderError("external signer request does not require the legacy Play upload certificate")
    validate_source_graph(graph)
    return request, graph


def _git(runner: Callable[..., subprocess.CompletedProcess], arguments: list[str], *, timeout: int,
         cwd: Path | None = None, binary: bool = False) -> bytes | str:
    environment = {
        "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/tmp",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
    }
    completed = runner(
        ["/usr/bin/git", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
         "-c", "core.attributesFile=/dev/null", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
         *arguments],
        cwd=cwd, env=environment, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, text=not binary,
    )
    if completed.returncode != 0:
        raise RebuilderError("trusted git operation failed")
    return completed.stdout if binary else completed.stdout.strip()


def checkout_source_graph(graph: Mapping[str, Any], workspace: Path, *,
                          runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                          timeout: int = 900) -> dict[str, Path]:
    rows = validate_source_graph(graph)
    if not workspace.is_absolute() or workspace.exists() or workspace.is_symlink():
        raise RebuilderError("independent source workspace must be a new absolute path")
    workspace.mkdir(parents=True, mode=0o700)
    workspace.chmod(0o700)
    roots: dict[str, Path] = {}
    try:
        for name, (_role, relative, repository) in REPOSITORIES.items():
            root = workspace.joinpath(*PurePosixPath(relative).parts)
            root.parent.mkdir(parents=True, exist_ok=True)
            row = rows[name]
            _git(runner, ["init", "--quiet", os.fspath(root)], timeout=timeout)
            _git(runner, ["-C", os.fspath(root), "remote", "add", "origin", repository], timeout=timeout)
            _git(runner, ["-C", os.fspath(root), "fetch", "--no-tags", "origin", row["commit"]], timeout=timeout)
            _git(runner, ["-C", os.fspath(root), "checkout", "--quiet", "--detach", "FETCH_HEAD"], timeout=timeout)
            roots[name] = root
        verify_source_checkout_graph(graph, workspace, runner=runner, timeout=timeout)
        return roots
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def verify_source_checkout_graph(graph: Mapping[str, Any], workspace: Path, *,
                                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                                 timeout: int = 900) -> dict[str, Path]:
    return _verify_source_checkout_graph(
        graph, workspace, lambda args, **kwargs: _git(runner, args, **kwargs), timeout=timeout,
    )


def _verify_source_checkout_graph(graph: Mapping[str, Any], workspace: Path,
                                  git: Callable[..., bytes | str], *, timeout: int) -> dict[str, Path]:
    rows = validate_source_graph(graph)
    roots: dict[str, Path] = {}
    for name, (_role, relative, repository) in REPOSITORIES.items():
        root = workspace.joinpath(*PurePosixPath(relative).parts)
        if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root:
            raise RebuilderError(f"independent source checkout is missing or noncanonical: {name}")
        row = rows[name]
        status = git(["-C", os.fspath(root), "status", "--porcelain", "--untracked-files=all"], timeout=timeout)
        head = git(["-C", os.fspath(root), "rev-parse", "HEAD^{commit}"], timeout=timeout)
        tree = git(["-C", os.fspath(root), "rev-parse", "HEAD^{tree}"], timeout=timeout)
        remote = git(["-C", os.fspath(root), "remote", "get-url", "origin"], timeout=timeout)
        listing = git(["-C", os.fspath(root), "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
                       timeout=timeout, binary=True)
        assert isinstance(listing, bytes)
        if status or head != row["commit"] or tree != row["tree"] or remote != repository \
                or hashlib.sha256(listing).hexdigest() != row["tree_sha256"]:
            raise RebuilderError(f"independent source checkout differs from source graph: {name}")
        roots[name] = root
    return roots


def _offline_git(arguments: list[str], *, timeout: int, binary: bool = False) -> bytes | str:
    """Capture bounded Git metadata; source contents use the same stream pump."""
    output = bytearray()
    _offline_git_stream(arguments, timeout=timeout, output_limit=OFFLINE_GIT_OUTPUT_BYTES,
                        consume=output.extend)
    try:
        return bytes(output) if binary else output.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        raise RebuilderError("offline Git operation failed") from None


def _offline_git_stream(arguments: list[str], *, timeout: int, output_limit: int,
                        consume: Callable[[bytes], None]) -> int:
    """Local Git only, bounded streaming and content-free failures.

    Use Popen here so output is bounded while the process runs, not after a
    potentially unlimited subprocess.run(capture_output=True) allocation.
    """
    environment = {
        "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
        "GIT_ALLOW_PROTOCOL": "", "GIT_PROTOCOL_FROM_USER": "0",
    }
    command = ["/usr/bin/git", "-c", "protocol.allow=never", "-c", "core.hooksPath=/dev/null",
               "-c", "core.attributesFile=/dev/null", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
               "-c", "init.templateDir=", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
               *arguments]
    process, leader_reserved = None, False
    try:
        if type(timeout) is not int or timeout < 1 or type(output_limit) is not int or output_limit < 0:
            raise RebuilderError("offline Git timeout is invalid")
        deadline = time.monotonic() + min(timeout, OFFLINE_GIT_TIMEOUT_SECONDS)
        process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL, umask=0o077,
                                   start_new_session=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        leader_reserved = True
        assert process.stdout is not None
        consumed = 0
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RebuilderError("offline Git operation exceeded its time limit")
                for key, _ in selector.select(min(remaining, 1)):
                    chunk = os.read(key.fd, min(64 * 1024, output_limit + 1 - consumed))
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        consumed += len(chunk)
                        if consumed > output_limit:
                            raise RebuilderError("offline Git operation exceeded its output limit")
                        consume(chunk)
        # Observe exit without releasing the leader PID. Cleanup can then
        # signal only our still-owned process group, before wait() reaps it.
        while True:
            try:
                status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT | os.WNOHANG)
            except ChildProcessError:
                leader_reserved = False
                raise RebuilderError("offline Git process ownership changed") from None
            if status is not None:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RebuilderError("offline Git operation exceeded its time limit")
            time.sleep(min(remaining, 0.01))
        if status.si_code != os.CLD_EXITED or status.si_status != 0:
            raise RebuilderError("offline Git operation failed")
        return consumed
    except (OSError, ValueError, subprocess.SubprocessError):
        raise RebuilderError("offline Git operation failed") from None
    finally:
        if process is not None:
            try:
                # Git may have started index-pack. Reap our entire private
                # process group, never a caller's or an unrelated session.
                if leader_reserved:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=5)
                if process.stdout is not None:
                    process.stdout.close()
            except (OSError, subprocess.SubprocessError):
                raise RebuilderError("offline Git process cleanup failed") from None


def _offline_input_identity(path: Path, limit: int) -> os.stat_result:
    """Admit one canonical, unlinked regular input and its actual ancestors."""
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise RebuilderError("offline source input path is not canonical")
    for ancestor in path.parents:
        if not stat.S_ISDIR(ancestor.lstat().st_mode):
            raise RebuilderError("offline source input ancestry is not canonical")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 \
            or metadata.st_size < 1 or metadata.st_size > limit:
        raise RebuilderError("offline source input is not one bounded unlinked regular file")
    return metadata


def _copy_offline_input(path: Path, metadata: os.stat_result, output: Any, limit: int) -> str:
    """Copy through a stable descriptor, checking both descriptor and pathname."""
    expected = _file_identity(metadata)
    if _file_identity(_offline_input_identity(path, limit)) != expected:
        raise RebuilderError("offline source input changed before snapshot")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if _file_identity(os.fstat(descriptor)) != expected or os.fstat(descriptor).st_nlink != 1:
            raise RebuilderError("offline source input changed before snapshot")
        digest, consumed = hashlib.sha256(), 0
        while chunk := os.read(descriptor, min(1024 * 1024, metadata.st_size + 1 - consumed)):
            consumed += len(chunk)
            if consumed > metadata.st_size or consumed > limit:
                raise RebuilderError("offline source input grew during snapshot")
            output.write(chunk)
            digest.update(chunk)
        if consumed != metadata.st_size or _file_identity(os.fstat(descriptor)) != expected \
                or os.fstat(descriptor).st_nlink != 1 \
                or _file_identity(_offline_input_identity(path, limit)) != expected:
            raise RebuilderError("offline source input changed during snapshot")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _offline_manifest(path: Path, workspace: Path) -> dict[str, tuple[Path, os.stat_result, str]]:
    # This exact mapping is transport data, not a signed release contract or
    # authentication of the party supplying expected hashes.
    metadata = _offline_input_identity(path, OFFLINE_MANIFEST_BYTES)
    raw = io.BytesIO()
    _copy_offline_input(path, metadata, raw, OFFLINE_MANIFEST_BYTES)
    try:
        manifest = _strict_json(raw.getvalue(), "offline source manifest")
    except RebuilderError:
        # Duplicate keys and other JSON diagnostics may contain hostile text.
        raise RebuilderError("offline source manifest is not strict JSON") from None
    if set(manifest) != set(REPOSITORIES):
        raise RebuilderError("offline source manifest repository inventory is not exact")
    inputs, total = {}, 0
    for name, row in manifest.items():
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size_bytes"} \
                or not isinstance(row["path"], str) or len(row["path"]) > 4096 \
                or not isinstance(row["sha256"], str) or not HEX64.fullmatch(row["sha256"]) \
                or type(row["size_bytes"]) is not int or not 0 < row["size_bytes"] <= OFFLINE_BUNDLE_BYTES:
            raise RebuilderError("offline source manifest row is not exact")
        source = Path(row["path"])
        if str(source) != row["path"]:
            raise RebuilderError("offline source bundle path is not canonical")
        identity = _offline_input_identity(source, OFFLINE_BUNDLE_BYTES)
        if identity.st_size != row["size_bytes"]:
            raise RebuilderError("offline source bundle size differs from manifest")
        total += identity.st_size
        if total > OFFLINE_TOTAL_BUNDLE_BYTES:
            raise RebuilderError("offline source bundle inventory exceeds its byte limit")
        inputs[name] = (source, identity, row["sha256"])
    if any(input_path == workspace or input_path.is_relative_to(workspace)
           or workspace.is_relative_to(input_path) for input_path in (path, *(item[0] for item in inputs.values()))):
        raise RebuilderError("offline source inputs overlap the output workspace")
    return inputs


def _remove_owned_directory(path: Path, identity: os.stat_result) -> None:
    """Never delete a replacement placed at an exclusively created pathname."""
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        current = os.fstat(descriptor)
        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
            return
        # Anchor child removal to the owned directory descriptor, even if a
        # caller renames its pathname while cleanup is running.
        for name in os.listdir(descriptor):
            child = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(child.st_mode):
                shutil.rmtree(name, dir_fd=descriptor)
            else:
                os.unlink(name, dir_fd=descriptor)
        current = path.lstat()
        if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
            os.rmdir(path)
    except FileNotFoundError:
        pass
    except (OSError, RuntimeError, ValueError):
        raise RebuilderError("offline source cleanup failed") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                raise RebuilderError("offline source cleanup failed") from None


def _offline_bundle_header(path: Path) -> None:
    """Reject prerequisite/filtered transports even if a small pack is complete.

    Git still verifies the actual header, pack and full object closure below.
    This bounded capability check adds no release authority.
    """
    with path.open("rb") as stream:
        first = stream.readline(32)
        if first not in (b"# v2 git bundle\n", b"# v3 git bundle\n"):
            raise RebuilderError("offline bundle version is unsupported")
        consumed = len(first)
        while consumed <= OFFLINE_MANIFEST_BYTES:
            line = stream.readline(OFFLINE_MANIFEST_BYTES + 1 - consumed)
            consumed += len(line)
            if not line or consumed > OFFLINE_MANIFEST_BYTES:
                break
            if line == b"\n":
                return
            if line.startswith(b"-") or (line.startswith(b"@") and line != b"@object-format=sha1\n"):
                raise RebuilderError("offline bundle requires partial or unsupported source transport")
    raise RebuilderError("offline bundle header is missing or oversized")


def _offline_workspace_parent(parent: Path) -> None:
    """Keep staged pathnames beneath private, owner-controlled ancestry.

    A trusted sticky ancestor such as /tmp is allowed: its entries are also
    required to be owned by this user or root. A writable non-sticky ancestor
    would let another user replace an otherwise private child directory.
    """
    identity = parent.lstat()
    if identity.st_uid != os.getuid() or stat.S_IMODE(identity.st_mode) & 0o077:
        raise RebuilderError("offline source workspace parent is not private")
    for ancestor in (parent, *parent.parents):
        metadata = ancestor.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid not in (0, os.getuid()) \
                or (stat.S_IMODE(metadata.st_mode) & 0o022 and not metadata.st_mode & stat.S_ISVTX):
            raise RebuilderError("offline source workspace ancestry is not owner-controlled")


def checkout_source_graph_from_bundles(graph: Mapping[str, Any], workspace: Path, manifest_path: Path, *,
                                       timeout: int = 900) -> dict[str, Path]:
    """Snapshot all eight complete bundles, then materialize exact local sources.

    No network, SDK or NuGet work occurs here. This transport does not establish
    producer authentication, protected custody, signing or release eligibility.
    The caller must provide a filesystem quota for expanded Git/source bytes.
    """
    workspace_identity = stage_identity = None
    stage = None
    try:
        rows = validate_source_graph(graph)
        if not workspace.is_absolute() or workspace.exists() or workspace.is_symlink() \
                or workspace.parent.resolve(strict=True) != workspace.parent \
                or not workspace.parent.is_dir():
            raise RebuilderError("offline source workspace must be a new canonical absolute path")
        _offline_workspace_parent(workspace.parent)
        inputs = _offline_manifest(manifest_path, workspace)
        stage = Path(tempfile.mkdtemp(prefix=".offline-source-", dir=workspace.parent))
        stage_identity = stage.lstat()
        snapshots = {}
        # Complete every size/hash snapshot before creating any checkout.
        for name, (source, metadata, expected_digest) in inputs.items():
            snapshot = stage / (name + ".bundle")
            with snapshot.open("xb") as output:
                actual = _copy_offline_input(source, metadata, output, OFFLINE_BUNDLE_BYTES)
                output.flush()
                os.fsync(output.fileno())
            snapshot.chmod(0o400)
            if actual != expected_digest:
                raise RebuilderError("offline source bundle digest differs from manifest")
            _offline_bundle_header(snapshot)
            snapshots[name] = snapshot
        workspace.mkdir(mode=0o700)
        workspace_identity = workspace.lstat()
        for name, (_role, relative, repository) in REPOSITORIES.items():
            root = workspace / relative
            root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _offline_git(["init", "--quiet", "--template=", os.fspath(root)], timeout=timeout)
            command = ["-C", os.fspath(root)]
            _offline_git([*command, "bundle", "verify", os.fspath(snapshots[name])], timeout=timeout)
            _offline_git([*command, "bundle", "unbundle", os.fspath(snapshots[name])], timeout=timeout)
            _offline_git([*command, "fsck", "--full", "--strict", "--no-reflogs", rows[name]["commit"]], timeout=timeout)
            _offline_git([*command, "remote", "add", "origin", repository], timeout=timeout)
            _preserved_git_storage(root, repository)
            expected, _ = _preserved_git_inventory(root, rows[name]["commit"], _offline_git, timeout)
            _preserved_checkout_attributes(root, rows[name]["commit"], expected, _offline_git, timeout)
            _offline_git(["--attr-source=" + rows[name]["commit"], *command, "checkout", "--quiet",
                          "--detach", rows[name]["commit"]], timeout=timeout)
        roots = _verify_source_checkout_graph(graph, workspace, _offline_git, timeout=timeout)
        for name, root in roots.items():
            _preserved_repository_bytes(root, rows[name]["commit"], git=_offline_git,
                                        owner_uid=os.getuid(), timeout=timeout)
        return roots
    except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError):
        if workspace_identity is not None:
            _remove_owned_directory(workspace, workspace_identity)
        raise RebuilderError("offline source bundle materialization failed") from None
    finally:
        if stage is not None and stage_identity is not None:
            _remove_owned_directory(stage, stage_identity)


def _trusted_root(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir() or path.resolve(strict=True) != path:
        raise RebuilderError(f"{label} is not one canonical toolchain root")
    for ancestor in (path, *path.parents):
        metadata = ancestor.stat()
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
            raise RebuilderError(f"{label} ancestry is not immutable root-owned authority")
    return path


def _resolve_tree_link(root: Path, path: Path, target: str, label: str, *, owner_uid: int = 0) -> None:
    """Walk every hop inside the sealed tree, not merely the final realpath."""
    location = list(path.parent.relative_to(root).parts)
    pending = deque()
    hops = 0

    def enqueue(text: str) -> None:
        nonlocal location
        value = PurePosixPath(text)
        if not text:
            raise RebuilderError(f"{label} contains an unresolved symlink")
        if value.is_absolute():
            if not value.is_relative_to(root):
                raise RebuilderError(f"{label} symlink escapes its trusted root")
            location = []
            value = value.relative_to(root)
        pending.extendleft(reversed(value.parts))

    try:
        enqueue(target)
        while pending:
            part = pending.popleft()
            if part == "..":
                if not location:
                    raise RebuilderError(f"{label} symlink escapes its trusted root")
                location.pop()
                continue
            candidate = root.joinpath(*location, part)
            metadata = candidate.lstat()
            if metadata.st_uid != owner_uid:
                raise RebuilderError(f"{label} symlink reaches non-root-owned content")
            if stat.S_ISLNK(metadata.st_mode):
                hops += 1
                if hops > 64:
                    raise RebuilderError(f"{label} contains a cyclic or excessive-hop symlink")
                enqueue(os.readlink(candidate))
            else:
                if stat.S_IMODE(metadata.st_mode) & 0o022:
                    raise RebuilderError(f"{label} symlink reaches writable content")
                if not (stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode)):
                    raise RebuilderError(f"{label} symlink reaches unsupported content")
                if pending and not stat.S_ISDIR(metadata.st_mode):
                    raise RebuilderError(f"{label} contains an unresolved symlink")
                location.append(part)
        # Preserve kernel lookup semantics too: PurePosixPath normalizes a
        # trailing slash or '/.', which must not make a file into a directory.
        final = path.stat()
        if (final.st_uid != owner_uid or stat.S_IMODE(final.st_mode) & 0o022
                or not (stat.S_ISREG(final.st_mode) or stat.S_ISDIR(final.st_mode))):
            raise RebuilderError(f"{label} symlink reaches unsafe content")
    except (OSError, ValueError):
        raise RebuilderError(f"{label} contains an unresolved symlink") from None


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_uid,
            metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)


def _stable_file_digest(path: Path, metadata: os.stat_result, label: str, *, git_blob: bool = False) -> str:
    """Two bounded reads detect persistent drift hidden by timestamp granularity.

    Agreement is not an atomic snapshot or a substitute for immutable custody.
    """
    expected = _file_identity(metadata)
    changed = f"{label} changed while hashing"
    try:
        if _file_identity(path.lstat()) != expected:
            raise RebuilderError(changed)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
        try:
            if _file_identity(os.fstat(descriptor)) != expected:
                raise RebuilderError(changed)
            verified_digest = None
            # The descriptor remains ours even if constructing/closing the
            # stream fails. O_NONBLOCK also prevents a raced FIFO from hanging.
            with os.fdopen(descriptor, "rb", buffering=0, closefd=False) as stream:
                for pass_index in range(2):
                    if pass_index:
                        stream.seek(0)
                    digest = hashlib.sha1(usedforsecurity=False) if git_blob else hashlib.sha256()
                    if git_blob:
                        digest.update(b"blob " + str(metadata.st_size).encode("ascii") + b"\0")
                    consumed = 0
                    while chunk := stream.read(1024 * 1024):
                        consumed += len(chunk)
                        if consumed > metadata.st_size:
                            raise RebuilderError(changed)
                        digest.update(chunk)
                    if consumed != metadata.st_size or _file_identity(os.fstat(descriptor)) != expected:
                        raise RebuilderError(changed)
                    current_digest = digest.hexdigest()
                    if verified_digest is not None and current_digest != verified_digest:
                        raise RebuilderError(changed)
                    verified_digest = current_digest
        finally:
            os.close(descriptor)
        if _file_identity(path.lstat()) != expected:
            raise RebuilderError(changed)
        assert verified_digest is not None
        return verified_digest
    except (OSError, ValueError):
        raise RebuilderError(changed) from None


def _stable_file_sha256(path: Path, metadata: os.stat_result, label: str) -> str:
    return _stable_file_digest(path, metadata, label)


def _tree_digest(root: Path, label: str) -> tuple[str, int, int]:
    root = _trusted_root(root, label)
    digest, count, total = hashlib.sha256(), 0, 0
    pending = [root]
    while pending:
        directory = pending.pop()
        for entry in sorted(os.scandir(directory), key=lambda item: item.name):
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            metadata = entry.stat(follow_symlinks=False)
            is_link = stat.S_ISLNK(metadata.st_mode)
            # Linux symlink mode is normally 0777 and is not a writable-target
            # permission grant. Ownership still matters; real entries below
            # this root (including link targets) retain the strict mode check.
            if metadata.st_uid != 0 or (not is_link and stat.S_IMODE(metadata.st_mode) & 0o022):
                raise RebuilderError(f"{label} contains writable or non-root-owned content")
            if is_link:
                target = os.readlink(path)
                _resolve_tree_link(root, path, target, label)
                row = f"L\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\0{target}\n".encode()
            elif entry.is_dir(follow_symlinks=False):
                pending.append(path)
                row = f"D\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\n".encode()
            elif entry.is_file(follow_symlinks=False):
                count += 1
                total += metadata.st_size
                if count > 250_000 or total > 16 * 1024 * 1024 * 1024:
                    raise RebuilderError(f"{label} exceeds its closure bound")
                file_digest = _stable_file_sha256(path, metadata, label)
                row = (f"F\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\0{metadata.st_size}\0"
                       f"{file_digest}\n").encode()
            else:
                raise RebuilderError(f"{label} contains unsupported filesystem content")
            digest.update(row)
    return digest.hexdigest(), count, total


def _probe(runner: Callable[..., subprocess.CompletedProcess], command: list[str], label: str) -> str:
    completed = runner(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30,
                       env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/tmp"}, text=True)
    if completed.returncode != 0 or not completed.stdout or len(completed.stdout) > 256 * 1024:
        raise RebuilderError(f"{label} version probe failed")
    return completed.stdout.strip()


def _bind_auxiliary_toolchain(
    lock: Mapping[str, Any], bundletool: Path, installed_closure_receipt: Path,
    reported_builder_image: str,
) -> dict[str, Any]:
    """Bind non-tree build inputs without claiming protected-job provenance."""

    return _bind_auxiliary_toolchain_inputs(
        lock, bundletool, installed_closure_receipt, reported_builder_image, require_signer=True
    )


def _bind_auxiliary_toolchain_inputs(
    lock: Mapping[str, Any], bundletool: Path, installed_closure_receipt: Path,
    reported_builder_image: str, *, require_signer: bool,
) -> dict[str, Any]:

    toolchain = lock["toolchain"]
    if reported_builder_image != toolchain.get("builder_image"):
        raise RebuilderError("reported builder image differs from lock")
    bundletool_sha256 = _sha256_file(
        bundletool, "trusted bundletool", 64 * 1024 * 1024, owner_only=True
    )
    if bundletool_sha256 != toolchain.get("bundletool_sha256"):
        raise RebuilderError("trusted bundletool differs from lock")
    receipt_sha256 = _sha256_file(
        installed_closure_receipt,
        "installed toolchain closure receipt",
        8 * 1024 * 1024,
        owner_only=True,
    )
    if receipt_sha256 != toolchain.get("installed_closure_receipt_sha256"):
        raise RebuilderError("installed toolchain closure receipt differs from lock")
    signer_image = toolchain.get("signer_image")
    if require_signer and (not isinstance(signer_image, str) or not signer_image):
        raise RebuilderError("planned protected signer image is absent")
    return {
        "bundletoolSha256": bundletool_sha256,
        "installedClosureReceiptSha256": receipt_sha256,
        "reportedBuilderImage": reported_builder_image,
        "plannedSignerImage": signer_image,
        # These can become true only in a future protected two-job transaction.
        # Caller-supplied paths, bytes, and image strings cannot establish them.
        "builderExecutionProvenanceAuthenticated": False,
        "protectedSignerRuntimeVerified": False,
    }


def _measured_toolchain_closure(
    lock: Mapping[str, Any], observed: Mapping[str, Any], bundletool: Path,
    installed_closure_receipt: Path, reported_builder_image: str,
) -> dict[str, Any]:
    auxiliary = _bind_auxiliary_toolchain(
        lock, bundletool, installed_closure_receipt, reported_builder_image
    )
    closure = {"platform": "linux/amd64", **observed, **auxiliary}
    return {**closure, "closureSha256": hashlib.sha256(_canonical_json(closure)).hexdigest()}


def verify_toolchain(
    lock: Mapping[str, Any], dotnet_root: Path, java_root: Path, android_sdk_root: Path,
    bundletool: Path, installed_closure_receipt: Path, reported_builder_image: str, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Measure the existing full toolchain, including its planned signer image."""
    return _verify_toolchain_inputs(
        lock, dotnet_root, java_root, android_sdk_root, bundletool, installed_closure_receipt,
        reported_builder_image, runner=runner, unsigned=False,
    )


def verify_unsigned_toolchain(
    lock: Mapping[str, Any], dotnet_root: Path, java_root: Path, android_sdk_root: Path,
    bundletool: Path, installed_closure_receipt: Path, reported_builder_image: str, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Measure identical build inputs without requiring downstream signer setup.

    plannedSignerImage may remain null. This ordinary closure is bound to this
    lock's bytes by the handoff. A later configured signing lock requires a new
    matching rebuild/capture; this observation cannot promote the old handoff.
    """
    return _verify_toolchain_inputs(
        lock, dotnet_root, java_root, android_sdk_root, bundletool, installed_closure_receipt,
        reported_builder_image, runner=runner, unsigned=True,
    )


def _verify_toolchain_inputs(
    lock: Mapping[str, Any], dotnet_root: Path, java_root: Path, android_sdk_root: Path,
    bundletool: Path, installed_closure_receipt: Path, reported_builder_image: str, *,
    runner: Callable[..., subprocess.CompletedProcess], unsigned: bool,
) -> dict[str, Any]:
    toolchain = lock["toolchain"]
    roots = {"dotnet": dotnet_root, "java": java_root, "android_sdk": android_sdk_root}
    observed: dict[str, Any] = {}
    for name, root in roots.items():
        digest, count, size = _tree_digest(root, f"trusted {name} closure")
        expected = toolchain[name]
        if (digest, count, size) != (expected["tree_sha256"], expected["file_count"], expected["size_bytes"]):
            raise RebuilderError(f"trusted {name} closure differs from lock")
        observed[name] = {"treeSha256": digest, "fileCount": count, "sizeBytes": size}
    dotnet = dotnet_root / "dotnet"
    java = java_root / "bin/java"
    if _probe(runner, [os.fspath(dotnet), "--version"], "dotnet") != toolchain["dotnet"]["version"]:
        raise RebuilderError("trusted dotnet version differs from lock")
    java_output = _probe(runner, [os.fspath(java), "-version"], "Java")
    if f'"{toolchain["java"]["version"]}' not in java_output:
        raise RebuilderError("trusted Java version differs from lock")
    if not (android_sdk_root / "platforms/android-36/android.jar").is_file() \
            or not (android_sdk_root / "build-tools/36.0.0/aapt2").is_file():
        raise RebuilderError("trusted Android API/build-tools 36 closure is incomplete")
    if unsigned:
        auxiliary = _bind_auxiliary_toolchain_inputs(
            lock, bundletool, installed_closure_receipt, reported_builder_image, require_signer=False
        )
        closure = {"platform": "linux/amd64", **observed, **auxiliary}
        return {**closure, "closureSha256": hashlib.sha256(_canonical_json(closure)).hexdigest()}
    return _measured_toolchain_closure(
        lock, observed, bundletool, installed_closure_receipt, reported_builder_image
    )


def _validate_android_consumer_inputs(android_root: Path, commit: str) -> None:
    """Check import/helper/policy bytes against Git objects, not index status.

    The protected caller still owns process and filesystem immutability. This
    preflight does not turn a caller-writable checkout into a signer capability.
    """
    tree = _git(subprocess.run, ["-C", os.fspath(android_root), "ls-tree", "-r", "-z",
        "--full-tree", commit, "--", "scripts", "eng"], timeout=30, binary=True)
    if not tree or len(tree) > 1024 * 1024:
        raise RebuilderError("Android consumer closure inventory is missing or oversized")
    expected: dict[str, tuple[str, str]] = {}
    directories: set[str] = set()
    for entry in tree.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, blob = metadata.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
            path = PurePosixPath(relative)
        except (ValueError, UnicodeDecodeError) as error:
            raise RebuilderError("Android consumer closure inventory is malformed") from error
        if kind != "blob" or mode not in ("100644", "100755") or not HEX40.fullmatch(blob) \
                or path.is_absolute() or ".." in path.parts or "\\" in relative \
                or path.parts[0] not in ("scripts", "eng") or str(path) != relative \
                or relative in expected:
            raise RebuilderError("Android consumer closure inventory is not exact regular files")
        expected[relative] = (mode, blob)
        directories.update(str(parent) for parent in path.parents if str(parent) != ".")
    observed: set[str] = set()
    for top in ("scripts", "eng"):
        folder = android_root / top
        if folder.is_symlink() or not folder.is_dir() or folder.resolve(strict=True) != folder:
            raise RebuilderError("Android consumer input directory is not canonical")
        for base, children, files in os.walk(folder, followlinks=False):
            parent = Path(base)
            for name in children:
                child = parent / name
                if child.is_symlink() or child.relative_to(android_root).as_posix() not in directories:
                    raise RebuilderError("Android consumer closure has an unreviewed directory")
            for name in files:
                path = parent / name
                relative = path.relative_to(android_root).as_posix()
                if relative not in expected:
                    raise RebuilderError("Android consumer closure has an unreviewed file")
                raw = _stable_bytes(path, "Android consumer input", 8 * 1024 * 1024)
                # Git's object ID binds bytes directly, ignoring assume-unchanged,
                # staged replacements, clean filters and stat-cache shortcuts.
                blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
                                    usedforsecurity=False).hexdigest()
                mode, expected_blob = expected[relative]
                if blob != expected_blob or bool(path.stat().st_mode & 0o111) != (mode == "100755"):
                    raise RebuilderError("Android consumer input bytes or mode differ from qualified commit")
                observed.add(relative)
    if observed != set(expected):
        raise RebuilderError("Android consumer closure is incomplete")


def _bind_android_builder(module: Any, android_root: Path, lock: Mapping[str, Any]) -> None:
    """Bind the builder role after the caller has verified the source closure."""
    authority = lock["approval_authority"]  # Historical lock field; builder role.
    key_id = authority["key_id"]
    if not isinstance(key_id, str) or key_id not in BUILDER_KEY_IDS:
        raise RebuilderError("Android builder key ID is not supported")
    if authority["role"] != "android_internal_release_builder" \
            or authority["scope"] != "android_internal_release_artifact_binding":
        raise RebuilderError("Android builder authority role or scope differs")
    public_key = android_root.joinpath(*PurePosixPath(authority["public_key_path"]).parts)
    if hasattr(module.VERIFY, "_release_builder_key"):
        try:
            selected = module.VERIFY._release_builder_key(key_id)
        except Exception:
            raise RebuilderError("Android builder selector rejected the qualified key") from None
        if not isinstance(selected, tuple) or len(selected) != 2 \
                or not isinstance(selected[0], Path) \
                or selected != (public_key, authority["public_key_sha256"]):
            raise RebuilderError("Android builder selector differs from qualified authority")
        selection = "explicit-builder"
    else:
        android = lock["android_authority"]
        binding = (android["commit"], android["tree"], android["attestation_consumer"]["path"],
                   android["attestation_consumer"]["sha256"], key_id, authority["public_key_path"],
                   authority["public_key_sha256"], authority["public_key_spki_sha256"])
        if binding != LEGACY_BUILDER_BINDING \
                or getattr(module.VERIFY, "RELEASE_APPROVER_KEY_ID", None) != key_id:
            raise RebuilderError("Android consumer lacks the qualified builder selector")
        selection = "qualified-legacy"
    raw = _stable_bytes(public_key, "Android attestation public key", 64 * 1024)
    if hashlib.sha256(raw).hexdigest() != authority["public_key_sha256"]:
        raise RebuilderError("Android attestation public key differs from lock")
    # Ed25519 SPKI is exactly 44 bytes. Decode the same held public PEM bytes
    # whose SHA was checked; no OpenSSL/private-key operation is needed here.
    lines = raw.splitlines()
    if len(lines) != 3 or lines[0] != b"-----BEGIN PUBLIC KEY-----" \
            or lines[2] != b"-----END PUBLIC KEY-----":
        raise RebuilderError("Android builder public key is not Ed25519 SPKI")
    try:
        der = base64.b64decode(lines[1], validate=True)
    except (ValueError, binascii.Error):
        raise RebuilderError("Android builder public key is not Ed25519 SPKI") from None
    if len(der) != 44 or der[:12] != bytes.fromhex("302a300506032b6570032100") \
            or base64.b64encode(der) != lines[1] \
            or hashlib.sha256(der).hexdigest() != authority["public_key_spki_sha256"]:
        raise RebuilderError("Android builder public SPKI differs from lock")
    module._fleet_builder_key_id = key_id
    module._fleet_builder_selection = selection
    module._fleet_expected_spki_sha256 = authority["public_key_spki_sha256"]


def _android_builder_selection(android: Any, authority: Mapping[str, Any] | None = None) -> tuple[str, bool]:
    key_id = getattr(android, "_fleet_builder_key_id", None)
    selection = getattr(android, "_fleet_builder_selection", None)
    if not isinstance(key_id, str) or key_id not in BUILDER_KEY_IDS \
            or selection not in ("explicit-builder", "qualified-legacy") \
            or (selection == "qualified-legacy" and key_id != BUILDER_KEY_IDS[0]) \
            or (authority is not None and key_id != authority["key_id"]):
        raise RebuilderError("Fleet did not bind the qualified Android builder selector")
    return key_id, selection == "explicit-builder"


def validate_android_consumer(android_root: Path, lock: Mapping[str, Any]):
    # SourceFileLoader may READ timestamp/hash-valid caches even when writes
    # are disabled. A prefix outside scripts/eng is outside the checked blob
    # closure, so reject it before any direct or transitive consumer import.
    if sys.pycache_prefix is not None:
        raise RebuilderError("Android consumer bytecode cache prefix is not permitted")
    android = lock["android_authority"]
    if android_root.is_symlink() or not android_root.is_dir() or android_root.resolve(strict=True) != android_root:
        raise RebuilderError("Android consumer checkout is not canonical")
    head = _git(subprocess.run, ["-C", os.fspath(android_root), "rev-parse", "HEAD^{commit}"], timeout=30)
    tree = _git(subprocess.run, ["-C", os.fspath(android_root), "rev-parse", "HEAD^{tree}"], timeout=30)
    remote = _git(subprocess.run, ["-C", os.fspath(android_root), "remote", "get-url", "origin"], timeout=30)
    if (head, tree, remote) != (android["commit"], android["tree"], android["repository"]):
        raise RebuilderError("Android consumer checkout differs from qualified authority")
    _validate_android_consumer_inputs(android_root, android["commit"])
    for binding_name in ("build_script", "attestation_consumer", "two_green_verifier", "source_graph_verifier"):
        binding = android[binding_name]
        path = android_root.joinpath(*PurePosixPath(binding["path"]).parts)
        if _sha256_file(path, f"Android {binding_name}", 8 * 1024 * 1024) != binding["sha256"]:
            raise RebuilderError(f"Android {binding_name} bytes differ from lock")
    consumer_path = android_root / android["attestation_consumer"]["path"]
    prior_release_root = os.environ.get("CHUMMER_RELEASE_REPO_ROOT")
    prior_bytecode_posture = sys.dont_write_bytecode
    os.environ["CHUMMER_RELEASE_REPO_ROOT"] = os.fspath(android_root)
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("fleet_android_v2_consumer", consumer_path)
        if spec is None or spec.loader is None:
            raise RebuilderError("cannot load exact Android v2 consumer")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = prior_bytecode_posture
        if prior_release_root is None:
            os.environ.pop("CHUMMER_RELEASE_REPO_ROOT", None)
        else:
            os.environ["CHUMMER_RELEASE_REPO_ROOT"] = prior_release_root
    _validate_android_consumer_inputs(android_root, android["commit"])
    if module.CONTRACT != ANDROID_ATTESTATION_CONTRACT \
            or module.EXPECTED_UPLOAD_CERTIFICATE_SHA256.replace(":", "").lower() != UPLOAD_CERTIFICATE_SHA256:
        raise RebuilderError("Android v2 consumer authority differs from lock")
    _bind_android_builder(module, android_root, lock)
    return module


def _preserved_path(path: Path, label: str, *, directory: bool = False) -> None:
    """Require actual read-only mounts, not caller assertions of custody."""
    try:
        if not isinstance(path, Path) or not path.is_absolute() or path.is_symlink() \
                or path.resolve(strict=True) != path \
                or not (path.is_dir() if directory else path.is_file()):
            raise RebuilderError(f"{label} is not a canonical preserved input")
        _trusted_root(path if directory else path.parent, label)
        metadata = path.stat()
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022 \
                or not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RebuilderError(f"{label} is not root-owned read-only custody")
    except (OSError, RuntimeError, ValueError) as error:
        if isinstance(error, RebuilderError):
            raise
        raise RebuilderError(f"{label} preserved input is unavailable") from None


def _preserved_tree(root: Path, label: str) -> None:
    # Checking just a mount root admits a writable nested bind mount. Inspect
    # every actual entry, including Git metadata; never follow links in walks.
    _preserved_path(root, label, directory=True)
    pending, count = [root], 0
    while pending:
        current = pending.pop()
        for path in current.iterdir():
            count += 1
            if count > 250_000:
                raise RebuilderError(f"{label} preserved inventory is oversized")
            if path.is_symlink():
                if path.lstat().st_uid != 0:
                    raise RebuilderError(f"{label} link is not root-owned")
                _resolve_tree_link(root, path, os.readlink(path), label)
                if not os.statvfs(path).f_flag & os.ST_RDONLY:
                    raise RebuilderError(f"{label} link reaches a writable mount")
            else:
                is_directory = path.is_dir()
                _preserved_path(path, label, directory=is_directory)
                if is_directory:
                    pending.append(path)


def _preserved_git_storage(root: Path, repository: str | None = None) -> None:
    """Plain detached clones only: no external storage or executable config."""
    if not (root / ".git").is_dir() or (root / ".git").is_symlink():
        raise RebuilderError("preserved source requires independent contained Git storage")
    for relative in ("objects/info/alternates", "objects/info/http-alternates", "commondir", "gitdir",
                     "shallow", "worktrees", "modules", "info/grafts", "refs/replace", "info/attributes"):
        path = root / ".git" / relative
        if path.exists() or path.is_symlink():
            raise RebuilderError("preserved Git storage references an external or replacement authority")
    hooks = root / ".git/hooks"
    if hooks.exists() and (hooks.is_symlink() or not hooks.is_dir()
                           or any(path.is_symlink() or not path.is_file() or not path.name.endswith(".sample")
                                  for path in hooks.iterdir())):
        raise RebuilderError("preserved Git storage contains active hooks")
    packs = root / ".git/objects/pack"
    if packs.exists() and (packs.is_symlink() or not packs.is_dir()
                           or any(path.name.endswith(".promisor") for path in packs.iterdir())):
        raise RebuilderError("preserved Git storage is a partial clone")
    path = root / ".git/config"
    raw = _stable_bytes(path, "preserved Git config", 64 * 1024)
    parser = configparser.ConfigParser(interpolation=None, strict=True, delimiters=("=",),
                                       empty_lines_in_values=False)
    try:
        parser.read_string(raw.decode("utf-8", errors="strict"))
        if parser.defaults() or set(parser.sections()) - {"core", 'remote "origin"'} or "core" not in parser:
            raise ValueError()
        core = dict(parser["core"])
        if set(core) - {"repositoryformatversion", "bare", "filemode", "logallrefupdates", "ignorecase",
                        "precomposeunicode", "symlinks"} \
                or core.get("repositoryformatversion") != "0" or core.get("bare") != "false" \
                or any(value not in ("true", "false") for key, value in core.items()
                       if key != "repositoryformatversion"):
            raise ValueError()
        if 'remote "origin"' in parser:
            remote = dict(parser['remote "origin"'])
            if set(remote) != {"url", "fetch"} or remote["fetch"] != "+refs/heads/*:refs/remotes/origin/*" \
                    or remote["url"] not in ({repository} if repository is not None else {value[2] for value in REPOSITORIES.values()}) \
                    or (repository is not None and remote["url"] != repository):
                raise ValueError()
        elif repository is not None:
            raise ValueError()
    except (ValueError, UnicodeDecodeError, configparser.Error):
        raise RebuilderError("preserved Git config is not an exact helper-free clone") from None


def _preserved_git_inventory(root: Path, commit: str, operation: Callable[..., bytes | str],
                              timeout: int) -> tuple[dict[str, tuple[str, str]], set[str]]:
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise RebuilderError("preserved source commit is not exact")
    listing = operation(["-C", os.fspath(root), "ls-tree", "-r", "-z", "--full-tree", commit],
                        timeout=timeout, binary=True)
    if not isinstance(listing, bytes) or not listing or len(listing) > 8 * 1024 * 1024:
        raise RebuilderError("preserved source Git inventory is missing or oversized")
    expected, parents = {}, set()
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, blob = metadata.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
            path = PurePosixPath(relative)
        except (ValueError, UnicodeDecodeError):
            raise RebuilderError("preserved source Git inventory is malformed") from None
        if kind != "blob" or mode not in ("100644", "100755", "120000") \
                or not HEX40.fullmatch(blob) or path.is_absolute() or ".." in path.parts \
                or "\\" in relative or str(path) != relative or relative in expected or ".git" in path.parts:
            raise RebuilderError("preserved source Git inventory is not exact")
        expected[relative] = (mode, blob)
        parents.update(str(parent) for parent in path.parents if str(parent) != ".")
    return expected, parents


def _preserved_checkout_attributes(root: Path, commit: str, expected: Mapping[str, tuple[str, str]],
                                    operation: Callable[..., bytes | str], timeout: int) -> None:
    """Only committed built-in checkout transformations, never filter helpers.

    --attr-source is a required Git capability, not a silently ignored config
    variable. Both attribute lookup and conversion use the exact admitted tree.
    """
    paths = list(expected)
    for relative, (mode, _blob) in expected.items():
        if PurePosixPath(relative).name == ".gitattributes" and mode == "120000":
            raise RebuilderError("preserved source has an unsupported attribute link")
    for offset in range(0, len(paths), 128):
        batch = paths[offset:offset + 128]
        raw = operation(["--attr-source=" + commit, "-C", os.fspath(root), "check-attr",
                         "--source=" + commit, "-z", "filter", "--", *batch], timeout=timeout, binary=True)
        if not isinstance(raw, bytes) or len(raw) > OFFLINE_GIT_OUTPUT_BYTES or not raw.endswith(b"\0"):
            raise RebuilderError("preserved checkout attributes are not exact")
        fields = raw[:-1].split(b"\0")
        if len(fields) != 3 * len(batch):
            raise RebuilderError("preserved checkout attributes are not exact")
        for index, relative in enumerate(batch):
            path, attribute, value = fields[3 * index:3 * index + 3]
            if path != relative.encode("utf-8") or attribute != b"filter" \
                    or value not in (b"unspecified", b"unset"):
                raise RebuilderError("preserved source requires an unsupported checkout filter")


def _expected_checkout_digest(root: Path, commit: str, relative: str, blob: str, *,
                               size: int, timeout: int) -> str:
    """Stream exactly the declared checkout representation; do not normalize input.

    The actual file size is a strict output bound, not authority about expected
    bytes. Too much/too little output fails. Large source files remain streamed
    rather than being collected under the separate eight-MiB metadata limit.
    """
    digest = hashlib.sha256()
    consumed = _offline_git_stream(
        ["--attr-source=" + commit, "-C", os.fspath(root), "cat-file", "--filters",
         "--path=" + relative, blob], timeout=timeout, output_limit=size, consume=digest.update,
    )
    if consumed != size:
        raise RebuilderError("preserved source checkout size differs from Git")
    return digest.hexdigest()


def _preserved_repository_bytes(root: Path, commit: str, *, git: Callable[..., bytes | str] | None = None,
                                owner_uid: int = 0, timeout: int = 30, repository: str | None = None) -> None:
    """Bind exact committed checkout bytes, including hidden and EOL-only drift."""
    _preserved_git_storage(root, repository)
    operation = git or _offline_git
    expected, parents = _preserved_git_inventory(root, commit, operation, timeout)
    observed = set()
    regular = []
    for base, directories, files in os.walk(root, followlinks=False):
        parent = Path(base)
        if parent == root:
            directories.remove(".git")
        for name in list(directories):
            path = parent / name
            if path.is_symlink():
                directories.remove(name)
                files.append(name)
            elif path.relative_to(root).as_posix() not in parents:
                raise RebuilderError("preserved source has an unreviewed directory")
        for name in files:
            path = parent / name
            relative = path.relative_to(root).as_posix()
            if relative not in expected:
                raise RebuilderError("preserved source has an unreviewed file")
            mode, blob = expected[relative]
            if path.is_symlink():
                if mode != "120000":
                    raise RebuilderError("preserved source file became a link")
                raw = os.fsencode(os.readlink(path))
                _resolve_tree_link(root, path, os.fsdecode(raw), "preserved source", owner_uid=owner_uid)
                actual = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw,
                                      usedforsecurity=False).hexdigest()
                if actual != blob:
                    raise RebuilderError("preserved source bytes differ from Git")
            else:
                if mode == "120000" or bool(path.stat().st_mode & 0o111) != (mode == "100755"):
                    raise RebuilderError("preserved source mode differs from Git")
                regular.append((relative, path, blob, path.lstat()))
            observed.add(relative)
    if observed != set(expected):
        raise RebuilderError("preserved source is incomplete")
    # Reject untracked attribute overrides/membership before conversion. Compare
    # tracked attribute files first; conversion never consults their live bytes.
    _preserved_checkout_attributes(root, commit, expected, operation, timeout)
    regular.sort(key=lambda row: PurePosixPath(row[0]).name != ".gitattributes")
    for relative, path, blob, metadata in regular:
        actual = _stable_file_digest(path, metadata, "preserved source")
        prescribed = _expected_checkout_digest(root, commit, relative, blob,
                                                size=metadata.st_size, timeout=timeout)
        if _file_identity(path.lstat()) != _file_identity(metadata) or actual != prescribed:
            raise RebuilderError("preserved source bytes differ from Git checkout")


class PreservedProtectedValidation:
    """Concrete, key-free composition for both protected transaction seams.

    Use this object's load_consumer and this callable together. Its independently
    retained read-only workspace is NOT the disposable unsigned builder root.
    It grants no provenance/signing authority and never replaces Android checks.
    """

    def __init__(self, lock_path: Path, *, workspace_root: Path, source_graph: Path,
                 package_authority: Path, authority_root: Path, bundletool: Path,
                 upload_certificate: Path, java_tool_observation: Path,
                 installed_closure_receipt: Path,
                 dotnet_root: Path, java_root: Path, android_sdk_root: Path) -> None:
        self.workspace_root, self.authority_root = workspace_root, authority_root
        self.files = {
            "lock": lock_path, "source_graph": source_graph, "package_authority": package_authority,
            "bundletool": bundletool, "upload_certificate": upload_certificate,
            "java_tool_observation": java_tool_observation,
            "installed_closure_receipt": installed_closure_receipt,
        }
        self.tool_roots = {"dotnet": dotnet_root, "java": java_root, "android_sdk": android_sdk_root}
        self._limits = {"bundletool": 64 * 1024 * 1024, "upload_certificate": 1024 * 1024}
        self._bindings = self._capture_inputs()
        self.lock, _ = load_lock(lock_path)
        self.graph, _ = _json_file(source_graph, "preserved source graph", 8 * 1024 * 1024, owner_only=True)
        self._check_source()
        self.android = validate_android_consumer(workspace_root / "chummer-android", self.lock)
        self._functions = {name: getattr(self.android, name) for name in (
            "_artifact_claims", "_protected_validation", "_validate_validation_claims",
        )}
        self._check_exact()

    def _capture_installed_closure_receipt(self) -> tuple[tuple[int, ...], str]:
        path = self.files["installed_closure_receipt"]
        _preserved_path(path, "preserved installed closure receipt")
        before = _file_identity(path.stat())
        digest = _sha256_file(path, "preserved installed closure receipt", 8 * 1024 * 1024, owner_only=True)
        _preserved_path(path, "preserved installed closure receipt")
        if before != _file_identity(path.stat()):
            raise RebuilderError("preserved installed closure receipt changed while being captured")
        return before, digest

    def _capture_inputs(self) -> dict[str, Any]:
        for root in (self.workspace_root, self.authority_root, *self.tool_roots.values()):
            _preserved_tree(root, "protected validation root")
        roots = [self.workspace_root, self.authority_root, *self.tool_roots.values()]
        if any(left == right or left.is_relative_to(right) or right.is_relative_to(left)
               for index, left in enumerate(roots) for right in roots[index + 1:]):
            raise RebuilderError("preserved validation roots must be disjoint")
        result = {}
        for name, path in self.files.items():
            if name == "installed_closure_receipt":
                result[name] = self._capture_installed_closure_receipt()
                continue
            _preserved_path(path, f"preserved {name}")
            result[name] = _sha256_file(path, f"preserved {name}", self._limits.get(name, 8 * 1024 * 1024),
                                        owner_only=name != "lock")
        if not self.files["package_authority"].is_relative_to(self.authority_root):
            raise RebuilderError("package authority is outside its preserved authority root")
        return result

    def _check_source(self) -> None:
        rows = validate_source_graph(self.graph)
        for name, (_role, relative, repository) in REPOSITORIES.items():
            _preserved_git_storage(self.workspace_root / relative, repository)
        roots = verify_source_checkout_graph(self.graph, self.workspace_root, timeout=30)
        permitted = {str(parent) for root in roots.values()
                     for parent in (root, *root.parents) if parent.is_relative_to(self.workspace_root)}
        for base, directories, files in os.walk(self.workspace_root, followlinks=False):
            parent = Path(base)
            if parent in roots.values():
                directories[:] = []
                continue
            if files or any(str(parent / name) not in permitted for name in directories):
                raise RebuilderError("preserved workspace contains unrelated input")
        for name, root in roots.items():
            _preserved_repository_bytes(root, rows[name]["commit"])

    def _check_exact(self) -> dict[str, Any]:
        if self._capture_inputs() != self._bindings:
            raise RebuilderError("preserved validation input bytes changed")
        self._check_source()
        android = self.android
        if android.ROOT != self.workspace_root / "chummer-android" \
                or Path(android.__file__) != android.ROOT / self.lock["android_authority"]["attestation_consumer"]["path"] \
                or any(getattr(android, name) is not function for name, function in self._functions.items()):
            raise RebuilderError("protected validation consumer instance changed")
        _validate_android_consumer_inputs(android.ROOT, self.lock["android_authority"]["commit"])
        rows = validate_source_graph(self.graph)
        python = android._trusted_system_executable(Path("/usr/bin/python3"), "protected Python")
        _preserved_path(python, "protected Python")
        # Execute the actual qualified verifier in an isolated process; do not
        # let an ambient Git config/helper environment alter its source checks.
        android._run_validator(
            [os.fspath(python), "-I", "-E", "-S", os.fspath(android.ROOT / "scripts/verify_release_source_graph.py"),
             "--android-root", os.fspath(android.ROOT), "--workspace-root", os.fspath(self.workspace_root),
             "--package-authority", os.fspath(self.files["package_authority"]),
             "--authority-root", os.fspath(self.authority_root), "--expected-version-name", VERSION_NAME,
             "--expected-version-code", str(VERSION_CODE), "--verify-existing", os.fspath(self.files["source_graph"])],
            {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_REPLACE_OBJECTS": "1",
             **{REVISION_VARIABLES[name]: row["commit"] for name, row in rows.items()}},
            "preserved canonical source/package graph", 120)
        if self._bindings["bundletool"] != self.lock["toolchain"]["bundletool_sha256"]:
            raise RebuilderError("preserved bundletool differs from qualified lock")
        openssl = android._trusted_system_executable(Path("/usr/bin/openssl"), "protected openssl")
        _preserved_path(openssl, "protected openssl")
        certificate = subprocess.run(
            [os.fspath(openssl), "x509", "-in", os.fspath(self.files["upload_certificate"]),
             "-noout", "-fingerprint", "-sha256"],
            check=False, capture_output=True, text=True, timeout=20,
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
        fingerprint = certificate.stdout.strip().removeprefix("sha256 Fingerprint=").removeprefix("SHA256 Fingerprint=")
        if certificate.returncode != 0 or fingerprint.replace(":", "").lower() != UPLOAD_CERTIFICATE_SHA256:
            raise RebuilderError("preserved public upload certificate differs")
        # Observation is not the installed-archive receipt. Android checks its
        # real tools and probes; Fleet additionally binds all three locked trees.
        observed = android._load_trusted_java_toolchain(self.files["java_tool_observation"])
        if observed["tools"]["java"] != self.tool_roots["java"] / "bin/java" \
                or observed["dotnet"] != self.tool_roots["dotnet"] / "dotnet":
            raise RebuilderError("preserved tool observation uses different tool roots")
        measured = {}
        for name, root in self.tool_roots.items():
            pin = self.lock["toolchain"][name]
            digest, count, size = _tree_digest(root, f"preserved {name}")
            if (digest, count, size) != (pin["tree_sha256"], pin["file_count"], pin["size_bytes"]):
                raise RebuilderError("preserved tool tree differs from qualified lock")
            measured[name] = {"treeSha256": digest, "fileCount": count, "sizeBytes": size}
        # Reuse these measurements: do not reread the multi-gigabyte tool trees.
        # Locked image strings bind the closure, never the current runtime.
        closure = _measured_toolchain_closure(
            self.lock, measured, self.files["bundletool"], self.files["installed_closure_receipt"],
            self.lock["toolchain"]["builder_image"],
        )
        if self._capture_installed_closure_receipt() != self._bindings["installed_closure_receipt"]:
            raise RebuilderError("preserved installed closure receipt changed during validation")
        return closure

    def bind_transaction(self, lock_raw: bytes, lease: Any, load_consumer: Any) -> None:
        # Binding happens before ledger reservation/credentials in both paths.
        # This does not authenticate the preserved workspace's provisioner.
        if load_consumer != self.load_consumer \
                or hashlib.sha256(lock_raw).hexdigest() != self._bindings["lock"] \
                or lease.handoff["bindings"]["sourceGraphSha256"] != self._bindings["source_graph"] \
                or lease.java_root != self.tool_roots["java"]:
            raise RebuilderError("preserved validation differs from authenticated transaction")
        closure = self._check_exact()
        if lease.handoff["bindings"].get("toolchainClosureSha256") != closure["closureSha256"] \
                or lease.toolchain.get("builderClosureSha256") != closure["closureSha256"] \
                or lease.toolchain.get("installedClosureReceiptSha256") != closure["installedClosureReceiptSha256"]:
            raise RebuilderError("preserved measured toolchain differs from authenticated handoff")

    def load_consumer(self) -> Any:
        self._check_exact()
        return self.android

    def __call__(self, *, android: Any, signed_aab: Path, source_graph: Path,
                 sidecar: Path, two_green_receipt: Path, approval: Path) -> Mapping[str, Any]:
        if android is not self.android:
            raise RebuilderError("protected validation requires its exact preserved consumer")
        self._check_exact()
        if _sha256_file(source_graph, "protected source graph", 8 * 1024 * 1024, owner_only=True) \
                != self._bindings["source_graph"]:
            raise RebuilderError("protected source graph differs from preserved workspace")
        claims = self._functions["_artifact_claims"](
            signed_aab, source_graph, sidecar, two_green_receipt, approval)
        android.VERIFY.verify_release_eligibility(
            two_green_receipt, approval, android_root=android.ROOT,
            expected_version_name=VERSION_NAME, expected_version_code=VERSION_CODE,
            source_graph_path=source_graph)
        result = self._functions["_protected_validation"](
            claims, signed_aab, source_graph, two_green_receipt, approval,
            workspace_root=self.workspace_root, package_authority=self.files["package_authority"],
            authority_root=self.authority_root, bundletool=self.files["bundletool"],
            upload_certificate=self.files["upload_certificate"],
            java_tool_authority=self.files["java_tool_observation"])
        result = self._functions["_validate_validation_claims"](result)
        self._check_exact()
        return result


def _checked(runner: Callable[..., subprocess.CompletedProcess], command: list[str], *, env: Mapping[str, str],
             label: str, timeout: int = 120, text: bool = False) -> subprocess.CompletedProcess:
    completed = runner(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       env=dict(env), timeout=timeout, text=text)
    if completed.returncode != 0:
        raise RebuilderError(f"{label} failed")
    return completed


def _pem_der(raw: str) -> bytes:
    match = re.search(r"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", raw, re.S)
    if not match:
        raise RebuilderError("signed AAB did not expose one certificate")
    try:
        return base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=True)
    except (ValueError, binascii.Error) as error:
        raise RebuilderError("signed AAB certificate is not valid PEM") from error


def _secret_file(path: Path, label: str) -> Path:
    _stable_bytes(path, label, 32 * 1024 * 1024, owner_only=True)
    return path


def sign_aab(unsigned_aab: Path, output: Path, lock: Mapping[str, Any], keystore: Path,
             store_password_file: Path, key_password_file: Path, java_root: Path, *,
             runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict[str, Any]:
    upload = lock["upload_key"]
    # Capture immutable candidate bytes before the first signing credential is
    # opened. The transaction admits credentials only after reservation.
    unsigned_raw = _stable_bytes(
        unsigned_aab, "unsigned AAB", lock["limits"]["aab_bytes"], owner_only=True
    )
    for path, label in ((keystore, "upload keystore"), (store_password_file, "store password"),
                        (key_password_file, "key password")):
        _secret_file(path, label)
    store_password = _stable_bytes(store_password_file, "store password", 4096, owner_only=True).decode("utf-8").rstrip("\n")
    key_password = _stable_bytes(key_password_file, "key password", 4096, owner_only=True).decode("utf-8").rstrip("\n")
    if not store_password or not key_password or "\n" in store_password or "\n" in key_password:
        raise RebuilderError("upload-key password files are invalid")
    env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": "/tmp",
           "FLEET_STOREPASS": store_password, "FLEET_KEYPASS": key_password}
    keytool, jarsigner = java_root / "bin/keytool", java_root / "bin/jarsigner"
    certificate = _checked(runner, [os.fspath(keytool), "-exportcert", "-alias", upload["key_alias"],
        "-keystore", os.fspath(keystore), "-storetype", "PKCS12", "-storepass:env", "FLEET_STOREPASS"],
        env=env, label="upload certificate extraction").stdout
    if hashlib.sha256(certificate).hexdigest() != UPLOAD_CERTIFICATE_SHA256:
        raise RebuilderError("upload keystore is not the recovered legacy Play identity")
    _write_exclusive(output, unsigned_raw)
    # From this point onward the file may contain the only bytes produced by a
    # consumed sign-once operation.  Verification failures are handled by the
    # transaction journal and must never destroy those unverified bytes.
    _checked(runner, [os.fspath(jarsigner), "-keystore", os.fspath(keystore), "-storetype", "PKCS12",
        "-storepass:env", "FLEET_STOREPASS", "-keypass:env", "FLEET_KEYPASS", "-sigalg",
        upload["signature_algorithm"], "-digestalg", upload["digest_algorithm"], os.fspath(output),
        upload["key_alias"]], env=env, label="AAB signing", timeout=300)
    verified = _checked(runner, [os.fspath(jarsigner), "-verify", "-verbose", "-certs", os.fspath(output)],
                        env=env, label="signed AAB verification", timeout=300, text=True)
    if "jar verified." not in verified.stdout:
        raise RebuilderError("jarsigner did not verify the signed AAB")
    pem = _checked(runner, [os.fspath(keytool), "-printcert", "-jarfile", os.fspath(output), "-rfc"],
                   env=env, label="signed AAB certificate inspection", text=True).stdout
    if hashlib.sha256(_pem_der(pem)).hexdigest() != UPLOAD_CERTIFICATE_SHA256:
        raise RebuilderError("signed AAB certificate is not the recovered legacy Play identity")
    return {"sha256": _sha256_file(output, "signed AAB", lock["limits"]["aab_bytes"]),
            "sizeBytes": output.stat().st_size, "uploadCertificateSha256": UPLOAD_CERTIFICATE_SHA256}


def materialize_signed_sidecar(signed_aab: Path, graph: Path, output: Path, limit: int) -> bytes:
    """Create the exact two-line sidecar Android v2 validates for signed bytes."""

    signed_sha = _sha256_file(signed_aab, "signed AAB", limit)
    graph_sha = _sha256_file(graph, "signed source graph", 8 * 1024 * 1024, owner_only=True)
    raw = (
        f"{signed_sha}  artifacts/{signed_aab.name}\n"
        f"{graph_sha}  artifacts/{graph.name}\n"
    ).encode("ascii")
    _write_exclusive(output, raw)
    return raw


def _owner_key_matches(runner: Callable[..., subprocess.CompletedProcess], private_key: Path,
                       expected_spki: str) -> None:
    _secret_file(private_key, "Android v2 attestation private key")
    completed = _checked(runner, ["/usr/bin/openssl", "pkey", "-in", os.fspath(private_key), "-pubout", "-outform", "DER"],
                         env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                         label="Android v2 attestation key identity")
    if hashlib.sha256(completed.stdout).hexdigest() != expected_spki:
        raise RebuilderError("Android v2 attestation private key does not match qualified public authority")


def android_v2_attestation(android, signed_aab: Path, graph: Path, sidecar: Path, two_green_receipt: Path,
                           approval: Path, protected_validation: Mapping[str, Any], owner_private_key: Path,
                           output: Path, *, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                           now: datetime | None = None, nonce: str | None = None) -> dict[str, Any]:
    key_id, explicit = _android_builder_selection(android)
    claims = android._artifact_claims(signed_aab, graph, sidecar, two_green_receipt, approval)
    identity = claims["graph"]["releaseIdentity"]
    qualification = android.VERIFY.verify_release_eligibility(
        two_green_receipt, approval, android_root=android.ROOT,
        expected_version_name=identity["versionName"], expected_version_code=identity["versionCode"],
        source_graph_path=graph,
    )
    validation = android._validate_validation_claims(dict(protected_validation))
    generated = (now or datetime.now(UTC)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    challenge = nonce or os.urandom(32).hex()
    _sha256(challenge, "build attestation challenge nonce")
    unsigned = android._unsigned(claims, qualification, validation, generated, challenge,
                                 **({"key_id": key_id} if explicit else {}))
    if unsigned.get("contractName") != ANDROID_ATTESTATION_CONTRACT \
            or unsigned.get("keyId") != key_id \
            or set(unsigned).intersection({"contract_name", "fleetAudit"}):
        raise RebuilderError("Android v2 attestation materializer returned an incompatible dialect")
    # The Android verifier pins the PEM bytes; Fleet additionally pins the SPKI.
    expected_spki = getattr(android, "_fleet_expected_spki_sha256", None)
    if not isinstance(expected_spki, str):
        raise RebuilderError("Fleet did not bind the Android v2 attestation SPKI")
    _owner_key_matches(runner, owner_private_key, expected_spki)
    with tempfile.TemporaryDirectory(prefix="fleet-android-v2-attestation-") as directory:
        payload = Path(directory) / "payload.json"
        payload.write_bytes(android.VERIFY._canonical_json_bytes(unsigned))
        signed = _checked(runner, ["/usr/bin/openssl", "pkeyutl", "-sign", "-inkey", os.fspath(owner_private_key),
                           "-rawin", "-in", os.fspath(payload)],
                          env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                          label="Android v2 detached attestation signing")
    if len(signed.stdout) != 64:
        raise RebuilderError("Android v2 detached attestation signature length is invalid")
    value = {**unsigned, "signatureBase64": base64.b64encode(signed.stdout).decode("ascii")}
    raw = android._pretty(value)
    _write_exclusive(output, raw)
    # A detached-signature operation has already been consumed.  Preserve the
    # generated bytes if the independent consumer rejects them; the outer
    # transaction quarantines them and never promotes or retries signing.
    android.verify(output, signed_aab, graph, sidecar, two_green_receipt, approval)
    if output.read_bytes() != android._pretty(value) or not output.read_bytes().endswith(b"\n"):
        raise RebuilderError("Android v2 attestation bytes are not exact pretty JSON with one trailing newline")
    return value


def external_signer_attestation(
    request: Mapping[str, Any], rebuilt: Mapping[str, Any], signed: Mapping[str, Any],
    graph_raw: bytes, toolchain: Mapping[str, Any], android_v2_path: Path,
    owner_private_key: Path, approval_authority: Mapping[str, Any], output: Path, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    now: datetime | None = None, nonce: str | None = None,
) -> dict[str, Any]:
    """Emit the detached public v1 response explicitly required by Android."""

    if toolchain.get("builderExecutionProvenanceAuthenticated") is not True \
            or toolchain.get("protectedSignerRuntimeVerified") is not True:
        raise RebuilderError("protected builder and signer runtime provenance is not established")
    _sha256(toolchain.get("closureSha256"), "full protected toolchain closure")
    expected = request["expectedExternalSignerOutput"]
    key_id = approval_authority.get("key_id")
    role = approval_authority.get("role")
    scope = approval_authority.get("scope")
    spki = approval_authority.get("public_key_spki_sha256")
    if not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._-]{3,128}", value)
               for value in (key_id, role, scope)) or not HEX64.fullmatch(str(spki or "")):
        raise RebuilderError("external signer approval authority is invalid")
    generated = (now or datetime.now(UTC)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    challenge = nonce or os.urandom(32).hex()
    _sha256(challenge, "external signer challenge nonce")
    value = {
        "contractName": EXTERNAL_SIGNER_ATTESTATION_CONTRACT,
        "algorithm": "ed25519",
        "keyId": key_id,
        "role": role,
        "attestationScope": scope,
        "generatedAtUtc": generated,
        "challengeNonce": challenge,
        "releaseIdentity": dict(request["releaseIdentity"]),
        "unsignedAabSha256": rebuilt["sha256"],
        "signedAabSha256": signed["sha256"],
        "signedAabSizeBytes": signed["sizeBytes"],
        "sourceGraphSha256": hashlib.sha256(graph_raw).hexdigest(),
        "expectedUploadCertificateSha256": signed["uploadCertificateSha256"],
        "fullToolchainClosureSha256": toolchain["closureSha256"],
        "androidReleaseBuildAttestation": {
            "contractName": ANDROID_ATTESTATION_CONTRACT,
            "sha256": _sha256_file(
                android_v2_path, "Android v2 attestation", 8 * 1024 * 1024, owner_only=True
            ),
        },
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
    }
    if value["unsignedAabSha256"] != expected["mustBindUnsignedAabSha256"] \
            or value["sourceGraphSha256"] != expected["mustBindSourceGraphSha256"] \
            or value["expectedUploadCertificateSha256"] \
            != expected["mustBindExpectedUploadCertificateSha256"].replace(":", "").lower() \
            or value["releaseIdentity"] != expected["mustBindReleaseIdentity"]:
        raise RebuilderError("external signer v1 response does not satisfy Android's exact request")
    _owner_key_matches(runner, owner_private_key, str(spki))
    with tempfile.TemporaryDirectory(prefix="fleet-external-signer-v1-") as directory:
        payload = Path(directory) / "payload.json"
        payload.write_bytes(_canonical_json(value))
        signature = _checked(
            runner,
            ["/usr/bin/openssl", "pkeyutl", "-sign", "-inkey", os.fspath(owner_private_key),
             "-rawin", "-in", os.fspath(payload)],
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            label="external signer v1 detached signing",
        ).stdout
    if len(signature) != 64:
        raise RebuilderError("external signer v1 detached signature length is invalid")
    result = {**value, "signatureBase64": base64.b64encode(signature).decode("ascii")}
    _write_exclusive(output, _pretty_json(result))
    return result


def _immutable_ledger_path(fleet_root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative or PurePosixPath(relative).is_absolute() \
            or ".." in PurePosixPath(relative).parts or "\\" in relative \
            or PurePosixPath(relative).as_posix() != relative:
        raise RebuilderError(f"{label} is not one canonical Fleet-relative path")
    path = fleet_root.joinpath(*PurePosixPath(relative).parts)
    for ancestor in (path, *path.parents):
        metadata = ancestor.stat()
        if ancestor.is_symlink() or metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
            raise RebuilderError(f"{label} is not in a root-owned immutable runtime")
        if ancestor == fleet_root:
            return path
    raise RebuilderError(f"{label} escapes the protected Fleet root")


def _validate_signing_ledger_wrapper(policy: Mapping[str, Any]) -> Mapping[str, Any]:
    if set(policy) != {
        "contract_name", "contract_version", "state", "approval_policy", "credential_input", "replay_protection",
    } or policy.get("contract_name") != SIGNING_LEDGER_POLICY_CONTRACT \
            or type(policy.get("contract_version")) is not int or policy["contract_version"] != 1 \
            or policy.get("state") != "ready" \
            or policy.get("credential_input") != SIGNING_LEDGER_CREDENTIAL_INPUT:
        raise RebuilderError("separate binary-signing ledger policy is not exact and ready")
    binding = policy.get("approval_policy")
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"} \
            or binding.get("path") != APPROVAL_LEDGER_POLICY_PATH:
        raise RebuilderError("signing ledger lacks the exact approval-policy comparison binding")
    _sha256(binding.get("sha256"), "pinned approval-policy comparison digest")
    replay = policy.get("replay_protection")
    if not isinstance(replay, dict) or set(replay) != {"external_ledger"}:
        raise RebuilderError("binary-signing ledger replay fields are not exact")
    return binding


def _validate_ledger_separation(module, signing_policy, approval_policy, lock):
    """Compare actual pinned policy data, not a caller-asserted lane name."""
    if approval_policy.get("contract_name") != "fleet.android_preview12_two_green_release_approval_policy.v1" \
            or type(approval_policy.get("contract_version")) is not int \
            or approval_policy.get("contract_version") != 1 or approval_policy.get("state") != "ready":
        raise RebuilderError("pinned comparison is not the PR11 approval policy")
    output = approval_policy.get("output", {})
    if not isinstance(output, dict) \
            or output.get("contract_name") != "chummer.android.two-green-release-approval/v1" \
            or any(output.get(key) is not False for key in (
                "signing_authorized", "publication_authorized", "google_play_upload_authorized",
            )):
        raise RebuilderError("pinned comparison does not retain approval-only authority")
    replay = approval_policy.get("replay_protection")
    key = approval_policy.get("external_ed25519_key")
    attestation = lock.get("approval_authority")
    if not isinstance(replay, dict) or "external_ledger" not in replay \
            or not isinstance(key, dict) or key.get("configured") is not True \
            or not isinstance(attestation, dict):
        raise RebuilderError("pinned approval/signing comparison fields are invalid")
    try:
        signing = module.validate_ledger_policy(
            signing_policy["replay_protection"]["external_ledger"], require_configured=True
        )
        approval = module.validate_ledger_policy(replay["external_ledger"], require_configured=True)
    except module.LedgerError:
        raise RebuilderError("pinned lane ledger authority is invalid") from None
    if any(signing[name] == approval[name] for name in (
        "base_url", "expected_service_identity", "receipt_public_key_spki_sha256",
    )):
        raise RebuilderError("approval and binary-signing ledgers are not independently bound")
    approval_spki = _sha256(key.get("expected_public_key_spki_sha256"), "approval signing SPKI")
    try:
        approval_der = base64.b64decode(key.get("public_key_spki_der_base64"), validate=True)
    except (ValueError, TypeError):
        raise RebuilderError("pinned approval public key is invalid") from None
    if len(approval_der) != 44 or not approval_der.startswith(bytes.fromhex("302a300506032b6570032100")) \
            or hashlib.sha256(approval_der).hexdigest() != approval_spki:
        raise RebuilderError("pinned approval public key digest differs")
    attestation_spki = _sha256(attestation.get("public_key_spki_sha256"), "attestation signing SPKI")
    if attestation_spki == approval_spki:
        raise RebuilderError("builder and approval signing keys are not independent")
    if {signing["receipt_public_key_spki_sha256"], approval["receipt_public_key_spki_sha256"]} \
            & {approval_spki, attestation_spki}:
        raise RebuilderError("ledger receipt key is reused for approval or attestation signing")
    return signing


def load_reviewed_ledger(fleet_root: Path, lock: Mapping[str, Any], environment: Mapping[str, str]):
    """Load Draft #11's reviewed signed/no-redirect ledger after it is merged.

    The checked-in lock has null digests and therefore cannot reach this code.
    Both policy byte identities are transitively bound by the existing lock.
    No endpoint or response dialect is implemented by this module.
    """

    reservation = lock["reservation"]
    # The runtime root itself can be replaced through a writable/non-root
    # parent. Reuse the full ancestry check, not only the files below the root.
    fleet_root = _trusted_root(fleet_root, "Fleet signer runtime")
    if reservation.get("policy_path") != SIGNING_LEDGER_POLICY_PATH:
        raise RebuilderError("binary signing cannot use the approval-ledger policy")
    adapter = _immutable_ledger_path(fleet_root, reservation["adapter_path"], "reviewed approval-ledger adapter")
    policy_path = _immutable_ledger_path(fleet_root, reservation["policy_path"], "reviewed signing-ledger policy")
    adapter_raw = _stable_bytes(adapter, "reviewed approval-ledger adapter", 2 * 1024 * 1024)
    signing_policy, signing_raw = _json_file(policy_path, "reviewed signing-ledger policy", 256 * 1024)
    if hashlib.sha256(adapter_raw).hexdigest() != reservation["adapter_sha256"] \
            or hashlib.sha256(signing_raw).hexdigest() != reservation["policy_sha256"]:
        raise RebuilderError("reviewed durable approval-ledger bytes differ from lock")
    binding = _validate_signing_ledger_wrapper(signing_policy)
    approval_path = _immutable_ledger_path(fleet_root, binding["path"], "pinned comparison approval policy")
    approval_policy, approval_raw = _json_file(approval_path, "pinned comparison approval policy", 256 * 1024)
    if hashlib.sha256(approval_raw).hexdigest() != binding["sha256"]:
        raise RebuilderError("actual approval policy differs from signing comparison pin")
    module_name = "fleet_preview12_reviewed_ledger"
    module = types.ModuleType(module_name)
    module.__file__ = os.fspath(adapter)
    prior = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(compile(adapter_raw, os.fspath(adapter), "exec"), module.__dict__)
    finally:
        if prior is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = prior
    policy, policy_sha256 = module.load_policy(policy_path)
    if policy_sha256 != reservation["policy_sha256"]:
        raise RebuilderError("reviewed durable approval-ledger policy changed during load")
    ledger_policy = _validate_ledger_separation(module, policy, approval_policy, lock)
    # Never fall back to the approval lane's credential. The protected signing
    # job supplies its own capability; only the unchanged client's slot is mapped.
    if module.CREDENTIAL_ENV_NAME in environment:
        raise RebuilderError("approval-ledger credential must not enter the signing lane")
    token = environment.get(SIGNING_LEDGER_CREDENTIAL_INPUT)
    if environment is os.environ:
        os.environ.pop(SIGNING_LEDGER_CREDENTIAL_INPUT, None)
    client = module.DurableApprovalLedgerClient(ledger_policy, {module.CREDENTIAL_ENV_NAME: token})
    return module, client, policy_sha256


def reserve_signing_attempt(
    ledger, client, *, attempt_id: str, two_green_artifact_id: int,
    two_green_artifact_sha256: str, two_green_receipt_sha256: str,
    main_tree: str, policy_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reserve through the reviewed signed ledger before any signing-key read."""

    _sha256(attempt_id, "external signer attempt")
    subject = ledger.make_subject(
        approval_request_nonce=attempt_id,
        two_green_artifact_id=two_green_artifact_id,
        two_green_artifact_sha256=two_green_artifact_sha256,
        two_green_receipt_sha256=two_green_receipt_sha256,
        main_tree=main_tree,
        policy_sha256=policy_sha256,
        version_name=VERSION_NAME,
        version_code=VERSION_CODE,
    )
    reservation = client.reserve(subject)
    if reservation.get("receipt", {}).get("state") != "reserved":
        raise RebuilderError("external signing attempt was already terminal; key access is forbidden")
    return subject, reservation


def commit_signing_attempt(client, subject: Mapping[str, Any], reservation: Mapping[str, Any],
                           external_attestation: Path) -> dict[str, Any]:
    """Commit public v1 bytes; Draft #11 resolves lost commit responses by status."""

    raw = _stable_bytes(
        external_attestation, "external signer v1 attestation", 32 * 1024, owner_only=True
    )
    committed = client.commit(subject, raw, reservation)
    _validate_ledger_commit(committed, raw)
    return committed


def _validate_ledger_commit(committed: Mapping[str, Any], approval_raw: bytes) -> None:
    receipt = committed.get("receipt", {})
    approval = receipt.get("approval", {})
    expected_approval = {
        "sha256": hashlib.sha256(approval_raw).hexdigest(),
        "sizeBytes": len(approval_raw),
        "publicJsonBase64": base64.b64encode(approval_raw).decode("ascii"),
    }
    if receipt.get("state") != "committed" \
            or approval != expected_approval:
        raise RebuilderError("durable ledger did not commit exact external signer v1 bytes")


def _validate_authenticated_ledger_commit(
    ledger: Any, client: Any, response: Mapping[str, Any], subject: Mapping[str, Any],
    reservation: Mapping[str, Any], approval_raw: bytes,
) -> dict[str, Any]:
    """Revalidate a commit/status envelope and its semantic reservation continuity."""

    try:
        prior = ledger.validate_response(
            reservation, request=ledger._request("reserve", subject), policy=client.policy
        )
        prior_receipt = prior["receipt"]
        binding = {
            "reservationId": prior_receipt["reservationId"],
            "priorRevision": prior_receipt["revision"],
            "reservationReceiptSha256": prior["receiptSha256"],
        }
        operation = response.get("receipt", {}).get("operation")
        if operation not in {"commit", "status"}:
            raise RebuilderError("authenticated ledger response is not a commit recovery operation")
        approval = {
            "sha256": hashlib.sha256(approval_raw).hexdigest(),
            "sizeBytes": len(approval_raw),
            "publicJsonBase64": base64.b64encode(approval_raw).decode("ascii"),
        }
        request = ledger._request(
            operation, subject,
            approval=approval if operation == "commit" else None,
            prior_reservation=binding,
        )
        validated = ledger.validate_response(
            response, request=request, policy=client.policy
        )
        client._require_continuity(prior, validated, transition=True)
    except RebuilderError:
        raise
    except Exception as error:
        raise RebuilderError("durable ledger response failed reviewed adapter validation") from error
    if validated["receipt"].get("reservationId") != prior_receipt.get("reservationId") \
            or validated["receipt"].get("priorReservation") != binding:
        raise RebuilderError("durable ledger response changed reservation continuity")
    _validate_ledger_commit(validated, approval_raw)
    return dict(validated)


def _persist_authenticated_ledger_response(
    directory: Path, response: Mapping[str, Any], limit: int,
) -> Path:
    raw = _pretty_json(response)
    digest = hashlib.sha256(raw).hexdigest()
    path = directory / f"LEDGER_AUTHENTICATED_RESPONSE.{digest}.generated.json"
    _write_or_match(path, raw, "authenticated ledger response", limit)
    return path


def _select_authenticated_ledger_commit(
    directory: Path, ledger: Any, client: Any, fresh: Mapping[str, Any],
    subject: Mapping[str, Any], reservation: Mapping[str, Any], approval_raw: bytes,
    limit: int,
) -> dict[str, Any]:
    """Preserve every envelope while keeping the first authenticated audit binding stable."""

    validated_fresh = _validate_authenticated_ledger_commit(
        ledger, client, fresh, subject, reservation, approval_raw
    )
    _persist_authenticated_ledger_response(directory, validated_fresh, limit)
    selected_path = directory / "LEDGER_COMMIT.generated.json"
    if selected_path.exists():
        selected, _ = _json_file(
            selected_path, "selected ledger commit response", limit, owner_only=True
        )
        validated_selected = _validate_authenticated_ledger_commit(
            ledger, client, selected, subject, reservation, approval_raw
        )
    else:
        _write_or_match(
            selected_path, _pretty_json(validated_fresh),
            "selected ledger commit response", limit,
        )
        validated_selected = validated_fresh
    # Every retained history file is evidence labelled as authenticated.  Do
    # not promote a directory containing an injected or corrupt extra record,
    # even when the fresh and selected responses themselves are valid.
    for entry in sorted(os.scandir(directory), key=lambda item: item.name):
        match = LEDGER_RESPONSE_NAME.fullmatch(entry.name)
        if match is None:
            continue
        path = Path(entry.path)
        value, raw = _json_file(
            path, "authenticated ledger response history", limit, owner_only=True
        )
        if raw != _pretty_json(value) or hashlib.sha256(raw).hexdigest() != match.group(1):
            raise RebuilderError("authenticated ledger response history is not content-addressed")
        _validate_authenticated_ledger_commit(
            ledger, client, value, subject, reservation, approval_raw
        )
    return validated_selected


def require_rebuild_match(rebuilt_aab: Path, request: Mapping[str, Any], limit: int) -> dict[str, Any]:
    raw = _stable_bytes(rebuilt_aab, "independently rebuilt unsigned AAB", limit)
    expected = request["unsignedAab"]
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected["sha256"] or len(raw) != expected["sizeBytes"]:
        raise RebuilderError("independent unsigned AAB differs from producer")
    return {"sha256": actual, "sizeBytes": len(raw), "producerMatch": True}


def fleet_audit(lock: Mapping[str, Any], lock_raw: bytes, request_raw: bytes, graph_raw: bytes,
                rebuilt: Mapping[str, Any], signed: Mapping[str, Any], toolchain: Mapping[str, Any],
                ledger_commit: Mapping[str, Any], android_attestation: Path,
                external_attestation: Path) -> dict[str, Any]:
    ledger_receipt = ledger_commit.get("receipt", {})
    if ledger_receipt.get("state") != "committed" or ledger_commit.get("signature") is None:
        raise RebuilderError("Fleet audit requires the reviewed ledger's signed committed receipt")
    value = {
        "contract_name": FLEET_AUDIT_CONTRACT,
        "status": "verified",
        "release": dict(lock["release"]),
        "android_authority": {"commit": lock["android_authority"]["commit"], "tree": lock["android_authority"]["tree"]},
        "producer": {"request_sha256": hashlib.sha256(request_raw).hexdigest(),
                     "source_graph_sha256": hashlib.sha256(graph_raw).hexdigest(),
                     "unsigned_aab_sha256": rebuilt["sha256"]},
        "independent_rebuild": dict(rebuilt),
        "toolchain": dict(toolchain),
        "durable_ledger": {
            "response_sha256": hashlib.sha256(_canonical_json(ledger_commit)).hexdigest(),
            "receipt_sha256": ledger_commit.get("receiptSha256"),
            "reservation_id_sha256": hashlib.sha256(
                str(ledger_receipt.get("reservationId") or "").encode("utf-8")
            ).hexdigest(),
            "state": "committed",
            "signed_receipt_verified_by_reviewed_adapter": True,
        },
        "signed_aab": dict(signed),
        "android_v2_attestation": {"contract_name": ANDROID_ATTESTATION_CONTRACT,
                                   "sha256": _sha256_file(android_attestation, "Android v2 attestation", 8 * 1024 * 1024,
                                                          owner_only=True)},
        "external_signer_v1_attestation": {
            "contract_name": EXTERNAL_SIGNER_ATTESTATION_CONTRACT,
            "sha256": _sha256_file(
                external_attestation, "external signer v1 attestation", 32 * 1024, owner_only=True
            ),
        },
        "fleet_lock_sha256": hashlib.sha256(lock_raw).hexdigest(),
        "signed_content_handoff_performed": False,
        "google_play_upload_performed": False,
        "publication_performed": False,
    }
    forbidden = ("password", "private_key", "keystore", "token", "authorization", "endpoint")
    serialized = _canonical_json(value).decode("utf-8").lower()
    if any(name in serialized for name in forbidden):
        raise RebuilderError("Fleet audit contains a forbidden secret-bearing field")
    return value


def _copy_protected(source: Path, destination: Path, label: str, limit: int) -> None:
    raw = _stable_bytes(source, label, limit, owner_only=True)
    _write_exclusive(destination, raw)


def _validate_authority_feed_paths(authority_root: Path, owner_feed: Path) -> None:
    """Match Android's existing owner_feed.parent routing, not a second verifier."""
    for path in (authority_root, owner_feed):
        try:
            valid = isinstance(path, Path) and path.is_absolute() and not path.is_symlink() \
                and path.is_dir() and path.resolve(strict=True) == path
        except (OSError, RuntimeError):
            valid = False
        if not valid:
            raise RebuilderError("package authority root and feed must be canonical existing directories")
    if owner_feed.parent != authority_root:
        raise RebuilderError("package authority root must equal the owner feed parent")


def _validate_offline_feed(path: Path | None, *separate_roots: Path, kind: str) -> None:
    """Admit transport only; Android owns input selection and byte validation."""
    if path is None:
        return
    try:
        if not isinstance(path, Path) or not path.is_absolute() \
                or len(os.fspath(path)) > 4095 or not re.fullmatch(r"/[A-Za-z0-9._/-]+", os.fspath(path)) \
                or path.resolve(strict=True) != path:
            raise ValueError
        metadata = path.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid() \
                or stat.S_IMODE(metadata.st_mode) & 0o022 \
                or any(not stat.S_ISDIR(parent.lstat().st_mode) for parent in path.parents):
            raise ValueError
        for root in separate_roots:
            root = root.resolve(strict=False)
            if path == root or path in root.parents or root in path.parents:
                raise ValueError
    except (OSError, RuntimeError, ValueError):
        raise RebuilderError(f"offline {kind} feed must be a safe canonical owned directory disjoint from rebuild inputs and outputs") from None


def _validate_offline_nuget_feed(path: Path | None, *separate_roots: Path) -> None:
    _validate_offline_feed(path, *separate_roots, kind="NuGet")


def _validate_offline_feeds(nuget: Path | None, aar: Path | None, *separate_roots: Path) -> None:
    _validate_offline_nuget_feed(nuget, *separate_roots)
    # Admission above precedes the symmetric ancestor/equality check against AARs.
    _validate_offline_feed(aar, *separate_roots, *((nuget,) if nuget is not None else ()), kind="AAR")


def _require_offline_feed_consumer(lock: Mapping[str, Any], workspace: Path, kind: str) -> None:
    """Check the already-bound script's capability without creating authority."""
    binding = lock["android_authority"]["build_script"]
    script = workspace / "chummer-android/scripts/build-release.sh"
    raw = _stable_bytes(script, f"Android offline {kind} build script", 8 * 1024 * 1024)
    if binding["path"] != "scripts/build-release.sh" or hashlib.sha256(raw).hexdigest() != binding["sha256"]:
        raise RebuilderError(f"Android offline {kind} build script bytes differ from lock")
    variable = f"CHUMMER_ANDROID_RELEASE_OFFLINE_{kind.upper()}_FEED".encode("ascii")
    reference = rb"\$(?:" + variable + rb"\b|\{" + variable + rb"[}:])"
    # A capability marker, not a shell execution proof: ignore comments, literal
    # single quotes and escaped dollars while recognizing ordinary expansions.
    tokens = re.finditer(
        rb"'[^']*'|\\.|\#[^\n]*|(?P<quoted>\"(?:[^\"\\]|\\.)*\")|(?P<reference>" + reference + rb")", raw)
    if not any(token.lastgroup == "reference" or (
        token.lastgroup == "quoted" and re.search(reference, re.sub(rb"\\.", b"", token.group()))
    ) for token in tokens):
        raise RebuilderError(f"bound Android build script does not support offline {kind} input")


def _require_offline_nuget_consumer(lock: Mapping[str, Any], workspace: Path) -> None:
    _require_offline_feed_consumer(lock, workspace, "NuGet")


def _require_offline_aar_consumer(lock: Mapping[str, Any], workspace: Path) -> None:
    _require_offline_feed_consumer(lock, workspace, "AAR")


# Compatibility only, never source admission or a change to an active lock.
# The checked-in historical script predates offline source-test inputs. The
# reviewed successor must use exactly this stdlib-only Android capture helper.
# Unknown scripts require a reviewed capability entry, never substring probing.
RELEASE_TEST_CONSUMERS = {
    "61ea9fa04338889f78e26de26a90b392c5f16def2a4150a64a94e9d4fadd5ca9": None,
    "fc8b6e637ba3220e4e9c5ea55c5e4dcca6cb26c196eaa75f6d19e91a87ed3db6":
        "a295c226850edda9ce3a57a3c43690188e271b3059c33dd14abca04f65ef4bcf",
    "4e29b255aae29d30f1b8ddb7fc96947cf851df2c661fa820031bd5db2604f3f6":
        "a295c226850edda9ce3a57a3c43690188e271b3059c33dd14abca04f65ef4bcf",
}
TEST_ORACLE_REPOSITORY = "https://github.com/ArchonMegalon/chummer5a.git"
TEST_ORACLE_FILE_COUNT = 250_000


def _release_test_capability(lock: Mapping[str, Any]) -> str | None:
    binding = lock["android_authority"]["build_script"]
    if binding["path"] != "scripts/build-release.sh" or binding["sha256"] not in RELEASE_TEST_CONSUMERS:
        raise RebuilderError("Android release source-test consumer capability is not admitted")
    return RELEASE_TEST_CONSUMERS[binding["sha256"]]


def _admit_release_test_inputs(lock: Mapping[str, Any], bootstrap: Path | None, wheels: Path | None,
                              oracle: Path | None, *separate_roots: Path) -> None:
    required = _release_test_capability(lock) is not None
    paths = (bootstrap, wheels, oracle)
    if not required:
        if any(path is not None for path in paths):
            raise RebuilderError("historical Android consumer does not accept source-test inputs")
        return
    if any(path is None for path in paths):
        raise RebuilderError("Android source tests require explicit bootstrap, wheelhouse and oracle inputs")
    for index, path in enumerate(paths):
        _validate_offline_feed(path, *separate_roots, *paths[:index], kind="source-test")


def _load_release_test_capture(lock: Mapping[str, Any], android: Path) -> Any:
    """Import only the exact reviewed stdlib helper after full source checks.

    Never install anything in Fleet, alter sys.path or import the test suite.
    The requirements/workflow sit outside scripts/eng; check their Git bytes too.
    """
    helper_digest = _release_test_capability(lock)
    commit = lock["android_authority"]["commit"]
    _preserved_git_storage(android, REPOSITORIES["chummer-android"][2])
    if _offline_git(["-C", str(android), "rev-parse", "HEAD"], timeout=30) != commit:
        raise RebuilderError("source-test Android checkout is not the admitted commit")
    _validate_android_consumer_inputs(android, commit)
    for relative in ("scripts/build-release.sh", "scripts/run_release_source_tests.py",
                     "eng/release-test-bootstrap.lock.json", "tests/requirements-ci.txt",
                     ".github/workflows/api36-editing-e2e.yml"):
        raw = _stable_bytes(android / relative, "Android source-test authority", 1024 * 1024)
        tracked = _offline_git(["-C", str(android), "show", f"{commit}:{relative}"], timeout=30, binary=True)
        if raw != tracked:
            raise RebuilderError("Android source-test authority differs from tracked bytes")
        if relative == "scripts/build-release.sh" and hashlib.sha256(raw).hexdigest() != lock["android_authority"]["build_script"]["sha256"]:
            raise RebuilderError("Android source-test build script differs from admitted capability")
    path = android / "scripts/run_release_source_tests.py"
    helper = _stable_bytes(path, "Android source-test capture helper", 1024 * 1024)
    if hashlib.sha256(helper).hexdigest() != helper_digest:
        raise RebuilderError("Android source-test capture helper differs from admitted capability")
    module = types.ModuleType("fleet_reviewed_android_test_capture")
    module.__file__ = str(path)
    exec(compile(helper, str(path), "exec"), module.__dict__)
    return module


def _oracle_inventory(root: Path) -> dict[str, os.stat_result]:
    """No links, devices, shared objects or writable-by-other entries, before Git."""
    entries, total = {}, 0
    for base, directories, files in os.walk(root, followlinks=False):
        for name in (*directories, *files):
            path = Path(base) / name
            info = path.lstat()
            if info.st_uid != os.getuid() or info.st_mode & 0o022 \
                    or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) \
                    or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1):
                raise RebuilderError("test oracle contains unsafe or shared entries")
            if len(entries) >= TEST_ORACLE_FILE_COUNT:
                raise RebuilderError("test oracle inventory exceeds its limit")
            entries[path.relative_to(root).as_posix()] = info
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
                if info.st_size > OFFLINE_ORACLE_FILE_BYTES or total > OFFLINE_ORACLE_TOTAL_BYTES:
                    raise RebuilderError("test oracle bytes exceed transport limits")
    return entries


def _verify_test_oracle(module: Any, android: Path, oracle: Path) -> str:
    _oracle_inventory(oracle)
    _preserved_git_storage(oracle, TEST_ORACLE_REPOSITORY)
    workflow = module.read_stable(android / ".github/workflows/api36-editing-e2e.yml").decode("utf-8")
    pins = re.findall(r"repository: ArchonMegalon/chummer5a\n\s+ref: ([0-9a-f]{40})\n", workflow)
    if len(pins) != 1:
        raise RebuilderError("test oracle workflow pin is missing or ambiguous")
    def read_git(arguments: list[str], **options: Any) -> bytes | str:
        # Status must not refresh the supplied index while checking identity.
        return _offline_git(["--no-optional-locks", *arguments], **options)
    commit = read_git(["-C", str(oracle), "rev-parse", "HEAD"], timeout=30)
    if commit != pins[0]:
        raise RebuilderError("test oracle does not match the Android workflow commit")
    for name in ("Chummer", "Plugins/ChummerHub.Client/UI", "Translator", "CrashHandler", "ChummerDataViewer"):
        if not (oracle / name).is_dir():
            raise RebuilderError("test oracle is missing an Android inventory root")
    if read_git(["-C", str(oracle), "status", "--porcelain", "--untracked-files=all"], timeout=30):
        raise RebuilderError("test oracle checkout is not clean")
    _preserved_repository_bytes(oracle, commit, git=read_git, owner_uid=os.getuid(),
                                repository=TEST_ORACLE_REPOSITORY)
    reachable = read_git(["-C", str(oracle), "rev-list", "--objects", "--no-object-names", commit], timeout=900)
    stored = read_git(["-C", str(oracle), "cat-file", "--batch-all-objects", "--batch-check=%(objectname)"], timeout=900)
    wanted, actual = reachable.splitlines(), stored.splitlines()
    if not wanted or any(not HEX40.fullmatch(value) for value in (*wanted, *actual)) \
            or set(wanted) != set(actual):
        raise RebuilderError("test oracle object storage is not the exact reachable commit closure")
    return commit


def _stage_test_oracle(module: Any, android: Path, source: Path, destination: Path) -> os.stat_result:
    """Copy only bounded ordinary Git object files into a fresh helper-free repo.

    No clone/file-protocol exemption, bundles, hooks, index, caller config or
    worktree bytes are copied. Git materializes the exact verified object tree.
    Filesystem quota remains the enclosing builder's responsibility.
    """
    commit = _verify_test_oracle(module, android, source)
    before = _oracle_inventory(source)
    destination.mkdir(mode=0o700)
    identity = destination.lstat()
    try:
        _offline_git(["init", "--quiet", "--template=", str(destination)], timeout=30)
        objects = []
        for relative, info in before.items():
            if not relative.startswith(".git/objects/") or not stat.S_ISREG(info.st_mode):
                continue
            name = relative.removeprefix(".git/objects/")
            if name == "info/packs" or re.fullmatch(r"pack/pack-[0-9a-f]{40}\.(?:rev|bitmap)", name):
                continue  # Pack advertisement/acceleration indexes are not source objects.
            if not re.fullmatch(r"(?:[0-9a-f]{2}/[0-9a-f]{38}|pack/pack-[0-9a-f]{40}\.(?:pack|idx))", name):
                raise RebuilderError("test oracle has unsupported Git object storage")
            objects.append((relative, info))
        if not objects:
            raise RebuilderError("test oracle has no independent objects")
        for relative, info in objects:
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with output.open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                _copy_offline_input(source / relative, info, stream, OFFLINE_ORACLE_FILE_BYTES)
        _offline_git(["-C", str(destination), "fsck", "--full", "--strict", "--no-reflogs", commit], timeout=900)
        _offline_git(["-C", str(destination), "remote", "add", "origin", TEST_ORACLE_REPOSITORY], timeout=30)
        _offline_git(["-C", str(destination), "checkout", "--quiet", "--detach", commit], timeout=900)
        if _verify_test_oracle(module, android, destination) != commit \
                or _verify_test_oracle(module, android, source) != commit \
                or {name: _file_identity(info) for name, info in before.items()} != \
                   {name: _file_identity(info) for name, info in _oracle_inventory(source).items()}:
            raise RebuilderError("test oracle changed during staging")
        return identity
    except BaseException:
        _remove_owned_directory(destination, identity)
        raise


@contextmanager
def _staged_release_test_inputs(lock: Mapping[str, Any], workspace: Path, scratch: Path,
                                bootstrap: Path | None, wheels: Path | None, oracle: Path | None):
    if _release_test_capability(lock) is None:
        yield {}
        return
    module = _load_release_test_capture(lock, workspace / "chummer-android")
    stage = Path(tempfile.mkdtemp(prefix=".release-test-inputs-", dir=scratch))
    stage_identity, oracle_identity = stage.lstat(), None
    destination = workspace / "chummer5a"
    child_started = False
    try:
        # Android owns lock semantics and byte limits; Fleet only stages data.
        for path in (bootstrap, wheels, oracle):
            module.directory(path)
        _lock, inputs, _requirements = module.capture_inputs(workspace / "chummer-android", bootstrap, wheels)
        for name in ("bootstrap", "wheels"):
            (stage / name).mkdir(mode=0o700)
        for name, raw in inputs.items():
            _write_exclusive(stage / name, raw)
        oracle_identity = _stage_test_oracle(module, workspace / "chummer-android", oracle, destination)
        child_started = True
        yield {"CHUMMER_ANDROID_RELEASE_TEST_BOOTSTRAP_DIR": str(stage / "bootstrap"),
               "CHUMMER_ANDROID_RELEASE_TEST_WHEELHOUSE": str(stage / "wheels")}
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        if child_started:
            raise  # Preserve build/timeout classification; this is not bad input.
        raise RebuilderError("offline Android source-test input admission or staging failed") from None
    finally:
        try:
            if oracle_identity is not None:
                _remove_owned_directory(destination, oracle_identity)
        finally:
            _remove_owned_directory(stage, stage_identity)


class _RebuildToolchainInputs:
    """Local input snapshots, not runtime authority or a transported dialect."""

    __slots__ = ("paths", "bindings")

    def __init__(self, installed_closure_receipt: Path, java_tool_observation: Path) -> None:
        self.paths = (installed_closure_receipt, java_tool_observation)
        self.bindings = self._capture()
        if self.paths[0] == self.paths[1] or self.bindings[0][0][:2] == self.bindings[1][0][:2]:
            raise RebuilderError("installed closure receipt and Java observation must be separate files")

    def _capture(self) -> tuple[tuple[tuple[int, ...], str], ...]:
        result = []
        for path, label in zip(self.paths, ("installed closure receipt", "Java tool observation")):
            # Owner-only canonical admission and bounded reads precede hashing;
            # retain identity as well as bytes to reject same-byte replacement.
            try:
                metadata = path.lstat()
                before = (*_file_identity(metadata), metadata.st_gid, metadata.st_nlink)
                digest = _sha256_file(path, label, 8 * 1024 * 1024, owner_only=True)
                metadata = path.lstat()
                after = (*_file_identity(metadata), metadata.st_gid, metadata.st_nlink)
            except OSError:
                raise RebuilderError("rebuild toolchain input is unavailable") from None
            if after != before:
                raise RebuilderError("rebuild toolchain input changed while being captured")
            result.append((before, digest))
        return tuple(result)

    def assert_exact(self, installed_closure_receipt: Path, java_tool_observation: Path) -> None:
        if self.paths != (installed_closure_receipt, java_tool_observation) or self._capture() != self.bindings:
            raise RebuilderError("rebuild toolchain input differs from the admitted snapshot")

    def validate_observation(self, android: Any, dotnet_root: Path, java_root: Path) -> None:
        self.assert_exact(*self.paths)
        observed = android._load_trusted_java_toolchain(self.paths[1])
        if observed["observationSha256"] != self.bindings[1][1] \
                or observed["tools"]["java"] != java_root / "bin/java" \
                or observed["dotnet"] != dotnet_root / "dotnet":
            raise RebuilderError("rebuild Java observation differs from admitted bytes or tool roots")
        self.assert_exact(*self.paths)


def _contextual_rebuild_observation(
    lock: Mapping[str, Any], android_root: Path, original: _RebuildToolchainInputs,
    dotnet_root: Path, java_root: Path, output: Path, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> _RebuildToolchainInputs:
    """Measure the canonical observation in the build's actual cwd, never chdir.

    The original remains a fenced historical input. Only dotnet's full --info
    output digest may change with global.json's absolute staged pathname. Both
    generation and live version verification use the qualified Android CLI.
    This stage-local file follows build-input cleanup; it is not an eighth
    handoff member or independently retained protected validation evidence.
    """
    binding = lock["android_authority"]["attestation_consumer"]
    helper = android_root / binding["path"]
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
                   "CHUMMER_RELEASE_REPO_ROOT": os.fspath(android_root)}
    contextual: _RebuildToolchainInputs | None = None

    def guard() -> None:
        original.assert_exact(*original.paths)
        if contextual is not None:
            contextual.assert_exact(*contextual.paths)
        try:
            canonical = android_root.resolve(strict=True) == android_root and not android_root.is_symlink()
        except OSError:
            canonical = False
        if not canonical:
            raise RebuilderError("contextual Android root is not canonical")
        _validate_android_consumer_inputs(android_root, lock["android_authority"]["commit"])
        if _sha256_file(helper, "contextual Android observer", 8 * 1024 * 1024) != binding["sha256"]:
            raise RebuilderError("contextual Android observer differs from qualified bytes")

    def invoke(action: str, arguments: list[str]) -> dict[str, Any]:
        guard()
        try:
            completed = runner(
                ["/usr/bin/python3", "-I", "-B", "-S", os.fspath(helper), action, *arguments],
                cwd=android_root, env=environment, stdin=subprocess.DEVNULL, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
            )
        except (OSError, subprocess.SubprocessError):
            raise RebuilderError("contextual Android tool observation failed") from None
        finally:
            guard()
        if completed.returncode != 0 or not isinstance(completed.stdout, bytes) \
                or not 0 < len(completed.stdout) <= 64 * 1024:
            raise RebuilderError("contextual Android tool observation failed")
        value = _strict_json(completed.stdout, "contextual Android observation result")
        if value.get("status") != "pass" or value.get("signingAuthorized") is not False \
                or value.get("publicationAuthorized") is not False \
                or value.get("authorityClass") != "non_authoritative_local_unsigned_preparation":
            raise RebuilderError("contextual Android observation result differs")
        return value

    generated = invoke("observe-toolchain", ["--java-sdk", os.fspath(java_root),
        "--dotnet", os.fspath(dotnet_root / "dotnet"), "--output", os.fspath(output)])
    contextual = _RebuildToolchainInputs(original.paths[0], output)
    verified = invoke("verify-toolchain", ["--authority", os.fspath(output)])
    contextual.assert_exact(*contextual.paths)
    if any(value.get("observationSha256") != contextual.bindings[1][1]
           for value in (generated, verified)) \
            or verified.get("javaSdkRoot") != os.fspath(java_root) \
            or verified.get("dotnetPath") != os.fspath(dotnet_root / "dotnet"):
        raise RebuilderError("contextual observation differs from measured bytes or tool roots")
    previous, previous_raw = _json_file(original.paths[1], "original Java observation", 8 * 1024 * 1024,
                                        owner_only=True)
    current, _ = _json_file(output, "contextual Java observation", 8 * 1024 * 1024, owner_only=True)
    if previous_raw != _pretty_json(previous):
        raise RebuilderError("original Java observation is not canonical")
    if not isinstance(current.get("dotnet"), dict):
        raise RebuilderError("contextual dotnet claim is missing")
    if current.get("javaSdkRoot") != os.fspath(java_root) \
            or current["dotnet"].get("absolutePath") != os.fspath(dotnet_root / "dotnet") \
            or any(current.get(name) is not False for name in (
                "signingAuthorized", "publicationAuthorized", "androidSdkBound")) \
            or current.get("externalSignerMustBindFullJdkDotnetAndroidSdkClosure") is not True:
        raise RebuilderError("contextual observation roots or authority posture differ")
    for prefix, name in (("javaSdk", "java"), ("dotnetSdk", "dotnet")):
        expected = lock["toolchain"][name]
        if _canonical_json([current.get(prefix + suffix) for suffix in
                            ("TreeSha256", "TreeFileCount", "TreeSizeBytes")]) != _canonical_json(
                [expected["tree_sha256"], expected["file_count"], expected["size_bytes"]]):
            raise RebuilderError("contextual observation closure differs from lock")
    for value in (previous, current):
        claim = value.get("dotnet")
        if not isinstance(claim, dict):
            raise RebuilderError("contextual dotnet claim is missing")
        _sha256(claim.get("versionOutputSha256"), "dotnet version observation")
        del claim["versionOutputSha256"]
    # Canonical byte comparison is type-aware: False != 0 and 1 != 1.0 here.
    if _canonical_json(previous) != _canonical_json(current):
        raise RebuilderError("contextual observation changed non-context toolchain claims")
    guard()
    contextual.assert_exact(*contextual.paths)
    return contextual


def _run_independent_rebuild(
    lock: Mapping[str, Any],
    workspace: Path,
    two_green_receipt: Path,
    approval: Path,
    package_authority: Path,
    authority_root: Path,
    owner_feed: Path,
    ui_authority_receipt: Path,
    java_tool_observation: Path,
    installed_closure_receipt: Path,
    bundletool: Path,
    upload_certificate: Path,
    dotnet_root: Path,
    java_root: Path,
    android_sdk_root: Path,
    build_input_root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    offline_nuget_feed: Path | None = None,
    offline_aar_feed: Path | None = None,
    toolchain_inputs: _RebuildToolchainInputs | None = None,
    test_bootstrap_dir: Path | None = None,
    test_wheelhouse: Path | None = None,
    test_oracle_root: Path | None = None,
) -> tuple[Path, Path]:
    _validate_authority_feed_paths(authority_root, owner_feed)
    _validate_offline_feeds(
        offline_nuget_feed, offline_aar_feed, authority_root, workspace, build_input_root, package_authority,
        ui_authority_receipt, java_tool_observation, installed_closure_receipt,
        dotnet_root, java_root, android_sdk_root,
        two_green_receipt, approval, bundletool, upload_certificate,
    )
    if offline_nuget_feed is not None:
        _require_offline_nuget_consumer(lock, workspace)
    if offline_aar_feed is not None:
        _require_offline_aar_consumer(lock, workspace)
    _admit_release_test_inputs(lock, test_bootstrap_dir, test_wheelhouse, test_oracle_root,
        authority_root, workspace, build_input_root, package_authority, ui_authority_receipt,
        java_tool_observation, installed_closure_receipt, dotnet_root, java_root, android_sdk_root,
        two_green_receipt, approval, bundletool, upload_certificate,
        *(path for path in (offline_nuget_feed, offline_aar_feed) if path is not None))
    if toolchain_inputs is None:
        toolchain_inputs = _RebuildToolchainInputs(installed_closure_receipt, java_tool_observation)
    toolchain_inputs.assert_exact(installed_closure_receipt, java_tool_observation)
    build_input_root.mkdir(mode=0o700)
    contextual = _contextual_rebuild_observation(
        lock, workspace / "chummer-android", toolchain_inputs, dotnet_root, java_root,
        build_input_root / "java-tool-observation.json", runner=runner,
    )
    (build_input_root / "nuget-packages").mkdir(mode=0o700)
    (build_input_root / "unsigned-child-home").mkdir(mode=0o700)
    _copy_protected(two_green_receipt, build_input_root / "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json",
                    "two-green receipt", lock["limits"]["json_bytes"])
    _copy_protected(approval, build_input_root / "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json",
                    "two-green approval", lock["limits"]["json_bytes"])
    graph_rows = validate_source_graph(
        _json_file(
            workspace.parent / "producer-source-graph.json",
            "staged producer source graph",
            lock["limits"]["json_bytes"],
            owner_only=True,
        )[0]
    )
    environment = {
        "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": os.fspath(build_input_root / "unsigned-child-home"),
        "CHUMMER_COMPLETE_ROOT": os.fspath(workspace),
        "CHUMMER_ANDROID_EXPECTED_VERSION_NAME": VERSION_NAME,
        "CHUMMER_ANDROID_EXPECTED_VERSION_CODE": str(VERSION_CODE),
        "CHUMMER_ANDROID_RELEASE_TOOLCHAIN_AUTHORITY": os.fspath(contextual.paths[1]),
        "CHUMMER_ANDROID_RELEASE_PACKAGE_AUTHORITY": os.fspath(package_authority),
        "CHUMMER_CURRENT_UI_PACKAGE_AUTHORITY_RECEIPT": os.fspath(ui_authority_receipt),
        "CHUMMER_INTERNAL_PHONE_BETA_PACKAGE_FEED": os.fspath(owner_feed),
        "CHUMMER_ANDROID_UPLOAD_CERTIFICATE_PATH": os.fspath(upload_certificate),
        "CHUMMER_BUNDLETOOL_JAR": os.fspath(bundletool),
        "NUGET_PACKAGES": os.fspath(build_input_root / "nuget-packages"),
        "AndroidSdkDirectory": os.fspath(android_sdk_root),
        "JavaSdkDirectory": os.fspath(java_root),
        "CHUMMER_DOTNET": os.fspath(dotnet_root / "dotnet"),
        **{REVISION_VARIABLES[name]: row["commit"] for name, row in graph_rows.items()},
    }
    if offline_nuget_feed is not None:
        environment["CHUMMER_ANDROID_RELEASE_OFFLINE_NUGET_FEED"] = os.fspath(offline_nuget_feed)
    if offline_aar_feed is not None:
        environment["CHUMMER_ANDROID_RELEASE_OFFLINE_AAR_FEED"] = os.fspath(offline_aar_feed)
    build_script = workspace / "chummer-android/scripts/build-release.sh"
    stdout_path, stderr_path = build_input_root / "build.stdout", build_input_root / "build.stderr"
    with _staged_release_test_inputs(lock, workspace, build_input_root,
            test_bootstrap_dir, test_wheelhouse, test_oracle_root) as test_environment, \
            stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        environment.update(test_environment)
        toolchain_inputs.assert_exact(installed_closure_receipt, java_tool_observation)
        contextual.assert_exact(*contextual.paths)
        try:
            completed = runner(
                ["/bin/bash", "-p", os.fspath(build_script)], cwd=workspace / "chummer-android",
                env=environment, check=False, stdout=stdout, stderr=stderr,
                timeout=lock["limits"]["build_timeout_seconds"],
            )
        except (OSError, subprocess.SubprocessError):
            raise RebuilderError("independent Android unsigned rebuild process failed") from None
        finally:
            toolchain_inputs.assert_exact(installed_closure_receipt, java_tool_observation)
            contextual.assert_exact(*contextual.paths)
    # build-release intentionally exits 3 after creating an unsigned external-
    # signer handoff.  Any other result is either a failed build or an
    # unauthorized semantic change to the Android build boundary.
    if completed.returncode != 3:
        raise RebuilderError("independent Android unsigned rebuild failed")
    rebuilt_aab = build_input_root / f"artifacts/chummer-android-{VERSION_NAME}-unsigned.aab"
    rebuilt_graph = build_input_root / f"artifacts/chummer-android-{VERSION_NAME}-source-graph.json"
    _stable_bytes(rebuilt_aab, "independently rebuilt unsigned AAB", lock["limits"]["aab_bytes"])
    _stable_bytes(rebuilt_graph, "independently rebuilt source graph", lock["limits"]["json_bytes"], owner_only=True)
    return rebuilt_aab, rebuilt_graph


def prepare_rebuild_handoff(
    lock_path: Path, external_request: Path, producer_unsigned_aab: Path,
    producer_source_graph: Path, producer_sidecar: Path, two_green_receipt: Path,
    approval: Path, package_authority: Path, authority_root: Path, owner_feed: Path,
    ui_authority_receipt: Path, java_tool_observation: Path, installed_closure_receipt: Path, bundletool: Path,
    upload_certificate: Path, dotnet_root: Path, java_root: Path,
    android_sdk_root: Path, output_dir: Path, reported_builder_image: str, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    offline_source_manifest: Path | None = None,
    offline_nuget_feed: Path | None = None,
    offline_aar_feed: Path | None = None,
    test_bootstrap_dir: Path | None = None,
    test_wheelhouse: Path | None = None,
    test_oracle_root: Path | None = None,
) -> dict[str, Any]:
    """Run the secret-free rebuild stage in a job with no credential mounts."""

    _validate_authority_feed_paths(authority_root, owner_feed)
    _validate_offline_feeds(
        offline_nuget_feed, offline_aar_feed, authority_root, output_dir, package_authority,
        ui_authority_receipt, java_tool_observation, installed_closure_receipt,
        dotnet_root, java_root, android_sdk_root,
        lock_path, external_request, producer_unsigned_aab, producer_source_graph, producer_sidecar,
        two_green_receipt, approval, bundletool, upload_certificate,
        *((offline_source_manifest,) if offline_source_manifest is not None else ()),
    )
    lock, lock_raw = load_lock(lock_path)
    failures = validate_unsigned_rebuild_lock(lock, lock_raw, reported_builder_image)
    if failures:
        raise RebuilderError("; ".join(failures))
    _admit_release_test_inputs(lock, test_bootstrap_dir, test_wheelhouse, test_oracle_root,
        authority_root, output_dir, package_authority, ui_authority_receipt, java_tool_observation,
        installed_closure_receipt, dotnet_root, java_root, android_sdk_root, lock_path, external_request,
        producer_unsigned_aab, producer_source_graph, producer_sidecar, two_green_receipt, approval,
        bundletool, upload_certificate,
        *(path for path in (offline_source_manifest, offline_nuget_feed, offline_aar_feed) if path is not None))
    toolchain_inputs = _RebuildToolchainInputs(installed_closure_receipt, java_tool_observation)
    if toolchain_inputs.bindings[0][1] != lock["toolchain"]["installed_closure_receipt_sha256"]:
        raise RebuilderError("installed toolchain closure receipt differs from lock")
    request, graph = validate_external_request(
        external_request, producer_source_graph, lock["limits"]["json_bytes"]
    )
    rows = validate_source_graph(graph)
    android_row = rows["chummer-android"]
    authority = lock["android_authority"]
    if (android_row["commit"], android_row["tree"], android_row["repository"]) != (
        authority["commit"], authority["tree"], authority["repository"]
    ):
        raise RebuilderError("producer source graph is not the qualified Preview12 Android authority")
    producer_raw = _stable_bytes(
        producer_unsigned_aab, "producer unsigned AAB", lock["limits"]["aab_bytes"]
    )
    if hashlib.sha256(producer_raw).hexdigest() != request["unsignedAab"]["sha256"] \
            or len(producer_raw) != request["unsignedAab"]["sizeBytes"]:
        raise RebuilderError("producer unsigned AAB differs from external signer request")
    graph_raw = _stable_bytes(
        producer_source_graph, "producer source graph", lock["limits"]["json_bytes"], owner_only=True
    )
    request_raw = _stable_bytes(
        external_request, "external signer request", lock["limits"]["json_bytes"], owner_only=True
    )
    sidecar_raw = _stable_bytes(producer_sidecar, "producer build sidecar", 64 * 1024, owner_only=True)
    if hashlib.sha256(sidecar_raw).hexdigest() != request["buildSidecar"]["sha256"]:
        raise RebuilderError("producer build sidecar differs from external signer request")
    if not output_dir.is_absolute() or output_dir.exists() or output_dir.is_symlink() \
            or output_dir.parent.is_symlink() or output_dir.parent.resolve(strict=True) != output_dir.parent \
            or output_dir.parent.stat().st_uid != os.getuid() \
            or stat.S_IMODE(output_dir.parent.stat().st_mode) & 0o077:
        raise RebuilderError("rebuild handoff must be a new path below one owner-only directory")
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    stage.chmod(0o700)
    moved = False
    try:
        source_graph_copy = stage / "producer-source-graph.json"
        _write_exclusive(source_graph_copy, graph_raw)
        workspace = stage / "workspace"
        if offline_source_manifest is None:
            checkout_source_graph(graph, workspace, runner=runner, timeout=lock["limits"]["git_timeout_seconds"])
        else:
            checkout_source_graph_from_bundles(
                graph, workspace, offline_source_manifest, timeout=lock["limits"]["git_timeout_seconds"],
            )
        android = validate_android_consumer(workspace / "chummer-android", lock)
        if offline_nuget_feed is not None:
            _require_offline_nuget_consumer(lock, workspace)
        if offline_aar_feed is not None:
            _require_offline_aar_consumer(lock, workspace)
        toolchain = verify_unsigned_toolchain(
            lock, dotnet_root, java_root, android_sdk_root,
            bundletool, installed_closure_receipt, reported_builder_image, runner=runner,
        )
        qualification = android.VERIFY.verify_release_eligibility(
            two_green_receipt, approval, android_root=workspace / "chummer-android",
            expected_version_name=VERSION_NAME, expected_version_code=VERSION_CODE,
            source_graph_path=source_graph_copy,
        )
        android._sidecar_claims(producer_sidecar, producer_unsigned_aab, producer_source_graph)
        toolchain_inputs.assert_exact(installed_closure_receipt, java_tool_observation)
        rebuilt_aab, rebuilt_graph = _run_independent_rebuild(
            lock, workspace, two_green_receipt, approval, package_authority, authority_root, owner_feed,
            ui_authority_receipt, java_tool_observation, installed_closure_receipt, bundletool, upload_certificate,
            dotnet_root, java_root, android_sdk_root, stage / "build-input", runner=runner,
            offline_nuget_feed=offline_nuget_feed,
            offline_aar_feed=offline_aar_feed,
            toolchain_inputs=toolchain_inputs,
            test_bootstrap_dir=test_bootstrap_dir,
            test_wheelhouse=test_wheelhouse,
            test_oracle_root=test_oracle_root,
        )
        toolchain_inputs.assert_exact(installed_closure_receipt, java_tool_observation)
        rebuilt = require_rebuild_match(rebuilt_aab, request, lock["limits"]["aab_bytes"])
        rebuilt_graph_value = _json_file(
            rebuilt_graph, "rebuilt source graph", lock["limits"]["json_bytes"], owner_only=True
        )[0]
        for field, value in graph.items():
            if field != "generatedAtUtc" and rebuilt_graph_value.get(field) != value:
                raise RebuilderError(f"independent source graph differs from producer: {field}")
        outputs = {
            "unsignedAab": f"chummer-android-{VERSION_NAME}-unsigned.aab",
            "sourceGraph": f"chummer-android-{VERSION_NAME}-source-graph.json",
            "buildSidecar": f"chummer-android-{VERSION_NAME}-unsigned.aab.sha256",
            "twoGreenReceipt": "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json",
            "twoGreenApproval": "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json",
            "externalSignerRequest": "ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json",
        }
        for source, name, label, limit in (
            (rebuilt_aab, outputs["unsignedAab"], "rebuilt unsigned AAB", lock["limits"]["aab_bytes"]),
            (producer_source_graph, outputs["sourceGraph"], "producer source graph", lock["limits"]["json_bytes"]),
            (producer_sidecar, outputs["buildSidecar"], "producer sidecar", 64 * 1024),
            (two_green_receipt, outputs["twoGreenReceipt"], "two-green receipt", lock["limits"]["json_bytes"]),
            (approval, outputs["twoGreenApproval"], "two-green approval", lock["limits"]["json_bytes"]),
            (external_request, outputs["externalSignerRequest"], "external signer request", lock["limits"]["json_bytes"]),
        ):
            _write_exclusive(stage / name, _stable_bytes(source, label, limit))
        bindings = {
            "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
            "requestSha256": hashlib.sha256(request_raw).hexdigest(),
            "sourceGraphSha256": hashlib.sha256(graph_raw).hexdigest(),
            "unsignedAabSha256": rebuilt["sha256"],
            "unsignedAabSizeBytes": rebuilt["sizeBytes"],
            "twoGreenReceiptSha256": _sha256_file(
                two_green_receipt, "two-green receipt", lock["limits"]["json_bytes"], owner_only=True
            ),
            "twoGreenApprovalSha256": _sha256_file(
                approval, "two-green approval", lock["limits"]["json_bytes"], owner_only=True
            ),
            "toolchainClosureSha256": toolchain["closureSha256"],
            "sourceCommit": qualification["sourceCommit"],
            "sourceTree": qualification["sourceTree"],
        }
        handoff = {
            "contractName": REBUILD_HANDOFF_CONTRACT,
            "status": "verified",
            "releaseIdentity": {"packageId": PACKAGE_ID, "versionName": VERSION_NAME, "versionCode": VERSION_CODE},
            "outputs": outputs,
            "bindings": bindings,
            "builderCredentialIsolationAuthority": "none_local_preparation_only",
            "eligibleForProtectedSigner": False,
            "signingPerformed": False,
            "publicationAuthorized": False,
            "googlePlayUploadAuthorized": False,
        }
        _write_exclusive(stage / "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json", _pretty_json(handoff))
        shutil.rmtree(workspace)
        shutil.rmtree(stage / "build-input")
        source_graph_copy.unlink()
        toolchain_inputs.assert_exact(installed_closure_receipt, java_tool_observation)
        os.replace(stage, output_dir)
        moved = True
        return handoff
    finally:
        if not moved:
            shutil.rmtree(stage, ignore_errors=True)


def validate_local_rebuild_handoff(directory: Path, lock: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Path]]:
    """Validate local bytes only; this does not authenticate job isolation."""

    if not directory.is_absolute() or directory.is_symlink() or directory.resolve(strict=True) != directory \
            or stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise RebuilderError("rebuild handoff directory is not canonical and owner-only")
    handoff_path = directory / "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json"
    handoff, _ = _json_file(handoff_path, "rebuild handoff", lock["limits"]["json_bytes"], owner_only=True)
    expected_fields = {
        "contractName", "status", "releaseIdentity", "outputs", "bindings",
        "builderCredentialIsolationAuthority", "eligibleForProtectedSigner",
        "signingPerformed", "publicationAuthorized",
        "googlePlayUploadAuthorized",
    }
    if set(handoff) != expected_fields or handoff.get("contractName") != REBUILD_HANDOFF_CONTRACT \
            or handoff.get("status") != "verified" \
            or handoff.get("releaseIdentity") != {
                "packageId": PACKAGE_ID, "versionName": VERSION_NAME, "versionCode": VERSION_CODE
            } \
            or handoff.get("builderCredentialIsolationAuthority") != "none_local_preparation_only" \
            or handoff.get("eligibleForProtectedSigner") is not False \
            or any(handoff.get(name) is not False for name in (
                "signingPerformed", "publicationAuthorized", "googlePlayUploadAuthorized"
            )):
        raise RebuilderError("rebuild handoff posture is not exact")
    names = handoff.get("outputs")
    expected_names = {
        "unsignedAab": f"chummer-android-{VERSION_NAME}-unsigned.aab",
        "sourceGraph": f"chummer-android-{VERSION_NAME}-source-graph.json",
        "buildSidecar": f"chummer-android-{VERSION_NAME}-unsigned.aab.sha256",
        "twoGreenReceipt": "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json",
        "twoGreenApproval": "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json",
        "externalSignerRequest": "ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json",
    }
    if names != expected_names:
        raise RebuilderError("rebuild handoff output inventory is not exact")
    paths = {name: directory / file_name for name, file_name in expected_names.items()}
    request, _graph = validate_external_request(paths["externalSignerRequest"], paths["sourceGraph"])
    rebuilt = require_rebuild_match(paths["unsignedAab"], request, lock["limits"]["aab_bytes"])
    bindings = handoff.get("bindings")
    digest_fields = {
        "lockSha256", "requestSha256", "sourceGraphSha256", "unsignedAabSha256",
        "twoGreenReceiptSha256", "twoGreenApprovalSha256", "toolchainClosureSha256",
    }
    if not isinstance(bindings, dict) or set(bindings) != digest_fields | {
        "unsignedAabSizeBytes", "sourceCommit", "sourceTree"
    } or any(not HEX64.fullmatch(str(bindings.get(name) or "")) for name in digest_fields) \
            or bindings.get("unsignedAabSha256") != rebuilt["sha256"] \
            or bindings.get("unsignedAabSizeBytes") != rebuilt["sizeBytes"] \
            or bindings.get("requestSha256") != _sha256_file(
                paths["externalSignerRequest"], "external signer request", lock["limits"]["json_bytes"], owner_only=True
            ) \
            or bindings.get("sourceGraphSha256") != _sha256_file(
                paths["sourceGraph"], "source graph", lock["limits"]["json_bytes"], owner_only=True
            ) \
            or bindings.get("twoGreenReceiptSha256") != _sha256_file(
                paths["twoGreenReceipt"], "two-green receipt", lock["limits"]["json_bytes"], owner_only=True
            ) \
            or bindings.get("twoGreenApprovalSha256") != _sha256_file(
                paths["twoGreenApproval"], "two-green approval", lock["limits"]["json_bytes"], owner_only=True
            ):
        raise RebuilderError("rebuild handoff bindings differ from transported bytes")
    _sha40(bindings.get("sourceCommit"), "rebuild source commit")
    _sha40(bindings.get("sourceTree"), "rebuild source tree")
    return handoff, paths


class PreservedRebuildHandoff:
    """Retain exact local handoff inputs without authenticating their producer.

    This is NOT an authenticated capability or a release receipt. A future
    protected caller must independently authenticate provenance, toolchains and
    isolation before using this object's byte assertion in its own capability.
    No signing, approval, publication or upload authority is granted here.
    """

    __slots__ = ("_lock_path", "_directory", "_limits", "_snapshot", "_handoff", "_paths")

    def __init__(self, lock_path: Path, directory: Path) -> None:
        self._lock_path, self._directory = lock_path, directory
        try:
            first_lock = self._file_snapshot(lock_path, "preserved handoff lock", 1024 * 1024)
            lock, lock_raw = load_lock(lock_path)
            json_limit, aab_limit = lock["limits"]["json_bytes"], lock["limits"]["aab_bytes"]
            if type(json_limit) is not int or not 0 < json_limit <= 8 * 1024 * 1024 \
                    or type(aab_limit) is not int or not 0 < aab_limit <= 512 * 1024 * 1024:
                raise RebuilderError("preserved handoff input bounds are not exact")
            self._limits = types.MappingProxyType({
                "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json": json_limit,
                f"chummer-android-{VERSION_NAME}-unsigned.aab": aab_limit,
                f"chummer-android-{VERSION_NAME}-source-graph.json": json_limit,
                f"chummer-android-{VERSION_NAME}-unsigned.aab.sha256": 64 * 1024,
                "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json": json_limit,
                "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json": json_limit,
                "ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json": json_limit,
            })
            before = self._capture()
            if before["lock"] != first_lock or first_lock[1] != hashlib.sha256(lock_raw).hexdigest():
                raise RebuilderError("preserved handoff lock changed during admission")
            handoff, paths = validate_local_rebuild_handoff(directory, lock)
            request, graph = validate_external_request(paths["externalSignerRequest"], paths["sourceGraph"], json_limit)
            android = validate_source_graph(graph)["chummer-android"]
            bindings = handoff["bindings"]
            if bindings["lockSha256"] != first_lock[1] \
                    or any(bindings[f"source{field.title()}"] != lock["android_authority"][field]
                           or android[field] != lock["android_authority"][field] for field in ("commit", "tree")) \
                    or request["buildSidecar"]["sha256"] != before[paths["buildSidecar"].name][1]:
                raise RebuilderError("preserved handoff lock, source or sidecar binding differs")
            if self._capture() != before:
                raise RebuilderError("preserved handoff inputs changed during admission")
            self._snapshot = types.MappingProxyType(before)
            self._handoff = self._freeze(handoff)
            self._paths = types.MappingProxyType(dict(paths))
        except (OSError, KeyError, TypeError, ValueError):
            raise RebuilderError("preserved handoff inputs are unavailable or malformed") from None

    @staticmethod
    def _freeze(value: Any) -> Any:
        # Detach every level; a read-only outer dict alone still exposes nested
        # mutable maps/lists to a later caller.
        if isinstance(value, dict):
            return types.MappingProxyType({name: PreservedRebuildHandoff._freeze(item)
                                           for name, item in value.items()})
        if isinstance(value, list):
            return tuple(PreservedRebuildHandoff._freeze(item) for item in value)
        return value

    @staticmethod
    def _identity(metadata: Any) -> tuple[int, ...]:
        return tuple(getattr(metadata, name) for name in (
            "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns",
            "st_mode", "st_uid", "st_gid", "st_nlink",
        ))

    @classmethod
    def _file_snapshot(cls, path: Path, label: str, limit: int) -> tuple[tuple[int, ...], str]:
        _preserved_path(path, label)
        before = cls._identity(path.stat())
        digest = _sha256_file(path, label, limit)
        _preserved_path(path, label)
        if before != cls._identity(path.stat()):
            raise RebuilderError("preserved handoff input changed while being captured")
        return before, digest

    def _inventory(self) -> None:
        names = set()
        for path in self._directory.iterdir():
            if path.name not in self._limits or path.is_symlink() or not path.is_file():
                raise RebuilderError("preserved handoff physical inventory is not exact")
            names.add(path.name)
            if len(names) > len(self._limits):
                raise RebuilderError("preserved handoff physical inventory is oversized")
        if names != set(self._limits):
            raise RebuilderError("preserved handoff physical inventory is incomplete")

    def _capture(self) -> dict[str, Any]:
        try:
            _preserved_path(self._directory, "preserved handoff directory", directory=True)
            root_before = self._identity(self._directory.stat())
            self._inventory()
            _preserved_tree(self._directory, "preserved handoff directory")
            result = {"directory": root_before, "lock": self._file_snapshot(
                self._lock_path, "preserved handoff lock", 1024 * 1024,
            )}
            for name, limit in self._limits.items():
                result[name] = self._file_snapshot(self._directory / name, "preserved handoff input", limit)
            self._inventory()
            if root_before != self._identity(self._directory.stat()):
                raise RebuilderError("preserved handoff directory changed while being captured")
            return result
        except OSError:
            raise RebuilderError("preserved handoff input is unavailable") from None

    @property
    def handoff(self) -> Mapping[str, Any]:
        return self._handoff

    @property
    def paths(self) -> Mapping[str, Path]:
        return self._paths

    @property
    def artifact_subject_path(self) -> Path:
        """Exact retained root manifest; reading this property does not re-admit it."""
        return self._directory / "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json"

    @property
    def artifact_closure_sha256(self) -> str:
        """Original raw root-manifest SHA256, NOT a transport archive digest.

        The admitted closed seven-file handoff binds five payloads directly and
        the sidecar through its request. Its root's exact bytes therefore bind
        that closure, but do not authenticate a producer or grant authority.
        Callers must assert_exact around use; this value never refreshes itself.
        """
        return self._snapshot[self.artifact_subject_path.name][1]

    def assert_exact(self) -> None:
        """Reject changed custody, inventory, bytes or identity; never recapture."""
        if self._capture() != self._snapshot:
            raise RebuilderError("preserved handoff inputs differ from the admitted snapshot")


def _recovery_store_identity(recovery_root: Path) -> str:
    """Bind one protected journal store independently of the output destination."""

    if not isinstance(recovery_root, Path) or not recovery_root.is_absolute() \
            or recovery_root.is_symlink() or not recovery_root.is_dir() \
            or recovery_root.resolve(strict=True) != recovery_root \
            or recovery_root.stat().st_uid != os.getuid() \
            or stat.S_IMODE(recovery_root.stat().st_mode) & 0o077:
        raise RebuilderError("protected signer recovery store is not canonical and owner-only")
    return hashlib.sha256(os.fsencode(recovery_root)).hexdigest()


class AuthenticatedRebuildHandoff:
    """In-memory capability returned only by a protected provenance verifier.

    This is deliberately not a serialized authority contract.  The future
    protected workflow owns authentication of the immutable artifact and
    supplies an assertion that rechecks its pinned bytes throughout signing.
    """

    __slots__ = (
        "handoff", "paths", "toolchain", "provenance", "java_root",
        "recovery_root", "assert_exact",
    )

    def __init__(
        self,
        handoff: Mapping[str, Any],
        paths: Mapping[str, Path],
        toolchain: Mapping[str, Any],
        provenance: Mapping[str, Any],
        java_root: Path,
        recovery_root: Path,
        assert_exact: Callable[[], None],
    ) -> None:
        self.handoff = handoff
        self.paths = paths
        self.toolchain = toolchain
        self.provenance = provenance
        self.java_root = java_root
        self.recovery_root = recovery_root
        self.assert_exact = assert_exact


def _validate_authenticated_handoff(
    lease: AuthenticatedRebuildHandoff, lock: Mapping[str, Any], lock_raw: bytes, *,
    attempt_id: str, two_green_artifact_id: int, two_green_artifact_sha256: str,
) -> None:
    expected_provenance_fields = {
        "authorityClass", "lockSha256", "artifactClosureSha256", "builderImage",
        "signerImage", "builderCredentialMountsPresent",
        "builderExecutionProvenanceAuthenticated", "protectedSignerRuntimeVerified",
        "consumerBytesRootOwnedImmutable", "ledgerAdapterBytesRootOwnedImmutable",
        "recoveryStoreIdentitySha256", "attemptId", "twoGreenArtifactId",
        "twoGreenArtifactSha256",
    }
    provenance = lease.provenance
    if not isinstance(provenance, Mapping) or set(provenance) != expected_provenance_fields \
            or provenance.get("authorityClass") != "authenticated_immutable_workflow_artifact" \
            or provenance.get("lockSha256") != hashlib.sha256(lock_raw).hexdigest() \
            or not HEX64.fullmatch(str(provenance.get("artifactClosureSha256") or "")) \
            or provenance.get("builderImage") != lock["toolchain"]["builder_image"] \
            or provenance.get("signerImage") != lock["toolchain"]["signer_image"] \
            or provenance.get("builderCredentialMountsPresent") is not False \
            or provenance.get("recoveryStoreIdentitySha256") \
            != _recovery_store_identity(lease.recovery_root) \
            or provenance.get("attemptId") != attempt_id \
            or provenance.get("twoGreenArtifactId") != two_green_artifact_id \
            or provenance.get("twoGreenArtifactSha256") != two_green_artifact_sha256 \
            or any(provenance.get(name) is not True for name in (
                "builderExecutionProvenanceAuthenticated", "protectedSignerRuntimeVerified",
                "consumerBytesRootOwnedImmutable", "ledgerAdapterBytesRootOwnedImmutable",
            )):
        raise RebuilderError("protected rebuild handoff provenance is not authenticated and exact")
    handoff = lease.handoff
    bindings = handoff.get("bindings")
    expected_binding_fields = {
        "lockSha256", "requestSha256", "sourceGraphSha256", "unsignedAabSha256",
        "unsignedAabSizeBytes", "twoGreenReceiptSha256", "twoGreenApprovalSha256",
        "toolchainClosureSha256", "sourceCommit", "sourceTree",
    }
    if handoff.get("contractName") != REBUILD_HANDOFF_CONTRACT \
            or handoff.get("releaseIdentity") != {
                "packageId": PACKAGE_ID, "versionName": VERSION_NAME, "versionCode": VERSION_CODE
            } \
            or not isinstance(bindings, Mapping) or set(bindings) != expected_binding_fields \
            or bindings.get("lockSha256") != provenance["lockSha256"] \
            or bindings.get("toolchainClosureSha256") \
            != lease.toolchain.get("builderClosureSha256"):
        raise RebuilderError("authenticated handoff differs from current lock or toolchain closure")
    exact_toolchain_fields = {
        "platform", "dotnet", "java", "android_sdk", "bundletoolSha256",
        "installedClosureReceiptSha256", "reportedBuilderImage", "plannedSignerImage",
        "builderExecutionProvenanceAuthenticated", "protectedSignerRuntimeVerified",
        "builderClosureSha256", "closureSha256",
    }
    if set(lease.toolchain) != exact_toolchain_fields:
        raise RebuilderError("protected full toolchain closure fields are not exact")
    for name in ("dotnet", "java", "android_sdk"):
        expected = lock["toolchain"][name]
        if lease.toolchain.get(name) != {
            "treeSha256": expected["tree_sha256"],
            "fileCount": expected["file_count"],
            "sizeBytes": expected["size_bytes"],
        }:
            raise RebuilderError(f"protected {name} closure differs from lock")
    if lease.toolchain.get("platform") != lock["toolchain"]["platform"] \
            or lease.toolchain.get("bundletoolSha256") != lock["toolchain"]["bundletool_sha256"] \
            or lease.toolchain.get("installedClosureReceiptSha256") \
            != lock["toolchain"]["installed_closure_receipt_sha256"]:
        raise RebuilderError("protected auxiliary toolchain closure differs from lock")
    builder_toolchain = {
        name: value for name, value in lease.toolchain.items()
        if name not in {"builderClosureSha256", "closureSha256"}
    }
    builder_toolchain["builderExecutionProvenanceAuthenticated"] = False
    builder_toolchain["protectedSignerRuntimeVerified"] = False
    if hashlib.sha256(_canonical_json(builder_toolchain)).hexdigest() \
            != lease.toolchain.get("builderClosureSha256"):
        raise RebuilderError("protected handoff changed the authenticated builder closure")
    full_toolchain = dict(lease.toolchain)
    claimed_full_closure = full_toolchain.pop("closureSha256", None)
    if not isinstance(claimed_full_closure, str) or not HEX64.fullmatch(claimed_full_closure) \
            or hashlib.sha256(_canonical_json(full_toolchain)).hexdigest() != claimed_full_closure:
        raise RebuilderError("protected full toolchain closure digest is not canonical")
    if lease.toolchain.get("builderExecutionProvenanceAuthenticated") is not True \
            or lease.toolchain.get("protectedSignerRuntimeVerified") is not True \
            or lease.toolchain.get("reportedBuilderImage") != provenance["builderImage"] \
            or lease.toolchain.get("plannedSignerImage") != provenance["signerImage"]:
        raise RebuilderError("authenticated handoff did not promote protected runtime provenance")
    expected_paths = {
        "unsignedAab", "sourceGraph", "buildSidecar", "twoGreenReceipt",
        "twoGreenApproval", "externalSignerRequest",
    }
    expected_path_names = {
        "unsignedAab": f"chummer-android-{VERSION_NAME}-unsigned.aab",
        "sourceGraph": f"chummer-android-{VERSION_NAME}-source-graph.json",
        "buildSidecar": f"chummer-android-{VERSION_NAME}-unsigned.aab.sha256",
        "twoGreenReceipt": "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json",
        "twoGreenApproval": "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json",
        "externalSignerRequest": "ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json",
    }
    if set(lease.paths) != expected_paths or any(
        not isinstance(path, Path) or not path.is_absolute() for path in lease.paths.values()
    ) or any(lease.paths[name].name != expected for name, expected in expected_path_names.items()):
        raise RebuilderError("authenticated handoff path inventory is not exact")
    actual_bindings = {
        "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
        "requestSha256": _sha256_file(
            lease.paths["externalSignerRequest"], "authenticated external signer request",
            lock["limits"]["json_bytes"], owner_only=True,
        ),
        "sourceGraphSha256": _sha256_file(
            lease.paths["sourceGraph"], "authenticated source graph",
            lock["limits"]["json_bytes"], owner_only=True,
        ),
        "unsignedAabSha256": _sha256_file(
            lease.paths["unsignedAab"], "authenticated unsigned AAB",
            lock["limits"]["aab_bytes"], owner_only=True,
        ),
        "unsignedAabSizeBytes": lease.paths["unsignedAab"].stat().st_size,
        "twoGreenReceiptSha256": _sha256_file(
            lease.paths["twoGreenReceipt"], "authenticated two-green receipt",
            lock["limits"]["json_bytes"], owner_only=True,
        ),
        "twoGreenApprovalSha256": _sha256_file(
            lease.paths["twoGreenApproval"], "authenticated two-green approval",
            lock["limits"]["json_bytes"], owner_only=True,
        ),
        "toolchainClosureSha256": lease.toolchain["builderClosureSha256"],
        "sourceCommit": lock["android_authority"]["commit"],
        "sourceTree": lock["android_authority"]["tree"],
    }
    if dict(bindings) != actual_bindings:
        raise RebuilderError("authenticated handoff byte or source-authority binding differs")
    java_digest, java_count, java_size = _tree_digest(
        lease.java_root, "protected signer Java closure"
    )
    expected_java = lock["toolchain"]["java"]
    if (java_digest, java_count, java_size) != (
        expected_java["tree_sha256"], expected_java["file_count"], expected_java["size_bytes"]
    ):
        raise RebuilderError("protected signer Java closure differs from lock")
    lease.assert_exact()


def _admit_signing_paths(value: Mapping[str, Any]) -> dict[str, Path]:
    expected = {"keystore", "storePassword", "keyPassword", "ownerPrivateKey"}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise RebuilderError("protected credential admission did not return the exact path inventory")
    paths = {name: path for name, path in value.items() if isinstance(path, Path)}
    if set(paths) != expected or any(not path.is_absolute() for path in paths.values()):
        raise RebuilderError("protected credential admission returned a noncanonical path")
    return paths


def _validate_protected_output_path(output_dir: Path, *, allow_existing: bool = False) -> None:
    if not output_dir.is_absolute() or output_dir.is_symlink() \
            or output_dir.parent.is_symlink() \
            or output_dir.parent.resolve(strict=True) != output_dir.parent \
            or output_dir.parent.stat().st_uid != os.getuid() \
            or stat.S_IMODE(output_dir.parent.stat().st_mode) & 0o077 \
            or (output_dir.exists() and not allow_existing):
        raise RebuilderError("protected signer output is not canonical below one owner-only directory")
    if output_dir.exists() and (
        not output_dir.is_dir() or output_dir.resolve(strict=True) != output_dir
        or output_dir.stat().st_uid != os.getuid()
        or stat.S_IMODE(output_dir.stat().st_mode) & 0o077
    ):
        raise RebuilderError("existing protected signer output is not one owner-only directory")


def _validate_pre_signing_inputs(
    lease: AuthenticatedRebuildHandoff, lock: Mapping[str, Any], android: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bytes, bytes]:
    """Replay every public semantic gate before a signing credential is admitted."""

    request, graph = validate_external_request(
        lease.paths["externalSignerRequest"], lease.paths["sourceGraph"],
        lock["limits"]["json_bytes"],
    )
    rebuilt = require_rebuild_match(
        lease.paths["unsignedAab"], request, lock["limits"]["aab_bytes"]
    )
    rows = validate_source_graph(graph)
    android_row = rows["chummer-android"]
    if (android_row["commit"], android_row["tree"], android_row["repository"]) != (
        lock["android_authority"]["commit"], lock["android_authority"]["tree"],
        lock["android_authority"]["repository"],
    ):
        raise RebuilderError("authenticated source graph is not the qualified Android authority")
    if _sha256_file(
        lease.paths["buildSidecar"], "authenticated producer sidecar", 64 * 1024,
        owner_only=True,
    ) != request["buildSidecar"]["sha256"]:
        raise RebuilderError("authenticated producer sidecar differs from the signer request")
    try:
        claims = android._artifact_claims(
            lease.paths["unsignedAab"], lease.paths["sourceGraph"],
            lease.paths["buildSidecar"], lease.paths["twoGreenReceipt"],
            lease.paths["twoGreenApproval"],
        )
        identity = claims["graph"]["releaseIdentity"]
        qualification = android.VERIFY.verify_release_eligibility(
            lease.paths["twoGreenReceipt"], lease.paths["twoGreenApproval"],
            android_root=android.ROOT,
            expected_version_name=identity["versionName"],
            expected_version_code=identity["versionCode"],
            source_graph_path=lease.paths["sourceGraph"],
        )
    except Exception as error:
        raise RebuilderError("authenticated Android pre-signing eligibility replay failed") from error
    bindings = lease.handoff["bindings"]
    if claims.get("sourceCommit") != bindings["sourceCommit"] \
            or claims.get("sourceTree") != bindings["sourceTree"] \
            or claims.get("aab") != {
                "fileName": request["unsignedAab"]["fileName"],
                "sha256": rebuilt["sha256"], "sizeBytes": rebuilt["sizeBytes"],
            } \
            or claims.get("sourceGraph") != {
                "fileName": request["sourceGraph"]["fileName"],
                "sha256": bindings["sourceGraphSha256"],
                "sizeBytes": request["sourceGraph"]["sizeBytes"],
            } \
            or claims.get("buildSidecar", {}).get("sha256") != request["buildSidecar"]["sha256"] \
            or claims.get("twoGreen") != {
                "receiptSha256": bindings["twoGreenReceiptSha256"],
                "approvalSha256": bindings["twoGreenApprovalSha256"],
            }:
        raise RebuilderError("Android pre-signing artifact claims differ from authenticated handoff")
    if qualification.get("sourceCommit") != bindings["sourceCommit"] \
            or qualification.get("sourceTree") != bindings["sourceTree"] \
            or qualification.get("receiptSha256") != bindings["twoGreenReceiptSha256"] \
            or qualification.get("eligible") is not True \
            or qualification.get("internalTestingEligible") is not True \
            or qualification.get("publicationAuthorized") is not False \
            or qualification.get("googlePlayUploadAuthorized") is not False:
        raise RebuilderError("two-green eligibility is not exact for the authenticated handoff")
    request_raw = _stable_bytes(
        lease.paths["externalSignerRequest"], "authenticated external signer request",
        lock["limits"]["json_bytes"], owner_only=True,
    )
    graph_raw = _stable_bytes(
        lease.paths["sourceGraph"], "authenticated source graph",
        lock["limits"]["json_bytes"], owner_only=True,
    )
    lease.assert_exact()
    return request, graph, rebuilt, request_raw, graph_raw


LEDGER_RESPONSE_NAME = re.compile(
    r"^LEDGER_AUTHENTICATED_RESPONSE\.([0-9a-f]{64})\.generated\.json$"
)


def _recovery_path(recovery_root: Path, attempt_id: str) -> Path:
    _recovery_store_identity(recovery_root)
    _sha256(attempt_id, "protected signer attempt")
    return recovery_root / attempt_id


def _recovery_write(directory: Path, name: str, value: Mapping[str, Any]) -> Path:
    path = directory / name
    _write_exclusive(path, _pretty_json(value))
    _fsync_directory(directory)
    return path


def _recovery_read(directory: Path, name: str, limit: int) -> tuple[dict[str, Any], bytes]:
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir() \
            or directory.resolve(strict=True) != directory \
            or directory.stat().st_uid != os.getuid() \
            or stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise RebuilderError("protected signer recovery directory is not canonical and owner-only")
    return _json_file(
        directory / name, f"protected signer recovery {name}", limit, owner_only=True
    )


def _write_or_match(path: Path, raw: bytes, label: str, limit: int) -> None:
    if path.exists():
        if _stable_bytes(path, label, limit, owner_only=True) != raw:
            raise RebuilderError(f"existing {label} differs from recovered transaction")
        return
    _write_exclusive(path, raw)
    _fsync_directory(path.parent)


def _validate_recovery_inventory(directory: Path, *, require_final: bool) -> None:
    required = {
        "RESERVATION.generated.json",
        "ATTESTED.generated.json",
        "LEDGER_COMMIT_INTENT.generated.json",
        f"chummer-android-{VERSION_NAME}-signed.aab",
        f"chummer-android-{VERSION_NAME}-signed.aab.sha256",
        "ANDROID_RELEASE_BUILD_ATTESTATION.v2.json",
        "ANDROID_EXTERNAL_SIGNER_ATTESTATION.v1.json",
    }
    optional = {
        "LEDGER_COMMIT.generated.json",
        "FLEET_ANDROID_PREVIEW12_EXTERNAL_REBUILD_AUDIT.v3.json",
    }
    actual = {entry.name for entry in os.scandir(directory)}
    if "QUARANTINED.generated.json" in actual:
        raise RebuilderError("protected signer recovery contains quarantined unverified evidence")
    histories = {name for name in actual if LEDGER_RESPONSE_NAME.fullmatch(name)}
    unknown = actual - required - optional - histories
    final_fixed = optional
    if not required.issubset(actual) or unknown or len(histories) > 4 \
            or (require_final and (not histories or not final_fixed.issubset(actual))):
        raise RebuilderError("protected signer recovery inventory is incomplete or contaminated")
    for name in actual:
        path = directory / name
        metadata = path.lstat()
        if path.is_symlink() or not path.is_file() or metadata.st_uid != os.getuid() \
                or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RebuilderError("protected signer recovery contains a noncanonical entry")
        match = LEDGER_RESPONSE_NAME.fullmatch(name)
        if match is not None:
            raw = _stable_bytes(
                path, "authenticated ledger response history", 8 * 1024 * 1024,
                owner_only=True,
            )
            if hashlib.sha256(raw).hexdigest() != match.group(1):
                raise RebuilderError("authenticated ledger response history name differs from bytes")


def _quarantine_unverified_recovery(
    directory: Path, attempt_id: str, lock: Mapping[str, Any], *, phase: str,
) -> None:
    """Record post-credential bytes as diagnostic-only, never recoverable authority."""

    artifacts: list[dict[str, Any]] = []
    for entry in sorted(os.scandir(directory), key=lambda item: item.name):
        path = Path(entry.path)
        metadata = path.lstat()
        if entry.name == "QUARANTINED.generated.json":
            continue
        if path.is_symlink() or not path.is_file() or metadata.st_uid != os.getuid() \
                or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise RebuilderError("cannot quarantine a noncanonical signer artifact")
        limit = lock["limits"]["aab_bytes"] if entry.name.endswith(".aab") \
            else lock["limits"]["json_bytes"]
        raw = _stable_bytes(path, f"quarantined {entry.name}", limit, owner_only=True)
        artifacts.append({
            "fileName": entry.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "sizeBytes": len(raw),
        })
    value = {
        "contractName": RECOVERY_CONTRACT,
        "contractVersion": 1,
        "phase": "quarantined",
        "failurePhase": phase,
        "attemptId": attempt_id,
        "artifacts": artifacts,
        "verified": False,
        "reconciliationEligible": False,
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
    }
    _write_or_match(
        directory / "QUARANTINED.generated.json", _pretty_json(value),
        "protected signer quarantine marker", lock["limits"]["json_bytes"],
    )


def _reservation_record(
    lock_raw: bytes, lease: AuthenticatedRebuildHandoff, subject: Mapping[str, Any],
    reservation: Mapping[str, Any], output_dir: Path, attempt_id: str,
    two_green_artifact_id: int, two_green_artifact_sha256: str,
) -> dict[str, Any]:
    return {
        "contractName": RECOVERY_CONTRACT,
        "contractVersion": 1,
        "phase": "reserved",
        "attemptId": attempt_id,
        "outputPathSha256": hashlib.sha256(os.fsencode(output_dir)).hexdigest(),
        "recoveryStoreIdentitySha256": _recovery_store_identity(lease.recovery_root),
        "twoGreenArtifactId": two_green_artifact_id,
        "twoGreenArtifactSha256": two_green_artifact_sha256,
        "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
        "artifactClosureSha256": lease.provenance["artifactClosureSha256"],
        "subject": dict(subject),
        "reservation": dict(reservation),
    }


def _attested_record(
    lock_raw: bytes, lease: AuthenticatedRebuildHandoff, signed: Mapping[str, Any],
    rebuilt: Mapping[str, Any], request_raw: bytes, graph_raw: bytes,
    signed_path: Path, signed_sidecar: Path, android_v2_path: Path,
    external_v1_path: Path, attempt_id: str,
) -> dict[str, Any]:
    return {
        "contractName": RECOVERY_CONTRACT,
        "contractVersion": 1,
        "phase": "attested",
        "attemptId": attempt_id,
        "signedAab": dict(signed),
        "bindings": {
            "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
            "artifactClosureSha256": lease.provenance["artifactClosureSha256"],
            "requestSha256": hashlib.sha256(request_raw).hexdigest(),
            "sourceGraphSha256": hashlib.sha256(graph_raw).hexdigest(),
            "unsignedAabSha256": rebuilt["sha256"],
            "toolchainClosureSha256": lease.toolchain["closureSha256"],
            "signedAabSha256": _sha256_file(
                signed_path, "recovery signed AAB", 512 * 1024 * 1024, owner_only=True
            ),
            "signedSidecarSha256": _sha256_file(
                signed_sidecar, "recovery signed sidecar", 64 * 1024, owner_only=True
            ),
            "androidV2Sha256": _sha256_file(
                android_v2_path, "recovery Android v2", 8 * 1024 * 1024, owner_only=True
            ),
            "externalV1Sha256": _sha256_file(
                external_v1_path, "recovery external v1", 32 * 1024, owner_only=True
            ),
        },
    }


def validate_external_signer_attestation(
    android: Any, path: Path, request: Mapping[str, Any], rebuilt: Mapping[str, Any],
    signed: Mapping[str, Any], graph_raw: bytes, toolchain: Mapping[str, Any],
    android_v2_path: Path, approval_authority: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify the exact public v1 response using Android's pinned Ed25519 key."""

    key_id, explicit = _android_builder_selection(android, approval_authority)
    value, raw = _json_file(
        path, "external signer v1 attestation", 32 * 1024, owner_only=True
    )
    if raw != _pretty_json(value):
        raise RebuilderError("external signer v1 bytes are not exact pretty JSON")
    expected_fields = {
        "contractName", "algorithm", "keyId", "role", "attestationScope",
        "generatedAtUtc", "challengeNonce", "releaseIdentity", "unsignedAabSha256",
        "signedAabSha256", "signedAabSizeBytes", "sourceGraphSha256",
        "expectedUploadCertificateSha256", "fullToolchainClosureSha256",
        "androidReleaseBuildAttestation", "publicationAuthorized",
        "googlePlayUploadAuthorized", "signatureBase64",
    }
    if set(value) != expected_fields:
        raise RebuilderError("external signer v1 fields are not exact")
    generated = value.get("generatedAtUtc")
    try:
        parsed = datetime.fromisoformat(str(generated).removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise RebuilderError("external signer v1 timestamp is not canonical UTC") from error
    if not isinstance(generated, str) or not generated.endswith("Z") \
            or parsed.tzinfo is None \
            or parsed.microsecond != 0 \
            or parsed.astimezone(UTC).isoformat().replace("+00:00", "Z") != generated:
        raise RebuilderError("external signer v1 timestamp is not canonical UTC")
    challenge = value.get("challengeNonce")
    if not isinstance(challenge, str) or not HEX64.fullmatch(challenge):
        raise RebuilderError("external signer v1 challenge is not exact")
    expected_unsigned = {
        "contractName": EXTERNAL_SIGNER_ATTESTATION_CONTRACT,
        "algorithm": "ed25519",
        "keyId": approval_authority["key_id"],
        "role": approval_authority["role"],
        "attestationScope": approval_authority["scope"],
        "generatedAtUtc": generated,
        "challengeNonce": challenge,
        "releaseIdentity": dict(request["releaseIdentity"]),
        "unsignedAabSha256": rebuilt["sha256"],
        "signedAabSha256": signed["sha256"],
        "signedAabSizeBytes": signed["sizeBytes"],
        "sourceGraphSha256": hashlib.sha256(graph_raw).hexdigest(),
        "expectedUploadCertificateSha256": UPLOAD_CERTIFICATE_SHA256,
        "fullToolchainClosureSha256": toolchain["closureSha256"],
        "androidReleaseBuildAttestation": {
            "contractName": ANDROID_ATTESTATION_CONTRACT,
            "sha256": _sha256_file(
                android_v2_path, "external signer Android v2", 8 * 1024 * 1024,
                owner_only=True,
            ),
        },
        "publicationAuthorized": False,
        "googlePlayUploadAuthorized": False,
    }
    unsigned = dict(value)
    signature = unsigned.pop("signatureBase64")
    if unsigned != expected_unsigned:
        raise RebuilderError("external signer v1 claims differ from the recovered transaction")
    try:
        android.VERIFY._verify_ed25519_signature(
            unsigned, signature, label="external signer v1",
            **({"builder_key_id": key_id} if explicit else {}),
        )
    except Exception as error:
        raise RebuilderError("external signer v1 detached signature is invalid") from error
    return value


def _expected_ledger_subject(
    ledger: Any, lease: AuthenticatedRebuildHandoff, policy_sha256: str, *,
    attempt_id: str, two_green_artifact_id: int, two_green_artifact_sha256: str,
    json_limit: int,
) -> dict[str, Any]:
    return ledger.make_subject(
        approval_request_nonce=attempt_id,
        two_green_artifact_id=two_green_artifact_id,
        two_green_artifact_sha256=two_green_artifact_sha256,
        two_green_receipt_sha256=_sha256_file(
            lease.paths["twoGreenReceipt"], "two-green receipt", json_limit, owner_only=True
        ),
        main_tree=str(lease.handoff["bindings"]["sourceTree"]),
        policy_sha256=policy_sha256,
        version_name=VERSION_NAME,
        version_code=VERSION_CODE,
    )


def _validate_recovery_records(
    directory: Path, lock: Mapping[str, Any], lock_raw: bytes,
    lease: AuthenticatedRebuildHandoff, expected_subject: Mapping[str, Any],
    request_raw: bytes, graph_raw: bytes, rebuilt: Mapping[str, Any], *,
    output_dir: Path, attempt_id: str, two_green_artifact_id: int,
    two_green_artifact_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    reservation_record, _ = _recovery_read(
        directory, "RESERVATION.generated.json", lock["limits"]["json_bytes"]
    )
    expected_reservation_fields = {
        "contractName", "contractVersion", "phase", "attemptId", "outputPathSha256",
        "recoveryStoreIdentitySha256",
        "twoGreenArtifactId", "twoGreenArtifactSha256", "lockSha256",
        "artifactClosureSha256", "subject", "reservation",
    }
    if set(reservation_record) != expected_reservation_fields \
            or reservation_record.get("contractName") != RECOVERY_CONTRACT \
            or reservation_record.get("contractVersion") != 1 \
            or reservation_record.get("phase") != "reserved" \
            or reservation_record.get("attemptId") != attempt_id \
            or reservation_record.get("outputPathSha256") \
            != hashlib.sha256(os.fsencode(output_dir)).hexdigest() \
            or reservation_record.get("recoveryStoreIdentitySha256") \
            != _recovery_store_identity(lease.recovery_root) \
            or reservation_record.get("twoGreenArtifactId") != two_green_artifact_id \
            or reservation_record.get("twoGreenArtifactSha256") != two_green_artifact_sha256 \
            or reservation_record.get("lockSha256") != hashlib.sha256(lock_raw).hexdigest() \
            or reservation_record.get("artifactClosureSha256") \
            != lease.provenance["artifactClosureSha256"] \
            or reservation_record.get("subject") != expected_subject \
            or reservation_record.get("reservation", {}).get("receipt", {}).get("state") != "reserved":
        raise RebuilderError("protected signer recovery reservation is not exact")

    attested_record, _ = _recovery_read(
        directory, "ATTESTED.generated.json", lock["limits"]["json_bytes"]
    )
    if set(attested_record) != {
        "contractName", "contractVersion", "phase", "attemptId", "signedAab", "bindings"
    } or attested_record.get("contractName") != RECOVERY_CONTRACT \
            or attested_record.get("contractVersion") != 1 \
            or attested_record.get("phase") != "attested" \
            or attested_record.get("attemptId") != attempt_id:
        raise RebuilderError("protected signer recovery attestation marker is not exact")
    paths = {
        "signedAab": directory / f"chummer-android-{VERSION_NAME}-signed.aab",
        "signedSidecar": directory / f"chummer-android-{VERSION_NAME}-signed.aab.sha256",
        "androidV2": directory / "ANDROID_RELEASE_BUILD_ATTESTATION.v2.json",
        "externalV1": directory / "ANDROID_EXTERNAL_SIGNER_ATTESTATION.v1.json",
        "commitIntent": directory / "LEDGER_COMMIT_INTENT.generated.json",
        "ledgerCommit": directory / "LEDGER_COMMIT.generated.json",
        "audit": directory / "FLEET_ANDROID_PREVIEW12_EXTERNAL_REBUILD_AUDIT.v3.json",
    }
    signed = attested_record.get("signedAab")
    if not isinstance(signed, dict) or signed != {
        "sha256": _sha256_file(
            paths["signedAab"], "recovered signed AAB", lock["limits"]["aab_bytes"], owner_only=True
        ),
        "sizeBytes": paths["signedAab"].stat().st_size,
        "uploadCertificateSha256": UPLOAD_CERTIFICATE_SHA256,
    }:
        raise RebuilderError("recovered signed AAB differs from its attested identity")
    expected_bindings = {
        "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
        "artifactClosureSha256": lease.provenance["artifactClosureSha256"],
        "requestSha256": hashlib.sha256(request_raw).hexdigest(),
        "sourceGraphSha256": hashlib.sha256(graph_raw).hexdigest(),
        "unsignedAabSha256": rebuilt["sha256"],
        "toolchainClosureSha256": lease.toolchain["closureSha256"],
        "signedAabSha256": signed["sha256"],
        "signedSidecarSha256": _sha256_file(
            paths["signedSidecar"], "recovered signed sidecar", 64 * 1024, owner_only=True
        ),
        "androidV2Sha256": _sha256_file(
            paths["androidV2"], "recovered Android v2", lock["limits"]["json_bytes"], owner_only=True
        ),
        "externalV1Sha256": _sha256_file(
            paths["externalV1"], "recovered external v1", 32 * 1024, owner_only=True
        ),
    }
    if attested_record.get("bindings") != expected_bindings:
        raise RebuilderError("recovered signed evidence differs from its exclusive journal")
    intent, _ = _recovery_read(
        directory, "LEDGER_COMMIT_INTENT.generated.json", lock["limits"]["json_bytes"]
    )
    if intent != {
        "contractName": RECOVERY_CONTRACT,
        "contractVersion": 1,
        "phase": "commit-intent",
        "attemptId": attempt_id,
        "externalV1Sha256": expected_bindings["externalV1Sha256"],
    }:
        raise RebuilderError("protected signer recovery commit intent is not exact")
    _validate_recovery_inventory(directory, require_final=False)
    return dict(reservation_record["reservation"]), dict(signed), paths


def execute_protected_signer_transaction(
    lock_path: Path,
    authenticate_handoff: Callable[[Mapping[str, Any], bytes], AuthenticatedRebuildHandoff],
    load_consumer: Callable[[], Any],
    fleet_root: Path,
    ledger_environment: Mapping[str, str],
    admit_signing_credentials: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]],
    protected_validation_factory: Callable[..., Mapping[str, Any]],
    output_dir: Path,
    *,
    attempt_id: str,
    two_green_artifact_id: int,
    two_green_artifact_sha256: str,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Compose one dormant protected sign-once transaction.

    The callback capabilities are test seams, not runtime provenance.  A future
    protected owner workflow must construct them from immutable job evidence.
    """

    lock, lock_raw = load_lock(lock_path)
    failures = validate_lock(lock, lock_raw)
    if failures:
        raise RebuilderError("; ".join(failures))
    _sha256(attempt_id, "protected signer attempt")
    _sha256(two_green_artifact_sha256, "two-green artifact")
    if type(two_green_artifact_id) is not int or two_green_artifact_id < 1:
        raise RebuilderError("two-green artifact ID must be a positive integer")
    _validate_protected_output_path(output_dir)

    lease = authenticate_handoff(lock, lock_raw)
    if not isinstance(lease, AuthenticatedRebuildHandoff):
        raise RebuilderError("protected provenance verifier returned no authenticated handoff")
    _validate_authenticated_handoff(
        lease, lock, lock_raw, attempt_id=attempt_id,
        two_green_artifact_id=two_green_artifact_id,
        two_green_artifact_sha256=two_green_artifact_sha256,
    )
    recovery = _recovery_path(lease.recovery_root, attempt_id)
    if lease.recovery_root.stat().st_dev != output_dir.parent.stat().st_dev:
        raise RebuilderError("protected recovery store and final output are not on one filesystem")
    if recovery.exists() or recovery.is_symlink():
        raise RebuilderError("protected signer attempt already has a journal; reconciliation is required")
    if isinstance(protected_validation_factory, PreservedProtectedValidation):
        protected_validation_factory.bind_transaction(lock_raw, lease, load_consumer)
    android = load_consumer()
    if getattr(android, "CONTRACT", None) != ANDROID_ATTESTATION_CONTRACT:
        raise RebuilderError("protected Android consumer contract differs")
    builder_selection = _android_builder_selection(android, lock["approval_authority"])
    request, _graph, rebuilt, request_raw, graph_raw = _validate_pre_signing_inputs(
        lease, lock, android
    )
    ledger, client, policy_sha256 = load_reviewed_ledger(
        fleet_root, lock, ledger_environment
    )
    subject, reservation = reserve_signing_attempt(
        ledger, client, attempt_id=attempt_id,
        two_green_artifact_id=two_green_artifact_id,
        two_green_artifact_sha256=two_green_artifact_sha256,
        two_green_receipt_sha256=lease.handoff["bindings"]["twoGreenReceiptSha256"],
        main_tree=str(lease.handoff["bindings"]["sourceTree"]),
        policy_sha256=policy_sha256,
    )

    credential_admission_started = False
    attested_record_written = False
    failure_phase = "reserved"
    recovery_created = False
    try:
        lease.assert_exact()
        recovery.mkdir(mode=0o700)
        recovery.chmod(0o700)
        # The attempt entry lives under the authenticated recovery store, not
        # beside the eventual output destination. Persist that actual parent
        # before any credential can be admitted.
        _fsync_directory(recovery.parent)
        recovery_created = True
        _recovery_write(
            recovery, "RESERVATION.generated.json",
            _reservation_record(
                lock_raw, lease, subject, reservation, output_dir, attempt_id,
                two_green_artifact_id, two_green_artifact_sha256,
            ),
        )
        if _android_builder_selection(android, lock["approval_authority"]) != builder_selection:
            raise RebuilderError("Android builder selector changed before credential admission")
        expected_spki = lock["approval_authority"]["public_key_spki_sha256"]
        if getattr(android, "_fleet_expected_spki_sha256", None) != expected_spki:
            raise RebuilderError("Android builder key binding differs from the qualified lock")
        credential_admission_started = True
        failure_phase = "credential-admission"
        credentials = _admit_signing_paths(
            admit_signing_credentials(reservation, lease.provenance)
        )
        lease.assert_exact()
        # Reject unusable builder custody before consuming the AAB signing
        # operation. Later attestation checks remain necessary as well.
        _owner_key_matches(runner, credentials["ownerPrivateKey"], expected_spki)
        lease.assert_exact()
        signed_path = recovery / f"chummer-android-{VERSION_NAME}-signed.aab"
        signed = sign_aab(
            lease.paths["unsignedAab"], signed_path, lock, credentials["keystore"],
            credentials["storePassword"], credentials["keyPassword"],
            lease.java_root, runner=runner,
        )
        failure_phase = "signed-aab-unverified-chain"
        signed_sidecar = recovery / f"{signed_path.name}.sha256"
        materialize_signed_sidecar(
            signed_path, lease.paths["sourceGraph"], signed_sidecar,
            lock["limits"]["aab_bytes"],
        )
        lease.assert_exact()
        protected_validation = protected_validation_factory(
            android=android, signed_aab=signed_path,
            source_graph=lease.paths["sourceGraph"], sidecar=signed_sidecar,
            two_green_receipt=lease.paths["twoGreenReceipt"],
            approval=lease.paths["twoGreenApproval"],
        )
        android_v2_path = recovery / "ANDROID_RELEASE_BUILD_ATTESTATION.v2.json"
        android_v2_attestation(
            android, signed_path, lease.paths["sourceGraph"], signed_sidecar,
            lease.paths["twoGreenReceipt"], lease.paths["twoGreenApproval"],
            protected_validation, credentials["ownerPrivateKey"], android_v2_path,
            runner=runner,
        )
        failure_phase = "android-v2-generated"
        external_v1_path = recovery / "ANDROID_EXTERNAL_SIGNER_ATTESTATION.v1.json"
        external_signer_attestation(
            request, rebuilt, signed, graph_raw, lease.toolchain, android_v2_path,
            credentials["ownerPrivateKey"], lock["approval_authority"],
            external_v1_path, runner=runner,
        )
        validate_external_signer_attestation(
            android, external_v1_path, request, rebuilt, signed, graph_raw,
            lease.toolchain, android_v2_path, lock["approval_authority"],
        )
        failure_phase = "external-v1-verified"
        lease.assert_exact()
        _recovery_write(
            recovery, "ATTESTED.generated.json",
            _attested_record(
                lock_raw, lease, signed, rebuilt, request_raw, graph_raw,
                signed_path, signed_sidecar, android_v2_path, external_v1_path,
                attempt_id,
            ),
        )
        attested_record_written = True
        failure_phase = "attested"
        _recovery_write(
            recovery, "LEDGER_COMMIT_INTENT.generated.json",
            {
                "contractName": RECOVERY_CONTRACT, "contractVersion": 1,
                "phase": "commit-intent", "attemptId": attempt_id,
                "externalV1Sha256": _sha256_file(
                    external_v1_path, "external signer v1 attestation", 32 * 1024,
                    owner_only=True,
                ),
            },
        )
        _validate_recovery_inventory(recovery, require_final=False)
        ledger_commit = commit_signing_attempt(
            client, subject, reservation, external_v1_path
        )
        external_raw = _stable_bytes(
            external_v1_path, "external signer v1 attestation", 32 * 1024,
            owner_only=True,
        )
        selected_ledger_commit = _select_authenticated_ledger_commit(
            recovery, ledger, client, ledger_commit, subject, reservation,
            external_raw, lock["limits"]["json_bytes"],
        )
        audit = fleet_audit(
            lock, lock_raw, request_raw, graph_raw, rebuilt, signed,
            lease.toolchain, selected_ledger_commit, android_v2_path, external_v1_path,
        )
        _write_or_match(
            recovery / "FLEET_ANDROID_PREVIEW12_EXTERNAL_REBUILD_AUDIT.v3.json",
            _pretty_json(audit), "Fleet external rebuild audit",
            lock["limits"]["json_bytes"],
        )
        _validate_recovery_inventory(recovery, require_final=True)
        os.replace(recovery, output_dir)
        _fsync_directory(recovery.parent)
        _fsync_directory(output_dir.parent)
        return audit
    except Exception:
        if not credential_admission_started:
            try:
                client.abort(subject, "protected_signer_failed", reservation)
            except Exception:
                pass
            finally:
                if recovery_created:
                    shutil.rmtree(recovery, ignore_errors=True)
        elif recovery_created and not attested_record_written:
            # Signing or detached attestation may already have consumed a
            # sign-once key operation. Preserve every private byte, but mark
            # the journal as unverified and permanently ineligible for normal
            # reconciliation or promotion.
            try:
                _quarantine_unverified_recovery(
                    recovery, attempt_id, lock, phase=failure_phase
                )
            except Exception:
                # Never destroy the evidence if even the quarantine marker
                # cannot be durably written. The existing canonical attempt
                # directory still blocks any second signing execution.
                pass
        # Once credential admission begins the private recovery directory is
        # retained.  It is the only copy of the signed bytes and sign-once
        # evidence; reconciliation never accepts signing credentials.
        raise


def reconcile_protected_signer_transaction(
    lock_path: Path,
    authenticate_handoff: Callable[[Mapping[str, Any], bytes], AuthenticatedRebuildHandoff],
    load_consumer: Callable[[], Any],
    fleet_root: Path,
    ledger_environment: Mapping[str, str],
    protected_validation_factory: Callable[..., Mapping[str, Any]],
    output_dir: Path,
    *,
    attempt_id: str,
    two_green_artifact_id: int,
    two_green_artifact_sha256: str,
) -> dict[str, Any]:
    """Recover commit/audit/promotion without admitting keys or signing again."""

    lock, lock_raw = load_lock(lock_path)
    failures = validate_lock(lock, lock_raw)
    if failures:
        raise RebuilderError("; ".join(failures))
    _sha256(attempt_id, "protected signer attempt")
    _sha256(two_green_artifact_sha256, "two-green artifact")
    if type(two_green_artifact_id) is not int or two_green_artifact_id < 1:
        raise RebuilderError("two-green artifact ID must be a positive integer")
    _validate_protected_output_path(output_dir, allow_existing=True)

    lease = authenticate_handoff(lock, lock_raw)
    if not isinstance(lease, AuthenticatedRebuildHandoff):
        raise RebuilderError("protected provenance verifier returned no authenticated handoff")
    _validate_authenticated_handoff(
        lease, lock, lock_raw, attempt_id=attempt_id,
        two_green_artifact_id=two_green_artifact_id,
        two_green_artifact_sha256=two_green_artifact_sha256,
    )
    recovery = _recovery_path(lease.recovery_root, attempt_id)
    if lease.recovery_root.stat().st_dev != output_dir.parent.stat().st_dev:
        raise RebuilderError("protected recovery store and final output are not on one filesystem")
    if output_dir.exists() and recovery.exists():
        raise RebuilderError("both completed output and recovery directory exist")
    directory = output_dir if output_dir.exists() else recovery
    if not directory.exists():
        raise RebuilderError("no protected signer recovery evidence exists")
    if isinstance(protected_validation_factory, PreservedProtectedValidation):
        protected_validation_factory.bind_transaction(lock_raw, lease, load_consumer)
    android = load_consumer()
    if getattr(android, "CONTRACT", None) != ANDROID_ATTESTATION_CONTRACT:
        raise RebuilderError("protected Android consumer contract differs")
    _android_builder_selection(android, lock["approval_authority"])
    request, _graph, rebuilt, request_raw, graph_raw = _validate_pre_signing_inputs(
        lease, lock, android
    )
    ledger, client, policy_sha256 = load_reviewed_ledger(
        fleet_root, lock, ledger_environment
    )
    subject = _expected_ledger_subject(
        ledger, lease, policy_sha256, attempt_id=attempt_id,
        two_green_artifact_id=two_green_artifact_id,
        two_green_artifact_sha256=two_green_artifact_sha256,
        json_limit=lock["limits"]["json_bytes"],
    )
    reservation, signed, paths = _validate_recovery_records(
        directory, lock, lock_raw, lease, subject, request_raw, graph_raw, rebuilt,
        output_dir=output_dir, attempt_id=attempt_id,
        two_green_artifact_id=two_green_artifact_id,
        two_green_artifact_sha256=two_green_artifact_sha256,
    )
    fresh_validation = protected_validation_factory(
        android=android, signed_aab=paths["signedAab"],
        source_graph=lease.paths["sourceGraph"], sidecar=paths["signedSidecar"],
        two_green_receipt=lease.paths["twoGreenReceipt"],
        approval=lease.paths["twoGreenApproval"],
    )
    try:
        recovered_v2, _ = _json_file(
            paths["androidV2"], "recovered Android v2",
            lock["limits"]["json_bytes"], owner_only=True,
        )
        fresh_validation = android._validate_validation_claims(dict(fresh_validation))
        recovered_validation = android._validate_validation_claims(
            dict(recovered_v2.get("protectedValidation", {}))
        )
        if fresh_validation != recovered_validation:
            raise RebuilderError("fresh protected validation differs from recovered Android v2")
        android.verify(
            paths["androidV2"], paths["signedAab"], lease.paths["sourceGraph"],
            paths["signedSidecar"], lease.paths["twoGreenReceipt"],
            lease.paths["twoGreenApproval"],
        )
    except Exception as error:
        if isinstance(error, RebuilderError):
            raise
        raise RebuilderError("recovered Android v2 evidence failed exact consumer verification") from error
    validate_external_signer_attestation(
        android, paths["externalV1"], request, rebuilt, signed, graph_raw,
        lease.toolchain, paths["androidV2"], lock["approval_authority"],
    )
    lease.assert_exact()

    # Always go through the reviewed signed ledger adapter.  A local recovery
    # file can never substitute for service-authenticated status/commit replay.
    ledger_commit = commit_signing_attempt(
        client, subject, reservation, paths["externalV1"]
    )
    external_raw = _stable_bytes(
        paths["externalV1"], "external signer v1 attestation", 32 * 1024,
        owner_only=True,
    )
    selected_ledger_commit = _select_authenticated_ledger_commit(
        directory, ledger, client, ledger_commit, subject, reservation,
        external_raw, lock["limits"]["json_bytes"],
    )
    audit = fleet_audit(
        lock, lock_raw, request_raw, graph_raw, rebuilt, signed,
        lease.toolchain, selected_ledger_commit, paths["androidV2"], paths["externalV1"],
    )
    _write_or_match(
        paths["audit"], _pretty_json(audit), "Fleet external rebuild audit",
        lock["limits"]["json_bytes"],
    )
    _validate_recovery_inventory(directory, require_final=True)
    if directory == recovery:
        os.replace(recovery, output_dir)
    # Also repair an earlier promotion whose rename succeeded but whose source
    # or destination parent fsync acknowledgement was lost.
    _fsync_directory(recovery.parent)
    _fsync_directory(output_dir.parent)
    return audit


def contract_check(lock_path: Path) -> dict[str, Any]:
    lock, raw = load_lock(lock_path)
    blockers = validate_lock(lock, raw)
    return {"contract_name": "fleet.android_preview12_external_rebuilder_check.v1", "status": "dormant" if blockers else "ready",
            "blockers": blockers, "android_attestation_contract": ANDROID_ATTESTATION_CONTRACT,
            "fleet_audit_contract": FLEET_AUDIT_CONTRACT, "signing_performed": False,
            "google_play_upload_performed": False, "publication_performed": False}


def _offline_feed_argument(value: str, kind: str) -> Path:
    path = Path(value)
    if os.fspath(path) != value:
        raise argparse.ArgumentTypeError(f"offline {kind} feed path must not contain aliases or be empty")
    return path


def _offline_nuget_feed_argument(value: str) -> Path:
    return _offline_feed_argument(value, "NuGet")


def _offline_aar_feed_argument(value: str) -> Path:
    return _offline_feed_argument(value, "AAR")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("contract-check")
    compatibility = commands.add_parser("consumer-check")
    compatibility.add_argument("--android-root", required=True, type=Path)
    prepare = commands.add_parser("prepare-rebuild")
    for name in (
        "external-request", "producer-unsigned-aab", "producer-source-graph", "producer-sidecar",
        "two-green-receipt", "approval", "package-authority", "authority-root", "owner-feed",
        "ui-authority-receipt", "bundletool", "upload-certificate",
        "dotnet-root", "java-root", "android-sdk-root", "output-dir",
    ):
        prepare.add_argument(f"--{name}", required=True, type=Path)
    for name in ("java-tool-observation", "installed-closure-receipt"):
        prepare.add_argument(f"--{name}", required=True, type=Path,
                            help="separate canonical owner-only input; no legacy toolchain-authority fallback")
    prepare.add_argument("--builder-image", required=True)
    prepare.add_argument(
        "--offline-source-manifest", type=Path,
        help="absolute JSON path mapping all eight repositories to path, sha256 and size_bytes; source transport only",
    )
    prepare.add_argument(
        "--offline-nuget-feed", type=_offline_nuget_feed_argument,
        help="absolute canonical directory of offline packages; Android selects and validates the restore inputs",
    )
    prepare.add_argument(
        "--offline-aar-feed", type=_offline_aar_feed_argument,
        help="absolute canonical directory of offline Android archives; Android owns manifest and byte validation",
    )
    for name in ("test-bootstrap-dir", "test-wheelhouse", "test-oracle-root"):
        prepare.add_argument("--" + name, type=lambda value: _offline_feed_argument(value, "source-test"),
                            help="explicit offline test-only input; mandatory together for the admitted new test runner")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        lock, _raw = load_lock(arguments.lock.absolute())
        if arguments.command == "contract-check":
            result = contract_check(arguments.lock.absolute())
        elif arguments.command == "consumer-check":
            module = validate_android_consumer(arguments.android_root.absolute(), lock)
            # Do not invent a second schema.  The exact checked-out Android
            # consumer remains the only v2 field/canonicalization authority.
            result = {"contract_name": "fleet.android_preview12_android_v2_consumer_check.v1", "status": "pass",
                      "android_commit": lock["android_authority"]["commit"], "consumer_contract": module.CONTRACT,
                      "consumer_sha256": lock["android_authority"]["attestation_consumer"]["sha256"],
                      "signing_performed": False, "publication_performed": False}
        else:
            result = prepare_rebuild_handoff(
                arguments.lock.absolute(), arguments.external_request.absolute(),
                arguments.producer_unsigned_aab.absolute(), arguments.producer_source_graph.absolute(),
                arguments.producer_sidecar.absolute(), arguments.two_green_receipt.absolute(),
                arguments.approval.absolute(), arguments.package_authority.absolute(),
                arguments.authority_root.absolute(), arguments.owner_feed.absolute(),
                arguments.ui_authority_receipt.absolute(), arguments.java_tool_observation,
                arguments.installed_closure_receipt,
                arguments.bundletool.absolute(), arguments.upload_certificate.absolute(),
                arguments.dotnet_root.absolute(), arguments.java_root.absolute(),
                arguments.android_sdk_root.absolute(), arguments.output_dir.absolute(),
                arguments.builder_image,
                offline_source_manifest=arguments.offline_source_manifest,
                offline_nuget_feed=arguments.offline_nuget_feed,
                offline_aar_feed=arguments.offline_aar_feed,
                test_bootstrap_dir=arguments.test_bootstrap_dir,
                test_wheelhouse=arguments.test_wheelhouse,
                test_oracle_root=arguments.test_oracle_root,
            )
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError, RebuilderError) as error:
        print(f"android-preview12-external-rebuilder: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
