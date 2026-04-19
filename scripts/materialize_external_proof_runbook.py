#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import shlex
import tarfile
from pathlib import Path
from typing import Any

try:
    from scripts.external_proof_paths import (
        CHUMMER_COMPLETE_ROOT,
        DEFAULT_EXTERNAL_PROOF_COMMANDS_DIR,
        DEFAULT_EXTERNAL_PROOF_RUNBOOK,
        DEFAULT_JOURNEY_GATES,
        DEFAULT_RELEASE_CHANNEL,
        DEFAULT_SUPPORT_PACKETS,
        FLEET_ROOT,
        REGISTRY_RELEASE_CHANNEL_PATH,
        RELEASE_CHANNEL_REPO_ROOT,
        UI_DOCKER_DOWNLOADS_FILES_ROOT,
        UI_DOCKER_DOWNLOADS_ROOT,
        UI_DOCKER_DOWNLOADS_STARTUP_SMOKE_ROOT,
        UI_LOCALIZATION_RELEASE_GATE_PATH,
        UI_LOCAL_RELEASE_PROOF_PATH,
        UI_REPO_ROOT,
        build_download_path,
        normalize_external_proof_relative_path,
        normalize_external_proof_tuple_id,
    )
except ModuleNotFoundError:
    from external_proof_paths import (
        CHUMMER_COMPLETE_ROOT,
        DEFAULT_EXTERNAL_PROOF_COMMANDS_DIR,
        DEFAULT_EXTERNAL_PROOF_RUNBOOK,
        DEFAULT_JOURNEY_GATES,
        DEFAULT_RELEASE_CHANNEL,
        DEFAULT_SUPPORT_PACKETS,
        FLEET_ROOT,
        REGISTRY_RELEASE_CHANNEL_PATH,
        RELEASE_CHANNEL_REPO_ROOT,
        UI_DOCKER_DOWNLOADS_FILES_ROOT,
        UI_DOCKER_DOWNLOADS_ROOT,
        UI_DOCKER_DOWNLOADS_STARTUP_SMOKE_ROOT,
        UI_LOCALIZATION_RELEASE_GATE_PATH,
        UI_LOCAL_RELEASE_PROOF_PATH,
        UI_REPO_ROOT,
        build_download_path,
        normalize_external_proof_relative_path,
        normalize_external_proof_tuple_id,
    )


UTC = dt.timezone.utc
DEFAULT_OUT = DEFAULT_EXTERNAL_PROOF_RUNBOOK
DEFAULT_RELEASE_CHANNEL_MANIFEST_PATH = UI_REPO_ROOT / "Docker" / "Downloads" / "RELEASE_CHANNEL.generated.json"
FLEET_DESIGN_PRODUCT_ROOT = CHUMMER_COMPLETE_ROOT / "chummer-design"
FLEET_FLAGSHIP_PRODUCT_READINESS_MIRROR_PATH = (
    FLEET_ROOT / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
)
DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR = "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}"
DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR = "${CHUMMER_EXTERNAL_PROOF_AUTH_HEADER:-}"
DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR = "${CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER:-}"
DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR = "${CHUMMER_EXTERNAL_PROOF_COOKIE_JAR:-}"
DEFAULT_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD_EXPR = "${CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD:-0}"
ALLOWED_REQUIRED_HOSTS = frozenset({"windows", "macos", "linux"})
ALLOWED_REQUIRED_PROOFS = frozenset({"promoted_installer_artifact", "startup_smoke_receipt"})
STARTUP_SMOKE_MAX_AGE_SECONDS = 7 * 24 * 3600
STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS = 300

def _post_capture_republish_commands(
    *,
    journey_gates_path: Path | None = None,
    release_channel_path: Path | None = None,
) -> list[str]:
    effective_journey_gates_path = journey_gates_path or (FLEET_ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json")
    effective_release_channel_path = release_channel_path or REGISTRY_RELEASE_CHANNEL_PATH
    chummer6_ui_html_report = (
        FLEET_DESIGN_PRODUCT_ROOT / "products" / "chummer" / "PROGRESS_REPORT.generated.html"
    )
    chummer6_html_preview = (
        FLEET_DESIGN_PRODUCT_ROOT / "products" / "chummer" / "PROGRESS_REPORT.generated.json"
    )
    return [
        f"cd {shlex.quote(str(UI_REPO_ROOT))} && ./scripts/generate-releases-manifest.sh",
        "cd "
        + shlex.quote(str(RELEASE_CHANNEL_REPO_ROOT))
        + " && python3 scripts/materialize_public_release_channel.py --manifest "
        + shlex.quote(str(DEFAULT_RELEASE_CHANNEL_MANIFEST_PATH))
        + " --downloads-dir "
        + shlex.quote(str(UI_DOCKER_DOWNLOADS_FILES_ROOT))
        + " --startup-smoke-dir "
        + shlex.quote(str(UI_DOCKER_DOWNLOADS_STARTUP_SMOKE_ROOT))
        + " --proof "
        + shlex.quote(str(UI_LOCAL_RELEASE_PROOF_PATH))
        + " --ui-localization-release-gate "
        + shlex.quote(str(UI_LOCALIZATION_RELEASE_GATE_PATH))
        + " --channel docker --version unpublished --published-at \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" --output .codex-studio/published/RELEASE_CHANNEL.generated.json",
        f"cd {shlex.quote(str(RELEASE_CHANNEL_REPO_ROOT))} && python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json",
        f"cd {shlex.quote(str(FLEET_ROOT))} && python3 scripts/materialize_status_plane.py --out .codex-studio/published/STATUS_PLANE.generated.yaml",
        f"cd {shlex.quote(str(FLEET_ROOT))} && python3 scripts/verify_status_plane_semantics.py --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml",
        "cd "
        + shlex.quote(str(FLEET_ROOT))
        + " && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json --html-out "
        + shlex.quote(str(chummer6_ui_html_report))
        + " --history-out .codex-studio/published/PROGRESS_HISTORY.generated.json --preview-out "
        + shlex.quote(str(chummer6_html_preview)),
        f"cd {shlex.quote(str(FLEET_ROOT))} && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --release-channel {shlex.quote(str(effective_release_channel_path))}",
        f"cd {shlex.quote(str(FLEET_ROOT))} && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml --progress-report .codex-studio/published/PROGRESS_REPORT.generated.json --progress-history .codex-studio/published/PROGRESS_HISTORY.generated.json --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
        "cd "
        + shlex.quote(str(FLEET_ROOT))
        + " && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates "
        + shlex.quote(str(effective_journey_gates_path))
        + " --release-channel "
        + shlex.quote(str(effective_release_channel_path))
        + " --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md",
        f"cd {shlex.quote(str(FLEET_ROOT))} && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel {shlex.quote(str(effective_release_channel_path))} --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands",
        "cd "
        + shlex.quote(str(FLEET_ROOT))
        + " && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json --mirror-out "
        + shlex.quote(str(FLEET_FLAGSHIP_PRODUCT_READINESS_MIRROR_PATH)),
        "cd "
        + shlex.quote(str(FLEET_DESIGN_PRODUCT_ROOT))
        + " && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json",
    ]


def _finalize_after_host_proof_commands(*, hosts: list[str], commands_dir: Path) -> list[str]:
    commands = [
        f"cd {shlex.quote(str(commands_dir))}",
    ]
    for host in hosts:
        host_token = _normalize_host_token(host)
        commands.append(f"./ingest-{host_token}-proof-bundle.sh")
        commands.append(f"./validate-{host_token}-proof.sh")
    commands.append("./republish-after-host-proof.sh")
    return commands


def _host_proof_lane_commands(*, host: str, commands_dir: Path) -> list[str]:
    host_token = _normalize_host_token(host)
    return [
        f"cd {shlex.quote(str(commands_dir))}",
        f"./preflight-{host_token}-proof.sh",
        f"./capture-{host_token}-proof.sh",
        f"./validate-{host_token}-proof.sh",
        f"./bundle-{host_token}-proof.sh",
    ]


def utc_now_iso() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> dt.datetime | None:
    raw = _normalize_text(value)
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


def _startup_smoke_payload_is_fresh(
    payload: Any,
    *,
    now: dt.datetime | None = None,
    max_age_seconds: int = STARTUP_SMOKE_MAX_AGE_SECONDS,
    max_future_skew_seconds: int = STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
) -> bool:
    if not isinstance(payload, dict):
        return False
    raw = next(
        (
            str(payload.get(key) or "").strip()
            for key in ("recordedAtUtc", "completedAtUtc", "generatedAt", "generated_at", "startedAtUtc")
            if str(payload.get(key) or "").strip()
        ),
        "",
    )
    if not raw:
        return False
    parsed = _parse_iso(raw)
    if parsed is None:
        return False
    current = now or dt.datetime.now(UTC)
    age_seconds = int((current - parsed).total_seconds())
    if age_seconds < -max_future_skew_seconds:
        return False
    if age_seconds < 0:
        age_seconds = 0
    return age_seconds <= max_age_seconds


def _startup_smoke_payload_freshness_detail(
    payload: Any,
    *,
    now: dt.datetime | None = None,
    max_age_seconds: int = STARTUP_SMOKE_MAX_AGE_SECONDS,
    max_future_skew_seconds: int = STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"fresh": False, "reason": "receipt_payload_not_object"}
    raw = next(
        (
            str(payload.get(key) or "").strip()
            for key in ("recordedAtUtc", "completedAtUtc", "generatedAt", "generated_at", "startedAtUtc")
            if str(payload.get(key) or "").strip()
        ),
        "",
    )
    if not raw:
        return {"fresh": False, "reason": "receipt_timestamp_missing"}
    parsed = _parse_iso(raw)
    if parsed is None:
        return {"fresh": False, "reason": f"receipt_timestamp_invalid:{raw}"}
    current = now or dt.datetime.now(UTC)
    age_seconds = int((current - parsed).total_seconds())
    if age_seconds < -max_future_skew_seconds:
        return {
            "fresh": False,
            "reason": (
                f"receipt_future_skew:recorded_at={raw}:age_seconds={age_seconds}:"
                f"max_future_skew_seconds={max_future_skew_seconds}"
            ),
            "recorded_at": raw,
            "age_seconds": age_seconds,
        }
    if age_seconds < 0:
        age_seconds = 0
    if age_seconds > max_age_seconds:
        return {
            "fresh": False,
            "reason": (
                f"receipt_stale:recorded_at={raw}:age_seconds={age_seconds}:"
                f"max_age_seconds={max_age_seconds}"
            ),
            "recorded_at": raw,
            "age_seconds": age_seconds,
        }
    return {
        "fresh": True,
        "reason": "receipt_fresh",
        "recorded_at": raw,
        "age_seconds": age_seconds,
    }


def _bundle_member_name(name: str) -> str:
    normalized = name.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip("/")


def _bundle_archive_is_reusable(bundle_archive: Path, *, expected_manifest: dict[str, Any]) -> bool:
    if not bundle_archive.is_file():
        return False
    try:
        with tarfile.open(bundle_archive, "r:gz") as archive:
            members = {
                _bundle_member_name(member.name): member
                for member in archive.getmembers()
                if member.isfile()
            }
            manifest_member = members.get("external-proof-manifest.json")
            if manifest_member is None:
                return False
            manifest_file = archive.extractfile(manifest_member)
            if manifest_file is None:
                return False
            manifest_payload = json.loads(manifest_file.read().decode("utf-8"))
            if manifest_payload != expected_manifest:
                return False
            for request in expected_manifest.get("requests") or []:
                if not isinstance(request, dict):
                    return False
                installer_relative = _normalize_text(request.get("expected_installer_bundle_relative_path"))
                installer_sha256 = _normalize_text(request.get("expected_installer_sha256")).lower()
                if installer_relative:
                    installer_member = members.get(installer_relative)
                    if installer_member is None:
                        return False
                    installer_file = archive.extractfile(installer_member)
                    if installer_file is None:
                        return False
                    if installer_sha256:
                        import hashlib

                        digest = hashlib.sha256(installer_file.read()).hexdigest().lower()
                        if digest != installer_sha256:
                            return False
                receipt_relative = _normalize_text(request.get("expected_startup_smoke_receipt_path"))
                if receipt_relative:
                    receipt_member = members.get(receipt_relative)
                    if receipt_member is None:
                        return False
                    receipt_file = archive.extractfile(receipt_member)
                    if receipt_file is None:
                        return False
                    receipt_payload = json.loads(receipt_file.read().decode("utf-8"))
                    if not _startup_smoke_payload_is_fresh(receipt_payload):
                        return False
            return True
    except Exception:
        return False


def _bundle_directory_is_reusable(bundle_dir: Path, *, expected_manifest: dict[str, Any]) -> bool:
    if not bundle_dir.is_dir():
        return False
    try:
        manifest_path = bundle_dir / "external-proof-manifest.json"
        if not manifest_path.is_file():
            return False
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_payload != expected_manifest:
            return False
        for request in expected_manifest.get("requests") or []:
            if not isinstance(request, dict):
                return False
            installer_relative = _normalize_text(request.get("expected_installer_bundle_relative_path"))
            installer_sha256 = _normalize_text(request.get("expected_installer_sha256")).lower()
            if installer_relative:
                installer_path = bundle_dir / installer_relative
                if not installer_path.is_file():
                    return False
                if installer_sha256:
                    import hashlib

                    digest = hashlib.sha256(installer_path.read_bytes()).hexdigest().lower()
                    if digest != installer_sha256:
                        return False
            receipt_relative = _normalize_text(request.get("expected_startup_smoke_receipt_path"))
            if receipt_relative:
                receipt_path = bundle_dir / receipt_relative
                if not receipt_path.is_file():
                    return False
                receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
                if not _startup_smoke_payload_is_fresh(receipt_payload):
                    return False
        return True
    except Exception:
        return False


def _inspect_bundle_directory_state(bundle_dir: Path, *, expected_manifest: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"reusable": False, "detail": ""}
    if not bundle_dir.is_dir():
        result["detail"] = "bundle_directory_missing"
        return result
    manifest_path = bundle_dir / "external-proof-manifest.json"
    if not manifest_path.is_file():
        result["detail"] = f"manifest_missing:{manifest_path}"
        return result
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["detail"] = f"manifest_invalid_json:{manifest_path}:{exc}"
        return result
    if manifest_payload != expected_manifest:
        result["detail"] = f"manifest_mismatch:{manifest_path}"
        return result
    for request in expected_manifest.get("requests") or []:
        if not isinstance(request, dict):
            result["detail"] = "manifest_request_invalid"
            return result
        installer_relative = _normalize_text(request.get("expected_installer_bundle_relative_path"))
        installer_sha256 = _normalize_text(request.get("expected_installer_sha256")).lower()
        if installer_relative:
            installer_path = bundle_dir / installer_relative
            if not installer_path.is_file():
                result["detail"] = f"installer_missing:{installer_path}"
                return result
            if installer_sha256:
                import hashlib

                digest = hashlib.sha256(installer_path.read_bytes()).hexdigest().lower()
                if digest != installer_sha256:
                    result["detail"] = (
                        f"installer_sha256_mismatch:{installer_path}:digest={digest}:expected={installer_sha256}"
                    )
                    return result
        receipt_relative = _normalize_text(request.get("expected_startup_smoke_receipt_path"))
        if receipt_relative:
            receipt_path = bundle_dir / receipt_relative
            if not receipt_path.is_file():
                result["detail"] = f"receipt_missing:{receipt_path}"
                return result
            try:
                receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            except Exception as exc:
                result["detail"] = f"receipt_invalid_json:{receipt_path}:{exc}"
                return result
            freshness = _startup_smoke_payload_freshness_detail(receipt_payload)
            if not freshness.get("fresh"):
                result["detail"] = f"{freshness.get('reason')}:{receipt_path}"
                return result
    result["reusable"] = True
    result["detail"] = "bundle_directory_reusable"
    return result


def _existing_bundle_state(
    *, commands_dir: Path, host_token: str, host: str, expected_manifest: dict[str, Any]
) -> dict[str, str | bool]:
    bundle_archive = commands_dir / f"{host_token}-proof-bundle.tgz"
    bundle_dir = commands_dir / "host-proof-bundles" / host_token
    archive_present = bundle_archive.is_file()
    directory_present = bundle_dir.is_dir()
    archive_reusable = _bundle_archive_is_reusable(bundle_archive, expected_manifest=expected_manifest)
    directory_state = _inspect_bundle_directory_state(bundle_dir, expected_manifest=expected_manifest)
    directory_reusable = bool(directory_state.get("reusable"))

    status = "missing"
    detail = ""
    if archive_reusable:
        status = "reusable_archive"
        detail = "bundle_archive_reusable"
    elif directory_reusable:
        status = "reusable_directory"
        detail = _normalize_text(directory_state.get("detail")) or "bundle_directory_reusable"
    elif archive_present:
        status = "stale_archive"
        detail = "bundle_archive_stale_or_invalid"
    elif directory_present:
        status = "stale_directory"
        detail = _normalize_text(directory_state.get("detail")) or "bundle_directory_stale_or_invalid"

    return {
        "status": status,
        "detail": detail,
        "archive_path": str(bundle_archive),
        "directory_path": str(bundle_dir),
        "archive_present": archive_present,
        "directory_present": directory_present,
        "archive_reusable": archive_reusable,
        "directory_reusable": directory_reusable,
        "host": host,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a host-grouped external-proof execution runbook from "
            "SUPPORT_CASE_PACKETS.generated.json."
        )
    )
    parser.add_argument("--support-packets", type=Path, default=DEFAULT_SUPPORT_PACKETS)
    parser.add_argument("--journey-gates", type=Path, default=DEFAULT_JOURNEY_GATES)
    parser.add_argument(
        "--release-channel",
        type=Path,
        default=DEFAULT_RELEASE_CHANNEL,
        help="Optional release-channel artifact path used in post-capture republish commands.",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--commands-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory for generated command scripts. "
            "Defaults to <out-dir>/external-proof-commands."
        ),
    )
    return parser.parse_args()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _startup_smoke_operating_system_hint(*, required_host: str = "", platform: str = "") -> str:
    host_token = _normalize_text(required_host).lower()
    platform_token = _normalize_text(platform).lower()
    normalized = host_token or platform_token
    if normalized == "windows":
        return "Windows"
    if normalized == "macos":
        return "macOS"
    if normalized == "linux":
        return "Linux"
    return ""


def _sanitize_proof_capture_command(
    value: Any, *, required_host: str = "", platform: str = ""
) -> str:
    raw = _normalize_text(value)
    if not raw:
        return ""
    normalized = raw
    operating_system_hint = _startup_smoke_operating_system_hint(
        required_host=required_host,
        platform=platform,
    )
    if "./scripts/run-desktop-startup-smoke.sh" in normalized:
        normalized = re.sub(
            r"(^|\s+)CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=[^\s]+(?=\s|$)",
            r"\1",
            normalized,
        ).strip()
        if operating_system_hint:
            normalized = normalized.replace(
                "./scripts/run-desktop-startup-smoke.sh",
                f"CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM={operating_system_hint} ./scripts/run-desktop-startup-smoke.sh",
                1,
            )
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized


def _proof_capture_command_dedupe_key(value: Any) -> str:
    raw = _normalize_text(value)
    if not raw:
        return ""
    normalized = re.sub(
        r"(^|\s+)CHUMMER_DESKTOP_STARTUP_SMOKE_OPERATING_SYSTEM=[^\s]+(?=\s|$)",
        r"\1",
        raw,
    ).strip()
    if "./scripts/run-desktop-startup-smoke.sh" in normalized:
        normalized = re.sub(r"\s+run-[^\s\"']+\s*$", "", normalized).strip()
    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized


def _normalized_platform(value: Any) -> str:
    return _normalize_text(value).lower()


def _normalized_token(value: Any) -> str:
    return str(value or "").strip()


def _normalized_required_proofs(
    value: Any, *, field: str, failures: list[str], required: set[str] = ALLOWED_REQUIRED_PROOFS
) -> list[str]:
    if not isinstance(value, list):
        failures.append(f"{field} must be a string array")
        return []
    if not value:
        return []
    normalized: set[str] = set()
    for token in value:
        if not isinstance(token, str):
            failures.append(
                f"{field} contains a non-string required_proofs token: {_normalized_token(token)!r}"
            )
            continue
        normalized_token = token.strip().lower()
        if normalized_token:
            normalized.add(normalized_token)
    if not normalized:
        return []
    unknown_tokens = sorted(normalized - required)
    if unknown_tokens:
        failures.append(
            f"{field} contains unsupported required proof token(s): " + ", ".join(unknown_tokens)
        )
    return sorted(normalized)


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    raw = _normalize_text(value)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _ordered_unique_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = _normalize_text(value).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _normalized_smoke_contract_map(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    status_tokens = source.get("status_any_of") or source.get("statusAnyOf") or []
    status_any_of = sorted(
        {
            _normalize_text(token).lower()
            for token in status_tokens
            if _normalize_text(token)
        }
    ) if isinstance(status_tokens, list) else []
    return {
        "status_any_of": status_any_of,
        "ready_checkpoint": _normalize_text(
            source.get("ready_checkpoint") or source.get("readyCheckpoint")
        ).lower(),
        "head_id": _normalize_text(source.get("head_id") or source.get("headId")).lower(),
        "platform": _normalize_text(source.get("platform")).lower(),
        "rid": _normalize_text(source.get("rid")).lower(),
        "host_class_contains": _normalize_text(
            source.get("host_class_contains") or source.get("hostClassContains")
        ).lower(),
    }


def _normalize_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "request_count": 0,
            "hosts": [],
            "host_groups": {},
            "generated_at": "",
            "release_channel_generated_at": "",
            "capture_deadline_hours": 0,
            "capture_deadline_utc": "",
        }

    request_count_raw = value.get("request_count")
    if request_count_raw is None:
        request_count_raw = value.get("requestCount")
    request_count = request_count_raw if isinstance(request_count_raw, int) and not isinstance(request_count_raw, bool) else 0

    raw_hosts = value.get("hosts")
    hosts: list[str] = []
    if isinstance(raw_hosts, list):
        hosts = _ordered_unique_strings(raw_hosts)

    raw_host_groups = value.get("host_groups")
    if raw_host_groups is None:
        raw_host_groups = value.get("hostGroups")
    host_groups: dict[str, Any] = {}
    if isinstance(raw_host_groups, dict):
        for raw_host, raw_group in raw_host_groups.items():
            host = _normalize_text(raw_host).lower()
            if not host or not isinstance(raw_group, dict):
                continue
            raw_requests = raw_group.get("requests")
            requests: list[dict[str, Any]] = []
            if isinstance(raw_requests, list):
                for row in raw_requests:
                    if not isinstance(row, dict):
                        continue
                    raw_tuple_id = (
                        row.get("tuple_id") if row.get("tuple_id") is not None else row.get("tupleId")
                    )
                    raw_required_host = (
                        row.get("required_host")
                        if row.get("required_host") is not None
                        else row.get("requiredHost")
                    )
                    commands_raw = row.get("proof_capture_commands")
                    if commands_raw is None:
                        commands_raw = row.get("proofCaptureCommands")
                    if isinstance(commands_raw, list):
                        commands: list[str] = []
                        for token in commands_raw:
                            normalized = _sanitize_proof_capture_command(
                                token,
                                required_host=_normalize_text(raw_required_host),
                                platform=_normalize_text(row.get("platform")).lower(),
                            )
                            if normalized:
                                commands.append(normalized)
                    else:
                        commands = []
                    required_proofs_raw = row.get("required_proofs")
                    if required_proofs_raw is None:
                        required_proofs_raw = row.get("requiredProofs")
                    tuple_parts = _normalize_text(raw_tuple_id).split(":")
                    inferred_head = tuple_parts[0].strip().lower() if len(tuple_parts) >= 1 else ""
                    inferred_rid = tuple_parts[1].strip().lower() if len(tuple_parts) >= 2 else ""
                    inferred_host = tuple_parts[2].strip().lower() if len(tuple_parts) >= 3 else ""
                    raw_platform = _normalize_text(row.get("platform")).lower()
                    inferred_platform = (
                        "windows" if inferred_host == "windows"
                        else "macos" if inferred_host == "macos"
                        else "linux" if inferred_host == "linux"
                        else ""
                    )
                    requests.append(
                        {
                            "tuple_id": _normalize_text(raw_tuple_id),
                            "head_id": _normalize_text(row.get("head_id") or row.get("headId")).lower() or inferred_head,
                            "platform": raw_platform or inferred_platform,
                            "rid": _normalize_text(row.get("rid")).lower() or inferred_rid,
                            "required_host": _normalize_text(raw_required_host).lower() or inferred_host,
                            "expected_artifact_id": _normalize_text(
                                row.get("expected_artifact_id") or row.get("expectedArtifactId")
                            ),
                            "expected_installer_file_name": _normalize_text(
                                row.get("expected_installer_file_name") or row.get("expectedInstallerFileName")
                            ),
                            "expected_installer_relative_path": _normalize_text(
                                row.get("expected_installer_relative_path")
                                or row.get("expectedInstallerRelativePath")
                            ),
                            "expected_installer_sha256": _normalize_text(
                                row.get("expected_installer_sha256") or row.get("expectedInstallerSha256")
                            ).lower(),
                            "expected_public_install_route": _normalize_text(
                                row.get("expected_public_install_route") or row.get("expectedPublicInstallRoute")
                            ),
                            "expected_startup_smoke_receipt_path": _normalize_text(
                                row.get("expected_startup_smoke_receipt_path")
                                or row.get("expectedStartupSmokeReceiptPath")
                            ),
                            "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                                row.get("startup_smoke_receipt_contract")
                                if row.get("startup_smoke_receipt_contract") is not None
                                else row.get("startupSmokeReceiptContract")
                            ),
                            "capture_deadline_utc": _normalize_text(
                                row.get("capture_deadline_utc") or row.get("captureDeadlineUtc")
                            ),
                            "required_proofs": _ordered_unique_strings(required_proofs_raw or []),
                            "proof_capture_commands": commands,
                            "local_evidence": dict(row.get("local_evidence") or row.get("localEvidence") or {}),
                        }
                    )
            tuples_raw = raw_group.get("tuples")
            if tuples_raw is None:
                tuples_raw = raw_group.get("tuple_ids") or raw_group.get("tupleIds")
            tuples: list[str] = []
            for raw_tuple_id in tuples_raw or []:
                tuple_id = _normalize_text(raw_tuple_id)
                if tuple_id:
                    tuples.append(tuple_id)
            host_groups[host] = {
                "request_count": int(raw_group.get("request_count") or raw_group.get("requestCount") or len(requests)),
                "tuples": tuples,
                "requests": requests,
            }
    if not hosts:
        hosts = list(host_groups.keys())
    return {
        "request_count": request_count or sum(
            int(group.get("request_count") or 0)
            for group in host_groups.values()
            if isinstance(group, dict)
        ),
        "hosts": hosts,
        "host_groups": host_groups,
        "generated_at": _normalize_text(value.get("generated_at") or value.get("generatedAt")),
        "release_channel_generated_at": _normalize_text(
            value.get("release_channel_generated_at") or value.get("releaseChannelGeneratedAt")
        ),
        "capture_deadline_hours": _safe_int(
            value.get("capture_deadline_hours")
            if value.get("capture_deadline_hours") is not None
            else value.get("captureDeadlineHours"),
            default=0,
        ),
        "capture_deadline_utc": _normalize_text(
            value.get("capture_deadline_utc") or value.get("captureDeadlineUtc")
        ),
    }


def _load_support_packets(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _load_journey_gates(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _journey_requests_plan(journey_gates: dict[str, Any], *, fallback_plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(journey_gates, dict):
        return {}
    journeys = journey_gates.get("journeys")
    if not isinstance(journeys, list):
        return {}
    requests_by_host: dict[str, dict[str, dict[str, Any]]] = {}
    for row in journeys:
        if not isinstance(row, dict):
            continue
        request_rows = row.get("external_proof_requests")
        if not isinstance(request_rows, list):
            continue
        for request in request_rows:
            if not isinstance(request, dict):
                continue
            tuple_id = _normalize_text(request.get("tuple_id") or request.get("tupleId"))
            required_host = _normalize_text(request.get("required_host") or request.get("requiredHost")).lower()
            if not tuple_id or not required_host:
                continue
            normalized_request = {
                "tuple_id": tuple_id,
                "head_id": _normalize_text(request.get("head_id") or request.get("headId")).lower(),
                "platform": _normalize_text(request.get("platform")).lower(),
                "rid": _normalize_text(request.get("rid")).lower(),
                "required_host": required_host,
                "expected_artifact_id": _normalize_text(request.get("expected_artifact_id") or request.get("expectedArtifactId")),
                "expected_installer_file_name": _normalize_text(
                    request.get("expected_installer_file_name") or request.get("expectedInstallerFileName")
                ),
                "expected_installer_relative_path": _normalize_text(
                    request.get("expected_installer_relative_path") or request.get("expectedInstallerRelativePath")
                ),
                "expected_installer_sha256": _normalize_text(
                    request.get("expected_installer_sha256") or request.get("expectedInstallerSha256")
                ).lower(),
                "expected_public_install_route": _normalize_text(
                    request.get("expected_public_install_route") or request.get("expectedPublicInstallRoute")
                ),
                "expected_startup_smoke_receipt_path": _normalize_text(
                    request.get("expected_startup_smoke_receipt_path") or request.get("expectedStartupSmokeReceiptPath")
                ),
                "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                    request.get("startup_smoke_receipt_contract") or request.get("startupSmokeReceiptContract")
                ),
                "capture_deadline_utc": _normalize_text(
                    request.get("capture_deadline_utc") or request.get("captureDeadlineUtc") or fallback_plan.get("capture_deadline_utc")
                ),
                "required_proofs": _ordered_unique_strings(
                    request.get("required_proofs") if request.get("required_proofs") is not None else request.get("requiredProofs")
                ),
                "proof_capture_commands": [
                    normalized
                    for token in (
                        request.get("proof_capture_commands")
                        if request.get("proof_capture_commands") is not None
                        else request.get("proofCaptureCommands")
                    ) or []
                    if (
                        normalized := _sanitize_proof_capture_command(
                            token,
                            required_host=required_host,
                            platform=_normalize_text(request.get("platform")).lower(),
                        )
                    )
                ],
            }
            requests_by_host.setdefault(required_host, {})[tuple_id] = normalized_request
    if not requests_by_host:
        return {}
    host_groups: dict[str, Any] = {}
    for host in requests_by_host.keys():
        requests = [requests_by_host[host][tuple_id] for tuple_id in requests_by_host[host].keys()]
        host_groups[host] = {
            "request_count": len(requests),
            "tuples": [request["tuple_id"] for request in requests],
            "requests": requests,
        }
    plan_generated_at = (
        _normalize_text(fallback_plan.get("generated_at"))
        or _normalize_text(journey_gates.get("generated_at"))
    )
    return {
        "request_count": sum(int(group.get("request_count") or 0) for group in host_groups.values()),
        "hosts": list(host_groups.keys()),
        "host_groups": host_groups,
        "generated_at": plan_generated_at,
        "release_channel_generated_at": _normalize_text(fallback_plan.get("release_channel_generated_at")),
        "capture_deadline_hours": _safe_int(fallback_plan.get("capture_deadline_hours"), default=0),
        "capture_deadline_utc": _normalize_text(fallback_plan.get("capture_deadline_utc")),
    }


def _merge_plan_with_journey_gates(plan: dict[str, Any], journey_gates: dict[str, Any]) -> dict[str, Any]:
    merged = _normalize_plan(plan)
    journey_plan = _journey_requests_plan(journey_gates, fallback_plan=merged)
    if not journey_plan:
        return merged
    merged_host_groups = merged.get("host_groups")
    if not isinstance(merged_host_groups, dict):
        merged_host_groups = {}
    journey_host_groups = journey_plan.get("host_groups")
    if not isinstance(journey_host_groups, dict):
        journey_host_groups = {}
    for host, group in journey_host_groups.items():
        if host not in merged_host_groups or int((merged_host_groups.get(host) or {}).get("request_count") or 0) <= 0:
            merged_host_groups[host] = dict(group)
    merged["host_groups"] = merged_host_groups
    merged_hosts = [str(item) for item in (merged.get("hosts") or []) if str(item)]
    for host in journey_host_groups.keys():
        if host not in merged_hosts:
            merged_hosts.append(host)
    merged["hosts"] = merged_hosts
    merged["request_count"] = sum(
        int((group or {}).get("request_count") or 0)
        for group in merged_host_groups.values()
        if isinstance(group, dict)
    )
    if not _normalize_text(merged.get("generated_at")):
        merged["generated_at"] = _normalize_text(journey_plan.get("generated_at"))
    if not _normalize_text(merged.get("capture_deadline_utc")):
        merged["capture_deadline_utc"] = _normalize_text(journey_plan.get("capture_deadline_utc"))
    if not _safe_int(merged.get("capture_deadline_hours"), default=0):
        merged["capture_deadline_hours"] = _safe_int(journey_plan.get("capture_deadline_hours"), default=0)
    if not _normalize_text(merged.get("release_channel_generated_at")):
        merged["release_channel_generated_at"] = _normalize_text(journey_plan.get("release_channel_generated_at"))
    return merged


def _normalize_relative_path(value: Any, *, field: str) -> str:
    return normalize_external_proof_relative_path(value, field=field)


def _expected_installer_bundle_relative_path(row: dict[str, Any]) -> str:
    installer_relative_path = _normalize_relative_path(
        row.get("expected_installer_relative_path")
        or row.get("expectedInstallerRelativePath"),
        field="expected_installer_relative_path",
    )
    if installer_relative_path:
        return installer_relative_path
    installer_file_name = _normalize_text(
        row.get("expected_installer_file_name") or row.get("expectedInstallerFileName")
    )
    return f"files/{installer_file_name}" if installer_file_name else ""


def _request_startup_smoke_receipt_relative_path(row: dict[str, Any]) -> str:
    return _normalize_relative_path(
        row.get("expected_startup_smoke_receipt_path")
        or row.get("expectedStartupSmokeReceiptPath"),
        field="expected_startup_smoke_receipt_path",
    )


def _validate_plan_relative_paths(plan: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    host_groups = plan.get("host_groups")
    if not isinstance(host_groups, dict):
        failures.append("unresolved_external_proof_execution_plan.host_groups is missing or not an object")
        return failures
    for raw_host, raw_group in host_groups.items():
        host = _normalize_text(raw_host).lower()
        if not host:
            failures.append(
                "unresolved_external_proof_execution_plan.host_groups contains an empty host key"
            )
            continue
        if host not in ALLOWED_REQUIRED_HOSTS:
            failures.append(
                f"unresolved_external_proof_execution_plan.host_groups.{host} has unsupported required_host value: {host}"
            )
        if not isinstance(raw_group, dict):
            failures.append(
                f"unresolved_external_proof_execution_plan.host_groups.{host} is not an object"
            )
            continue
        raw_requests = raw_group.get("requests")
        if raw_requests is None:
            raw_requests = []
        request_count_for_host = len(raw_requests) if isinstance(raw_requests, list) else 0
        raw_tuples = raw_group.get("tuples")
        if raw_tuples is None:
            raw_tuples = raw_group.get("tuple_ids") or raw_group.get("tupleIds")
        if raw_tuples is not None and not isinstance(raw_tuples, list):
            failures.append(
                f"unresolved_external_proof_execution_plan.host_groups.{host}.tuples is not an array"
            )
            raw_tuples = []
        host_group_tuple_ids: set[str] = set()
        for tuple_index, tuple_value in enumerate(raw_tuples or []):
            tuple_id = _normalize_text(tuple_value)
            if not tuple_id:
                continue
            try:
                tuple_id = normalize_external_proof_tuple_id(
                    tuple_id,
                    field=f"unresolved_external_proof_execution_plan.host_groups.{host}.tuples[{tuple_index}]",
                )
                if tuple_id in host_group_tuple_ids:
                    if request_count_for_host <= 1:
                        failures.append(
                            f"unresolved_external_proof_execution_plan.host_groups.{host}.tuples[{tuple_index}] duplicate tuple_id: {tuple_id}"
                        )
                host_group_tuple_ids.add(tuple_id)
                tuple_parts = tuple_id.split(":")
                tuple_host = tuple_parts[2].strip() if len(tuple_parts) == 3 else ""
                if tuple_host and tuple_host != host:
                    failures.append(
                        f"unresolved_external_proof_execution_plan.host_groups.{host}.tuples[{tuple_index}] tuple host mismatch: "
                        f"{tuple_id} (tuple host: {tuple_host})"
                    )
            except ValueError as exc:
                failures.append(f"{tuple_id}: tuple_id is invalid: {exc}")
        if not isinstance(raw_requests, list):
            failures.append(
                f"unresolved_external_proof_execution_plan.host_groups.{host}.requests is not an array"
            )
            continue
        request_tuple_ids: set[str] = set()
        for index, row in enumerate(raw_requests):
            if not isinstance(row, dict):
                failures.append(
                    f"unresolved_external_proof_execution_plan.host_groups.{host}.requests[{index}] is not an object"
                )
                continue
            tuple_id = "<unknown>"
            raw_tuple_id = row.get("tuple_id") if row.get("tuple_id") is not None else row.get("tupleId")
            if not _normalize_text(raw_tuple_id):
                failures.append(
                    "unresolved_external_proof_execution_plan."
                    f"host_groups.{host}.requests[{index}].tuple_id is missing"
                )
            else:
                tuple_id = _normalize_text(raw_tuple_id)
                try:
                    tuple_id = normalize_external_proof_tuple_id(
                        tuple_id,
                        field=(
                            f"unresolved_external_proof_execution_plan.host_groups.{host}.requests[{index}].tuple_id"
                        ),
                    )
                    if tuple_id in request_tuple_ids:
                        failures.append(
                            f"unresolved_external_proof_execution_plan.host_groups.{host}.requests duplicate tuple_id: {tuple_id}"
                        )
                    request_tuple_ids.add(tuple_id)
                    tuple_parts = tuple_id.split(":")
                    tuple_host = tuple_parts[2].strip() if len(tuple_parts) == 3 else ""
                    if tuple_host and tuple_host != host:
                        failures.append(
                            f"unresolved_external_proof_execution_plan.host_groups.{host}.requests[{index}].tuple_id "
                            f"has tuple host mismatch: {tuple_id} (tuple host: {tuple_host})"
                        )
                    required_host = _normalized_platform(
                        row.get("required_host") or row.get("requiredHost") or row.get("platform")
                    )
                    if required_host:
                        if required_host not in ALLOWED_REQUIRED_HOSTS:
                            failures.append(f"{tuple_id}: requiredHost is invalid: {required_host}")
                        elif required_host != host:
                            failures.append(
                                f"{tuple_id}: requiredHost ({required_host}) does not match group host ({host})"
                            )
                    required_proofs = _normalized_required_proofs(
                        row.get("required_proofs") if row.get("required_proofs") is not None else row.get("requiredProofs"),
                        field=f"unresolved_external_proof_execution_plan.host_groups.{host}.requests[{index}].required_proofs",
                        failures=failures,
                    )
                    if not {"promoted_installer_artifact", "startup_smoke_receipt"}.issubset(
                        set(required_proofs)
                    ):
                        failures.append(
                            f"{tuple_id}: required_proofs is missing required tokens: startup_smoke_receipt"
                        )
                except ValueError as exc:
                    failures.append(f"{tuple_id}: tuple_id is invalid: {exc}")
            if not raw_tuple_id:
                tuple_id = "<unknown>"
            installer_path = row.get("expected_installer_relative_path") or row.get("expectedInstallerRelativePath")
            receipt_path = row.get("expected_startup_smoke_receipt_path") or row.get("expectedStartupSmokeReceiptPath")
            try:
                if str(installer_path or "").strip():
                    _normalize_relative_path(
                        installer_path,
                        field=f"unresolved_external_proof_execution_plan.host_groups.{host}.requests[{index}].expected_installer_relative_path",
                    )
            except ValueError as exc:
                failures.append(f"{tuple_id}: expected_installer_relative_path is invalid: {exc}")
            try:
                if str(receipt_path or "").strip():
                    _normalize_relative_path(
                        receipt_path,
                        field=f"unresolved_external_proof_execution_plan.host_groups.{host}.requests[{index}].expected_startup_smoke_receipt_path",
                    )
            except ValueError as exc:
                failures.append(f"{tuple_id}: expected_startup_smoke_receipt_path is invalid: {exc}")
    return failures


def _commands_for_group(group: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        for command in _commands_for_request(row):
            normalized = _normalize_text(command)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            commands.append(normalized)
    return commands


def _bundle_relative_paths_for_group(group: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        installer_path = _expected_installer_bundle_relative_path(row)
        receipt_relative_path = _request_startup_smoke_receipt_relative_path(row)
        for rel in (installer_path, receipt_relative_path):
            normalized = _normalize_text(rel)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            paths.append(normalized)
    return paths


def _bundle_manifest_payload_for_group(group: dict[str, Any], *, host: str) -> dict[str, Any]:
    requests: list[dict[str, Any]] = []
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        tuple_id = _normalize_text(row.get("tuple_id"))
        if not tuple_id:
            continue
        installer_bundle_relative_path = _expected_installer_bundle_relative_path(row)
        requests.append(
            {
                "tuple_id": tuple_id,
                "expected_installer_bundle_relative_path": installer_bundle_relative_path,
                "expected_startup_smoke_receipt_path": _request_startup_smoke_receipt_relative_path(row),
                "expected_installer_sha256": _normalize_text(
                    row.get("expected_installer_sha256")
                ).lower(),
            }
        )
    requests.sort(key=lambda item: item.get("tuple_id", ""))
    return {
        "schema_version": 1,
        "host": host.lower(),
        "request_count": len(requests),
        "requests": requests,
    }


def _bundle_commands_for_group(group: dict[str, Any], *, host_token: str, host: str) -> list[str]:
    bundle_paths = _bundle_relative_paths_for_group(group)
    manifest_payload = _bundle_manifest_payload_for_group(group, host=host)
    manifest_payload_json = json.dumps(manifest_payload, sort_keys=True)
    commands = [
        "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"",
        f"BUNDLE_ROOT=\"$SCRIPT_DIR/host-proof-bundles/{host_token}\"",
        "export BUNDLE_ROOT",
        "rm -rf \"$BUNDLE_ROOT\"",
        "mkdir -p \"$BUNDLE_ROOT\"",
        "python3 -c "
        + shlex.quote(
            "import json, os, pathlib; "
            "bundle_root=pathlib.Path(os.environ['BUNDLE_ROOT']); "
            f"payload=json.loads({manifest_payload_json!r}); "
            "manifest_path=bundle_root / 'external-proof-manifest.json'; "
            "manifest_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + '\\n', encoding='utf-8')"
        ),
    ]
    if not bundle_paths:
        commands.append(f"echo {shlex.quote('No host proof files were queued for bundling.')}")
        return commands
    for rel in bundle_paths:
        src = build_download_path(rel)
        dst = f"$BUNDLE_ROOT/{rel}"
        dst_dir = f"$BUNDLE_ROOT/{Path(rel).parent.as_posix()}"
        commands.append(f"mkdir -p \"{dst_dir}\"")
        commands.append(f"cp -f {shlex.quote(str(src))} \"{dst}\"")
    commands.extend(
        [
            f"tar -czf \"$SCRIPT_DIR/{host_token}-proof-bundle.tgz\" -C \"$BUNDLE_ROOT\" .",
            f"echo \"Wrote $SCRIPT_DIR/{host_token}-proof-bundle.tgz\"",
        ]
    )
    return commands


def _ingest_commands_for_group(group: dict[str, Any], *, host_token: str, host: str) -> list[str]:
    bundle_paths = _bundle_relative_paths_for_group(group)
    manifest_payload = _bundle_manifest_payload_for_group(group, host=host)
    manifest_payload_json = json.dumps(manifest_payload, sort_keys=True)
    target_root = UI_DOCKER_DOWNLOADS_ROOT
    commands = [
        "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"",
        f"BUNDLE_ARCHIVE=\"$SCRIPT_DIR/{host_token}-proof-bundle.tgz\"",
        f"BUNDLE_DIR=\"$SCRIPT_DIR/host-proof-bundles/{host_token}\"",
        "export BUNDLE_ARCHIVE",
        "export BUNDLE_DIR",
        f"TARGET_ROOT={shlex.quote(str(target_root))}",
        "export TARGET_ROOT",
        "mkdir -p \"$TARGET_ROOT\"",
        "if [ ! -s \"$BUNDLE_ARCHIVE\" ]; then",
        "  if [ ! -d \"$BUNDLE_DIR\" ]; then",
        "    echo \"Missing host proof bundle: $BUNDLE_ARCHIVE or $BUNDLE_DIR\"",
        "    exit 1",
        "  fi",
        "fi",
        "if [ ! -s \"$BUNDLE_ARCHIVE\" ]; then",
        "  python3 -c "
        + shlex.quote(
            "import os, pathlib, shutil\n"
            "bundle_dir=pathlib.Path(os.environ['BUNDLE_DIR'])\n"
            "target_root=pathlib.Path(os.environ['TARGET_ROOT'])\n"
            "bad=[]\n"
            "copied=[]\n"
            "for source in sorted(bundle_dir.rglob('*')):\n"
            "    if source.is_dir():\n"
            "        continue\n"
            "    relative=source.relative_to(bundle_dir)\n"
            "    if source.is_symlink() or any(part in ('..', '') for part in relative.parts):\n"
            "        bad.append(str(relative))\n"
            "        continue\n"
            "    destination=target_root / relative\n"
            "    destination.parent.mkdir(parents=True, exist_ok=True)\n"
            "    shutil.copy2(source, destination)\n"
            "    copied.append(str(relative))\n"
            "assert not bad, 'external-proof-bundle-path-unsafe:' + ','.join(sorted(set(bad)))\n"
            "assert copied, 'external-proof-bundle-empty:' + str(bundle_dir)"
        ),
        "else",
        "  python3 -c "
        + shlex.quote(
            "import os, pathlib, tarfile; "
            "bundle=pathlib.Path(os.environ['BUNDLE_ARCHIVE']); "
            "members=tarfile.open(bundle, 'r:gz').getmembers(); "
            "bad=[member.name for member in members if member.name.startswith('/') or '..' in pathlib.PurePosixPath(member.name).parts]; "
            "assert not any('..' in parts for parts in [pathlib.PurePosixPath(member.name).parts for member in members]), "
            "'external-proof-bundle-path-unsafe:' + ','.join(sorted(set(bad)))"
        ),
        "  tar -xzf \"$BUNDLE_ARCHIVE\" -C \"$TARGET_ROOT\"",
        "fi",
        "python3 -c "
        + shlex.quote(
            "import os, json, pathlib; "
            "manifest_path=pathlib.Path(os.environ['TARGET_ROOT']) / 'external-proof-manifest.json'; "
            f"expected=json.loads({manifest_payload_json!r}); "
            "assert manifest_path.is_file(), 'external-proof-bundle-manifest-missing:' + str(manifest_path); "
            "payload=json.loads(manifest_path.read_text(encoding='utf-8')); "
            "assert payload == expected, "
            "'external-proof-bundle-manifest-mismatch:' + str(manifest_path) + ':expected=' + "
            "json.dumps(expected, sort_keys=True) + ':actual=' + json.dumps(payload, sort_keys=True)"
        ),
    ]
    if not bundle_paths:
        commands.append(f"echo {shlex.quote('No expected host proof files were queued for ingest.')}")
        return commands
    for rel in bundle_paths:
        extracted = f"$TARGET_ROOT/{rel}"
        commands.append(f"test -s \"{extracted}\"")
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        tuple_id = _normalize_text(row.get("tuple_id")) or "<unknown>"
        installer_relative_path = _expected_installer_bundle_relative_path(row)
        installer_sha256 = _normalize_text(row.get("expected_installer_sha256")).lower()
        installer_bundle_relative_path = installer_relative_path
        if installer_bundle_relative_path and installer_sha256:
            commands.append(
                "python3 -c "
                + shlex.quote(
                "import hashlib, os, pathlib; "
                "target_root=pathlib.Path(os.environ['TARGET_ROOT']); "
                f"tuple_id={tuple_id!r}; "
                f"relative={installer_bundle_relative_path!r}; "
                f"expected={installer_sha256!r}; "
                "path=target_root / relative; "
                "assert path.is_file(), f'external-proof-bundle-installer-missing:{tuple_id}:{path}'; "
                "digest=hashlib.sha256(path.read_bytes()).hexdigest().lower(); "
                "assert digest==expected, f'installer-contract-mismatch:{tuple_id}:{path}:digest={digest}:expected={expected}'"
                )
            )
        receipt_relative_path = _normalize_text(row.get("expected_startup_smoke_receipt_path"))
        receipt_contract = _normalized_smoke_contract_map(row.get("startup_smoke_receipt_contract"))
        if receipt_relative_path and (
            receipt_contract.get("status_any_of")
            or receipt_contract.get("ready_checkpoint")
            or receipt_contract.get("head_id")
            or receipt_contract.get("platform")
            or receipt_contract.get("rid")
            or receipt_contract.get("host_class_contains")
        ):
            contract_payload = json.dumps(receipt_contract, sort_keys=True)
            commands.append(
                "python3 -c "
                + shlex.quote(
                    "import datetime as dt, json, os, pathlib; "
                    "target_root=pathlib.Path(os.environ['TARGET_ROOT']); "
                    f"relative={receipt_relative_path!r}; "
                    f"max_age_seconds={STARTUP_SMOKE_MAX_AGE_SECONDS}; "
                    f"max_future_skew_seconds={STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS}; "
                    "path=target_root / relative; "
                    "assert path.is_file(), 'external-proof-bundle-receipt-missing:' + str(path); "
                    "payload=json.loads(path.read_text(encoding='utf-8')); "
                    "payload=payload if isinstance(payload, dict) else {}; "
                    "raw=next((str(payload.get(key) or '').strip() for key in "
                    "('recordedAtUtc','completedAtUtc','generatedAt','generated_at','startedAtUtc') "
                    "if str(payload.get(key) or '').strip()), ''); "
                    "assert raw, 'startup-smoke-receipt-timestamp-missing:' + str(path); "
                    "raw = raw[:-1] + '+00:00' if raw.endswith('Z') else raw; "
                    "parsed=dt.datetime.fromisoformat(raw); "
                    "parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); "
                    "parsed=parsed.astimezone(dt.timezone.utc); "
                    "now=dt.datetime.now(dt.timezone.utc); "
                    "age_seconds=int((now-parsed).total_seconds()); "
                    "assert age_seconds >= -max_future_skew_seconds, "
                    "'startup-smoke-receipt-future-skew:' + str(path) + f':age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}'; "
                    "age_seconds = 0 if age_seconds < 0 else age_seconds; "
                    "assert age_seconds <= max_age_seconds, "
                    "'startup-smoke-receipt-stale:' + str(path) + f':age_seconds={age_seconds}:max_age_seconds={max_age_seconds}'"
                )
            )
            commands.append(
                "python3 -c "
                + shlex.quote(
                    "import json, os, pathlib; "
                    "target_root=pathlib.Path(os.environ['TARGET_ROOT']); "
                    f"tuple_id={tuple_id!r}; "
                    f"relative={receipt_relative_path!r}; "
                    f"contract=json.loads({contract_payload!r}); "
                    "path=target_root / relative; "
                    "assert path.is_file(), f'external-proof-bundle-receipt-missing:{tuple_id}:{path}'; "
                    "payload=json.loads(path.read_text(encoding='utf-8')); "
                    "payload=payload if isinstance(payload, dict) else {}; "
                    "status=str(payload.get('status') or '').strip().lower(); "
                    "expected_statuses=[str(token).strip().lower() for token in (contract.get('status_any_of') or []) if str(token).strip()]; "
                    "head_id=str(payload.get('headId') or '').strip().lower(); "
                    "platform=str(payload.get('platform') or '').strip().lower(); "
                    "rid=str(payload.get('rid') or '').strip().lower(); "
                    "ready_checkpoint=str(payload.get('readyCheckpoint') or '').strip().lower(); "
                    "host_class=str(payload.get('hostClass') or '').strip().lower(); "
                    "expected_head=str(contract.get('head_id') or '').strip().lower(); "
                    "expected_platform=str(contract.get('platform') or '').strip().lower(); "
                    "expected_rid=str(contract.get('rid') or '').strip().lower(); "
                    "expected_ready=str(contract.get('ready_checkpoint') or '').strip().lower(); "
                    "expected_host_contains=str(contract.get('host_class_contains') or '').strip().lower(); "
                    "assert ("
                    "(not expected_statuses or status in expected_statuses) and "
                    "(not expected_head or head_id == expected_head) and "
                    "(not expected_platform or platform == expected_platform) and "
                    "(not expected_rid or rid == expected_rid) and "
                    "(not expected_ready or ready_checkpoint == expected_ready) and "
                    "(not expected_host_contains or expected_host_contains in host_class), "
                    "f'receipt-contract-mismatch:{tuple_id}:{path}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}')"
                )
            )
    commands.append("echo \"Host proof bundle ingest complete: $BUNDLE_ARCHIVE\"")
    return commands


def _validation_commands_for_request(request: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    tuple_id = _normalize_text(request.get("tuple_id"))
    expected_artifact_id = _normalize_text(request.get("expected_artifact_id"))
    expected_public_install_route = _normalize_text(request.get("expected_public_install_route"))
    installer_file_name = _normalize_text(request.get("expected_installer_file_name"))
    installer_relative_path = _expected_installer_bundle_relative_path(request)
    installer_sha256 = _normalize_text(request.get("expected_installer_sha256")).lower()
    receipt_relative_path = _request_startup_smoke_receipt_relative_path(request)
    installer_path: Path | None = None
    if installer_relative_path:
        installer_path = build_download_path(installer_relative_path)
    elif installer_file_name:
        installer_path = UI_DOCKER_DOWNLOADS_FILES_ROOT / installer_file_name
    if installer_path is not None:
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && test -s {shlex.quote(str(installer_path))}"
        )
        if installer_sha256:
            commands.append(
                f"cd {shlex.quote(str(UI_REPO_ROOT))} && "
                "python3 -c "
                + shlex.quote(
                    "import hashlib, pathlib, sys; "
                    f"p=pathlib.Path({str(installer_path)!r}); "
                    f"expected={installer_sha256!r}; "
                    "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
                    "sys.exit(0) if digest==expected else sys.exit("
                    "f'installer-contract-mismatch:{p}:digest={digest}:expected={expected}')"
                )
            )
    if receipt_relative_path:
        receipt_path = build_download_path(receipt_relative_path)
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && test -s {shlex.quote(str(receipt_path))}"
        )
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && {_startup_smoke_receipt_freshness_command(receipt_path)}"
        )
        receipt_contract = _normalized_smoke_contract_map(request.get("startup_smoke_receipt_contract"))
        contract_payload = json.dumps(receipt_contract, sort_keys=True)
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && "
            "python3 -c "
            + shlex.quote(
                "import json, pathlib, sys; "
                f"p=pathlib.Path({str(receipt_path)!r}); "
                f"contract=json.loads({contract_payload!r}); "
                "payload=json.loads(p.read_text(encoding='utf-8')); "
                "payload=payload if isinstance(payload, dict) else {}; "
                "status=str(payload.get('status') or '').strip().lower(); "
                "expected_statuses=[str(token).strip().lower() for token in (contract.get('status_any_of') or []) if str(token).strip()]; "
                "head_id=str(payload.get('headId') or '').strip().lower(); "
                "platform=str(payload.get('platform') or '').strip().lower(); "
                "rid=str(payload.get('rid') or '').strip().lower(); "
                "ready_checkpoint=str(payload.get('readyCheckpoint') or '').strip().lower(); "
                "host_class=str(payload.get('hostClass') or '').strip().lower(); "
                "expected_head=str(contract.get('head_id') or '').strip().lower(); "
                "expected_platform=str(contract.get('platform') or '').strip().lower(); "
                "expected_rid=str(contract.get('rid') or '').strip().lower(); "
                "expected_ready=str(contract.get('ready_checkpoint') or '').strip().lower(); "
                "expected_host_contains=str(contract.get('host_class_contains') or '').strip().lower(); "
                "sys.exit(0) if ("
                "(not expected_statuses or status in expected_statuses) and "
                "(not expected_head or head_id == expected_head) and "
                "(not expected_platform or platform == expected_platform) and "
                "(not expected_rid or rid == expected_rid) and "
                "(not expected_ready or ready_checkpoint == expected_ready) and "
                "(not expected_host_contains or expected_host_contains in host_class)"
                ") else sys.exit("
                "f'receipt-contract-mismatch:{p}:status={status}:head={head_id}:platform={platform}:rid={rid}:ready={ready_checkpoint}:host_class={host_class}:contract={contract}')"
                )
            )
    if tuple_id and (expected_artifact_id or expected_public_install_route):
        commands.append(
            f"cd {shlex.quote(str(UI_REPO_ROOT))} && "
            "python3 -c "
            + shlex.quote(
                "import json, pathlib, sys; "
                f"p=pathlib.Path({str(DEFAULT_RELEASE_CHANNEL)!r}); "
                f"tuple_id={tuple_id!r}; "
                f"expected_artifact={expected_artifact_id!r}; "
                f"expected_route={expected_public_install_route!r}; "
                "payload=json.loads(p.read_text(encoding='utf-8')); "
                "coverage=payload.get('desktopTupleCoverage') if isinstance(payload, dict) else {}; "
                "coverage=coverage if isinstance(coverage, dict) else {}; "
                "rows=coverage.get('externalProofRequests') if isinstance(coverage, dict) else []; "
                "rows=rows if isinstance(rows, list) else []; "
                "row=next((item for item in rows if isinstance(item, dict) and str(item.get('tupleId') or item.get('tuple_id') or '').strip()==tuple_id), None); "
                "sys.exit(f'release-channel-contract-mismatch:{tuple_id}:missing-external-proof-row') if row is None else None; "
                "artifact=str(row.get('expectedArtifactId') or row.get('expected_artifact_id') or '').strip(); "
                "route=str(row.get('expectedPublicInstallRoute') or row.get('expected_public_install_route') or '').strip(); "
                "artifact_ok=(not expected_artifact) or artifact==expected_artifact; "
                "route_ok=(not expected_route) or route==expected_route; "
                "sys.exit(0) if artifact_ok and route_ok else sys.exit("
                "f'release-channel-contract-mismatch:{tuple_id}:artifact={artifact}:expected_artifact={expected_artifact}:route={route}:expected_route={expected_route}')"
            )
        )
    return commands


def _validation_commands_for_group(group: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        for command in _validation_commands_for_request(row):
            normalized = _normalize_text(command)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            commands.append(normalized)
    return commands


def _startup_smoke_receipt_freshness_command(receipt_path: Path) -> str:
    return (
        "python3 -c "
        + shlex.quote(
            "import datetime as dt, json, pathlib, sys; "
            f"p=pathlib.Path({str(receipt_path)!r}); "
            f"max_age_seconds={STARTUP_SMOKE_MAX_AGE_SECONDS}; "
            f"max_future_skew_seconds={STARTUP_SMOKE_MAX_FUTURE_SKEW_SECONDS}; "
            "payload=json.loads(p.read_text(encoding='utf-8')); "
            "payload=payload if isinstance(payload, dict) else {}; "
            "raw=next((str(payload.get(key) or '').strip() for key in "
            "('recordedAtUtc','completedAtUtc','generatedAt','generated_at','startedAtUtc') "
            "if str(payload.get(key) or '').strip()), ''); "
            "sys.exit(f'startup-smoke-receipt-timestamp-missing:{p}') if not raw else None; "
            "raw = raw[:-1] + '+00:00' if raw.endswith('Z') else raw; "
            "parsed=dt.datetime.fromisoformat(raw); "
            "parsed=parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc); "
            "parsed=parsed.astimezone(dt.timezone.utc); "
            "now=dt.datetime.now(dt.timezone.utc); "
            "age_seconds=int((now-parsed).total_seconds()); "
            "sys.exit("
            "f'startup-smoke-receipt-future-skew:{p}:age_seconds={age_seconds}:max_future_skew_seconds={max_future_skew_seconds}') "
            "if age_seconds < -max_future_skew_seconds else None; "
            "age_seconds = 0 if age_seconds < 0 else age_seconds; "
            "sys.exit(0) if age_seconds <= max_age_seconds else sys.exit("
            "f'startup-smoke-receipt-stale:{p}:age_seconds={age_seconds}:max_age_seconds={max_age_seconds}')"
        )
    )


def _shell_hint_for_host(host: str) -> str:
    normalized = _normalize_text(host).lower()
    if normalized == "windows":
        return (
            "Run canonical commands in Git Bash (or WSL bash). "
            "PowerShell wrappers are provided below when you need to stay in PowerShell."
        )
    return "Run commands in a POSIX shell (bash/zsh) on the required host."


def _powershell_wrappers(commands: list[str]) -> list[str]:
    wrapped: list[str] = []
    for command in commands:
        normalized = _normalize_text(command)
        if not normalized:
            continue
        escaped = normalized.replace("'", "''")
        wrapped.append(f"bash -lc '{escaped}'")
    return wrapped


def _preflight_commands_for_group(group: dict[str, Any], *, host: str) -> list[str]:
    commands: list[str] = [
        "if ! command -v python3 >/dev/null 2>&1; then echo 'external-proof-python3-missing' >&2; exit 1; fi",
        "if ! command -v curl >/dev/null 2>&1; then echo 'external-proof-curl-missing' >&2; exit 1; fi",
    ]
    normalized_host = _normalize_text(host).lower()
    if normalized_host == "macos":
        commands.append(
            "if ! command -v hdiutil >/dev/null 2>&1; then "
            "echo 'external-proof-macos-host-missing-hdiutil' >&2; "
            "echo 'Hint: run this lane on a macOS host (install xcode tools if needed) rather than Linux.' >&2; "
            "exit 1; fi"
        )
    elif normalized_host == "windows":
        commands.append(
            "if ! command -v powershell.exe >/dev/null 2>&1 && ! command -v pwsh >/dev/null 2>&1; then "
            "echo 'external-proof-powershell-missing' >&2; "
            "echo 'Hint: run this lane on a Windows host (Git Bash wrapper is supported for bash commands). ' >&2; "
            "exit 1; fi"
        )

    requires_signed_in_download = False
    for row in group.get("requests") or []:
        if not isinstance(row, dict):
            continue
        if _normalize_text(row.get("expected_public_install_route")):
            requires_signed_in_download = True
            break
    if requires_signed_in_download:
        commands.append(
            "if [ -z \""
            + DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR
            + "\" ] && [ -z \""
            + DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR
            + "\" ] && [ -z \""
            + DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR
            + "\" ] && [ \""
            + DEFAULT_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD_EXPR
            + "\" != \"1\" ]; then echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR (or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; exit 1; fi"
        )
    return commands


def _render_powershell_script(commands: list[str], *, no_op_message: str) -> str:
    wrapped = _powershell_wrappers(commands)
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "Set-StrictMode -Version Latest",
        "",
    ]
    if wrapped:
        for command in wrapped:
            lines.append(command)
            lines.append("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }")
    else:
        escaped = no_op_message.replace("'", "''")
        lines.append(f"Write-Output '{escaped}'")
    lines.append("exit 0")
    lines.append("")
    return "\n".join(lines)


def _installer_fetch_preflight_command(request: dict[str, Any]) -> str:
    expected_route = _normalize_text(request.get("expected_public_install_route"))
    installer_relative_path = _expected_installer_bundle_relative_path(request)
    installer_file_name = _normalize_text(request.get("expected_installer_file_name"))
    installer_sha256 = _normalize_text(request.get("expected_installer_sha256")).lower()
    if not expected_route:
        return ""
    if not expected_route.startswith("/"):
        expected_route = "/" + expected_route
    if installer_relative_path:
        installer_path = build_download_path(installer_relative_path)
    elif installer_file_name:
        installer_path = UI_DOCKER_DOWNLOADS_FILES_ROOT / installer_file_name
    else:
        return ""
    digest_preflight = ""
    post_download_contract_check = ""
    digest_post_download = ""
    installer_suffix = installer_path.name.lower()
    expected_magic = ""
    if installer_suffix.endswith(".exe"):
        expected_magic = "MZ"
    elif installer_suffix.endswith(".deb"):
        expected_magic = "!<arch>\\n"
    post_download_contract_check = (
        "; "
        + "python3 -c "
        + shlex.quote(
            "import os, pathlib, sys; "
            f"p=pathlib.Path({str(installer_path)!r}); "
            f"expected_magic={expected_magic!r}; "
            "sys.exit(f'installer-download-missing:{p}') if (not p.is_file()) else None; "
            "probe=p.read_bytes()[:8192]; "
            "probe_text=probe.decode('latin-1', errors='ignore').lower(); "
            "auth_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_AUTH_HEADER','')).strip()); "
            "cookie_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER','')).strip()); "
            "cookie_jar_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_JAR','')).strip()); "
            "html_like=('<!doctype html' in probe_text) or ('<html' in probe_text) or ('<head' in probe_text); "
            "sys.exit("
            "f'installer-download-html-response:{p}:auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:"
            "hint=signed-in-download-route-required-or-missing-auth') if html_like else None; "
            "sys.exit(0) if (not expected_magic or probe.startswith(expected_magic.encode('latin-1'))) else sys.exit("
            "f'installer-download-signature-mismatch:{p}:expected_magic={expected_magic}:"
            "auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:"
            "hint=unexpected-binary-format-or-route-response')"
        )
    )
    if installer_sha256:
        digest_preflight = (
            "python3 -c "
            + shlex.quote(
                "import hashlib, pathlib; "
                f"p=pathlib.Path({str(installer_path)!r}); "
                f"expected={installer_sha256!r}; "
                "import sys; "
                "sys.exit(0) if (not p.is_file()) else None; "
                "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
                "sys.exit(0) if digest==expected else print("
                "f'installer-preflight-sha256-mismatch:{p}:digest={digest}:expected={expected}') or p.unlink()"
            )
            + " && "
        )
        digest_post_download = (
            "; "
            + "python3 -c "
            + shlex.quote(
                "import hashlib, os, pathlib, sys; "
                f"p=pathlib.Path({str(installer_path)!r}); "
                f"expected={installer_sha256!r}; "
                "sys.exit(f'installer-download-missing:{p}') if (not p.is_file()) else None; "
                "digest=hashlib.sha256(p.read_bytes()).hexdigest().lower(); "
                "auth_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_AUTH_HEADER','')).strip()); "
                "cookie_header_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER','')).strip()); "
                "cookie_jar_set=bool(str(os.environ.get('CHUMMER_EXTERNAL_PROOF_COOKIE_JAR','')).strip()); "
                "sys.exit(0) if digest==expected else sys.exit("
                "f'installer-postdownload-sha256-mismatch:{p}:digest={digest}:expected={expected}:"
                "auth_header_set={auth_header_set}:cookie_header_set={cookie_header_set}:cookie_jar_set={cookie_jar_set}:"
                "hint=signed-in-download-route-required-or-bytes-drift')"
            )
        )
    return (
        f"cd {shlex.quote(str(UI_REPO_ROOT))} && "
        f"mkdir -p {shlex.quote(str(installer_path.parent))} && "
        f"{digest_preflight}"
        f"if [ ! -s {shlex.quote(str(installer_path))} ]; then "
        f"if [ -z \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ] && "
        f"[ -z \"{DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ] && "
        f"[ -z \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ] && "
        f"[ \"{DEFAULT_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD_EXPR}\" != \"1\" ]; then "
        "echo 'external-proof-auth-missing: set CHUMMER_EXTERNAL_PROOF_AUTH_HEADER, "
        "CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER, or CHUMMER_EXTERNAL_PROOF_COOKIE_JAR "
        "(or set CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1 to bypass)' >&2; "
        "exit 1; "
        "fi; "
        "curl_auth_args=(); "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ]; then "
        f"curl_auth_args+=( -H \"{DEFAULT_EXTERNAL_PROOF_AUTH_HEADER_EXPR}\" ); "
        "fi; "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ]; then "
        f"curl_auth_args+=( -H \"Cookie: {DEFAULT_EXTERNAL_PROOF_COOKIE_HEADER_EXPR}\" ); "
        "fi; "
        f"if [ -n \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ]; then "
        f"curl_auth_args+=( --cookie \"{DEFAULT_EXTERNAL_PROOF_COOKIE_JAR_EXPR}\" ); "
        "fi; "
        f"curl -fL --retry 3 --retry-delay 2 "
        "${curl_auth_args[@]} "
        f"\"{DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR}{expected_route}\" "
        f"-o {shlex.quote(str(installer_path))}; "
        f"fi"
        f"{post_download_contract_check}"
        f"{digest_post_download}"
    )


def _commands_for_request(request: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    normalized_seen: set[str] = set()
    preflight = _installer_fetch_preflight_command(request)
    if preflight:
        commands.append(preflight)
        normalized_preflight = _proof_capture_command_dedupe_key(preflight)
        if normalized_preflight:
            normalized_seen.add(normalized_preflight)
    for command in request.get("proof_capture_commands") or []:
        raw = _normalize_text(command)
        normalized = _proof_capture_command_dedupe_key(raw)
        if not raw or not normalized or normalized in normalized_seen:
            continue
        commands.append(raw)
        normalized_seen.add(normalized)
    return commands


def _normalize_host_token(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "-" for ch in _normalize_text(value).lower())
    text = text.strip("-")
    return text or "unknown"


def _render_bash_script(commands: list[str], *, no_op_message: str) -> str:
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    if commands:
        lines.extend(commands)
    else:
        lines.append(f"echo {shlex.quote(no_op_message)}")
    lines.append("")
    return "\n".join(lines)


def _write_file(path: Path, content: str, *, executable: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    mode = 0o755 if executable else 0o644
    os.chmod(path, mode)


def _materialize_command_files(
    plan: dict[str, Any], *, commands_dir: Path, journey_gates_path: Path | None = None, release_channel_path: Path | None = None
) -> dict[str, Any]:
    hosts = [str(item) for item in (plan.get("hosts") or []) if str(item)]
    host_groups = plan.get("host_groups") or {}
    host_files: list[dict[str, str]] = []
    commands_dir.mkdir(parents=True, exist_ok=True)

    for host in hosts:
        group = host_groups.get(host)
        if not isinstance(group, dict):
            continue
        host_token = _normalize_host_token(host)
        preflight_commands = _preflight_commands_for_group(group, host=host)
        capture_commands = _commands_for_group(group)
        validation_commands = _validation_commands_for_group(group)
        bundle_commands = _bundle_commands_for_group(group, host_token=host_token, host=host)
        ingest_commands = _ingest_commands_for_group(group, host_token=host_token, host=host)
        bundle_archive = commands_dir / f"{host_token}-proof-bundle.tgz"
        expected_manifest = _bundle_manifest_payload_for_group(group, host=host)
        if bundle_archive.exists() and not _bundle_archive_is_reusable(
            bundle_archive, expected_manifest=expected_manifest
        ):
            bundle_archive.unlink()
        preflight_script = commands_dir / f"preflight-{host_token}-proof.sh"
        capture_script = commands_dir / f"capture-{host_token}-proof.sh"
        validation_script = commands_dir / f"validate-{host_token}-proof.sh"
        bundle_script = commands_dir / f"bundle-{host_token}-proof.sh"
        ingest_script = commands_dir / f"ingest-{host_token}-proof-bundle.sh"
        host_lane_script = commands_dir / f"run-{host_token}-proof-lane.sh"
        _write_file(
            preflight_script,
            _render_bash_script(
                preflight_commands,
                no_op_message=f"No external-proof preflight commands were generated for host '{host}'.",
            ),
            executable=True,
        )
        _write_file(
            capture_script,
            _render_bash_script(
                capture_commands,
                no_op_message=f"No unresolved external-proof commands for host '{host}'.",
            ),
            executable=True,
        )
        _write_file(
            validation_script,
            _render_bash_script(
                validation_commands,
                no_op_message=f"No external-proof validation commands for host '{host}'.",
            ),
            executable=True,
        )
        _write_file(
            bundle_script,
            _render_bash_script(
                bundle_commands,
                no_op_message=f"No external-proof bundle commands were generated for host '{host}'.",
            ),
            executable=True,
        )
        _write_file(
            ingest_script,
            _render_bash_script(
                ingest_commands,
                no_op_message=f"No external-proof ingest commands were generated for host '{host}'.",
            ),
            executable=True,
        )
        _write_file(
            host_lane_script,
            _render_bash_script(
                _host_proof_lane_commands(host=host, commands_dir=commands_dir),
                no_op_message=f"No host proof lane commands were generated for host '{host}'.",
            ),
            executable=True,
        )
        host_file_row: dict[str, str] = {
            "host": host,
            "preflight_script": str(preflight_script),
            "capture_script": str(capture_script),
            "validation_script": str(validation_script),
            "bundle_script": str(bundle_script),
            "ingest_script": str(ingest_script),
            "host_lane_script": str(host_lane_script),
        }
        if host.lower() == "windows":
            capture_wrappers = _powershell_wrappers(capture_commands)
            validation_wrappers = _powershell_wrappers(validation_commands)
            bundle_wrappers = _powershell_wrappers(bundle_commands)
            ingest_wrappers = _powershell_wrappers(ingest_commands)
            capture_ps1 = commands_dir / f"capture-{host_token}-proof.ps1"
            validation_ps1 = commands_dir / f"validate-{host_token}-proof.ps1"
            bundle_ps1 = commands_dir / f"bundle-{host_token}-proof.ps1"
            ingest_ps1 = commands_dir / f"ingest-{host_token}-proof-bundle.ps1"
            preflight_ps1 = commands_dir / f"preflight-{host_token}-proof.ps1"
            host_lane_ps1 = commands_dir / f"run-{host_token}-proof-lane.ps1"
            _write_file(
                preflight_ps1,
                _render_powershell_script(
                    preflight_commands,
                    no_op_message=f"No external-proof preflight commands were generated for host '{host}'.",
                ),
                executable=False,
            )
            _write_file(
                capture_ps1,
                _render_powershell_script(
                    capture_commands,
                    no_op_message=f"No unresolved external-proof commands for host '{host}'.",
                ),
                executable=False,
            )
            _write_file(
                validation_ps1,
                _render_powershell_script(
                    validation_commands,
                    no_op_message=f"No external-proof validation commands for host '{host}'.",
                ),
                executable=False,
            )
            _write_file(
                bundle_ps1,
                _render_powershell_script(
                    bundle_commands,
                    no_op_message=f"No external-proof bundle commands were generated for host '{host}'.",
                ),
                executable=False,
            )
            _write_file(
                ingest_ps1,
                _render_powershell_script(
                    ingest_commands,
                    no_op_message=f"No external-proof ingest commands were generated for host '{host}'.",
                ),
                executable=False,
            )
            _write_file(
                host_lane_ps1,
                _render_powershell_script(
                    _host_proof_lane_commands(host=host, commands_dir=commands_dir),
                    no_op_message=f"No host proof lane commands were generated for host '{host}'.",
                ),
                executable=False,
            )
            host_file_row["preflight_powershell"] = str(preflight_ps1)
            host_file_row["capture_powershell"] = str(capture_ps1)
            host_file_row["validation_powershell"] = str(validation_ps1)
            host_file_row["bundle_powershell"] = str(bundle_ps1)
            host_file_row["ingest_powershell"] = str(ingest_ps1)
            host_file_row["host_lane_powershell"] = str(host_lane_ps1)
        host_files.append(host_file_row)

    post_capture_script = commands_dir / "republish-after-host-proof.sh"
    _write_file(
        post_capture_script,
        _render_bash_script(
            _post_capture_republish_commands(
                journey_gates_path=journey_gates_path,
                release_channel_path=release_channel_path,
            ),
            no_op_message="No post-capture republish commands were generated.",
        ),
        executable=True,
    )
    finalize_script = commands_dir / "finalize-external-host-proof.sh"
    _write_file(
        finalize_script,
        _render_bash_script(
            _finalize_after_host_proof_commands(hosts=hosts, commands_dir=commands_dir),
            no_op_message="No finalize commands were generated.",
        ),
        executable=True,
    )
    return {
        "commands_dir": str(commands_dir),
        "hosts": host_files,
        "post_capture_script": str(post_capture_script),
        "finalize_script": str(finalize_script),
    }


def materialize_markdown(
    plan: dict[str, Any], *, generated_at: str, command_files: dict[str, Any] | None = None
) -> str:
    lines: list[str] = []
    request_count = int(plan.get("request_count") or 0)
    hosts = [str(item) for item in (plan.get("hosts") or []) if str(item)]
    host_groups = plan.get("host_groups") or {}
    rendered_commands_dir = Path(".")
    if isinstance(command_files, dict) and _normalize_text(command_files.get("commands_dir")):
        rendered_commands_dir = Path(_normalize_text(command_files.get("commands_dir")))

    lines.append("# External Proof Runbook")
    lines.append("")
    lines.append(f"- generated_at: {generated_at}")
    lines.append(f"- unresolved_request_count: {request_count}")
    lines.append(f"- unresolved_hosts: {', '.join(hosts) if hosts else '(none)'}")
    lines.append(f"- plan_generated_at: {_normalize_text(plan.get('generated_at')) or '(missing)'}")
    lines.append(
        f"- release_channel_generated_at: {_normalize_text(plan.get('release_channel_generated_at')) or '(missing)'}"
    )
    lines.append(f"- capture_deadline_hours: {_safe_int(plan.get('capture_deadline_hours'), default=0)}")
    lines.append(f"- capture_deadline_utc: {_normalize_text(plan.get('capture_deadline_utc')) or '(missing)'}")
    lines.append("")
    lines.append("## Prerequisites")
    lines.append("")
    lines.append("- Run each host section on the matching native host (`macos` on macOS, `windows` on Windows).")
    lines.append(
        "- Provide signed-in download credentials before capture when public routes are account-gated."
    )
    lines.append(
        f"- Supported auth inputs: `CHUMMER_EXTERNAL_PROOF_AUTH_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_JAR`."
    )
    lines.append(
        "- Set `CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1` only when install routes are intentionally guest-readable."
    )
    lines.append(
        f"- Optional base URL override: `CHUMMER_EXTERNAL_PROOF_BASE_URL` (default `{DEFAULT_EXTERNAL_PROOF_BASE_URL_EXPR}`)."
    )
    lines.append("")
    if isinstance(command_files, dict) and _normalize_text(command_files.get("commands_dir")):
        lines.append("## Generated Command Files")
        lines.append("")
        lines.append(f"- commands_dir: `{_normalize_text(command_files.get('commands_dir'))}`")
        for host_row in command_files.get("hosts") or []:
            if not isinstance(host_row, dict):
                continue
            host = _normalize_text(host_row.get("host")) or "unknown"
            capture_script = _normalize_text(host_row.get("capture_script"))
            validation_script = _normalize_text(host_row.get("validation_script"))
            preflight_script = _normalize_text(host_row.get("preflight_script"))
            capture_powershell = _normalize_text(host_row.get("capture_powershell"))
            validation_powershell = _normalize_text(host_row.get("validation_powershell"))
            preflight_powershell = _normalize_text(host_row.get("preflight_powershell"))
            bundle_script = _normalize_text(host_row.get("bundle_script"))
            bundle_powershell = _normalize_text(host_row.get("bundle_powershell"))
            ingest_script = _normalize_text(host_row.get("ingest_script"))
            ingest_powershell = _normalize_text(host_row.get("ingest_powershell"))
            host_lane_script = _normalize_text(host_row.get("host_lane_script"))
            host_lane_powershell = _normalize_text(host_row.get("host_lane_powershell"))
            lines.append(f"- host `{host}`")
            if preflight_script:
                lines.append(f"  preflight_script: `{preflight_script}`")
            if capture_script:
                lines.append(f"  capture_script: `{capture_script}`")
            if validation_script:
                lines.append(f"  validation_script: `{validation_script}`")
            if bundle_script:
                lines.append(f"  bundle_script: `{bundle_script}`")
            if ingest_script:
                lines.append(f"  ingest_script: `{ingest_script}`")
            if host_lane_script:
                lines.append(f"  host_lane_script: `{host_lane_script}`")
            if preflight_powershell:
                lines.append(f"  preflight_powershell: `{preflight_powershell}`")
            if capture_powershell:
                lines.append(f"  capture_powershell: `{capture_powershell}`")
            if validation_powershell:
                lines.append(f"  validation_powershell: `{validation_powershell}`")
            if bundle_powershell:
                lines.append(f"  bundle_powershell: `{bundle_powershell}`")
            if ingest_powershell:
                lines.append(f"  ingest_powershell: `{ingest_powershell}`")
            if host_lane_powershell:
                lines.append(f"  host_lane_powershell: `{host_lane_powershell}`")
        post_capture_script = _normalize_text(command_files.get("post_capture_script"))
        if post_capture_script:
            lines.append(f"- post_capture_script: `{post_capture_script}`")
        finalize_script = _normalize_text(command_files.get("finalize_script"))
        if finalize_script:
            lines.append(f"- finalize_script: `{finalize_script}`")
        lines.append("")

    if request_count <= 0 or not host_groups:
        lines.append("No unresolved external-proof requests are currently queued.")
        lines.append("")
        return "\n".join(lines)

    for host in hosts:
        group = host_groups.get(host)
        if not isinstance(group, dict):
            continue
        host_token = _normalize_host_token(host)
        bundle_state = _existing_bundle_state(
            commands_dir=rendered_commands_dir,
            host_token=host_token,
            host=host,
            expected_manifest=_bundle_manifest_payload_for_group(group, host=host),
        )
        lines.append(f"## Host: {host}")
        lines.append("")
        lines.append(f"- shell_hint: {_shell_hint_for_host(host)}")
        if _normalize_text(host).lower() == "macos":
            lines.append("- platform_hint: macOS proofs require `hdiutil` on the proof host.")
        if _normalize_text(host).lower() == "windows":
            lines.append("- platform_hint: Windows proofs require `powershell.exe` or `pwsh` on the proof host.")
        lines.append(f"- request_count: {int(group.get('request_count') or 0)}")
        tuples = [str(item) for item in (group.get("tuples") or []) if str(item)]
        lines.append(f"- tuples: {', '.join(tuples) if tuples else '(none)'}")
        lines.append(f"- cached_bundle_status: `{_normalize_text(bundle_state.get('status')) or 'missing'}`")
        bundle_detail = _normalize_text(bundle_state.get("detail"))
        if bundle_detail:
            lines.append(f"- cached_bundle_detail: `{bundle_detail}`")
        lines.append(
            f"- cached_bundle_archive_path: `{_normalize_text(bundle_state.get('archive_path')) or '(missing)'}`"
        )
        lines.append(
            f"- cached_bundle_directory_path: `{_normalize_text(bundle_state.get('directory_path')) or '(missing)'}`"
        )
        lines.append("")
        lines.append("### Requested Tuples")
        lines.append("")
        for request in group.get("requests") or []:
            if not isinstance(request, dict):
                continue
            tuple_id = _normalize_text(request.get("tuple_id")) or "unknown"
            required_proofs = ", ".join(request.get("required_proofs") or []) or "(none)"
            artifact_id = _normalize_text(request.get("expected_artifact_id")) or "(missing)"
            installer = _normalize_text(request.get("expected_installer_file_name")) or "(missing)"
            installer_relative_path = _normalize_text(request.get("expected_installer_relative_path")) or "(missing)"
            installer_sha256 = _normalize_text(request.get("expected_installer_sha256")) or "(missing)"
            route = _normalize_text(request.get("expected_public_install_route")) or "(missing)"
            receipt_path = _normalize_text(request.get("expected_startup_smoke_receipt_path")) or "(missing)"
            local_evidence = dict(request.get("local_evidence") or {})
            local_installer = dict(local_evidence.get("installer_artifact") or {})
            local_receipt = dict(local_evidence.get("startup_smoke_receipt") or {})
            capture_deadline_utc = _normalize_text(request.get("capture_deadline_utc"))
            deadline_state = "unknown"
            deadline_dt = _parse_iso(capture_deadline_utc)
            if deadline_dt is not None:
                deadline_state = "overdue" if deadline_dt < dt.datetime.now(UTC) else "pending"
            lines.append(f"- `{tuple_id}`")
            lines.append(f"  required_proofs: `{required_proofs}`")
            lines.append(f"  artifact_id: `{artifact_id}`")
            lines.append(f"  installer_file: `{installer}`")
            lines.append(f"  installer_relative_path: `{installer_relative_path}`")
            lines.append(f"  installer_sha256: `{installer_sha256}`")
            lines.append(f"  public_route: `{route}`")
            lines.append(f"  startup_smoke_receipt: `{receipt_path}`")
            if local_installer:
                lines.append(
                    "  local_installer_state: "
                    f"`{_normalize_text(local_installer.get('state')) or 'unknown'}`"
                )
                installer_local_path = _normalize_text(local_installer.get("path"))
                if installer_local_path:
                    lines.append(f"  local_installer_path: `{installer_local_path}`")
            if local_receipt:
                lines.append(
                    "  local_startup_smoke_receipt_state: "
                    f"`{_normalize_text(local_receipt.get('state')) or 'unknown'}`"
                )
                receipt_local_path = _normalize_text(local_receipt.get("path"))
                if receipt_local_path:
                    lines.append(f"  local_startup_smoke_receipt_path: `{receipt_local_path}`")
                receipt_recorded_at = _normalize_text(local_receipt.get("recorded_at_utc"))
                if receipt_recorded_at:
                    lines.append(f"  local_startup_smoke_receipt_recorded_at: `{receipt_recorded_at}`")
                receipt_age_seconds = _normalize_text(local_receipt.get("age_seconds"))
                if receipt_age_seconds:
                    lines.append(f"  local_startup_smoke_receipt_age_seconds: `{receipt_age_seconds}`")
            lines.append(f"  capture_deadline_utc: `{capture_deadline_utc or '(missing)'}`")
            lines.append(f"  capture_deadline_state: `{deadline_state}`")
            tuple_commands = _commands_for_request(request)
            lines.append("  commands:")
            if not tuple_commands:
                lines.append("    - (none)")
            else:
                for command in tuple_commands:
                    lines.append(f"    - `{command}`")
        lines.append("")
        lines.append("### Commands (Host Consolidated)")
        lines.append("")
        commands = _commands_for_group(group)
        if not commands:
            lines.append("No proof-capture commands were provided for this host.")
        else:
            lines.append("```bash")
            for command in commands:
                lines.append(command)
            lines.append("```")
        validation_commands = _validation_commands_for_group(group)
        preflight_commands = _preflight_commands_for_group(group, host=host)
        bundle_commands = _bundle_commands_for_group(
            group,
            host_token=host_token,
            host=host,
        )
        ingest_commands = _ingest_commands_for_group(
            group,
            host_token=host_token,
            host=host,
        )
        lines.append("")
        lines.append("### Commands (Host Preflight)")
        lines.append("")
        if not preflight_commands:
            lines.append("No host preflight commands were generated for this host.")
        else:
            lines.append("```bash")
            for command in preflight_commands:
                lines.append(command)
            lines.append("```")
        lines.append("")
        lines.append("### Commands (Host Validation)")
        lines.append("")
        if not validation_commands:
            lines.append("No host validation commands were generated for this host.")
        else:
            lines.append("```bash")
            for command in validation_commands:
                lines.append(command)
            lines.append("```")
        lines.append("")
        lines.append("### Commands (Host Bundle)")
        lines.append("")
        if not bundle_commands:
            lines.append("No host bundle commands were generated for this host.")
        else:
            lines.append("```bash")
            for command in bundle_commands:
                lines.append(command)
            lines.append("```")
        lines.append("")
        lines.append("### Commands (Host Ingest)")
        lines.append("")
        if not ingest_commands:
            lines.append("No host ingest commands were generated for this host.")
        else:
            lines.append("```bash")
            for command in ingest_commands:
                lines.append(command)
            lines.append("```")
        lines.append("")
        lines.append("### Commands (Host Lane)")
        lines.append("")
        host_lane_commands = _host_proof_lane_commands(
            host=host,
            commands_dir=rendered_commands_dir,
        )
        if not host_lane_commands:
            lines.append("No host lane commands were generated for this host.")
        else:
            lines.append("```bash")
            for command in host_lane_commands:
                lines.append(command)
            lines.append("```")
        if host.lower() == "windows":
            wrappers = _powershell_wrappers(commands)
            validation_wrappers = _powershell_wrappers(validation_commands)
            preflight_wrappers = _powershell_wrappers(preflight_commands)
            bundle_wrappers = _powershell_wrappers(bundle_commands)
            ingest_wrappers = _powershell_wrappers(ingest_commands)
            host_lane_wrappers = _powershell_wrappers(host_lane_commands)
            lines.append("")
            lines.append("### Commands (PowerShell Preflight Wrappers)")
            lines.append("")
            if not preflight_wrappers:
                lines.append("No PowerShell preflight wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in preflight_wrappers:
                    lines.append(command)
                lines.append("```")
            lines.append("")
            lines.append("### Commands (PowerShell Wrappers)")
            lines.append("")
            if not wrappers:
                lines.append("No PowerShell wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in wrappers:
                    lines.append(command)
                lines.append("```")
            lines.append("")
            lines.append("### Commands (PowerShell Validation Wrappers)")
            lines.append("")
            if not validation_wrappers:
                lines.append("No PowerShell validation wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in validation_wrappers:
                    lines.append(command)
                lines.append("```")
            lines.append("")
            lines.append("### Commands (PowerShell Bundle Wrappers)")
            lines.append("")
            if not bundle_wrappers:
                lines.append("No PowerShell bundle wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in bundle_wrappers:
                    lines.append(command)
                lines.append("```")
            lines.append("")
            lines.append("### Commands (PowerShell Ingest Wrappers)")
            lines.append("")
            if not ingest_wrappers:
                lines.append("No PowerShell ingest wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in ingest_wrappers:
                    lines.append(command)
                lines.append("```")
            lines.append("")
            lines.append("### Commands (PowerShell Host Lane Wrappers)")
            lines.append("")
            if not host_lane_wrappers:
                lines.append("No PowerShell host lane wrappers were generated for this host.")
            else:
                lines.append("```powershell")
                for command in host_lane_wrappers:
                    lines.append(command)
                lines.append("```")
        lines.append("")

    lines.append("## After Host Proof Capture")
    lines.append("")
    lines.append(
        "Run these commands after macOS/Windows proofs land to validate receipts, ingest bundles, and republish release truth."
    )
    lines.append("")
    if isinstance(command_files, dict):
        finalize_script = _normalize_text(command_files.get("finalize_script"))
        if finalize_script:
            lines.append("```bash")
            lines.append(finalize_script)
            lines.append("```")
            lines.append("")
    lines.append("```bash")
    for command in _post_capture_republish_commands():
        lines.append(command)
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    support_packets = _load_support_packets(args.support_packets)
    support_packets_path = args.support_packets.resolve()
    journey_gates_path = args.journey_gates.resolve()
    should_merge_journey_gates = (
        support_packets_path == DEFAULT_SUPPORT_PACKETS.resolve()
        or journey_gates_path != DEFAULT_JOURNEY_GATES.resolve()
    )
    journey_gates = _load_journey_gates(journey_gates_path) if should_merge_journey_gates else {}
    plan = _merge_plan_with_journey_gates(
        _normalize_plan(support_packets.get("unresolved_external_proof_execution_plan")),
        journey_gates,
    )
    failures = _validate_plan_relative_paths(plan)
    if failures:
        print("external-proof materialize failed: malformed relative paths", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    commands_dir = (
        Path(args.commands_dir).resolve()
        if args.commands_dir is not None
        else (args.out.parent / "external-proof-commands").resolve()
    )
    command_files = _materialize_command_files(
        plan,
        commands_dir=commands_dir,
        journey_gates_path=journey_gates_path if should_merge_journey_gates else None,
        release_channel_path=args.release_channel.resolve(),
    )
    markdown = materialize_markdown(plan, generated_at=utc_now_iso(), command_files=command_files)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
