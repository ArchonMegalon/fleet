#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def _release_channel_index(release_channel: Dict[str, Any]) -> Dict[str, Any]:
    tuple_rows = []
    coverage = release_channel.get("desktopTupleCoverage")
    if isinstance(coverage, dict):
        tuple_rows = coverage.get("promotedInstallerTuples") or []
    rows: List[Dict[str, str]] = []
    for item in tuple_rows:
        if not isinstance(item, dict):
            continue
        head = _normalize_text(item.get("head")).lower()
        platform = _normalize_platform(item.get("platform"))
        rid = _normalize_text(item.get("rid")).lower()
        tuple_id = _normalize_text(item.get("tupleId") or item.get("tuple_id"), f"{head}:{platform}:{rid}" if head and platform and rid else "")
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
    return {
        "channel_id": _normalize_text(release_channel.get("channelId") or release_channel.get("channel")).lower(),
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
    }


def _lookup_promoted_tuple(*, index: Dict[str, Any], head: str, platform: str, arch: str, tuple_id: str = "") -> Dict[str, str]:
    promoted_rows = [dict(row) for row in (index.get("promoted_tuples") or []) if isinstance(row, dict)]
    if tuple_id:
        for row in promoted_rows:
            if _normalize_text(row.get("tuple_id")).lower() == tuple_id.lower():
                return row
    rid = _rid_for_platform_arch(platform, arch)
    if head and platform and rid:
        key = f"{head}:{platform}:{rid}"
        for row in promoted_rows:
            if _normalize_text(row.get("tuple_id")).lower() == key:
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
    fixed_version = _normalize_text(item.get("fixedVersion") or item.get("fixed_version"))
    fixed_channel = _normalize_text(item.get("fixedChannel") or item.get("fixed_channel"))
    promoted_tuple = _lookup_promoted_tuple(
        index=release_channel_index,
        head=head_id,
        platform=platform,
        arch=arch,
        tuple_id=tuple_id,
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
    packets = [
        packet
        for item in raw_items
        if isinstance(item, dict)
        for packet in [_decision_for_case(dict(item), release_channel_index=release_channel_index)]
        if packet["status"] in open_statuses
    ]
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
        },
        "summary": {
            "open_case_count": len(open_packets),
            "design_impact_count": sum(1 for item in open_packets if item["design_impact_suspected"]),
            "owner_repo_counts": _counter_map(
                _normalize_text(item.get("candidateOwnerRepo") or item.get("candidate_owner_repo"), "chummer6-hub")
                for item in open_items
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
        },
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
