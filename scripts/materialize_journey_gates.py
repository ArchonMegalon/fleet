#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic
    from scripts.materialize_support_case_packets import _refresh_weekly_governor_packet_if_possible
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic
    from materialize_support_case_packets import _refresh_weekly_governor_packet_if_possible


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
DEFAULT_STATUS_PLANE = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEFAULT_PROGRESS_REPORT = ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY = ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_SUPPORT_PACKETS = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
REGISTRY_CANDIDATES = (
    ROOT / ".codex-design" / "product" / "GOLDEN_JOURNEY_RELEASE_GATES.yaml",
    Path("/docker/chummercomplete/chummer-design/products/chummer/GOLDEN_JOURNEY_RELEASE_GATES.yaml"),
)

STAGE_ORDER = {
    "pre_repo_local_complete": 0,
    "repo_local_complete": 1,
    "package_canonical": 2,
    "boundary_pure": 3,
    "publicly_promoted": 4,
}
PROMOTION_ORDER = {
    "internal": 0,
    "protected_preview": 1,
    "public": 2,
}
ARTIFACT_STALE_HOURS = {
    "compile_manifest": 24,
    "status_plane": 24,
    "support_packets": 24,
    "progress_report": 24 * 7,
    "progress_history": 24 * 7,
}
RECOVERY_ACTION_HREF_MAP = {
    "open_downloads": "/downloads",
    "open_support_timeline": "/account/support",
    "open_account_access": "/account/access",
}
REPO_ROOT_CANDIDATES = {
    "fleet": (ROOT,),
    "chummer6-design": (Path("/docker/chummercomplete/chummer-design"),),
    "chummer6-core": (
        Path("/docker/chummercomplete/chummer6-core"),
        Path("/docker/chummercomplete/chummer-core-engine"),
    ),
    "chummer6-hub": (
        Path("/docker/chummercomplete/chummer6-hub"),
        Path("/docker/chummercomplete/chummer.run-services"),
    ),
    "chummer6-hub-registry": (Path("/docker/chummercomplete/chummer-hub-registry"),),
    "chummer6-ui": (
        Path("/docker/chummercomplete/chummer6-ui"),
        Path("/docker/chummercomplete/chummer6-ui-finish"),
    ),
    "chummer6-mobile": (Path("/docker/chummercomplete/chummer6-mobile"),),
    "chummer6-media-factory": (
        Path("/docker/chummercomplete/chummer-media-factory"),
        Path("/docker/fleet/repos/chummer-media-factory"),
    ),
    "executive-assistant": (Path("/docker/EA"),),
}

EXTERNAL_BLOCKER_MARKERS = (
    "external proof request: capture",
    "requires a windows-capable host",
    "requires a macos host",
    "requires a linux host",
    "current host cannot run promoted windows installer smoke",
    "current host cannot run promoted macos installer smoke",
    "current host cannot run promoted linux installer smoke",
)

RELEASE_CHANNEL_PLATFORM_COVERAGE_MARKERS = (
    "release_channel.generated.json field 'desktoptuplecoverage.missingrequiredplatforms'",
    "release_channel.generated.json field 'desktoptuplecoverage.missingrequiredplatformheadpairs'",
    "release_channel.generated.json field 'desktoptuplecoverage.missingrequiredplatformheadridtuples'",
)
REQUIRED_EXTERNAL_PROOF_TOKENS = ("promoted_installer_artifact", "startup_smoke_receipt")
SUPPORTED_DESKTOP_PLATFORMS = ("linux", "macos", "windows")
SUPPORTED_DESKTOP_HEADS = ("avalonia", "blazor-desktop")


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(ts: dt.datetime) -> str:
    return ts.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_json_path(payload: Any, path: str) -> Any:
    current = payload
    for segment in [part.strip() for part in str(path).split(".") if part.strip()]:
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
            continue
        if isinstance(current, list):
            try:
                index = int(segment)
            except ValueError:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _release_channel_external_proof_requests(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    release_channel_id = str(payload.get("channelId") or payload.get("channel") or "").strip().lower()

    def _default_installer_file_name(head: str, rid: str, platform: str) -> str:
        platform_token = str(platform or "").strip().lower()
        if platform_token == "windows":
            suffix = ".exe"
        elif platform_token == "macos":
            suffix = ".dmg"
        elif platform_token == "linux":
            suffix = ".deb"
        else:
            suffix = ""
        if not head or not rid:
            return ""
        return f"chummer-{head}-{rid}-installer{suffix}"

    def _parse_tuple_identity(tuple_id: str) -> Tuple[str, str, str]:
        raw = str(tuple_id or "").strip()
        if not raw:
            return "", "", ""
        parts = [part.strip() for part in raw.split(":")]
        if len(parts) != 3:
            return "", "", ""
        return parts[0].lower(), parts[1].lower(), parts[2].lower()

    def _required_receipt_contract(head: str, rid: str, platform: str, required_host: str) -> Dict[str, Any]:
        host_value = required_host.strip().lower() or platform.strip().lower() or "required"
        return {
            "status_any_of": ["pass", "passed", "ready"],
            "ready_checkpoint": "pre_ui_event_loop",
            "head_id": head,
            "platform": platform,
            "rid": rid,
            "host_class_contains": host_value,
        }

    def _default_launch_target(head: str, platform: str) -> str:
        head_token = str(head or "").strip().lower()
        platform_token = str(platform or "").strip().lower()
        if head_token == "blazor-desktop":
            return "Chummer.Blazor.Desktop.exe" if platform_token == "windows" else "Chummer.Blazor.Desktop"
        return "Chummer.Avalonia.exe" if platform_token == "windows" else "Chummer.Avalonia"

    def _proof_capture_commands(
        *,
        head: str,
        rid: str,
        platform: str,
        installer_file_name: str,
        expected_installer_sha256: str,
        required_host: str,
        release_version: str,
    ) -> List[str]:
        if not head or not rid:
            return []
        repo_root = "/docker/chummercomplete/chummer6-ui"
        installer_name = installer_file_name or _default_installer_file_name(head=head, rid=rid, platform=platform)
        if not installer_name:
            return []
        host_class = required_host or platform or "required"
        operating_system_hint = {
            "windows": "Windows",
            "macos": "macOS",
            "linux": "Linux",
        }.get(host_class, "")
        expected_sha256 = str(expected_installer_sha256 or "").strip().lower()
        release_version_suffix = f" {release_version}" if release_version else ""
        preflight_download = ""
        if expected_sha256:
            preflight_download = (
                f"cd {repo_root} && "
                f"mkdir -p {repo_root}/Docker/Downloads/files && "
                "python3 -c 'import hashlib, pathlib; "
                f"p=pathlib.Path('\"'\"'{repo_root}/Docker/Downloads/files/{installer_name}'\"'\"'); "
                f"expected='\"'\"'{expected_sha256}'\"'\"'; "
                "import sys; "
                "sys.exit(0) if (not p.is_file()) else None; "
                "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
                "sys.exit(0) if digest==expected else "
                "print(f'\"'\"'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}'\"'\"') or p.unlink()' "
                f"&& if [ ! -s {repo_root}/Docker/Downloads/files/{installer_name} ]; then "
                "if [ -z \"${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}\" ] && "
                "   [ -z \"${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}\" ] && "
                "   [ -z \"${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}\" ] && "
                "   [ \"${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}\" != \"1\" ]; then "
                "  echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, "
                "CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR "
                "(or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; "
                "  exit 1; "
                "fi; "
                "curl_auth_args=(); "
                "if [ -n \"${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}\" ]; then "
                "  curl_auth_args+=( -H \"${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}\" ); "
                "fi; "
                "if [ -n \"${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}\" ]; then "
                "  curl_auth_args+=( -H \"Cookie: ${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}\" ); "
                "fi; "
                "if [ -n \"${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}\" ]; then "
                "  curl_auth_args+=( --cookie \"${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}\" ); "
                "fi; "
                f"curl -fL --retry 3 --retry-delay 2 ${{curl_auth_args[@]}} "
                f"\"${{CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}}/downloads/install/{head}-{rid}-installer\" "
                f"-o {repo_root}/Docker/Downloads/files/{installer_name}; "
                "fi; "
                "python3 -c 'import os, pathlib, sys; "
                f"p=pathlib.Path('\"'\"'{repo_root}/Docker/Downloads/files/{installer_name}'\"'\"'); "
                "expected_magic='\"'\"''\"'\"'; "
                "sys.exit(f'\"'\"'installer-download-missing:{p}'\"'\"') if (not p.is_file()) else None; "
                "probe=p.read_bytes()[:8192]; "
                "probe_text=probe.decode('\"'\"'latin-1'\"'\"', errors='\"'\"'ignore'\"'\"').lower(); "
                "auth_header_set=bool(str(os.environ.get('\"'\"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'\"'\"','\"'\"''\"'\"')).strip()); "
                "cookie_header_set=bool(str(os.environ.get('\"'\"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'\"'\"','\"'\"''\"'\"')).strip()); "
                "cookie_jar_set=bool(str(os.environ.get('\"'\"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'\"'\"','\"'\"''\"'\"')).strip()); "
                "html_like=('\"'\"'<!doctype html'\"'\"' in probe_text) or ('\"'\"'<html'\"'\"' in probe_text) or ('\"'\"'<head'\"'\"' in probe_text); "
                "sys.exit(f'\"'\"'installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-missing-auth'\"'\"') if html_like else None; "
                "sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode('\"'\"'latin-1'\"'\"'))) else "
                "sys.exit(f'\"'\"'installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=unexpected-binary-format-or-route-response'\"'\"')'; "
                "python3 -c 'import hashlib, os, pathlib, sys; "
                f"p=pathlib.Path('\"'\"'{repo_root}/Docker/Downloads/files/{installer_name}'\"'\"'); "
                f"expected='\"'\"'{expected_sha256}'\"'\"'; "
                "sys.exit(f'\"'\"'installer-download-missing:{p}'\"'\"') if (not p.is_file()) else None; "
                "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
                "auth_header_set=bool(str(os.environ.get('\"'\"'CHUMMER_EXTERNAL_PROOF_AUTH_HEADER'\"'\"','\"'\"''\"'\"')).strip()); "
                "cookie_header_set=bool(str(os.environ.get('\"'\"'CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER'\"'\"','\"'\"''\"'\"')).strip()); "
                "cookie_jar_set=bool(str(os.environ.get('\"'\"'CHUMMER_EXTERNAL_PROOF_COOKIE_JAR'\"'\"','\"'\"''\"'\"')).strip()); "
                "sys.exit(0) if digest==expected else "
                "sys.exit(f'\"'\"'installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:hint=signed-in-download-route-required-or-bytes-drift'\"'\"')'"
            )
        run_smoke = (
            f"cd {repo_root} && "
            f"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS={host_class}-host "
            f"{f'CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM={operating_system_hint} ' if operating_system_hint else ''}"
            "./scripts/run-desktop-startup-smoke.sh "
            f"{repo_root}/Docker/Downloads/files/{installer_name} "
            f"{head} "
            f"{rid} "
            f"{_default_launch_target(head=head, platform=platform)} "
            f"{repo_root}/Docker/Downloads/startup-smoke"
            f"{release_version_suffix}"
        )
        refresh_manifest = (
            f"cd {repo_root} && "
            "./scripts/generate-releases-manifest.sh"
        )
        commands: List[str] = []
        if preflight_download:
            commands.append(preflight_download)
        commands.extend([run_smoke, refresh_manifest])
        return commands

    def _normalize_proof_capture_command(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        host_class_match = re.search(r"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=([^\s]+)", raw)
        host_class_value = ""
        if host_class_match is not None:
            host_class_value = host_class_match.group(1).strip().lower().removesuffix("-host")
        normalized = re.sub(
            r"\s*CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=[^\s]+",
            "",
            raw,
            count=1,
        )
        if "./scripts/run-desktop-startup-smoke.sh" in normalized and host_class_value:
            operating_system_hint = {
                "windows": "Windows",
                "macos": "macOS",
                "linux": "Linux",
            }.get(host_class_value, "")
            if operating_system_hint:
                normalized = re.sub(
                    r"(CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=[^\s]+)",
                    rf"\1 CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM={operating_system_hint}",
                    normalized,
                    count=1,
                )
        return re.sub(r"\s{2,}", " ", normalized).strip()

    def _sanitize_proof_capture_command(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        normalized = raw
        host_class_match = re.search(r"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=([^\s]+)", raw)
        host_class_value = ""
        if host_class_match is not None:
            host_class_value = host_class_match.group(1).strip().lower().removesuffix("-host")
        normalized = re.sub(
            r"\s*CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=[^\s]+",
            "",
            normalized,
            count=1,
        )
        if "./scripts/run-desktop-startup-smoke.sh" in normalized and host_class_value:
            operating_system_hint = {
                "windows": "Windows",
                "macos": "macOS",
                "linux": "Linux",
            }.get(host_class_value, "")
            if operating_system_hint:
                normalized = re.sub(
                    r"(CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=[^\s]+)",
                    rf"\1 CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM={operating_system_hint}",
                    normalized,
                    count=1,
                )
        return re.sub(r"\s{2,}", " ", normalized).strip()

    release_version = str(payload.get("version") or payload.get("releaseVersion") or "").strip()
    coverage = dict(payload.get("desktopTupleCoverage") or {})
    source_requests = coverage.get("externalProofRequests")
    if not isinstance(source_requests, list):
        return []
    requests: List[Dict[str, Any]] = []
    for item in source_requests:
        if not isinstance(item, dict):
            continue
        tuple_id = str(item.get("tupleId") or "").strip()
        required_host = str(item.get("requiredHost") or item.get("platform") or "").strip().lower()
        required_host_provided = bool(str(item.get("requiredHost") or "").strip())
        required_proofs = item.get("requiredProofs")
        if not tuple_id or not isinstance(required_proofs, list):
            continue
        proof_tokens = [
            str(token or "").strip().lower()
            for token in required_proofs
            if str(token or "").strip()
        ]
        if not proof_tokens:
            continue
        head, rid, platform = _parse_tuple_identity(tuple_id)
        canonical_tuple_id = f"{head}:{rid}:{platform}" if head and rid and platform else ""
        tuple_identity_valid = bool(head and rid and platform)
        tuple_identity_canonical = bool(tuple_identity_valid and tuple_id == canonical_tuple_id)
        required_host_matches_tuple_platform = not bool(required_host) or not tuple_identity_valid or required_host == platform
        effective_required_host = required_host or platform
        canonical_expected_artifact_id = f"{head}-{rid}-installer" if head and rid else ""
        canonical_expected_installer_file_name = _default_installer_file_name(head=head, rid=rid, platform=platform)
        canonical_expected_public_install_route = (
            f"/downloads/install/{head}-{rid}-installer"
            if head and rid
            else ""
        )
        canonical_expected_installer_relative_path = (
            f"files/{canonical_expected_installer_file_name}"
            if canonical_expected_installer_file_name
            else ""
        )
        provided_expected_installer_sha256 = str(
            item.get("expectedInstallerSha256") or item.get("expected_installer_sha256") or ""
        ).strip().lower()
        canonical_expected_startup_smoke_receipt_path = (
            f"startup-smoke/startup-smoke-{head}-{rid}.receipt.json"
            if head and rid
            else ""
        )
        canonical_startup_smoke_receipt_contract = _required_receipt_contract(
            head=head,
            rid=rid,
            platform=platform,
            required_host=effective_required_host,
        )
        canonical_proof_capture_commands = _proof_capture_commands(
            head=head,
            rid=rid,
            platform=platform,
            installer_file_name=canonical_expected_installer_file_name,
            expected_installer_sha256=provided_expected_installer_sha256,
            required_host=effective_required_host,
            release_version=release_version,
        )
        canonical_proof_capture_commands_sanitized = [
            _sanitize_proof_capture_command(token)
            for token in canonical_proof_capture_commands
            if _sanitize_proof_capture_command(token)
        ]
        canonical_proof_capture_commands_normalized = [
            _normalize_proof_capture_command(token)
            for token in canonical_proof_capture_commands
            if _normalize_proof_capture_command(token)
        ]
        provided_expected_artifact_id = str(item.get("expectedArtifactId") or "").strip()
        provided_expected_installer_file_name = str(item.get("expectedInstallerFileName") or "").strip()
        provided_expected_installer_relative_path = str(item.get("expectedInstallerRelativePath") or "").strip()
        provided_expected_public_install_route = str(item.get("expectedPublicInstallRoute") or "").strip()
        provided_expected_startup_smoke_receipt_path = str(item.get("expectedStartupSmokeReceiptPath") or "").strip()
        row_channel_id_raw = str(item.get("channelId") or item.get("channel") or "").strip().lower()
        row_head_raw = str(item.get("head") or item.get("headId") or "").strip().lower()
        row_platform_raw = str(item.get("platform") or "").strip().lower()
        row_rid_raw = str(item.get("rid") or "").strip().lower()
        provided_smoke_contract = item.get("startupSmokeReceiptContract")
        provided_smoke_contract_normalized = (
            {
                "status_any_of": sorted(
                    {
                        str(token or "").strip().lower()
                        for token in (provided_smoke_contract.get("statusAnyOf") or [])
                        if str(token or "").strip()
                    }
                ),
                "ready_checkpoint": str(provided_smoke_contract.get("readyCheckpoint") or "").strip().lower(),
                "head_id": str(provided_smoke_contract.get("headId") or "").strip().lower(),
                "platform": str(provided_smoke_contract.get("platform") or "").strip().lower(),
                "rid": str(provided_smoke_contract.get("rid") or "").strip().lower(),
                "host_class_contains": str(provided_smoke_contract.get("hostClassContains") or "").strip().lower(),
            }
            if isinstance(provided_smoke_contract, dict)
            else {}
        )
        provided_commands = item.get("proofCaptureCommands")
        provided_commands_normalized = (
            [_normalize_proof_capture_command(token) for token in provided_commands if _normalize_proof_capture_command(token)]
            if isinstance(provided_commands, list)
            else []
        )
        provided_commands_sanitized = (
            [_sanitize_proof_capture_command(token) for token in provided_commands if _sanitize_proof_capture_command(token)]
            if isinstance(provided_commands, list)
            else []
        )
        request_payload: Dict[str, Any] = {
                "tuple_id": tuple_id,
                "channel_id": release_channel_id,
                "required_host": effective_required_host or "required",
                "required_host_provided": required_host_provided,
                "required_proofs": sorted(set(proof_tokens)),
                "head_id": head,
                "rid": rid,
                "platform": platform,
                "row_channel_id": row_channel_id_raw or release_channel_id,
                "row_channel_id_provided": bool(row_channel_id_raw),
                "row_channel_matches_release_channel": not bool(row_channel_id_raw) or row_channel_id_raw == release_channel_id,
                "row_head": row_head_raw,
                "row_platform": row_platform_raw,
                "row_rid": row_rid_raw,
                "row_head_provided": bool(row_head_raw),
                "row_platform_provided": bool(row_platform_raw),
                "row_rid_provided": bool(row_rid_raw),
                "row_identity_matches_tuple": bool(row_head_raw and row_platform_raw and row_rid_raw)
                and row_head_raw == head
                and row_platform_raw == platform
                and row_rid_raw == rid,
                "tuple_identity_valid": tuple_identity_valid,
                "tuple_identity_canonical": tuple_identity_canonical,
                "required_host_matches_tuple_platform": required_host_matches_tuple_platform,
                "expected_artifact_id": provided_expected_artifact_id or canonical_expected_artifact_id,
                "expected_installer_file_name": provided_expected_installer_file_name or canonical_expected_installer_file_name,
                "expected_installer_relative_path": (
                    provided_expected_installer_relative_path or canonical_expected_installer_relative_path
                ),
                "expected_public_install_route": provided_expected_public_install_route or canonical_expected_public_install_route,
                "expected_startup_smoke_receipt_path": provided_expected_startup_smoke_receipt_path or canonical_expected_startup_smoke_receipt_path,
                "expected_artifact_id_provided": bool(provided_expected_artifact_id),
                "expected_installer_file_name_provided": bool(provided_expected_installer_file_name),
                "expected_installer_relative_path_provided": bool(provided_expected_installer_relative_path),
                "expected_public_install_route_provided": bool(provided_expected_public_install_route),
                "expected_startup_smoke_receipt_path_provided": bool(provided_expected_startup_smoke_receipt_path),
                "startup_smoke_receipt_contract_provided": isinstance(provided_smoke_contract, dict),
                "proof_capture_commands_provided": isinstance(provided_commands, list),
                "canonical_expected_artifact_id": canonical_expected_artifact_id,
                "canonical_expected_installer_file_name": canonical_expected_installer_file_name,
                "canonical_expected_installer_relative_path": canonical_expected_installer_relative_path,
                "canonical_expected_public_install_route": canonical_expected_public_install_route,
                "canonical_expected_startup_smoke_receipt_path": canonical_expected_startup_smoke_receipt_path,
                "canonical_startup_smoke_receipt_contract": canonical_startup_smoke_receipt_contract,
                "canonical_proof_capture_commands": canonical_proof_capture_commands_sanitized,
                "startup_smoke_receipt_contract": (
                    provided_smoke_contract_normalized
                    if isinstance(provided_smoke_contract, dict)
                    else canonical_startup_smoke_receipt_contract
                ),
                "proof_capture_commands": (
                    provided_commands_sanitized
                    if isinstance(provided_commands, list)
                    else canonical_proof_capture_commands_sanitized
                ),
            }
        if provided_expected_installer_sha256:
            request_payload["expected_installer_sha256"] = provided_expected_installer_sha256
            request_payload["expected_installer_sha256_provided"] = True
        requests.append(request_payload)
    deduped_by_tuple: Dict[str, Dict[str, Any]] = {}
    tuple_occurrence_counts: Dict[str, int] = {}
    for request in requests:
        tuple_id_key = str(request.get("tuple_id") or "").strip().lower()
        if tuple_id_key:
            tuple_occurrence_counts[tuple_id_key] = tuple_occurrence_counts.get(tuple_id_key, 0) + 1
            deduped_by_tuple[tuple_id_key] = request
    deduped_requests = [deduped_by_tuple[key] for key in sorted(deduped_by_tuple.keys())]
    for item in deduped_requests:
        tuple_id_key = str(item.get("tuple_id") or "").strip().lower()
        item["tuple_entry_count"] = tuple_occurrence_counts.get(tuple_id_key, 0)
        item["tuple_unique"] = tuple_occurrence_counts.get(tuple_id_key, 0) <= 1
    return deduped_requests


EXTERNAL_PROOF_REQUEST_PUBLIC_KEYS: Tuple[str, ...] = (
    "tuple_id",
    "channel_id",
    "required_host",
    "required_proofs",
    "head_id",
    "rid",
    "platform",
    "tuple_identity_valid",
    "required_host_matches_tuple_platform",
    "expected_artifact_id",
    "expected_installer_file_name",
    "expected_installer_relative_path",
    "expected_installer_sha256",
    "expected_public_install_route",
    "expected_startup_smoke_receipt_path",
    "startup_smoke_receipt_contract",
    "proof_capture_commands",
    "tuple_entry_count",
    "tuple_unique",
)


def _public_external_proof_request(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: item.get(key)
        for key in EXTERNAL_PROOF_REQUEST_PUBLIC_KEYS
        if key in item
    }


def _release_channel_external_proof_reasons(payload: Dict[str, Any]) -> List[str]:
    requests = _release_channel_external_proof_requests(payload)
    reasons: List[str] = []
    release_channel_id = str(payload.get("channelId") or payload.get("channel") or "").strip().lower()
    coverage = dict(payload.get("desktopTupleCoverage") or {})
    required_desktop_platforms_value = coverage.get("requiredDesktopPlatforms")
    required_desktop_heads_value = coverage.get("requiredDesktopHeads")
    promoted_installer_tuples_value = coverage.get("promotedInstallerTuples")
    normalized_required_desktop_platforms: List[str] = []
    normalized_required_desktop_heads: List[str] = []
    if required_desktop_platforms_value is not None:
        if not isinstance(required_desktop_platforms_value, list):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.requiredDesktopPlatforms' "
                "must be an explicit list when present."
            )
        else:
            normalized_required_desktop_platforms = sorted(
                {
                    str(item or "").strip().lower()
                    for item in required_desktop_platforms_value
                    if str(item or "").strip()
                }
            )
    if required_desktop_heads_value is not None:
        if not isinstance(required_desktop_heads_value, list):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.requiredDesktopHeads' "
                "must be an explicit list when present."
            )
        else:
            normalized_required_desktop_heads = sorted(
                {
                    str(item or "").strip().lower()
                    for item in required_desktop_heads_value
                    if str(item or "").strip()
                }
            )
    promoted_head_platform_pairs: set[Tuple[str, str]] = set()
    if promoted_installer_tuples_value is not None:
        if not isinstance(promoted_installer_tuples_value, list):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.promotedInstallerTuples' "
                "must be an explicit list when present."
            )
        else:
            for index, row in enumerate(promoted_installer_tuples_value):
                row_id = f"desktopTupleCoverage.promotedInstallerTuples[{index}]"
                if not isinstance(row, dict):
                    reasons.append(
                        "release_channel.generated.json field "
                        f"'{row_id}' must be an object."
                    )
                    continue
                head = str(row.get("head") or "").strip().lower()
                platform = str(row.get("platform") or "").strip().lower()
                rid = str(row.get("rid") or "").strip().lower()
                tuple_id = str(row.get("tupleId") or "").strip()
                if not head or not platform or not rid:
                    reasons.append(
                        "release_channel.generated.json field "
                        f"'{row_id}' must include non-empty head/platform/rid."
                    )
                    continue
                canonical_tuple_id = f"{head}:{platform}:{rid}"
                if tuple_id and tuple_id != canonical_tuple_id:
                    reasons.append(
                        "release_channel.generated.json field "
                        f"'{row_id}.tupleId' must be lowercase canonical 'head:platform:rid' "
                        f"but was {tuple_id!r}."
                    )
                promoted_head_platform_pairs.add((head, platform))
    if (
        normalized_required_desktop_platforms
        and normalized_required_desktop_heads
        and isinstance(promoted_installer_tuples_value, list)
    ):
        expected_missing_platforms_from_promoted = sorted(
            {
                platform
                for platform in normalized_required_desktop_platforms
                if (not any(pair_platform == platform for _pair_head, pair_platform in promoted_head_platform_pairs))
            }
        )
        expected_missing_head_pairs_from_promoted = sorted(
            {
                f"{head}:{platform}"
                for head in normalized_required_desktop_heads
                for platform in normalized_required_desktop_platforms
                if (head, platform) not in promoted_head_platform_pairs
            }
        )
        reported_missing_platforms = coverage.get("missingRequiredPlatforms")
        if isinstance(reported_missing_platforms, list):
            normalized_reported_missing_platforms = sorted(
                {
                    str(item or "").strip().lower()
                    for item in reported_missing_platforms
                    if str(item or "").strip()
                }
            )
            if normalized_reported_missing_platforms != expected_missing_platforms_from_promoted:
                reasons.append(
                    "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatforms' "
                    "must match requiredDesktopPlatforms coverage derived from promotedInstallerTuples."
                )
        reported_missing_head_pairs = coverage.get("missingRequiredPlatformHeadPairs")
        if isinstance(reported_missing_head_pairs, list):
            normalized_reported_missing_head_pairs = sorted(
                {
                    str(item or "").strip().lower()
                    for item in reported_missing_head_pairs
                    if str(item or "").strip()
                }
            )
            if normalized_reported_missing_head_pairs != expected_missing_head_pairs_from_promoted:
                reasons.append(
                    "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadPairs' "
                    "must match requiredDesktopHeads x requiredDesktopPlatforms coverage derived from promotedInstallerTuples."
                )
        reported_complete = coverage.get("complete")
        if isinstance(reported_complete, bool):
            expected_complete_from_promoted = not bool(expected_missing_head_pairs_from_promoted)
            if reported_complete is not expected_complete_from_promoted:
                reasons.append(
                    "release_channel.generated.json field 'desktopTupleCoverage.complete' "
                    "must match requiredDesktopHeads x requiredDesktopPlatforms coverage derived from promotedInstallerTuples."
                )
    normalized_missing_platforms_for_posture = sorted(
        {
            str(item or "").strip().lower()
            for item in (coverage.get("missingRequiredPlatforms") or [])
            if str(item or "").strip()
        }
    ) if isinstance(coverage.get("missingRequiredPlatforms"), list) else []
    normalized_missing_head_pairs_for_posture = sorted(
        {
            str(item or "").strip().lower()
            for item in (coverage.get("missingRequiredPlatformHeadPairs") or [])
            if str(item or "").strip()
        }
    ) if isinstance(coverage.get("missingRequiredPlatformHeadPairs"), list) else []
    normalized_missing_tuples_for_posture = sorted(
        {
            str(item or "").strip().lower()
            for item in (coverage.get("missingRequiredPlatformHeadRidTuples") or [])
            if str(item or "").strip()
        }
    ) if isinstance(coverage.get("missingRequiredPlatformHeadRidTuples"), list) else []
    rollout_state = str(payload.get("rolloutState") or "").strip().lower()
    supportability_state = str(payload.get("supportabilityState") or "").strip().lower()
    declared_coverage_incomplete = bool(
        normalized_missing_platforms_for_posture
        or normalized_missing_head_pairs_for_posture
        or normalized_missing_tuples_for_posture
    )
    if declared_coverage_incomplete:
        if rollout_state and rollout_state != "coverage_incomplete":
            reasons.append(
                "release_channel.generated.json field 'rolloutState' must be 'coverage_incomplete' "
                "while desktopTupleCoverage reports missing platform/head/tuple inventory."
            )
        if supportability_state and supportability_state != "review_required":
            reasons.append(
                "release_channel.generated.json field 'supportabilityState' must be 'review_required' "
                "while desktopTupleCoverage reports missing platform/head/tuple inventory."
            )
    raw_external_proof_requests = coverage.get("externalProofRequests")
    if raw_external_proof_requests is not None:
        if not isinstance(raw_external_proof_requests, list):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests' "
                "must be an explicit list when present."
            )
        else:
            for index, raw_request in enumerate(raw_external_proof_requests):
                row_id = f"externalProofRequests[{index}]"
                if not isinstance(raw_request, dict):
                    reasons.append(
                        "release_channel.generated.json field "
                        f"'desktopTupleCoverage.{row_id}' must be an object."
                    )
                    continue
                tuple_id = str(raw_request.get("tupleId") or "").strip()
                required_proofs = raw_request.get("requiredProofs")
                if not tuple_id:
                    reasons.append(
                        "release_channel.generated.json field "
                        f"'desktopTupleCoverage.{row_id}.tupleId' must be a non-empty string."
                    )
                if not isinstance(required_proofs, list):
                    reasons.append(
                        "release_channel.generated.json field "
                        f"'desktopTupleCoverage.{row_id}.requiredProofs' must be an explicit list."
                    )
                    continue
                normalized_required_proofs = [
                    str(token or "").strip()
                    for token in required_proofs
                    if str(token or "").strip()
                ]
                if not normalized_required_proofs:
                    reasons.append(
                        "release_channel.generated.json field "
                        f"'desktopTupleCoverage.{row_id}.requiredProofs' must include at least one token."
                    )
    reported_missing_tuples = coverage.get("missingRequiredPlatformHeadRidTuples")
    reported_complete = coverage.get("complete")
    if reported_missing_tuples is not None and not isinstance(raw_external_proof_requests, list):
        reasons.append(
            "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests' "
            "must be an explicit list (empty when complete) whenever missingRequiredPlatformHeadRidTuples are declared."
        )
    if isinstance(reported_complete, bool) and not reported_complete and not isinstance(raw_external_proof_requests, list):
        reasons.append(
            "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests' "
            "must be an explicit list whenever desktopTupleCoverage.complete is false."
        )
    if not isinstance(reported_complete, bool):
        reasons.append(
            "release_channel.generated.json field 'desktopTupleCoverage.complete' must be an explicit boolean."
        )
    if requests and not isinstance(reported_missing_tuples, list):
        reasons.append(
            "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' "
            "must be an explicit list (empty when complete) whenever externalProofRequests are present."
        )
    request_tuple_ids = sorted(
        {
            str(item.get("tuple_id") or "").strip().lower()
            for item in requests
            if str(item.get("tuple_id") or "").strip()
        }
    )
    if isinstance(reported_missing_tuples, list):
        raw_reported_missing_tuples = [
            str(item or "").strip()
            for item in reported_missing_tuples
            if str(item or "").strip()
        ]
        canonical_reported_missing_tuples: List[str] = []
        noncanonical_missing_tuples: List[str] = []
        malformed_missing_tuple = False
        for tuple_id in raw_reported_missing_tuples:
            parts = [part.strip().lower() for part in tuple_id.split(":")]
            if len(parts) != 3 or not all(parts):
                malformed_missing_tuple = True
                continue
            canonical_tuple_id = ":".join(parts)
            canonical_reported_missing_tuples.append(canonical_tuple_id)
            if tuple_id != canonical_tuple_id:
                noncanonical_missing_tuples.append(tuple_id)
        if noncanonical_missing_tuples:
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' "
                "must contain lowercase canonical 'head:rid:platform' entries."
            )
        if len(canonical_reported_missing_tuples) != len(set(canonical_reported_missing_tuples)):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' "
                "must not contain duplicate entries."
            )
        normalized_reported_missing_tuples = sorted(
            {
                token
                for token in canonical_reported_missing_tuples
            }
        )
        if isinstance(reported_complete, bool):
            expected_complete = not bool(normalized_reported_missing_tuples)
            if reported_complete is not expected_complete:
                reasons.append(
                    "release_channel.generated.json field 'desktopTupleCoverage.complete' "
                    "must match missingRequiredPlatformHeadRidTuples completeness."
                )
        if normalized_reported_missing_tuples != request_tuple_ids:
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' "
                "must exactly match externalProofRequests tupleId inventory."
            )
        expected_missing_platforms: set[str] = set()
        expected_missing_head_pairs: set[str] = set()
        for tuple_id in normalized_reported_missing_tuples:
            parts = [part.strip().lower() for part in tuple_id.split(":")]
            if len(parts) != 3 or not all(parts):
                malformed_missing_tuple = True
                break
            head, _rid, platform = parts
            expected_missing_platforms.add(platform)
            expected_missing_head_pairs.add(f"{head}:{platform}")
        if malformed_missing_tuple:
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' "
                "must contain canonical 'head:rid:platform' entries."
            )
        else:
            reported_missing_platforms = coverage.get("missingRequiredPlatforms")
            if requests and not isinstance(reported_missing_platforms, list):
                reasons.append(
                    "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatforms' "
                    "must be an explicit list (empty when complete) whenever externalProofRequests are present."
                )
            elif isinstance(reported_missing_platforms, list):
                normalized_reported_missing_platforms = sorted(
                    {
                        str(item or "").strip().lower()
                        for item in reported_missing_platforms
                        if str(item or "").strip()
                    }
                )
                if normalized_reported_missing_platforms != sorted(expected_missing_platforms):
                    reasons.append(
                        "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatforms' "
                        "must match platforms implied by missingRequiredPlatformHeadRidTuples."
                    )
            reported_missing_head_pairs = coverage.get("missingRequiredPlatformHeadPairs")
            if requests and not isinstance(reported_missing_head_pairs, list):
                reasons.append(
                    "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadPairs' "
                    "must be an explicit list (empty when complete) whenever externalProofRequests are present."
                )
            elif isinstance(reported_missing_head_pairs, list):
                normalized_reported_missing_head_pairs = sorted(
                    {
                        str(item or "").strip().lower()
                        for item in reported_missing_head_pairs
                        if str(item or "").strip()
                    }
                )
                if normalized_reported_missing_head_pairs != sorted(expected_missing_head_pairs):
                    reasons.append(
                        "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadPairs' "
                        "must match head/platform pairs implied by missingRequiredPlatformHeadRidTuples."
                    )
    for item in requests:
        tuple_id = str(item.get("tuple_id") or "").strip()
        required_host = str(item.get("required_host") or "").strip().lower()
        tuple_head = str(item.get("head_id") or "").strip().lower()
        tuple_platform = str(item.get("platform") or "").strip().lower()
        proof_tokens = item.get("required_proofs")
        if not tuple_id or not isinstance(proof_tokens, list) or not proof_tokens:
            continue
        if not bool(item.get("tuple_identity_valid")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.tupleId' "
                f"must be canonical 'head:rid:platform' but was {tuple_id!r}."
            )
            continue
        if not bool(item.get("tuple_identity_canonical")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.tupleId' "
                f"must be lowercase canonical 'head:rid:platform' but was {tuple_id!r}."
            )
            continue
        if tuple_platform not in SUPPORTED_DESKTOP_PLATFORMS:
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.tupleId' "
                f"must use a supported desktop platform token {list(SUPPORTED_DESKTOP_PLATFORMS)!r} but tuple {tuple_id!r} "
                f"used {tuple_platform!r}."
            )
            continue
        if tuple_head not in SUPPORTED_DESKTOP_HEADS:
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.tupleId' "
                f"must use a supported desktop head token {list(SUPPORTED_DESKTOP_HEADS)!r} but tuple {tuple_id!r} "
                f"used {tuple_head!r}."
            )
            continue
        if required_host not in SUPPORTED_DESKTOP_PLATFORMS:
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.requiredHost' "
                f"must be one of {list(SUPPORTED_DESKTOP_PLATFORMS)!r} for tuple {tuple_id} but was {required_host!r}."
            )
            continue
        if not bool(item.get("required_host_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.requiredHost' "
                f"must be explicit for tuple {tuple_id}."
            )
            continue
        row_channel_id = str(item.get("row_channel_id") or "").strip().lower()
        if not bool(item.get("row_channel_id_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.channelId' "
                f"must be explicit for tuple {tuple_id}."
            )
            continue
        if not bool(item.get("row_channel_matches_release_channel")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.channelId' "
                f"must match release channel id {release_channel_id!r} for tuple {tuple_id} but was {row_channel_id!r}."
            )
            continue
        if not bool(item.get("row_head_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.head' "
                f"must be explicit for tuple {tuple_id}."
            )
            continue
        if not bool(item.get("row_platform_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.platform' "
                f"must be explicit for tuple {tuple_id}."
            )
            continue
        if not bool(item.get("row_rid_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.rid' "
                f"must be explicit for tuple {tuple_id}."
            )
            continue
        if not bool(item.get("row_identity_matches_tuple")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.head/platform/rid' "
                f"must match tuple-derived identity for {tuple_id}."
            )
            continue
        if not bool(item.get("tuple_unique")):
            duplicate_count = int(item.get("tuple_entry_count") or 0)
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests' "
                f"must contain unique tupleId entries, but tuple {tuple_id!r} appeared {duplicate_count} times."
            )
            continue
        if not bool(item.get("required_host_matches_tuple_platform")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.requiredHost' "
                f"must match tuple platform for {tuple_id} but was {required_host!r}."
            )
            continue
        normalized_proof_tokens = sorted(
            {
                str(token or "").strip().lower()
                for token in proof_tokens
                if str(token or "").strip()
            }
        )
        if normalized_proof_tokens != list(REQUIRED_EXTERNAL_PROOF_TOKENS):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.requiredProofs' "
                f"for tuple {tuple_id} must equal {list(REQUIRED_EXTERNAL_PROOF_TOKENS)!r} but was {normalized_proof_tokens!r}."
            )
            continue
        expected_artifact_id = str(item.get("expected_artifact_id") or "").strip()
        expected_installer = str(item.get("expected_installer_file_name") or "").strip()
        expected_installer_relative_path = str(item.get("expected_installer_relative_path") or "").strip()
        expected_route = str(item.get("expected_public_install_route") or "").strip()
        expected_receipt = str(item.get("expected_startup_smoke_receipt_path") or "").strip()
        if not bool(item.get("expected_artifact_id_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedArtifactId' "
                f"must be explicit for tuple {tuple_id}."
            )
        if not bool(item.get("expected_installer_file_name_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedInstallerFileName' "
                f"must be explicit for tuple {tuple_id}."
            )
        if not bool(item.get("expected_public_install_route_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedPublicInstallRoute' "
                f"must be explicit for tuple {tuple_id}."
            )
        if not bool(item.get("expected_startup_smoke_receipt_path_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedStartupSmokeReceiptPath' "
                f"must be explicit for tuple {tuple_id}."
            )
        if not bool(item.get("startup_smoke_receipt_contract_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.startupSmokeReceiptContract' "
                f"must be explicit for tuple {tuple_id}."
            )
        if not bool(item.get("proof_capture_commands_provided")):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.proofCaptureCommands' "
                f"must be explicit for tuple {tuple_id}."
            )
        if expected_artifact_id != str(item.get("canonical_expected_artifact_id") or "").strip():
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedArtifactId' "
                f"must match tuple-derived canonical value for {tuple_id}."
            )
        if expected_installer != str(item.get("canonical_expected_installer_file_name") or "").strip():
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedInstallerFileName' "
                f"must match tuple-derived canonical value for {tuple_id}."
            )
        if expected_route != str(item.get("canonical_expected_public_install_route") or "").strip():
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedPublicInstallRoute' "
                f"must match tuple-derived canonical value for {tuple_id}."
            )
        if expected_receipt != str(item.get("canonical_expected_startup_smoke_receipt_path") or "").strip():
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.expectedStartupSmokeReceiptPath' "
                f"must match tuple-derived canonical value for {tuple_id}."
            )
        if (
            dict(item.get("startup_smoke_receipt_contract") or {})
            != dict(item.get("canonical_startup_smoke_receipt_contract") or {})
        ):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.startupSmokeReceiptContract' "
                f"must match tuple-derived canonical value for {tuple_id}."
            )
        if not _proof_capture_commands_match_expected(
            list(item.get("proof_capture_commands") or []),
            list(item.get("canonical_proof_capture_commands") or []),
        ):
            reasons.append(
                "release_channel.generated.json field 'desktopTupleCoverage.externalProofRequests.proofCaptureCommands' "
                f"must match tuple-derived canonical command sequence for {tuple_id}."
            )
        detail_parts: List[str] = []
        if expected_artifact_id:
            detail_parts.append(f"artifactId {expected_artifact_id}")
        if expected_installer:
            detail_parts.append(f"installer {expected_installer}")
        if expected_route:
            detail_parts.append(f"public route {expected_route}")
        if expected_receipt:
            detail_parts.append(f"startup-smoke receipt {expected_receipt}")
        details = f" Expected targets: {', '.join(detail_parts)}." if detail_parts else ""
        reasons.append(
            "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' "
            f"external proof request: capture {', '.join(proof_tokens)} on {required_host or 'required'} host "
            f"for tuple {tuple_id}.{details}"
        )
    return sorted(set(reasons))


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    for attempt in range(3):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            if attempt >= 2:
                return {}
            time.sleep(0.05 * (attempt + 1))
            continue
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    for attempt in range(3):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            if attempt >= 2:
                return {}
            time.sleep(0.05 * (attempt + 1))
            continue
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def artifact_state(name: str, payload: Dict[str, Any], *, time_field: str) -> Dict[str, Any]:
    stale_after_hours = ARTIFACT_STALE_HOURS.get(name, 24)
    parsed = parse_iso(payload.get(time_field))
    if parsed is None:
        return {
            "artifact": name,
            "available": False,
            "at": "",
            "state": "missing",
            "age_seconds": None,
        }
    age_seconds = max(0, int((utc_now() - parsed).total_seconds()))
    state = "fresh" if age_seconds <= stale_after_hours * 3600 else "stale"
    return {
        "artifact": name,
        "available": True,
        "at": iso(parsed),
        "state": state,
        "age_seconds": age_seconds,
    }


def resolve_registry_path(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise SystemExit(f"journey registry is missing: {path}")
        return path
    for candidate in REGISTRY_CANDIDATES:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit("could not locate GOLDEN_JOURNEY_RELEASE_GATES.yaml in the Fleet mirror or canonical design repo")


def posture_value(project_row: Dict[str, Any]) -> str:
    return (
        str(project_row.get("deployment_access_posture") or "").strip()
        or str(project_row.get("deployment_visibility") or "").strip()
        or str(project_row.get("deployment_promotion_stage") or "").strip()
        or str(project_row.get("deployment_status") or "").strip()
    )


def compare_order(actual: str, expected: str, order: Dict[str, int]) -> int:
    return order.get(str(actual or "").strip(), -1) - order.get(str(expected or "").strip(), -1)


def _normalize_external_proof_capture_command(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    host_class_match = re.search(r"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=([^\s]+)", raw)
    host_class_value = ""
    if host_class_match is not None:
        host_class_value = host_class_match.group(1).strip().lower().removesuffix("-host")
    normalized = re.sub(
        r"\s*CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=[^\s]+",
        "",
        raw,
        count=1,
    )
    if "./scripts/run-desktop-startup-smoke.sh" in normalized and host_class_value:
        operating_system_hint = {
            "windows": "Windows",
            "macos": "macOS",
            "linux": "Linux",
        }.get(host_class_value, "")
        if operating_system_hint:
            normalized = re.sub(
                r"(CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=[^\s]+)",
                rf"\1 CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM={operating_system_hint}",
                normalized,
                count=1,
            )
    if "./scripts/run-desktop-startup-smoke.sh" in normalized:
        normalized = re.sub(r"\s+run-[^\s\"']+\s*$", "", normalized).strip()
    return re.sub(r"\s{2,}", " ", normalized).strip()


def _proof_capture_commands_match_expected(actual: List[str], expected: List[str]) -> bool:
    actual_commands = [
        _normalize_external_proof_capture_command(token)
        for token in actual
        if _normalize_external_proof_capture_command(token)
    ]
    expected_commands = [
        _normalize_external_proof_capture_command(token)
        for token in expected
        if _normalize_external_proof_capture_command(token)
    ]
    if actual_commands == expected_commands:
        return True
    if len(actual_commands) > len(expected_commands) and actual_commands[-len(expected_commands) :] == expected_commands:
        return True
    return False


def _align_proof_capture_commands_with_expected(
    actual_row: Dict[str, Any],
    expected_row: Dict[str, Any] | None,
) -> Dict[str, Any]:
    if not isinstance(actual_row, dict):
        return {}
    aligned = dict(actual_row)
    if not isinstance(expected_row, dict):
        return aligned
    actual_commands = [
        _normalize_external_proof_capture_command(token)
        for token in (aligned.get("proof_capture_commands") or [])
        if _normalize_external_proof_capture_command(token)
    ]
    expected_commands = [
        _normalize_external_proof_capture_command(token)
        for token in (expected_row.get("proof_capture_commands") or [])
        if _normalize_external_proof_capture_command(token)
    ]
    if _proof_capture_commands_match_expected(actual_commands, expected_commands):
        aligned["proof_capture_commands"] = [
            str(token or "").strip()
            for token in (expected_row.get("proof_capture_commands") or [])
            if str(token or "").strip()
        ]
    return aligned


def resolve_repo_root(repo_name: str) -> Path | None:
    for candidate in REPO_ROOT_CANDIDATES.get(repo_name, ()):
        if candidate.exists():
            return candidate
    return None


def classify_blocking_reasons(blocking_reasons: List[str]) -> Tuple[List[str], List[str]]:
    external_blocking_reasons: List[str] = []
    local_blocking_reasons: List[str] = []
    for reason in blocking_reasons:
        normalized = str(reason or "").strip().lower()
        is_external = normalized and any(marker in normalized for marker in EXTERNAL_BLOCKER_MARKERS)
        if not is_external and normalized and any(
            marker in normalized for marker in RELEASE_CHANNEL_PLATFORM_COVERAGE_MARKERS
        ):
            # Missing Windows/macOS tuples on a non-hosted platform should not be
            # reported as repo-local defects; Linux tuple gaps still stay local.
            is_external = "linux" not in normalized
        if is_external:
            external_blocking_reasons.append(reason)
        else:
            local_blocking_reasons.append(reason)
    return external_blocking_reasons, local_blocking_reasons


def _desktop_executable_gate_effective_local_blockers(
    payload: Dict[str, Any],
    *,
    release_channel_payload: Dict[str, Any] | None,
) -> List[str]:
    if not isinstance(payload, dict):
        return []
    raw_local_blockers = payload.get("local_blocking_findings")
    if not isinstance(raw_local_blockers, list):
        raw_local_blockers = payload.get("localBlockingFindings")
    local_blockers = [str(item).strip() for item in (raw_local_blockers or []) if str(item).strip()]
    if not local_blockers:
        return []

    release_channel_payload = release_channel_payload if isinstance(release_channel_payload, dict) else {}
    tuple_coverage = (
        release_channel_payload.get("desktopTupleCoverage")
        if isinstance(release_channel_payload.get("desktopTupleCoverage"), dict)
        else {}
    )
    required_heads = {
        str(item).strip().lower()
        for item in (tuple_coverage.get("requiredDesktopHeads") or [])
        if str(item).strip()
    }
    release_channel_external_contract_drift = [
        reason
        for reason in _release_channel_external_proof_reasons(release_channel_payload)
        if (
            "desktoptuplecoverage.externalproofrequests" in str(reason).strip().lower()
            and "external proof request: capture" not in str(reason).strip().lower()
        )
    ]
    release_channel_external_contract_ready = not release_channel_external_contract_drift

    effective: List[str] = []
    for reason in local_blockers:
        normalized = reason.lower()
        if "blazor-desktop" in normalized and "blazor-desktop" not in required_heads:
            continue
        if _reason_is_external_nonlinux_startup_smoke_receipt_drift(reason):
            continue
        if release_channel_external_contract_ready and (
            "desktoptuplecoverage.externalproofrequests" in normalized
            or "proofcapturecommands" in normalized
            or "missing-tuple external proof contract" in normalized
        ):
            continue
        effective.append(reason)
    return effective


def _reason_is_external_nonlinux_startup_smoke_receipt_drift(reason: str) -> bool:
    normalized = str(reason or "").strip().lower()
    if not normalized:
        return False
    if "linux" in normalized:
        return False
    if not any(token in normalized for token in ("windows startup smoke receipt", "macos startup smoke receipt")):
        return False
    return any(
        token in normalized
        for token in (
            "receipt path is missing/unreadable",
            "receipt timestamp is missing/invalid",
            "receipt channelid does not match",
            "receipt version does not match",
            "receipt is missing version",
            "receipt is stale",
        )
    )


def evaluate_journey(
    row: Dict[str, Any],
    *,
    projects_by_id: Dict[str, Dict[str, Any]],
    status_plane_projects_present: bool,
    artifacts: Dict[str, Dict[str, Any]],
    progress_report: Dict[str, Any],
    progress_history: Dict[str, Any],
    support_packets: Dict[str, Any],
) -> Dict[str, Any]:
    fleet_gate = dict(row.get("fleet_gate") or {})
    blocking_reasons: List[str] = []
    warning_reasons: List[str] = []
    external_proof_requests: List[Dict[str, Any]] = []
    release_channel_external_proof_source_present = False
    release_channel_expected_channel_id = ""
    release_channel_expected_status = ""
    release_channel_expected_version = ""
    release_channel_generated_at: dt.datetime | None = None
    release_channel_proof_payload: Dict[str, Any] | None = None
    now = utc_now()

    repo_source_proof_rows = [dict(item or {}) for item in (fleet_gate.get("repo_source_proof") or [])]
    for proof_row in repo_source_proof_rows:
        if (
            str(proof_row.get("repo") or "").strip() == "chummer6-hub-registry"
            and str(proof_row.get("path") or "").strip() == ".codex-studio/published/RELEASE_CHANNEL.generated.json"
        ):
            repo_root = resolve_repo_root("chummer6-hub-registry")
            if repo_root is None:
                break
            target_path = (repo_root / ".codex-studio/published/RELEASE_CHANNEL.generated.json").resolve()
            if not target_path.is_file():
                break
            try:
                decoded = json.loads(target_path.read_text(encoding="utf-8"))
            except Exception:
                break
            if isinstance(decoded, dict):
                release_channel_proof_payload = decoded
            break

    for artifact_name in fleet_gate.get("required_artifacts") or []:
        artifact = dict(artifacts.get(str(artifact_name)) or {})
        state = str(artifact.get("state") or "missing").strip()
        if state in {"missing", "stale"}:
            blocking_reasons.append(f"{artifact_name} is {state}.")

    minimum_history = int(fleet_gate.get("minimum_history_snapshots") or 0)
    target_history = int(fleet_gate.get("target_history_snapshots") or 0)
    history_count = int(progress_history.get("snapshot_count") or progress_report.get("history_snapshot_count") or 0)
    if minimum_history and history_count < minimum_history:
        blocking_reasons.append(
            f"progress history depth {history_count} is below the minimum journey evidence floor of {minimum_history}."
        )
    elif target_history and history_count < target_history:
        warning_reasons.append(
            f"progress history depth {history_count} is still below the boring target of {target_history}."
        )

    required_project_posture = [dict(item or {}) for item in (fleet_gate.get("required_project_posture") or [])]
    if required_project_posture and not status_plane_projects_present:
        blocking_reasons.append(
            "status-plane project inventory is empty; cannot evaluate required project posture gates."
        )

    for posture_row in required_project_posture:
        project_id = str(posture_row.get("project_id") or "").strip()
        if not status_plane_projects_present:
            continue
        project = dict(projects_by_id.get(project_id) or {})
        if not project:
            blocking_reasons.append(f"required project {project_id} is missing from status-plane truth.")
            continue
        stage = str(project.get("readiness_stage") or "").strip()
        minimum_stage = str(posture_row.get("minimum_stage") or "").strip()
        target_stage = str(posture_row.get("target_stage") or "").strip()
        if minimum_stage and compare_order(stage, minimum_stage, STAGE_ORDER) < 0:
            blocking_reasons.append(f"{project_id} is at {stage or 'unknown'} below minimum stage {minimum_stage}.")
        elif target_stage and compare_order(stage, target_stage, STAGE_ORDER) < 0:
            warning_reasons.append(f"{project_id} is at {stage or 'unknown'} below target stage {target_stage}.")

        actual_promotion = posture_value(project)
        minimum_promotion = str(posture_row.get("minimum_deployment_posture") or "").strip()
        target_promotion = str(posture_row.get("target_deployment_posture") or "").strip()
        if minimum_promotion and compare_order(actual_promotion, minimum_promotion, PROMOTION_ORDER) < 0:
            blocking_reasons.append(
                f"{project_id} promotion posture {actual_promotion or 'unknown'} is below minimum {minimum_promotion}."
            )
        elif target_promotion and compare_order(actual_promotion, target_promotion, PROMOTION_ORDER) < 0:
            warning_reasons.append(
                f"{project_id} promotion posture {actual_promotion or 'unknown'} is below target {target_promotion}."
            )

    for proof in repo_source_proof_rows:
        proof_row = dict(proof or {})
        repo_name = str(proof_row.get("repo") or "").strip()
        relative_path = str(proof_row.get("path") or "").strip()
        repo_root = resolve_repo_root(repo_name)
        if repo_root is None:
            blocking_reasons.append(f"repo proof root for {repo_name or 'unknown'} is not configured.")
            continue
        target_path = (repo_root / relative_path).resolve()
        if not target_path.is_file():
            blocking_reasons.append(f"repo proof file is missing: {repo_name}:{relative_path}.")
            continue
        try:
            text = target_path.read_text(encoding="utf-8")
        except OSError as exc:
            blocking_reasons.append(f"repo proof file could not be read: {repo_name}:{relative_path} ({exc}).")
            continue
        proof_payload_for_marker: Dict[str, Any] | None = None
        if (
            repo_name == "chummer6-ui"
            and relative_path == ".codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        ):
            try:
                decoded_marker_payload = json.loads(text)
            except Exception:
                decoded_marker_payload = None
            if isinstance(decoded_marker_payload, dict):
                proof_payload_for_marker = decoded_marker_payload
        for snippet in proof_row.get("must_contain") or []:
            snippet_text = str(snippet or "").strip()
            if (
                snippet_text == '"local_blocking_findings_count": 0'
                and proof_payload_for_marker is not None
                and not _desktop_executable_gate_effective_local_blockers(
                    proof_payload_for_marker,
                    release_channel_payload=release_channel_proof_payload,
                )
            ):
                continue
            if snippet_text and snippet_text not in text:
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} is missing required marker '{snippet_text}'."
                )
        json_required = dict(proof_row.get("json_must_equal") or {})
        json_required_one_of = dict(proof_row.get("json_must_be_one_of") or {})
        json_required_non_empty = dict(proof_row.get("json_must_be_non_empty_string") or {})
        max_age_hours_raw = proof_row.get("max_age_hours")
        enforce_json_parsing = (
            bool(json_required)
            or bool(json_required_one_of)
            or bool(json_required_non_empty)
            or (max_age_hours_raw is not None and str(max_age_hours_raw).strip())
        )
        proof_payload: Dict[str, Any] | None = None
        validate_release_channel_external_proof_contract = False
        if enforce_json_parsing:
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} is not valid json, cannot enforce structured checks."
                )
                continue
            if not isinstance(decoded, dict):
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} must be a json object to enforce structured checks."
                )
                continue
            proof_payload = decoded
            if (
                repo_name == "chummer6-hub-registry"
                and relative_path == ".codex-studio/published/RELEASE_CHANNEL.generated.json"
            ):
                release_channel_proof_payload = proof_payload
                # Support/install contract checks need the tuple backlog whenever release-channel truth is present,
                # even when this gate only enforces json_must_be_one_of fields.
                external_proof_requests = _release_channel_external_proof_requests(proof_payload)
                release_channel_external_proof_source_present = True
                validate_release_channel_external_proof_contract = True
                release_channel_expected_channel_id = str(
                    proof_payload.get("channelId") or proof_payload.get("channel") or ""
                ).strip()
                release_channel_expected_status = str(proof_payload.get("status") or "").strip()
                release_channel_expected_version = str(proof_payload.get("version") or "").strip()
                release_channel_generated_at = parse_iso(
                    proof_payload.get("generated_at") or proof_payload.get("generatedAt")
                )

        effective_desktop_exit_gate_local_blockers: List[str] | None = None
        if (
            proof_payload is not None
            and repo_name == "chummer6-ui"
            and relative_path == ".codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        ):
            effective_desktop_exit_gate_local_blockers = _desktop_executable_gate_effective_local_blockers(
                proof_payload,
                release_channel_payload=release_channel_proof_payload,
            )

        if json_required:
            assert proof_payload is not None
            for field_path, expected in json_required.items():
                if (
                    effective_desktop_exit_gate_local_blockers is not None
                    and str(field_path).strip().lower() in {"local_blocking_findings_count", "localblockingfindingscount"}
                    and expected == 0
                ):
                    if len(effective_desktop_exit_gate_local_blockers) == 0:
                        continue
                actual = _resolve_json_path(proof_payload, str(field_path))
                if actual != expected:
                    blocking_reasons.append(
                        f"repo proof {repo_name}:{relative_path} field '{field_path}' expected {expected!r} but was {actual!r}."
                    )

        if json_required_one_of:
            assert proof_payload is not None
            for field_path, allowed_values in json_required_one_of.items():
                if isinstance(allowed_values, list):
                    normalized_allowed = list(allowed_values)
                else:
                    normalized_allowed = [allowed_values]
                actual = _resolve_json_path(proof_payload, str(field_path))
                if actual not in normalized_allowed:
                    blocking_reasons.append(
                        f"repo proof {repo_name}:{relative_path} field '{field_path}' expected one of {normalized_allowed!r} but was {actual!r}."
                    )

        if json_required_non_empty:
            assert proof_payload is not None
            for field_path in json_required_non_empty.keys():
                actual = _resolve_json_path(proof_payload, str(field_path))
                if not isinstance(actual, str) or not actual.strip():
                    blocking_reasons.append(
                        f"repo proof {repo_name}:{relative_path} field '{field_path}' must be a non-empty string but was {actual!r}."
                    )

        if max_age_hours_raw is not None and str(max_age_hours_raw).strip():
            try:
                max_age_hours = float(max_age_hours_raw)
            except (TypeError, ValueError):
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} has invalid max_age_hours value '{max_age_hours_raw}'."
                )
                continue
            timestamp_fields = [
                str(item).strip()
                for item in (proof_row.get("generated_at_fields") or ["generated_at", "generatedAt"])
                if str(item).strip()
            ]
            max_future_skew_seconds = int(proof_row.get("max_future_skew_seconds") or 300)
            assert proof_payload is not None
            proof_generated_at = None
            proof_generated_field = ""
            for field_name in timestamp_fields:
                candidate = parse_iso(proof_payload.get(field_name))
                if candidate is not None:
                    proof_generated_at = candidate
                    proof_generated_field = field_name
                    break
            if proof_generated_at is None:
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} is missing a parseable timestamp in fields {timestamp_fields}."
                )
                continue
            age_seconds = int((now - proof_generated_at).total_seconds())
            if age_seconds < -max_future_skew_seconds:
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} timestamp field {proof_generated_field} is too far in the future ({iso(proof_generated_at)})."
                )
                continue
            if age_seconds > int(max_age_hours * 3600):
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} is stale ({age_seconds}s old > {int(max_age_hours * 3600)}s max)."
                )

        if validate_release_channel_external_proof_contract:
            assert proof_payload is not None
            blocking_reasons.extend(_release_channel_external_proof_reasons(proof_payload))

    support_summary = dict(support_packets.get("summary") or {})
    support_packet_contract_violations: List[str] = []
    support_recovery_contract_violations: List[str] = []
    support_generated_at = str(support_packets.get("generated_at") or "").strip()
    support_freshness = dict(artifacts.get("support_packets") or {})
    if bool(fleet_gate.get("require_support_freshness")) and support_freshness.get("state") != "fresh":
        blocking_reasons.append(
            f"support packet freshness is {support_freshness.get('state') or 'unknown'}."
        )
    if bool(fleet_gate.get("require_support_closure_waiting_zero")) and int(support_summary.get("closure_waiting_on_release_truth") or 0) > 0:
        warning_reasons.append("support closure is still waiting on release truth.")
    if bool(fleet_gate.get("require_support_update_required_routes_to_downloads")):
        update_required_case_count = int(support_summary.get("update_required_case_count") or 0)
        update_required_routed_to_downloads_count = int(
            support_summary.get("update_required_routed_to_downloads_count") or 0
        )
        update_required_misrouted_case_count = int(support_summary.get("update_required_misrouted_case_count") or 0)
        if update_required_misrouted_case_count > 0:
            blocking_reasons.append(
                "support packets include update-required cases not routed to /downloads."
            )
        if update_required_routed_to_downloads_count < update_required_case_count:
            blocking_reasons.append(
                "support packets do not prove all update-required cases route to /downloads."
            )
    if bool(fleet_gate.get("require_support_install_truth_contract")):
        if release_channel_external_proof_source_present:
            if release_channel_generated_at is None:
                support_packet_contract_violations.append(
                    "release channel install-truth proof is missing parseable generated_at/generatedAt timestamp."
                )
            else:
                support_generated_at_parsed = parse_iso(support_generated_at)
                if support_generated_at_parsed is None:
                    support_packet_contract_violations.append(
                        "support packet install-truth proof is missing parseable generated_at timestamp."
                    )
                elif support_generated_at_parsed < release_channel_generated_at:
                    support_packet_contract_violations.append(
                        "support packet install-truth proof predates release-channel truth and may be stale for the current release."
                    )

        def _counter_map(values: List[str]) -> Dict[str, int]:
            counts: Dict[str, int] = {}
            for raw in values:
                token = str(raw or "").strip()
                if not token:
                    continue
                counts[token] = counts.get(token, 0) + 1
            return {key: counts[key] for key in sorted(counts)}

        def _normalized_summary_counter(value: Any, *, field_name: str, field_present: bool) -> Dict[str, int]:
            if value is None:
                return {}
            if not isinstance(value, dict):
                if field_present:
                    support_packet_contract_violations.append(
                        f"support packet summary {field_name} must be an object map when present."
                    )
                return {}
            normalized: Dict[str, int] = {}
            for key, raw_count in value.items():
                token = str(key or "").strip()
                if not token:
                    continue
                if isinstance(raw_count, bool) or not isinstance(raw_count, int):
                    support_packet_contract_violations.append(
                        f"support packet summary {field_name} token '{token}' is missing integer count."
                    )
                    continue
                count = int(raw_count)
                if count > 0:
                    normalized[token] = count
            return {key: normalized[key] for key in sorted(normalized)}

        def _normalized_summary_count(value: Any, *, field_name: str) -> int:
            if isinstance(value, bool) or not isinstance(value, int):
                support_packet_contract_violations.append(
                    f"support packet summary {field_name} is missing integer count."
                )
                return -1
            return int(value)

        def _normalized_summary_tokens(value: Any, *, field_name: str, lower: bool, field_present: bool) -> List[str]:
            if value is None:
                return []
            if not isinstance(value, list):
                if field_present:
                    support_packet_contract_violations.append(
                        f"support packet summary {field_name} must be a string list when present."
                    )
                return []
            tokens = []
            for raw in value:
                token = str(raw or "").strip()
                if not token:
                    continue
                tokens.append(token.lower() if lower else token)
            return sorted(set(tokens))

        def _normalized_smoke_contract_map(contract: Any) -> Dict[str, Any]:
            if not isinstance(contract, dict):
                return {}
            status_any_of = [
                str(token or "").strip().lower()
                for token in (contract.get("status_any_of") or [])
                if str(token or "").strip()
            ]
            return {
                "ready_checkpoint": str(contract.get("ready_checkpoint") or "").strip(),
                "head_id": str(contract.get("head_id") or "").strip().lower(),
                "platform": str(contract.get("platform") or "").strip().lower(),
                "rid": str(contract.get("rid") or "").strip().lower(),
                "host_class_contains": str(contract.get("host_class_contains") or "").strip().lower(),
                "status_any_of": sorted(set(status_any_of)),
            }

        def _normalized_external_proof_summary_specs(value: Any, *, field_present: bool) -> Dict[str, Dict[str, Any]]:
            if value is None:
                return {}
            if not isinstance(value, dict):
                if field_present:
                    support_packet_contract_violations.append(
                        "support packet summary unresolved_external_proof_request_specs must be an object map when present."
                    )
                return {}
            normalized: Dict[str, Dict[str, Any]] = {}
            for raw_tuple, raw_spec in value.items():
                tuple_id = str(raw_tuple or "").strip()
                if not tuple_id or not isinstance(raw_spec, dict):
                    continue
                required_proofs = sorted(
                    set(
                        str(token or "").strip()
                        for token in (raw_spec.get("required_proofs") or [])
                        if str(token or "").strip()
                    )
                )
                proof_capture_commands = [
                    str(token or "").strip()
                    for token in (raw_spec.get("proof_capture_commands") or [])
                    if str(token or "").strip()
                ]
                expected_installer_sha256 = str(raw_spec.get("expected_installer_sha256") or "").strip().lower()
                if expected_installer_sha256 and (
                    len(expected_installer_sha256) != 64
                    or any(ch not in "0123456789abcdef" for ch in expected_installer_sha256)
                ):
                    support_packet_contract_violations.append(
                        "support packet summary unresolved_external_proof_request_specs "
                        f"tuple '{tuple_id}' has invalid expected_installer_sha256."
                    )
                tuple_entry_count_value = raw_spec.get("tuple_entry_count")
                tuple_unique_value = raw_spec.get("tuple_unique")
                tuple_entry_count = -1
                if isinstance(tuple_entry_count_value, bool) or not isinstance(tuple_entry_count_value, int):
                    support_packet_contract_violations.append(
                        "support packet summary unresolved_external_proof_request_specs "
                        f"tuple '{tuple_id}' is missing integer tuple_entry_count."
                    )
                else:
                    tuple_entry_count = int(tuple_entry_count_value)
                tuple_unique = False
                if not isinstance(tuple_unique_value, bool):
                    support_packet_contract_violations.append(
                        "support packet summary unresolved_external_proof_request_specs "
                        f"tuple '{tuple_id}' is missing boolean tuple_unique."
                    )
                else:
                    tuple_unique = tuple_unique_value
                normalized[tuple_id] = {
                    "channel_id": str(raw_spec.get("channel_id") or "").strip().lower(),
                    "tuple_entry_count": tuple_entry_count,
                    "tuple_unique": tuple_unique,
                    "required_host": str(raw_spec.get("required_host") or "").strip().lower(),
                    "required_proofs": required_proofs,
                    "expected_artifact_id": str(raw_spec.get("expected_artifact_id") or "").strip(),
                    "expected_installer_file_name": str(raw_spec.get("expected_installer_file_name") or "").strip(),
                    "expected_installer_relative_path": (
                        str(raw_spec.get("expected_installer_relative_path") or "").strip()
                        or (
                            f"files/{str(raw_spec.get('expected_installer_file_name') or '').strip()}"
                            if str(raw_spec.get("expected_installer_file_name") or "").strip()
                            else ""
                        )
                    ),
                    "expected_public_install_route": str(raw_spec.get("expected_public_install_route") or "").strip(),
                    "expected_startup_smoke_receipt_path": str(
                        raw_spec.get("expected_startup_smoke_receipt_path") or ""
                    ).strip(),
                    "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                        raw_spec.get("startup_smoke_receipt_contract")
                    ),
                    "proof_capture_commands": proof_capture_commands,
                }
                if expected_installer_sha256:
                    normalized[tuple_id]["expected_installer_sha256"] = expected_installer_sha256
            return {key: normalized[key] for key in sorted(normalized)}

        def _normalized_external_proof_execution_plan(value: Any, *, field_present: bool) -> Dict[str, Any]:
            if value is None:
                return {"request_count": 0, "hosts": [], "host_groups": {}}
            if not isinstance(value, dict):
                if field_present:
                    support_packet_contract_violations.append(
                        "support packet unresolved_external_proof_execution_plan must be an object map when present."
                    )
                return {"request_count": 0, "hosts": [], "host_groups": {}}

            host_groups_value = value.get("host_groups")
            host_groups_raw = host_groups_value if isinstance(host_groups_value, dict) else {}
            normalized_host_groups: Dict[str, Any] = {}
            for raw_host, raw_group in host_groups_raw.items():
                host = str(raw_host or "").strip().lower()
                if not host or not isinstance(raw_group, dict):
                    continue
                group_requests = raw_group.get("requests")
                request_rows = group_requests if isinstance(group_requests, list) else []
                normalized_requests = []
                for raw_request in request_rows:
                    if not isinstance(raw_request, dict):
                        continue
                    tuple_id = str(raw_request.get("tuple_id") or "").strip()
                    required_proofs = sorted(
                        {
                            str(token or "").strip().lower()
                            for token in (raw_request.get("required_proofs") or [])
                            if str(token or "").strip()
                        }
                    )
                    proof_capture_commands = [
                        str(token or "").strip()
                        for token in (raw_request.get("proof_capture_commands") or [])
                        if str(token or "").strip()
                    ]
                    expected_installer_sha256 = str(
                        raw_request.get("expected_installer_sha256") or ""
                    ).strip().lower()
                    if expected_installer_sha256 and (
                        len(expected_installer_sha256) != 64
                        or any(ch not in "0123456789abcdef" for ch in expected_installer_sha256)
                    ):
                        support_packet_contract_violations.append(
                            "support packet unresolved_external_proof_execution_plan "
                            f"host '{host}' tuple '{tuple_id or 'unknown'}' has invalid expected_installer_sha256."
                        )
                    tuple_entry_count_value = raw_request.get("tuple_entry_count")
                    tuple_unique_value = raw_request.get("tuple_unique")
                    tuple_entry_count = -1
                    if isinstance(tuple_entry_count_value, bool) or not isinstance(tuple_entry_count_value, int):
                        support_packet_contract_violations.append(
                            "support packet unresolved_external_proof_execution_plan "
                            f"host '{host}' tuple '{tuple_id or 'unknown'}' is missing integer tuple_entry_count."
                        )
                    else:
                        tuple_entry_count = int(tuple_entry_count_value)
                    tuple_unique = False
                    if not isinstance(tuple_unique_value, bool):
                        support_packet_contract_violations.append(
                            "support packet unresolved_external_proof_execution_plan "
                            f"host '{host}' tuple '{tuple_id or 'unknown'}' is missing boolean tuple_unique."
                        )
                    else:
                        tuple_unique = tuple_unique_value
                    normalized_request = {
                            "tuple_id": tuple_id,
                            "tuple_entry_count": tuple_entry_count,
                            "tuple_unique": tuple_unique,
                            "channel_id": str(raw_request.get("channel_id") or "").strip().lower(),
                            "head_id": str(raw_request.get("head_id") or "").strip().lower(),
                            "platform": str(raw_request.get("platform") or "").strip().lower(),
                            "rid": str(raw_request.get("rid") or "").strip().lower(),
                            "expected_artifact_id": str(raw_request.get("expected_artifact_id") or "").strip(),
                            "expected_installer_file_name": str(
                                raw_request.get("expected_installer_file_name") or ""
                            ).strip(),
                            "expected_installer_relative_path": (
                                str(raw_request.get("expected_installer_relative_path") or "").strip()
                                or (
                                    f"files/{str(raw_request.get('expected_installer_file_name') or '').strip()}"
                                    if str(raw_request.get("expected_installer_file_name") or "").strip()
                                    else ""
                                )
                            ),
                            "expected_public_install_route": str(
                                raw_request.get("expected_public_install_route") or ""
                            ).strip(),
                            "expected_startup_smoke_receipt_path": str(
                                raw_request.get("expected_startup_smoke_receipt_path") or ""
                            ).strip(),
                            "required_proofs": required_proofs,
                            "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                                raw_request.get("startup_smoke_receipt_contract")
                            ),
                            "proof_capture_commands": proof_capture_commands,
                        }
                    if expected_installer_sha256:
                        normalized_request["expected_installer_sha256"] = expected_installer_sha256
                    normalized_requests.append(normalized_request)
                normalized_requests = sorted(
                    normalized_requests,
                    key=lambda item: str(item.get("tuple_id") or "").strip(),
                )
                group_request_count_value = raw_group.get("request_count")
                group_request_count = -1
                if isinstance(group_request_count_value, bool) or not isinstance(group_request_count_value, int):
                    support_packet_contract_violations.append(
                        "support packet unresolved_external_proof_execution_plan "
                        f"host '{host}' is missing integer request_count."
                    )
                else:
                    group_request_count = int(group_request_count_value)
                normalized_host_groups[host] = {
                    "request_count": group_request_count,
                    "tuples": sorted(
                        {
                            str(token or "").strip()
                            for token in (raw_group.get("tuples") or [])
                            if str(token or "").strip()
                        }
                    ),
                    "requests": normalized_requests,
                }
            request_count_value = value.get("request_count")
            request_count = -1
            if isinstance(request_count_value, bool) or not isinstance(request_count_value, int):
                support_packet_contract_violations.append(
                    "support packet unresolved_external_proof_execution_plan is missing integer request_count."
                )
            else:
                request_count = int(request_count_value)
            hosts = sorted(
                {
                    str(token or "").strip().lower()
                    for token in (value.get("hosts") or [])
                    if str(token or "").strip()
                }
            )
            return {
                "request_count": request_count,
                "hosts": hosts,
                "host_groups": {key: normalized_host_groups[key] for key in sorted(normalized_host_groups)},
            }

        packets = [dict(item) for item in (support_packets.get("packets") or []) if isinstance(item, dict)]
        support_external_proof_required_count = 0
        expected_external_proof_request_by_tuple = {
            str(item.get("tuple_id") or "").strip(): dict(item)
            for item in external_proof_requests
            if str(item.get("tuple_id") or "").strip()
        }

        def _is_case_backed_packet(packet: Dict[str, Any], *, packet_id: str | None = None) -> bool:
            # Backward compatibility: older packets do not include support_case_backed and
            # are support-case-backed by default.
            if "support_case_backed" not in packet:
                return True
            support_case_backed = packet.get("support_case_backed")
            if not isinstance(support_case_backed, bool):
                support_packet_contract_violations.append(
                    f"support packet {packet_id or 'unknown'} is missing boolean support_case_backed."
                )
                return False
            return support_case_backed

        case_backed_packets: List[Dict[str, Any]] = []
        for index, packet in enumerate(packets, start=1):
            packet_id = str(packet.get("packet_id") or "").strip() or f"packet#{index}"
            install_truth_state = str(packet.get("install_truth_state") or "").strip().lower()
            install_diagnosis = packet.get("install_diagnosis")
            fix_confirmation = packet.get("fix_confirmation")
            recovery_path = packet.get("recovery_path")
            case_backed = _is_case_backed_packet(packet, packet_id=packet_id)
            if case_backed:
                case_backed_packets.append(packet)
            if not install_truth_state:
                support_packet_contract_violations.append(
                    f"support packet {packet_id} is missing install_truth_state."
                )
            if not isinstance(install_diagnosis, dict):
                support_packet_contract_violations.append(
                    f"support packet {packet_id} is missing install_diagnosis."
                )
            else:
                if not str(install_diagnosis.get("registry_channel_id") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing install_diagnosis.registry_channel_id."
                    )
                elif (
                    release_channel_expected_channel_id
                    and str(install_diagnosis.get("registry_channel_id") or "").strip().lower()
                    != release_channel_expected_channel_id.lower()
                ):
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} install_diagnosis.registry_channel_id must match release-channel value "
                        f"'{release_channel_expected_channel_id}' but was "
                        f"'{str(install_diagnosis.get('registry_channel_id') or '').strip()}'."
                    )
                if not str(install_diagnosis.get("registry_release_channel_status") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing install_diagnosis.registry_release_channel_status."
                    )
                elif (
                    release_channel_expected_status
                    and str(install_diagnosis.get("registry_release_channel_status") or "").strip().lower()
                    != release_channel_expected_status.lower()
                ):
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} install_diagnosis.registry_release_channel_status must match release-channel value "
                        f"'{release_channel_expected_status}' but was "
                        f"'{str(install_diagnosis.get('registry_release_channel_status') or '').strip()}'."
                    )
                if not str(install_diagnosis.get("registry_release_version") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing install_diagnosis.registry_release_version."
                    )
                elif (
                    release_channel_expected_version
                    and str(install_diagnosis.get("registry_release_version") or "").strip()
                    != release_channel_expected_version
                ):
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} install_diagnosis.registry_release_version must match release-channel value "
                        f"'{release_channel_expected_version}' but was "
                        f"'{str(install_diagnosis.get('registry_release_version') or '').strip()}'."
                    )
                if not str(install_diagnosis.get("registry_release_proof_status") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing install_diagnosis.registry_release_proof_status."
                    )
                external_proof_required = install_diagnosis.get("external_proof_required")
                external_proof_request = install_diagnosis.get("external_proof_request")
                if not isinstance(external_proof_required, bool):
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing boolean install_diagnosis.external_proof_required."
                    )
                elif external_proof_required:
                    if case_backed:
                        support_external_proof_required_count += 1
                    if not isinstance(external_proof_request, dict):
                        support_packet_contract_violations.append(
                            f"support packet {packet_id} is missing install_diagnosis.external_proof_request."
                        )
                    else:
                        if not str(external_proof_request.get("tuple_id") or "").strip():
                            support_packet_contract_violations.append(
                                f"support packet {packet_id} is missing install_diagnosis.external_proof_request.tuple_id."
                            )
                        if not str(external_proof_request.get("channel_id") or "").strip():
                            support_packet_contract_violations.append(
                                f"support packet {packet_id} is missing install_diagnosis.external_proof_request.channel_id."
                            )
                        if not str(external_proof_request.get("required_host") or "").strip():
                            support_packet_contract_violations.append(
                                f"support packet {packet_id} is missing install_diagnosis.external_proof_request.required_host."
                            )
                        for required_key in (
                            "expected_artifact_id",
                            "expected_installer_file_name",
                            "expected_public_install_route",
                            "expected_startup_smoke_receipt_path",
                        ):
                            if not str(external_proof_request.get(required_key) or "").strip():
                                support_packet_contract_violations.append(
                                    f"support packet {packet_id} is missing install_diagnosis.external_proof_request.{required_key}."
                                )
                        required_proofs = external_proof_request.get("required_proofs")
                        if not isinstance(required_proofs, list) or not [
                            str(token or "").strip() for token in required_proofs if str(token or "").strip()
                        ]:
                            support_packet_contract_violations.append(
                                f"support packet {packet_id} is missing install_diagnosis.external_proof_request.required_proofs."
                            )
                        smoke_contract = external_proof_request.get("startup_smoke_receipt_contract")
                        if not isinstance(smoke_contract, dict):
                            support_packet_contract_violations.append(
                                f"support packet {packet_id} is missing install_diagnosis.external_proof_request.startup_smoke_receipt_contract."
                            )
                        else:
                            for required_key in (
                                "status_any_of",
                                "ready_checkpoint",
                                "head_id",
                                "platform",
                                "rid",
                                "host_class_contains",
                            ):
                                value = smoke_contract.get(required_key)
                                if required_key == "status_any_of":
                                    if not isinstance(value, list) or not [
                                        str(token or "").strip() for token in value if str(token or "").strip()
                                    ]:
                                        support_packet_contract_violations.append(
                                            f"support packet {packet_id} is missing install_diagnosis.external_proof_request.startup_smoke_receipt_contract.status_any_of."
                                        )
                                elif not str(value or "").strip():
                                    support_packet_contract_violations.append(
                                        f"support packet {packet_id} is missing install_diagnosis.external_proof_request.startup_smoke_receipt_contract.{required_key}."
                                    )
                        proof_capture_commands = external_proof_request.get("proof_capture_commands")
                        if not isinstance(proof_capture_commands, list) or not [
                            str(token or "").strip() for token in proof_capture_commands if str(token or "").strip()
                        ]:
                            support_packet_contract_violations.append(
                                f"support packet {packet_id} is missing install_diagnosis.external_proof_request.proof_capture_commands."
                            )
                        else:
                            normalized_commands = [
                                str(token or "").strip()
                                for token in proof_capture_commands
                                if str(token or "").strip()
                            ]
                            expected_installer_file_name = str(
                                external_proof_request.get("expected_installer_file_name") or ""
                            ).strip()
                            expected_installer_relative_path = str(
                                external_proof_request.get("expected_installer_relative_path") or ""
                            ).strip()
                            required_host = str(external_proof_request.get("required_host") or "").strip().lower()
                            if not any("run-desktop-startup-smoke.sh" in token for token in normalized_commands):
                                support_packet_contract_violations.append(
                                    f"support packet {packet_id} install_diagnosis.external_proof_request.proof_capture_commands is missing run-desktop-startup-smoke.sh."
                                )
                            if expected_installer_relative_path and not any(
                                expected_installer_relative_path in token for token in normalized_commands
                            ):
                                support_packet_contract_violations.append(
                                    f"support packet {packet_id} install_diagnosis.external_proof_request.proof_capture_commands does not reference expected installer path '{expected_installer_relative_path}'."
                                )
                            if expected_installer_file_name and not any(
                                expected_installer_file_name in token for token in normalized_commands
                            ):
                                support_packet_contract_violations.append(
                                    f"support packet {packet_id} install_diagnosis.external_proof_request.proof_capture_commands does not reference expected installer file '{expected_installer_file_name}'."
                                )
                            if required_host:
                                expected_host_token = (
                                    f"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS={required_host}-host"
                                )
                                if not any(expected_host_token in token for token in normalized_commands):
                                    support_packet_contract_violations.append(
                                        f"support packet {packet_id} install_diagnosis.external_proof_request.proof_capture_commands does not declare expected host token '{expected_host_token}'."
                                    )
                        tuple_id = str(external_proof_request.get("tuple_id") or "").strip()
                        expected_request = expected_external_proof_request_by_tuple.get(tuple_id)
                        if release_channel_external_proof_source_present:
                            if expected_request is None:
                                support_packet_contract_violations.append(
                                    f"support packet {packet_id} external proof tuple '{tuple_id or 'unknown'}' is not present in release-channel external proof backlog."
                                )
                        if expected_request is not None:
                                for required_key in (
                                    "channel_id",
                                    "required_host",
                                    "expected_artifact_id",
                                    "expected_installer_file_name",
                                    "expected_installer_relative_path",
                                    "expected_public_install_route",
                                    "expected_startup_smoke_receipt_path",
                                ):
                                    actual_value = str(external_proof_request.get(required_key) or "").strip()
                                    expected_value = str(expected_request.get(required_key) or "").strip()
                                    if required_key == "expected_installer_relative_path":
                                        if not actual_value:
                                            installer_file = str(
                                                external_proof_request.get("expected_installer_file_name") or ""
                                            ).strip()
                                            actual_value = f"files/{installer_file}" if installer_file else ""
                                        if not expected_value:
                                            expected_installer_file = str(
                                                expected_request.get("expected_installer_file_name") or ""
                                            ).strip()
                                            expected_value = (
                                                f"files/{expected_installer_file}" if expected_installer_file else ""
                                            )
                                    if required_key == "required_host":
                                        actual_value = actual_value.lower()
                                        expected_value = expected_value.lower()
                                    if actual_value != expected_value:
                                        support_packet_contract_violations.append(
                                            f"support packet {packet_id} install_diagnosis.external_proof_request.{required_key} must match release-channel tuple truth '{expected_value}' but was '{actual_value}'."
                                        )
                                actual_expected_installer_sha256 = str(
                                    external_proof_request.get("expected_installer_sha256") or ""
                                ).strip().lower()
                                expected_expected_installer_sha256 = str(
                                    expected_request.get("expected_installer_sha256") or ""
                                ).strip().lower()
                                if actual_expected_installer_sha256 and (
                                    len(actual_expected_installer_sha256) != 64
                                    or any(ch not in "0123456789abcdef" for ch in actual_expected_installer_sha256)
                                ):
                                    support_packet_contract_violations.append(
                                        f"support packet {packet_id} install_diagnosis.external_proof_request.expected_installer_sha256 has invalid format."
                                    )
                                if expected_expected_installer_sha256 and (
                                    len(expected_expected_installer_sha256) != 64
                                    or any(ch not in "0123456789abcdef" for ch in expected_expected_installer_sha256)
                                ):
                                    support_packet_contract_violations.append(
                                        "release-channel external proof request "
                                        f"for tuple '{tuple_id}' has invalid expected_installer_sha256 format."
                                    )
                                if (
                                    actual_expected_installer_sha256 or expected_expected_installer_sha256
                                ) and actual_expected_installer_sha256 != expected_expected_installer_sha256:
                                    support_packet_contract_violations.append(
                                        "support packet "
                                        f"{packet_id} install_diagnosis.external_proof_request.expected_installer_sha256 "
                                        f"must match release-channel tuple truth '{expected_expected_installer_sha256}' "
                                        f"but was '{actual_expected_installer_sha256}'."
                                    )

                                tuple_entry_count_value = external_proof_request.get("tuple_entry_count")
                                if isinstance(tuple_entry_count_value, bool) or not isinstance(tuple_entry_count_value, int):
                                    support_packet_contract_violations.append(
                                        "support packet "
                                        f"{packet_id} is missing integer install_diagnosis.external_proof_request.tuple_entry_count."
                                    )
                                    actual_tuple_entry_count = -1
                                else:
                                    actual_tuple_entry_count = int(tuple_entry_count_value)
                                expected_tuple_entry_count = int(expected_request.get("tuple_entry_count") or 0)
                                if actual_tuple_entry_count != expected_tuple_entry_count:
                                    support_packet_contract_violations.append(
                                        "support packet "
                                        f"{packet_id} install_diagnosis.external_proof_request.tuple_entry_count "
                                        f"must match release-channel tuple truth {expected_tuple_entry_count!r} but was {actual_tuple_entry_count!r}."
                                    )

                                tuple_unique_value = external_proof_request.get("tuple_unique")
                                if not isinstance(tuple_unique_value, bool):
                                    support_packet_contract_violations.append(
                                        "support packet "
                                        f"{packet_id} is missing boolean install_diagnosis.external_proof_request.tuple_unique."
                                    )
                                actual_tuple_unique = bool(tuple_unique_value)
                                expected_tuple_unique = bool(expected_request.get("tuple_unique"))
                                if actual_tuple_unique != expected_tuple_unique:
                                    support_packet_contract_violations.append(
                                        "support packet "
                                        f"{packet_id} install_diagnosis.external_proof_request.tuple_unique "
                                        f"must match release-channel tuple truth {expected_tuple_unique!r} but was {actual_tuple_unique!r}."
                                    )

                                actual_required_proofs = sorted(
                                    {
                                        str(token or "").strip()
                                        for token in (required_proofs if isinstance(required_proofs, list) else [])
                                        if str(token or "").strip()
                                    }
                                )
                                expected_required_proofs = sorted(
                                    {
                                        str(token or "").strip()
                                        for token in (
                                            expected_request.get("required_proofs")
                                            if isinstance(expected_request.get("required_proofs"), list)
                                            else []
                                        )
                                        if str(token or "").strip()
                                    }
                                )
                                if actual_required_proofs != expected_required_proofs:
                                    support_packet_contract_violations.append(
                                        "support packet "
                                        f"{packet_id} install_diagnosis.external_proof_request.required_proofs "
                                        f"must match release-channel tuple truth {expected_required_proofs!r} but was {actual_required_proofs!r}."
                                    )

                                expected_smoke_contract = expected_request.get("startup_smoke_receipt_contract")
                                if isinstance(smoke_contract, dict) and isinstance(expected_smoke_contract, dict):
                                    for required_key in (
                                        "ready_checkpoint",
                                        "head_id",
                                        "platform",
                                        "rid",
                                        "host_class_contains",
                                    ):
                                        actual_value = str(smoke_contract.get(required_key) or "").strip()
                                        expected_value = str(expected_smoke_contract.get(required_key) or "").strip()
                                        if required_key in {"platform", "host_class_contains"}:
                                            actual_value = actual_value.lower()
                                            expected_value = expected_value.lower()
                                        if actual_value != expected_value:
                                            support_packet_contract_violations.append(
                                                "support packet "
                                                f"{packet_id} install_diagnosis.external_proof_request.startup_smoke_receipt_contract.{required_key} "
                                                f"must match release-channel tuple truth '{expected_value}' but was '{actual_value}'."
                                            )

                                    actual_status_any_of = sorted(
                                        {
                                            str(token or "").strip()
                                            for token in (
                                                smoke_contract.get("status_any_of")
                                                if isinstance(smoke_contract.get("status_any_of"), list)
                                                else []
                                            )
                                            if str(token or "").strip()
                                        }
                                    )
                                    expected_status_any_of = sorted(
                                        {
                                            str(token or "").strip()
                                            for token in (
                                                expected_smoke_contract.get("status_any_of")
                                                if isinstance(expected_smoke_contract.get("status_any_of"), list)
                                                else []
                                            )
                                            if str(token or "").strip()
                                        }
                                    )
                                    if actual_status_any_of != expected_status_any_of:
                                        support_packet_contract_violations.append(
                                            "support packet "
                                            f"{packet_id} install_diagnosis.external_proof_request.startup_smoke_receipt_contract.status_any_of "
                                            f"must match release-channel tuple truth {expected_status_any_of!r} but was {actual_status_any_of!r}."
                                        )

                                expected_commands = [
                                    str(token or "").strip()
                                    for token in (expected_request.get("proof_capture_commands") or [])
                                    if str(token or "").strip()
                                ]
                                if isinstance(proof_capture_commands, list) and expected_commands:
                                    actual_commands = [
                                        str(token or "").strip()
                                        for token in proof_capture_commands
                                        if str(token or "").strip()
                                    ]
                                    if not _proof_capture_commands_match_expected(actual_commands, expected_commands):
                                        support_packet_contract_violations.append(
                                            "support packet "
                                            f"{packet_id} install_diagnosis.external_proof_request.proof_capture_commands "
                                            "must exactly match release-channel tuple truth command sequence."
                                        )
                if install_truth_state == "tuple_not_on_promoted_shelf" and external_proof_required is not True:
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} with install_truth_state 'tuple_not_on_promoted_shelf' must declare external_proof_required=true."
                    )
            if not isinstance(fix_confirmation, dict):
                support_packet_contract_violations.append(
                    f"support packet {packet_id} is missing fix_confirmation."
                )
            elif not str(fix_confirmation.get("state") or "").strip():
                support_packet_contract_violations.append(
                    f"support packet {packet_id} is missing fix_confirmation.state."
                )
            if not isinstance(recovery_path, dict):
                support_packet_contract_violations.append(
                    f"support packet {packet_id} is missing recovery_path."
                )
            else:
                if not str(recovery_path.get("action_id") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing recovery_path.action_id."
                    )
                if not str(recovery_path.get("href") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing recovery_path.href."
                    )
        processed_support_packet_contract_violations = 0
        if support_packet_contract_violations:
            blocking_reasons.extend(support_packet_contract_violations[:5])
            if len(support_packet_contract_violations) > 5:
                blocking_reasons.append(
                    f"support packet install-truth contract has {len(support_packet_contract_violations) - 5} additional violations."
                )
            processed_support_packet_contract_violations = len(support_packet_contract_violations)
        reported_external_proof_required_case_count = _normalized_summary_count(
            support_summary.get("external_proof_required_case_count"),
            field_name="external_proof_required_case_count",
        )
        if support_external_proof_required_count != reported_external_proof_required_case_count:
            blocking_reasons.append(
                "support packet summary external_proof_required_case_count does not match packet install_diagnosis facts."
            )
        expected_external_proof_required_host_counts = _counter_map(
            [
                str((item.get("install_diagnosis") or {}).get("external_proof_request", {}).get("required_host") or "")
                .strip()
                .lower()
                for item in case_backed_packets
                if isinstance((item.get("install_diagnosis") or {}).get("external_proof_required"), bool)
                if (item.get("install_diagnosis") or {}).get("external_proof_required")
            ]
        )
        reported_external_proof_required_host_counts = _normalized_summary_counter(
            support_summary.get("external_proof_required_host_counts"),
            field_name="external_proof_required_host_counts",
            field_present="external_proof_required_host_counts" in support_summary,
        )
        if expected_external_proof_required_host_counts != reported_external_proof_required_host_counts:
            blocking_reasons.append(
                "support packet summary external_proof_required_host_counts does not match packet install_diagnosis facts."
            )
        expected_external_proof_required_tuple_counts = _counter_map(
            [
                str((item.get("install_diagnosis") or {}).get("external_proof_request", {}).get("tuple_id") or "").strip()
                for item in case_backed_packets
                if isinstance((item.get("install_diagnosis") or {}).get("external_proof_required"), bool)
                if (item.get("install_diagnosis") or {}).get("external_proof_required")
            ]
        )
        reported_external_proof_required_tuple_counts = _normalized_summary_counter(
            support_summary.get("external_proof_required_tuple_counts"),
            field_name="external_proof_required_tuple_counts",
            field_present="external_proof_required_tuple_counts" in support_summary,
        )
        if expected_external_proof_required_tuple_counts != reported_external_proof_required_tuple_counts:
            blocking_reasons.append(
                "support packet summary external_proof_required_tuple_counts does not match packet install_diagnosis facts."
            )
        expected_external_proof_backlog_count = len(external_proof_requests)
        reported_external_proof_backlog_count = _normalized_summary_count(
            support_summary.get("unresolved_external_proof_request_count"),
            field_name="unresolved_external_proof_request_count",
        )
        if expected_external_proof_backlog_count != reported_external_proof_backlog_count:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_count does not match release-channel external proof backlog."
            )
        expected_external_proof_backlog_host_counts = _counter_map(
            [str(item.get("required_host") or "").strip().lower() for item in external_proof_requests]
        )
        reported_external_proof_backlog_host_counts = _normalized_summary_counter(
            support_summary.get("unresolved_external_proof_request_host_counts"),
            field_name="unresolved_external_proof_request_host_counts",
            field_present="unresolved_external_proof_request_host_counts" in support_summary,
        )
        if expected_external_proof_backlog_host_counts != reported_external_proof_backlog_host_counts:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_host_counts does not match release-channel external proof backlog."
            )
        expected_external_proof_backlog_hosts = sorted(expected_external_proof_backlog_host_counts.keys())
        reported_external_proof_backlog_hosts = _normalized_summary_tokens(
            support_summary.get("unresolved_external_proof_request_hosts"),
            field_name="unresolved_external_proof_request_hosts",
            lower=True,
            field_present="unresolved_external_proof_request_hosts" in support_summary,
        )
        if expected_external_proof_backlog_hosts != reported_external_proof_backlog_hosts:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_hosts does not match release-channel external proof backlog."
            )
        expected_external_proof_backlog_tuple_counts = _counter_map(
            [str(item.get("tuple_id") or "").strip() for item in external_proof_requests]
        )
        reported_external_proof_backlog_tuple_counts = _normalized_summary_counter(
            support_summary.get("unresolved_external_proof_request_tuple_counts"),
            field_name="unresolved_external_proof_request_tuple_counts",
            field_present="unresolved_external_proof_request_tuple_counts" in support_summary,
        )
        if expected_external_proof_backlog_tuple_counts != reported_external_proof_backlog_tuple_counts:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_tuple_counts does not match release-channel external proof backlog."
            )
        expected_external_proof_backlog_tuples = sorted(expected_external_proof_backlog_tuple_counts.keys())
        reported_external_proof_backlog_tuples = _normalized_summary_tokens(
            support_summary.get("unresolved_external_proof_request_tuples"),
            field_name="unresolved_external_proof_request_tuples",
            lower=False,
            field_present="unresolved_external_proof_request_tuples" in support_summary,
        )
        if expected_external_proof_backlog_tuples != reported_external_proof_backlog_tuples:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_tuples does not match release-channel external proof backlog."
            )
        expected_external_proof_backlog_specs = {
            tuple_id: {
                "channel_id": str(item.get("channel_id") or "").strip().lower(),
                "tuple_entry_count": int(item.get("tuple_entry_count") or 0),
                "tuple_unique": bool(item.get("tuple_unique")),
                "required_host": str(item.get("required_host") or "").strip().lower(),
                "required_proofs": sorted(
                    set(str(token or "").strip() for token in (item.get("required_proofs") or []) if str(token or "").strip())
                ),
                "expected_artifact_id": str(item.get("expected_artifact_id") or "").strip(),
                "expected_installer_file_name": str(item.get("expected_installer_file_name") or "").strip(),
                "expected_installer_relative_path": str(
                    item.get("expected_installer_relative_path") or ""
                ).strip(),
                "expected_public_install_route": str(item.get("expected_public_install_route") or "").strip(),
                "expected_startup_smoke_receipt_path": str(item.get("expected_startup_smoke_receipt_path") or "").strip(),
                "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                    item.get("startup_smoke_receipt_contract")
                ),
                "proof_capture_commands": [
                    str(token or "").strip()
                    for token in (item.get("proof_capture_commands") or [])
                    if str(token or "").strip()
                ],
                **(
                    {
                        "expected_installer_sha256": str(
                            item.get("expected_installer_sha256") or ""
                        ).strip().lower()
                    }
                    if str(item.get("expected_installer_sha256") or "").strip()
                    else {}
                ),
            }
            for item in external_proof_requests
            for tuple_id in [str(item.get("tuple_id") or "").strip()]
            if tuple_id
        }
        expected_external_proof_backlog_specs = {
            key: expected_external_proof_backlog_specs[key] for key in sorted(expected_external_proof_backlog_specs)
        }
        reported_external_proof_backlog_specs = _normalized_external_proof_summary_specs(
            support_summary.get("unresolved_external_proof_request_specs"),
            field_present="unresolved_external_proof_request_specs" in support_summary,
        )
        reported_external_proof_backlog_specs = {
            key: _align_proof_capture_commands_with_expected(
                reported_external_proof_backlog_specs[key],
                expected_external_proof_backlog_specs.get(key),
            )
            for key in sorted(reported_external_proof_backlog_specs)
        }
        if expected_external_proof_backlog_specs != reported_external_proof_backlog_specs:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_specs does not match release-channel external proof backlog."
            )
        expected_external_proof_execution_plan_host_groups: Dict[str, Any] = {}
        grouped_external_proof_requests: Dict[str, List[Dict[str, Any]]] = {}
        for item in external_proof_requests:
            host = str(item.get("required_host") or "").strip().lower()
            if not host:
                continue
            grouped_external_proof_requests.setdefault(host, []).append(dict(item))
        for host in sorted(grouped_external_proof_requests):
            host_rows = sorted(
                grouped_external_proof_requests[host],
                key=lambda request_row: str(request_row.get("tuple_id") or "").strip(),
            )
            normalized_requests = []
            for request_row in host_rows:
                required_proofs = sorted(
                    {
                        str(token or "").strip().lower()
                        for token in (request_row.get("required_proofs") or [])
                        if str(token or "").strip()
                    }
                )
                proof_capture_commands = [
                    str(token or "").strip()
                    for token in (request_row.get("proof_capture_commands") or [])
                    if str(token or "").strip()
                ]
                normalized_requests.append(
                    {
                        "tuple_id": str(request_row.get("tuple_id") or "").strip(),
                        "tuple_entry_count": int(request_row.get("tuple_entry_count") or 0),
                        "tuple_unique": bool(request_row.get("tuple_unique")),
                        "channel_id": str(request_row.get("channel_id") or "").strip().lower(),
                        "head_id": str(request_row.get("head_id") or request_row.get("head") or "").strip().lower(),
                        "platform": str(request_row.get("platform") or "").strip().lower(),
                        "rid": str(request_row.get("rid") or "").strip().lower(),
                        "expected_artifact_id": str(request_row.get("expected_artifact_id") or "").strip(),
                        "expected_installer_file_name": str(
                            request_row.get("expected_installer_file_name") or ""
                        ).strip(),
                        "expected_installer_relative_path": str(
                            request_row.get("expected_installer_relative_path") or ""
                        ).strip(),
                        "expected_public_install_route": str(
                            request_row.get("expected_public_install_route") or ""
                        ).strip(),
                        "expected_startup_smoke_receipt_path": str(
                            request_row.get("expected_startup_smoke_receipt_path") or ""
                        ).strip(),
                        "required_proofs": required_proofs,
                        "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                            request_row.get("startup_smoke_receipt_contract")
                        ),
                        "proof_capture_commands": proof_capture_commands,
                        **(
                            {
                                "expected_installer_sha256": str(
                                    request_row.get("expected_installer_sha256") or ""
                                ).strip().lower()
                            }
                            if str(request_row.get("expected_installer_sha256") or "").strip()
                            else {}
                        ),
                    }
                )
            expected_external_proof_execution_plan_host_groups[host] = {
                "request_count": len(normalized_requests),
                "tuples": sorted(
                    [str(item.get("tuple_id") or "").strip() for item in normalized_requests if str(item.get("tuple_id") or "").strip()]
                ),
                "requests": normalized_requests,
            }
        expected_external_proof_execution_plan = {
            "request_count": len(external_proof_requests),
            "hosts": sorted(expected_external_proof_execution_plan_host_groups.keys()),
            "host_groups": {
                key: expected_external_proof_execution_plan_host_groups[key]
                for key in sorted(expected_external_proof_execution_plan_host_groups)
            },
        }
        reported_external_proof_execution_plan = _normalized_external_proof_execution_plan(
            support_packets.get("unresolved_external_proof_execution_plan"),
            field_present="unresolved_external_proof_execution_plan" in support_packets,
        )
        reported_external_proof_execution_plan = {
            **reported_external_proof_execution_plan,
            "host_groups": {
                host: {
                    **dict(group or {}),
                    "requests": [
                        _align_proof_capture_commands_with_expected(
                            dict(request or {}),
                            expected_external_proof_backlog_specs.get(str((request or {}).get("tuple_id") or "").strip()),
                        )
                        for request in (dict(group or {}).get("requests") or [])
                        if isinstance(request, dict)
                    ],
                }
                for host, group in sorted((reported_external_proof_execution_plan.get("host_groups") or {}).items())
                if isinstance(group, dict)
            },
        }
        if expected_external_proof_execution_plan != reported_external_proof_execution_plan:
            blocking_reasons.append(
                "support packet unresolved_external_proof_execution_plan does not match release-channel external proof backlog."
            )
        if len(support_packet_contract_violations) > processed_support_packet_contract_violations:
            new_violations = support_packet_contract_violations[processed_support_packet_contract_violations:]
            blocking_reasons.extend(new_violations[:5])
            if len(new_violations) > 5:
                blocking_reasons.append(
                    f"support packet install-truth contract has {len(new_violations) - 5} additional violations."
                )
    if bool(fleet_gate.get("require_support_recovery_path_contract")):
        packets = [dict(item) for item in (support_packets.get("packets") or []) if isinstance(item, dict)]
        for index, packet in enumerate(packets, start=1):
            packet_id = str(packet.get("packet_id") or "").strip() or f"packet#{index}"
            install_truth_state = str(packet.get("install_truth_state") or "").strip().lower()
            fix_confirmation = packet.get("fix_confirmation")
            recovery_path = packet.get("recovery_path")

            action_id = ""
            href = ""
            if not isinstance(recovery_path, dict):
                support_recovery_contract_violations.append(
                    f"support packet {packet_id} is missing recovery_path for recovery-route contract."
                )
            else:
                action_id = str(recovery_path.get("action_id") or "").strip().lower()
                href = str(recovery_path.get("href") or "").strip()
                if not action_id:
                    support_recovery_contract_violations.append(
                        f"support packet {packet_id} is missing recovery_path.action_id for recovery-route contract."
                    )
                else:
                    expected_href = RECOVERY_ACTION_HREF_MAP.get(action_id)
                    if expected_href is None:
                        support_recovery_contract_violations.append(
                            f"support packet {packet_id} has unsupported recovery_path.action_id '{action_id}'."
                        )
                    elif href != expected_href:
                        support_recovery_contract_violations.append(
                            f"support packet {packet_id} maps recovery_path.action_id '{action_id}' to '{href}' instead of '{expected_href}'."
                        )

            if not isinstance(fix_confirmation, dict):
                support_recovery_contract_violations.append(
                    f"support packet {packet_id} is missing fix_confirmation for recovery-route contract."
                )
            else:
                update_required = fix_confirmation.get("update_required")
                if not isinstance(update_required, bool):
                    support_recovery_contract_violations.append(
                        f"support packet {packet_id} fix_confirmation.update_required must be boolean for recovery-route contract."
                    )
                elif update_required and (action_id != "open_downloads" or href != "/downloads"):
                    support_recovery_contract_violations.append(
                        f"support packet {packet_id} requires download recovery when update_required is true."
                    )

                fix_state = str(fix_confirmation.get("state") or "").strip().lower()
                fixed_version = str(fix_confirmation.get("fixed_version") or "").strip()
                fixed_channel = str(fix_confirmation.get("fixed_channel") or "").strip()
                if (
                    fix_state
                    and fix_state != "no_fix_recorded"
                    and not fixed_version
                    and not fixed_channel
                ):
                    support_recovery_contract_violations.append(
                        f"support packet {packet_id} fix_confirmation.state '{fix_state}' requires fixed_version or fixed_channel."
                    )

            if install_truth_state in {"channel_mismatch", "tuple_not_on_promoted_shelf"} and (
                action_id != "open_downloads" or href != "/downloads"
            ):
                support_recovery_contract_violations.append(
                    f"support packet {packet_id} must route install_truth_state '{install_truth_state}' to /downloads."
                )

        if support_recovery_contract_violations:
            blocking_reasons.extend(support_recovery_contract_violations[:5])
            if len(support_recovery_contract_violations) > 5:
                blocking_reasons.append(
                    f"support packet recovery-route contract has {len(support_recovery_contract_violations) - 5} additional violations."
                )

    state = "ready"
    if blocking_reasons:
        state = "blocked"
    elif warning_reasons:
        state = "warning"

    external_blocking_reasons, local_blocking_reasons = classify_blocking_reasons(blocking_reasons)
    blocked_by_external_constraints_only = bool(external_blocking_reasons) and not local_blocking_reasons
    external_proof_hosts = sorted(
        {
            str(item.get("required_host") or "").strip().lower()
            for item in external_proof_requests
            if str(item.get("required_host") or "").strip()
        }
    )
    external_proof_host_label = ", ".join(external_proof_hosts) if external_proof_hosts else "required platform"
    external_proof_tuple_count = len(
        {
            str(item.get("tuple_id") or "").strip()
            for item in external_proof_requests
            if str(item.get("tuple_id") or "").strip()
        }
    )

    recommended_action = "Keep the journey under routine weekly proof."
    if blocking_reasons:
        if blocked_by_external_constraints_only:
            recommended_action = (
                f"Run the missing {external_proof_host_label} host proof lane for "
                f"{external_proof_tuple_count or len(external_proof_requests) or 1} desktop tuple(s) and ingest "
                "receipts before widening promotion or trust claims."
            )
        else:
            recommended_action = "Resolve the blocking artifact or posture gap before widening promotion or trust claims."
    elif warning_reasons:
        recommended_action = "Close the remaining target-stage or evidence-depth gap before calling the journey boring."

    external_proof_requests_public = [
        _public_external_proof_request(item)
        for item in external_proof_requests
        if isinstance(item, dict)
    ]

    evidence = {
        "history_snapshot_count": history_count,
        "support_packets_generated_at": support_generated_at,
        "required_artifacts": [str(item) for item in (fleet_gate.get("required_artifacts") or []) if str(item).strip()],
        "canonical_journeys": [str(item) for item in (row.get("canonical_journeys") or []) if str(item).strip()],
        "external_proof_requests": external_proof_requests_public,
    }
    signals = {
        "blocking_reason_count": len(blocking_reasons),
        "warning_reason_count": len(warning_reasons),
        "support_closure_waiting_count": int(support_summary.get("closure_waiting_on_release_truth") or 0),
        "support_needs_human_response_count": int(support_summary.get("needs_human_response") or 0),
        "support_update_required_case_count": int(support_summary.get("update_required_case_count") or 0),
        "support_update_required_routed_to_downloads_count": int(
            support_summary.get("update_required_routed_to_downloads_count") or 0
        ),
        "support_update_required_misrouted_case_count": int(
            support_summary.get("update_required_misrouted_case_count") or 0
        ),
        "support_external_proof_required_case_count": int(
            support_summary.get("external_proof_required_case_count") or 0
        ),
        "support_unresolved_external_proof_request_count": int(
            support_summary.get("unresolved_external_proof_request_count") or 0
        ),
        "support_install_truth_contract_violation_count": len(support_packet_contract_violations),
        "support_recovery_route_contract_violation_count": len(support_recovery_contract_violations),
        "external_blocking_reason_count": len(external_blocking_reasons),
        "local_blocking_reason_count": len(local_blocking_reasons),
        "blocked_by_external_constraints_only": blocked_by_external_constraints_only,
        "external_proof_request_count": len(external_proof_requests),
    }
    return {
        "id": str(row.get("id") or "").strip(),
        "title": str(row.get("title") or "").strip(),
        "user_promise": str(row.get("user_promise") or "").strip(),
        "state": state,
        "recommended_action": recommended_action,
        # Backward-compatible alias for consumers that still read `journeys[].blockers`.
        "blockers": blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "external_blocking_reasons": external_blocking_reasons,
        "local_blocking_reasons": local_blocking_reasons,
        "blocked_by_external_constraints_only": blocked_by_external_constraints_only,
        "external_proof_requests": external_proof_requests_public,
        "warning_reasons": warning_reasons,
        "owner_repos": [str(item) for item in (row.get("owner_repos") or []) if str(item).strip()],
        "canonical_journeys": [str(item) for item in (row.get("canonical_journeys") or []) if str(item).strip()],
        "scorecard_refs": dict(row.get("scorecard_refs") or {}),
        "fleet_gate": fleet_gate,
        "evidence": evidence,
        "signals": signals,
    }


def build_payload(
    *,
    registry_path: Path,
    status_plane_path: Path,
    progress_report_path: Path,
    progress_history_path: Path,
    support_packets_path: Path,
) -> Dict[str, Any]:
    registry = load_yaml(registry_path)
    status_plane = load_yaml(status_plane_path)
    progress_report = load_json(progress_report_path)
    progress_history = load_json(progress_history_path)
    support_packets = load_json(support_packets_path)
    compile_manifest = load_json(status_plane_path.parent / "compile.manifest.json")

    artifacts = {
        "compile_manifest": artifact_state("compile_manifest", compile_manifest, time_field="published_at"),
        "status_plane": artifact_state("status_plane", status_plane, time_field="generated_at"),
        "progress_report": artifact_state("progress_report", progress_report, time_field="generated_at"),
        "progress_history": artifact_state("progress_history", progress_history, time_field="generated_at"),
        "support_packets": artifact_state("support_packets", support_packets, time_field="generated_at"),
    }
    projects_by_id = {
        str(item.get("id") or "").strip(): dict(item)
        for item in (status_plane.get("projects") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    status_plane_projects_present = bool(projects_by_id)

    rows = []
    for row in registry.get("journey_gates") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            evaluate_journey(
                dict(row),
                projects_by_id=projects_by_id,
                status_plane_projects_present=status_plane_projects_present,
                artifacts=artifacts,
                progress_report=progress_report,
                progress_history=progress_history,
                support_packets=support_packets,
            )
        )

    blocked = [row for row in rows if row["state"] == "blocked"]
    warnings = [row for row in rows if row["state"] == "warning"]
    blocked_external_only = [row for row in blocked if row.get("blocked_by_external_constraints_only")]
    blocked_with_local = [row for row in blocked if not row.get("blocked_by_external_constraints_only")]
    blocked_external_only_requests = [
        dict(item)
        for row in blocked_external_only
        for item in (row.get("external_proof_requests") or [])
        if isinstance(item, dict)
    ]
    blocked_external_only_requests_by_tuple: Dict[str, Dict[str, Any]] = {}
    blocked_external_only_requests_without_tuple: List[Dict[str, Any]] = []
    for item in blocked_external_only_requests:
        tuple_id = str(item.get("tuple_id") or "").strip()
        if tuple_id:
            blocked_external_only_requests_by_tuple[tuple_id.lower()] = dict(item)
            continue
        blocked_external_only_requests_without_tuple.append(dict(item))
    blocked_external_only_unique_requests = [
        blocked_external_only_requests_by_tuple[key]
        for key in sorted(blocked_external_only_requests_by_tuple)
    ] + blocked_external_only_requests_without_tuple
    blocked_external_only_host_counts: Dict[str, int] = {}
    blocked_external_only_tuples: List[str] = []
    for item in blocked_external_only_unique_requests:
        host = str(item.get("required_host") or "").strip().lower()
        tuple_id = str(item.get("tuple_id") or "").strip()
        if host:
            blocked_external_only_host_counts[host] = blocked_external_only_host_counts.get(host, 0) + 1
        if tuple_id and tuple_id not in blocked_external_only_tuples:
            blocked_external_only_tuples.append(tuple_id)
    blocked_external_only_hosts = sorted(blocked_external_only_host_counts.keys())
    overall_state = "ready"
    if blocked:
        overall_state = "blocked"
    elif warnings:
        overall_state = "warning"

    generated_candidates = [
        parse_iso(item.get("at"))
        for item in artifacts.values()
        if isinstance(item, dict) and parse_iso(item.get("at")) is not None
    ]
    generated_at = iso(max(generated_candidates + [utc_now()]))
    recommended_action = "Journey proof is steady on current published evidence."
    blocking_mode = "none"
    if blocked:
        if blocked_external_only and len(blocked_external_only) == len(blocked):
            blocking_mode = "external_only"
            host_label = ", ".join(blocked_external_only_hosts) if blocked_external_only_hosts else "required platform"
            tuple_count = (
                len(blocked_external_only_tuples)
                or len(blocked_external_only_unique_requests)
                or len(blocked_external_only)
            )
            recommended_action = (
                f"Only external host-proof gaps remain: run the missing {host_label} proof lane for "
                f"{tuple_count} desktop tuple(s), ingest receipts, and then republish release truth."
            )
        elif blocked_with_local:
            blocking_mode = "mixed" if blocked_external_only else "local"
            recommended_action = "Resolve the blocking golden-journey gaps before widening publish claims."
    elif warnings:
        warning_text = "\n".join(
            reason
            for row in warnings
            for reason in row.get("warning_reasons", [])
            if isinstance(reason, str)
        )
        has_history_warning = "history depth" in warning_text
        has_evidence_warning = "evidence-depth" in warning_text or "evidence depth" in warning_text
        if has_history_warning or has_evidence_warning:
            recommended_action = "Close the target-stage and history-depth warnings before claiming the campaign OS is boringly proven."
        else:
            recommended_action = "Close the remaining target-stage warnings before claiming the campaign OS is boringly proven."

    return {
        "contract_name": "fleet.journey_gates",
        "contract_version": 1,
        "generated_at": generated_at,
        "source_registry_path": str(registry_path),
        "summary": {
            "overall_state": overall_state,
            "total_journey_count": len(rows),
            "ready_count": sum(1 for row in rows if row["state"] == "ready"),
            "warning_count": len(warnings),
            "blocked_count": len(blocked),
            "blocked_external_only_count": len(blocked_external_only),
            "blocked_with_local_count": len(blocked_with_local),
            "blocking_mode": blocking_mode,
            "blocked_external_only_hosts": blocked_external_only_hosts,
            "blocked_external_only_host_counts": blocked_external_only_host_counts,
            "blocked_external_only_tuples": blocked_external_only_tuples,
            "recommended_action": recommended_action,
        },
        "artifact_freshness": artifacts,
        "journeys": rows,
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize Fleet golden-journey release gate truth.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output path for JOURNEY_GATES.generated.json")
    parser.add_argument("--registry", default=None, help="optional path to GOLDEN_JOURNEY_RELEASE_GATES.yaml")
    parser.add_argument("--status-plane", default=str(DEFAULT_STATUS_PLANE), help="path to STATUS_PLANE.generated.yaml")
    parser.add_argument("--progress-report", default=str(DEFAULT_PROGRESS_REPORT), help="path to PROGRESS_REPORT.generated.json")
    parser.add_argument("--progress-history", default=str(DEFAULT_PROGRESS_HISTORY), help="path to PROGRESS_HISTORY.generated.json")
    parser.add_argument("--support-packets", default=str(DEFAULT_SUPPORT_PACKETS), help="path to SUPPORT_CASE_PACKETS.generated.json")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    out_path = Path(args.out).resolve()
    payload = build_payload(
        registry_path=resolve_registry_path(args.registry),
        status_plane_path=Path(args.status_plane).resolve(),
        progress_report_path=Path(args.progress_report).resolve(),
        progress_history_path=Path(args.progress_history).resolve(),
        support_packets_path=Path(args.support_packets).resolve(),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(out_path, json.dumps(payload, indent=2, sort_keys=False) + "\n")
    manifest_repo_root = repo_root_for_published_path(out_path)
    if manifest_repo_root is not None:
        support_packets_path = (
            manifest_repo_root / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
        )
        refreshed_weekly = _refresh_weekly_governor_packet_if_possible(
            manifest_repo_root,
            support_packets_path,
        )
        if not refreshed_weekly:
            write_compile_manifest(manifest_repo_root)
    print(f"wrote journey gates: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
