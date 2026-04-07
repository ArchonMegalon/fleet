#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
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
DEFAULT_FLAGSHIP_BAR = ROOT / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_BAR.md"
DEFAULT_HORIZONS_OVERVIEW = ROOT / ".codex-design" / "product" / "HORIZONS.md"
DEFAULT_HORIZONS_DIR = ROOT / ".codex-design" / "product" / "horizons"
CANONICAL_ACCEPTANCE = Path("/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
CANONICAL_FLAGSHIP_BAR = Path("/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_PRODUCT_BAR.md")
CANONICAL_HORIZONS_DIR = Path("/docker/chummercomplete/chummer-design/products/chummer/horizons")
DEFAULT_PARITY_REGISTRY = ROOT / ".codex-design" / "product" / "LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml"
CANONICAL_PARITY_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml"
)
DEFAULT_STATUS_PLANE = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEFAULT_PROGRESS_REPORT = ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY = ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_JOURNEY_GATES = ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
DEFAULT_SUPPORT_PACKETS = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_EXTERNAL_PROOF_RUNBOOK = ROOT / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
DEFAULT_SUPERVISOR_STATE = ROOT / "state" / "chummer_design_supervisor" / "state.json"
DEFAULT_OODA_STATE = ROOT / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"

DEFAULT_UI_LOCAL_RELEASE_PROOF = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json")
DEFAULT_UI_LINUX_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
DEFAULT_UI_WINDOWS_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json")
DEFAULT_UI_WORKFLOW_PARITY_PROOF = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json")
DEFAULT_UI_EXECUTABLE_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json")
DEFAULT_UI_WORKFLOW_EXECUTION_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json")
DEFAULT_UI_VISUAL_FAMILIARITY_EXIT_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json")
DEFAULT_UI_LOCALIZATION_RELEASE_GATE = Path("/docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json")
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
    "Opening_mainframe_preserves_chummer5a_successor_workbench_posture",
    "Runtime_backed_file_menu_preserves_working_open_save_import_routes",
    "Master_index_is_a_first_class_runtime_backed_workbench_route",
    "Character_roster_is_a_first_class_runtime_backed_workbench_route",
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
DESKTOP_VISUAL_FAMILIARITY_HARD_BAR_MILESTONE2_TESTS = (
    "Opening_mainframe_preserves_chummer5a_successor_workbench_posture",
    "Runtime_backed_file_menu_preserves_working_open_save_import_routes",
    "Master_index_is_a_first_class_runtime_backed_workbench_route",
    "Character_roster_is_a_first_class_runtime_backed_workbench_route",
)
DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TEST_VARIANT_GROUPS = (
    ("Opening_mainframe_preserves_chummer5a_successor_workbench_posture",),
    ("Runtime_backed_file_menu_preserves_working_open_save_import_routes",),
    ("Master_index_is_a_first_class_runtime_backed_workbench_route",),
    ("Character_roster_is_a_first_class_runtime_backed_workbench_route",),
    ("Runtime_backed_shell_chrome_stays_enabled_after_runner_load",),
    ("Runtime_backed_codex_tree_preserves_legacy_left_rail_navigation_posture",),
    ("Loaded_runner_header_stays_tab_panel_only_without_metric_cards",),
    ("Character_creation_preserves_familiar_dense_builder_rhythm",),
    ("Advancement_and_karma_journal_workflows_preserve_familiar_progression_rhythm",),
    ("Gear_builder_preserves_familiar_browse_detail_confirm_rhythm",),
    ("Vehicles_and_drones_builder_preserves_familiar_browse_detail_confirm_rhythm",),
    ("Cyberware_and_cyberlimb_builder_preserve_legacy_dialog_familiarity_cues",),
    ("Contacts_diary_and_support_routes_execute_with_public_path_visibility",),
    (
        "Magic_matrix_and_consumables_workflows_execute_with_specific_dialog_fields_and_confirm_actions",
        "Magic_workflows_execute_with_specific_dialog_fields_and_confirm_actions",
        "Matrix_workflows_execute_with_specific_dialog_fields_and_confirm_actions",
    ),
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
    Path("/docker/fleet/repos/chummer-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"),
    Path("/docker/fleet/repos/chummer-media-factory/.codex-studio/published/ARTIFACT_PUBLICATION_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer6-media-factory/.codex-studio/published/MEDIA_LOCAL_RELEASE_PROOF.generated.json"),
    Path("/docker/chummercomplete/chummer6-media-factory/.codex-studio/published/ARTIFACT_PUBLICATION_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/ARTIFACT_PUBLICATION_CERTIFICATION.generated.json"),
    Path("/docker/chummercomplete/chummer.run-services/.codex-studio/published/HUB_CAMPAIGN_OS_LOCAL_PROOF.generated.json"),
)
PARITY_BLOCKING_STATUSES = {"missing", "partial", "warning", "blocked", "fail", "failed"}
PARITY_DESKTOP_FAMILY_IDS = {
    "shell_workbench_orientation",
    "dense_builder_and_career_workflows",
    "identity_contacts_lifestyles_history",
    "sourcebooks_reference_and_master_index",
    "settings_and_rules_environment_authoring",
    "custom_data_xml_and_translator_bridge",
    "dice_initiative_and_table_utilities",
    "roster_dashboards_and_multi_character_ops",
    "sheet_export_print_viewer_and_exchange",
    "sr6_supplements_designers_and_house_rules",
}
PARITY_RULES_AND_IMPORT_FAMILY_IDS = {
    "sourcebooks_reference_and_master_index",
    "settings_and_rules_environment_authoring",
    "custom_data_xml_and_translator_bridge",
    "legacy_and_adjacent_import_oracles",
    "sr6_supplements_designers_and_house_rules",
}


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
    parser.add_argument(
        "--parity-registry",
        default=str(DEFAULT_PARITY_REGISTRY),
        help="path to LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml",
    )
    parser.add_argument("--status-plane", default=str(DEFAULT_STATUS_PLANE), help="path to STATUS_PLANE.generated.yaml")
    parser.add_argument("--progress-report", default=str(DEFAULT_PROGRESS_REPORT), help="path to PROGRESS_REPORT.generated.json")
    parser.add_argument("--progress-history", default=str(DEFAULT_PROGRESS_HISTORY), help="path to PROGRESS_HISTORY.generated.json")
    parser.add_argument("--journey-gates", default=str(DEFAULT_JOURNEY_GATES), help="path to JOURNEY_GATES.generated.json")
    parser.add_argument("--support-packets", default=str(DEFAULT_SUPPORT_PACKETS), help="path to SUPPORT_CASE_PACKETS.generated.json")
    parser.add_argument(
        "--external-proof-runbook",
        default="",
        help=(
            "optional path to EXTERNAL_PROOF_RUNBOOK.generated.md; defaults to the sibling of support packets when omitted"
        ),
    )
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
        "--ui-localization-release-gate",
        default=str(DEFAULT_UI_LOCALIZATION_RELEASE_GATE),
        help="path to UI_LOCALIZATION_RELEASE_GATE.generated.json",
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
    parser.add_argument(
        "--ignore-nonlinux-desktop-host-proof-blockers",
        action="store_true",
        help=(
            "Ignore desktop proof blockers tied to Windows and macOS external-host or tuple expectations; still require Linux proof."
        ),
    )
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


def _format_external_only_completion_reason(external_host_proof_reason: str) -> str:
    prefix = "Only external host-proof gaps remain"
    detail = str(external_host_proof_reason or "").strip()
    if not detail:
        return prefix + "."
    detail = detail.lstrip(":").strip()
    if detail.lower().startswith(prefix.lower()):
        detail = detail[len(prefix) :].lstrip(" :")
    if not detail:
        return prefix + "."
    return f"{prefix}: {detail[0].lower() + detail[1:]}"


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
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def load_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def extract_runbook_field(markdown: str, key: str) -> str:
    if not markdown:
        return ""
    needle = f"- {key}:"
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith(needle):
            return line[len(needle) :].strip().strip("`")
    return ""


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
    is_shard_state = (
        preferred_path.name == "state.json"
        and parent is not None
        and grandparent is not None
        and parent.name.startswith("shard-")
    )
    if is_shard_state:
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
    mode = str(payload.get("mode") or "").strip().lower()
    active_runs = payload.get("active_runs")
    active_runs_count = int(
        payload.get("active_runs_count")
        or (len(active_runs) if isinstance(active_runs, list) else 0)
        or 0
    )
    updated_at = parse_iso(payload.get("updated_at")) or parse_iso((payload.get("active_run") or {}).get("started_at"))
    if mode in {"loop", "sharded", "flagship_product", "complete"} and active_runs_count > 0 and updated_at is not None:
        return "pass"
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


def load_parity_registry_with_fallback(primary_path: Path) -> tuple[Path, Dict[str, Any]]:
    primary_payload = load_yaml(primary_path)
    if primary_payload:
        return primary_path, primary_payload
    if CANONICAL_PARITY_REGISTRY != primary_path and CANONICAL_PARITY_REGISTRY.is_file():
        canonical_payload = load_yaml(CANONICAL_PARITY_REGISTRY)
        if canonical_payload:
            return CANONICAL_PARITY_REGISTRY, canonical_payload
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


def _as_int_list(value: Any) -> List[int]:
    if not isinstance(value, list):
        return []
    results: List[int] = []
    for item in value:
        try:
            results.append(int(item))
        except (TypeError, ValueError):
            continue
    return results


def _path_contract_passed(path: Path, *, expected_contract: str = "") -> bool:
    if not path.is_file():
        return False
    return proof_passed(load_json(path), expected_contract=expected_contract)


def _text_contains_all(path: Path, tokens: Sequence[str]) -> bool:
    if not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return False
    return all(str(token).strip() and str(token) in content for token in tokens)


def _first_existing_path(candidates: Sequence[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _parity_proof_backed_family_closures(
    *,
    ui_workflow_parity_proof_path: Path,
    ui_workflow_execution_gate_path: Path,
    ui_visual_familiarity_exit_gate_path: Path,
    sr4_workflow_parity_proof_path: Path,
    sr6_workflow_parity_proof_path: Path,
    sr4_sr6_frontier_receipt_path: Path,
    hub_local_release_proof: Dict[str, Any],
    mobile_local_release_proof: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    ui_published_dir = ui_workflow_parity_proof_path.parent
    ui_root = ui_published_dir.parent.parent if ui_workflow_parity_proof_path.name else Path("/docker/chummercomplete/chummer6-ui")
    core_root = _first_existing_path(
        (
            Path("/docker/chummercomplete/chummer6-core"),
            Path("/docker/chummercomplete/chummer-core-engine"),
        )
    ) or Path("/docker/chummercomplete/chummer6-core")
    hub_root = _first_existing_path(
        (
            Path("/docker/chummercomplete/chummer6-hub"),
            Path("/docker/chummercomplete/chummer.run-services"),
        )
    ) or Path("/docker/chummercomplete/chummer6-hub")

    dense_sr4_path = ui_published_dir / "SR4_WORKFLOW_FAMILY_DENSE_WORKBENCH_AFFORDANCES_SEARCH_ADD_EDIT_REMOVE_PREVIEW_DRILL_IN_COMPARE_PARITY.generated.json"
    dense_sr6_path = ui_published_dir / "SR6_WORKFLOW_FAMILY_DENSE_WORKBENCH_AFFORDANCES_SEARCH_ADD_EDIT_REMOVE_PREVIEW_DRILL_IN_COMPARE_PARITY.generated.json"
    contacts_sr4_path = ui_published_dir / "SR4_WORKFLOW_FAMILY_QUALITIES_CONTACTS_IDENTITIES_NOTES_CALENDAR_EXPENSES_LIFESTYLES_SOURCES_PARITY.generated.json"
    contacts_sr6_path = ui_published_dir / "SR6_WORKFLOW_FAMILY_QUALITIES_CONTACTS_IDENTITIES_NOTES_CALENDAR_EXPENSES_LIFESTYLES_SOURCES_PARITY.generated.json"
    export_sr4_path = ui_published_dir / "SR4_WORKFLOW_FAMILY_CREATE_OPEN_IMPORT_SAVE_SAVE_AS_PRINT_EXPORT_PARITY.generated.json"
    export_sr6_path = ui_published_dir / "SR6_WORKFLOW_FAMILY_CREATE_OPEN_IMPORT_SAVE_SAVE_AS_PRINT_EXPORT_PARITY.generated.json"

    core_api_tests_path = core_root / "Chummer.Tests" / "ApiIntegrationTests.cs"
    core_xml_tool_catalog_path = core_root / "Chummer.Infrastructure" / "Xml" / "XmlToolCatalogService.cs"
    build_lab_projection_path = core_root / "Chummer.Application" / "BuildLab" / "BuildLabWorkspaceProjectionFactory.cs"

    ui_dialog_factory_tests_path = ui_root / "Chummer.Tests" / "Presentation" / "DesktopDialogFactoryTests.cs"
    ui_presenter_tests_path = ui_root / "Chummer.Tests" / "Presentation" / "CharacterOverviewPresenterTests.cs"
    ui_audit_parity_path = ui_root / "scripts" / "audit-ui-parity.sh"
    hub_workflow_surface_contracts_path = hub_root / "Chummer.Run.Contracts" / "CompatCore" / "Presentation" / "WorkflowSurfaceContracts.cs"

    closures: Dict[str, Dict[str, Any]] = {}

    def add_closure(family_id: str, *, reason: str, receipts: Sequence[str]) -> None:
        closures[family_id] = {
            "id": family_id,
            "closure_strategy": "proof_backed_successor_route",
            "effective_status": "covered",
            "reason": reason,
            "receipts": [str(item).strip() for item in receipts if str(item).strip()],
        }

    if all(
        (
            _path_contract_passed(
                ui_visual_familiarity_exit_gate_path,
                expected_contract="chummer6-ui.desktop_visual_familiarity_exit_gate",
            ),
            _path_contract_passed(
                ui_workflow_execution_gate_path,
                expected_contract="chummer6-ui.desktop_workflow_execution_gate",
            ),
            _path_contract_passed(
                ui_workflow_parity_proof_path,
                expected_contract="chummer6-ui.chummer5a_desktop_workflow_parity",
            ),
            _path_contract_passed(
                sr4_workflow_parity_proof_path,
                expected_contract="chummer6-ui.sr4_desktop_workflow_parity",
            ),
            _path_contract_passed(
                sr6_workflow_parity_proof_path,
                expected_contract="chummer6-ui.sr6_desktop_workflow_parity",
            ),
            _path_contract_passed(
                sr4_sr6_frontier_receipt_path,
                expected_contract="chummer6-ui.sr4_sr6_desktop_parity_frontier",
            ),
        )
    ):
        add_closure(
            "shell_workbench_orientation",
            reason="Promoted desktop chrome, visual familiarity, and cross-ruleset workflow parity are all passing.",
            receipts=(
                str(ui_visual_familiarity_exit_gate_path),
                str(ui_workflow_execution_gate_path),
                str(ui_workflow_parity_proof_path),
                str(sr4_workflow_parity_proof_path),
                str(sr6_workflow_parity_proof_path),
                str(sr4_sr6_frontier_receipt_path),
            ),
        )

    if all(
        (
            _path_contract_passed(dense_sr4_path, expected_contract="chummer6-ui.ruleset_workflow_family_parity"),
            _path_contract_passed(dense_sr6_path, expected_contract="chummer6-ui.ruleset_workflow_family_parity"),
            _path_contract_passed(
                ui_workflow_execution_gate_path,
                expected_contract="chummer6-ui.desktop_workflow_execution_gate",
            ),
        )
    ):
        add_closure(
            "dense_builder_and_career_workflows",
            reason="Dense workbench workflow-family parity is passing on both SR4 and SR6 heads with promoted desktop execution proof.",
            receipts=(str(dense_sr4_path), str(dense_sr6_path), str(ui_workflow_execution_gate_path)),
        )

    if all(
        (
            _path_contract_passed(contacts_sr4_path, expected_contract="chummer6-ui.ruleset_workflow_family_parity"),
            _path_contract_passed(contacts_sr6_path, expected_contract="chummer6-ui.ruleset_workflow_family_parity"),
        )
    ):
        add_closure(
            "identity_contacts_lifestyles_history",
            reason="Contacts, identities, notes, lifestyles, and source-family workflow parity is passing across SR4 and SR6.",
            receipts=(str(contacts_sr4_path), str(contacts_sr6_path)),
        )

    if all(
        (
            _text_contains_all(
                core_xml_tool_catalog_path,
                ("BuildReferenceLaneReceipt", "BuildReferenceSourceLaneReceipt", "BuildSourceSelectionLaneReceipt"),
            ),
            _text_contains_all(
                core_api_tests_path,
                ('response["referenceSourceLaneReceipt"]', 'response["sourceSelectionLaneReceipt"]'),
            ),
            _text_contains_all(
                ui_dialog_factory_tests_path,
                ("CreateCommandDialog_master_index_surfaces_sourcebook_and_parity_posture", "dialog.master_index"),
            ),
        )
    ):
        add_closure(
            "sourcebooks_reference_and_master_index",
            reason="Master-index sourcebook, reference-source, and source-selection successor lanes are explicit in core and surfaced on the flagship desktop dialog.",
            receipts=(
                f"{core_xml_tool_catalog_path}::BuildReferenceLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildReferenceSourceLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildSourceSelectionLaneReceipt",
                f"{core_api_tests_path}::referenceSourceLaneReceipt",
                f"{core_api_tests_path}::sourceSelectionLaneReceipt",
                f"{ui_dialog_factory_tests_path}::CreateCommandDialog_master_index_surfaces_sourcebook_and_parity_posture",
            ),
        )

    if all(
        (
            _text_contains_all(
                core_xml_tool_catalog_path,
                ("BuildSettingsLaneReceipt", "BuildSourceToggleLaneReceipt", "BuildSourceSelectionLaneReceipt"),
            ),
            _text_contains_all(
                core_api_tests_path,
                ('response["settingsLaneReceipt"]', 'response["sourceToggleLaneReceipt"]', 'response["sourceSelectionLaneReceipt"]'),
            ),
            _text_contains_all(
                ui_dialog_factory_tests_path,
                ("CreateCommandDialog_character_settings_surfaces_rules_environment_posture",),
            ),
        )
    ):
        add_closure(
            "settings_and_rules_environment_authoring",
            reason="Settings, source-toggle, and rules-environment successor lanes are explicit in core receipts and surfaced through the flagship character-settings dialog.",
            receipts=(
                f"{core_xml_tool_catalog_path}::BuildSettingsLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildSourceToggleLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildSourceSelectionLaneReceipt",
                f"{core_api_tests_path}::settingsLaneReceipt",
                f"{core_api_tests_path}::sourceToggleLaneReceipt",
                f"{ui_dialog_factory_tests_path}::CreateCommandDialog_character_settings_surfaces_rules_environment_posture",
            ),
        )

    if all(
        (
            _text_contains_all(
                core_xml_tool_catalog_path,
                ("BuildCustomDataLaneReceipt", "BuildCustomDataAuthoringLaneReceipt", "BuildXmlBridgeLaneReceipt", "BuildTranslatorLaneReceipt"),
            ),
            _text_contains_all(
                core_api_tests_path,
                ('response["customDataLaneReceipt"]', 'response["customDataAuthoringLaneReceipt"]', 'response["xmlBridgeLaneReceipt"]', 'response["translatorLaneReceipt"]'),
            ),
            _text_contains_all(
                ui_dialog_factory_tests_path,
                ("CreateCommandDialog_translator_prefers_catalog_languages_and_surfaces_lane_posture", "CreateCommandDialog_translator_lists_locked_shipping_locales"),
            ),
        )
    ):
        add_closure(
            "custom_data_xml_and_translator_bridge",
            reason="Custom-data, XML bridge, and translator successor lanes are explicit in core receipts and surfaced through the flagship translator dialog.",
            receipts=(
                f"{core_xml_tool_catalog_path}::BuildCustomDataLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildCustomDataAuthoringLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildXmlBridgeLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildTranslatorLaneReceipt",
                f"{core_api_tests_path}::customDataLaneReceipt",
                f"{core_api_tests_path}::customDataAuthoringLaneReceipt",
                f"{core_api_tests_path}::xmlBridgeLaneReceipt",
                f"{core_api_tests_path}::translatorLaneReceipt",
                f"{ui_dialog_factory_tests_path}::CreateCommandDialog_translator_prefers_catalog_languages_and_surfaces_lane_posture",
            ),
        )

    if all(
        (
            _text_contains_all(
                ui_audit_parity_path,
                ('"dice_roller": ["diceThreshold", "diceUtilityLane", "initiativePreview"]', 'workflow catalog surface does not expose dice_roller on catalog.tool.dice'),
            ),
            _text_contains_all(
                ui_dialog_factory_tests_path,
                ("CreateCommandDialog_dice_roller_surfaces_initiative_preview_and_roster_context",),
            ),
            _text_contains_all(
                ui_presenter_tests_path,
                ("ExecuteCommandAsync_dice_roller_opens_utility_lane_with_roster_context",),
            ),
        )
    ):
        add_closure(
            "dice_initiative_and_table_utilities",
            reason="Dice and initiative utility lanes are explicit in the shared audit contract and exercised through flagship desktop dialog and presenter tests.",
            receipts=(
                f"{ui_audit_parity_path}::dice_roller",
                f"{ui_dialog_factory_tests_path}::CreateCommandDialog_dice_roller_surfaces_initiative_preview_and_roster_context",
                f"{ui_presenter_tests_path}::ExecuteCommandAsync_dice_roller_opens_utility_lane_with_roster_context",
            ),
        )

    if all(
        (
            _text_contains_all(
                ui_audit_parity_path,
                ('"character_roster": ["rosterOpenCount", "rosterOpsLane", "rosterEntries"]',),
            ),
            _text_contains_all(
                ui_dialog_factory_tests_path,
                ("CreateCommandDialog_character_roster_summarizes_open_workspaces",),
            ),
            _text_contains_all(
                ui_presenter_tests_path,
                ("ExecuteCommandAsync_character_roster_opens_dialog_with_workspace_summary",),
            ),
            _text_contains_all(
                hub_workflow_surface_contracts_path,
                ('public const string Dashboard = "dashboard";', 'public const string SessionDashboard = "session-dashboard";'),
            ),
            proof_passed(hub_local_release_proof, expected_contract="chummer6-hub.local_release_proof"),
        )
    ):
        add_closure(
            "roster_dashboards_and_multi_character_ops",
            reason="Roster/operator lanes are explicit in the flagship desktop shell and Hub workflow-surface contracts, with hub local release proof current.",
            receipts=(
                f"{ui_audit_parity_path}::character_roster",
                f"{ui_dialog_factory_tests_path}::CreateCommandDialog_character_roster_summarizes_open_workspaces",
                f"{ui_presenter_tests_path}::ExecuteCommandAsync_character_roster_opens_dialog_with_workspace_summary",
                f"{hub_workflow_surface_contracts_path}::dashboard",
                "chummer6-hub.local_release_proof",
            ),
        )

    if all(
        (
            _text_contains_all(
                build_lab_projection_path,
                ('WorkflowId: "workflow.exchange.foundry"', 'WorkflowId: "workflow.exchange.json"', 'WorkflowId: "workflow.viewer.sheet"', 'WorkflowId: "workflow.export.pdf"'),
            ),
            _path_contract_passed(export_sr4_path, expected_contract="chummer6-ui.ruleset_workflow_family_parity"),
            _path_contract_passed(export_sr6_path, expected_contract="chummer6-ui.ruleset_workflow_family_parity"),
        )
    ):
        add_closure(
            "sheet_export_print_viewer_and_exchange",
            reason="Build Lab now projects explicit sheet-viewer, PDF, JSON, and Foundry exchange lanes, and print/export workflow parity is passing on SR4 and SR6.",
            receipts=(
                f"{build_lab_projection_path}::workflow.exchange.foundry",
                f"{build_lab_projection_path}::workflow.exchange.json",
                f"{build_lab_projection_path}::workflow.viewer.sheet",
                f"{build_lab_projection_path}::workflow.export.pdf",
                str(export_sr4_path),
                str(export_sr6_path),
            ),
        )

    if all(
        (
            _text_contains_all(
                core_xml_tool_catalog_path,
                ("BuildImportOracleLaneReceipt", "BuildAdjacentSr6OracleLaneReceipt", "BuildSr6SuccessorLaneReceipt"),
            ),
            _text_contains_all(
                core_api_tests_path,
                ('response["importOracleLaneReceipt"]', 'response["adjacentSr6OracleLaneReceipt"]', 'response["sr6SuccessorLaneReceipt"]'),
            ),
            _text_contains_all(
                ui_dialog_factory_tests_path,
                ("CreateCommandDialog_master_index_surfaces_sourcebook_and_parity_posture",),
            ),
        )
    ):
        add_closure(
            "legacy_and_adjacent_import_oracles",
            reason="Core import-oracle and adjacent-SR6 successor receipts are explicit and surfaced through the flagship master-index dialog.",
            receipts=(
                f"{core_xml_tool_catalog_path}::BuildImportOracleLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildAdjacentSr6OracleLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildSr6SuccessorLaneReceipt",
                f"{core_api_tests_path}::importOracleLaneReceipt",
                f"{core_api_tests_path}::adjacentSr6OracleLaneReceipt",
                f"{core_api_tests_path}::sr6SuccessorLaneReceipt",
                f"{ui_dialog_factory_tests_path}::CreateCommandDialog_master_index_surfaces_sourcebook_and_parity_posture",
            ),
        )

    if all(
        (
            _text_contains_all(
                core_xml_tool_catalog_path,
                ("ResolveSr6SupplementLanePosture", "BuildSr6SuccessorLaneReceipt", "BuildOnlineStorageSummary", "BuildOnlineStorageLaneReceipt"),
            ),
            _text_contains_all(
                core_api_tests_path,
                ('response["sr6SuccessorLaneReceipt"]', 'response["onlineStorageLaneReceipt"]'),
            ),
            proof_passed(hub_local_release_proof, expected_contract="chummer6-hub.local_release_proof"),
            proof_passed(mobile_local_release_proof, expected_contract="chummer6-mobile.local_release_proof"),
        )
    ):
        add_closure(
            "sr6_supplements_designers_and_house_rules",
            reason="SR6 supplement, designer-family, house-rule, and online-storage successor receipts are explicit in core and backed by current hub/mobile release proof.",
            receipts=(
                f"{core_xml_tool_catalog_path}::ResolveSr6SupplementLanePosture",
                f"{core_xml_tool_catalog_path}::BuildSr6SuccessorLaneReceipt",
                f"{core_xml_tool_catalog_path}::BuildOnlineStorageSummary",
                f"{core_xml_tool_catalog_path}::BuildOnlineStorageLaneReceipt",
                f"{core_api_tests_path}::sr6SuccessorLaneReceipt",
                f"{core_api_tests_path}::onlineStorageLaneReceipt",
                "chummer6-hub.local_release_proof",
                "chummer6-mobile.local_release_proof",
            ),
        )

    return closures


def _parity_unresolved_families(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    unresolved: List[Dict[str, Any]] = []
    for row in payload.get("families") or []:
        if not isinstance(row, dict):
            continue
        family_id = str(row.get("id") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        if not family_id or status not in PARITY_BLOCKING_STATUSES:
            continue
        unresolved.append(
            {
                "id": family_id,
                "status": status,
                "sources": _as_string_list(row.get("sources")),
                "legacy_signals": _as_string_list(row.get("legacy_signals")),
                "current_design_equivalents": _as_string_list(row.get("current_design_equivalents")),
                "milestone_ids": _as_int_list(row.get("milestone_ids")),
            }
        )
    unresolved.sort(key=lambda item: str(item.get("id") or ""))
    return unresolved


def _parity_effective_status(
    *,
    declared_blocking_families: Sequence[Dict[str, Any]],
    proof_backed_closures: Dict[str, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    unresolved: List[Dict[str, Any]] = []
    proof_closed: List[Dict[str, Any]] = []
    for row in declared_blocking_families:
        family = dict(row)
        family_id = str(family.get("id") or "").strip()
        family["registry_status"] = str(family.get("status") or "").strip().lower()
        closure = dict(proof_backed_closures.get(family_id) or {})
        if closure:
            family["effective_status"] = str(closure.get("effective_status") or "covered").strip().lower()
            family["closure_strategy"] = str(closure.get("closure_strategy") or "proof_backed_successor_route").strip()
            family["closure_reason"] = str(closure.get("reason") or "").strip()
            family["closure_receipts"] = [str(item).strip() for item in (closure.get("receipts") or []) if str(item).strip()]
            proof_closed.append(family)
            continue
        family["effective_status"] = family["registry_status"]
        unresolved.append(family)
    return unresolved, proof_closed


def _milestone2_visual_requirement_satisfied(required_tests: set[str], group: tuple[str, ...]) -> bool:
    canonical, *split_variants = group
    if canonical in required_tests:
        return True
    if not split_variants:
        return False
    return all(variant in required_tests for variant in split_variants)


def _milestone2_visual_requirement_reported_missing(
    required_tests: set[str],
    missing_tests: set[str],
    group: tuple[str, ...],
) -> bool:
    canonical, *split_variants = group
    if canonical in missing_tests:
        return True
    if not split_variants:
        return False
    if canonical in required_tests:
        return False
    return any(variant in missing_tests for variant in split_variants)


def _normalize_platform_hint(value: str) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return ""
    if ":" in token:
        mapped = _normalize_platform_hint(token.rsplit(":", 1)[-1])
        if mapped:
            return mapped
    for part in re.split(r"[^a-z0-9]+", token):
        if not part:
            continue
        if part in {"linux", "ubuntu", "debian", "arch", "fedora", "opensuse"}:
            return "linux"
        if part in {"macos", "osx", "darwin"} or part.startswith("mac"):
            return "macos"
        if part in {"windows", "win"} or part.startswith("win"):
            return "windows"
    return ""


def _reason_targets_ignored_desktop_host_platform(reason: str) -> bool:
    normalized = str(reason or "").strip().lower()
    if not normalized:
        return False
    if "windows" in normalized:
        return True
    if "macos" in normalized or "osx" in normalized or "darwin" in normalized:
        return True
    if "win-" in normalized or "hdiutil" in normalized:
        return True
    return False


def _external_request_platform(request: Dict[str, Any]) -> str:
    if not isinstance(request, dict):
        return ""
    platform = _normalize_platform_hint(str(request.get("tuple_id") or request.get("tupleId") or ""))
    if platform:
        return platform
    return _normalize_platform_hint(str(request.get("required_host") or request.get("requiredHost") or ""))


def _filter_external_proof_requests(
    requests: Sequence[Dict[str, Any]],
    *,
    ignore_nonlinux_platform_host_blockers: bool,
) -> List[Dict[str, Any]]:
    if not ignore_nonlinux_platform_host_blockers:
        return list(requests)
    return [
        request
        for request in requests
        if _external_request_platform(request) not in {"windows", "macos"}
    ]


def _external_proof_request_identity(request: Dict[str, Any]) -> str:
    if not isinstance(request, dict):
        return ""
    tuple_id = str(request.get("tuple_id") or request.get("tupleId") or "").strip().lower()
    if tuple_id:
        return f"tuple:{tuple_id}"
    head = str(request.get("head_id") or request.get("headId") or "").strip().lower()
    rid = str(request.get("rid") or "").strip().lower()
    platform = str(request.get("platform") or "").strip().lower()
    host = str(request.get("required_host") or request.get("requiredHost") or "").strip().lower()
    installer = str(
        request.get("expected_installer_relative_path")
        or request.get("expectedInstallerRelativePath")
        or request.get("expected_installer_bundle_relative_path")
        or request.get("expectedInstallerBundleRelativePath")
        or ""
    ).strip().lower()
    receipt = str(
        request.get("expected_startup_smoke_receipt_path")
        or request.get("expectedStartupSmokeReceiptPath")
        or ""
    ).strip().lower()
    if any([head, rid, platform, host, installer, receipt]):
        return "|".join(
            [
                "fallback",
                head,
                rid,
                platform,
                host,
                installer,
                receipt,
            ]
        )
    return json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _dedupe_external_proof_requests(
    requests: Sequence[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], int]:
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for request in requests:
        identity = _external_proof_request_identity(request)
        if not identity:
            deduped.append(dict(request))
            continue
        if identity in seen:
            duplicate_count += 1
            continue
        seen.add(identity)
        deduped.append(dict(request))
    return deduped, duplicate_count


def _has_relevant_external_blockers(
    external_blockers: Sequence[str],
    *,
    external_proof_requests: Sequence[Dict[str, Any]],
    filtered_external_proof_requests: Sequence[Dict[str, Any]],
    ignore_nonlinux_platform_host_blockers: bool,
) -> bool:
    if not external_blockers:
        return False
    if not ignore_nonlinux_platform_host_blockers:
        return True
    if external_proof_requests:
        return bool(filtered_external_proof_requests)
    return True


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


def _status_or_bool_ok(value: Any) -> bool:
    return str(value or "").strip().lower() in {"pass", "passed", "ready", "true", "yes", "1"}


def _normalized_stale_receipt_inventory(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: List[Dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in value:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "").strip()
        tuple_key = str(row.get("tuple") or "").strip().lower()
        status = str(row.get("status") or "").strip().lower()
        if not (path and tuple_key and status):
            continue
        dedupe_key = (path, tuple_key, status)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "path": path,
                "tuple": tuple_key,
                "status": status,
            }
        )
    return sorted(normalized, key=lambda item: (item["tuple"], item["status"], item["path"]))


def _derive_stale_passing_platform_receipt_tokens(
    *,
    platform: str,
    stale_inventory: List[Dict[str, str]],
) -> List[str]:
    passing_statuses = {"pass", "passed", "ready"}
    tokens = [
        f"{platform}:{row['tuple']}"
        for row in stale_inventory
        if str(row.get("status") or "").strip().lower() in passing_statuses
        and str(row.get("tuple") or "").strip()
    ]
    return sorted(set(tokens))


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
    parity_registry_path: Path,
    status_plane_path: Path,
    progress_report_path: Path,
    progress_history_path: Path,
    journey_gates_path: Path,
    support_packets_path: Path,
    external_proof_runbook_path: Path | None,
    supervisor_state_path: Path,
    ooda_state_path: Path,
    ui_local_release_proof_path: Path,
    ui_linux_exit_gate_path: Path,
    ui_windows_exit_gate_path: Path,
    ui_workflow_parity_proof_path: Path,
    ui_executable_exit_gate_path: Path,
    ui_workflow_execution_gate_path: Path,
    ui_visual_familiarity_exit_gate_path: Path,
    ui_localization_release_gate_path: Path,
    sr4_workflow_parity_proof_path: Path,
    sr6_workflow_parity_proof_path: Path,
    sr4_sr6_frontier_receipt_path: Path,
    hub_local_release_proof_path: Path,
    mobile_local_release_proof_path: Path,
    release_channel_path: Path,
    releases_json_path: Path,
    ignore_nonlinux_desktop_host_proof_blockers: bool = False,
) -> Dict[str, Any]:
    effective_acceptance_path, acceptance = load_acceptance_with_fallback(acceptance_path)
    effective_parity_registry_path, parity_registry = load_parity_registry_with_fallback(parity_registry_path)
    status_plane = load_yaml(status_plane_path)
    progress_report = load_json(progress_report_path)
    progress_history = load_json(progress_history_path)
    journey_gates = load_json(journey_gates_path)
    support_packets = load_json(support_packets_path)
    effective_external_proof_runbook_path = (
        external_proof_runbook_path if external_proof_runbook_path is not None else support_packets_path.parent / DEFAULT_EXTERNAL_PROOF_RUNBOOK.name
    )
    external_proof_runbook = load_text(effective_external_proof_runbook_path)
    runbook_generated_at = extract_runbook_field(external_proof_runbook, "generated_at")
    runbook_plan_generated_at = extract_runbook_field(external_proof_runbook, "plan_generated_at")
    runbook_release_generated_at = extract_runbook_field(external_proof_runbook, "release_channel_generated_at")
    effective_supervisor_state_path, supervisor_state = _select_best_supervisor_state(supervisor_state_path)
    ooda_state = load_json(ooda_state_path)
    ui_local_release_proof = load_json(ui_local_release_proof_path)
    ui_linux_exit_gate = load_json(ui_linux_exit_gate_path)
    ui_windows_exit_gate = load_json(ui_windows_exit_gate_path)
    ui_workflow_parity_proof = load_json(ui_workflow_parity_proof_path)
    ui_executable_exit_gate = load_json(ui_executable_exit_gate_path)
    ui_workflow_execution_gate = load_json(ui_workflow_execution_gate_path)
    ui_visual_familiarity_exit_gate = load_json(ui_visual_familiarity_exit_gate_path)
    ui_localization_release_gate = load_json(ui_localization_release_gate_path)
    sr4_workflow_parity_proof = load_json(sr4_workflow_parity_proof_path)
    sr6_workflow_parity_proof = load_json(sr6_workflow_parity_proof_path)
    sr4_sr6_frontier_receipt = load_json(sr4_sr6_frontier_receipt_path)
    hub_local_release_proof = load_json(hub_local_release_proof_path)
    mobile_local_release_proof = load_json(mobile_local_release_proof_path)
    release_channel = load_json(release_channel_path)
    releases_json = load_json(releases_json_path)
    rules_cert_path, rules_cert_payload = _first_existing_payload(RULES_CERTIFICATION_CANDIDATES)
    media_proof_path, media_proof_payload = _first_existing_payload(MEDIA_PROOF_CANDIDATES)
    parity_declared_blocking_families = _parity_unresolved_families(parity_registry)
    parity_proof_backed_closures = _parity_proof_backed_family_closures(
        ui_workflow_parity_proof_path=ui_workflow_parity_proof_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        sr4_workflow_parity_proof_path=sr4_workflow_parity_proof_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_proof_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof=hub_local_release_proof,
        mobile_local_release_proof=mobile_local_release_proof,
    )
    parity_unresolved_families, parity_proof_closed_families = _parity_effective_status(
        declared_blocking_families=parity_declared_blocking_families,
        proof_backed_closures=parity_proof_backed_closures,
    )
    parity_excluded_scope = _as_string_list(((parity_registry.get("scope") or {}).get("excluded")))
    parity_desktop_families = [
        row for row in parity_unresolved_families if str(row.get("id") or "") in PARITY_DESKTOP_FAMILY_IDS
    ]
    parity_rules_families = [
        row for row in parity_unresolved_families if str(row.get("id") or "") in PARITY_RULES_AND_IMPORT_FAMILY_IDS
    ]

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
        executable_gate_raw_reasons = [
            str(item).strip()
            for item in (ui_executable_exit_gate.get("reasons") or [])
            if str(item).strip()
        ]
        executable_gate_reasons = list(executable_gate_raw_reasons)
        if ignore_nonlinux_desktop_host_proof_blockers:
            executable_gate_reasons = [
                reason
                for reason in executable_gate_reasons
                if not _reason_targets_ignored_desktop_host_platform(reason)
            ]
        ignored_only_executable_gate = bool(ignore_nonlinux_desktop_host_proof_blockers) and bool(
            [
                reason
                for reason in executable_gate_raw_reasons
                if _reason_targets_ignored_desktop_host_platform(reason)
            ]
        ) and (
            not executable_gate_reasons
            or all(
                reason == "Release channel status cannot be publishable while required desktop tuple coverage is incomplete."
                for reason in executable_gate_reasons
            )
        )
        if ignored_only_executable_gate and proof_passed(
            ui_linux_exit_gate,
            expected_contract="chummer6-ui.linux_desktop_exit_gate",
        ):
            desktop_reasons.append(
                "Executable desktop exit gate remains globally failed only because ignored macOS/Windows host-proof tuples are still absent; Linux desktop proof is already present."
            )
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Executable desktop exit gate proof is missing or not passed. Desktop shell/install/support liveliness must be proven from shipped artifacts."
            )
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
        visual_failing_legacy_interaction_keys = _as_string_list(
            visual_evidence.get("failing_required_legacy_interaction_keys")
        )
        visual_missing_desktop_landmark_keys = sorted(
            set(visual_missing_legacy_interaction_keys).union(set(visual_failing_legacy_interaction_keys)).intersection(
                {
                    "runtimeBackedFileMenuRoutes",
                    "runtimeBackedMasterIndex",
                    "runtimeBackedCharacterRoster",
                    "legacyMainframeVisualSimilarity",
                }
            )
        )
        visual_landmark_statuses = {
            key: str(visual_evidence.get(key) or "").strip().lower()
            for key in (
                "runtimeBackedFileMenuRoutes",
                "runtimeBackedMasterIndex",
                "runtimeBackedCharacterRoster",
                "legacyMainframeVisualSimilarity",
            )
        }
        visual_nonpassing_desktop_landmark_keys = sorted(
            key for key, value in visual_landmark_statuses.items()
            if not _status_or_bool_ok(value)
        )
        visual_required_tests_set = set(visual_required_tests)
        visual_missing_tests_set = set(visual_missing_tests)
        visual_missing_required_milestone2_tests_from_inventory: List[str] = []
        if visual_required_tests_set:
            visual_missing_required_milestone2_tests_from_inventory = sorted(
                group[0]
                for group in DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TEST_VARIANT_GROUPS
                if not _milestone2_visual_requirement_satisfied(visual_required_tests_set, group)
            )
        visual_reported_missing_milestone2_tests = sorted(
            group[0]
            for group in DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TEST_VARIANT_GROUPS
            if _milestone2_visual_requirement_reported_missing(
                visual_required_tests_set,
                visual_missing_tests_set,
                group,
            )
        )
        visual_hard_bar_missing_tests = sorted(
            set(DESKTOP_VISUAL_FAMILIARITY_HARD_BAR_MILESTONE2_TESTS).intersection(
                set(visual_reported_missing_milestone2_tests)
            )
        )
        visual_milestone2_integrity_gap = False
        if visual_hard_bar_missing_tests:
            visual_milestone2_integrity_gap = True
            desktop_hard_fail = True
            desktop_reasons.append(
                "Desktop visual familiarity hard-bar failed on flagship anchors: "
                + ", ".join(visual_hard_bar_missing_tests)
                + "."
            )
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
        if visual_failing_legacy_interaction_keys:
            visual_milestone2_integrity_gap = True
            desktop_hard_fail = True
            desktop_reasons.append(
                "Desktop visual familiarity gate reports non-passing required legacy interaction proof keys."
            )
        if visual_missing_desktop_landmark_keys:
            visual_milestone2_integrity_gap = True
            desktop_hard_fail = True
            desktop_reasons.append(
                "Desktop visual familiarity gate is missing required Chummer5a desktop landmark proof keys: "
                + ", ".join(visual_missing_desktop_landmark_keys)
            )
        if visual_nonpassing_desktop_landmark_keys:
            visual_milestone2_integrity_gap = True
            desktop_hard_fail = True
            desktop_reasons.append(
                "Desktop visual familiarity gate does not currently pass the required Chummer5a desktop landmark proof keys: "
                + ", ".join(visual_nonpassing_desktop_landmark_keys)
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
        visual_required_tests_set = set(visual_required_tests)
        visual_missing_tests_set = set(visual_missing_tests)
        visual_missing_required_milestone2_tests_from_inventory = []
        if visual_required_tests_set:
            visual_missing_required_milestone2_tests_from_inventory = sorted(
                group[0]
                for group in DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TEST_VARIANT_GROUPS
                if not _milestone2_visual_requirement_satisfied(visual_required_tests_set, group)
            )
        visual_reported_missing_milestone2_tests = sorted(
            group[0]
            for group in DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TEST_VARIANT_GROUPS
            if _milestone2_visual_requirement_reported_missing(
                visual_required_tests_set,
                visual_missing_tests_set,
                group,
            )
        )
        visual_missing_legacy_interaction_keys = _as_string_list(
            visual_evidence.get("missing_required_legacy_interaction_keys")
        )
        visual_missing_desktop_landmark_keys = sorted(
            set(visual_missing_legacy_interaction_keys).intersection(
                {
                    "runtimeBackedFileMenuRoutes",
                    "runtimeBackedMasterIndex",
                    "runtimeBackedCharacterRoster",
                    "legacyMainframeVisualSimilarity",
                }
            )
        )
    localization_locale_summary = (
        ui_localization_release_gate.get("locale_summary")
        if isinstance(ui_localization_release_gate.get("locale_summary"), list)
        else (
            ui_localization_release_gate.get("localeSummary")
            if isinstance(ui_localization_release_gate.get("localeSummary"), list)
            else []
        )
    )
    localization_shipping_locales = sorted(
        {
            locale.strip().lower()
            for locale in _as_string_list(
                ui_localization_release_gate.get("shipping_locales")
                if isinstance(ui_localization_release_gate.get("shipping_locales"), list)
                else ui_localization_release_gate.get("shippingLocales")
            )
            if locale.strip()
        }
    )
    localization_translation_backlog_findings = _as_string_list(
        ui_localization_release_gate.get("translation_backlog_findings")
        if isinstance(ui_localization_release_gate.get("translation_backlog_findings"), list)
        else ui_localization_release_gate.get("translationBacklogFindings")
    )
    localization_untranslated_counts_by_locale: Dict[str, int] = {}
    localization_locale_summary_locales: set[str] = set()
    for locale_entry in localization_locale_summary:
        if not isinstance(locale_entry, dict):
            continue
        locale = str(locale_entry.get("locale") or "").strip().lower()
        if not locale:
            continue
        localization_locale_summary_locales.add(locale)
        try:
            untranslated_count = int(
                locale_entry.get("untranslated_key_count")
                if locale_entry.get("untranslated_key_count") is not None
                else locale_entry.get("untranslatedKeyCount")
            )
        except (TypeError, ValueError):
            continue
        if untranslated_count > 0:
            localization_untranslated_counts_by_locale[locale] = untranslated_count
    localization_missing_locale_summary_shipping_locales = sorted(
        locale for locale in localization_shipping_locales if locale not in localization_locale_summary_locales
    )
    if ui_localization_release_gate:
        if proof_passed(
            ui_localization_release_gate,
            expected_contract="chummer6-ui.localization_release_gate",
            accepted_statuses=("passed", "pass", "ready"),
        ):
            if not localization_shipping_locales:
                desktop_hard_fail = True
                desktop_reasons.append(
                    "Localization release gate does not declare shipping locales. Milestone-2 locale coverage cannot be proven."
                )
            elif localization_missing_locale_summary_shipping_locales:
                desktop_hard_fail = True
                desktop_reasons.append(
                    "Localization release gate is missing locale-summary rows for declared shipping locales."
                )
            elif localization_untranslated_counts_by_locale:
                desktop_hard_fail = True
                desktop_reasons.append(
                    "Localization release gate still reports untranslated shipping-locale trust-surface keys."
                )
            else:
                desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Localization release gate proof is missing or not passed. Milestone-2 shipping-locale trust surfaces are not release-ready."
            )
    if proof_passed(ui_linux_exit_gate, expected_contract="chummer6-ui.linux_desktop_exit_gate"):
        desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append("Linux desktop exit gate proof is missing or not passed.")
    if windows_exit_gate_passed(ui_windows_exit_gate):
        desktop_positives += 1
    elif not ignore_nonlinux_desktop_host_proof_blockers:
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
    executable_gate_trusted_local_roots = _as_string_list(executable_gate_evidence.get("trusted_local_roots"))
    executable_gate_hub_registry_root = str(executable_gate_evidence.get("hub_registry_root") or "").strip()
    executable_gate_hub_registry_release_channel_path = str(
        executable_gate_evidence.get("hub_registry_release_channel_path") or ""
    ).strip()
    executable_gate_hub_registry_root_trusted = bool(
        executable_gate_evidence.get("hub_registry_root_trusted_for_startup_smoke_proof")
    )
    executable_gate_has_expanded_trusted_local_roots = len(set(executable_gate_trusted_local_roots)) > 1
    if executable_gate_has_expanded_trusted_local_roots and not executable_gate_hub_registry_root_trusted:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate reports expanded trusted startup-smoke roots without canonical hub-registry release-channel binding."
        )
    if executable_gate_hub_registry_root_trusted and (
        not executable_gate_hub_registry_root or not executable_gate_hub_registry_release_channel_path
    ):
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate marks hub-registry startup-smoke trust as active but omits canonical hub root/channel evidence."
        )
    stale_linux_gate_receipts_without_promoted_tuples = _normalized_stale_receipt_inventory(
        executable_gate_evidence.get("stale_linux_gate_receipts_without_promoted_tuples")
    )
    stale_windows_gate_receipts_without_promoted_tuples = _normalized_stale_receipt_inventory(
        executable_gate_evidence.get("stale_windows_gate_receipts_without_promoted_tuples")
    )
    stale_macos_gate_receipts_without_promoted_tuples = _normalized_stale_receipt_inventory(
        executable_gate_evidence.get("stale_macos_gate_receipts_without_promoted_tuples")
    )
    stale_linux_gate_receipt_tuple_keys_without_promoted_tuples = sorted(
        {
            str(item.get("tuple") or "").strip().lower()
            for item in stale_linux_gate_receipts_without_promoted_tuples
            if str(item.get("tuple") or "").strip()
        }
    )
    stale_windows_gate_receipt_tuple_keys_without_promoted_tuples = sorted(
        {str(item.get("tuple") or "").strip().lower() for item in stale_windows_gate_receipts_without_promoted_tuples if str(item.get("tuple") or "").strip()}
    )
    stale_macos_gate_receipt_tuple_keys_without_promoted_tuples = sorted(
        {str(item.get("tuple") or "").strip().lower() for item in stale_macos_gate_receipts_without_promoted_tuples if str(item.get("tuple") or "").strip()}
    )
    stale_passing_platform_gate_receipts_without_promoted_tuples = _normalized_token_list(
        executable_gate_evidence.get("stale_passing_platform_gate_receipts_without_promoted_tuples")
    )
    stale_passing_platform_gate_receipts_without_promoted_tuples_derived = sorted(
        set(
            _derive_stale_passing_platform_receipt_tokens(
                platform="linux",
                stale_inventory=stale_linux_gate_receipts_without_promoted_tuples,
            )
            +
            _derive_stale_passing_platform_receipt_tokens(
                platform="windows",
                stale_inventory=stale_windows_gate_receipts_without_promoted_tuples,
            )
            + _derive_stale_passing_platform_receipt_tokens(
                platform="macos",
                stale_inventory=stale_macos_gate_receipts_without_promoted_tuples,
            )
        )
    )
    stale_passing_platform_gate_receipts_without_promoted_tuples_mismatch = sorted(
        set(stale_passing_platform_gate_receipts_without_promoted_tuples).symmetric_difference(
            set(stale_passing_platform_gate_receipts_without_promoted_tuples_derived)
        )
    )
    stale_passing_platform_gate_receipts_without_promoted_tuples_effective = sorted(
        set(stale_passing_platform_gate_receipts_without_promoted_tuples).union(
            set(stale_passing_platform_gate_receipts_without_promoted_tuples_derived)
        )
    )
    artifact_heads = sorted({str(item.get("head") or "").strip() for item in release_artifacts if isinstance(item, dict)})
    has_avalonia_public_artifact = any(str(item.get("head") or "").strip() == "avalonia" for item in release_artifacts if isinstance(item, dict))
    promoted_tuple_keys_by_platform: Dict[str, List[str]] = {"linux": [], "windows": [], "macos": []}
    tuple_occurrence_counts_by_platform: Dict[str, Dict[str, int]] = {
        "linux": {},
        "windows": {},
        "macos": {},
    }
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
            tuple_occurrence_counts_by_platform[platform][tuple_key] = (
                int(tuple_occurrence_counts_by_platform[platform].get(tuple_key) or 0) + 1
            )
            if release_channel_id and artifact_channel and artifact_channel != release_channel_id:
                channel_mismatch_keys_by_platform[platform].append(tuple_key)
        else:
            invalid_tuple_metadata_by_platform[platform] = True
    for platform in promoted_tuple_keys_by_platform:
        promoted_tuple_keys_by_platform[platform] = sorted(set(promoted_tuple_keys_by_platform[platform]))
        channel_mismatch_keys_by_platform[platform] = sorted(set(channel_mismatch_keys_by_platform[platform]))
    duplicate_tuple_keys_by_platform: Dict[str, List[str]] = {
        platform: sorted(
            tuple_key
            for tuple_key, count in tuple_occurrence_counts_by_platform[platform].items()
            if int(count or 0) > 1
        )
        for platform in tuple_occurrence_counts_by_platform
    }
    stale_linux_receipt_tuples_overlapping_promoted_tuples = sorted(
        set(stale_linux_gate_receipt_tuple_keys_without_promoted_tuples).intersection(
            set(promoted_tuple_keys_by_platform["linux"])
        )
    )
    stale_windows_receipt_tuples_overlapping_promoted_tuples = sorted(
        set(stale_windows_gate_receipt_tuple_keys_without_promoted_tuples).intersection(
            set(promoted_tuple_keys_by_platform["windows"])
        )
    )
    stale_macos_receipt_tuples_overlapping_promoted_tuples = sorted(
        set(stale_macos_gate_receipt_tuple_keys_without_promoted_tuples).intersection(
            set(promoted_tuple_keys_by_platform["macos"])
        )
    )

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
    tuple_coverage_reported_missing_platforms = _normalized_token_list(
        release_channel_tuple_coverage.get("missingRequiredPlatforms")
    )
    tuple_coverage_reported_missing_heads = _normalized_token_list(
        release_channel_tuple_coverage.get("missingRequiredHeads")
    )
    if ignore_nonlinux_desktop_host_proof_blockers:
        tuple_coverage_reported_missing_platform_head_pairs = sorted(
            {
                token
                for token in tuple_coverage_reported_missing_platform_head_pairs
                if not token.endswith(":windows") and not token.endswith(":macos")
            }
        )
        tuple_coverage_reported_missing_platforms = sorted(
            platform
            for platform in tuple_coverage_reported_missing_platforms
            if platform != "windows" and platform != "macos"
        )
    tuple_coverage_declares_missing_required_platform_head_pairs = (
        "missingRequiredPlatformHeadPairs" in release_channel_tuple_coverage
    )
    tuple_coverage_declares_missing_required_platforms = (
        "missingRequiredPlatforms" in release_channel_tuple_coverage
    )
    tuple_coverage_declares_missing_required_heads = (
        "missingRequiredHeads" in release_channel_tuple_coverage
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
    unpromoted_desktop_shelf_installers = sorted(
        {
            str(item).strip()
            for item in _as_string_list((executable_gate_evidence or {}).get("unpromoted_desktop_shelf_installers"))
            if str(item).strip()
        }
    )
    required_platforms_for_pair_matrix = tuple_coverage_required_platforms or ["linux", "windows", "macos"]
    if ignore_nonlinux_desktop_host_proof_blockers:
        required_platforms_for_pair_matrix = [platform for platform in required_platforms_for_pair_matrix if platform == "linux"]
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
    missing_required_platforms_derived = sorted(
        {
            platform
            for platform in required_platforms_for_pair_matrix
            if not promoted_tuple_keys_by_platform.get(platform)
        }
    )
    missing_required_heads_derived = sorted(
        {
            head
            for head in required_heads_for_pair_matrix
            if head and head not in set(promoted_tuple_heads)
        }
    )
    tuple_coverage_missing_platform_inventory_mismatch = sorted(
        set(tuple_coverage_reported_missing_platforms).symmetric_difference(
            set(missing_required_platforms_derived)
        )
    )
    tuple_coverage_missing_head_inventory_mismatch = sorted(
        set(tuple_coverage_reported_missing_heads).symmetric_difference(
            set(missing_required_heads_derived)
        )
    )
    tuple_coverage_incomplete = bool(
        missing_required_platforms_derived
        or missing_required_heads_derived
        or missing_required_platform_head_pairs
    )
    missing_required_platform_head_pairs_by_platform: Dict[str, List[str]] = {
        "linux": [],
        "windows": [],
        "macos": [],
    }
    for pair in missing_required_platform_head_pairs:
        token = str(pair).strip().lower()
        if ":" not in token:
            continue
        head, platform = token.split(":", 1)
        if not head or platform not in missing_required_platform_head_pairs_by_platform:
            continue
        missing_required_platform_head_pairs_by_platform[platform].append(token)
    for platform in missing_required_platform_head_pairs_by_platform:
        missing_required_platform_head_pairs_by_platform[platform] = sorted(
            set(missing_required_platform_head_pairs_by_platform[platform])
        )
    tuple_coverage_declared = bool(release_channel_tuple_coverage)
    release_channel_rollout_state = str(release_channel.get("rolloutState") or "").strip().lower()
    release_channel_supportability_state = str(release_channel.get("supportabilityState") or "").strip().lower()

    has_linux_public_installer = bool(promoted_tuple_keys_by_platform["linux"])
    has_windows_public_installer = bool(promoted_tuple_keys_by_platform["windows"])
    has_macos_public_installer = bool(promoted_tuple_keys_by_platform["macos"])
    has_any_public_installer = has_linux_public_installer or (
        not ignore_nonlinux_desktop_host_proof_blockers and (has_windows_public_installer or has_macos_public_installer)
    )
    if release_channel_published_and_proven and release_channel_freshness_ok and has_avalonia_public_artifact:
        desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel is not simultaneously published, release-proven, and Avalonia-desktop-backed."
        )
    if not has_linux_public_installer:
        desktop_reasons.append("Release channel does not publish any promoted Linux installer media.")
    if not ignore_nonlinux_desktop_host_proof_blockers and not has_windows_public_installer:
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

    def _tuple_proof_stats(statuses: Dict[str, Any], expected_keys: List[str]) -> tuple[int, int, List[str], List[str]]:
        normalized_statuses = {str(key).strip(): str(value).strip().lower() for key, value in statuses.items()}
        passing_count = sum(1 for key in expected_keys if normalized_statuses.get(key) in {"pass", "passed", "ready"})
        stale_expected = sorted(
            key for key in expected_keys if "stale" in str(normalized_statuses.get(key) or "")
        )
        missing_or_failing = [key for key in expected_keys if normalized_statuses.get(key) not in {"pass", "passed", "ready"}]
        missing_or_failing.extend(
            sorted(
                key
                for key, value in normalized_statuses.items()
                if key not in expected_keys and value not in {"pass", "passed", "ready"}
            )
        )
        return len(expected_keys), passing_count, sorted(set(missing_or_failing)), stale_expected

    linux_tuple_count, linux_passing_status_count, linux_missing_or_failing_keys, linux_stale_promoted_keys = _tuple_proof_stats(
        linux_statuses, promoted_tuple_keys_by_platform["linux"]
    )
    windows_tuple_count, windows_passing_status_count, windows_missing_or_failing_keys, windows_stale_promoted_keys = _tuple_proof_stats(
        windows_statuses, promoted_tuple_keys_by_platform["windows"]
    )
    macos_tuple_count, macos_passing_status_count, macos_missing_or_failing_keys, macos_stale_promoted_keys = _tuple_proof_stats(
        macos_statuses, promoted_tuple_keys_by_platform["macos"]
    )
    linux_missing_or_failing_keys = sorted(
        set(linux_missing_or_failing_keys + missing_required_platform_head_pairs_by_platform["linux"])
    )
    windows_missing_or_failing_keys = sorted(
        set(windows_missing_or_failing_keys + missing_required_platform_head_pairs_by_platform["windows"])
    )
    macos_missing_or_failing_keys = sorted(
        set(macos_missing_or_failing_keys + missing_required_platform_head_pairs_by_platform["macos"])
    )

    if invalid_tuple_metadata_by_platform["linux"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Linux installer media without explicit head/rid tuple metadata."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and invalid_tuple_metadata_by_platform["windows"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Windows installer media without explicit head/rid tuple metadata."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and invalid_tuple_metadata_by_platform["macos"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes macOS installer media without explicit head/rid tuple metadata."
        )
    if channel_mismatch_keys_by_platform["linux"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Linux installer media with artifact channel metadata that does not match top-level channelId."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and channel_mismatch_keys_by_platform["windows"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes Windows installer media with artifact channel metadata that does not match top-level channelId."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and channel_mismatch_keys_by_platform["macos"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes macOS installer media with artifact channel metadata that does not match top-level channelId."
        )
    if duplicate_tuple_keys_by_platform["linux"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes duplicate Linux installer tuple metadata for promoted head/rid pair(s): "
            + ", ".join(duplicate_tuple_keys_by_platform["linux"])
            + "."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and duplicate_tuple_keys_by_platform["windows"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes duplicate Windows installer tuple metadata for promoted head/rid pair(s): "
            + ", ".join(duplicate_tuple_keys_by_platform["windows"])
            + "."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and duplicate_tuple_keys_by_platform["macos"]:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel publishes duplicate macOS installer tuple metadata for promoted head/rid pair(s): "
            + ", ".join(duplicate_tuple_keys_by_platform["macos"])
            + "."
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
    if tuple_coverage_missing_platform_inventory_mismatch:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel desktop tuple coverage missingRequiredPlatforms inventory does not match promoted installer tuple reality."
        )
    if tuple_coverage_missing_head_inventory_mismatch:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel desktop tuple coverage missingRequiredHeads inventory does not match promoted installer tuple reality."
        )
    if missing_required_platform_head_pairs:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel is missing required desktop platform/head installer tuple pair(s): "
            + ", ".join(missing_required_platform_head_pairs)
            + "."
        )
    if tuple_coverage_declared and has_any_public_installer and not tuple_coverage_declares_missing_required_platform_head_pairs:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel desktop tuple coverage must declare missingRequiredPlatformHeadPairs explicitly (empty list when complete)."
        )
    if tuple_coverage_declared and has_any_public_installer and not tuple_coverage_declares_missing_required_platforms:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel desktop tuple coverage must declare missingRequiredPlatforms explicitly (empty list when complete)."
        )
    if tuple_coverage_declared and has_any_public_installer and not tuple_coverage_declares_missing_required_heads:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel desktop tuple coverage must declare missingRequiredHeads explicitly (empty list when complete)."
        )
    if tuple_coverage_declared and tuple_coverage_incomplete and release_channel_rollout_state != "coverage_incomplete":
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel must set rolloutState=coverage_incomplete when required desktop tuple coverage is incomplete."
        )
    if tuple_coverage_declared and tuple_coverage_incomplete and release_channel_supportability_state != "review_required":
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel must set supportabilityState=review_required when required desktop tuple coverage is incomplete."
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
    if unpromoted_desktop_shelf_installers:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Desktop shelf contains installer artifacts not represented in release-channel promoted tuples: "
            + ", ".join(unpromoted_desktop_shelf_installers)
            + "."
        )
    if stale_passing_platform_gate_receipts_without_promoted_tuples_mismatch:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate stale passing non-promoted tuple inventory does not match stale receipt status rows."
        )
    if stale_linux_receipt_tuples_overlapping_promoted_tuples:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate stale Linux non-promoted tuple inventory overlaps promoted release-channel tuples: "
            + ", ".join(stale_linux_receipt_tuples_overlapping_promoted_tuples)
            + "."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and stale_windows_receipt_tuples_overlapping_promoted_tuples:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate stale Windows non-promoted tuple inventory overlaps promoted release-channel tuples: "
            + ", ".join(stale_windows_receipt_tuples_overlapping_promoted_tuples)
            + "."
        )
    if not ignore_nonlinux_desktop_host_proof_blockers and stale_macos_receipt_tuples_overlapping_promoted_tuples:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate stale macOS non-promoted tuple inventory overlaps promoted release-channel tuples: "
            + ", ".join(stale_macos_receipt_tuples_overlapping_promoted_tuples)
            + "."
        )
    if stale_passing_platform_gate_receipts_without_promoted_tuples_effective:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Executable gate reports stale passing platform gate receipts for non-promoted desktop tuples: "
            + ", ".join(stale_passing_platform_gate_receipts_without_promoted_tuples_effective)
            + "."
        )

    if has_linux_public_installer:
        if linux_stale_promoted_keys:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes Linux installer media, but executable-gate startup-smoke tuple proof is stale for tuple(s): "
                + ", ".join(linux_stale_promoted_keys)
                + "."
            )
        if linux_tuple_count > 0 and linux_passing_status_count == linux_tuple_count and not linux_missing_or_failing_keys:
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes Linux installer media, but executable-gate evidence is missing passing Linux startup-smoke tuple proof."
            )
    if has_windows_public_installer and not ignore_nonlinux_desktop_host_proof_blockers:
        if windows_stale_promoted_keys:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes Windows installer media, but executable-gate startup-smoke tuple proof is stale for tuple(s): "
                + ", ".join(windows_stale_promoted_keys)
                + "."
            )
        if windows_tuple_count > 0 and windows_passing_status_count == windows_tuple_count and not windows_missing_or_failing_keys:
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes Windows installer media, but executable-gate evidence is missing passing Windows startup-smoke tuple proof."
            )
    if has_macos_public_installer and not ignore_nonlinux_desktop_host_proof_blockers:
        if macos_stale_promoted_keys:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes macOS installer media, but executable-gate startup-smoke tuple proof is stale for tuple(s): "
                + ", ".join(macos_stale_promoted_keys)
                + "."
            )
        if macos_tuple_count > 0 and macos_passing_status_count == macos_tuple_count and not macos_missing_or_failing_keys:
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Release channel publishes macOS installer media, but executable-gate evidence is missing passing macOS startup-smoke tuple proof."
            )
    install_journey = dict(journeys.get("install_claim_restore_continue") or {})
    build_journey = dict(journeys.get("build_explain_publish") or {})
    install_journey_state = str(install_journey.get("state") or "").strip()
    build_journey_state = str(build_journey.get("state") or "").strip()
    install_journey_external_blockers = [
        str(item).strip()
        for item in (install_journey.get("external_blocking_reasons") or [])
        if str(item).strip()
    ]
    install_journey_local_blockers = [
        str(item).strip()
        for item in (install_journey.get("local_blocking_reasons") or [])
        if str(item).strip()
    ]
    install_journey_external_proof_requests = [
        dict(item)
        for item in (install_journey.get("external_proof_requests") or [])
        if isinstance(item, dict)
    ]
    install_journey_external_proof_request_hosts = sorted(
        {
            str(item.get("required_host") or item.get("requiredHost") or "").strip().lower()
            for item in install_journey_external_proof_requests
            if str(item.get("required_host") or item.get("requiredHost") or "").strip()
        }
    )
    install_journey_external_proof_request_tuples = sorted(
        {
            str(item.get("tuple_id") or item.get("tupleId") or "").strip()
            for item in install_journey_external_proof_requests
            if str(item.get("tuple_id") or item.get("tupleId") or "").strip()
        }
    )
    build_journey_external_blockers = [
        str(item).strip()
        for item in (build_journey.get("external_blocking_reasons") or [])
        if str(item).strip()
    ]
    build_journey_external_proof_requests = [
        dict(item)
        for item in (build_journey.get("external_proof_requests") or [])
        if isinstance(item, dict)
    ]
    build_journey_local_blockers = [
        str(item).strip()
        for item in (build_journey.get("local_blocking_reasons") or [])
        if str(item).strip()
    ]
    executable_local_blocking_findings_count = int(
        ui_executable_exit_gate.get("local_blocking_findings_count")
        or ui_executable_exit_gate.get("localBlockingFindingsCount")
        or 0
    )
    install_journey_filtered_external_proof_requests = _filter_external_proof_requests(
        install_journey_external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_desktop_host_proof_blockers,
    )
    build_journey_filtered_external_proof_requests = _filter_external_proof_requests(
        build_journey_external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_desktop_host_proof_blockers,
    )
    install_journey_has_relevant_external_blockers = _has_relevant_external_blockers(
        install_journey_external_blockers,
        external_proof_requests=install_journey_external_proof_requests,
        filtered_external_proof_requests=install_journey_filtered_external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_desktop_host_proof_blockers,
    )
    build_journey_has_relevant_external_blockers = _has_relevant_external_blockers(
        build_journey_external_blockers,
        external_proof_requests=build_journey_external_proof_requests,
        filtered_external_proof_requests=build_journey_filtered_external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_desktop_host_proof_blockers,
    )
    install_journey_external_only = (
        bool(install_journey.get("blocked_by_external_constraints_only"))
        and install_journey_has_relevant_external_blockers
    )
    install_journey_effective_external_only = install_journey_external_only or (
        ignore_nonlinux_desktop_host_proof_blockers
        and bool(install_journey.get("blocked_by_external_constraints_only"))
        and not install_journey_local_blockers
    )
    install_journey_external_reason = (
        "Install/claim/restore journey is blocked only by external platform-host proof requests; "
        "the remaining work is to capture and ingest the missing desktop host receipts."
    )
    report_cluster_journey = journeys.get("report_cluster_release_notify") or {}
    report_cluster_external_blockers = [
        str(item).strip()
        for item in (report_cluster_journey.get("external_blocking_reasons") or [])
        if str(item).strip()
    ]
    report_cluster_external_proof_requests = [
        dict(item)
        for item in (report_cluster_journey.get("external_proof_requests") or [])
        if isinstance(item, dict)
    ]
    report_cluster_local_blockers = [
        str(item).strip()
        for item in (report_cluster_journey.get("local_blocking_reasons") or [])
        if str(item).strip()
    ]
    report_cluster_filtered_external_proof_requests = _filter_external_proof_requests(
        report_cluster_external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_desktop_host_proof_blockers,
    )
    report_cluster_has_relevant_external_blockers = _has_relevant_external_blockers(
        report_cluster_external_blockers,
        external_proof_requests=report_cluster_external_proof_requests,
        filtered_external_proof_requests=report_cluster_filtered_external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_desktop_host_proof_blockers,
    )
    report_cluster_external_only = (
        bool(report_cluster_journey.get("blocked_by_external_constraints_only"))
        and report_cluster_has_relevant_external_blockers
    )
    report_cluster_effective_external_only = report_cluster_external_only or (
        ignore_nonlinux_desktop_host_proof_blockers
        and bool(report_cluster_journey.get("blocked_by_external_constraints_only"))
        and not report_cluster_local_blockers
    )
    report_cluster_external_reason = (
        "Report/cluster/release/notify journey is blocked only by external platform-host proof requests; "
        "the remaining work is to capture and ingest the missing desktop host receipts."
    )
    if install_journey_state == "ready":
        desktop_positives += 1
    else:
        if install_journey_effective_external_only:
            desktop_reasons.append(
                "Install/claim/restore journey is blocked by external platform-host constraints; capture the missing host proof lane and ingest receipts."
            )
        else:
            desktop_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if build_journey_state == "ready":
        desktop_positives += 1
    else:
        if (
            bool(build_journey.get("blocked_by_external_constraints_only"))
            and (
                build_journey_has_relevant_external_blockers
                or (
                    ignore_nonlinux_desktop_host_proof_blockers
                    and not build_journey_local_blockers
                )
            )
        ):
            desktop_reasons.append(
                "Build/explain/publish journey is blocked by external platform-host constraints; capture the missing host proof lane and ingest receipts."
            )
        else:
            desktop_reasons.append(f"Build/explain/publish journey is {build_journey_state or 'missing'}, not ready.")
    if (
        desktop_hard_fail
        and install_journey_effective_external_only
        and not install_journey_local_blockers
        and executable_local_blocking_findings_count == 0
    ):
        desktop_hard_fail = False
    if (
        desktop_hard_fail
        and bool(build_journey.get("blocked_by_external_constraints_only"))
        and build_journey_has_relevant_external_blockers
        and not build_journey_local_blockers
        and executable_local_blocking_findings_count == 0
    ):
        desktop_hard_fail = False
    if parity_unresolved_families:
        desktop_hard_fail = True
        parity_family_text = ", ".join(
            f"{row['id']} ({row['status']})" for row in (parity_desktop_families or parity_unresolved_families)
        )
        desktop_reasons.append(
            "No-step-back parity registry still has unresolved non-plugin families: "
            f"{parity_family_text}."
        )
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
            "ui_visual_familiarity_required_milestone2_test_variant_groups": [
                list(group) for group in DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TEST_VARIANT_GROUPS
            ],
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
            "ui_localization_release_gate_present": bool(ui_localization_release_gate),
            "ui_localization_release_gate_status": str(ui_localization_release_gate.get("status") or "").strip(),
            "ui_localization_release_gate_path": report_path(ui_localization_release_gate_path),
            "ui_localization_release_gate_default_key_count": int(
                ui_localization_release_gate.get("default_key_count") or 0
            ),
            "ui_localization_release_gate_locale_summary_count": len(localization_locale_summary),
            "ui_localization_release_gate_shipping_locale_count": len(localization_shipping_locales),
            "ui_localization_release_gate_shipping_locales": localization_shipping_locales,
            "ui_localization_release_gate_missing_locale_summary_shipping_locale_count": len(
                localization_missing_locale_summary_shipping_locales
            ),
            "ui_localization_release_gate_missing_locale_summary_shipping_locales": localization_missing_locale_summary_shipping_locales,
            "ui_localization_release_gate_translation_backlog_finding_count": len(
                localization_translation_backlog_findings
            ),
            "ui_localization_release_gate_translation_backlog_findings": localization_translation_backlog_findings,
            "ui_localization_release_gate_untranslated_locale_count": len(
                localization_untranslated_counts_by_locale
            ),
            "ui_localization_release_gate_untranslated_counts_by_locale": localization_untranslated_counts_by_locale,
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
            "release_channel_missing_required_platforms_derived": missing_required_platforms_derived,
            "release_channel_missing_required_heads_derived": missing_required_heads_derived,
            "release_channel_tuple_coverage_reported_missing_required_platform_head_pairs": (
                tuple_coverage_reported_missing_platform_head_pairs
            ),
            "release_channel_tuple_coverage_reported_missing_required_platforms": (
                tuple_coverage_reported_missing_platforms
            ),
            "release_channel_tuple_coverage_reported_missing_required_heads": (
                tuple_coverage_reported_missing_heads
            ),
            "release_channel_tuple_coverage_declares_missing_required_platform_head_pairs": (
                tuple_coverage_declares_missing_required_platform_head_pairs
            ),
            "release_channel_tuple_coverage_declares_missing_required_platforms": (
                tuple_coverage_declares_missing_required_platforms
            ),
            "release_channel_tuple_coverage_declares_missing_required_heads": (
                tuple_coverage_declares_missing_required_heads
            ),
            "release_channel_tuple_coverage_incomplete": tuple_coverage_incomplete,
            "release_channel_tuple_coverage_missing_pair_inventory_mismatch": (
                tuple_coverage_missing_pair_inventory_mismatch
            ),
            "release_channel_tuple_coverage_missing_platform_inventory_mismatch": (
                tuple_coverage_missing_platform_inventory_mismatch
            ),
            "release_channel_tuple_coverage_missing_head_inventory_mismatch": (
                tuple_coverage_missing_head_inventory_mismatch
            ),
            "release_channel_rollout_state": release_channel_rollout_state,
            "release_channel_supportability_state": release_channel_supportability_state,
            "ui_executable_gate_visual_required_promoted_heads": visual_required_heads,
            "ui_executable_gate_workflow_required_promoted_heads": workflow_required_heads,
            "ui_executable_gate_visual_missing_required_inventory_heads": missing_visual_required_inventory_heads,
            "ui_executable_gate_workflow_missing_required_inventory_heads": missing_workflow_required_inventory_heads,
            "ui_executable_gate_visual_missing_or_failing_head_proofs": missing_visual_passing_head_proofs,
            "ui_executable_gate_workflow_missing_or_failing_head_proofs": missing_workflow_passing_head_proofs,
            "ui_executable_gate_unpromoted_desktop_shelf_installers": unpromoted_desktop_shelf_installers,
            "ui_executable_gate_trusted_local_roots": executable_gate_trusted_local_roots,
            "ui_executable_gate_has_expanded_trusted_local_roots": executable_gate_has_expanded_trusted_local_roots,
            "ui_executable_gate_hub_registry_root": executable_gate_hub_registry_root,
            "ui_executable_gate_hub_registry_release_channel_path": (
                executable_gate_hub_registry_release_channel_path
            ),
            "ui_executable_gate_hub_registry_root_trusted_for_startup_smoke_proof": (
                executable_gate_hub_registry_root_trusted
            ),
            "ui_executable_gate_stale_linux_gate_receipts_without_promoted_tuples": (
                stale_linux_gate_receipts_without_promoted_tuples
            ),
            "ui_executable_gate_stale_windows_gate_receipts_without_promoted_tuples": (
                stale_windows_gate_receipts_without_promoted_tuples
            ),
            "ui_executable_gate_stale_macos_gate_receipts_without_promoted_tuples": (
                stale_macos_gate_receipts_without_promoted_tuples
            ),
            "ui_executable_gate_stale_linux_gate_receipt_tuple_keys_without_promoted_tuples": (
                stale_linux_gate_receipt_tuple_keys_without_promoted_tuples
            ),
            "ui_executable_gate_stale_windows_gate_receipt_tuple_keys_without_promoted_tuples": (
                stale_windows_gate_receipt_tuple_keys_without_promoted_tuples
            ),
            "ui_executable_gate_stale_macos_gate_receipt_tuple_keys_without_promoted_tuples": (
                stale_macos_gate_receipt_tuple_keys_without_promoted_tuples
            ),
            "ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples": (
                stale_passing_platform_gate_receipts_without_promoted_tuples
            ),
            "ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples_derived": (
                stale_passing_platform_gate_receipts_without_promoted_tuples_derived
            ),
            "ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples_mismatch": (
                stale_passing_platform_gate_receipts_without_promoted_tuples_mismatch
            ),
            "ui_executable_gate_stale_linux_receipt_tuples_overlapping_promoted_tuples": (
                stale_linux_receipt_tuples_overlapping_promoted_tuples
            ),
            "ui_executable_gate_stale_windows_receipt_tuples_overlapping_promoted_tuples": (
                stale_windows_receipt_tuples_overlapping_promoted_tuples
            ),
            "ui_executable_gate_stale_macos_receipt_tuples_overlapping_promoted_tuples": (
                stale_macos_receipt_tuples_overlapping_promoted_tuples
            ),
            "release_channel_linux_has_invalid_tuple_metadata": invalid_tuple_metadata_by_platform["linux"],
            "release_channel_windows_has_invalid_tuple_metadata": invalid_tuple_metadata_by_platform["windows"],
            "release_channel_macos_has_invalid_tuple_metadata": invalid_tuple_metadata_by_platform["macos"],
            "release_channel_linux_channel_mismatch_keys": channel_mismatch_keys_by_platform["linux"],
            "release_channel_windows_channel_mismatch_keys": channel_mismatch_keys_by_platform["windows"],
            "release_channel_macos_channel_mismatch_keys": channel_mismatch_keys_by_platform["macos"],
            "release_channel_linux_duplicate_tuple_keys": duplicate_tuple_keys_by_platform["linux"],
            "release_channel_windows_duplicate_tuple_keys": duplicate_tuple_keys_by_platform["windows"],
            "release_channel_macos_duplicate_tuple_keys": duplicate_tuple_keys_by_platform["macos"],
            "ui_executable_gate_linux_statuses": linux_statuses,
            "ui_executable_gate_linux_tuple_count": linux_tuple_count,
            "ui_executable_gate_linux_passing_tuple_count": linux_passing_status_count,
            "ui_executable_gate_linux_missing_or_failing_keys": linux_missing_or_failing_keys,
            "ui_executable_gate_linux_stale_promoted_tuple_keys": linux_stale_promoted_keys,
            "ui_executable_gate_windows_statuses": windows_statuses,
            "ui_executable_gate_windows_tuple_count": windows_tuple_count,
            "ui_executable_gate_windows_passing_tuple_count": windows_passing_status_count,
            "ui_executable_gate_windows_missing_or_failing_keys": windows_missing_or_failing_keys,
            "ui_executable_gate_windows_stale_promoted_tuple_keys": windows_stale_promoted_keys,
            "ui_executable_gate_macos_statuses": macos_statuses,
            "ui_executable_gate_macos_tuple_count": macos_tuple_count,
            "ui_executable_gate_macos_passing_tuple_count": macos_passing_status_count,
            "ui_executable_gate_macos_missing_or_failing_keys": macos_missing_or_failing_keys,
            "ui_executable_gate_macos_stale_promoted_tuple_keys": macos_stale_promoted_keys,
            "install_claim_restore_continue": install_journey_state,
            "build_explain_publish": build_journey_state,
            "install_claim_restore_continue_external_blocking_reason_count": len(
                install_journey_external_blockers
            ),
            "install_claim_restore_continue_local_blocking_reason_count": len(
                install_journey_local_blockers
            ),
            "install_claim_restore_continue_external_proof_request_count": len(
                install_journey_external_proof_requests
            ),
            "install_claim_restore_continue_external_proof_request_hosts": (
                install_journey_external_proof_request_hosts
            ),
            "install_claim_restore_continue_external_proof_request_tuples": (
                install_journey_external_proof_request_tuples
            ),
            "install_claim_restore_continue_external_proof_requests": (
                install_journey_external_proof_requests
            ),
            "install_claim_restore_continue_relevant_external_proof_request_count": len(
                install_journey_filtered_external_proof_requests
            ),
            "build_explain_publish_relevant_external_proof_request_count": len(
                build_journey_filtered_external_proof_requests
            ),
            "desktop_ignore_nonlinux_desktop_host_proof_blockers": bool(
                ignore_nonlinux_desktop_host_proof_blockers
            ),
            "parity_registry_path": str(effective_parity_registry_path),
            "parity_registry_excluded_scope": parity_excluded_scope,
            "parity_registry_declared_blocking_family_count": len(parity_declared_blocking_families),
            "parity_registry_declared_blocking_family_ids": [
                str(item.get("id") or "") for item in parity_declared_blocking_families if str(item.get("id") or "").strip()
            ],
            "parity_registry_proof_closed_family_count": len(parity_proof_closed_families),
            "parity_registry_proof_closed_family_ids": [
                str(item.get("id") or "") for item in parity_proof_closed_families if str(item.get("id") or "").strip()
            ],
            "parity_registry_unresolved_family_count": len(parity_unresolved_families),
            "parity_registry_unresolved_family_ids": [
                str(item.get("id") or "") for item in parity_unresolved_families if str(item.get("id") or "").strip()
            ],
            "parity_registry_desktop_family_ids": [
                str(item.get("id") or "") for item in parity_desktop_families if str(item.get("id") or "").strip()
            ],
            "parity_registry_unresolved_families": parity_unresolved_families,
            "ui_executable_exit_gate_local_blocking_findings_count": executable_local_blocking_findings_count,
            "install_claim_restore_continue_blocked_by_external_constraints_only": bool(
                install_journey.get("blocked_by_external_constraints_only")
            ),
            "build_explain_publish_external_blocking_reason_count": len(build_journey_external_blockers),
            "build_explain_publish_local_blocking_reason_count": len(build_journey_local_blockers),
            "build_explain_publish_blocked_by_external_constraints_only": bool(
                build_journey.get("blocked_by_external_constraints_only")
            ),
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
    if parity_rules_families:
        parity_family_text = ", ".join(f"{row['id']} ({row['status']})" for row in parity_rules_families)
        rules_reasons.append(
            "No-step-back rules/import parity remains unresolved outside the declared plugin exclusion: "
            f"{parity_family_text}."
        )
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
            "parity_registry_path": str(effective_parity_registry_path),
            "parity_registry_excluded_scope": parity_excluded_scope,
            "parity_registry_declared_blocking_family_count": len(parity_declared_blocking_families),
            "parity_registry_declared_blocking_family_ids": [
                str(item.get("id") or "") for item in parity_declared_blocking_families if str(item.get("id") or "").strip()
            ],
            "parity_registry_proof_closed_family_count": len(parity_proof_closed_families),
            "parity_registry_proof_closed_family_ids": [
                str(item.get("id") or "") for item in parity_proof_closed_families if str(item.get("id") or "").strip()
            ],
            "parity_registry_rules_family_ids": [
                str(item.get("id") or "") for item in parity_rules_families if str(item.get("id") or "").strip()
            ],
            "parity_registry_unresolved_family_count": len(parity_unresolved_families),
            "parity_registry_unresolved_family_ids": [
                str(item.get("id") or "") for item in parity_unresolved_families if str(item.get("id") or "").strip()
            ],
        },
    )

    hub_project = projects.get("hub") or {}
    registry_project = projects.get("hub-registry") or {}
    hub_reasons: List[str] = []
    hub_positives = 0
    report_cluster_state = str(report_cluster_journey.get("state") or "").strip()
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
        if install_journey_effective_external_only:
            hub_positives += 1
        else:
            hub_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if report_cluster_state == "ready":
        hub_positives += 1
    else:
        if report_cluster_effective_external_only:
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
            "report_cluster_release_notify_blocked_by_external_constraints_only": bool(
                report_cluster_journey.get("blocked_by_external_constraints_only")
            ),
            "report_cluster_release_notify_external_blocking_reason_count": len(report_cluster_external_blockers),
            "report_cluster_release_notify_local_blocking_reason_count": len(report_cluster_local_blockers),
            "report_cluster_release_notify_external_proof_request_count": len(report_cluster_external_proof_requests),
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
    flagship_bar_mirror_exists = DEFAULT_FLAGSHIP_BAR.is_file()
    flagship_bar_canonical_exists = CANONICAL_FLAGSHIP_BAR.is_file()
    horizons_overview_mirror_exists = DEFAULT_HORIZONS_OVERVIEW.is_file()
    mirror_horizon_doc_names = (
        {path.name for path in DEFAULT_HORIZONS_DIR.glob("*.md")}
        if DEFAULT_HORIZONS_DIR.is_dir()
        else set()
    )
    canonical_horizon_doc_names = (
        {path.name for path in CANONICAL_HORIZONS_DIR.glob("*.md")}
        if CANONICAL_HORIZONS_DIR.is_dir()
        else set()
    )
    missing_mirror_horizon_doc_names = sorted(canonical_horizon_doc_names - mirror_horizon_doc_names)
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
        if install_journey_effective_external_only:
            horizons_positives += 1
        else:
            horizons_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if report_cluster_state == "ready":
        horizons_positives += 1
    else:
        if report_cluster_effective_external_only:
            horizons_positives += 1
        else:
            horizons_reasons.append(f"Report/cluster/release/notify journey is {report_cluster_state or 'missing'}, not ready.")
    if horizons_overview_mirror_exists:
        horizons_positives += 1
    else:
        horizons_reasons.append("Fleet design mirror is missing HORIZONS.md.")
    if acceptance:
        horizons_positives += 1
    else:
        horizons_reasons.append("Flagship acceptance matrix is missing from the design mirror.")
    if flagship_bar_mirror_exists:
        horizons_positives += 1
    elif flagship_bar_canonical_exists:
        horizons_reasons.append("Fleet design mirror is missing FLAGSHIP_PRODUCT_BAR.md.")
    else:
        horizons_reasons.append("Canonical FLAGSHIP_PRODUCT_BAR.md is missing.")
    if canonical_horizon_doc_names and not missing_mirror_horizon_doc_names:
        horizons_positives += 1
    elif canonical_horizon_doc_names:
        horizons_reasons.append(
            "Fleet design mirror is missing horizon canon files: " + ", ".join(missing_mirror_horizon_doc_names) + "."
        )
    else:
        horizons_reasons.append("Canonical horizon doc set is missing or unreadable.")
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
            "report_cluster_release_notify_blocked_by_external_constraints_only": bool(
                report_cluster_journey.get("blocked_by_external_constraints_only")
            ),
            "report_cluster_release_notify_external_blocking_reason_count": len(report_cluster_external_blockers),
            "report_cluster_release_notify_local_blocking_reason_count": len(report_cluster_local_blockers),
            "report_cluster_release_notify_external_proof_request_count": len(report_cluster_external_proof_requests),
            "acceptance_path": str(effective_acceptance_path),
            "flagship_bar_mirror_path": str(DEFAULT_FLAGSHIP_BAR),
            "flagship_bar_mirror_exists": flagship_bar_mirror_exists,
            "horizons_overview_mirror_path": str(DEFAULT_HORIZONS_OVERVIEW),
            "horizons_overview_mirror_exists": horizons_overview_mirror_exists,
            "canonical_horizon_doc_count": len(canonical_horizon_doc_names),
            "mirror_horizon_doc_count": len(mirror_horizon_doc_names),
            "missing_mirror_horizon_doc_names": missing_mirror_horizon_doc_names,
        },
    )

    fleet_reasons: List[str] = []
    fleet_positives = 0
    support_summary = dict(support_packets.get("summary") or {}) if isinstance(support_packets, dict) else {}
    support_open_packet_count = int(support_summary.get("open_packet_count") or 0)
    support_unresolved_external_packet_count = int(support_summary.get("unresolved_external_proof_request_count") or 0)
    support_open_non_external_packet_count = max(0, support_open_packet_count - support_unresolved_external_packet_count)
    support_generated_at = str(support_packets.get("generated_at") or support_packets.get("generatedAt") or "").strip()
    release_channel_generated_at = str(release_channel.get("generatedAt") or release_channel.get("generated_at") or "").strip()
    external_backlog_requests_raw = [
        *install_journey_external_proof_requests,
        *report_cluster_external_proof_requests,
    ]
    external_backlog_requests, external_backlog_duplicate_count = _dedupe_external_proof_requests(
        external_backlog_requests_raw
    )
    unresolved_external_requests = len(external_backlog_requests)
    external_runbook_sync_reasons: List[str] = []
    external_runbook_synced = True
    if unresolved_external_requests > 0:
        if not external_proof_runbook:
            external_runbook_sync_reasons.append(
                "External proof runbook is missing while external desktop host-proof backlog is still open."
            )
            external_runbook_synced = False
        if not runbook_plan_generated_at:
            external_runbook_sync_reasons.append(
                "External proof runbook is missing plan_generated_at while external desktop host-proof backlog is still open."
            )
            external_runbook_synced = False
        elif support_generated_at and runbook_plan_generated_at != support_generated_at:
            external_runbook_sync_reasons.append(
                "External proof runbook plan_generated_at does not match support packets generated_at; operator follow-through is stale."
            )
            external_runbook_synced = False
        if not runbook_release_generated_at:
            external_runbook_sync_reasons.append(
                "External proof runbook is missing release_channel_generated_at while external desktop host-proof backlog is still open."
            )
            external_runbook_synced = False
        elif release_channel_generated_at and runbook_release_generated_at != release_channel_generated_at:
            external_runbook_sync_reasons.append(
                "External proof runbook release_channel_generated_at does not match release-channel generatedAt; tuple instructions are stale."
            )
            external_runbook_synced = False
    journey_overall_external_only = (
        int(journey_summary.get("blocked_count") or 0) > 0
        and int(journey_summary.get("blocked_count") or 0) == int(journey_summary.get("blocked_external_only_count") or 0)
        and int(journey_summary.get("blocked_with_local_count") or 0) == 0
    )
    runtime_alert_state = str(runtime_healing_summary.get("alert_state") or "").strip().lower()
    runtime_last_event_at = parse_iso(runtime_healing_summary.get("last_event_at"))
    supervisor_mode = str(supervisor_state.get("mode") or "").strip()
    supervisor_completion_status = _supervisor_completion_status(supervisor_state)
    supervisor_updated_at = parse_iso(supervisor_state.get("updated_at"))
    supervisor_focus_profiles = sorted(
        {
            str(item).strip()
            for item in (supervisor_state.get("focus_profiles") or [])
            if str(item).strip()
        }
    )
    supervisor_focus_profile_keys = {item.lower() for item in supervisor_focus_profiles}
    supervisor_hard_flagship_ready = "top_flagship_grade" in supervisor_focus_profile_keys
    supervisor_whole_project_frontier_ready = "whole_project_frontier" in supervisor_focus_profile_keys
    supervisor_recent_enough = (
        supervisor_updated_at is not None
        and (utc_now() - supervisor_updated_at).total_seconds() <= FLAGSHIP_OPERATOR_SUPERVISOR_MAX_AGE_HOURS * 3600
    )
    supervisor_completion_external_only = (
        supervisor_completion_status in {"fail", "failed"}
        and journey_overall_external_only
        and int(journey_summary.get("blocked_with_local_count") or 0) == 0
    )
    supervisor_loop_ready = (
        supervisor_mode in {"loop", "sharded", "flagship_product", "complete"}
        and (supervisor_completion_status in {"pass", "passed"} or supervisor_completion_external_only)
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
    if supervisor_hard_flagship_ready and supervisor_whole_project_frontier_ready:
        fleet_positives += 1
    else:
        fleet_reasons.append(
            "Supervisor is not running with the hard top-flagship / whole-project frontier profile."
        )
    if ooda_loop_ready:
        fleet_positives += 1
    else:
        fleet_reasons.append("OODA monitor does not currently report controller/supervisor up with non-stale aggregate state.")
    if str(journey_summary.get("overall_state") or "").strip().lower() == "ready":
        fleet_positives += 1
    else:
        if journey_overall_external_only:
            fleet_positives += 1
        else:
            fleet_reasons.append(f"Journey-gate overall state is {journey_summary.get('overall_state') or 'missing'}, not ready.")
    if history_snapshot_count >= 4:
        fleet_positives += 1
    else:
        fleet_reasons.append(f"Progress history only has {history_snapshot_count} snapshots; flagship operator proof expects at least 4.")
    if support_packets and parse_iso(support_packets.get("generated_at")) is not None and support_open_non_external_packet_count == 0:
        fleet_positives += 1
    elif support_packets and parse_iso(support_packets.get("generated_at")) is not None:
        fleet_reasons.append(
            f"Support-case packets still expose {support_open_non_external_packet_count} non-external open packets; the feedback/autofix loop is not fail-closed yet."
        )
    else:
        fleet_reasons.append("Support-case packets are missing or stale enough to lack a generated_at timestamp.")
    if external_runbook_synced:
        fleet_positives += 1
    else:
        fleet_reasons.extend(external_runbook_sync_reasons)
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
            "journey_blocked_external_only_count": int(journey_summary.get("blocked_external_only_count") or 0),
            "journey_blocked_with_local_count": int(journey_summary.get("blocked_with_local_count") or 0),
            "history_snapshot_count": history_snapshot_count,
            "support_packets_generated_at": str(support_packets.get("generated_at") or "").strip(),
            "support_open_packet_count": support_open_packet_count,
            "support_open_non_external_packet_count": support_open_non_external_packet_count,
            "external_proof_backlog_request_count": unresolved_external_requests,
            "external_proof_backlog_request_observation_count": len(external_backlog_requests_raw),
            "external_proof_backlog_duplicate_observation_count": external_backlog_duplicate_count,
            "external_proof_runbook_path": str(effective_external_proof_runbook_path),
            "external_proof_runbook_generated_at": runbook_generated_at,
            "external_proof_runbook_plan_generated_at": runbook_plan_generated_at,
            "external_proof_runbook_release_channel_generated_at": runbook_release_generated_at,
            "external_proof_runbook_synced": external_runbook_synced,
            "external_proof_runbook_sync_issue_count": len(external_runbook_sync_reasons),
            "dispatchable_truth_ready": bool(compile_manifest.get("dispatchable_truth_ready")),
            "supervisor_mode": supervisor_mode,
            "supervisor_completion_status": supervisor_completion_status,
            "supervisor_completion_external_only": supervisor_completion_external_only,
            "supervisor_updated_at": str(supervisor_state.get("updated_at") or "").strip(),
            "supervisor_recent_enough": supervisor_recent_enough,
            "supervisor_focus_profiles": supervisor_focus_profiles,
            "supervisor_hard_flagship_ready": supervisor_hard_flagship_ready,
            "supervisor_whole_project_frontier_ready": supervisor_whole_project_frontier_ready,
            "ooda_controller": ooda_controller,
            "ooda_supervisor": ooda_supervisor,
            "ooda_aggregate_stale": ooda_aggregate_stale,
            "ooda_timestamp_stale": ooda_timestamp_stale,
            "ooda_steady_complete_quiet": ooda_steady_complete_quiet,
        },
    )

    desktop_detail = dict(details.get("desktop_client") or {})
    desktop_evidence = dict(desktop_detail.get("evidence") or {})
    desktop_linux_ready = str(desktop_evidence.get("ui_linux_exit_gate_status") or "").strip().lower() in {"pass", "passed", "ready"}
    desktop_external_hosts = {
        str(item).strip().lower()
        for item in (desktop_evidence.get("install_claim_restore_continue_external_proof_request_hosts") or [])
        if str(item).strip()
    }
    desktop_local_blocking_count = int(desktop_evidence.get("install_claim_restore_continue_local_blocking_reason_count") or 0)
    desktop_external_request_count = int(desktop_evidence.get("install_claim_restore_continue_external_proof_request_count") or 0)
    desktop_scoped_deferable = False
    if desktop_scoped_deferable:
        desktop_detail["scoped_deferable"] = True
        details["desktop_client"] = desktop_detail
    ready_keys = [key for key, value in coverage.items() if value == "ready"]
    warning_keys = [key for key, value in coverage.items() if value == "warning"]
    missing_keys = [key for key, value in coverage.items() if value == "missing"]
    deferred_warning_keys: List[str] = []
    scoped_warning_keys = list(warning_keys)
    scoped_missing_keys = list(missing_keys)
    if desktop_scoped_deferable and str(coverage.get("desktop_client") or "").strip().lower() == "warning":
        deferred_warning_keys = ["desktop_client"]
    status = "pass" if not warning_keys and not missing_keys else "fail"
    scoped_status = status
    external_backlog_hosts = sorted(
        {
            host
            for host in (_external_request_required_host(request) for request in external_backlog_requests)
            if host
        }
    )
    external_backlog_tuples = sorted(
        {
            tuple_id
            for tuple_id in (_external_request_tuple_id(request) for request in external_backlog_requests)
            if tuple_id
        }
    )
    external_host_proof_status = "pass" if unresolved_external_requests == 0 else "fail"
    external_host_proof_reason = (
        "No unresolved external desktop host-proof requests remain."
        if external_host_proof_status == "pass"
        else (
            str(journey_summary.get("recommended_action") or "").strip()
            or (
                f"Run the missing {', '.join(external_backlog_hosts) if external_backlog_hosts else 'external-host'} proof lane "
                f"for {unresolved_external_requests} desktop tuple(s), ingest receipts, and then republish release truth."
            )
        )
    )

    completion_audit_status = "pass" if status == "pass" else "fail"
    if completion_audit_status == "pass":
        completion_audit_reason = "Flagship product readiness proof is green."
    elif unresolved_external_requests > 0 and journey_overall_external_only:
        completion_audit_reason = _format_external_only_completion_reason(external_host_proof_reason)
    else:
        completion_audit_reason = "Flagship product readiness proof is not green."

    flagship_readiness_audit_status = "pass" if status == "pass" else "fail"
    coverage_gap_keys = [*warning_keys, *missing_keys]
    scoped_coverage_gap_keys = [*scoped_warning_keys, *scoped_missing_keys]
    if flagship_readiness_audit_status == "pass":
        flagship_readiness_audit_reason = "Flagship product readiness proof is green."
    else:
        flagship_readiness_audit_reason = f"flagship product readiness proof is not green: {status}"
        if missing_keys:
            flagship_readiness_audit_reason += (
                "; missing coverage: " + ", ".join(missing_keys)
            )
        elif warning_keys:
            flagship_readiness_audit_reason += (
                "; warning coverage: " + ", ".join(warning_keys)
            )

    payload: Dict[str, Any] = {
        "contract_name": "fleet.flagship_product_readiness",
        "schema_version": 1,
        "generated_at": iso(utc_now()),
        "status": status,
        "scoped_status": scoped_status,
        "ready_keys": ready_keys,
        "warning_keys": warning_keys,
        "missing_keys": missing_keys,
        "scoped_warning_keys": scoped_warning_keys,
        "scoped_missing_keys": scoped_missing_keys,
        "deferred_warning_keys": deferred_warning_keys,
        "completion_audit": {
            "status": completion_audit_status,
            "reason": completion_audit_reason,
            "external_only": bool(unresolved_external_requests > 0 and journey_overall_external_only),
            "unresolved_external_proof_request_count": unresolved_external_requests,
            "unresolved_external_proof_request_hosts": external_backlog_hosts,
            "unresolved_external_proof_request_tuples": external_backlog_tuples,
        },
        "flagship_readiness_audit": {
            "status": flagship_readiness_audit_status,
            "reason": flagship_readiness_audit_reason,
            "coverage_gap_keys": coverage_gap_keys,
            "scoped_coverage_gap_keys": scoped_coverage_gap_keys,
            "warning_coverage_keys": warning_keys,
            "missing_coverage_keys": missing_keys,
            "scoped_warning_coverage_keys": scoped_warning_keys,
            "scoped_missing_coverage_keys": scoped_missing_keys,
            "deferred_warning_coverage_keys": deferred_warning_keys,
        },
        "external_host_proof": {
            "status": external_host_proof_status,
            "reason": external_host_proof_reason,
            "unresolved_request_count": unresolved_external_requests,
            "unresolved_hosts": external_backlog_hosts,
            "unresolved_tuples": external_backlog_tuples,
            "runbook_path": str(effective_external_proof_runbook_path),
            "runbook_generated_at": runbook_generated_at,
            "runbook_plan_generated_at": runbook_plan_generated_at,
            "runbook_release_channel_generated_at": runbook_release_generated_at,
            "runbook_synced": external_runbook_synced,
            "runbook_sync_reasons": external_runbook_sync_reasons,
        },
        "summary": {
            "ready_count": len(ready_keys),
            "warning_count": len(warning_keys),
            "missing_count": len(missing_keys),
            "scoped_warning_count": len(scoped_warning_keys),
            "scoped_missing_count": len(scoped_missing_keys),
            "deferred_warning_count": len(deferred_warning_keys),
            "history_snapshot_count": history_snapshot_count,
        },
        "quality_policy": {
            "bar": "top_flagship_grade",
            "whole_project_frontier_required": True,
            "feedback_autofix_loop_required": True,
            "accept_lowered_standards": False,
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
        "scoped_warning_keys": scoped_warning_keys,
        "scoped_missing_keys": scoped_missing_keys,
        "deferred_warning_keys": deferred_warning_keys,
        "parity_registry": {
            "path": str(effective_parity_registry_path),
            "excluded_scope": parity_excluded_scope,
            "declared_blocking_family_count": len(parity_declared_blocking_families),
            "declared_blocking_family_ids": [
                str(item.get("id") or "") for item in parity_declared_blocking_families if str(item.get("id") or "").strip()
            ],
            "declared_blocking_families": parity_declared_blocking_families,
            "proof_closed_family_count": len(parity_proof_closed_families),
            "proof_closed_family_ids": [
                str(item.get("id") or "") for item in parity_proof_closed_families if str(item.get("id") or "").strip()
            ],
            "proof_closed_families": parity_proof_closed_families,
            "unresolved_family_count": len(parity_unresolved_families),
            "unresolved_family_ids": [
                str(item.get("id") or "") for item in parity_unresolved_families if str(item.get("id") or "").strip()
            ],
            "unresolved_families": parity_unresolved_families,
        },
        "evidence_sources": {
            "acceptance": str(effective_acceptance_path),
            "parity_registry": str(effective_parity_registry_path),
            "status_plane": str(status_plane_path),
            "progress_report": str(progress_report_path),
            "progress_history": str(progress_history_path),
            "journey_gates": str(journey_gates_path),
            "support_packets": str(support_packets_path),
            "external_proof_runbook": str(effective_external_proof_runbook_path),
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


def _external_request_tuple_id(request: Dict[str, Any]) -> str:
    if not isinstance(request, dict):
        return ""
    return str(request.get("tuple_id") or request.get("tupleId") or "").strip()


def _external_request_required_host(request: Dict[str, Any]) -> str:
    if not isinstance(request, dict):
        return ""
    return str(request.get("required_host") or request.get("requiredHost") or "").strip().lower()


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
    parity_registry_path: Path,
    status_plane_path: Path,
    progress_report_path: Path,
    progress_history_path: Path,
    journey_gates_path: Path,
    support_packets_path: Path,
    external_proof_runbook_path: Path | None,
    supervisor_state_path: Path,
    ooda_state_path: Path,
    ui_local_release_proof_path: Path,
    ui_linux_exit_gate_path: Path,
    ui_windows_exit_gate_path: Path,
    ui_workflow_parity_proof_path: Path,
    ui_executable_exit_gate_path: Path,
    ui_workflow_execution_gate_path: Path,
    ui_visual_familiarity_exit_gate_path: Path,
    ui_localization_release_gate_path: Path,
    sr4_workflow_parity_proof_path: Path,
    sr6_workflow_parity_proof_path: Path,
    sr4_sr6_frontier_receipt_path: Path,
    hub_local_release_proof_path: Path,
    mobile_local_release_proof_path: Path,
    release_channel_path: Path,
    releases_json_path: Path,
    ignore_nonlinux_desktop_host_proof_blockers: bool = False,
) -> Dict[str, Any]:
    payload = build_flagship_product_readiness_payload(
        acceptance_path=acceptance_path,
        parity_registry_path=parity_registry_path,
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        external_proof_runbook_path=external_proof_runbook_path,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_proof_path,
        ui_linux_exit_gate_path=ui_linux_exit_gate_path,
        ui_windows_exit_gate_path=ui_windows_exit_gate_path,
        ui_workflow_parity_proof_path=ui_workflow_parity_proof_path,
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        ui_localization_release_gate_path=ui_localization_release_gate_path,
        sr4_workflow_parity_proof_path=sr4_workflow_parity_proof_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_proof_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_proof_path,
        mobile_local_release_proof_path=mobile_local_release_proof_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ignore_nonlinux_desktop_host_proof_blockers=ignore_nonlinux_desktop_host_proof_blockers,
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
        parity_registry_path=Path(args.parity_registry).resolve(),
        status_plane_path=Path(args.status_plane).resolve(),
        progress_report_path=Path(args.progress_report).resolve(),
        progress_history_path=Path(args.progress_history).resolve(),
        journey_gates_path=Path(args.journey_gates).resolve(),
        support_packets_path=Path(args.support_packets).resolve(),
        external_proof_runbook_path=Path(args.external_proof_runbook).resolve() if str(args.external_proof_runbook or "").strip() else None,
        supervisor_state_path=Path(args.supervisor_state).resolve(),
        ooda_state_path=Path(args.ooda_state).resolve(),
        ui_local_release_proof_path=Path(args.ui_local_release_proof).resolve(),
        ui_linux_exit_gate_path=Path(args.ui_linux_exit_gate).resolve(),
        ui_windows_exit_gate_path=Path(args.ui_windows_exit_gate).resolve(),
        ui_workflow_parity_proof_path=Path(args.ui_workflow_parity_proof).resolve(),
        ui_executable_exit_gate_path=Path(args.ui_executable_exit_gate).resolve(),
        ui_workflow_execution_gate_path=Path(args.ui_workflow_execution_gate).resolve(),
        ui_visual_familiarity_exit_gate_path=Path(args.ui_visual_familiarity_exit_gate).resolve(),
        ui_localization_release_gate_path=Path(args.ui_localization_release_gate).resolve(),
        sr4_workflow_parity_proof_path=Path(args.sr4_workflow_parity_proof).resolve(),
        sr6_workflow_parity_proof_path=Path(args.sr6_workflow_parity_proof).resolve(),
        sr4_sr6_frontier_receipt_path=Path(args.sr4_sr6_frontier_receipt).resolve(),
        hub_local_release_proof_path=Path(args.hub_local_release_proof).resolve(),
        mobile_local_release_proof_path=Path(args.mobile_local_release_proof).resolve(),
        release_channel_path=Path(args.release_channel).resolve(),
        releases_json_path=Path(args.releases_json).resolve(),
        ignore_nonlinux_desktop_host_proof_blockers=bool(args.ignore_nonlinux_desktop_host_proof_blockers),
    )
    print(
        "wrote flagship product readiness: "
        f"{Path(args.out).resolve()} ({payload['status']}; ready={payload['summary']['ready_count']}, "
        f"warning={payload['summary']['warning_count']}, missing={payload['summary']['missing_count']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
