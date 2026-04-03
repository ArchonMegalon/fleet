#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import yaml

try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest
except ModuleNotFoundError:
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")

DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEFAULT_MIRROR_OUT = ROOT / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEFAULT_ACCEPTANCE = ROOT / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
CANONICAL_ACCEPTANCE = Path("/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
DEFAULT_STATUS_PLANE = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEFAULT_PROGRESS_REPORT = ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY = ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_JOURNEY_GATES = ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
DEFAULT_SUPPORT_PACKETS = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_SUPERVISOR_STATE = ROOT / "state" / "chummer_design_supervisor" / "state.json"
DEFAULT_OODA_STATE = ROOT / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"

DEFAULT_UI_LOCAL_RELEASE_PROOF = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json")
DEFAULT_UI_LINUX_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
DEFAULT_UI_WINDOWS_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json")
DEFAULT_UI_WORKFLOW_PARITY_PROOF = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json")
DEFAULT_UI_EXECUTABLE_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json")
DEFAULT_UI_WORKFLOW_EXECUTION_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json")
DEFAULT_UI_VISUAL_FAMILIARITY_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json")
DEFAULT_HUB_LOCAL_RELEASE_PROOF = Path("/docker/chummercomplete/chummer6-hub/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json")
DEFAULT_MOBILE_LOCAL_RELEASE_PROOF = Path("/docker/chummercomplete/chummer6-mobile/.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json")
DEFAULT_RELEASE_CHANNEL = Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json")
DEFAULT_RELEASES_JSON = Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/releases.json")
DEFAULT_SHARD_SUPERVISOR_ROOT = Path("/var/lib/codex-fleet/chummer_design_supervisor")
UI_REPO_CANONICAL_ALIAS_ROOT = Path("/docker/chummercomplete/chummer6-ui")
UI_REPO_LEGACY_REAL_ROOT = Path("/docker/chummercomplete/chummer-presentation")

STAGE_ORDER = {
    "pre_repo_local_complete": 0,
    "repo_local_complete": 1,
    "package_canonical": 2,
    "boundary_pure": 3,
    "publicly_promoted": 4,
}
FLAGSHIP_OPERATOR_STALE_INCIDENT_HOURS = 36
FLAGSHIP_OPERATOR_SUPERVISOR_MAX_AGE_HOURS = 6
PROMOTION_ORDER = {
    "internal": 0,
    "protected_preview": 1,
    "public": 2,
}
DESKTOP_EXECUTABLE_GATE_PROOF_MAX_AGE_SECONDS = 24 * 3600
RELEASE_CHANNEL_PROOF_MAX_AGE_SECONDS = 24 * 3600
DESKTOP_EXECUTABLE_GATE_REQUIRED_PROOF_AGE_KEYS = (
    "flagship UI release gate proof_age_seconds",
    "desktop workflow execution gate proof_age_seconds",
    "desktop visual familiarity gate proof_age_seconds",
)
DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TESTS = (
    "Runtime_backed_shell_chrome_stays_enabled_after_runner_load",
    "Runtime_backed_codex_tree_preserves_legacy_left_rail_navigation_posture",
    "Loaded_runner_header_stays_tab_panel_only_without_metric_cards",
    "Character_creation_preserves_familiar_dense_builder_rhythm",
    "Advancement_and_karma_journal_workflows_preserve_familiar_progression_rhythm",
    "Gear_builder_preserves_familiar_browse_detail_confirm_rhythm",
    "Vehicles_and_drones_builder_preserves_familiar_browse_detail_confirm_rhythm",
    "Cyberware_and_cyberlimb_builder_preserve_legacy_dialog_familiarity_cues",
    "Contacts_diary_and_support_routes_execute_with_public_path_visibility",
    "Magic_matrix_and_consumables_workflows_execute_with_specific_dialog_fields_and_confirm_actions",
)

RULES_CERTIFICATION_CANDIDATES = (
    Path("/docker/chummercomplete/chummer6-core/.codex-studio/published/RULES_IMPORT_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer6-core/.codex-studio/published/LEGACY_IMPORT_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer6-core/.codex-studio/published/IMPORT_PARITY_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer6-core/.codex-studio/published/ORACLE_IMPORT_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer-core-engine/.codex-studio/published/RULES_IMPORT_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer-core-engine/.codex-studio/published/LEGACY_IMPORT_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer-core-engine/.codex-studio/published/IMPORT_PARITY_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer-core-engine/.codex-studio/published/ORACLE_IMPORT_CERTIFICATION.generated.json"),
)
MEDIA_PROOF_CANDIDATES = (
    Path("/docker/chummercomplete/chummer6-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"),
    Path("/docker/chummercomplete/chummer6-media-factory/.codex-studio/published/ARTIFACT_PUBLICATION_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/ARTIFACT_PUBLICATION_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer.run-services/.codex-studio/published/HUB_CAMPAIGN_OS_LOCAL_PROOF.generated.json"),
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize flagship whole-product readiness proof from Fleet's published evidence and repo-local release proofs."
    )
    parser.add_argument("--repo-root", default=str(ROOT), help="Fleet repo root")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output path for FLAGSHIP_PRODUCT_READINESS.generated.json")
    parser.add_argument(
        "--mirror-out",
        default=str(DEFAULT_MIRROR_OUT),
        help="optional mirror path for FLAGSHIP_PRODUCT_READINESS.generated.json",
    )
    parser.add_argument("--acceptance", default=str(DEFAULT_ACCEPTANCE), help="path to FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
    parser.add_argument("--status-plane", default=str(DEFAULT_STATUS_PLANE), help="path to STATUS_PLANE.generated.yaml")
    parser.add_argument("--progress-report", default=str(DEFAULT_PROGRESS_REPORT), help="path to PROGRESS_REPORT.generated.json")
    parser.add_argument("--progress-history", default=str(DEFAULT_PROGRESS_HISTORY), help="path to PROGRESS_HISTORY.generated.json")
    parser.add_argument("--journey-gates", default=str(DEFAULT_JOURNEY_GATES), help="path to JOURNEY_GATES.generated.json")
    parser.add_argument("--support-packets", default=str(DEFAULT_SUPPORT_PACKETS), help="path to SUPPORT_CASE_PACKETS.generated.json")
    parser.add_argument(
        "--supervisor-state",
        default=str(DEFAULT_SUPERVISOR_STATE),
        help="path to supervisor state.json used for fleet/operator loop proof",
    )
    parser.add_argument(
        "--ooda-state",
        default=str(DEFAULT_OODA_STATE),
        help="path to OODA monitor state.json used for fleet/operator loop proof",
    )
    parser.add_argument(
        "--ui-local-release-proof",
        default=str(DEFAULT_UI_LOCAL_RELEASE_PROOF),
        help="path to UI_LOCAL_RELEASE_PROOF.generated.json",
    )
    parser.add_argument(
        "--ui-linux-exit-gate",
        default=str(DEFAULT_UI_LINUX_EXIT_GATE),
        help="path to UI_LINUX_DESKTOP_EXIT_GATE.generated.json",
    )
    parser.add_argument(
        "--ui-windows-exit-gate",
        default=str(DEFAULT_UI_WINDOWS_EXIT_GATE),
        help="path to UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json",
    )
    parser.add_argument(
        "--ui-workflow-parity-proof",
        default=str(DEFAULT_UI_WORKFLOW_PARITY_PROOF),
        help="path to CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json",
    )
    parser.add_argument(
        "--ui-executable-exit-gate",
        default=str(DEFAULT_UI_EXECUTABLE_EXIT_GATE),
        help="path to DESKTOP_EXECUTABLE_EXIT_GATE.generated.json",
    )
    parser.add_argument(
        "--ui-workflow-execution-gate",
        default=str(DEFAULT_UI_WORKFLOW_EXECUTION_GATE),
        help="path to DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
    )
    parser.add_argument(
        "--ui-visual-familiarity-exit-gate",
        default=str(DEFAULT_UI_VISUAL_FAMILIARITY_EXIT_GATE),
        help="path to DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
    )
    parser.add_argument(
        "--sr4-workflow-parity-proof",
        default=str(DEFAULT_UI_WORKFLOW_PARITY_PROOF.with_name("SR4_DESKTOP_WORKFLOW_PARITY.generated.json")),
        help="path to SR4_DESKTOP_WORKFLOW_PARITY.generated.json",
    )
    parser.add_argument(
        "--sr6-workflow-parity-proof",
        default=str(DEFAULT_UI_WORKFLOW_PARITY_PROOF.with_name("SR6_DESKTOP_WORKFLOW_PARITY.generated.json")),
        help="path to SR6_DESKTOP_WORKFLOW_PARITY.generated.json",
    )
    parser.add_argument(
        "--sr4-sr6-frontier-receipt",
        default=str(DEFAULT_UI_WORKFLOW_PARITY_PROOF.with_name("SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json")),
        help="path to SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json",
    )
    parser.add_argument(
        "--hub-local-release-proof",
        default=str(DEFAULT_HUB_LOCAL_RELEASE_PROOF),
        help="path to HUB_LOCAL_RELEASE_PROOF.generated.json",
    )
    parser.add_argument(
        "--mobile-local-release-proof",
        default=str(DEFAULT_MOBILE_LOCAL_RELEASE_PROOF),
        help="path to MOBILE_LOCAL_RELEASE_PROOF.generated.json",
    )
    parser.add_argument("--release-channel", default=str(DEFAULT_RELEASE_CHANNEL), help="path to RELEASE_CHANNEL.generated.json")
    parser.add_argument("--releases-json", default=str(DEFAULT_RELEASES_JSON), help="path to releases.json")
    return parser.parse_args(list(argv or sys.argv[1:]))


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


def payload_generated_age_seconds(payload: Dict[str, Any], *, now: dt.datetime | None = None) -> tuple[str, int | None]:
    if now is None:
        now = utc_now()
    raw = ""
    parsed: dt.datetime | None = None
    for key in ("generated_at", "generatedAt"):
        if key in payload:
            raw = str(payload.get(key) or "").strip()
            parsed = parse_iso(raw)
            break
    if not raw or parsed is None:
        return raw, None
    return raw, max(0, int((now - parsed).total_seconds()))


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


def report_path(path: Path) -> str:
    raw = str(path)
    if not raw:
        return raw
    try:
        resolved = path.resolve()
    except OSError:
        return raw
    resolved_raw = str(resolved)
    legacy_prefix = str(UI_REPO_LEGACY_REAL_ROOT)
    canonical_prefix = str(UI_REPO_CANONICAL_ALIAS_ROOT)
    if resolved_raw == legacy_prefix:
        return canonical_prefix
    if resolved_raw.startswith(legacy_prefix + "/"):
        suffix = resolved_raw[len(legacy_prefix) :]
        return canonical_prefix + suffix
    return raw


def _candidate_supervisor_state_paths(preferred_path: Path) -> List[Path]:
    candidates: List[Path] = [preferred_path]
    parent = preferred_path.parent
    grandparent = parent.parent if parent else None
    if preferred_path.name == "state.json" and parent and grandparent and parent.name.startswith("shard-"):
        candidates.extend(sorted(grandparent.glob("shard-*/state.json")))
    candidates.extend(sorted(DEFAULT_SHARD_SUPERVISOR_ROOT.glob("shard-*/state.json")))
    unique: List[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _select_best_supervisor_state(preferred_path: Path) -> tuple[Path, Dict[str, Any]]:
    selected_path = preferred_path
    selected_payload = load_json(preferred_path)
    selected_score = (-1, -1, -1.0)
    for path in _candidate_supervisor_state_paths(preferred_path):
        payload = load_json(path)
        if not payload:
            continue
        mode = str(payload.get("mode") or "").strip().lower()
        completion_status = _supervisor_completion_status(payload)
        updated_at = parse_iso(payload.get("updated_at")) or parse_iso((payload.get("active_run") or {}).get("started_at"))
        updated_ts = updated_at.timestamp() if updated_at is not None else -1.0
        score = (
            1 if completion_status in {"pass", "passed"} else 0,
            3 if mode == "complete" else 2 if mode == "flagship_product" else 1 if mode == "loop" else 0,
            updated_ts,
        )
        if score > selected_score:
            selected_path = path
            selected_payload = payload
            selected_score = score
    return selected_path, selected_payload


def _supervisor_completion_status(payload: Dict[str, Any]) -> str:
    completion_status = str((payload.get("completion_audit") or {}).get("status") or "").strip().lower()
    if completion_status in {"pass", "passed", "fail", "failed"}:
        return completion_status
    last_run = payload.get("last_run") if isinstance(payload.get("last_run"), dict) else {}
    accepted = bool(last_run.get("accepted"))
    finished_at = parse_iso(last_run.get("finished_at"))
    if accepted and finished_at is not None:
        return "pass"
    return completion_status


def load_acceptance_with_fallback(primary_path: Path) -> tuple[Path, Dict[str, Any]]:
    primary_payload = load_yaml(primary_path)
    if primary_payload:
        return primary_path, primary_payload
    if CANONICAL_ACCEPTANCE != primary_path and CANONICAL_ACCEPTANCE.is_file():
        canonical_payload = load_yaml(CANONICAL_ACCEPTANCE)
        if canonical_payload:
            return CANONICAL_ACCEPTANCE, canonical_payload
    return primary_path, {}


def compare_order(actual: str, expected: str, order: Dict[str, int]) -> int:
    return order.get(str(actual or "").strip(), -1) - order.get(str(expected or "").strip(), -1)


def project_posture(project_row: Dict[str, Any]) -> str:
    return (
        str(project_row.get("deployment_access_posture") or "").strip()
        or str(project_row.get("deployment_visibility") or "").strip()
        or str(project_row.get("deployment_promotion_stage") or "").strip()
        or str(project_row.get("deployment_status") or "").strip()
    )


def proof_passed(payload: Dict[str, Any], *, expected_contract: str = "", accepted_statuses: Sequence[str] = ("passed", "pass")) -> bool:
    if not payload:
        return False
    if expected_contract and str(payload.get("contract_name") or "").strip() != expected_contract:
        return False
    return str(payload.get("status") or "").strip().lower() in {str(item).strip().lower() for item in accepted_statuses}


def windows_exit_gate_passed(payload: Dict[str, Any]) -> bool:
    if not proof_passed(payload, expected_contract="chummer6-ui.windows_desktop_exit_gate"):
        return False
    checks = payload.get("checks") or {}
    if not isinstance(checks, dict):
        return False
    return bool(checks.get("embedded_payload_marker_present")) and bool(checks.get("embedded_sample_marker_present"))


def _as_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalized_token_list(value: Any) -> List[str]:
    normalized: List[str] = []
    for item in _as_string_list(value):
        token = item.strip().lower()
        if token:
            normalized.append(token)
    return sorted(set(normalized))


def _normalized_status_map(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, str] = {}
    for raw_key, raw_status in value.items():
        key = str(raw_key or "").strip().lower()
        status = str(raw_status or "").strip().lower()
        if key:
            normalized[key] = status
    return normalized


def workflow_execution_gate_receipt_gaps(payload: Dict[str, Any]) -> Dict[str, List[str]]:
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    return {
        "workflow_family_missing_receipts": _as_string_list(evidence.get("workflow_family_missing_receipts")),
        "workflow_family_failing_receipts": _as_string_list(evidence.get("workflow_family_failing_receipts")),
        "workflow_execution_missing_receipts": _as_string_list(evidence.get("workflow_execution_missing_receipts")),
        "workflow_execution_failing_receipts": _as_string_list(evidence.get("workflow_execution_failing_receipts")),
        "workflow_execution_weak_receipts": _as_string_list(evidence.get("workflow_execution_weak_receipts")),
    }


def executable_gate_freshness_issues(
    payload: Dict[str, Any], *, max_age_seconds: int = DESKTOP_EXECUTABLE_GATE_PROOF_MAX_AGE_SECONDS
) -> tuple[Dict[str, int], List[str]]:
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    parsed_ages: Dict[str, int] = {}
    issues: List[str] = []
    for key in DESKTOP_EXECUTABLE_GATE_REQUIRED_PROOF_AGE_KEYS:
        raw = evidence.get(key)
        if raw in (None, ""):
            issues.append(f"Executable gate freshness evidence is missing '{key}'.")
            continue
        try:
            age_seconds = int(float(raw))
        except (TypeError, ValueError):
            issues.append(f"Executable gate freshness evidence '{key}' is not numeric.")
            continue
        if age_seconds < 0:
            issues.append(f"Executable gate freshness evidence '{key}' is negative.")
            continue
        parsed_ages[key] = age_seconds
        if age_seconds > max_age_seconds:
            issues.append(
                f"Executable gate freshness evidence '{key}' is stale ({age_seconds}s old; max {max_age_seconds}s)."
            )
    return parsed_ages, issues


def _coverage_entry(
    *,
    positives: int,
    reasons: List[str],
    summary_ready: str,
    summary_missing: str,
    evidence: Dict[str, Any],
    hard_fail: bool = False,
) -> tuple[str, Dict[str, Any]]:
    if not reasons:
        return "ready", {"status": "ready", "summary": summary_ready, "reasons": [], "evidence": evidence}
    status = "missing" if hard_fail or positives <= 0 else "warning"
    return status, {"status": status, "summary": summary_missing, "reasons": reasons, "evidence": evidence}


def _first_existing_payload(paths: Iterable[Path]) -> tuple[Path | None, Dict[str, Any]]:
    for path in paths:
        payload = load_json(path)
        if payload:
            return path, payload
    return None, {}


def _ooda_steady_complete_quiet(ooda_state: Dict[str, Any]) -> bool:
    if bool(ooda_state.get("steady_complete_quiet")):
        return True
    frontier_ids = ooda_state.get("frontier_ids")
    if isinstance(frontier_ids, list) and frontier_ids:
        return False
    shards = ooda_state.get("shards") or ooda_state.get("last_observed_shards") or []
    if not isinstance(shards, list) or not shards:
        return False
    for shard in shards:
        if not isinstance(shard, dict):
            return False
        mode = str(shard.get("mode") or "").strip().lower()
        if mode not in {"complete", "idle"}:
            return False
        if bool(shard.get("active_run")):
            return False
    return True


def build_flagship_product_readiness_payload(
    *,
    acceptance_path: Path,
    status_plane_path: Path,
    progress_report_path: Path,
    progress_history_path: Path,
    journey_gates_path: Path,
    support_packets_path: Path,
    supervisor_state_path: Path,
    ooda_state_path: Path,
    ui_local_release_proof_path: Path,
    ui_linux_exit_gate_path: Path,
    ui_windows_exit_gate_path: Path,
    ui_workflow_parity_proof_path: Path,
    ui_executable_exit_gate_path: Path,
    ui_workflow_execution_gate_path: Path,
    ui_visual_familiarity_exit_gate_path: Path,
    sr4_workflow_parity_proof_path: Path,
    sr6_workflow_parity_proof_path: Path,
    sr4_sr6_frontier_receipt_path: Path,
    hub_local_release_proof_path: Path,
    mobile_local_release_proof_path: Path,
    release_channel_path: Path,
    releases_json_path: Path,
) -> Dict[str, Any]:
    effective_acceptance_path, acceptance = load_acceptance_with_fallback(acceptance_path)
    status_plane = load_yaml(status_plane_path)
    progress_report = load_json(progress_report_path)
    progress_history = load_json(progress_history_path)
    journey_gates = load_json(journey_gates_path)
    support_packets = load_json(support_packets_path)
    effective_supervisor_state_path, supervisor_state = _select_best_supervisor_state(supervisor_state_path)
    ooda_state = load_json(ooda_state_path)
    ui_local_release_proof = load_json(ui_local_release_proof_path)
    ui_linux_exit_gate = load_json(ui_linux_exit_gate_path)
    ui_windows_exit_gate = load_json(ui_windows_exit_gate_path)
    ui_workflow_parity_proof = load_json(ui_workflow_parity_proof_path)
    ui_executable_exit_gate = load_json(ui_executable_exit_gate_path)
    ui_workflow_execution_gate = load_json(ui_workflow_execution_gate_path)
    ui_visual_familiarity_exit_gate = load_json(ui_visual_familiarity_exit_gate_path)
    sr4_workflow_parity_proof = load_json(sr4_workflow_parity_proof_path)
    sr6_workflow_parity_proof = load_json(sr6_workflow_parity_proof_path)
    sr4_sr6_frontier_receipt = load_json(sr4_sr6_frontier_receipt_path)
    hub_local_release_proof = load_json(hub_local_release_proof_path)
    mobile_local_release_proof = load_json(mobile_local_release_proof_path)
    release_channel = load_json(release_channel_path)
    releases_json = load_json(releases_json_path)
    rules_cert_path, rules_cert_payload = _first_existing_payload(RULES_CERTIFICATION_CANDIDATES)
    media_proof_path, media_proof_payload = _first_existing_payload(MEDIA_PROOF_CANDIDATES)

    projects = {
        str(item.get("id") or "").strip(): dict(item or {})
        for item in (status_plane.get("projects") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    groups = {
        str(item.get("id") or "").strip(): dict(item or {})
        for item in (status_plane.get("groups") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    journeys = {
        str(item.get("id") or "").strip(): dict(item or {})
        for item in (journey_gates.get("journeys") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }

    history_snapshot_count = int(progress_history.get("snapshot_count") or progress_report.get("history_snapshot_count") or 0)
    journey_summary = dict(journey_gates.get("summary") or {})
    runtime_healing_summary = dict(status_plane.get("runtime_healing", {}).get("summary") or {})
    public_group = groups.get("chummer-vnext") or {}

    coverage: Dict[str, str] = {}
    details: Dict[str, Any] = {}

    ui_project = projects.get("ui") or {}
    desktop_reasons: List[str] = []
    desktop_positives = 0
    desktop_hard_fail = False
    executable_gate_freshness_proof_ages: Dict[str, int] = {}
    executable_gate_freshness_issues_list: List[str] = []
    executable_gate_generated_at_raw, executable_gate_age_seconds = payload_generated_age_seconds(ui_executable_exit_gate)
    if ui_executable_exit_gate:
        executable_gate_freshness_proof_ages, executable_gate_freshness_issues_list = executable_gate_freshness_issues(
            ui_executable_exit_gate
        )
    if proof_passed(ui_local_release_proof, expected_contract="chummer6-ui.local_release_proof"):
        desktop_positives += 1
    else:
        desktop_reasons.append("UI local release proof is missing or not passed.")
    if proof_passed(
        ui_executable_exit_gate,
        expected_contract="chummer6-ui.desktop_executable_exit_gate",
        accepted_statuses=("passed", "pass", "ready"),
    ):
        if not executable_gate_generated_at_raw or executable_gate_age_seconds is None:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Executable desktop exit gate is missing a valid generated_at timestamp; stale gate snapshots are not allowed."
            )
        elif executable_gate_age_seconds > DESKTOP_EXECUTABLE_GATE_PROOF_MAX_AGE_SECONDS:
            desktop_hard_fail = True
            desktop_reasons.append(
                f"Executable desktop exit gate receipt is stale ({executable_gate_age_seconds}s old; max {DESKTOP_EXECUTABLE_GATE_PROOF_MAX_AGE_SECONDS}s)."
            )
        if executable_gate_freshness_issues_list:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Executable desktop exit gate freshness evidence is missing, invalid, or stale. Per-head proof cannot be treated as current."
            )
            desktop_reasons.extend(executable_gate_freshness_issues_list)
        else:
            desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable desktop exit gate proof is missing or not passed. Desktop shell/install/support liveliness must be proven from shipped artifacts."
        )
        executable_gate_reasons = [
            str(item).strip()
            for item in (ui_executable_exit_gate.get("reasons") or [])
            if str(item).strip()
        ]
        for reason in executable_gate_reasons:
            desktop_reasons.append(f"Executable gate blocker: {reason}")
    if proof_passed(
        ui_workflow_execution_gate,
        expected_contract="chummer6-ui.desktop_workflow_execution_gate",
        accepted_statuses=("passed", "pass", "ready"),
    ):
        workflow_execution_receipt_gaps = workflow_execution_gate_receipt_gaps(ui_workflow_execution_gate)
        unresolved_workflow_execution_receipts = sorted(
            {
                *workflow_execution_receipt_gaps["workflow_family_missing_receipts"],
                *workflow_execution_receipt_gaps["workflow_family_failing_receipts"],
                *workflow_execution_receipt_gaps["workflow_execution_missing_receipts"],
                *workflow_execution_receipt_gaps["workflow_execution_failing_receipts"],
                *workflow_execution_receipt_gaps["workflow_execution_weak_receipts"],
            }
        )
        if unresolved_workflow_execution_receipts:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Executable desktop workflow execution gate reports unresolved family/execution receipt drift (missing/failing/weak)."
            )
        else:
            desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable desktop workflow execution gate proof is missing or not passed. Catalog parity without click-through receipts does not pass."
        )
        workflow_execution_receipt_gaps = workflow_execution_gate_receipt_gaps(ui_workflow_execution_gate)
        unresolved_workflow_execution_receipts = sorted(
            {
                *workflow_execution_receipt_gaps["workflow_family_missing_receipts"],
                *workflow_execution_receipt_gaps["workflow_family_failing_receipts"],
                *workflow_execution_receipt_gaps["workflow_execution_missing_receipts"],
                *workflow_execution_receipt_gaps["workflow_execution_failing_receipts"],
                *workflow_execution_receipt_gaps["workflow_execution_weak_receipts"],
            }
        )
    if proof_passed(
        ui_visual_familiarity_exit_gate,
        expected_contract="chummer6-ui.desktop_visual_familiarity_exit_gate",
        accepted_statuses=("passed", "pass", "ready"),
    ):
        visual_evidence = (
            ui_visual_familiarity_exit_gate.get("evidence")
            if isinstance(ui_visual_familiarity_exit_gate.get("evidence"), dict)
            else {}
        )
        visual_required_tests = _as_string_list(visual_evidence.get("required_tests"))
        visual_missing_tests = _as_string_list(visual_evidence.get("missing_tests"))
        visual_missing_legacy_interaction_keys = _as_string_list(
            visual_evidence.get("missing_required_legacy_interaction_keys")
        )
        visual_missing_required_milestone2_tests_from_inventory: List[str] = []
        if visual_required_tests:
            visual_missing_required_milestone2_tests_from_inventory = sorted(
                test_name
                for test_name in DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TESTS
                if test_name not in visual_required_tests
            )
        visual_reported_missing_milestone2_tests = sorted(
            test_name
            for test_name in DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TESTS
            if test_name in set(visual_missing_tests)
        )
        visual_milestone2_integrity_gap = False
        if visual_missing_required_milestone2_tests_from_inventory:
            visual_milestone2_integrity_gap = True
            desktop_hard_fail = True
            desktop_reasons.append(
                "Desktop visual familiarity gate is missing required milestone-2 legacy workflow tests in its required test inventory."
            )
        if visual_reported_missing_milestone2_tests:
            visual_milestone2_integrity_gap = True
            desktop_hard_fail = True
            desktop_reasons.append(
                "Desktop visual familiarity gate reports missing required milestone-2 legacy workflow tests."
            )
        if visual_missing_legacy_interaction_keys:
            visual_milestone2_integrity_gap = True
            desktop_hard_fail = True
            desktop_reasons.append(
                "Desktop visual familiarity gate reports missing required legacy interaction proof keys."
            )
        if not visual_milestone2_integrity_gap:
            desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Desktop visual familiarity exit gate proof is missing or not passed. Workflow parity without familiar theme/layout/dialog posture does not pass."
        )
        visual_evidence = (
            ui_visual_familiarity_exit_gate.get("evidence")
            if isinstance(ui_visual_familiarity_exit_gate.get("evidence"), dict)
            else {}
        )
        visual_required_tests = _as_string_list(visual_evidence.get("required_tests"))
        visual_missing_tests = _as_string_list(visual_evidence.get("missing_tests"))
        visual_missing_required_milestone2_tests_from_inventory = []
        visual_reported_missing_milestone2_tests = []
        visual_missing_legacy_interaction_keys = _as_string_list(
            visual_evidence.get("missing_required_legacy_interaction_keys")
        )
    if proof_passed(ui_linux_exit_gate, expected_contract="chummer6-ui.linux_desktop_exit_gate"):
        desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append("Linux desktop exit gate proof is missing or not passed.")
    if windows_exit_gate_passed(ui_windows_exit_gate):
        desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append("Windows desktop exit gate proof is missing, not passed, or lacks embedded payload/sample integrity proof.")
    if proof_passed(
        ui_workflow_parity_proof,
        expected_contract="chummer6-ui.chummer5a_desktop_workflow_parity",
        accepted_statuses=("passed", "pass", "ready"),
    ):
        desktop_positives += 1
    else:
        desktop_reasons.append(
            "Chummer5a desktop workflow parity proof is missing or not passed. Representative shell parity is not enough."
        )
    if proof_passed(
        sr4_workflow_parity_proof,
        expected_contract="chummer6-ui.sr4_desktop_workflow_parity",
        accepted_statuses=("passed", "pass", "ready"),
    ):
        desktop_positives += 1
    else:
        desktop_reasons.append(
            "SR4 desktop workflow parity proof is missing or not passed. Chummer4 parity must remain open until a real desktop parity gate lands."
        )
    if proof_passed(
        sr6_workflow_parity_proof,
        expected_contract="chummer6-ui.sr6_desktop_workflow_parity",
        accepted_statuses=("passed", "pass", "ready"),
    ):
        desktop_positives += 1
    else:
        desktop_reasons.append(
            "SR6 desktop workflow parity proof is missing or not passed. Cumulative carry-forward workflows are not complete yet."
        )
    if proof_passed(
        sr4_sr6_frontier_receipt,
        expected_contract="chummer6-ui.sr4_sr6_desktop_parity_frontier",
        accepted_statuses=("passed", "pass", "ready"),
    ):
        desktop_positives += 1
    else:
        desktop_reasons.append(
            "SR4/SR6 desktop parity frontier receipt is missing or not passed. Cross-edition completion cannot close on isolated family proofs alone."
        )
    release_artifacts = list(release_channel.get("artifacts") or [])
    release_proof = dict(release_channel.get("releaseProof") or {})
    release_proof_status = str(release_proof.get("status") or "").strip().lower()
    release_channel_id = str(release_channel.get("channelId") or release_channel.get("channel") or "").strip().lower()
    release_channel_generated_at_raw, release_channel_age_seconds = payload_generated_age_seconds(release_channel)
    release_channel_status = str(release_channel.get("status") or "").strip().lower()
    release_channel_published_and_proven = (
        release_channel_status == "published" and release_proof_status in {"pass", "passed", "ready"}
    )
    release_channel_freshness_ok = True
    if release_channel_published_and_proven:
        if not release_channel_generated_at_raw or release_channel_age_seconds is None:
            release_channel_freshness_ok = False
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel is missing a valid generated_at timestamp; stale release-truth snapshots are not allowed."
            )
        elif release_channel_age_seconds > RELEASE_CHANNEL_PROOF_MAX_AGE_SECONDS:
            release_channel_freshness_ok = False
            desktop_hard_fail = True
            desktop_reasons.append(
                f"Release channel receipt is stale ({release_channel_age_seconds}s old; max {RELEASE_CHANNEL_PROOF_MAX_AGE_SECONDS}s)."
            )
    executable_gate_evidence = ui_executable_exit_gate.get("evidence") if isinstance(ui_executable_exit_gate.get("evidence"), dict) else {}
    artifact_heads = sorted({str(item.get("head") or "").strip() for item in release_artifacts if isinstance(item, dict)})
    has_avalonia_public_artifact = any(str(item.get("head") or "").strip() == "avalonia" for item in release_artifacts if isinstance(item, dict))
    promoted_tuple_keys_by_platform: Dict[str, List[str]] = {"linux": [], "windows": [], "macos": []}
    invalid_tuple_metadata_by_platform: Dict[str, bool] = {"linux": False, "windows": False, "macos": False}
    channel_mismatch_keys_by_platform: Dict[str, List[str]] = {"linux": [], "windows": [], "macos": []}
    for artifact in release_artifacts:
        if not isinstance(artifact, dict):
            continue
        platform = str(artifact.get("platform") or "").strip().lower()
        if platform == "osx":
            platform = "macos"
        if platform not in promoted_tuple_keys_by_platform:
            continue
        kind = str(artifact.get("kind") or "").strip().lower()
        if platform == "macos":
            if kind not in {"installer", "dmg", "pkg"}:
                continue
        elif kind != "installer":
            continue
        artifact_channel = str(artifact.get("channel") or "").strip().lower()
        head = str(artifact.get("head") or "").strip().lower()
        rid = str(artifact.get("rid") or "").strip().lower()
        if not rid and head == "avalonia":
            if platform == "linux":
                rid = "linux-x64"
            elif platform == "windows":
                rid = "win-x64"
            elif platform == "macos":
                rid = "osx-arm64"
        if head and rid:
            tuple_key = f"{head}:{rid}"
            promoted_tuple_keys_by_platform[platform].append(tuple_key)
            if release_channel_id and artifact_channel and artifact_channel != release_channel_id:
                channel_mismatch_keys_by_platform[platform].append(tuple_key)
        else:
            invalid_tuple_metadata_by_platform[platform] = True
    for platform in promoted_tuple_keys_by_platform:
        promoted_tuple_keys_by_platform[platform] = sorted(set(promoted_tuple_keys_by_platform[platform]))
        channel_mismatch_keys_by_platform[platform] = sorted(set(channel_mismatch_keys_by_platform[platform]))

    promoted_tuple_heads = sorted(
        {
            str(tuple_key).split(":", 1)[0].strip().lower()
            for platform_keys in promoted_tuple_keys_by_platform.values()
            for tuple_key in platform_keys
            if str(tuple_key).strip()
        }
    )
    release_channel_tuple_coverage = (
        release_channel.get("desktopTupleCoverage")
        if isinstance(release_channel.get("desktopTupleCoverage"), dict)
        else {}
    )
    tuple_coverage_required_platforms = _normalized_token_list(
        release_channel_tuple_coverage.get("requiredDesktopPlatforms")
    )
    tuple_coverage_required_heads = _normalized_token_list(
        release_channel_tuple_coverage.get("requiredDesktopHeads")
    )
    tuple_coverage_promoted_platform_heads_raw = (
        release_channel_tuple_coverage.get("promotedPlatformHeads")
        if isinstance(release_channel_tuple_coverage.get("promotedPlatformHeads"), dict)
        else {}
    )
    tuple_coverage_promoted_platform_heads = {
        str(platform).strip().lower(): _normalized_token_list(heads)
        for platform, heads in tuple_coverage_promoted_platform_heads_raw.items()
        if str(platform).strip()
    }
    tuple_coverage_reported_missing_platform_head_pairs = _normalized_token_list(
        release_channel_tuple_coverage.get("missingRequiredPlatformHeadPairs")
    )
    executable_required_heads = _normalized_token_list((executable_gate_evidence or {}).get("heads_requiring_flagship_proof"))
    if not executable_required_heads:
        executable_required_heads = _normalized_token_list((executable_gate_evidence or {}).get("flagship_required_desktop_heads"))
    if not executable_required_heads:
        executable_required_heads = _normalized_token_list((executable_gate_evidence or {}).get("promoted_desktop_heads"))
    missing_required_tuple_heads = [head for head in executable_required_heads if head not in set(promoted_tuple_heads)]
    visual_required_heads = _normalized_token_list((executable_gate_evidence or {}).get("visual_familiarity_required_desktop_heads"))
    workflow_required_heads = _normalized_token_list((executable_gate_evidence or {}).get("workflow_execution_required_desktop_heads"))
    visual_head_proofs = _normalized_status_map((executable_gate_evidence or {}).get("visual_familiarity_head_proofs"))
    workflow_head_proofs = _normalized_status_map((executable_gate_evidence or {}).get("workflow_execution_head_proofs"))
    missing_visual_required_inventory_heads = [
        head for head in executable_required_heads if head not in set(visual_required_heads)
    ]
    missing_workflow_required_inventory_heads = [
        head for head in executable_required_heads if head not in set(workflow_required_heads)
    ]
    missing_visual_passing_head_proofs = [
        head for head in executable_required_heads if visual_head_proofs.get(head) not in {"pass", "passed", "ready"}
    ]
    missing_workflow_passing_head_proofs = [
        head for head in executable_required_heads if workflow_head_proofs.get(head) not in {"pass", "passed", "ready"}
    ]
    required_platforms_for_pair_matrix = tuple_coverage_required_platforms or ["linux", "windows", "macos"]
    required_heads_for_pair_matrix = tuple_coverage_required_heads or executable_required_heads
    promoted_platform_heads_for_pair_matrix: Dict[str, List[str]] = {}
    for platform in required_platforms_for_pair_matrix:
        promoted_heads = tuple_coverage_promoted_platform_heads.get(platform)
        if promoted_heads is None:
            promoted_heads = sorted(
                {
                    str(tuple_key).split(":", 1)[0].strip().lower()
                    for tuple_key in promoted_tuple_keys_by_platform.get(platform, [])
                    if str(tuple_key).strip() and ":" in str(tuple_key)
                }
            )
        promoted_platform_heads_for_pair_matrix[platform] = promoted_heads
    missing_required_platform_head_pairs_derived = sorted(
        {
            f"{head}:{platform}"
            for platform in required_platforms_for_pair_matrix
            for head in required_heads_for_pair_matrix
            if head and head not in set(promoted_platform_heads_for_pair_matrix.get(platform, []))
        }
    )
    missing_required_platform_head_pairs = (
        tuple_coverage_reported_missing_platform_head_pairs
        if tuple_coverage_reported_missing_platform_head_pairs
        else missing_required_platform_head_pairs_derived
    )
    tuple_coverage_missing_pair_inventory_mismatch = sorted(
        set(tuple_coverage_reported_missing_platform_head_pairs).symmetric_difference(
            set(missing_required_platform_head_pairs_derived)
        )
    )

    has_linux_public_installer = bool(promoted_tuple_keys_by_platform["linux"])
    has_windows_public_installer = bool(promoted_tuple_keys_by_platform["windows"])
    has_macos_public_installer = bool(promoted_tuple_keys_by_platform["macos"])
    if release_channel_published_and_proven and release_channel_freshness_ok and has_avalonia_public_artifact:
        desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel is not simultaneously published, release-proven, and Avalonia-desktop-backed."
        )
    if not has_linux_public_installer:
        desktop_reasons.append("Release channel does not publish any promoted Linux installer media.")
    if not has_windows_public_installer:
        desktop_reasons.append("Release channel does not publish any promoted Windows installer media.")
    linux_statuses = dict((executable_gate_evidence or {}).get("linux_statuses") or {})
    windows_statuses = dict((executable_gate_evidence or {}).get("windows_statuses") or {})
    macos_statuses = dict((executable_gate_evidence or {}).get("macos_statuses") or {})
    if (
        not linux_statuses
        and promoted_tuple_keys_by_platform["linux"] == ["avalonia:linux-x64"]
        and proof_passed(ui_linux_exit_gate, expected_contract="chummer6-ui.linux_desktop_exit_gate")
    ):
        linux_statuses = {"avalonia:linux-x64": "pass"}
    if (
        not windows_statuses
        and promoted_tuple_keys_by_platform["windows"] == ["avalonia:win-x64"]
        and windows_exit_gate_passed(ui_windows_exit_gate)
    ):
        windows_statuses = {"avalonia:win-x64": "pass"}

    def _tuple_proof_stats(statuses: Dict[str, Any], expected_keys: List[str]) -> tuple[int, int, List[str]]:
        normalized_statuses = {str(key).strip(): str(value).strip().lower() for key, value in statuses.items()}
        passing_count = sum(1 for key in expected_keys if normalized_statuses.get(key) in {"pass", "passed", "ready"})
        missing_or_failing = [key for key in expected_keys if normalized_statuses.get(key) not in {"pass", "passed", "ready"}]
        missing_or_failing.extend(
            sorted(
                key
                for key, value in normalized_statuses.items()
                if key not in expected_keys and value not in {"pass", "passed", "ready"}
            )
        )
        return len(expected_keys), passing_count, sorted(set(missing_or_failing))

    linux_tuple_count, linux_passing_status_count, linux_missing_or_failing_keys = _tuple_proof_stats(
        linux_statuses, promoted_tuple_keys_by_platform["linux"]
    )
    windows_tuple_count, windows_passing_status_count, windows_missing_or_failing_keys = _tuple_proof_stats(
        windows_statuses, promoted_tuple_keys_by_platform["windows"]
    )
    macos_tuple_count, macos_passing_status_count, macos_missing_or_failing_keys = _tuple_proof_stats(
        macos_statuses, promoted_tuple_keys_by_platform["macos"]
    )

    if invalid_tuple_metadata_by_platform["linux"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Linux installer media without explicit head/rid tuple metadata."
        )
    if invalid_tuple_metadata_by_platform["windows"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Windows installer media without explicit head/rid tuple metadata."
        )
    if invalid_tuple_metadata_by_platform["macos"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes macOS installer media without explicit head/rid tuple metadata."
        )
    if channel_mismatch_keys_by_platform["linux"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Linux installer media with artifact channel metadata that does not match top-level channelId."
        )
    if channel_mismatch_keys_by_platform["windows"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Windows installer media with artifact channel metadata that does not match top-level channelId."
        )
    if channel_mismatch_keys_by_platform["macos"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes macOS installer media with artifact channel metadata that does not match top-level channelId."
        )
    if missing_required_tuple_heads:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel is missing promoted installer tuple proof for required desktop head(s): "
            + ", ".join(missing_required_tuple_heads)
            + "."
        )
    if tuple_coverage_missing_pair_inventory_mismatch:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel desktop tuple coverage missingRequiredPlatformHeadPairs inventory does not match promoted installer tuple reality."
        )
    if missing_required_platform_head_pairs:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel is missing required desktop platform/head installer tuple pair(s): "
            + ", ".join(missing_required_platform_head_pairs)
            + "."
        )
    if not visual_required_heads:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate evidence is missing visual-familiarity required desktop head inventory."
        )
    if not workflow_required_heads:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate evidence is missing workflow-execution required desktop head inventory."
        )
    if missing_visual_required_inventory_heads:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate visual-familiarity required head inventory is missing required desktop head(s): "
            + ", ".join(missing_visual_required_inventory_heads)
            + "."
        )
    if missing_workflow_required_inventory_heads:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate workflow-execution required head inventory is missing required desktop head(s): "
            + ", ".join(missing_workflow_required_inventory_heads)
            + "."
        )
    if missing_visual_passing_head_proofs:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate visual-familiarity per-head proof is missing or not passing for required desktop head(s): "
            + ", ".join(missing_visual_passing_head_proofs)
            + "."
        )
    if missing_workflow_passing_head_proofs:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate workflow-execution per-head proof is missing or not passing for required desktop head(s): "
            + ", ".join(missing_workflow_passing_head_proofs)
            + "."
        )

    if has_linux_public_installer:
        if linux_tuple_count > 0 and linux_passing_status_count == linux_tuple_count and not linux_missing_or_failing_keys:
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes Linux installer media, but executable-gate evidence is missing passing Linux startup-smoke tuple proof."
            )
    if has_windows_public_installer:
        if windows_tuple_count > 0 and windows_passing_status_count == windows_tuple_count and not windows_missing_or_failing_keys:
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes Windows installer media, but executable-gate evidence is missing passing Windows startup-smoke tuple proof."
            )
    if has_macos_public_installer:
        if macos_tuple_count > 0 and macos_passing_status_count == macos_tuple_count and not macos_missing_or_failing_keys:
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes macOS installer media, but executable-gate evidence is missing passing macOS startup-smoke tuple proof."
            )
    install_journey_state = str((journeys.get("install_claim_restore_continue") or {}).get("state") or "").strip()
    build_journey_state = str((journeys.get("build_explain_publish") or {}).get("state") or "").strip()
    if install_journey_state == "ready":
        desktop_positives += 1
    else:
        desktop_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if build_journey_state == "ready":
        desktop_positives += 1
    else:
        desktop_reasons.append(f"Build/explain/publish journey is {build_journey_state or 'missing'}, not ready.")
    ui_stage = str(ui_project.get("readiness_stage") or "").strip()
    ui_promotion = project_posture(ui_project)
    if compare_order(ui_stage, "publicly_promoted", STAGE_ORDER) >= 0 and compare_order(ui_promotion, "public", PROMOTION_ORDER) >= 0:
        desktop_positives += 1
    else:
        desktop_reasons.append(
            f"UI project posture is {ui_stage or 'unknown'} / {ui_promotion or 'unknown'}, below flagship desktop promotion."
        )
    coverage["desktop_client"], details["desktop_client"] = _coverage_entry(
        positives=desktop_positives,
        reasons=desktop_reasons,
        summary_ready="Desktop install, release-channel, and flagship workbench proof are current.",
        summary_missing="Desktop flagship proof is still incomplete.",
        hard_fail=desktop_hard_fail,
        evidence={
            "ui_stage": ui_stage,
            "ui_promotion": ui_promotion,
            "ui_local_release_status": str(ui_local_release_proof.get("status") or "").strip(),
            "ui_executable_exit_gate_status": str(ui_executable_exit_gate.get("status") or "").strip(),
            "ui_executable_exit_gate_path": report_path(ui_executable_exit_gate_path),
            "ui_executable_exit_gate_reason_count": len(
                [str(item).strip() for item in (ui_executable_exit_gate.get("reasons") or []) if str(item).strip()]
            ),
            "ui_executable_exit_gate_reasons": [
                str(item).strip() for item in (ui_executable_exit_gate.get("reasons") or []) if str(item).strip()
            ],
            "ui_executable_gate_freshness_max_age_seconds": DESKTOP_EXECUTABLE_GATE_PROOF_MAX_AGE_SECONDS,
            "ui_executable_gate_freshness_proof_age_seconds": executable_gate_freshness_proof_ages,
            "ui_executable_gate_freshness_issue_count": len(executable_gate_freshness_issues_list),
            "ui_executable_gate_freshness_issues": executable_gate_freshness_issues_list,
            "ui_executable_gate_generated_at": executable_gate_generated_at_raw,
            "ui_executable_gate_age_seconds": executable_gate_age_seconds,
            "ui_linux_exit_gate_status": str(ui_linux_exit_gate.get("status") or "").strip(),
            "ui_windows_exit_gate_status": str(ui_windows_exit_gate.get("status") or "").strip(),
            "ui_windows_exit_gate_payload_marker_present": bool((ui_windows_exit_gate.get("checks") or {}).get("embedded_payload_marker_present")),
            "ui_windows_exit_gate_sample_marker_present": bool((ui_windows_exit_gate.get("checks") or {}).get("embedded_sample_marker_present")),
            "ui_workflow_execution_gate_status": str(ui_workflow_execution_gate.get("status") or "").strip(),
            "ui_workflow_execution_gate_path": report_path(ui_workflow_execution_gate_path),
            "ui_workflow_execution_gate_family_missing_receipt_count": len(workflow_execution_receipt_gaps["workflow_family_missing_receipts"]),
            "ui_workflow_execution_gate_family_failing_receipt_count": len(workflow_execution_receipt_gaps["workflow_family_failing_receipts"]),
            "ui_workflow_execution_gate_execution_missing_receipt_count": len(workflow_execution_receipt_gaps["workflow_execution_missing_receipts"]),
            "ui_workflow_execution_gate_execution_failing_receipt_count": len(workflow_execution_receipt_gaps["workflow_execution_failing_receipts"]),
            "ui_workflow_execution_gate_execution_weak_receipt_count": len(workflow_execution_receipt_gaps["workflow_execution_weak_receipts"]),
            "ui_workflow_execution_gate_unresolved_receipt_count": len(unresolved_workflow_execution_receipts),
            "ui_workflow_execution_gate_unresolved_receipts": unresolved_workflow_execution_receipts,
            "ui_visual_familiarity_exit_gate_status": str(ui_visual_familiarity_exit_gate.get("status") or "").strip(),
            "ui_visual_familiarity_exit_gate_path": report_path(ui_visual_familiarity_exit_gate_path),
            "ui_visual_familiarity_required_milestone2_tests": list(DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TESTS),
            "ui_visual_familiarity_required_test_inventory_count": len(visual_required_tests),
            "ui_visual_familiarity_missing_test_inventory_count": len(visual_missing_tests),
            "ui_visual_familiarity_missing_required_milestone2_test_inventory_count": len(
                visual_missing_required_milestone2_tests_from_inventory
            ),
            "ui_visual_familiarity_missing_required_milestone2_test_inventory": (
                visual_missing_required_milestone2_tests_from_inventory
            ),
            "ui_visual_familiarity_reported_missing_required_milestone2_test_count": len(
                visual_reported_missing_milestone2_tests
            ),
            "ui_visual_familiarity_reported_missing_required_milestone2_tests": visual_reported_missing_milestone2_tests,
            "ui_visual_familiarity_missing_required_legacy_interaction_key_count": len(
                visual_missing_legacy_interaction_keys
            ),
            "ui_visual_familiarity_missing_required_legacy_interaction_keys": visual_missing_legacy_interaction_keys,
            "ui_workflow_parity_status": str(ui_workflow_parity_proof.get("status") or "").strip(),
            "ui_workflow_parity_path": report_path(ui_workflow_parity_proof_path),
            "sr4_workflow_parity_status": str(sr4_workflow_parity_proof.get("status") or "").strip(),
            "sr4_workflow_parity_path": report_path(sr4_workflow_parity_proof_path),
            "sr6_workflow_parity_status": str(sr6_workflow_parity_proof.get("status") or "").strip(),
            "sr6_workflow_parity_path": report_path(sr6_workflow_parity_proof_path),
            "sr4_sr6_frontier_receipt_status": str(sr4_sr6_frontier_receipt.get("status") or "").strip(),
            "sr4_sr6_frontier_receipt_path": report_path(sr4_sr6_frontier_receipt_path),
            "release_channel_status": str(release_channel.get("status") or "").strip(),
            "release_channel_release_proof_status": str(release_proof.get("status") or "").strip(),
            "release_channel_generated_at": release_channel_generated_at_raw,
            "release_channel_age_seconds": release_channel_age_seconds,
            "release_channel_freshness_max_age_seconds": RELEASE_CHANNEL_PROOF_MAX_AGE_SECONDS,
            "release_channel_freshness_ok": release_channel_freshness_ok,
            "release_channel_id": release_channel_id,
            "release_channel_heads": artifact_heads,
            "release_channel_has_linux_public_installer": has_linux_public_installer,
            "release_channel_has_windows_public_installer": has_windows_public_installer,
            "release_channel_has_macos_public_installer": has_macos_public_installer,
            "release_channel_linux_promoted_tuples": promoted_tuple_keys_by_platform["linux"],
            "release_channel_windows_promoted_tuples": promoted_tuple_keys_by_platform["windows"],
            "release_channel_macos_promoted_tuples": promoted_tuple_keys_by_platform["macos"],
            "release_channel_promoted_tuple_heads": promoted_tuple_heads,
            "ui_executable_gate_required_promoted_heads": executable_required_heads,
            "release_channel_missing_required_head_tuples": missing_required_tuple_heads,
            "release_channel_required_tuple_platforms": required_platforms_for_pair_matrix,
            "release_channel_required_tuple_heads": required_heads_for_pair_matrix,
            "release_channel_promoted_platform_heads": promoted_platform_heads_for_pair_matrix,
            "release_channel_missing_required_platform_head_pairs": missing_required_platform_head_pairs,
            "release_channel_missing_required_platform_head_pairs_derived": (
                missing_required_platform_head_pairs_derived
            ),
            "release_channel_tuple_coverage_reported_missing_required_platform_head_pairs": (
                tuple_coverage_reported_missing_platform_head_pairs
            ),
            "release_channel_tuple_coverage_missing_pair_inventory_mismatch": (
                tuple_coverage_missing_pair_inventory_mismatch
            ),
            "ui_executable_gate_visual_required_promoted_heads": visual_required_heads,
            "ui_executable_gate_workflow_required_promoted_heads": workflow_required_heads,
            "ui_executable_gate_visual_missing_required_inventory_heads": missing_visual_required_inventory_heads,
            "ui_executable_gate_workflow_missing_required_inventory_heads": missing_workflow_required_inventory_heads,
            "ui_executable_gate_visual_missing_or_failing_head_proofs": missing_visual_passing_head_proofs,
            "ui_executable_gate_workflow_missing_or_failing_head_proofs": missing_workflow_passing_head_proofs,
            "release_channel_linux_has_invalid_tuple_metadata": invalid_tuple_metadata_by_platform["linux"],
            "release_channel_windows_has_invalid_tuple_metadata": invalid_tuple_metadata_by_platform["windows"],
            "release_channel_macos_has_invalid_tuple_metadata": invalid_tuple_metadata_by_platform["macos"],
            "release_channel_linux_channel_mismatch_keys": channel_mismatch_keys_by_platform["linux"],
            "release_channel_windows_channel_mismatch_keys": channel_mismatch_keys_by_platform["windows"],
            "release_channel_macos_channel_mismatch_keys": channel_mismatch_keys_by_platform["macos"],
            "ui_executable_gate_linux_statuses": linux_statuses,
            "ui_executable_gate_linux_tuple_count": linux_tuple_count,
            "ui_executable_gate_linux_passing_tuple_count": linux_passing_status_count,
            "ui_executable_gate_linux_missing_or_failing_keys": linux_missing_or_failing_keys,
            "ui_executable_gate_windows_statuses": windows_statuses,
            "ui_executable_gate_windows_tuple_count": windows_tuple_count,
            "ui_executable_gate_windows_passing_tuple_count": windows_passing_status_count,
            "ui_executable_gate_windows_missing_or_failing_keys": windows_missing_or_failing_keys,
            "ui_executable_gate_macos_statuses": macos_statuses,
            "ui_executable_gate_macos_tuple_count": macos_tuple_count,
            "ui_executable_gate_macos_passing_tuple_count": macos_passing_status_count,
            "ui_executable_gate_macos_missing_or_failing_keys": macos_missing_or_failing_keys,
            "install_claim_restore_continue": install_journey_state,
            "build_explain_publish": build_journey_state,
        },
    )

    core_project = projects.get("core") or {}
    rules_reasons: List[str] = []
    rules_positives = 0
    core_stage = str(core_project.get("readiness_stage") or "").strip()
    if compare_order(core_stage, "boundary_pure", STAGE_ORDER) >= 0:
        rules_positives += 1
    else:
        rules_reasons.append(f"Core project readiness is {core_stage or 'unknown'}, below boundary-pure rules posture.")
    if build_journey_state == "ready":
        rules_positives += 1
    else:
        rules_reasons.append(f"Build/explain/publish journey is {build_journey_state or 'missing'}, not ready.")
    if rules_cert_payload and str(rules_cert_payload.get("status") or "").strip().lower() in {"passed", "pass", "ready"}:
        rules_positives += 1
    else:
        rules_reasons.append("No explicit rules/import certification artifact is currently published.")
    coverage["rules_engine_and_import"], details["rules_engine_and_import"] = _coverage_entry(
        positives=rules_positives,
        reasons=rules_reasons,
        summary_ready="Rules parity and import certification are explicitly proven.",
        summary_missing="Rules and import flagship proof is still incomplete.",
        evidence={
            "core_stage": core_stage,
            "build_explain_publish": build_journey_state,
            "rules_certification_path": str(rules_cert_path) if rules_cert_path else "",
            "rules_certification_status": str(rules_cert_payload.get("status") or "").strip(),
        },
    )

    hub_project = projects.get("hub") or {}
    registry_project = projects.get("hub-registry") or {}
    hub_reasons: List[str] = []
    hub_positives = 0
    report_cluster_state = str((journeys.get("report_cluster_release_notify") or {}).get("state") or "").strip()
    if proof_passed(hub_local_release_proof, expected_contract="chummer6-hub.local_release_proof"):
        hub_positives += 1
    else:
        hub_reasons.append("Hub local release proof is missing or not passed.")
    if str(release_channel.get("status") or "").strip().lower() == "published" and str(release_proof.get("status") or "").strip().lower() == "passed":
        hub_positives += 1
    else:
        hub_reasons.append("Registry release channel is not in a published-and-proven state.")
    if install_journey_state == "ready":
        hub_positives += 1
    else:
        hub_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if report_cluster_state == "ready":
        hub_positives += 1
    else:
        hub_reasons.append(f"Report/cluster/release/notify journey is {report_cluster_state or 'missing'}, not ready.")
    hub_stage = str(hub_project.get("readiness_stage") or "").strip()
    hub_promotion = project_posture(hub_project)
    registry_stage = str(registry_project.get("readiness_stage") or "").strip()
    if compare_order(hub_stage, "publicly_promoted", STAGE_ORDER) >= 0 and compare_order(hub_promotion, "public", PROMOTION_ORDER) >= 0:
        hub_positives += 1
    else:
        hub_reasons.append(f"Hub project posture is {hub_stage or 'unknown'} / {hub_promotion or 'unknown'}, below flagship public support posture.")
    if compare_order(registry_stage, "boundary_pure", STAGE_ORDER) >= 0:
        hub_positives += 1
    else:
        hub_reasons.append(f"Hub-registry readiness is {registry_stage or 'unknown'}, below boundary-pure publication posture.")
    coverage["hub_and_registry"], details["hub_and_registry"] = _coverage_entry(
        positives=hub_positives,
        reasons=hub_reasons,
        summary_ready="Hub, registry, and public release shelf proof are aligned.",
        summary_missing="Hub and registry flagship proof is still incomplete.",
        evidence={
            "hub_stage": hub_stage,
            "hub_promotion": hub_promotion,
            "hub_registry_stage": registry_stage,
            "hub_local_release_status": str(hub_local_release_proof.get("status") or "").strip(),
            "release_channel_status": str(release_channel.get("status") or "").strip(),
            "release_channel_release_proof": str(release_proof.get("status") or "").strip(),
            "install_claim_restore_continue": install_journey_state,
            "report_cluster_release_notify": report_cluster_state,
        },
    )

    mobile_project = projects.get("mobile") or {}
    mobile_reasons: List[str] = []
    mobile_positives = 0
    campaign_recap_state = str((journeys.get("campaign_session_recover_recap") or {}).get("state") or "").strip()
    conflict_state = str((journeys.get("recover_from_sync_conflict") or {}).get("state") or "").strip()
    if proof_passed(mobile_local_release_proof, expected_contract="chummer6-mobile.local_release_proof"):
        mobile_positives += 1
    else:
        mobile_reasons.append("Mobile local release proof is missing or not passed.")
    if campaign_recap_state == "ready":
        mobile_positives += 1
    else:
        mobile_reasons.append(f"Campaign/recover/recap journey is {campaign_recap_state or 'missing'}, not ready.")
    if conflict_state == "ready":
        mobile_positives += 1
    else:
        mobile_reasons.append(f"Recover-from-sync-conflict journey is {conflict_state or 'missing'}, not ready.")
    mobile_stage = str(mobile_project.get("readiness_stage") or "").strip()
    mobile_promotion = project_posture(mobile_project)
    if compare_order(mobile_stage, "publicly_promoted", STAGE_ORDER) >= 0 and compare_order(mobile_promotion, "public", PROMOTION_ORDER) >= 0:
        mobile_positives += 1
    else:
        mobile_reasons.append(
            f"Mobile project posture is {mobile_stage or 'unknown'} / {mobile_promotion or 'unknown'}, below flagship play-shell promotion."
        )
    coverage["mobile_play_shell"], details["mobile_play_shell"] = _coverage_entry(
        positives=mobile_positives,
        reasons=mobile_reasons,
        summary_ready="Mobile play-shell continuity and reconnect proof are current.",
        summary_missing="Mobile and live-play flagship proof is still incomplete.",
        evidence={
            "mobile_stage": mobile_stage,
            "mobile_promotion": mobile_promotion,
            "mobile_local_release_status": str(mobile_local_release_proof.get("status") or "").strip(),
            "campaign_session_recover_recap": campaign_recap_state,
            "recover_from_sync_conflict": conflict_state,
        },
    )

    ui_kit_project = projects.get("ui-kit") or {}
    ui_kit_reasons: List[str] = []
    ui_kit_positives = 0
    ui_kit_stage = str(ui_kit_project.get("readiness_stage") or "").strip()
    if compare_order(ui_kit_stage, "boundary_pure", STAGE_ORDER) >= 0:
        ui_kit_positives += 1
    else:
        ui_kit_reasons.append(f"UI kit readiness is {ui_kit_stage or 'unknown'}, below boundary-pure shared-surface posture.")
    if build_journey_state == "ready":
        ui_kit_positives += 1
    else:
        ui_kit_reasons.append(f"Build/explain/publish journey is {build_journey_state or 'missing'}, not ready.")
    if campaign_recap_state == "ready":
        ui_kit_positives += 1
    else:
        ui_kit_reasons.append(f"Campaign/recover/recap journey is {campaign_recap_state or 'missing'}, not ready.")
    if compare_order(ui_stage, "publicly_promoted", STAGE_ORDER) >= 0 and compare_order(mobile_stage, "publicly_promoted", STAGE_ORDER) >= 0:
        ui_kit_positives += 1
    else:
        ui_kit_reasons.append("Workbench and mobile promoted posture is not yet jointly proven.")
    coverage["ui_kit_and_flagship_polish"], details["ui_kit_and_flagship_polish"] = _coverage_entry(
        positives=ui_kit_positives,
        reasons=ui_kit_reasons,
        summary_ready="Shared UI, accessibility, and flagship polish proof is current across heads.",
        summary_missing="Shared UI and flagship polish proof is still incomplete.",
        evidence={
            "ui_kit_stage": ui_kit_stage,
            "ui_stage": ui_stage,
            "mobile_stage": mobile_stage,
            "build_explain_publish": build_journey_state,
            "campaign_session_recover_recap": campaign_recap_state,
        },
    )

    media_project = projects.get("media-factory") or {}
    media_reasons: List[str] = []
    media_positives = 0
    media_stage = str(media_project.get("readiness_stage") or "").strip()
    if compare_order(media_stage, "boundary_pure", STAGE_ORDER) >= 0:
        media_positives += 1
    else:
        media_reasons.append(f"Media-factory readiness is {media_stage or 'unknown'}, below boundary-pure publication posture.")
    if build_journey_state == "ready":
        media_positives += 1
    else:
        media_reasons.append(f"Build/explain/publish journey is {build_journey_state or 'missing'}, not ready.")
    if media_proof_payload and str(media_proof_payload.get("status") or "").strip().lower() in {"passed", "pass", "ready"}:
        media_positives += 1
    else:
        media_reasons.append("No explicit media/artifact publication proof is currently published.")
    coverage["media_artifacts"], details["media_artifacts"] = _coverage_entry(
        positives=media_positives,
        reasons=media_reasons,
        summary_ready="Artifact publication and media proof are explicitly green.",
        summary_missing="Media and artifact flagship proof is still incomplete.",
        evidence={
            "media_stage": media_stage,
            "build_explain_publish": build_journey_state,
            "media_proof_path": str(media_proof_path) if media_proof_path else "",
            "media_proof_status": str(media_proof_payload.get("status") or "").strip(),
        },
    )

    horizons_reasons: List[str] = []
    horizons_positives = 0
    if progress_report:
        horizons_positives += 1
    else:
        horizons_reasons.append("Progress report is missing.")
    if str(public_group.get("deployment_status") or "").strip().lower() == "public":
        horizons_positives += 1
    else:
        horizons_reasons.append("Public Chummer group posture is not marked public.")
    if install_journey_state == "ready":
        horizons_positives += 1
    else:
        horizons_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if report_cluster_state == "ready":
        horizons_positives += 1
    else:
        horizons_reasons.append(f"Report/cluster/release/notify journey is {report_cluster_state or 'missing'}, not ready.")
    if acceptance:
        horizons_positives += 1
    else:
        horizons_reasons.append("Flagship acceptance matrix is missing from the design mirror.")
    coverage["horizons_and_public_surface"], details["horizons_and_public_surface"] = _coverage_entry(
        positives=horizons_positives,
        reasons=horizons_reasons,
        summary_ready="Horizons posture and public surface proof are aligned with live release truth.",
        summary_missing="Horizons and public-surface flagship proof is still incomplete.",
        evidence={
            "public_group_deployment_status": str(public_group.get("deployment_status") or "").strip(),
            "progress_report_generated_at": str(progress_report.get("generated_at") or "").strip(),
            "install_claim_restore_continue": install_journey_state,
            "report_cluster_release_notify": report_cluster_state,
            "acceptance_path": str(effective_acceptance_path),
        },
    )

    fleet_reasons: List[str] = []
    fleet_positives = 0
    runtime_alert_state = str(runtime_healing_summary.get("alert_state") or "").strip().lower()
    runtime_last_event_at = parse_iso(runtime_healing_summary.get("last_event_at"))
    supervisor_mode = str(supervisor_state.get("mode") or "").strip()
    supervisor_completion_status = _supervisor_completion_status(supervisor_state)
    supervisor_updated_at = parse_iso(supervisor_state.get("updated_at"))
    supervisor_recent_enough = (
        supervisor_updated_at is not None
        and (utc_now() - supervisor_updated_at).total_seconds() <= FLAGSHIP_OPERATOR_SUPERVISOR_MAX_AGE_HOURS * 3600
    )
    supervisor_loop_ready = (
        supervisor_mode in {"loop", "flagship_product", "complete"}
        and supervisor_completion_status in {"pass", "passed"}
        and supervisor_recent_enough
    )
    ooda_controller = str(ooda_state.get("controller") or "").strip().lower()
    ooda_supervisor = str(ooda_state.get("supervisor") or "").strip().lower()
    ooda_aggregate_stale = bool(ooda_state.get("aggregate_stale"))
    ooda_timestamp_stale = bool(ooda_state.get("aggregate_timestamp_stale"))
    ooda_steady_complete_quiet = _ooda_steady_complete_quiet(ooda_state)
    ooda_loop_ready = (
        ooda_controller == "up"
        and ooda_supervisor == "up"
        and (not ooda_aggregate_stale or ooda_steady_complete_quiet)
    )

    runtime_healing_ready = runtime_alert_state == "healthy"
    runtime_healing_override = False
    if not runtime_healing_ready:
        stale_incident = (
            runtime_last_event_at is not None
            and (utc_now() - runtime_last_event_at).total_seconds() >= FLAGSHIP_OPERATOR_STALE_INCIDENT_HOURS * 3600
        )
        if stale_incident and supervisor_loop_ready and ooda_loop_ready:
            runtime_healing_ready = True
            runtime_healing_override = True

    if runtime_healing_ready:
        fleet_positives += 1
    else:
        fleet_reasons.append(f"Runtime healing alert state is {runtime_healing_summary.get('alert_state') or 'missing'}.")
    if supervisor_loop_ready:
        fleet_positives += 1
    else:
        fleet_reasons.append(
            "Supervisor state is not current flagship-pass proof (mode, completion status, or recency check failed)."
        )
    if ooda_loop_ready:
        fleet_positives += 1
    else:
        fleet_reasons.append("OODA monitor does not currently report controller/supervisor up with non-stale aggregate state.")
    if str(journey_summary.get("overall_state") or "").strip().lower() == "ready":
        fleet_positives += 1
    else:
        fleet_reasons.append(f"Journey-gate overall state is {journey_summary.get('overall_state') or 'missing'}, not ready.")
    if history_snapshot_count >= 4:
        fleet_positives += 1
    else:
        fleet_reasons.append(f"Progress history only has {history_snapshot_count} snapshots; flagship operator proof expects at least 4.")
    if support_packets and parse_iso(support_packets.get("generated_at")) is not None:
        fleet_positives += 1
    else:
        fleet_reasons.append("Support-case packets are missing or stale enough to lack a generated_at timestamp.")
    compile_manifest_path = status_plane_path.parent / "compile.manifest.json"
    compile_manifest = load_json(compile_manifest_path)
    if bool(compile_manifest.get("dispatchable_truth_ready")):
        fleet_positives += 1
    else:
        fleet_reasons.append("Fleet compile manifest is not marked dispatchable_truth_ready.")
    coverage["fleet_and_operator_loop"], details["fleet_and_operator_loop"] = _coverage_entry(
        positives=fleet_positives,
        reasons=fleet_reasons,
        summary_ready="Fleet control-loop proof is current and steering a ready product surface set.",
        summary_missing="Fleet and operator-loop flagship proof is still incomplete.",
        evidence={
            "runtime_healing_alert_state": str(runtime_healing_summary.get("alert_state") or "").strip(),
            "runtime_healing_last_event_at": str(runtime_healing_summary.get("last_event_at") or "").strip(),
            "runtime_healing_override_stale_incident": runtime_healing_override,
            "journey_overall_state": str(journey_summary.get("overall_state") or "").strip(),
            "history_snapshot_count": history_snapshot_count,
            "support_packets_generated_at": str(support_packets.get("generated_at") or "").strip(),
            "dispatchable_truth_ready": bool(compile_manifest.get("dispatchable_truth_ready")),
            "supervisor_mode": supervisor_mode,
            "supervisor_completion_status": supervisor_completion_status,
            "supervisor_updated_at": str(supervisor_state.get("updated_at") or "").strip(),
            "supervisor_recent_enough": supervisor_recent_enough,
            "ooda_controller": ooda_controller,
            "ooda_supervisor": ooda_supervisor,
            "ooda_aggregate_stale": ooda_aggregate_stale,
            "ooda_timestamp_stale": ooda_timestamp_stale,
            "ooda_steady_complete_quiet": ooda_steady_complete_quiet,
        },
    )

    ready_keys = [key for key, value in coverage.items() if value == "ready"]
    warning_keys = [key for key, value in coverage.items() if value == "warning"]
    missing_keys = [key for key, value in coverage.items() if value == "missing"]
    status = "pass" if not warning_keys and not missing_keys else "fail"

    payload: Dict[str, Any] = {
        "contract_name": "fleet.flagship_product_readiness",
        "schema_version": 1,
        "generated_at": iso(utc_now()),
        "status": status,
        "summary": {
            "ready_count": len(ready_keys),
            "warning_count": len(warning_keys),
            "missing_count": len(missing_keys),
            "history_snapshot_count": history_snapshot_count,
        },
        "source_documents": [str(item) for item in (acceptance.get("source_documents") or []) if str(item).strip()],
        "acceptance_axes": [
            str(item.get("id") or "").strip()
            for item in (acceptance.get("acceptance_axes") or [])
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        ],
        "coverage": coverage,
        "coverage_details": details,
        "ready_keys": ready_keys,
        "warning_keys": warning_keys,
        "missing_keys": missing_keys,
        "evidence_sources": {
            "acceptance": str(effective_acceptance_path),
            "status_plane": str(status_plane_path),
            "progress_report": str(progress_report_path),
            "progress_history": str(progress_history_path),
            "journey_gates": str(journey_gates_path),
            "support_packets": str(support_packets_path),
            "supervisor_state": str(effective_supervisor_state_path),
            "ooda_state": str(ooda_state_path),
            "ui_local_release_proof": report_path(ui_local_release_proof_path),
            "ui_executable_exit_gate": report_path(ui_executable_exit_gate_path),
            "ui_linux_exit_gate": report_path(ui_linux_exit_gate_path),
            "ui_windows_exit_gate": report_path(ui_windows_exit_gate_path),
            "ui_workflow_execution_gate": report_path(ui_workflow_execution_gate_path),
            "ui_visual_familiarity_exit_gate": report_path(ui_visual_familiarity_exit_gate_path),
            "ui_workflow_parity_proof": report_path(ui_workflow_parity_proof_path),
            "sr4_workflow_parity_proof": report_path(sr4_workflow_parity_proof_path),
            "sr6_workflow_parity_proof": report_path(sr6_workflow_parity_proof_path),
            "sr4_sr6_frontier_receipt": report_path(sr4_sr6_frontier_receipt_path),
            "hub_local_release_proof": str(hub_local_release_proof_path),
            "mobile_local_release_proof": str(mobile_local_release_proof_path),
            "release_channel": str(release_channel_path),
            "releases_json": str(releases_json_path),
        },
    }
    return payload


def _normalized_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    return normalized


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _compile_manifest_missing_artifact(repo_root: Path, artifact_name: str) -> bool:
    manifest_path = repo_root / ".codex-studio" / "published" / "compile.manifest.json"
    manifest = load_json(manifest_path)
    artifacts = [str(item).strip() for item in (manifest.get("artifacts") or []) if str(item).strip()]
    return artifact_name not in artifacts


def materialize_flagship_product_readiness(
    *,
    out_path: Path,
    mirror_path: Path | None,
    acceptance_path: Path,
    status_plane_path: Path,
    progress_report_path: Path,
    progress_history_path: Path,
    journey_gates_path: Path,
    support_packets_path: Path,
    supervisor_state_path: Path,
    ooda_state_path: Path,
    ui_local_release_proof_path: Path,
    ui_linux_exit_gate_path: Path,
    ui_windows_exit_gate_path: Path,
    ui_workflow_parity_proof_path: Path,
    ui_executable_exit_gate_path: Path,
    ui_workflow_execution_gate_path: Path,
    ui_visual_familiarity_exit_gate_path: Path,
    sr4_workflow_parity_proof_path: Path,
    sr6_workflow_parity_proof_path: Path,
    sr4_sr6_frontier_receipt_path: Path,
    hub_local_release_proof_path: Path,
    mobile_local_release_proof_path: Path,
    release_channel_path: Path,
    releases_json_path: Path,
) -> Dict[str, Any]:
    payload = build_flagship_product_readiness_payload(
        acceptance_path=acceptance_path,
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_proof_path,
        ui_linux_exit_gate_path=ui_linux_exit_gate_path,
        ui_windows_exit_gate_path=ui_windows_exit_gate_path,
        ui_workflow_parity_proof_path=ui_workflow_parity_proof_path,
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        sr4_workflow_parity_proof_path=sr4_workflow_parity_proof_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_proof_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_proof_path,
        mobile_local_release_proof_path=mobile_local_release_proof_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
    )

    existing_payload = load_json(out_path)
    if existing_payload and _normalized_payload(existing_payload) == _normalized_payload(payload):
        payload["generated_at"] = str(existing_payload.get("generated_at") or payload["generated_at"]).strip() or payload["generated_at"]

    rendered = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    wrote_out = False
    if out_path.read_text(encoding="utf-8") != rendered if out_path.is_file() else True:
        _write_text(out_path, rendered)
        wrote_out = True

    if mirror_path is not None:
        mirror_content = mirror_path.read_text(encoding="utf-8") if mirror_path.is_file() else ""
        if mirror_content != rendered:
            mirror_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out_path, mirror_path)

    repo_root = repo_root_for_published_path(out_path)
    if repo_root is not None and (wrote_out or _compile_manifest_missing_artifact(repo_root, out_path.name)):
        write_compile_manifest(repo_root)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = materialize_flagship_product_readiness(
        out_path=Path(args.out).resolve(),
        mirror_path=Path(args.mirror_out).resolve() if str(args.mirror_out or "").strip() else None,
        acceptance_path=Path(args.acceptance).resolve(),
        status_plane_path=Path(args.status_plane).resolve(),
        progress_report_path=Path(args.progress_report).resolve(),
        progress_history_path=Path(args.progress_history).resolve(),
        journey_gates_path=Path(args.journey_gates).resolve(),
        support_packets_path=Path(args.support_packets).resolve(),
        supervisor_state_path=Path(args.supervisor_state).resolve(),
        ooda_state_path=Path(args.ooda_state).resolve(),
        ui_local_release_proof_path=Path(args.ui_local_release_proof).resolve(),
        ui_linux_exit_gate_path=Path(args.ui_linux_exit_gate).resolve(),
        ui_windows_exit_gate_path=Path(args.ui_windows_exit_gate).resolve(),
        ui_workflow_parity_proof_path=Path(args.ui_workflow_parity_proof).resolve(),
        ui_executable_exit_gate_path=Path(args.ui_executable_exit_gate).resolve(),
        ui_workflow_execution_gate_path=Path(args.ui_workflow_execution_gate).resolve(),
        ui_visual_familiarity_exit_gate_path=Path(args.ui_visual_familiarity_exit_gate).resolve(),
        sr4_workflow_parity_proof_path=Path(args.sr4_workflow_parity_proof).resolve(),
        sr6_workflow_parity_proof_path=Path(args.sr6_workflow_parity_proof).resolve(),
        sr4_sr6_frontier_receipt_path=Path(args.sr4_sr6_frontier_receipt).resolve(),
        hub_local_release_proof_path=Path(args.hub_local_release_proof).resolve(),
        mobile_local_release_proof_path=Path(args.mobile_local_release_proof).resolve(),
        release_channel_path=Path(args.release_channel).resolve(),
        releases_json_path=Path(args.releases_json).resolve(),
    )
    print(
        "wrote flagship product readiness: "
        f"{Path(args.out).resolve()} ({payload['status']}; ready={payload['summary']['ready_count']}, "
        f"warning={payload['summary']['warning_count']}, missing={payload['summary']['missing_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
