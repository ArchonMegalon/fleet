#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


ROOT = Path("/docker/fleet")
DEFAULT_OUT_PATH = Path("/docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json")
DEFAULT_RELEASE_CHANNEL_PATH = Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json")
DEFAULT_RUNTIME_ENV_CANDIDATES = (
    ROOT / "runtime.env",
    ROOT / ".env",
)
RUNTIME_ENV_PATHS_ENV = "FLEET_RUNTIME_ENV_PATHS"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize Fleet support-case decision packets from Hub support-case truth.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="JSON source path or URL for support cases. Accepts a list or a {items:[...]} payload.",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_PATH),
        help="output path for SUPPORT_CASE_PACKETS.generated.json",
    )
    parser.add_argument(
        "--bearer-token",
        default=None,
        help="optional bearer token for authenticated remote support-case sources",
    )
    parser.add_argument(
        "--release-channel",
        default=str(DEFAULT_RELEASE_CHANNEL_PATH),
        help="optional RELEASE_CHANNEL.generated.json path for install-specific diagnosis enrichment",
    )
    return parser.parse_args(argv or sys.argv[1:])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_env_candidates() -> List[Path]:
    configured = str(os.environ.get(RUNTIME_ENV_PATHS_ENV, "") or "").strip()
    if configured:
        return [Path(item).expanduser() for item in configured.split(os.pathsep) if str(item).strip()]
    return list(DEFAULT_RUNTIME_ENV_CANDIDATES)


def _load_runtime_env_defaults() -> Dict[str, str]:
    values: Dict[str, str] = {}
    for path in _runtime_env_candidates():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            clean_key = str(key or "").strip()
            if clean_key:
                values[clean_key] = str(value or "").strip()
    return values


def _source_value(explicit: str | None) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    for key in ("FLEET_SUPPORT_CASE_SOURCE", "CHUMMER6_HUB_SUPPORT_CASE_SOURCE", "SUPPORT_CASE_SOURCE"):
        value = str(os.environ.get(key, "") or "").strip()
        if value:
            return value
    runtime_defaults = _load_runtime_env_defaults()
    for key in ("FLEET_SUPPORT_CASE_SOURCE", "CHUMMER6_HUB_SUPPORT_CASE_SOURCE", "SUPPORT_CASE_SOURCE"):
        value = str(runtime_defaults.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _source_bearer_token(explicit: str | None) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    for key in ("SUPPORT_CASE_SOURCE_BEARER_TOKEN", "FLEET_INTERNAL_API_TOKEN"):
        value = str(os.environ.get(key, "") or "").strip()
        if value:
            return value
    runtime_defaults = _load_runtime_env_defaults()
    for key in ("SUPPORT_CASE_SOURCE_BEARER_TOKEN", "FLEET_INTERNAL_API_TOKEN"):
        value = str(runtime_defaults.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _load_json_source(source: str, *, bearer_token: str = "") -> tuple[Dict[str, Any], str]:
    raw = str(source or "").strip()
    if not raw:
        raise SystemExit("support-case source is required")
    if raw.startswith(("http://", "https://")):
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        parsed = urllib.parse.urlparse(raw)
        candidate_urls = [(raw, dict(headers))]
        if parsed.hostname == "host.docker.internal":
            fallback_url = parsed._replace(netloc=f"127.0.0.1:{parsed.port}" if parsed.port else "127.0.0.1").geturl()
            fallback_headers = dict(headers)
            fallback_headers.setdefault("X-Forwarded-Proto", "https")
            if all(candidate != fallback_url for candidate, _candidate_headers in candidate_urls):
                candidate_urls.append((fallback_url, fallback_headers))

        last_error: Exception | None = None
        for candidate, candidate_headers in candidate_urls:
            try:
                request = urllib.request.Request(candidate, headers=candidate_headers)
                with urllib.request.urlopen(request) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return _normalize_source_payload(data), candidate
            except (urllib.error.URLError, json.JSONDecodeError) as exc:
                last_error = exc
        curl_payload = _load_json_source_via_curl(raw, bearer_token=bearer_token)
        if curl_payload is not None:
            return _normalize_source_payload(curl_payload), raw
        raise SystemExit(f"unable to load support-case source {raw}: {last_error}") from last_error

    path = Path(raw).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"support-case source does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"support-case source is not valid JSON: {path}: {exc}") from exc
    return _normalize_source_payload(data), str(path)


def _load_json_source_via_curl(source: str, *, bearer_token: str = "") -> Any | None:
    cmd = ["curl", "-fsSL", "--max-time", "20"]
    if bearer_token:
        cmd.extend(["-H", f"Authorization: Bearer {bearer_token}"])
    cmd.append(source)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(str(result.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return None


def _source_kind(source_label: str) -> str:
    raw = str(source_label or "").strip().lower()
    if raw.startswith(("http://", "https://")):
        return "remote_url"
    return "local_file"


def _normalize_source_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, list):
        return {"items": payload, "count": len(payload)}
    if not isinstance(payload, dict):
        raise SystemExit("support-case source must be a JSON array or object")
    items = payload.get("items")
    if items is None and isinstance(payload.get("cases"), list):
        items = payload.get("cases")
    if items is None:
        raise SystemExit("support-case source object must contain an items or cases array")
    if not isinstance(items, list):
        raise SystemExit("support-case items must be an array")
    normalized = dict(payload)
    normalized["items"] = items
    normalized["count"] = int(payload.get("count") or len(items))
    return normalized


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip() or fallback


def _normalize_platform(value: Any) -> str:
    raw = _normalize_text(value).lower()
    if raw in {"win", "windows"}:
        return "windows"
    if raw in {"mac", "macos", "osx"}:
        return "macos"
    if raw in {"linux"}:
        return "linux"
    return raw


def _rid_for_platform_arch(platform: str, arch: str) -> str:
    if not platform:
        return ""
    arch_token = arch.lower()
    if arch_token in {"amd64", "x86_64"}:
        arch_token = "x64"
    if platform == "windows":
        return "win-arm64" if arch_token == "arm64" else "win-x64"
    if platform == "linux":
        return "linux-arm64" if arch_token == "arm64" else "linux-x64"
    if platform == "macos":
        return "osx-x64" if arch_token == "x64" else "osx-arm64"
    return ""


def _is_platform_token(value: str) -> bool:
    return _normalize_platform(value) in {"windows", "macos", "linux"}


def _canonical_tuple_id(
    tuple_id: Any,
    *,
    head: str = "",
    platform: str = "",
    rid: str = "",
) -> str:
    head_token = _normalize_text(head).lower()
    platform_token = _normalize_platform(platform)
    rid_token = _normalize_text(rid).lower()
    if head_token and platform_token and rid_token:
        return f"{head_token}:{rid_token}:{platform_token}"

    raw = _normalize_text(tuple_id).lower()
    if not raw:
        return ""
    parts = [segment.strip() for segment in raw.split(":")]
    if len(parts) != 3:
        return raw

    part_head, part_mid, part_last = parts
    mid_platform = _normalize_platform(part_mid)
    last_platform = _normalize_platform(part_last)
    if _is_platform_token(part_mid) and not _is_platform_token(part_last):
        return f"{part_head}:{part_last}:{mid_platform}"
    if _is_platform_token(part_last):
        return f"{part_head}:{part_mid}:{last_platform}"
    return raw


def _load_release_channel(path: str) -> Dict[str, Any]:
    if not str(path or "").strip():
        return {}
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _default_installer_file_name(head: str, rid: str, platform: str) -> str:
    if not head or not rid:
        return ""
    platform_token = _normalize_platform(platform)
    if platform_token == "windows":
        suffix = ".exe"
    elif platform_token == "macos":
        suffix = ".dmg"
    elif platform_token == "linux":
        suffix = ".deb"
    else:
        suffix = ""
    return f"chummer-{head}-{rid}-installer{suffix}"


def _default_launch_target(head: str, platform: str) -> str:
    head_token = _normalize_text(head).lower()
    platform_token = _normalize_platform(platform)
    if head_token == "blazor-desktop":
        return "Chummer.Blazor.Desktop.exe" if platform_token == "windows" else "Chummer.Blazor.Desktop"
    return "Chummer.Avalonia.exe" if platform_token == "windows" else "Chummer.Avalonia"


def _default_startup_smoke_receipt_contract(
    *,
    head: str,
    rid: str,
    platform: str,
    required_host: str,
) -> Dict[str, Any]:
    required_host_token = _normalize_platform(required_host) or _normalize_platform(platform) or "required"
    return {
        "ready_checkpoint": "pre_ui_event_loop",
        "head_id": _normalize_text(head).lower(),
        "platform": _normalize_platform(platform),
        "rid": _normalize_text(rid).lower(),
        "host_class_contains": required_host_token,
        "status_any_of": ["pass", "passed", "ready"],
    }


def _normalized_smoke_contract_map(
    contract: Any,
    *,
    default_contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    source = contract if isinstance(contract, dict) else {}
    defaults = default_contract if isinstance(default_contract, dict) else {}
    status_any_of_source = (
        source.get("status_any_of")
        or source.get("statusAnyOf")
        or defaults.get("status_any_of")
        or defaults.get("statusAnyOf")
        or []
    )
    status_any_of = [
        _normalize_text(token).lower()
        for token in status_any_of_source
        if _normalize_text(token)
    ]
    normalized: Dict[str, Any] = {
        "ready_checkpoint": _normalize_text(
            source.get("ready_checkpoint")
            or source.get("readyCheckpoint")
            or defaults.get("ready_checkpoint")
            or defaults.get("readyCheckpoint")
        ),
        "head_id": _normalize_text(
            source.get("head_id")
            or source.get("headId")
            or defaults.get("head_id")
            or defaults.get("headId")
        ).lower(),
        "platform": _normalize_platform(
            source.get("platform")
            or defaults.get("platform")
        ),
        "rid": _normalize_text(
            source.get("rid")
            or defaults.get("rid")
        ).lower(),
        "host_class_contains": _normalize_text(
            source.get("host_class_contains")
            or source.get("hostClassContains")
            or defaults.get("host_class_contains")
            or defaults.get("hostClassContains")
        ).lower(),
        "status_any_of": sorted(set(status_any_of)),
    }
    return normalized


def _derive_proof_capture_commands(
    *,
    head: str,
    rid: str,
    platform: str,
    installer_file_name: str,
    required_host: str,
) -> List[str]:
    head_token = _normalize_text(head).lower()
    rid_token = _normalize_text(rid).lower()
    platform_token = _normalize_platform(platform)
    if not head_token or not rid_token or not platform_token:
        return []
    repo_root = Path("/docker/chummercomplete/chummer6-ui")
    installer_name = _normalize_text(installer_file_name) or _default_installer_file_name(
        head=head_token,
        rid=rid_token,
        platform=platform_token,
    )
    if not installer_name:
        return []
    installer_path = repo_root / "Docker" / "Downloads" / "files" / installer_name
    startup_smoke_dir = repo_root / "Docker" / "Downloads" / "startup-smoke"
    host_class = _normalize_platform(required_host) or platform_token or "required"
    run_smoke = (
        f"cd {shlex.quote(str(repo_root))} && "
        f"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS={shlex.quote(host_class + '-host')} "
        f"./scripts/run-desktop-startup-smoke.sh "
        f"{shlex.quote(str(installer_path))} "
        f"{shlex.quote(head_token)} "
        f"{shlex.quote(rid_token)} "
        f"{shlex.quote(_default_launch_target(head=head_token, platform=platform_token))} "
        f"{shlex.quote(str(startup_smoke_dir))}"
    )
    refresh_manifest = (
        f"cd {shlex.quote(str(repo_root))} && "
        "./scripts/generate-releases-manifest.sh"
    )
    return [run_smoke, refresh_manifest]


def _release_channel_index(release_channel: Dict[str, Any]) -> Dict[str, Any]:
    channel_id = _normalize_text(release_channel.get("channelId") or release_channel.get("channel")).lower()
    tuple_rows = []
    external_proof_rows = []
    coverage = release_channel.get("desktopTupleCoverage")
    if isinstance(coverage, dict):
        tuple_rows = coverage.get("promotedInstallerTuples") or []
        external_proof_rows = coverage.get("externalProofRequests") or []
    rows: List[Dict[str, str]] = []
    for item in tuple_rows:
        if not isinstance(item, dict):
            continue
        head = _normalize_text(item.get("head")).lower()
        platform = _normalize_platform(item.get("platform"))
        rid = _normalize_text(item.get("rid")).lower()
        tuple_id = _canonical_tuple_id(
            item.get("tupleId") or item.get("tuple_id"),
            head=head,
            platform=platform,
            rid=rid,
        )
        if not tuple_id:
            continue
        rows.append(
            {
                "tuple_id": tuple_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "artifact_id": _normalize_text(item.get("artifactId") or item.get("artifact_id")),
            }
        )
    external_requests: List[Dict[str, Any]] = []
    external_request_tuple_counts: Dict[str, int] = {}
    for item in external_proof_rows:
        if not isinstance(item, dict):
            continue
        head = _normalize_text(item.get("head")).lower()
        platform = _normalize_platform(item.get("platform"))
        rid = _normalize_text(item.get("rid")).lower()
        required_host = _normalize_platform(item.get("requiredHost") or item.get("required_host"))
        default_smoke_contract = _default_startup_smoke_receipt_contract(
            head=head,
            rid=rid,
            platform=platform,
            required_host=required_host,
        )
        tuple_id = _canonical_tuple_id(
            item.get("tupleId") or item.get("tuple_id"),
            head=head,
            platform=platform,
            rid=rid,
        )
        required_proofs = [
            _normalize_text(token).lower()
            for token in (item.get("requiredProofs") or item.get("required_proofs") or [])
            if _normalize_text(token)
        ]
        if not tuple_id:
            continue
        external_request_tuple_counts[tuple_id] = external_request_tuple_counts.get(tuple_id, 0) + 1
        external_requests.append(
            {
                "tuple_id": tuple_id,
                "channel_id": channel_id,
                "head": head,
                "platform": platform,
                "rid": rid,
                "required_host": required_host,
                "required_proofs": sorted(set(required_proofs)),
                "expected_artifact_id": _normalize_text(item.get("expectedArtifactId") or item.get("expected_artifact_id")),
                "expected_installer_file_name": _normalize_text(
                    item.get("expectedInstallerFileName") or item.get("expected_installer_file_name")
                ),
                "expected_installer_relative_path": _normalize_text(
                    item.get("expectedInstallerRelativePath")
                    or item.get("expected_installer_relative_path")
                    or (
                        "files/"
                        + _normalize_text(
                            item.get("expectedInstallerFileName") or item.get("expected_installer_file_name")
                        )
                        if _normalize_text(item.get("expectedInstallerFileName") or item.get("expected_installer_file_name"))
                        else ""
                    )
                ),
                "expected_public_install_route": _normalize_text(
                    item.get("expectedPublicInstallRoute") or item.get("expected_public_install_route")
                ),
                "expected_startup_smoke_receipt_path": _normalize_text(
                    item.get("expectedStartupSmokeReceiptPath") or item.get("expected_startup_smoke_receipt_path")
                ),
                "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                    item.get("startupSmokeReceiptContract")
                    or item.get("startup_smoke_receipt_contract")
                    or {},
                    default_contract=default_smoke_contract,
                ),
                "proof_capture_commands": [
                    _normalize_text(token)
                    for token in (
                        item.get("proofCaptureCommands")
                        or item.get("proof_capture_commands")
                        or _derive_proof_capture_commands(
                            head=head,
                            rid=rid,
                            platform=platform,
                            installer_file_name=_normalize_text(
                                item.get("expectedInstallerFileName") or item.get("expected_installer_file_name")
                            ),
                            required_host=_normalize_platform(item.get("requiredHost") or item.get("required_host")),
                        )
                    )
                    if _normalize_text(token)
                ],
            }
        )
    deduped_external_requests_by_tuple: Dict[str, Dict[str, Any]] = {}
    for row in external_requests:
        tuple_id = _normalize_text(row.get("tuple_id"))
        if tuple_id:
            deduped_external_requests_by_tuple[tuple_id] = row
    deduped_external_requests = [
        deduped_external_requests_by_tuple[key]
        for key in sorted(deduped_external_requests_by_tuple.keys())
    ]
    for row in deduped_external_requests:
        tuple_id = _normalize_text(row.get("tuple_id"))
        row["tuple_entry_count"] = external_request_tuple_counts.get(tuple_id, 0)
        row["tuple_unique"] = external_request_tuple_counts.get(tuple_id, 0) <= 1

    return {
        "channel_id": channel_id,
        "status": _normalize_text(release_channel.get("status")).lower(),
        "version": _normalize_text(release_channel.get("version") or release_channel.get("releaseVersion")),
        "rollout_state": _normalize_text(release_channel.get("rolloutState") or release_channel.get("rollout_state")).lower(),
        "supportability_state": _normalize_text(
            release_channel.get("supportabilityState") or release_channel.get("supportability_state")
        ).lower(),
        "release_proof_status": _normalize_text(
            (release_channel.get("releaseProof") or {}).get("status")
            if isinstance(release_channel.get("releaseProof"), dict)
            else release_channel.get("releaseProofStatus")
        ).lower(),
        "fix_availability_summary": _normalize_text(release_channel.get("fixAvailabilitySummary") or release_channel.get("fix_availability_summary")),
        "promoted_tuples": rows,
        "external_proof_requests": deduped_external_requests,
    }


def _lookup_promoted_tuple(*, index: Dict[str, Any], head: str, platform: str, arch: str, tuple_id: str = "") -> Dict[str, str]:
    promoted_rows = [dict(row) for row in (index.get("promoted_tuples") or []) if isinstance(row, dict)]
    if tuple_id:
        canonical_tuple_id = _canonical_tuple_id(tuple_id)
        for row in promoted_rows:
            if _canonical_tuple_id(row.get("tuple_id")) == canonical_tuple_id:
                return row
    rid = _rid_for_platform_arch(platform, arch)
    if head and platform and rid:
        key = f"{head}:{platform}:{rid}"
        for row in promoted_rows:
            if _normalize_text(row.get("tuple_id")).lower() == key:
                return row
    return {}


def _lookup_external_proof_request(
    *,
    index: Dict[str, Any],
    head: str,
    platform: str,
    arch: str,
    tuple_id: str = "",
) -> Dict[str, Any]:
    request_rows = [dict(row) for row in (index.get("external_proof_requests") or []) if isinstance(row, dict)]
    if tuple_id:
        canonical_tuple_id = _canonical_tuple_id(tuple_id)
        for row in request_rows:
            if _canonical_tuple_id(row.get("tuple_id")) == canonical_tuple_id:
                return row
    rid = _rid_for_platform_arch(platform, arch)
    if head and platform and rid:
        for row in request_rows:
            row_head = _normalize_text(row.get("head")).lower()
            row_platform = _normalize_platform(row.get("platform"))
            row_rid = _normalize_text(row.get("rid")).lower()
            if row_head == head and row_platform == platform and row_rid == rid:
                return row
    return {}


def _install_truth_state(
    *,
    index: Dict[str, Any],
    case_release_channel: str,
    has_tuple_context: bool,
    tuple_match: bool,
) -> str:
    if not index:
        return "registry_unavailable"
    channel_id = _normalize_text(index.get("channel_id")).lower()
    if case_release_channel and channel_id and case_release_channel.lower() != channel_id:
        return "channel_mismatch"
    if has_tuple_context and not tuple_match:
        return "tuple_not_on_promoted_shelf"
    if tuple_match:
        return "promoted_tuple_match"
    return "insufficient_install_context"


def _fix_confirmation_state(item: Dict[str, Any], status: str) -> str:
    reporter_verification = _normalize_text(
        item.get("reporterVerificationState") or item.get("reporter_verification_state")
    ).lower()
    if reporter_verification == "confirmed_fixed":
        return "confirmed_fixed"
    if reporter_verification == "still_broken":
        return "still_broken"
    fixed_version = _normalize_text(item.get("fixedVersion") or item.get("fixed_version"))
    fixed_channel = _normalize_text(item.get("fixedChannel") or item.get("fixed_channel"))
    if fixed_version or fixed_channel:
        if status in {"fixed", "released_to_reporter_channel", "user_notified"}:
            return "awaiting_reporter_verification"
        return "fix_recorded_pre_release"
    return "no_fix_recorded"


def _version_requires_update(installed_version: str, fixed_version: str) -> bool:
    if not installed_version or not fixed_version:
        return False
    return installed_version.strip().lower() != fixed_version.strip().lower()


def _recovery_path(*, status: str, installation_id: str, install_truth_state: str, update_required: bool) -> Dict[str, str]:
    if not installation_id:
        return {
            "action_id": "open_account_access",
            "href": "/account/access",
            "reason": "No linked install id is attached, so support should relink or reclaim the affected install first.",
        }
    if update_required:
        return {
            "action_id": "open_downloads",
            "href": "/downloads",
            "reason": "A fix exists, but the linked install still reports an older build; route the user through the current release shelf before verification.",
        }
    if install_truth_state in {"channel_mismatch", "tuple_not_on_promoted_shelf"}:
        return {
            "action_id": "open_downloads",
            "href": "/downloads",
            "reason": "Install facts do not match the promoted shelf; route the user through the published installer/update shelf first.",
        }
    if status in {"fixed", "released_to_reporter_channel", "user_notified"}:
        return {
            "action_id": "open_support_timeline",
            "href": "/account/support",
            "reason": "Fix details are recorded; continue in support timeline to confirm the reporter-side outcome.",
        }
    return {
        "action_id": "open_support_timeline",
        "href": "/account/support",
        "reason": "Keep the case on the support timeline until release truth and closure evidence are complete.",
    }


def _decision_for_case(item: Dict[str, Any], *, release_channel_index: Dict[str, Any]) -> Dict[str, Any]:
    kind = _normalize_text(item.get("kind")).lower()
    status = _normalize_text(item.get("status")).lower()
    owner_repo = _normalize_text(item.get("candidateOwnerRepo") or item.get("candidate_owner_repo"), "chummer6-hub")
    design_impact = _normalize_bool(item.get("designImpactSuspected") or item.get("design_impact_suspected"))
    title = _normalize_text(item.get("title"), "Support case")
    summary = _normalize_text(item.get("summary"), title)

    primary_lane = "support"
    change_class = "type_b"
    target_repo = owner_repo
    affected_canon_files: List[str] = []
    reason = "Support case needs triage before it becomes a bounded delivery slice."
    exit_condition = "Case reaches released_to_reporter_channel, rejected, or deferred with a recorded reason."

    if kind == "crash_report":
        primary_lane = "code"
        change_class = "type_b"
        target_repo = owner_repo or "chummer6-ui"
        reason = "Crash reports default to code remediation in the repo that owns the failing desktop/runtime surface."
    elif kind == "bug_report":
        primary_lane = "code"
        change_class = "type_b"
        reason = "Bug reports default to code remediation unless triage proves a docs or canon contradiction."
    elif kind == "install_help":
        primary_lane = "support"
        change_class = "type_c"
        target_repo = owner_repo or "chummer6-hub"
        reason = "Install and account-help cases default to Hub-owned support closure backed by registry/update truth."
    elif kind == "feedback":
        primary_lane = "support"
        change_class = "type_c"
        reason = "Feedback starts in support until it proves a docs, queue, or canon contradiction."

    if design_impact:
        primary_lane = "canon" if kind == "feedback" else "mixed"
        change_class = "type_d"
        target_repo = "chummer6-design"
        affected_canon_files = [
            "FEEDBACK_AND_SIGNAL_OODA_LOOP.md",
            "FEEDBACK_AND_CRASH_STATUS_MODEL.md",
        ]
        reason = "Case content suggests public-story, docs, or policy drift and needs canon review instead of repo-local patching alone."

    if status in {"deferred", "rejected", "user_notified"}:
        primary_lane = "defer" if status == "deferred" else primary_lane
        reason = f"Case is already in terminal or quasi-terminal posture ({status}) and needs closure verification more than new execution."

    case_id = _normalize_text(item.get("caseId") or item.get("case_id"))
    packet_seed = "|".join(
        [
            case_id,
            owner_repo,
            primary_lane,
            change_class,
            _normalize_text(item.get("releaseChannel") or item.get("release_channel"), "-"),
            _normalize_text(item.get("headId") or item.get("head_id"), "-"),
        ]
    )
    packet_id = f"support_packet_{hashlib.sha1(packet_seed.encode('utf-8')).hexdigest()[:12]}"

    release_channel = _normalize_text(item.get("releaseChannel") or item.get("release_channel")).lower()
    head_id = _normalize_text(item.get("headId") or item.get("head_id")).lower()
    platform = _normalize_platform(item.get("platform"))
    arch = _normalize_text(item.get("arch")).lower()
    installation_id = _normalize_text(item.get("installationId") or item.get("installation_id"))
    installed_version = _normalize_text(
        item.get("installedVersion")
        or item.get("installed_version")
        or item.get("installedBuildVersion")
        or item.get("installed_build_version")
        or item.get("currentVersion")
        or item.get("current_version")
    )
    tuple_id = _normalize_text(item.get("desktopTupleId") or item.get("tupleId") or item.get("tuple_id")).lower()
    expected_tuple_id = _canonical_tuple_id(tuple_id)
    if not expected_tuple_id and head_id and platform:
        expected_rid = _rid_for_platform_arch(platform, arch)
        if expected_rid:
            expected_tuple_id = f"{head_id}:{expected_rid}:{platform}"
    fixed_version = _normalize_text(item.get("fixedVersion") or item.get("fixed_version"))
    fixed_channel = _normalize_text(item.get("fixedChannel") or item.get("fixed_channel"))
    promoted_tuple = _lookup_promoted_tuple(
        index=release_channel_index,
        head=head_id,
        platform=platform,
        arch=arch,
        tuple_id=expected_tuple_id,
    )
    external_proof_request = _lookup_external_proof_request(
        index=release_channel_index,
        head=head_id,
        platform=platform,
        arch=arch,
        tuple_id=expected_tuple_id,
    )
    has_tuple_context = bool(head_id and platform)
    install_truth_state = _install_truth_state(
        index=release_channel_index,
        case_release_channel=release_channel,
        has_tuple_context=has_tuple_context,
        tuple_match=bool(promoted_tuple),
    )
    fix_confirmation_state = _fix_confirmation_state(item, status)
    update_required = _version_requires_update(installed_version, fixed_version)
    recovery_path = _recovery_path(
        status=status,
        installation_id=installation_id,
        install_truth_state=install_truth_state,
        update_required=update_required,
    )

    return {
        "packet_id": packet_id,
        "kind": kind,
        "status": status,
        "target_repo": target_repo,
        "design_impact_suspected": design_impact,
        "primary_lane": primary_lane,
        "change_class": change_class,
        "reason": reason,
        "exit_condition": exit_condition,
        "affected_canon_files": affected_canon_files,
        "release_channel": release_channel,
        "head_id": head_id,
        "platform": platform,
        "arch": arch,
        "installation_id": installation_id,
        "installed_version": installed_version,
        "fixed_version": fixed_version,
        "fixed_channel": fixed_channel,
        "install_truth_state": install_truth_state,
        "install_diagnosis": {
            "registry_channel_id": _normalize_text(release_channel_index.get("channel_id")),
            "registry_release_channel_status": _normalize_text(release_channel_index.get("status")),
            "registry_release_version": _normalize_text(release_channel_index.get("version")),
            "registry_rollout_state": _normalize_text(release_channel_index.get("rollout_state")),
            "registry_supportability_state": _normalize_text(release_channel_index.get("supportability_state")),
            "registry_release_proof_status": _normalize_text(release_channel_index.get("release_proof_status")),
            "case_channel_matches_registry": bool(
                release_channel
                and _normalize_text(release_channel_index.get("channel_id"))
                and release_channel == _normalize_text(release_channel_index.get("channel_id")).lower()
            ),
            "promoted_tuple_id": _normalize_text(promoted_tuple.get("tuple_id")),
            "promoted_artifact_id": _normalize_text(promoted_tuple.get("artifact_id")),
            "tuple_present_on_promoted_shelf": bool(promoted_tuple),
            "case_tuple_id": expected_tuple_id,
            "external_proof_required": bool(external_proof_request),
            "external_proof_request": {
                "tuple_id": _normalize_text(external_proof_request.get("tuple_id")),
                "channel_id": _normalize_text(external_proof_request.get("channel_id")),
                "tuple_entry_count": int(external_proof_request.get("tuple_entry_count") or 0),
                "tuple_unique": bool(external_proof_request.get("tuple_unique")),
                "required_host": _normalize_text(external_proof_request.get("required_host")),
                "required_proofs": [
                    _normalize_text(token)
                    for token in (external_proof_request.get("required_proofs") or [])
                    if _normalize_text(token)
                ],
                "expected_artifact_id": _normalize_text(external_proof_request.get("expected_artifact_id")),
                "expected_installer_file_name": _normalize_text(
                    external_proof_request.get("expected_installer_file_name")
                ),
                "expected_installer_relative_path": _normalize_text(
                    external_proof_request.get("expected_installer_relative_path")
                ),
                "expected_public_install_route": _normalize_text(
                    external_proof_request.get("expected_public_install_route")
                ),
                "expected_startup_smoke_receipt_path": _normalize_text(
                    external_proof_request.get("expected_startup_smoke_receipt_path")
                ),
                "startup_smoke_receipt_contract": dict(
                    external_proof_request.get("startup_smoke_receipt_contract") or {}
                ),
                "proof_capture_commands": [
                    _normalize_text(token)
                    for token in (external_proof_request.get("proof_capture_commands") or [])
                    if _normalize_text(token)
                ],
            },
            "fix_availability_summary": _normalize_text(release_channel_index.get("fix_availability_summary")),
            "case_installed_version": installed_version,
            "case_version_matches_registry_release": bool(
                installed_version
                and _normalize_text(release_channel_index.get("version"))
                and installed_version.lower() == _normalize_text(release_channel_index.get("version")).lower()
            ),
            "case_fixed_version_matches_registry_release": bool(
                fixed_version
                and _normalize_text(release_channel_index.get("version"))
                and fixed_version.lower() == _normalize_text(release_channel_index.get("version")).lower()
            ),
        },
        "fix_confirmation": {
            "state": fix_confirmation_state,
            "reporter_verification_state": _normalize_text(
                item.get("reporterVerificationState") or item.get("reporter_verification_state")
            ).lower(),
            "installed_version": installed_version,
            "fixed_version": fixed_version,
            "fixed_channel": fixed_channel,
            "update_required": update_required,
        },
        "recovery_path": recovery_path,
    }


def _counter_map(values: Iterable[str]) -> Dict[str, int]:
    counter = Counter(value for value in values if value)
    return {key: counter[key] for key in sorted(counter)}


def _external_proof_request_spec(row: Dict[str, Any]) -> Dict[str, Any]:
    required_proofs = [
        _normalize_text(token)
        for token in (row.get("required_proofs") or [])
        if _normalize_text(token)
    ]
    proof_capture_commands = [
        _normalize_text(token)
        for token in (row.get("proof_capture_commands") or [])
        if _normalize_text(token)
    ]
    return {
        "channel_id": _normalize_text(row.get("channel_id")).lower(),
        "tuple_entry_count": int(row.get("tuple_entry_count") or 0),
        "tuple_unique": bool(row.get("tuple_unique")),
        "required_host": _normalize_platform(row.get("required_host")),
        "required_proofs": sorted(set(required_proofs)),
        "expected_artifact_id": _normalize_text(row.get("expected_artifact_id")),
        "expected_installer_file_name": _normalize_text(row.get("expected_installer_file_name")),
        "expected_installer_relative_path": _normalize_text(row.get("expected_installer_relative_path")),
        "expected_public_install_route": _normalize_text(row.get("expected_public_install_route")),
        "expected_startup_smoke_receipt_path": _normalize_text(row.get("expected_startup_smoke_receipt_path")),
        "startup_smoke_receipt_contract": _normalized_smoke_contract_map(row.get("startup_smoke_receipt_contract")),
        "proof_capture_commands": proof_capture_commands,
    }


def _external_proof_backlog_summary(release_channel_index: Dict[str, Any]) -> Dict[str, Any]:
    request_rows = [
        dict(row)
        for row in (release_channel_index.get("external_proof_requests") or [])
        if isinstance(row, dict)
    ]
    host_counts = _counter_map(_normalize_text(item.get("required_host")) for item in request_rows)
    tuple_counts = _counter_map(_normalize_text(item.get("tuple_id")) for item in request_rows)
    return {
        "count": len(request_rows),
        "host_counts": host_counts,
        "tuple_counts": tuple_counts,
        "hosts": sorted(host_counts.keys()),
        "tuples": sorted(tuple_counts.keys()),
        "specs": {
            tuple_id: _external_proof_request_spec(row)
            for row in sorted(request_rows, key=lambda item: _normalize_text(item.get("tuple_id")))
            for tuple_id in [_normalize_text(row.get("tuple_id"))]
            if tuple_id
        },
    }


def _external_proof_execution_plan(release_channel_index: Dict[str, Any]) -> Dict[str, Any]:
    request_rows = [
        dict(row)
        for row in (release_channel_index.get("external_proof_requests") or [])
        if isinstance(row, dict) and _normalize_text(row.get("tuple_id"))
    ]
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in request_rows:
        host = _normalize_platform(row.get("required_host")) or "required"
        grouped.setdefault(host, []).append(row)

    host_groups: Dict[str, Any] = {}
    for host in sorted(grouped.keys()):
        rows = sorted(grouped[host], key=lambda item: _normalize_text(item.get("tuple_id")))
        request_items = []
        for row in rows:
            request_items.append(
                {
                    "tuple_id": _normalize_text(row.get("tuple_id")),
                    "tuple_entry_count": int(row.get("tuple_entry_count") or 0),
                    "tuple_unique": bool(row.get("tuple_unique")),
                    "channel_id": _normalize_text(row.get("channel_id")).lower(),
                    "head_id": _normalize_text(row.get("head")).lower(),
                    "platform": _normalize_platform(row.get("platform")),
                    "rid": _normalize_text(row.get("rid")).lower(),
                    "expected_artifact_id": _normalize_text(row.get("expected_artifact_id")),
                    "expected_installer_file_name": _normalize_text(row.get("expected_installer_file_name")),
                    "expected_installer_relative_path": _normalize_text(row.get("expected_installer_relative_path")),
                    "expected_public_install_route": _normalize_text(row.get("expected_public_install_route")),
                    "expected_startup_smoke_receipt_path": _normalize_text(row.get("expected_startup_smoke_receipt_path")),
                    "required_proofs": sorted(
                        {
                            _normalize_text(token).lower()
                            for token in (row.get("required_proofs") or [])
                            if _normalize_text(token)
                        }
                    ),
                    "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                        row.get("startup_smoke_receipt_contract")
                    ),
                    "proof_capture_commands": [
                        _normalize_text(token)
                        for token in (row.get("proof_capture_commands") or [])
                        if _normalize_text(token)
                    ],
                }
            )
        host_groups[host] = {
            "request_count": len(request_items),
            "tuples": [item["tuple_id"] for item in request_items if item.get("tuple_id")],
            "requests": request_items,
        }

    return {
        "request_count": len(request_rows),
        "hosts": sorted(host_groups.keys()),
        "host_groups": host_groups,
    }


def _external_proof_operator_packet(
    row: Dict[str, Any],
    *,
    release_channel_index: Dict[str, Any],
) -> Dict[str, Any]:
    tuple_id = _normalize_text(row.get("tuple_id")).lower()
    channel_id = _normalize_text(row.get("channel_id")).lower()
    required_host = _normalize_platform(row.get("required_host"))
    tuple_parts = [token.strip().lower() for token in tuple_id.split(":") if str(token).strip()]
    head_id = tuple_parts[0] if len(tuple_parts) >= 1 else ""
    rid = tuple_parts[1] if len(tuple_parts) >= 2 else ""
    platform = tuple_parts[2] if len(tuple_parts) >= 3 else required_host
    expected_artifact_id = _normalize_text(row.get("expected_artifact_id"))
    expected_installer_file_name = _normalize_text(row.get("expected_installer_file_name"))
    expected_installer_relative_path = _normalize_text(row.get("expected_installer_relative_path"))
    expected_public_install_route = _normalize_text(row.get("expected_public_install_route"))
    expected_startup_smoke_receipt_path = _normalize_text(row.get("expected_startup_smoke_receipt_path"))
    required_proofs = [
        _normalize_text(token)
        for token in (row.get("required_proofs") or [])
        if _normalize_text(token)
    ]
    proof_capture_commands = [
        _normalize_text(token)
        for token in (row.get("proof_capture_commands") or [])
        if _normalize_text(token)
    ]
    packet_seed = f"external-proof|{channel_id}|{tuple_id}"
    packet_id = f"support_packet_{hashlib.sha1(packet_seed.encode('utf-8')).hexdigest()[:12]}"
    host_label = required_host or platform or "required"
    return {
        "packet_id": packet_id,
        "packet_kind": "external_proof_request",
        "support_case_backed": False,
        "kind": "external_proof_request",
        "status": "awaiting_evidence",
        "target_repo": "chummer6-ui",
        "design_impact_suspected": False,
        "primary_lane": "ops",
        "change_class": "type_b",
        "reason": (
            "Release-blocking desktop tuple proof is waiting on promoted installer bytes and startup-smoke "
            f"evidence from a {host_label} host."
        ),
        "exit_condition": (
            "Publish the promoted installer artifact and a passing startup-smoke receipt for the tuple, "
            "then regenerate release-channel truth."
        ),
        "affected_canon_files": [],
        "title": f"Capture desktop tuple proof for {tuple_id or expected_artifact_id or host_label}",
        "summary": (
            f"Missing promoted installer/startup-smoke proof for {tuple_id or expected_artifact_id or host_label}."
        ),
        "release_channel": channel_id,
        "head_id": head_id,
        "platform": platform,
        "arch": "",
        "installation_id": "",
        "installed_version": "",
        "fixed_version": "",
        "fixed_channel": "",
        "install_truth_state": "tuple_not_on_promoted_shelf",
        "install_diagnosis": {
            "registry_channel_id": _normalize_text(release_channel_index.get("channel_id")),
            "registry_release_channel_status": _normalize_text(release_channel_index.get("status")),
            "registry_release_version": _normalize_text(release_channel_index.get("version")),
            "registry_rollout_state": _normalize_text(release_channel_index.get("rollout_state")),
            "registry_supportability_state": _normalize_text(release_channel_index.get("supportability_state")),
            "registry_release_proof_status": _normalize_text(release_channel_index.get("release_proof_status")),
            "case_channel_matches_registry": bool(
                channel_id
                and _normalize_text(release_channel_index.get("channel_id"))
                and channel_id == _normalize_text(release_channel_index.get("channel_id")).lower()
            ),
            "promoted_tuple_id": "",
            "promoted_artifact_id": "",
            "tuple_present_on_promoted_shelf": False,
            "case_tuple_id": tuple_id,
            "external_proof_required": True,
            "external_proof_request": {
                "tuple_id": tuple_id,
                "channel_id": channel_id,
                "tuple_entry_count": int(row.get("tuple_entry_count") or 0),
                "tuple_unique": bool(row.get("tuple_unique")),
                "required_host": required_host,
                "required_proofs": required_proofs,
                "expected_artifact_id": expected_artifact_id,
                "expected_installer_file_name": expected_installer_file_name,
                "expected_installer_relative_path": expected_installer_relative_path,
                "expected_public_install_route": expected_public_install_route,
                "expected_startup_smoke_receipt_path": expected_startup_smoke_receipt_path,
                "startup_smoke_receipt_contract": _normalized_smoke_contract_map(
                    row.get("startup_smoke_receipt_contract")
                ),
                "proof_capture_commands": proof_capture_commands,
            },
            "fix_availability_summary": _normalize_text(release_channel_index.get("fix_availability_summary")),
            "case_installed_version": "",
            "case_version_matches_registry_release": False,
            "case_fixed_version_matches_registry_release": False,
        },
        "fix_confirmation": {
            "state": "no_fix_recorded",
            "reporter_verification_state": "",
            "installed_version": "",
            "fixed_version": "",
            "fixed_channel": "",
            "update_required": False,
        },
        "recovery_path": {
            "action_id": "open_downloads",
            "href": "/downloads",
            "reason": (
                "The promoted desktop tuple proof is incomplete; stay on the published downloads lane until the "
                "required host receipts land."
            ),
        },
    }


def _closure_waiting_on_release_truth(packet: Dict[str, Any]) -> bool:
    status = _normalize_text(packet.get("status")).lower()
    if status in {"accepted", "fixed"}:
        return True
    has_fix = bool(_normalize_text(packet.get("fixed_version")) or _normalize_text(packet.get("fixed_channel")))
    return has_fix and status not in {"released_to_reporter_channel", "rejected", "deferred"}


def _needs_human_response(packet: Dict[str, Any]) -> bool:
    status = _normalize_text(packet.get("status")).lower()
    return status in {"new", "clustered", "awaiting_evidence"}


def build_packets_payload(source_payload: Dict[str, Any], source_label: str, *, release_channel_index: Dict[str, Any]) -> Dict[str, Any]:
    raw_items = source_payload.get("items") or []
    open_statuses = {
        "new",
        "clustered",
        "routed",
        "awaiting_evidence",
        "accepted",
        "fixed",
        "released_to_reporter_channel",
    }
    case_packets = [
        packet
        for item in raw_items
        if isinstance(item, dict)
        for packet in [_decision_for_case(dict(item), release_channel_index=release_channel_index)]
        if packet["status"] in open_statuses
    ]
    unresolved_external_proof = _external_proof_backlog_summary(release_channel_index)
    unresolved_external_proof_execution_plan = _external_proof_execution_plan(release_channel_index)
    packet_external_tuple_ids = {
        _normalize_text((packet.get("install_diagnosis") or {}).get("external_proof_request", {}).get("tuple_id"))
        for packet in case_packets
        if bool((packet.get("install_diagnosis") or {}).get("external_proof_required"))
    }
    operator_packets = [
        _external_proof_operator_packet(dict(row), release_channel_index=release_channel_index)
        for row in (release_channel_index.get("external_proof_requests") or [])
        if isinstance(row, dict)
        and _normalize_text(row.get("tuple_id"))
        and _normalize_text(row.get("tuple_id")) not in packet_external_tuple_ids
    ]
    packets = case_packets + operator_packets
    open_packets = packets
    open_items = [
        dict(item)
        for item in raw_items
        if isinstance(item, dict) and _normalize_text(item.get("status")).lower() in open_statuses
    ]

    return {
        "contract_name": "fleet.support_case_packets",
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "source": {
            "source_kind": _source_kind(source_label),
            "reported_count": int(source_payload.get("count") or len(raw_items)),
            "materialized_count": len(packets),
            "case_materialized_count": len(case_packets),
            "operator_packet_count": len(operator_packets),
        },
        "summary": {
            "open_case_count": len(case_packets),
            "open_packet_count": len(open_packets),
            "operator_packet_count": len(operator_packets),
            "design_impact_count": sum(1 for item in case_packets if item["design_impact_suspected"]),
            "owner_repo_counts": _counter_map(
                _normalize_text(item.get("target_repo") or item.get("candidateOwnerRepo") or item.get("candidate_owner_repo"), "chummer6-hub")
                for item in open_packets
            ),
            "lane_counts": _counter_map(item["primary_lane"] for item in open_packets),
            "status_counts": _counter_map(item["status"] for item in open_packets),
            "closure_waiting_on_release_truth": sum(1 for item in open_packets if _closure_waiting_on_release_truth(item)),
            "needs_human_response": sum(1 for item in open_packets if _needs_human_response(item)),
            "install_truth_state_counts": _counter_map(item.get("install_truth_state") for item in open_packets),
            "update_required_case_count": sum(
                1 for item in open_packets if bool((item.get("fix_confirmation") or {}).get("update_required"))
            ),
            "update_required_routed_to_downloads_count": sum(
                1
                for item in open_packets
                if bool((item.get("fix_confirmation") or {}).get("update_required"))
                and _normalize_text((item.get("recovery_path") or {}).get("action_id")).lower() == "open_downloads"
            ),
            "update_required_misrouted_case_count": sum(
                1
                for item in open_packets
                if bool((item.get("fix_confirmation") or {}).get("update_required"))
                and _normalize_text((item.get("recovery_path") or {}).get("action_id")).lower() != "open_downloads"
            ),
            "external_proof_required_case_count": sum(
                1 for item in case_packets if bool((item.get("install_diagnosis") or {}).get("external_proof_required"))
            ),
            "external_proof_required_host_counts": _counter_map(
                _normalize_text((item.get("install_diagnosis") or {}).get("external_proof_request", {}).get("required_host"))
                for item in case_packets
                if bool((item.get("install_diagnosis") or {}).get("external_proof_required"))
            ),
            "external_proof_required_tuple_counts": _counter_map(
                _normalize_text((item.get("install_diagnosis") or {}).get("external_proof_request", {}).get("tuple_id"))
                for item in case_packets
                if bool((item.get("install_diagnosis") or {}).get("external_proof_required"))
            ),
            "unresolved_external_proof_request_count": int(unresolved_external_proof["count"]),
            "unresolved_external_proof_request_host_counts": dict(unresolved_external_proof["host_counts"]),
            "unresolved_external_proof_request_tuple_counts": dict(unresolved_external_proof["tuple_counts"]),
            "unresolved_external_proof_request_hosts": list(unresolved_external_proof["hosts"]),
            "unresolved_external_proof_request_tuples": list(unresolved_external_proof["tuples"]),
            "unresolved_external_proof_request_specs": dict(unresolved_external_proof["specs"]),
        },
        "unresolved_external_proof": dict(unresolved_external_proof),
        "unresolved_external_proof_execution_plan": dict(unresolved_external_proof_execution_plan),
        "packets": packets,
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    source_payload, source_label = _load_json_source(_source_value(args.source), bearer_token=_source_bearer_token(args.bearer_token))
    release_channel_payload = _load_release_channel(str(args.release_channel))
    release_channel_index = _release_channel_index(release_channel_payload)
    payload = build_packets_payload(source_payload, source_label, release_channel_index=release_channel_index)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_repo_root = repo_root_for_published_path(out_path)
    if manifest_repo_root is not None:
        write_compile_manifest(manifest_repo_root)

    print(f"wrote support-case packets: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
