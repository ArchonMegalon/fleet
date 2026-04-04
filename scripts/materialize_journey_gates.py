#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest
except ModuleNotFoundError:
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


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
        Path("/docker/chummercomplete/chummer-core-engine"),
        Path("/docker/chummercomplete/chummer6-core"),
    ),
    "chummer6-hub": (
        Path("/docker/chummercomplete/chummer.run-services"),
        Path("/docker/chummercomplete/chummer6-hub"),
    ),
    "chummer6-hub-registry": (Path("/docker/chummercomplete/chummer-hub-registry"),),
    "chummer6-ui": (Path("/docker/chummercomplete/chummer6-ui"),),
    "chummer6-mobile": (Path("/docker/chummercomplete/chummer6-mobile"),),
    "chummer6-media-factory": (
        Path("/docker/chummercomplete/chummer-media-factory"),
        Path("/docker/fleet/repos/chummer-media-factory"),
    ),
    "executive-assistant": (Path("/docker/EA"),),
}

EXTERNAL_BLOCKER_MARKERS = (
    "requires a windows-capable host",
    "requires a macos host",
    "current host cannot run promoted windows installer smoke",
    "current host cannot run promoted macos installer smoke",
)

RELEASE_CHANNEL_PLATFORM_COVERAGE_MARKERS = (
    "release_channel.generated.json field 'desktoptuplecoverage.missingrequiredplatforms'",
    "release_channel.generated.json field 'desktoptuplecoverage.missingrequiredplatformheadpairs'",
    "release_channel.generated.json field 'desktoptuplecoverage.missingrequiredplatformheadridtuples'",
)


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
        return parts[0], parts[1], parts[2]

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

    def _proof_capture_commands(*, head: str, rid: str, platform: str, installer_file_name: str, required_host: str) -> List[str]:
        if not head or not rid:
            return []
        repo_root = Path("/docker/chummercomplete/chummer6-ui")
        installer_name = installer_file_name or _default_installer_file_name(head=head, rid=rid, platform=platform)
        if not installer_name:
            return []
        installer_path = repo_root / "Docker" / "Downloads" / "files" / installer_name
        startup_smoke_dir = repo_root / "Docker" / "Downloads" / "startup-smoke"
        host_class = required_host or platform or "required"
        run_smoke = (
            f"cd {shlex.quote(str(repo_root))} && "
            f"CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS={shlex.quote(host_class + '-host')} "
            f"./scripts/run-desktop-startup-smoke.sh "
            f"{shlex.quote(str(installer_path))} "
            f"{shlex.quote(head)} "
            f"{shlex.quote(rid)} "
            f"{shlex.quote(_default_launch_target(head=head, platform=platform))} "
            f"{shlex.quote(str(startup_smoke_dir))}"
        )
        refresh_manifest = (
            f"cd {shlex.quote(str(repo_root))} && "
            "./scripts/generate-releases-manifest.sh"
        )
        return [run_smoke, refresh_manifest]

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
        required_proofs = item.get("requiredProofs")
        if not tuple_id or not isinstance(required_proofs, list):
            continue
        proof_tokens = [str(token or "").strip() for token in required_proofs if str(token or "").strip()]
        if not proof_tokens:
            continue
        head, rid, platform = _parse_tuple_identity(tuple_id)
        requests.append(
            {
                "tuple_id": tuple_id,
                "required_host": required_host or "required",
                "required_proofs": sorted(set(proof_tokens)),
                "head_id": head,
                "rid": rid,
                "platform": platform,
                "expected_artifact_id": str(item.get("expectedArtifactId") or "").strip(),
                "expected_installer_file_name": str(item.get("expectedInstallerFileName") or "").strip(),
                "expected_public_install_route": str(item.get("expectedPublicInstallRoute") or "").strip(),
                "expected_startup_smoke_receipt_path": str(item.get("expectedStartupSmokeReceiptPath") or "").strip(),
                "startup_smoke_receipt_contract": _required_receipt_contract(
                    head=head,
                    rid=rid,
                    platform=platform,
                    required_host=required_host,
                ),
                "proof_capture_commands": _proof_capture_commands(
                    head=head,
                    rid=rid,
                    platform=platform,
                    installer_file_name=str(item.get("expectedInstallerFileName") or "").strip(),
                    required_host=required_host,
                ),
            }
        )
    deduped_by_tuple: Dict[str, Dict[str, Any]] = {}
    for request in requests:
        tuple_id = str(request.get("tuple_id") or "").strip()
        if tuple_id:
            deduped_by_tuple[tuple_id] = request
    return [deduped_by_tuple[key] for key in sorted(deduped_by_tuple.keys())]


def _release_channel_external_proof_reasons(payload: Dict[str, Any]) -> List[str]:
    requests = _release_channel_external_proof_requests(payload)
    reasons: List[str] = []
    for item in requests:
        tuple_id = str(item.get("tuple_id") or "").strip()
        required_host = str(item.get("required_host") or "").strip().lower()
        proof_tokens = item.get("required_proofs")
        if not tuple_id or not isinstance(proof_tokens, list) or not proof_tokens:
            continue
        expected_artifact_id = str(item.get("expected_artifact_id") or "").strip()
        expected_installer = str(item.get("expected_installer_file_name") or "").strip()
        expected_route = str(item.get("expected_public_install_route") or "").strip()
        expected_receipt = str(item.get("expected_startup_smoke_receipt_path") or "").strip()
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
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


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
    now = utc_now()

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

    for proof in fleet_gate.get("repo_source_proof") or []:
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
        for snippet in proof_row.get("must_contain") or []:
            snippet_text = str(snippet or "").strip()
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

        if json_required:
            assert proof_payload is not None
            for field_path, expected in json_required.items():
                actual = _resolve_json_path(proof_payload, str(field_path))
                if actual != expected:
                    blocking_reasons.append(
                        f"repo proof {repo_name}:{relative_path} field '{field_path}' expected {expected!r} but was {actual!r}."
                    )
            if (
                repo_name == "chummer6-hub-registry"
                and relative_path == ".codex-studio/published/RELEASE_CHANNEL.generated.json"
            ):
                blocking_reasons.extend(_release_channel_external_proof_reasons(proof_payload))
                external_proof_requests = _release_channel_external_proof_requests(proof_payload)

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
        def _counter_map(values: List[str]) -> Dict[str, int]:
            counts: Dict[str, int] = {}
            for raw in values:
                token = str(raw or "").strip()
                if not token:
                    continue
                counts[token] = counts.get(token, 0) + 1
            return {key: counts[key] for key in sorted(counts)}

        def _normalized_summary_counter(value: Any) -> Dict[str, int]:
            if not isinstance(value, dict):
                return {}
            normalized: Dict[str, int] = {}
            for key, raw_count in value.items():
                token = str(key or "").strip()
                if not token:
                    continue
                try:
                    count = int(raw_count)
                except (TypeError, ValueError):
                    continue
                if count > 0:
                    normalized[token] = count
            return {key: normalized[key] for key in sorted(normalized)}

        packets = [dict(item) for item in (support_packets.get("packets") or []) if isinstance(item, dict)]
        support_external_proof_required_count = 0
        expected_external_proof_request_by_tuple = {
            str(item.get("tuple_id") or "").strip(): dict(item)
            for item in external_proof_requests
            if str(item.get("tuple_id") or "").strip()
        }
        for index, packet in enumerate(packets, start=1):
            packet_id = str(packet.get("packet_id") or "").strip() or f"packet#{index}"
            install_truth_state = str(packet.get("install_truth_state") or "").strip().lower()
            install_diagnosis = packet.get("install_diagnosis")
            fix_confirmation = packet.get("fix_confirmation")
            recovery_path = packet.get("recovery_path")
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
                if not str(install_diagnosis.get("registry_release_channel_status") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing install_diagnosis.registry_release_channel_status."
                    )
                if not str(install_diagnosis.get("registry_release_version") or "").strip():
                    support_packet_contract_violations.append(
                        f"support packet {packet_id} is missing install_diagnosis.registry_release_version."
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
                            required_host = str(external_proof_request.get("required_host") or "").strip().lower()
                            if not any("run-desktop-startup-smoke.sh" in token for token in normalized_commands):
                                support_packet_contract_violations.append(
                                    f"support packet {packet_id} install_diagnosis.external_proof_request.proof_capture_commands is missing run-desktop-startup-smoke.sh."
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
                        if expected_external_proof_request_by_tuple:
                            expected_request = expected_external_proof_request_by_tuple.get(tuple_id)
                            if expected_request is None:
                                support_packet_contract_violations.append(
                                    f"support packet {packet_id} external proof tuple '{tuple_id or 'unknown'}' is not present in release-channel external proof backlog."
                                )
                            else:
                                for required_key in (
                                    "required_host",
                                    "expected_artifact_id",
                                    "expected_installer_file_name",
                                    "expected_public_install_route",
                                    "expected_startup_smoke_receipt_path",
                                ):
                                    actual_value = str(external_proof_request.get(required_key) or "").strip()
                                    expected_value = str(expected_request.get(required_key) or "").strip()
                                    if required_key == "required_host":
                                        actual_value = actual_value.lower()
                                        expected_value = expected_value.lower()
                                    if actual_value != expected_value:
                                        support_packet_contract_violations.append(
                                            f"support packet {packet_id} install_diagnosis.external_proof_request.{required_key} must match release-channel tuple truth '{expected_value}' but was '{actual_value}'."
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
                                    actual_commands = {
                                        str(token or "").strip()
                                        for token in proof_capture_commands
                                        if str(token or "").strip()
                                    }
                                    missing_expected_commands = [
                                        token for token in expected_commands if token not in actual_commands
                                    ]
                                    if missing_expected_commands:
                                        support_packet_contract_violations.append(
                                            "support packet "
                                            f"{packet_id} install_diagnosis.external_proof_request.proof_capture_commands is missing "
                                            f"release-channel command(s): {missing_expected_commands}."
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
        if support_packet_contract_violations:
            blocking_reasons.extend(support_packet_contract_violations[:5])
            if len(support_packet_contract_violations) > 5:
                blocking_reasons.append(
                    f"support packet install-truth contract has {len(support_packet_contract_violations) - 5} additional violations."
                )
        reported_external_proof_required_case_count = int(
            support_summary.get("external_proof_required_case_count") or 0
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
                for item in packets
                if bool((item.get("install_diagnosis") or {}).get("external_proof_required"))
            ]
        )
        reported_external_proof_required_host_counts = _normalized_summary_counter(
            support_summary.get("external_proof_required_host_counts")
        )
        if expected_external_proof_required_host_counts != reported_external_proof_required_host_counts:
            blocking_reasons.append(
                "support packet summary external_proof_required_host_counts does not match packet install_diagnosis facts."
            )
        expected_external_proof_required_tuple_counts = _counter_map(
            [
                str((item.get("install_diagnosis") or {}).get("external_proof_request", {}).get("tuple_id") or "").strip()
                for item in packets
                if bool((item.get("install_diagnosis") or {}).get("external_proof_required"))
            ]
        )
        reported_external_proof_required_tuple_counts = _normalized_summary_counter(
            support_summary.get("external_proof_required_tuple_counts")
        )
        if expected_external_proof_required_tuple_counts != reported_external_proof_required_tuple_counts:
            blocking_reasons.append(
                "support packet summary external_proof_required_tuple_counts does not match packet install_diagnosis facts."
            )
        expected_external_proof_backlog_count = len(external_proof_requests)
        reported_external_proof_backlog_count = int(
            support_summary.get("unresolved_external_proof_request_count") or 0
        )
        if expected_external_proof_backlog_count != reported_external_proof_backlog_count:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_count does not match release-channel external proof backlog."
            )
        expected_external_proof_backlog_host_counts = _counter_map(
            [str(item.get("required_host") or "").strip().lower() for item in external_proof_requests]
        )
        reported_external_proof_backlog_host_counts = _normalized_summary_counter(
            support_summary.get("unresolved_external_proof_request_host_counts")
        )
        if expected_external_proof_backlog_host_counts != reported_external_proof_backlog_host_counts:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_host_counts does not match release-channel external proof backlog."
            )
        expected_external_proof_backlog_tuple_counts = _counter_map(
            [str(item.get("tuple_id") or "").strip() for item in external_proof_requests]
        )
        reported_external_proof_backlog_tuple_counts = _normalized_summary_counter(
            support_summary.get("unresolved_external_proof_request_tuple_counts")
        )
        if expected_external_proof_backlog_tuple_counts != reported_external_proof_backlog_tuple_counts:
            blocking_reasons.append(
                "support packet summary unresolved_external_proof_request_tuple_counts does not match release-channel external proof backlog."
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

    recommended_action = "Keep the journey under routine weekly proof."
    if blocking_reasons:
        if blocked_by_external_constraints_only:
            recommended_action = (
                "Run the missing platform-host proof lane (for example Windows/macOS startup smoke) "
                "and ingest receipts before widening promotion or trust claims."
            )
        else:
            recommended_action = "Resolve the blocking artifact or posture gap before widening promotion or trust claims."
    elif warning_reasons:
        recommended_action = "Close the remaining target-stage or evidence-depth gap before calling the journey boring."

    evidence = {
        "history_snapshot_count": history_count,
        "support_packets_generated_at": support_generated_at,
        "required_artifacts": [str(item) for item in (fleet_gate.get("required_artifacts") or []) if str(item).strip()],
        "canonical_journeys": [str(item) for item in (row.get("canonical_journeys") or []) if str(item).strip()],
        "external_proof_requests": external_proof_requests,
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
        "blocking_reasons": blocking_reasons,
        "external_blocking_reasons": external_blocking_reasons,
        "local_blocking_reasons": local_blocking_reasons,
        "blocked_by_external_constraints_only": blocked_by_external_constraints_only,
        "external_proof_requests": external_proof_requests,
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
    if blocked:
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
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    manifest_repo_root = repo_root_for_published_path(out_path)
    if manifest_repo_root is not None:
        write_compile_manifest(manifest_repo_root)
    print(f"wrote journey gates: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
