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
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Mapping


LOCK_CONTRACT = "fleet.android_preview12_external_rebuilder_lock.v1"
REQUEST_CONTRACT = "chummer.android.external-release-signer-request/v1"
ANDROID_ATTESTATION_CONTRACT = "chummer.android.release-build-attestation/v2"
FLEET_AUDIT_CONTRACT = "fleet.android_preview12_external_rebuild_audit.v3"
SOURCE_GRAPH_CONTRACT = "chummer.android.release-source-graph/v3"
LEDGER_POLICY_CONTRACT = "fleet.android_preview12_approval_ledger_policy.v1"
EXTERNAL_SIGNER_ATTESTATION_CONTRACT = "chummer.android.external-release-signer-attestation/v1"
REBUILD_HANDOFF_CONTRACT = "fleet.android_preview12_external_rebuild_handoff.v1"
PACKAGE_ID = "com.myexternalbrain.chummer"
VERSION_NAME = "0.1.0-preview.12"
VERSION_CODE = 12
MINIMUM_SDK = 24
TARGET_SDK = 36
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
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


def load_lock(path: Path) -> tuple[dict[str, Any], bytes]:
    value, raw = _json_file(path, "external rebuilder lock", 1024 * 1024)
    if value.get("contract_name") != LOCK_CONTRACT:
        raise RebuilderError("external rebuilder lock contract is not exact")
    return value, raw


def validate_lock(lock: Mapping[str, Any], lock_bytes: bytes, builder_image: str | None = None) -> list[str]:
    failures: list[str] = []
    expected_top = {
        "contract_name", "contract_version", "state", "release", "android_authority",
        "toolchain", "approval_authority", "upload_key", "rebuild", "reservation", "outputs", "limits",
    }
    if set(lock) != expected_top or lock.get("contract_version") != 1:
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
        "dotnet": ("10.0.110", 8899, 4232503090),
        "java": ("17.0.20.1", 454, 333699498),
    }
    for name, (version, count, size) in expected_tools.items():
        row = toolchain.get(name, {})
        if row.get("version") != version or row.get("file_count") != count or row.get("size_bytes") != size \
                or not HEX64.fullmatch(str(row.get("tree_sha256") or "")):
            failures.append(f"{name} closure is not exact")
    sdk = toolchain.get("android_sdk", {})
    if sdk.get("api_level") != 36 or sdk.get("build_tools_version") != "36.0.0" \
            or sdk.get("file_count") != 11670 or sdk.get("size_bytes") != 463020707 \
            or not HEX64.fullmatch(str(sdk.get("tree_sha256") or "")):
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
    if outputs.get("signed_content_handoff_enabled") is not True:
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
    for name in ("builder_image", "signer_image", "installed_closure_receipt_sha256"):
        if not toolchain.get(name):
            failures.append(f"toolchain.{name} is not configured")
    if toolchain.get("builder_image") and builder_image is not None \
            and builder_image != toolchain.get("builder_image"):
        failures.append("reported builder image differs from lock")
    for name in ("key_alias", "keystore_secret", "store_password_secret", "key_password_secret"):
        if not upload.get(name):
            failures.append(f"upload_key.{name} is not configured")
    if not approval.get("private_key_secret"):
        failures.append("approval attestation private-key secret is not configured")
    limits = lock.get("limits", {})
    for name in ("json_bytes", "aab_bytes", "git_timeout_seconds", "build_timeout_seconds", "reservation_timeout_seconds"):
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
        "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
    }
    completed = runner(
        ["/usr/bin/git", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always", *arguments],
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
            _git(runner, ["-C", os.fspath(root), "fetch", "--no-tags", "--filter=blob:none", "origin", row["commit"]], timeout=timeout)
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
    rows = validate_source_graph(graph)
    roots: dict[str, Path] = {}
    for name, (_role, relative, repository) in REPOSITORIES.items():
        root = workspace.joinpath(*PurePosixPath(relative).parts)
        if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root:
            raise RebuilderError(f"independent source checkout is missing or noncanonical: {name}")
        row = rows[name]
        status = _git(runner, ["-C", os.fspath(root), "status", "--porcelain", "--untracked-files=all"], timeout=timeout)
        head = _git(runner, ["-C", os.fspath(root), "rev-parse", "HEAD^{commit}"], timeout=timeout)
        tree = _git(runner, ["-C", os.fspath(root), "rev-parse", "HEAD^{tree}"], timeout=timeout)
        remote = _git(runner, ["-C", os.fspath(root), "remote", "get-url", "origin"], timeout=timeout)
        listing = _git(runner, ["-C", os.fspath(root), "ls-tree", "-r", "-z", "--full-tree", "HEAD"],
                       timeout=timeout, binary=True)
        assert isinstance(listing, bytes)
        if status or head != row["commit"] or tree != row["tree"] or remote != repository \
                or hashlib.sha256(listing).hexdigest() != row["tree_sha256"]:
            raise RebuilderError(f"independent source checkout differs from source graph: {name}")
        roots[name] = root
    return roots


def _trusted_root(path: Path, label: str) -> Path:
    if not path.is_absolute() or path.is_symlink() or not path.is_dir() or path.resolve(strict=True) != path:
        raise RebuilderError(f"{label} is not one canonical toolchain root")
    for ancestor in (path, *path.parents):
        metadata = ancestor.stat()
        if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
            raise RebuilderError(f"{label} ancestry is not immutable root-owned authority")
    return path


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
            if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o022:
                raise RebuilderError(f"{label} contains writable or non-root-owned content")
            if entry.is_symlink():
                target = os.readlink(path)
                if not path.resolve(strict=True).is_relative_to(root):
                    raise RebuilderError(f"{label} symlink escapes its trusted root")
                row = f"L\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\0{target}\n".encode()
            elif entry.is_dir(follow_symlinks=False):
                pending.append(path)
                row = f"D\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\n".encode()
            elif entry.is_file(follow_symlinks=False):
                count += 1
                total += metadata.st_size
                if count > 250_000 or total > 16 * 1024 * 1024 * 1024:
                    raise RebuilderError(f"{label} exceeds its closure bound")
                raw = path.read_bytes()
                if len(raw) != metadata.st_size:
                    raise RebuilderError(f"{label} changed while hashing")
                row = (f"F\0{relative}\0{stat.S_IMODE(metadata.st_mode):o}\0{metadata.st_size}\0"
                       f"{hashlib.sha256(raw).hexdigest()}\n").encode()
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
    if not isinstance(signer_image, str) or not signer_image:
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


def verify_toolchain(
    lock: Mapping[str, Any], dotnet_root: Path, java_root: Path, android_sdk_root: Path,
    bundletool: Path, installed_closure_receipt: Path, reported_builder_image: str, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
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
    auxiliary = _bind_auxiliary_toolchain(
        lock, bundletool, installed_closure_receipt, reported_builder_image
    )
    closure = {"platform": "linux/amd64", **observed, **auxiliary}
    return {**closure, "closureSha256": hashlib.sha256(_canonical_json(closure)).hexdigest()}


def validate_android_consumer(android_root: Path, lock: Mapping[str, Any]):
    android = lock["android_authority"]
    if android_root.is_symlink() or not android_root.is_dir() or android_root.resolve(strict=True) != android_root:
        raise RebuilderError("Android consumer checkout is not canonical")
    head = _git(subprocess.run, ["-C", os.fspath(android_root), "rev-parse", "HEAD^{commit}"], timeout=30)
    tree = _git(subprocess.run, ["-C", os.fspath(android_root), "rev-parse", "HEAD^{tree}"], timeout=30)
    remote = _git(subprocess.run, ["-C", os.fspath(android_root), "remote", "get-url", "origin"], timeout=30)
    if (head, tree, remote) != (android["commit"], android["tree"], android["repository"]):
        raise RebuilderError("Android consumer checkout differs from qualified authority")
    for binding_name in ("build_script", "attestation_consumer", "two_green_verifier", "source_graph_verifier"):
        binding = android[binding_name]
        path = android_root.joinpath(*PurePosixPath(binding["path"]).parts)
        if _sha256_file(path, f"Android {binding_name}", 8 * 1024 * 1024) != binding["sha256"]:
            raise RebuilderError(f"Android {binding_name} bytes differ from lock")
    consumer_path = android_root / android["attestation_consumer"]["path"]
    prior_release_root = os.environ.get("CHUMMER_RELEASE_REPO_ROOT")
    os.environ["CHUMMER_RELEASE_REPO_ROOT"] = os.fspath(android_root)
    try:
        spec = importlib.util.spec_from_file_location("fleet_android_v2_consumer", consumer_path)
        if spec is None or spec.loader is None:
            raise RebuilderError("cannot load exact Android v2 consumer")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if prior_release_root is None:
            os.environ.pop("CHUMMER_RELEASE_REPO_ROOT", None)
        else:
            os.environ["CHUMMER_RELEASE_REPO_ROOT"] = prior_release_root
    approval = lock["approval_authority"]
    public_key = android_root.joinpath(*PurePosixPath(approval["public_key_path"]).parts)
    if module.CONTRACT != ANDROID_ATTESTATION_CONTRACT \
            or module.EXPECTED_UPLOAD_CERTIFICATE_SHA256.replace(":", "").lower() != UPLOAD_CERTIFICATE_SHA256 \
            or module.VERIFY.RELEASE_APPROVER_KEY_ID != approval["key_id"] \
            or _sha256_file(public_key, "Android attestation public key", 64 * 1024) \
            != approval["public_key_sha256"]:
        raise RebuilderError("Android v2 consumer authority differs from lock")
    module._fleet_expected_spki_sha256 = approval["public_key_spki_sha256"]
    return module


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
    _write_exclusive(
        output,
        _stable_bytes(unsigned_aab, "unsigned AAB", lock["limits"]["aab_bytes"], owner_only=True),
    )
    try:
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
    except Exception:
        output.unlink(missing_ok=True)
        raise
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
    unsigned = android._unsigned(claims, qualification, validation, generated, challenge)
    if unsigned.get("contractName") != ANDROID_ATTESTATION_CONTRACT or set(unsigned).intersection({"contract_name", "fleetAudit"}):
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
    try:
        android.verify(output, signed_aab, graph, sidecar, two_green_receipt, approval)
        if output.read_bytes() != android._pretty(value) or not output.read_bytes().endswith(b"\n"):
            raise RebuilderError("Android v2 attestation bytes are not exact pretty JSON with one trailing newline")
    except Exception:
        output.unlink(missing_ok=True)
        raise
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


def load_reviewed_ledger(fleet_root: Path, lock: Mapping[str, Any], environment: Mapping[str, str]):
    """Load Draft #11's reviewed signed/no-redirect ledger after it is merged.

    The checked-in lock has null digests and therefore cannot reach this code.
    No endpoint or response dialect is implemented by this module.
    """

    reservation = lock["reservation"]
    if not fleet_root.is_absolute() or fleet_root.is_symlink() or fleet_root.resolve(strict=True) != fleet_root:
        raise RebuilderError("Fleet signer root is not canonical")
    adapter = fleet_root.joinpath(*PurePosixPath(reservation["adapter_path"]).parts)
    policy_path = fleet_root.joinpath(*PurePosixPath(reservation["policy_path"]).parts)
    if _sha256_file(adapter, "reviewed approval-ledger adapter", 2 * 1024 * 1024) \
            != reservation["adapter_sha256"] \
            or _sha256_file(policy_path, "reviewed approval-ledger policy", 1024 * 1024) \
            != reservation["policy_sha256"]:
        raise RebuilderError("reviewed durable approval-ledger bytes differ from lock")
    spec = importlib.util.spec_from_file_location("fleet_preview12_reviewed_ledger", adapter)
    if spec is None or spec.loader is None:
        raise RebuilderError("reviewed durable approval-ledger adapter cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy, policy_sha256 = module.load_policy(policy_path)
    ledger_policy = module.validate_ledger_policy(
        policy["replay_protection"]["external_ledger"], require_configured=True
    )
    client = module.DurableApprovalLedgerClient(ledger_policy, environment)
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
    receipt = committed.get("receipt", {})
    approval = receipt.get("approval", {})
    if receipt.get("state") != "committed" \
            or approval.get("sha256") != hashlib.sha256(raw).hexdigest() \
            or approval.get("sizeBytes") != len(raw):
        raise RebuilderError("durable ledger did not commit exact external signer v1 bytes")
    return committed


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


def _run_independent_rebuild(
    lock: Mapping[str, Any],
    workspace: Path,
    two_green_receipt: Path,
    approval: Path,
    package_authority: Path,
    authority_root: Path,
    owner_feed: Path,
    ui_authority_receipt: Path,
    toolchain_authority: Path,
    bundletool: Path,
    upload_certificate: Path,
    dotnet_root: Path,
    java_root: Path,
    android_sdk_root: Path,
    build_input_root: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> tuple[Path, Path]:
    build_input_root.mkdir(mode=0o700)
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
        "CHUMMER_ANDROID_RELEASE_TOOLCHAIN_AUTHORITY": os.fspath(toolchain_authority),
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
    build_script = workspace / "chummer-android/scripts/build-release.sh"
    stdout_path, stderr_path = build_input_root / "build.stdout", build_input_root / "build.stderr"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = runner(
            ["/bin/bash", "-p", os.fspath(build_script)], cwd=workspace / "chummer-android",
            env=environment, check=False, stdout=stdout, stderr=stderr,
            timeout=lock["limits"]["build_timeout_seconds"],
        )
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
    ui_authority_receipt: Path, toolchain_authority: Path, bundletool: Path,
    upload_certificate: Path, dotnet_root: Path, java_root: Path,
    android_sdk_root: Path, output_dir: Path, reported_builder_image: str, *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict[str, Any]:
    """Run the secret-free rebuild stage in a job with no credential mounts."""

    lock, lock_raw = load_lock(lock_path)
    failures = validate_lock(lock, lock_raw, reported_builder_image)
    if failures:
        raise RebuilderError("; ".join(failures))
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
        checkout_source_graph(graph, workspace, runner=runner, timeout=lock["limits"]["git_timeout_seconds"])
        android = validate_android_consumer(workspace / "chummer-android", lock)
        toolchain = verify_toolchain(
            lock, dotnet_root, java_root, android_sdk_root,
            bundletool, toolchain_authority, reported_builder_image, runner=runner,
        )
        qualification = android.VERIFY.verify_release_eligibility(
            two_green_receipt, approval, android_root=workspace / "chummer-android",
            expected_version_name=VERSION_NAME, expected_version_code=VERSION_CODE,
            source_graph_path=source_graph_copy,
        )
        android._sidecar_claims(producer_sidecar, producer_unsigned_aab, producer_source_graph)
        rebuilt_aab, rebuilt_graph = _run_independent_rebuild(
            lock, workspace, two_green_receipt, approval, package_authority, authority_root, owner_feed,
            ui_authority_receipt, toolchain_authority, bundletool, upload_certificate,
            dotnet_root, java_root, android_sdk_root, stage / "build-input", runner=runner,
        )
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


def contract_check(lock_path: Path) -> dict[str, Any]:
    lock, raw = load_lock(lock_path)
    blockers = validate_lock(lock, raw)
    return {"contract_name": "fleet.android_preview12_external_rebuilder_check.v1", "status": "dormant" if blockers else "ready",
            "blockers": blockers, "android_attestation_contract": ANDROID_ATTESTATION_CONTRACT,
            "fleet_audit_contract": FLEET_AUDIT_CONTRACT, "signing_performed": False,
            "google_play_upload_performed": False, "publication_performed": False}


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
        "ui-authority-receipt", "toolchain-authority", "bundletool", "upload-certificate",
        "dotnet-root", "java-root", "android-sdk-root", "output-dir",
    ):
        prepare.add_argument(f"--{name}", required=True, type=Path)
    prepare.add_argument("--builder-image", required=True)
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
                arguments.ui_authority_receipt.absolute(), arguments.toolchain_authority.absolute(),
                arguments.bundletool.absolute(), arguments.upload_certificate.absolute(),
                arguments.dotnet_root.absolute(), arguments.java_root.absolute(),
                arguments.android_sdk_root.absolute(), arguments.output_dir.absolute(),
                arguments.builder_image,
            )
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError, RebuilderError) as error:
        print(f"android-preview12-external-rebuilder: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
