#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml

try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest
    from scripts.materialize_support_case_packets import _refresh_weekly_governor_packet_if_possible
except ModuleNotFoundError:
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest
    from materialize_support_case_packets import _refresh_weekly_governor_packet_if_possible
try:
    from admin.readiness import studio_compile_summary
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from admin.readiness import studio_compile_summary
try:
    from scripts.external_proof_paths import resolve_release_channel_path
except ModuleNotFoundError:
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from external_proof_paths import resolve_release_channel_path


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")

DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEFAULT_MIRROR_OUT = ROOT / "state" / "chummer_design_supervisor" / "artifacts" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
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
DEFAULT_FLAGSHIP_PARITY_REGISTRY = ROOT / ".codex-design" / "product" / "FLAGSHIP_PARITY_REGISTRY.yaml"
CANONICAL_FLAGSHIP_PARITY_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_PARITY_REGISTRY.yaml"
)
DEFAULT_FLAGSHIP_READINESS_PLANES = ROOT / ".codex-design" / "product" / "FLAGSHIP_READINESS_PLANES.yaml"
CANONICAL_FLAGSHIP_READINESS_PLANES = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_READINESS_PLANES.yaml"
)
DEFAULT_FEEDBACK_LOOP_RELEASE_GATE = ROOT / ".codex-design" / "product" / "FEEDBACK_LOOP_RELEASE_GATE.yaml"
CANONICAL_FEEDBACK_LOOP_RELEASE_GATE = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/FEEDBACK_LOOP_RELEASE_GATE.yaml"
)
DEFAULT_FEEDBACK_PROGRESS_EMAIL_WORKFLOW = ROOT / ".codex-design" / "product" / "FEEDBACK_PROGRESS_EMAIL_WORKFLOW.yaml"
CANONICAL_FEEDBACK_PROGRESS_EMAIL_WORKFLOW = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/FEEDBACK_PROGRESS_EMAIL_WORKFLOW.yaml"
)
DEFAULT_DENSE_WORKBENCH_BUDGET = ROOT / ".codex-design" / "product" / "DENSE_WORKBENCH_BUDGET.yaml"
CANONICAL_DENSE_WORKBENCH_BUDGET = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/DENSE_WORKBENCH_BUDGET.yaml"
)
DEFAULT_VETERAN_FIRST_MINUTE_GATE = ROOT / ".codex-design" / "product" / "VETERAN_FIRST_MINUTE_GATE.yaml"
CANONICAL_VETERAN_FIRST_MINUTE_GATE = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/VETERAN_FIRST_MINUTE_GATE.yaml"
)
DEFAULT_PRIMARY_ROUTE_REGISTRY = ROOT / ".codex-design" / "product" / "PRIMARY_ROUTE_REGISTRY.yaml"
CANONICAL_PRIMARY_ROUTE_REGISTRY = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/PRIMARY_ROUTE_REGISTRY.yaml"
)
DEFAULT_STATUS_PLANE = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEFAULT_PROGRESS_REPORT = ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY = ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_JOURNEY_GATES = ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
DEFAULT_SUPPORT_PACKETS = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_M136_AGGREGATE_READINESS_GATE = (
    ROOT / ".codex-studio" / "published" / "NEXT90_M136_FLEET_AGGREGATE_READINESS_PARITY_GATES.generated.json"
)
DEFAULT_EXTERNAL_PROOF_RUNBOOK = ROOT / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
DEFAULT_EXTERNAL_PROOF_COMMANDS_DIR = ROOT / ".codex-studio" / "published" / "external-proof-commands"
DEFAULT_PARITY_LAB_DOCS_ROOT = ROOT / "docs" / "chummer5a-oracle"
DEFAULT_PARITY_LAB_CAPTURE_PACK = DEFAULT_PARITY_LAB_DOCS_ROOT / "parity_lab_capture_pack.yaml"
DEFAULT_VETERAN_WORKFLOW_PACK = DEFAULT_PARITY_LAB_DOCS_ROOT / "veteran_workflow_packs.yaml"
DEFAULT_SUPERVISOR_STATE = ROOT / "state" / "chummer_design_supervisor" / "state.json"
DEFAULT_OODA_STATE = ROOT / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
EXTERNAL_PROOF_COMMAND_BUNDLE_SUFFIXES = frozenset({".sh", ".ps1"})

def _preferred_ui_repo_root() -> Path:
    override = str(os.environ.get("CHUMMER_UI_REPO_ROOT", "") or "").strip()
    if override:
        return Path(override)
    for candidate in (
        Path("/docker/chummercomplete/chummer6-ui"),
        Path("/docker/chummercomplete/chummer6-ui-finish"),
        Path("/docker/chummercomplete/chummer-presentation"),
    ):
        if candidate.exists():
            return candidate
    return Path("/docker/chummercomplete/chummer6-ui")


PREFERRED_UI_REPO_ROOT = _preferred_ui_repo_root()
DEFAULT_UI_LOCAL_RELEASE_PROOF = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCAL_RELEASE_PROOF.generated.json"
DEFAULT_UI_LINUX_EXIT_GATE = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
DEFAULT_UI_WINDOWS_EXIT_GATE = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
DEFAULT_UI_WORKFLOW_PARITY_PROOF = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
DEFAULT_UI_EXECUTABLE_EXIT_GATE = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
DEFAULT_UI_WORKFLOW_EXECUTION_GATE = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
DEFAULT_UI_VISUAL_FAMILIARITY_EXIT_GATE = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
DEFAULT_UI_ELEMENT_PARITY_AUDIT = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json"
DEFAULT_UI_USER_JOURNEY_TESTER_AUDIT = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "USER_JOURNEY_TESTER_AUDIT.generated.json"
DEFAULT_UI_LOCALIZATION_RELEASE_GATE = PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
DEFAULT_HUB_LOCAL_RELEASE_PROOF = Path("/docker/chummercomplete/chummer6-hub/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json")
DEFAULT_MOBILE_LOCAL_RELEASE_PROOF = Path("/docker/chummercomplete/chummer6-mobile/.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json")
DEFAULT_RELEASE_CHANNEL = resolve_release_channel_path()
DEFAULT_RELEASES_JSON = DEFAULT_RELEASE_CHANNEL.with_name("releases.json")
DEFAULT_SHARD_SUPERVISOR_ROOT = DEFAULT_SUPERVISOR_STATE.parent
UI_REPO_CANONICAL_ALIAS_ROOT = Path("/docker/chummercomplete/chummer6-ui")
UI_REPO_FINISH_REAL_ROOT = Path("/docker/chummercomplete/chummer6-ui-finish")
UI_REPO_LEGACY_REAL_ROOT = Path("/docker/chummercomplete/chummer-presentation")
RUNTIME_ENV_CANDIDATES = (
    ROOT / "runtime.env",
    ROOT / "runtime.ea.env",
    ROOT / ".env",
)

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
USER_JOURNEY_TESTER_MIN_SCREENSHOTS_PER_WORKFLOW = 2
USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS = (
    "master_index_search_focus_stability",
    "file_new_character_visible_workspace",
    "minimal_character_build_save_reload",
    "major_navigation_sanity",
    "validation_or_export_smoke",
)
USER_JOURNEY_TESTER_REQUIRED_WORKFLOW_ASSERTIONS = {
    "master_index_search_focus_stability": (
        "focus_preserved_after_typing",
        "search_text_accumulates_keyboard_input",
    ),
    "file_new_character_visible_workspace": (
        "new_character_action_opened_visible_workspace",
        "visible_workspace_nonblank",
        "starter_attributes_match_seeded_workspace",
        "section_preview_omits_review_copy",
    ),
    "minimal_character_build_save_reload": (
        "character_created_saved_reloaded",
        "reload_preserved_character_identity",
    ),
    "major_navigation_sanity": (
        "primary_navigation_clicks_change_visible_content",
        "no_unhandled_errors",
    ),
    "validation_or_export_smoke": (
        "validation_or_export_action_completed",
        "result_visible_or_file_created",
    ),
}


def _runtime_env_candidates(repo_root: Path | None = None) -> List[Path]:
    candidates: List[Path] = []
    if repo_root is not None:
        repo_root = repo_root.resolve()
        candidates.extend(
            [
                repo_root / "runtime.env",
                repo_root / "runtime.ea.env",
                repo_root / ".env",
            ]
        )
        if repo_root != ROOT.resolve():
            return candidates
    candidates.extend(RUNTIME_ENV_CANDIDATES)
    return candidates


def _runtime_env_value(key: str, *, repo_root: Path | None = None) -> str:
    direct = str(os.environ.get(key, "") or "").strip()
    if direct:
        return direct
    for candidate in _runtime_env_candidates(repo_root):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            current_key, value = line.split("=", 1)
            if current_key.strip() != key:
                continue
            return value.strip().strip("'").strip('"')
    return ""


def _runtime_env_list(key: str, *, repo_root: Path | None = None) -> List[str]:
    raw = _runtime_env_value(key, repo_root=repo_root)
    if not raw:
        return []
    return sorted({item.strip() for item in re.split(r"[\s,]+", raw) if item.strip()})


def _ignore_nonlinux_desktop_host_proof_blockers_enabled(*, repo_root: Path | None = None) -> bool:
    env_key = "CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS"
    focus_profiles = {
        item.strip().lower()
        for item in _runtime_env_list("CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE", repo_root=repo_root)
    }
    if {"top_flagship_grade", "whole_project_frontier"}.issubset(focus_profiles):
        return False
    if repo_root is None or repo_root.resolve() == ROOT.resolve():
        direct = str(os.environ.get(env_key, "") or "").strip()
        if direct:
            return direct.lower() in {"1", "true", "yes", "on"}
    direct = ""
    for candidate in _runtime_env_candidates(repo_root):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            current_key, value = line.split("=", 1)
            if current_key.strip() != env_key:
                continue
            direct = value.strip().strip("'").strip('"')
            break
        if direct:
            break
    return direct.lower() in {"1", "true", "yes", "on"}
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
    (
        "Runtime_backed_codex_tree_preserves_legacy_left_rail_navigation_posture",
        "Standalone_navigator_tree_selection_raises_workspace_tab_section_and_workflow_events",
    ),
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
DESKTOP_VISUAL_FAMILIARITY_SEMANTIC_KEY_ALIASES = {
    "runtimeBackedFileMenuRoutes": (
        "runtimeBackedFileMenuRoutes",
        "runtime_backed_file_menu_routes",
    ),
    "runtimeBackedMasterIndex": (
        "runtimeBackedMasterIndex",
        "runtime_backed_master_index",
    ),
    "runtimeBackedCharacterRoster": (
        "runtimeBackedCharacterRoster",
        "runtime_backed_character_roster",
    ),
    "legacyMainframeVisualSimilarity": (
        "legacyMainframeVisualSimilarity",
        "legacy_mainframe_visual_similarity",
    ),
    "runtimeBackedLegacyWorkbench": (
        "runtimeBackedLegacyWorkbench",
        "runtime_backed_legacy_workbench",
    ),
}
SUPPORT_NEEDS_HUMAN_RESPONSE_STATUSES = {"new", "clustered", "awaiting_evidence"}
DESKTOP_VISUAL_FAMILIARITY_HARD_BAR_SEMANTIC_REQUIREMENTS = {
    "Opening_mainframe_preserves_chummer5a_successor_workbench_posture": (
        "runtimeBackedLegacyWorkbench",
        "legacyMainframeVisualSimilarity",
    ),
    "Runtime_backed_file_menu_preserves_working_open_save_import_routes": (
        "runtimeBackedFileMenuRoutes",
    ),
    "Master_index_is_a_first_class_runtime_backed_workbench_route": (
        "runtimeBackedMasterIndex",
    ),
    "Character_roster_is_a_first_class_runtime_backed_workbench_route": (
        "runtimeBackedCharacterRoster",
    ),
}

RULES_CERTIFICATION_CANDIDATES = (
    Path("/docker/chummercomplete/chummer6-core/.codex-studio/published/ENGINE_PROOF_PACK.generated.json"),
    Path("/docker/chummercomplete/chummer-core-engine/.codex-studio/published/ENGINE_PROOF_PACK.generated.json"),
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
FLAGSHIP_PARITY_RELEASE_STATUS_ORDER = {
    "documented": 0,
    "implemented": 1,
    "task_proven": 2,
    "veteran_approved": 3,
    "gold_ready": 4,
}
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
PARITY_LAB_REQUIRED_NON_NEGOTIABLE_IDS = frozenset(
    {
        "no_generic_shell_or_dashboard_first",
        "startup_is_workbench_or_restore",
        "file_menu_live",
        "master_index_first_class",
        "character_roster_first_class",
        "claim_restore_in_installer_or_in_app",
        "no_browser_only_claim_code_ritual",
        "guided_product_installer_happy_path",
    }
)
PARITY_LAB_REQUIRED_WHOLE_PRODUCT_COVERAGE_KEYS = frozenset({"desktop_client", "fleet_and_operator_loop"})
UI_ELEMENT_PARITY_AUDIT_RELEASE_BLOCKING_IDS = (
    "source:hero_lab_importer_route",
    "source:translator_route",
    "source:xml_amendment_editor_route",
    "family:custom_data_xml_and_translator_bridge",
    "family:dense_builder_and_career_workflows",
    "family:dice_initiative_and_table_utilities",
    "family:identity_contacts_lifestyles_history",
    "family:legacy_and_adjacent_import_oracles",
    "family:sheet_export_print_viewer_and_exchange",
    "family:sr6_supplements_designers_and_house_rules",
)
UI_ELEMENT_PARITY_AUDIT_VETERAN_DEEP_IDS = UI_ELEMENT_PARITY_AUDIT_RELEASE_BLOCKING_IDS
UI_ELEMENT_PARITY_AUDIT_DATA_DURABILITY_IDS = (
    "source:hero_lab_importer_route",
    "family:legacy_and_adjacent_import_oracles",
    "family:identity_contacts_lifestyles_history",
    "family:sheet_export_print_viewer_and_exchange",
)
UI_ELEMENT_PARITY_AUDIT_CUSTOM_DATA_SURVIVAL_IDS = (
    "source:translator_route",
    "source:xml_amendment_editor_route",
    "family:custom_data_xml_and_translator_bridge",
)
UI_ELEMENT_PARITY_AUDIT_SR6_IDS = (
    "family:sr6_supplements_designers_and_house_rules",
)
REPO_PROOF_REASON_RE = re.compile(r"repo proof (?P<repo>[^:\s]+):(?P<path>[^\s]+)")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    raw_args = list(argv or sys.argv[1:])
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--repo-root", default=str(ROOT))
    bootstrap_args, _ = bootstrap.parse_known_args(raw_args)
    repo_root = Path(str(bootstrap_args.repo_root or ROOT)).resolve()
    parser = argparse.ArgumentParser(
        description="Materialize flagship whole-product readiness proof from Fleet's published evidence and repo-local release proofs."
    )
    parser.add_argument("--repo-root", default=str(repo_root), help="Fleet repo root")
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
    parser.add_argument(
        "--feedback-loop-gate",
        default=str(DEFAULT_FEEDBACK_LOOP_RELEASE_GATE),
        help="path to FEEDBACK_LOOP_RELEASE_GATE.yaml",
    )
    parser.add_argument("--status-plane", default=str(DEFAULT_STATUS_PLANE), help="path to STATUS_PLANE.generated.yaml")
    parser.add_argument("--progress-report", default=str(DEFAULT_PROGRESS_REPORT), help="path to PROGRESS_REPORT.generated.json")
    parser.add_argument("--progress-history", default=str(DEFAULT_PROGRESS_HISTORY), help="path to PROGRESS_HISTORY.generated.json")
    parser.add_argument("--journey-gates", default=str(DEFAULT_JOURNEY_GATES), help="path to JOURNEY_GATES.generated.json")
    parser.add_argument("--support-packets", default=str(DEFAULT_SUPPORT_PACKETS), help="path to SUPPORT_CASE_PACKETS.generated.json")
    parser.add_argument(
        "--m136-aggregate-readiness-gate",
        default=str(DEFAULT_M136_AGGREGATE_READINESS_GATE),
        help="path to NEXT90_M136_FLEET_AGGREGATE_READINESS_PARITY_GATES.generated.json",
    )
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
        "--ui-element-parity-audit",
        default="",
        help="optional path to CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json",
    )
    parser.add_argument(
        "--ui-user-journey-tester-audit",
        default=str(DEFAULT_UI_USER_JOURNEY_TESTER_AUDIT),
        help="path to USER_JOURNEY_TESTER_AUDIT.generated.json",
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
        default=_ignore_nonlinux_desktop_host_proof_blockers_enabled(repo_root=repo_root),
        help=(
            "Ignore desktop proof blockers tied to Windows and macOS external-host or tuple expectations; still require Linux proof."
        ),
    )
    return parser.parse_args(raw_args)


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


def _load_jsonl_rows(path: Path, *, limit: int = 24) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in reversed(lines):
        clean = str(line or "").strip()
        if not clean:
            continue
        try:
            payload = json.loads(clean)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(dict(payload))
        if len(rows) >= limit:
            break
    return rows


def _runtime_healing_from_local_autoheal_state(repo_root: Path) -> Dict[str, Any]:
    autoheal_dir = repo_root / "state" / "rebuilder" / "autoheal"
    events_path = autoheal_dir / "events.jsonl"
    if not autoheal_dir.is_dir():
        return {}

    service_rows: List[Dict[str, Any]] = []
    for path in sorted(autoheal_dir.glob("*.status.json")):
        payload = load_json(path)
        if not payload:
            continue
        service = str(payload.get("service") or path.name.replace(".status.json", "")).strip()
        if not service:
            continue
        current_state = str(payload.get("current_state") or "unknown").strip() or "unknown"
        service_rows.append(
            {
                "service": service,
                "current_state": current_state,
                "cooldown_active": bool(payload.get("cooldown_active")),
                "generated_at": str(payload.get("generated_at") or "").strip(),
            }
        )

    recent_events = _load_jsonl_rows(events_path, limit=24)
    for event in recent_events:
        event["service"] = str(event.get("service") or "").strip()
        event["event"] = str(event.get("event") or "").strip()
        event["detail"] = str(event.get("detail") or "").strip()
        event["at"] = str(event.get("at") or "").strip()

    escalated_services = [
        row for row in service_rows if str(row.get("current_state") or "") in {"escalation_required", "restart_failed"}
    ]
    degraded_services = [
        row
        for row in service_rows
        if str(row.get("current_state") or "") in {"cooldown", "restarting", "observed_unhealthy", "escalation_required", "restart_failed"}
        or bool(row.get("cooldown_active"))
    ]
    cooldown_services = [row for row in service_rows if bool(row.get("cooldown_active"))]
    last_event = recent_events[0] if recent_events else {}
    last_recovery = next(
        (event for event in recent_events if str(event.get("event") or "") == "restart_recovered"),
        {},
    )

    alert_state = "healthy"
    alert_reason = "No runtime healing drift is currently recorded."
    recommended_action = "Keep the bounded auto-heal loop enabled and review the weekly healer history."
    if escalated_services:
        service_labels = ", ".join(str(item.get("service") or "") for item in escalated_services[:3])
        alert_state = "action_needed"
        alert_reason = f"Runtime self-healing escalated for {service_labels or 'one or more services'}."
        recommended_action = "Open Housekeeping, inspect the escalated service, and freeze new change pressure until the root cause is understood."
    elif degraded_services:
        service_labels = ", ".join(str(item.get("service") or "") for item in degraded_services[:3])
        alert_state = "degraded"
        alert_reason = f"Runtime healing is actively compensating for {service_labels or 'recent service drift'}."
        recommended_action = "Verify the unhealthy service, fail streak, and cooldown posture before assuming the stack is steady."

    generated_candidates: List[dt.datetime] = []
    for row in service_rows:
        parsed = parse_iso(row.get("generated_at"))
        if parsed is not None:
            generated_candidates.append(parsed)
    for event in recent_events:
        parsed = parse_iso(event.get("at"))
        if parsed is not None:
            generated_candidates.append(parsed)
    generated_at = iso(max(generated_candidates)) if generated_candidates else ""

    return {
        "generated_at": generated_at,
        "enabled": True,
        "event_log_present": events_path.is_file(),
        "services": service_rows,
        "recent_events": recent_events,
        "summary": {
            "service_count": len(service_rows),
            "degraded_service_count": len(degraded_services),
            "cooldown_active_count": len(cooldown_services),
            "escalated_service_count": len(escalated_services),
            "recent_restart_count": 0,
            "alert_state": alert_state,
            "alert_reason": alert_reason,
            "recommended_action": recommended_action,
            "last_event_at": str(last_event.get("at") or "").strip(),
            "last_event_service": str(last_event.get("service") or "").strip(),
            "last_event_kind": str(last_event.get("event") or "").strip(),
            "last_event_detail": str(last_event.get("detail") or "").strip(),
            "last_recovered_service": str(last_recovery.get("service") or "").strip(),
            "last_recovered_at": str(last_recovery.get("at") or "").strip(),
        },
    }


def _effective_runtime_healing_summary(status_plane: Dict[str, Any], *, status_plane_path: Path) -> Dict[str, Any]:
    summary = dict((status_plane.get("runtime_healing") or {}).get("summary") or {})
    if summary:
        return summary
    repo_root = repo_root_for_published_path(status_plane_path)
    if repo_root is None:
        return summary
    return dict((_runtime_healing_from_local_autoheal_state(repo_root).get("summary")) or {})


def _effective_compile_manifest(status_plane_path: Path) -> Dict[str, Any]:
    repo_root = repo_root_for_published_path(status_plane_path)
    manifest_path = status_plane_path.parent / "compile.manifest.json"
    manifest = load_json(manifest_path)
    manifest_dispatchable_truth_ready = bool(manifest.get("dispatchable_truth_ready"))
    if repo_root is None:
        return manifest
    try:
        compile_summary = studio_compile_summary(repo_root)
    except Exception:
        compile_summary = {}
    if compile_summary:
        manifest["dispatchable_truth_ready"] = manifest_dispatchable_truth_ready or bool(
            compile_summary.get("dispatchable_truth_ready")
        )
        if compile_summary.get("published_at") and not manifest.get("published_at"):
            manifest["published_at"] = compile_summary.get("published_at")
        if compile_summary.get("lifecycle") and not manifest.get("lifecycle"):
            manifest["lifecycle"] = compile_summary.get("lifecycle")
        summary_stages = compile_summary.get("stages") or {}
        if isinstance(summary_stages, dict):
            merged_stages = dict(manifest.get("stages") or {})
            for key, value in summary_stages.items():
                merged_stages[str(key)] = bool(value)
            manifest["stages"] = merged_stages
        if compile_summary.get("artifacts") and not manifest.get("artifacts"):
            manifest["artifacts"] = list(compile_summary.get("artifacts") or [])
    return manifest


def _ui_element_parity_audit_summary(payload: Dict[str, Any]) -> Dict[str, int]:
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    elements = payload.get("elements") if isinstance(payload, dict) else []
    if not isinstance(elements, list):
        elements = []
    visual_no_count = _nonnegative_int(summary.get("visual_no_count"), default=-1)
    behavioral_no_count = _nonnegative_int(summary.get("behavioral_no_count"), default=-1)
    if visual_no_count < 0:
        visual_no_count = sum(
            1 for row in elements if isinstance(row, dict) and str(row.get("visual_parity") or "").strip().lower() != "yes"
        )
    if behavioral_no_count < 0:
        behavioral_no_count = sum(
            1 for row in elements if isinstance(row, dict) and str(row.get("behavioral_parity") or "").strip().lower() != "yes"
        )
    return {
        "visual_no_count": max(0, visual_no_count),
        "behavioral_no_count": max(0, behavioral_no_count),
        "total_elements": _nonnegative_int(summary.get("total_elements"), default=len(elements)),
    }


def _ui_element_parity_audit_release_blockers(payload: Dict[str, Any]) -> Dict[str, Any]:
    elements = payload.get("elements") if isinstance(payload, dict) else []
    if not isinstance(elements, list):
        elements = []
    rows_by_id: Dict[str, Dict[str, Any]] = {}
    for row in elements:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "").strip()
        if row_id:
            rows_by_id[row_id] = row
    missing_required_ids = [
        row_id for row_id in UI_ELEMENT_PARITY_AUDIT_RELEASE_BLOCKING_IDS if row_id not in rows_by_id
    ]
    unresolved_release_blocking_rows: List[Dict[str, Any]] = []
    for row_id in UI_ELEMENT_PARITY_AUDIT_RELEASE_BLOCKING_IDS:
        row = rows_by_id.get(row_id)
        if not row:
            continue
        visual = str(row.get("visual_parity") or "").strip().lower()
        behavioral = str(row.get("behavioral_parity") or "").strip().lower()
        if visual == "yes" and behavioral == "yes":
            continue
        unresolved_release_blocking_rows.append(
            {
                "id": row_id,
                "label": str(row.get("label") or row_id).strip() or row_id,
                "visual_parity": visual or "unknown",
                "behavioral_parity": behavioral or "unknown",
                "reason": str(row.get("reason") or "").strip(),
            }
        )
    unresolved_release_blocking_ids = [row["id"] for row in unresolved_release_blocking_rows]
    return {
        "rows_by_id": rows_by_id,
        "missing_required_ids": missing_required_ids,
        "unresolved_release_blocking_rows": unresolved_release_blocking_rows,
        "unresolved_release_blocking_ids": unresolved_release_blocking_ids,
        "release_blocking_ready": not missing_required_ids and not unresolved_release_blocking_ids,
    }


def _m136_aggregate_readiness_gate_audit(payload: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    if not payload:
        reasons.append("M136 aggregate-readiness parity gate is missing.")
        return {
            "ready": False,
            "status": "",
            "aggregate_readiness_status": "",
            "generated_at": "",
            "reasons": reasons,
        }
    status = str(payload.get("status") or "").strip().lower()
    monitor_summary = dict(payload.get("monitor_summary") or {})
    aggregate_readiness_status = str(monitor_summary.get("aggregate_readiness_status") or "").strip().lower()
    runtime_blockers = [
        str(item).strip()
        for item in (monitor_summary.get("runtime_blockers") or [])
        if str(item).strip()
    ]
    generated_at = str(payload.get("generated_at") or payload.get("generatedAt") or "").strip()
    if status != "pass":
        reasons.append("M136 aggregate-readiness parity gate package is not passing.")
    if aggregate_readiness_status not in {"pass", "ready"} and (
        aggregate_readiness_status != "warning" or runtime_blockers
    ):
        reasons.append("M136 aggregate-readiness parity gate still reports blocked runtime proof.")
    if not generated_at:
        reasons.append("M136 aggregate-readiness parity gate generated_at is missing.")
    return {
        "ready": not reasons,
        "status": status,
        "aggregate_readiness_status": aggregate_readiness_status,
        "runtime_blockers": runtime_blockers,
        "generated_at": generated_at,
        "reasons": reasons,
    }


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _boolish(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    raw = str(value).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _nonnegative_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _support_packet_is_non_external(packet: Dict[str, Any]) -> bool:
    install_diagnosis = packet.get("install_diagnosis")
    if isinstance(install_diagnosis, dict) and bool(install_diagnosis.get("external_proof_required")):
        return False
    packet_kind = str(packet.get("packet_kind") or packet.get("kind") or "").strip().lower()
    return packet_kind != "external_proof_request"


def _support_packet_needs_human_response(packet: Dict[str, Any]) -> bool:
    return str(packet.get("status") or "").strip().lower() in SUPPORT_NEEDS_HUMAN_RESPONSE_STATUSES


def extract_runbook_field(markdown: str, key: str) -> str:
    if not markdown:
        return ""
    needle = f"- {key}:"
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith(needle):
            return line[len(needle) :].strip().strip("`")
    return ""


def external_proof_command_bundle_fingerprint(commands_dir: Path) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    aggregate = hashlib.sha256()
    if not commands_dir.exists():
        return {"sha256": "", "file_count": 0, "files": files}
    for candidate in sorted(
        path
        for path in commands_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in EXTERNAL_PROOF_COMMAND_BUNDLE_SUFFIXES
    ):
        relative_path = candidate.relative_to(commands_dir).as_posix()
        payload = candidate.read_bytes()
        file_sha256 = hashlib.sha256(payload).hexdigest()
        executable = os.access(candidate, os.X_OK)
        aggregate.update(relative_path.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(file_sha256.encode("ascii"))
        aggregate.update(b"\0")
        aggregate.update(b"1" if executable else b"0")
        aggregate.update(b"\n")
        files.append(
            {
                "path": relative_path,
                "sha256": file_sha256,
                "executable": executable,
            }
        )
    return {
        "sha256": aggregate.hexdigest() if files else "",
        "file_count": len(files),
        "files": files,
    }


def report_path(path: Path) -> str:
    raw = str(path)
    if not raw:
        return raw
    try:
        resolved = path.resolve()
    except OSError:
        return raw
    resolved_raw = str(resolved)
    canonical_prefix = str(UI_REPO_CANONICAL_ALIAS_ROOT)
    for real_root in (UI_REPO_FINISH_REAL_ROOT, UI_REPO_LEGACY_REAL_ROOT):
        real_prefix = str(real_root)
        if resolved_raw == real_prefix:
            return canonical_prefix
        if resolved_raw.startswith(real_prefix + "/"):
            suffix = resolved_raw[len(real_prefix) :]
            return canonical_prefix + suffix
    return raw


def _supervisor_state_root(path: Path) -> Path:
    parent = path.parent
    if path.name != "state.json":
        return parent
    if parent.name.startswith("shard-") or parent.name.startswith("orphaned-shard-"):
        return parent.parent
    return parent


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _feedback_loop_readiness_plane(
    *,
    feedback_loop_gate: Dict[str, Any],
    gate_path: Path,
    feedback_progress_email_workflow: Dict[str, Any],
    feedback_progress_email_workflow_path: Path,
    support_packets: Dict[str, Any],
    support_open_packet_count: int,
    support_open_non_external_packet_count: int,
    support_generated_at: str,
    support_generated_age_seconds: int | None,
    support_source_refresh_mode: str,
    support_closure_waiting_on_release_truth: int,
    support_update_required_misrouted_case_count: int,
    support_non_external_needs_human_response_count: int,
    support_non_external_packets_without_named_owner: int,
    support_non_external_packets_without_lane: int,
    unresolved_external_requests: int,
    external_runbook_synced: bool,
) -> tuple[str, Dict[str, Any]]:
    thresholds = (
        feedback_loop_gate.get("thresholds")
        if isinstance(feedback_loop_gate.get("thresholds"), dict)
        else {}
    )
    max_support_packet_age_hours = _nonnegative_int(thresholds.get("max_support_packet_age_hours"), 24)
    max_open_non_external_packets = _nonnegative_int(thresholds.get("max_open_non_external_packets"), 0)
    max_closure_waiting_on_release_truth = _nonnegative_int(
        thresholds.get("max_closure_waiting_on_release_truth"), 0
    )
    max_update_required_misrouted_cases = _nonnegative_int(
        thresholds.get("max_update_required_misrouted_cases"), 0
    )
    max_non_external_needs_human_response = _nonnegative_int(
        thresholds.get("max_non_external_needs_human_response"), 0
    )
    require_named_owner_on_non_external_packets = _boolish(
        thresholds.get("require_named_owner_on_non_external_packets"), default=True
    )
    require_named_lane_on_non_external_packets = _boolish(
        thresholds.get("require_named_lane_on_non_external_packets"), default=True
    )
    allow_cached_packet_refresh_for_gold = _boolish(
        thresholds.get("allow_cached_packet_refresh_for_gold"), default=False
    )
    allow_external_backlog_only_with_synced_runbook = _boolish(
        thresholds.get("allow_external_backlog_only_with_synced_runbook"), default=True
    )
    require_feedback_progress_email_workflow = _boolish(
        thresholds.get("require_feedback_progress_email_workflow"), default=True
    )
    require_feedback_progress_email_e2e_gate = _boolish(
        thresholds.get("require_feedback_progress_email_e2e_gate"), default=True
    )
    require_feedback_progress_email_decision_awards = _boolish(
        thresholds.get("require_feedback_progress_email_decision_awards"), default=True
    )
    required_feedback_progress_sender_email = str(
        thresholds.get("required_feedback_progress_sender_email") or "wageslave@chummer.run"
    ).strip().lower()
    require_feedback_discovery_gateway = _boolish(
        thresholds.get("require_feedback_discovery_gateway"), default=True
    )
    require_feedback_discovery_ltd_registry = _boolish(
        thresholds.get("require_feedback_discovery_ltd_registry"), default=True
    )
    required_feedback_discovery_route = str(
        thresholds.get("required_feedback_discovery_route") or "karma_forge_discovery"
    ).strip()
    required_feedback_discovery_first_part_steps = [
        str(item or "").strip()
        for item in (
            _as_string_list(thresholds.get("required_feedback_discovery_first_part_steps"))
            or ["public_signal", "structured_prescreen", "adaptive_interview"]
        )
        if str(item or "").strip()
    ]
    required_feedback_discovery_tools = [
        str(item or "").strip()
        for item in (
            _as_string_list(thresholds.get("required_feedback_discovery_tools"))
            or [
                "ProductLift",
                "Signitic",
                "FacePop",
                "Deftform",
                "Icanpreneur",
                "Lunacal",
                "MetaSurvey",
                "Teable",
                "NextStep",
                "Product Governor",
                "chummer6-design",
                "Emailit",
            ]
        )
        if str(item or "").strip()
    ]
    release_blocking = _boolish(feedback_loop_gate.get("release_blocking"), default=False)

    workflow_sender_email = str(
        (((feedback_progress_email_workflow.get("delivery_plane") or {}).get("sender_identity") or {}).get("from_email") or "")
    ).strip().lower()
    workflow_stages = {
        str(item.get("id") or "").strip().lower(): dict(item)
        for item in _dict_rows(feedback_progress_email_workflow.get("stages"))
        if str(item.get("id") or "").strip()
    }
    workflow_awards = (
        feedback_progress_email_workflow.get("decision_awards")
        if isinstance(feedback_progress_email_workflow.get("decision_awards"), dict)
        else {}
    )
    workflow_dispatch_contract = (
        (feedback_progress_email_workflow.get("delivery_plane") or {}).get("dispatch_contract")
        if isinstance((feedback_progress_email_workflow.get("delivery_plane") or {}).get("dispatch_contract"), dict)
        else {}
    )
    workflow_e2e_gate = (
        feedback_progress_email_workflow.get("e2e_gate")
        if isinstance(feedback_progress_email_workflow.get("e2e_gate"), dict)
        else {}
    )
    feedback_discovery_plan = (
        support_packets.get("feedback_discovery_plan")
        if isinstance(support_packets.get("feedback_discovery_plan"), dict)
        else {}
    )
    discovery_route_counts = (
        feedback_discovery_plan.get("route_counts")
        if isinstance(feedback_discovery_plan.get("route_counts"), dict)
        else {}
    )
    discovery_candidate_count = _nonnegative_int(feedback_discovery_plan.get("candidate_count"), 0)
    discovery_karma_forge_candidate_count = _nonnegative_int(
        feedback_discovery_plan.get("karma_forge_candidate_count"), 0
    )
    discovery_first_part_routed_count = _nonnegative_int(
        feedback_discovery_plan.get("first_part_routed_count"), 0
    )
    discovery_missing_route_count = _nonnegative_int(feedback_discovery_plan.get("missing_route_count"), 0)
    discovery_missing_next_action_count = _nonnegative_int(
        feedback_discovery_plan.get("missing_next_action_count"), 0
    )
    discovery_ltd_system_ready = _boolish(
        feedback_discovery_plan.get("ltd_discovery_system_ready"), default=False
    )
    discovery_ltd_missing_tools = [
        str(item or "").strip()
        for item in _as_string_list(feedback_discovery_plan.get("ltd_discovery_system_missing_tools"))
        if str(item or "").strip()
    ]
    discovery_required_first_part_steps = {
        str(item or "").strip().lower()
        for item in _as_string_list(feedback_discovery_plan.get("required_first_part_steps"))
        if str(item or "").strip()
    }
    discovery_required_tools = {
        str(item or "").strip().casefold()
        for item in _as_string_list(feedback_discovery_plan.get("required_tools"))
        if str(item or "").strip()
    }
    missing_required_discovery_steps = sorted(
        step
        for step in required_feedback_discovery_first_part_steps
        if step.lower() not in discovery_required_first_part_steps
    )
    missing_required_discovery_tools = sorted(
        tool
        for tool in required_feedback_discovery_tools
        if tool.casefold() not in discovery_required_tools
    )
    required_discovery_route_count = _nonnegative_int(
        discovery_route_counts.get(required_feedback_discovery_route), 0
    )

    reasons: List[str] = []
    if not feedback_loop_gate:
        reasons.append("Feedback loop release gate registry is missing.")
    elif not release_blocking:
        reasons.append("Feedback loop release gate is not marked release-blocking.")
    if not support_generated_at:
        reasons.append("Support-case packets are missing a generated_at timestamp.")
    elif support_generated_age_seconds is None:
        reasons.append("Support-case packets generated_at is unreadable.")
    elif support_generated_age_seconds > max_support_packet_age_hours * 3600:
        reasons.append(
            f"Support-case packets are older than {max_support_packet_age_hours}h; closure truth is stale."
        )
    external_only_support_fallback_ready = (
        bool(support_source_refresh_mode)
        and not allow_cached_packet_refresh_for_gold
        and unresolved_external_requests > 0
        and external_runbook_synced
        and support_open_non_external_packet_count == 0
        and support_closure_waiting_on_release_truth == 0
        and support_update_required_misrouted_case_count == 0
        and support_non_external_needs_human_response_count == 0
        and support_non_external_packets_without_named_owner == 0
        and support_non_external_packets_without_lane == 0
    )
    fresh_zero_backlog_support_mirror_ready = (
        support_source_refresh_mode == "source_mirror_fallback"
        and not allow_cached_packet_refresh_for_gold
        and support_generated_age_seconds is not None
        and support_generated_age_seconds <= max_support_packet_age_hours * 3600
        and support_open_packet_count == 0
        and support_open_non_external_packet_count == 0
        and support_closure_waiting_on_release_truth == 0
        and support_update_required_misrouted_case_count == 0
        and support_non_external_needs_human_response_count == 0
        and support_non_external_packets_without_named_owner == 0
        and support_non_external_packets_without_lane == 0
        and unresolved_external_requests == 0
    )
    if (
        support_source_refresh_mode
        and not allow_cached_packet_refresh_for_gold
        and not external_only_support_fallback_ready
        and not fresh_zero_backlog_support_mirror_ready
    ):
        reasons.append(
            f"Support-case packets are running in {support_source_refresh_mode} mode instead of fresh source truth."
        )
    if support_open_non_external_packet_count > max_open_non_external_packets:
        reasons.append(
            "Non-external open packets still exceed the gold closure budget: "
            f"{support_open_non_external_packet_count} > {max_open_non_external_packets}."
        )
    if support_closure_waiting_on_release_truth > max_closure_waiting_on_release_truth:
        reasons.append(
            "Cases are still waiting on release-truth-backed closure: "
            f"{support_closure_waiting_on_release_truth} > {max_closure_waiting_on_release_truth}."
        )
    if support_update_required_misrouted_case_count > max_update_required_misrouted_cases:
        reasons.append(
            "Update-required cases are still misrouted away from downloads or updater recovery: "
            f"{support_update_required_misrouted_case_count} > {max_update_required_misrouted_cases}."
        )
    if support_non_external_needs_human_response_count > max_non_external_needs_human_response:
        reasons.append(
            "Non-external support backlog still needs a human or grounded response: "
            f"{support_non_external_needs_human_response_count} > {max_non_external_needs_human_response}."
        )
    if require_named_owner_on_non_external_packets and support_non_external_packets_without_named_owner > 0:
        reasons.append(
            f"{support_non_external_packets_without_named_owner} non-external open packets still lack a named owner repo."
        )
    if require_named_lane_on_non_external_packets and support_non_external_packets_without_lane > 0:
        reasons.append(
            f"{support_non_external_packets_without_lane} non-external open packets still lack a concrete next lane."
        )
    if (
        unresolved_external_requests > 0
        and allow_external_backlog_only_with_synced_runbook
        and not external_runbook_synced
    ):
        reasons.append("External-host proof backlog is still open without a synced runbook.")
    if require_feedback_progress_email_workflow and not feedback_progress_email_workflow:
        reasons.append("Feedback progress email workflow registry is missing.")
    if feedback_progress_email_workflow:
        for stage_id in ("request_received", "audited_decision", "fix_available"):
            if stage_id not in workflow_stages:
                reasons.append(f"Feedback progress email workflow is missing the `{stage_id}` stage.")
    if required_feedback_progress_sender_email and workflow_sender_email != required_feedback_progress_sender_email:
        reasons.append(
            "Feedback progress email workflow sender drifted away from the required identity: "
            f"{workflow_sender_email or '(missing)'} != {required_feedback_progress_sender_email}."
        )
    if require_feedback_progress_email_decision_awards and (
        "accepted" not in workflow_awards or "denied" not in workflow_awards
    ):
        reasons.append("Feedback progress email workflow is missing the accepted or denied decision awards.")
    dispatch_required_receipt_fields = {
        str(item or "").strip()
        for item in _as_string_list(workflow_dispatch_contract.get("required_receipt_fields"))
        if str(item or "").strip()
    }
    if feedback_progress_email_workflow:
        if str(workflow_dispatch_contract.get("tool_name") or "").strip() != "connector.dispatch":
            reasons.append("Feedback progress email workflow does not require EA connector.dispatch.")
        if str(workflow_dispatch_contract.get("action_kind") or "").strip() != "delivery.send":
            reasons.append("Feedback progress email workflow does not require delivery.send action kind.")
        if str(workflow_dispatch_contract.get("channel") or "").strip().lower() != "email":
            reasons.append("Feedback progress email workflow does not lock the channel to email.")
        if str(workflow_dispatch_contract.get("preferred_provider") or "").strip().lower() != "emailit":
            reasons.append("Feedback progress email workflow does not require Emailit as the preferred provider.")
        if str(workflow_dispatch_contract.get("required_receipt_state") or "").strip().lower() != "sent":
            reasons.append("Feedback progress email workflow does not require sent receipts.")
        if str(workflow_dispatch_contract.get("required_receipt_transport") or "").strip().lower() != "emailit":
            reasons.append("Feedback progress email workflow does not require Emailit transport receipts.")
        if not {"delivery_id", "stage_id", "case_id", "recipient", "from_email", "subject", "provider"}.issubset(
            dispatch_required_receipt_fields
        ):
            reasons.append("Feedback progress email workflow does not require the full sent-receipt metadata set.")
    if require_feedback_progress_email_e2e_gate:
        if not workflow_e2e_gate:
            reasons.append("Feedback progress email workflow E2E gate is missing.")
        else:
            required_sequence = [
                str(item or "").strip().lower()
                for item in _as_string_list(workflow_e2e_gate.get("required_stage_sequence"))
                if str(item or "").strip()
            ]
            if required_sequence != ["request_received", "audited_decision", "fix_available"]:
                reasons.append("Feedback progress email workflow E2E gate does not require the full staged send sequence.")
            if not _boolish(workflow_e2e_gate.get("fail_closed"), default=False):
                reasons.append("Feedback progress email workflow E2E gate is not fail-closed.")
    if require_feedback_discovery_gateway and not feedback_discovery_plan:
        reasons.append("Feedback discovery gateway plan is missing from support packets.")
    elif require_feedback_discovery_gateway:
        if not _boolish(feedback_discovery_plan.get("workflow_ready"), default=False):
            reasons.append("Feedback discovery gateway workflow is missing or incomplete.")
        if missing_required_discovery_steps:
            reasons.append(
                "Feedback discovery gateway is missing first-part steps: "
                f"{', '.join(missing_required_discovery_steps)}."
            )
        if missing_required_discovery_tools:
            reasons.append(
                "Feedback discovery gateway is missing required tool lanes: "
                f"{', '.join(missing_required_discovery_tools)}."
            )
        if discovery_missing_route_count > 0:
            reasons.append(
                f"Feedback discovery gateway has {discovery_missing_route_count} routed candidates without a route id."
            )
        if discovery_missing_next_action_count > 0:
            reasons.append(
                "Feedback discovery gateway has routed candidates without a concrete next action: "
                f"{discovery_missing_next_action_count}."
            )
        if discovery_candidate_count > 0 and discovery_first_part_routed_count < discovery_candidate_count:
            reasons.append(
                "Feedback discovery gateway has candidates not yet routed into the first-part loop: "
                f"{discovery_first_part_routed_count} < {discovery_candidate_count}."
            )
        if require_feedback_discovery_ltd_registry and not discovery_ltd_system_ready:
            missing_ltd_suffix = (
                f" Missing tools: {', '.join(discovery_ltd_missing_tools)}."
                if discovery_ltd_missing_tools
                else ""
            )
            reasons.append(
                "Feedback discovery gateway is not backed by the LTD discovery system registry."
                f"{missing_ltd_suffix}"
            )
        if (
            required_feedback_discovery_route
            and discovery_karma_forge_candidate_count > 0
            and required_discovery_route_count <= 0
        ):
            reasons.append(
                "Feedback discovery gateway has Karma Forge candidates without the required route "
                f"`{required_feedback_discovery_route}`."
            )

    positives = (
        int(bool(feedback_loop_gate))
        + int(release_blocking)
        + int((not require_feedback_progress_email_workflow) or bool(feedback_progress_email_workflow))
        + int(all(stage_id in workflow_stages for stage_id in ("request_received", "audited_decision", "fix_available")))
        + int(not required_feedback_progress_sender_email or workflow_sender_email == required_feedback_progress_sender_email)
        + int((not require_feedback_progress_email_decision_awards) or ("accepted" in workflow_awards and "denied" in workflow_awards))
        + int(bool(feedback_progress_email_workflow) and str(workflow_dispatch_contract.get("tool_name") or "").strip() == "connector.dispatch")
        + int(bool(feedback_progress_email_workflow) and str(workflow_dispatch_contract.get("action_kind") or "").strip() == "delivery.send")
        + int(bool(feedback_progress_email_workflow) and str(workflow_dispatch_contract.get("channel") or "").strip().lower() == "email")
        + int(bool(feedback_progress_email_workflow) and str(workflow_dispatch_contract.get("preferred_provider") or "").strip().lower() == "emailit")
        + int(bool(feedback_progress_email_workflow) and str(workflow_dispatch_contract.get("required_receipt_state") or "").strip().lower() == "sent")
        + int(bool(feedback_progress_email_workflow) and str(workflow_dispatch_contract.get("required_receipt_transport") or "").strip().lower() == "emailit")
        + int(
            bool(feedback_progress_email_workflow)
            and {"delivery_id", "stage_id", "case_id", "recipient", "from_email", "subject", "provider"}.issubset(
                dispatch_required_receipt_fields
            )
        )
        + int(
            (not require_feedback_progress_email_e2e_gate)
            or (
                bool(workflow_e2e_gate)
                and _boolish(workflow_e2e_gate.get("fail_closed"), default=False)
                and [
                    str(item or "").strip().lower()
                    for item in _as_string_list(workflow_e2e_gate.get("required_stage_sequence"))
                    if str(item or "").strip()
                ]
                == ["request_received", "audited_decision", "fix_available"]
            )
        )
        + int(bool(support_generated_at) and support_generated_age_seconds is not None and support_generated_age_seconds <= max_support_packet_age_hours * 3600)
        + int(
            not support_source_refresh_mode
            or allow_cached_packet_refresh_for_gold
            or external_only_support_fallback_ready
            or fresh_zero_backlog_support_mirror_ready
        )
        + int(support_open_non_external_packet_count <= max_open_non_external_packets)
        + int(support_closure_waiting_on_release_truth <= max_closure_waiting_on_release_truth)
        + int(support_update_required_misrouted_case_count <= max_update_required_misrouted_cases)
        + int(support_non_external_needs_human_response_count <= max_non_external_needs_human_response)
        + int((not require_named_owner_on_non_external_packets) or support_non_external_packets_without_named_owner == 0)
        + int((not require_named_lane_on_non_external_packets) or support_non_external_packets_without_lane == 0)
        + int(unresolved_external_requests == 0 or not allow_external_backlog_only_with_synced_runbook or external_runbook_synced)
        + int((not require_feedback_discovery_gateway) or bool(feedback_discovery_plan))
        + int(
            (not require_feedback_discovery_gateway)
            or _boolish(feedback_discovery_plan.get("workflow_ready"), default=False)
        )
        + int((not require_feedback_discovery_gateway) or not missing_required_discovery_steps)
        + int((not require_feedback_discovery_gateway) or not missing_required_discovery_tools)
        + int((not require_feedback_discovery_gateway) or discovery_missing_route_count == 0)
        + int((not require_feedback_discovery_gateway) or discovery_missing_next_action_count == 0)
        + int(
            (not require_feedback_discovery_gateway)
            or (not require_feedback_discovery_ltd_registry)
            or discovery_ltd_system_ready
        )
        + int(
            (not require_feedback_discovery_gateway)
            or discovery_candidate_count == 0
            or discovery_first_part_routed_count >= discovery_candidate_count
        )
    )
    status, plane = _coverage_entry(
        positives=positives,
        reasons=reasons,
        summary_ready="Feedback, bug, and crash loops are closure-honest and release-truth-backed.",
        summary_missing="Feedback and support closure proof is still incomplete.",
        evidence={
            "registry_path": str(gate_path),
            "registry_present": bool(feedback_loop_gate),
            "release_blocking": release_blocking,
            "feedback_progress_email_workflow_path": str(feedback_progress_email_workflow_path),
            "feedback_progress_email_workflow_present": bool(feedback_progress_email_workflow),
            "feedback_progress_email_sender": workflow_sender_email,
            "feedback_progress_email_stage_ids": sorted(workflow_stages.keys()),
            "feedback_progress_email_award_keys": sorted(str(key).strip().lower() for key in workflow_awards.keys() if str(key).strip()),
            "feedback_progress_email_dispatch_tool": str(workflow_dispatch_contract.get("tool_name") or "").strip(),
            "feedback_progress_email_dispatch_action_kind": str(workflow_dispatch_contract.get("action_kind") or "").strip(),
            "feedback_progress_email_dispatch_channel": str(workflow_dispatch_contract.get("channel") or "").strip(),
            "feedback_progress_email_dispatch_provider": str(workflow_dispatch_contract.get("preferred_provider") or "").strip(),
            "feedback_progress_email_required_receipt_state": str(workflow_dispatch_contract.get("required_receipt_state") or "").strip(),
            "feedback_progress_email_required_receipt_transport": str(workflow_dispatch_contract.get("required_receipt_transport") or "").strip(),
            "feedback_progress_email_required_receipt_fields": sorted(dispatch_required_receipt_fields),
            "feedback_progress_email_e2e_gate_present": bool(workflow_e2e_gate),
            "feedback_discovery_gateway_present": bool(feedback_discovery_plan),
            "feedback_discovery_gateway_ready": bool(
                feedback_discovery_plan
                and _boolish(feedback_discovery_plan.get("workflow_ready"), default=False)
                and not missing_required_discovery_steps
                and not missing_required_discovery_tools
                and discovery_missing_route_count == 0
                and discovery_missing_next_action_count == 0
                and ((not require_feedback_discovery_ltd_registry) or discovery_ltd_system_ready)
                and (
                    discovery_candidate_count == 0
                    or discovery_first_part_routed_count >= discovery_candidate_count
                )
            ),
            "feedback_discovery_candidate_count": discovery_candidate_count,
            "feedback_discovery_karma_forge_candidate_count": discovery_karma_forge_candidate_count,
            "feedback_discovery_first_part_routed_count": discovery_first_part_routed_count,
            "feedback_discovery_missing_route_count": discovery_missing_route_count,
            "feedback_discovery_missing_next_action_count": discovery_missing_next_action_count,
            "feedback_discovery_ltd_registry_path": str(
                feedback_discovery_plan.get("ltd_registry_path") or ""
            ).strip(),
            "feedback_discovery_ltd_registry_key": str(
                feedback_discovery_plan.get("ltd_registry_key") or ""
            ).strip(),
            "feedback_discovery_ltd_product_system": str(
                feedback_discovery_plan.get("ltd_product_system") or ""
            ).strip(),
            "feedback_discovery_ltd_system_ready": discovery_ltd_system_ready,
            "feedback_discovery_ltd_missing_tools": discovery_ltd_missing_tools,
            "feedback_discovery_ltd_tools": [
                str(item or "").strip()
                for item in _as_string_list(feedback_discovery_plan.get("ltd_discovery_system_tools"))
                if str(item or "").strip()
            ],
            "feedback_discovery_route_counts": dict(discovery_route_counts),
            "feedback_discovery_required_first_part_steps": sorted(discovery_required_first_part_steps),
            "feedback_discovery_required_tools": sorted(discovery_required_tools),
            "support_generated_at": support_generated_at,
            "support_generated_age_seconds": support_generated_age_seconds,
            "support_source_refresh_mode": support_source_refresh_mode,
            "support_source_refresh_mode_recovered_from_external_only_backlog": external_only_support_fallback_ready,
            "support_source_refresh_mode_recovered_from_fresh_zero_backlog_mirror": fresh_zero_backlog_support_mirror_ready,
            "support_open_packet_count": support_open_packet_count,
            "support_open_non_external_packet_count": support_open_non_external_packet_count,
            "closure_waiting_on_release_truth": support_closure_waiting_on_release_truth,
            "update_required_misrouted_case_count": support_update_required_misrouted_case_count,
            "non_external_needs_human_response": support_non_external_needs_human_response_count,
            "non_external_packets_without_named_owner": support_non_external_packets_without_named_owner,
            "non_external_packets_without_lane": support_non_external_packets_without_lane,
            "unresolved_external_proof_request_count": unresolved_external_requests,
            "external_proof_runbook_synced": external_runbook_synced,
            "thresholds": {
                "max_support_packet_age_hours": max_support_packet_age_hours,
                "max_open_non_external_packets": max_open_non_external_packets,
                "max_closure_waiting_on_release_truth": max_closure_waiting_on_release_truth,
                "max_update_required_misrouted_cases": max_update_required_misrouted_cases,
                "max_non_external_needs_human_response": max_non_external_needs_human_response,
                "require_named_owner_on_non_external_packets": require_named_owner_on_non_external_packets,
                "require_named_lane_on_non_external_packets": require_named_lane_on_non_external_packets,
                "allow_cached_packet_refresh_for_gold": allow_cached_packet_refresh_for_gold,
                "allow_external_backlog_only_with_synced_runbook": allow_external_backlog_only_with_synced_runbook,
                "require_feedback_progress_email_workflow": require_feedback_progress_email_workflow,
                "require_feedback_progress_email_e2e_gate": require_feedback_progress_email_e2e_gate,
                "require_feedback_progress_email_decision_awards": require_feedback_progress_email_decision_awards,
                "required_feedback_progress_sender_email": required_feedback_progress_sender_email,
                "require_feedback_discovery_gateway": require_feedback_discovery_gateway,
                "require_feedback_discovery_ltd_registry": require_feedback_discovery_ltd_registry,
                "required_feedback_discovery_route": required_feedback_discovery_route,
                "required_feedback_discovery_first_part_steps": required_feedback_discovery_first_part_steps,
                "required_feedback_discovery_tools": required_feedback_discovery_tools,
            },
        },
        hard_fail=not bool(feedback_loop_gate) or not bool(support_generated_at),
    )
    return status, plane


def _candidate_supervisor_roots(preferred_path: Path) -> List[Path]:
    preferred_root = _supervisor_state_root(preferred_path)
    candidates = [preferred_root]
    if _path_is_within(preferred_root, ROOT):
        candidates.extend(
            [
                DEFAULT_SUPERVISOR_STATE.parent,
                DEFAULT_SHARD_SUPERVISOR_ROOT,
            ]
        )
    unique: List[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _candidate_supervisor_state_paths(preferred_path: Path) -> List[Path]:
    candidates: List[Path] = [preferred_path]
    for root in _candidate_supervisor_roots(preferred_path):
        candidates.append(root / "state.json")
        candidates.extend(sorted(root.glob("orphaned-shard-*/state.json")))
        candidates.extend(sorted(root.glob("shard-*/state.json")))
    unique: List[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _supervisor_state_payload_quality(payload: Dict[str, Any], *, path: Path, preferred_path: Path) -> int:
    quality = 0
    mode = str(payload.get("mode") or "").strip().lower()
    preferred_is_aggregate_state = (
        preferred_path.is_file()
        and preferred_path.name == "state.json"
        and not preferred_path.parent.name.startswith("shard-")
        and not preferred_path.parent.name.startswith("orphaned-shard-")
    )
    if path == preferred_path and preferred_is_aggregate_state:
        quality += 8
    if mode:
        quality += 4
    completion_audit = payload.get("completion_audit")
    if isinstance(completion_audit, dict) and completion_audit:
        quality += 3
    focus_profiles = [str(item).strip() for item in (payload.get("focus_profiles") or []) if str(item).strip()]
    if focus_profiles:
        quality += 2
    active_runs = payload.get("active_runs")
    active_runs_count = int(
        payload.get("active_runs_count")
        or (len(active_runs) if isinstance(active_runs, list) else 0)
        or (1 if isinstance(payload.get("active_run"), dict) and payload.get("active_run") else 0)
        or 0
    )
    if active_runs_count > 0:
        quality += 1
    if path.parent.name.startswith("shard-") and quality == 0:
        quality -= 1
    return quality


def _select_best_supervisor_state(preferred_path: Path) -> tuple[Path, Dict[str, Any]]:
    selected_path = preferred_path
    selected_payload = load_json(preferred_path)
    preferred_is_aggregate_state = (
        preferred_path.is_file()
        and preferred_path.name == "state.json"
        and not preferred_path.parent.name.startswith("shard-")
        and not preferred_path.parent.name.startswith("orphaned-shard-")
    )
    preferred_mode = str((selected_payload or {}).get("mode") or "").strip().lower()
    preferred_completion_status = _supervisor_completion_status(selected_payload)
    preferred_updated_at = parse_iso((selected_payload or {}).get("updated_at")) or parse_iso(
        ((selected_payload or {}).get("active_run") or {}).get("started_at")
    )
    preferred_updated_ts = preferred_updated_at.timestamp() if preferred_updated_at is not None else -1.0
    preferred_ready_mode = preferred_mode in {"loop", "sharded", "flagship_product", "complete", "successor_wave"}
    preferred_live_or_current = preferred_completion_status in {"pass", "passed"} and preferred_ready_mode
    selected_score = (-100, -1, -1, -1.0)
    for path in _candidate_supervisor_state_paths(preferred_path):
        payload = load_json(path)
        if not payload:
            continue
        mode = str(payload.get("mode") or "").strip().lower()
        completion_status = _supervisor_completion_status(payload)
        updated_at = parse_iso(payload.get("updated_at")) or parse_iso((payload.get("active_run") or {}).get("started_at"))
        updated_ts = updated_at.timestamp() if updated_at is not None else -1.0
        active_runs = payload.get("active_runs")
        active_runs_count = int(
            payload.get("active_runs_count")
            or (len(active_runs) if isinstance(active_runs, list) else 0)
            or (1 if isinstance(payload.get("active_run"), dict) and payload.get("active_run") else 0)
            or 0
        )
        shard_live_flagship_override = (
            preferred_is_aggregate_state
            and not preferred_live_or_current
            and path.parent.name.startswith("shard-")
            and completion_status in {"pass", "passed"}
            and mode in {"loop", "sharded", "flagship_product", "complete", "successor_wave"}
            and active_runs_count > 0
            and updated_ts >= preferred_updated_ts
        )
        quality = _supervisor_state_payload_quality(payload, path=path, preferred_path=preferred_path)
        score = (
            1 if shard_live_flagship_override else 0,
            quality,
            1 if completion_status in {"pass", "passed"} else 0,
            3 if mode == "complete" else 2 if mode == "flagship_product" else 1 if mode == "loop" else 0,
            updated_ts,
        )
        if score > selected_score:
            selected_path = path
            selected_payload = payload
            selected_score = score
    return selected_path, selected_payload


def _load_active_shards_payload(supervisor_state_path: Path) -> tuple[Path | None, Dict[str, Any]]:
    candidates = []
    for root in _candidate_supervisor_roots(supervisor_state_path):
        candidates.append(root / "active_shards.json")
    return _first_existing_payload(candidates)


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


def load_optional_yaml_with_fallback(primary_path: Path, canonical_path: Path) -> tuple[Path, Dict[str, Any]]:
    primary_payload = load_yaml(primary_path)
    if primary_payload:
        return primary_path, primary_payload
    if canonical_path != primary_path and canonical_path.is_file():
        canonical_payload = load_yaml(canonical_path)
        if canonical_payload:
            return canonical_path, canonical_payload
    return primary_path, {}


def _dict_rows(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _normalize_flagship_parity_release_status(value: Any) -> str:
    return str(value or "").strip().lower()


def _flagship_parity_families(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for family in _dict_rows(registry.get("families")):
        family_id = str(family.get("id") or "").strip()
        if not family_id:
            continue
        rows.append(
            {
                "id": family_id,
                "release_status": _normalize_flagship_parity_release_status(family.get("release_status")),
                "legacy_parity_status": str(family.get("legacy_parity_status") or "").strip().lower(),
                "owner_repos": _as_string_list(family.get("owner_repos")),
                "blocking_gaps": _as_string_list(family.get("blocking_gaps")),
            }
        )
    return rows


def _flagship_parity_status_counts(families: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    counts = {key: 0 for key in FLAGSHIP_PARITY_RELEASE_STATUS_ORDER}
    counts["unknown"] = 0
    for family in families:
        status = _normalize_flagship_parity_release_status(family.get("release_status"))
        if status in counts:
            counts[status] += 1
        else:
            counts["unknown"] += 1
    return counts


def _flagship_parity_family_ids_below(families: Sequence[Dict[str, Any]], minimum_status: str) -> List[str]:
    threshold = FLAGSHIP_PARITY_RELEASE_STATUS_ORDER.get(minimum_status, -1)
    ids: List[str] = []
    for family in families:
        status = _normalize_flagship_parity_release_status(family.get("release_status"))
        if FLAGSHIP_PARITY_RELEASE_STATUS_ORDER.get(status, -1) < threshold:
            family_id = str(family.get("id") or "").strip()
            if family_id:
                ids.append(family_id)
    return sorted(set(ids))


def _summarize_ids(ids: Sequence[str], *, limit: int = 4) -> str:
    values = [str(item).strip() for item in ids if str(item).strip()]
    if not values:
        return ""
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f", +{len(values) - limit} more"


def _summarize_status_gaps(rows: Sequence[Dict[str, Any]], *, limit: int = 4) -> str:
    parts = [
        f"{str(row.get('id') or '').strip()} ({str(row.get('release_status') or '').strip()} < {str(row.get('required_status') or '').strip()})"
        for row in rows
        if str(row.get("id") or "").strip()
    ]
    return _summarize_ids(parts, limit=limit)


def _flagship_parity_status_by_family(families: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    rows: Dict[str, str] = {}
    for family in families:
        family_id = str(family.get("id") or "").strip()
        if not family_id:
            continue
        rows[family_id] = _normalize_flagship_parity_release_status(family.get("release_status"))
    return rows


def _flagship_parity_family_meets(
    status_by_family: Dict[str, str],
    family_id: str,
    minimum_status: str,
) -> bool:
    release_status = _normalize_flagship_parity_release_status(status_by_family.get(family_id))
    return FLAGSHIP_PARITY_RELEASE_STATUS_ORDER.get(release_status, -1) >= FLAGSHIP_PARITY_RELEASE_STATUS_ORDER.get(
        minimum_status,
        -1,
    )


def _flagship_readiness_plane_ids(contract: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for row in _dict_rows(contract.get("planes")):
        plane_id = str(row.get("id") or "").strip()
        if plane_id:
            ids.append(plane_id)
    return sorted(set(ids))


def _parity_lab_readiness_evidence(
    *,
    flagship_families: Sequence[Dict[str, Any]],
    parity_lab_capture_pack: Dict[str, Any],
    veteran_workflow_pack: Dict[str, Any],
) -> Dict[str, Any]:
    status_by_family = _flagship_parity_status_by_family(flagship_families)
    family_target_rows: List[Dict[str, Any]] = []
    family_targets: Dict[str, str] = {}
    invalid_target_family_ids: List[str] = []
    for row in _dict_rows(veteran_workflow_pack.get("families")):
        family_id = str(row.get("id") or "").strip()
        if not family_id:
            continue
        target = _normalize_flagship_parity_release_status(row.get("readiness_target"))
        family_target_rows.append({"id": family_id, "readiness_target": target})
        family_targets[family_id] = target
        if target not in FLAGSHIP_PARITY_RELEASE_STATUS_ORDER:
            invalid_target_family_ids.append(family_id)

    missing_flagship_family_ids = sorted(set(status_by_family) - set(family_targets))
    families_below_target: List[Dict[str, Any]] = []
    for family_id, required_status in sorted(family_targets.items()):
        release_status = status_by_family.get(family_id, "")
        if FLAGSHIP_PARITY_RELEASE_STATUS_ORDER.get(release_status, -1) < FLAGSHIP_PARITY_RELEASE_STATUS_ORDER.get(
            required_status,
            -1,
        ):
            families_below_target.append(
                {
                    "id": family_id,
                    "release_status": release_status or "unknown",
                    "required_status": required_status or "unknown",
                }
            )

    capture_map = (
        parity_lab_capture_pack.get("desktop_non_negotiable_baseline_map")
        if isinstance(parity_lab_capture_pack.get("desktop_non_negotiable_baseline_map"), dict)
        else {}
    )
    capture_coverage_key = str(capture_map.get("coverage_key") or "").strip()
    capture_non_negotiable_ids = sorted(
        {
            str(dict(row).get("non_negotiable_id") or "").strip()
            for row in (capture_map.get("asserted_non_negotiables") or [])
            if str(dict(row).get("non_negotiable_id") or "").strip()
        }
    )
    workflow_non_negotiable_ids = sorted(
        {
            key.strip()
            for key, enabled in dict(veteran_workflow_pack.get("desktop_non_negotiables_asserted") or {}).items()
            if key.strip() and enabled is True
        }
    )
    whole_product_coverage = (
        veteran_workflow_pack.get("whole_product_frontier_coverage")
        if isinstance(veteran_workflow_pack.get("whole_product_frontier_coverage"), dict)
        else {}
    )
    whole_product_coverage_keys = sorted(
        set(_as_string_list(whole_product_coverage.get("package_relevant_coverage_keys")))
    )
    missing_capture_non_negotiable_ids = sorted(
        PARITY_LAB_REQUIRED_NON_NEGOTIABLE_IDS - set(capture_non_negotiable_ids)
    )
    missing_workflow_non_negotiable_ids = sorted(
        PARITY_LAB_REQUIRED_NON_NEGOTIABLE_IDS - set(workflow_non_negotiable_ids)
    )
    missing_whole_product_coverage_keys = sorted(
        PARITY_LAB_REQUIRED_WHOLE_PRODUCT_COVERAGE_KEYS - set(whole_product_coverage_keys)
    )
    ready = bool(parity_lab_capture_pack) and bool(veteran_workflow_pack) and not any(
        (
            not family_target_rows,
            invalid_target_family_ids,
            missing_flagship_family_ids,
            families_below_target,
            missing_capture_non_negotiable_ids,
            missing_workflow_non_negotiable_ids,
            capture_coverage_key != "desktop_client",
            missing_whole_product_coverage_keys,
        )
    )
    return {
        "ready": ready,
        "family_target_count": len(family_target_rows),
        "family_targets": family_target_rows,
        "invalid_target_family_ids": invalid_target_family_ids,
        "missing_flagship_family_ids": missing_flagship_family_ids,
        "families_below_target": families_below_target,
        "capture_coverage_key": capture_coverage_key,
        "capture_coverage_key_matches": capture_coverage_key == "desktop_client",
        "capture_non_negotiable_ids": capture_non_negotiable_ids,
        "workflow_non_negotiable_ids": workflow_non_negotiable_ids,
        "missing_capture_non_negotiable_ids": missing_capture_non_negotiable_ids,
        "missing_workflow_non_negotiable_ids": missing_workflow_non_negotiable_ids,
        "whole_product_coverage_keys": whole_product_coverage_keys,
        "missing_whole_product_coverage_keys": missing_whole_product_coverage_keys,
    }


def _route_job_missing_primary(job: Dict[str, Any]) -> bool:
    primary = job.get("primary_route")
    if not isinstance(primary, dict):
        return True
    return not all(str(primary.get(key) or "").strip() for key in ("repo", "head", "surface"))


def _route_job_has_unbounded_fallback(job: Dict[str, Any]) -> bool:
    fallback_rows = _dict_rows(job.get("fallback_routes"))
    for row in fallback_rows:
        posture = str(row.get("posture") or "").strip().lower()
        condition = str(row.get("condition") or "").strip()
        if posture not in {"bounded_fallback", "compatibility_only", "supporting_surface_only"}:
            return True
        if not condition:
            return True
    return False


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


def aggregate_windows_exit_gate_passed(payload: Dict[str, Any], *, tuple_key: str = "avalonia:win-x64") -> bool:
    if not proof_passed(payload, expected_contract="chummer6-ui.desktop_executable_exit_gate"):
        return False
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    statuses = evidence.get("windows_statuses") if isinstance(evidence.get("windows_statuses"), dict) else {}
    if str(statuses.get(tuple_key) or "").strip().lower() not in {"pass", "passed", "ready"}:
        return False
    gates = evidence.get("windows_gates") if isinstance(evidence.get("windows_gates"), dict) else {}
    gate = gates.get(tuple_key) if isinstance(gates.get(tuple_key), dict) else {}
    return bool(gate.get("embedded_payload_marker_present")) and bool(gate.get("embedded_sample_marker_present"))


def _as_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _reason_is_external_proof_request(reason: str) -> bool:
    return "external proof request:" in str(reason or "").strip().lower()


def _release_proof_passed_journeys(release_proof: Dict[str, Any]) -> set[str]:
    if not proof_passed(release_proof):
        return set()
    return {
        str(item).strip()
        for item in (release_proof.get("journeysPassed") or [])
        if str(item).strip()
    }


def _journey_local_reason_is_desktop_scoped(row: Dict[str, str]) -> bool:
    category_id = str(row.get("category_id") or "").strip().lower()
    if category_id.startswith("desktop_") or category_id.startswith("linux_blazor_desktop_"):
        return True
    evidence_path = str(row.get("evidence_path") or "").strip().lower()
    if "desktop_executable_exit_gate.generated.json" in evidence_path:
        return True
    reason = str(row.get("reason") or "").strip().lower()
    return any(
        token in reason
        for token in (
            "desktop_executable_exit_gate.generated.json",
            "desktoptuplecoverage",
            "desktop install media",
            "missing required marker",
            "local_blocking_findings_count",
            "linux_gate:blazor-desktop:linux-x64",
            "evidence.receipt_scope",
            "within_repo_root",
            "startup smoke",
            "promoted head",
            "promoted installer",
            "desktop tuples",
            "desktop tuple",
            "installer bytes",
        )
    )


def _journey_is_desktop_scoped_blocked(
    journey_id: str,
    journey_row: Dict[str, Any],
    *,
    ui_executable_exit_gate: Optional[Dict[str, Any]] = None,
    release_channel: Optional[Dict[str, Any]] = None,
) -> bool:
    state = str(journey_row.get("state") or "").strip().lower()
    if state in {"", "ready"}:
        return False

    local_rows = _journey_local_reasons(
        journey_id,
        journey_row,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
    )
    if any(not _journey_local_reason_is_desktop_scoped(row) for row in local_rows):
        return False

    external_requests = [
        dict(item)
        for item in (journey_row.get("external_proof_requests") or [])
        if isinstance(item, dict)
    ]
    external_blockers = [
        str(item).strip().lower()
        for item in (journey_row.get("external_blocking_reasons") or [])
        if str(item).strip()
    ]
    if any(
        not any(
            token in blocker
            for token in (
                "desktoptuplecoverage",
                "desktop tuple",
                "desktop install",
                "startup-smoke",
                "startup smoke",
                "platform-head",
                "platform head",
            )
        )
        for blocker in external_blockers
    ):
        return False

    if any(not _external_request_tuple_id(request) for request in external_requests):
        return False

    return bool(local_rows or external_blockers or external_requests)


def _sanitize_route_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    token = token.strip("-")
    return token or "unowned"


def _desktop_ui_local_blocker_family(reason: str) -> str:
    normalized = str(reason or "").strip().lower()
    if not normalized:
        return "desktop_ui_local_blocker"
    if "desktoptuplecoverage.externalproofrequests" in normalized or "proofcapturecommands" in normalized:
        return "desktop_tuple_external_proof_command_drift"
    if "missing-tuple external proof contract" in normalized:
        return "desktop_tuple_external_proof_contract_drift"
    if "blazor-desktop" in normalized and "stage unit_tests failed" in normalized:
        return "linux_blazor_desktop_unit_tests"
    if "blazor-desktop" in normalized and "runtime unit tests" in normalized:
        return "linux_blazor_desktop_runtime_tests"
    if "blazor-desktop" in normalized and "archive startup smoke" in normalized:
        return "linux_blazor_desktop_archive_startup_smoke"
    if "blazor-desktop" in normalized and "installer startup smoke" in normalized:
        return "linux_blazor_desktop_installer_startup_smoke"
    if "blazor-desktop" in normalized and any(
        marker in normalized
        for marker in (
            "install_launch_capture_path",
            "install_wrapper_capture_path",
            "install_desktop_entry_capture_path",
            "install_verification_path",
            "artifactdigest does not match",
            "readycheckpoint is not",
            "receipt path is missing",
            "receipt timestamp is missing",
            "receipt status is not",
            "receipt headid does not match",
            "receipt platform is not",
            "receipt rid is missing",
            "receipt hostclass is missing",
            "receipt operatingsystem is missing",
            "receipt channelid does not match",
            "receipt is missing version",
            "receipt arch does not match",
        )
    ):
        return "linux_blazor_desktop_receipt_contract"
    return "desktop_ui_local_blocker"


def _journey_local_reasons(
    journey_id: str,
    journey_row: Dict[str, Any],
    *,
    ui_executable_exit_gate: Optional[Dict[str, Any]] = None,
    release_channel: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    has_explicit_local_reasons = "local_blocking_reasons" in journey_row
    local_reasons = _as_string_list(journey_row.get("local_blocking_reasons"))
    if not local_reasons and not has_explicit_local_reasons:
        local_reasons = [
            reason
            for reason in _as_string_list(journey_row.get("blocking_reasons"))
            if not _reason_is_external_proof_request(reason)
        ]

    rows = [{"reason": reason, "category_id": "", "evidence_path": ""} for reason in local_reasons if reason]
    if journey_id != "install_claim_restore_continue" or not ui_executable_exit_gate:
        return rows

    ui_local_findings = _as_string_list(
        ui_executable_exit_gate.get("local_blocking_findings")
        or ui_executable_exit_gate.get("localBlockingFindings")
    )
    if not ui_local_findings:
        return rows
    ui_local_findings = _effective_desktop_executable_gate_local_blockers(
        ui_executable_exit_gate,
        release_channel=release_channel or {},
    )

    executable_gate_path = str(
        (ui_executable_exit_gate.get("evidence") or {}).get("ui_executable_exit_gate_path")
        or (ui_executable_exit_gate.get("evidence") or {}).get("executable_gate_path")
        or ""
    ).strip()
    if not executable_gate_path:
        executable_gate_path = ".codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"

    generic_gate_reasons = {
        reason
        for reason in local_reasons
        if "desktop_executable_exit_gate.generated.json" in reason.lower()
        or "local_blocking_findings_count" in reason.lower()
    }
    if not generic_gate_reasons:
        return rows

    expanded_rows = [
        row
        for row in rows
        if row["reason"] not in generic_gate_reasons
    ]
    if not ui_local_findings:
        return expanded_rows
    expanded_rows.extend(
        {
            "reason": reason,
            "category_id": _desktop_ui_local_blocker_family(reason),
            "evidence_path": executable_gate_path,
        }
        for reason in ui_local_findings
    )
    return expanded_rows


def _journey_local_blocker_routes(
    journeys: Dict[str, Dict[str, Any]],
    *,
    ui_executable_exit_gate: Optional[Dict[str, Any]] = None,
    release_channel: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    routes: List[Dict[str, Any]] = []
    unrouted_reasons: List[str] = []
    owner_repo_counts: Dict[str, int] = {}
    journey_local_blocker_counts: Dict[str, int] = {}
    dedupe_keys: set[str] = set()

    for journey_id, journey_row in journeys.items():
        if not isinstance(journey_row, dict):
            continue
        owner_repos = _as_string_list(journey_row.get("owner_repos"))
        local_reason_rows = _journey_local_reasons(
            journey_id,
            journey_row,
            ui_executable_exit_gate=ui_executable_exit_gate,
            release_channel=release_channel,
        )
        if not local_reason_rows:
            continue
        journey_local_blocker_counts[journey_id] = len(local_reason_rows)
        for index, row in enumerate(local_reason_rows):
            reason = str(row.get("reason") or "").strip()
            category_id = str(row.get("category_id") or "").strip()
            dedupe_key = f"{journey_id}|{reason}"
            if dedupe_key in dedupe_keys:
                continue
            dedupe_keys.add(dedupe_key)
            repo = ""
            evidence_path = str(row.get("evidence_path") or "").strip()
            match = REPO_PROOF_REASON_RE.search(reason)
            if match:
                repo = str(match.group("repo") or "").strip()
                evidence_path = evidence_path or str(match.group("path") or "").strip()
            if not repo and owner_repos:
                repo = owner_repos[0]
            route_owner = repo
            if not route_owner:
                unrouted_reasons.append(reason)
                continue
            owner_repo_counts[route_owner] = int(owner_repo_counts.get(route_owner) or 0) + 1
            route_hash = hashlib.sha1(f"{journey_id}|{reason}".encode("utf-8")).hexdigest()[:12]
            package_id = (
                f"autofix-{_sanitize_route_token(journey_id)}-"
                f"{_sanitize_route_token(route_owner)}-{index + 1}"
            )
            routes.append(
                {
                    "route_id": f"route-{route_hash}",
                    "journey_id": journey_id,
                    "journey_state": str(journey_row.get("state") or "").strip(),
                    "owner_repo": route_owner,
                    "primary_lane": "repo_fix",
                    "package_id": package_id,
                    "category_id": category_id,
                    "evidence_path": evidence_path,
                    "reason": reason,
                }
            )

    routes.sort(
        key=lambda row: (
            str(row.get("owner_repo") or ""),
            str(row.get("journey_id") or ""),
            str(row.get("route_id") or ""),
        )
    )
    total_local_blocker_count = int(sum(journey_local_blocker_counts.values()))
    routed_local_blocker_count = len(routes)
    unrouted_local_blocker_count = max(0, total_local_blocker_count - routed_local_blocker_count)
    return {
        "total_local_blocker_count": total_local_blocker_count,
        "routed_local_blocker_count": routed_local_blocker_count,
        "unrouted_local_blocker_count": unrouted_local_blocker_count,
        "journey_local_blocker_counts": journey_local_blocker_counts,
        "owner_repo_counts": owner_repo_counts,
        "routes": routes,
        "unrouted_reasons": unrouted_reasons,
    }


def _effective_journey_readiness(
    journey_id: str,
    journey_row: Dict[str, Any],
    *,
    release_proof: Optional[Dict[str, Any]] = None,
    ui_executable_exit_gate: Optional[Dict[str, Any]] = None,
    release_channel: Optional[Dict[str, Any]] = None,
    ignore_nonlinux_platform_host_blockers: bool = False,
) -> Dict[str, Any]:
    state = str(journey_row.get("state") or "").strip()
    local_reason_rows = _journey_local_reasons(
        journey_id,
        journey_row,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
    )
    local_reasons = [
        str(row.get("reason") or "").strip()
        for row in local_reason_rows
        if str(row.get("reason") or "").strip()
    ]
    external_blockers = _as_string_list(journey_row.get("external_blocking_reasons"))
    external_proof_requests = [
        dict(item)
        for item in (journey_row.get("external_proof_requests") or [])
        if isinstance(item, dict)
    ]
    filtered_external_proof_requests = _filter_external_proof_requests(
        external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_platform_host_blockers,
    )
    has_relevant_external_blockers = _has_relevant_external_blockers(
        external_blockers,
        external_proof_requests=external_proof_requests,
        filtered_external_proof_requests=filtered_external_proof_requests,
        ignore_nonlinux_platform_host_blockers=ignore_nonlinux_platform_host_blockers,
    )
    release_proof_override = journey_id in _release_proof_passed_journeys(release_proof or {})
    effective_external_only = state == "blocked" and not local_reasons and has_relevant_external_blockers
    effective_state = "ready" if state == "ready" or release_proof_override or effective_external_only else state
    return {
        "state": state,
        "effective_state": effective_state,
        "release_proof_override": release_proof_override,
        "effective_external_only": effective_external_only,
        "local_reason_count": len(local_reasons),
        "local_reasons": local_reasons,
        "external_proof_request_count": len(filtered_external_proof_requests),
        "has_relevant_external_blockers": has_relevant_external_blockers,
    }


def _owner_scoped_journey_effective_readiness(
    journey_id: str,
    effective_readiness: Dict[str, Any],
    *,
    journey_local_blocker_counts: Dict[str, int],
    journey_local_blocker_route_rows: Sequence[Dict[str, Any]],
    coverage_owner_repos: Sequence[str],
) -> Dict[str, Any]:
    base_state = str(effective_readiness.get("effective_state") or effective_readiness.get("state") or "").strip()
    total_local_blocker_count = int(journey_local_blocker_counts.get(journey_id) or 0)
    journey_routes = [
        dict(row)
        for row in journey_local_blocker_route_rows
        if isinstance(row, dict) and str(row.get("journey_id") or "").strip() == journey_id
    ]
    routed_local_blocker_count = len(journey_routes)
    coverage_owner_repo_keys = {
        str(item).strip().lower()
        for item in coverage_owner_repos
        if str(item).strip()
    }
    routed_owner_repos = sorted(
        {
            str(row.get("owner_repo") or "").strip()
            for row in journey_routes
            if str(row.get("owner_repo") or "").strip()
        }
    )
    coverage_owner_routed_blocker_count = sum(
        1
        for row in journey_routes
        if str(row.get("owner_repo") or "").strip().lower() in coverage_owner_repo_keys
    )
    unrelated_routed_local_only = (
        base_state == "blocked"
        and total_local_blocker_count > 0
        and routed_local_blocker_count >= total_local_blocker_count
        and coverage_owner_routed_blocker_count == 0
        and int(effective_readiness.get("local_reason_count") or 0) > 0
        and int(effective_readiness.get("external_proof_request_count") or 0) == 0
        and not bool(effective_readiness.get("has_relevant_external_blockers"))
    )
    owner_scoped_effective_state = "ready" if base_state == "ready" or unrelated_routed_local_only else base_state
    result = dict(effective_readiness)
    result.update(
        {
            "owner_scoped_effective_state": owner_scoped_effective_state,
            "owner_scoped_unrelated_routed_local_only": unrelated_routed_local_only,
            "owner_scoped_coverage_owner_repos": sorted(coverage_owner_repo_keys),
            "owner_scoped_total_local_blocker_count": total_local_blocker_count,
            "owner_scoped_routed_local_blocker_count": routed_local_blocker_count,
            "owner_scoped_coverage_owner_routed_blocker_count": coverage_owner_routed_blocker_count,
            "owner_scoped_routed_owner_repos": routed_owner_repos,
        }
    )
    return result


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


def _visual_evidence_status(visual_evidence: Dict[str, Any], canonical_key: str) -> str:
    legacy_statuses = (
        visual_evidence.get("required_legacy_interaction_key_statuses")
        if isinstance(visual_evidence.get("required_legacy_interaction_key_statuses"), dict)
        else {}
    )
    for key in DESKTOP_VISUAL_FAMILIARITY_SEMANTIC_KEY_ALIASES.get(canonical_key, (canonical_key,)):
        raw = legacy_statuses.get(key)
        if raw not in (None, ""):
            return str(raw).strip().lower()
        raw = visual_evidence.get(key)
        if raw not in (None, ""):
            return str(raw).strip().lower()
    return ""


def _milestone2_visual_requirement_semantically_satisfied(
    visual_evidence: Dict[str, Any], canonical_test: str
) -> bool:
    required_keys = DESKTOP_VISUAL_FAMILIARITY_HARD_BAR_SEMANTIC_REQUIREMENTS.get(canonical_test, ())
    if not required_keys:
        return False
    return all(_status_or_bool_ok(_visual_evidence_status(visual_evidence, key)) for key in required_keys)


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


def _reason_targets_sr4_sr6_workflow_oracle_backlog(reason: str) -> bool:
    normalized = str(reason or "").strip().lower()
    if not normalized:
        return False
    if "missing_api_surface_contract" in normalized:
        return True
    if "workflow execution receipts currently require a chummer-api host" in normalized:
        return True
    return False


def _desktop_parity_receipt_is_external_only_missing_api_surface_contract(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        if evidence.get("failingParityReceiptsExternalOnly") is True:
            external_failures = evidence.get("failingParityReceiptsExternal")
            if isinstance(external_failures, dict) and external_failures:
                failure_tokens = [
                    str(item).strip().lower()
                    for values in external_failures.values()
                    if isinstance(values, list)
                    for item in values
                    if str(item).strip()
                ]
                if bool(failure_tokens) and all(
                    "external_blocker=missing_api_surface_contract" in token
                    for token in failure_tokens
                ):
                    return True
        failing_receipts = evidence.get("failingParityReceipts")
        if isinstance(failing_receipts, dict) and failing_receipts:
            failure_tokens = [
                str(item).strip().lower()
                for values in failing_receipts.values()
                if isinstance(values, list)
                for item in values
                if str(item).strip()
            ]
            if bool(failure_tokens) and all(
                "external_blocker=missing_api_surface_contract" in token
                for token in failure_tokens
            ):
                return True
    reason_tokens = []
    if str(payload.get("reason") or "").strip():
        reason_tokens.append(str(payload.get("reason")).strip().lower())
    reason_tokens.extend(
        str(item).strip().lower()
        for item in (payload.get("reasons") or [])
        if str(item).strip()
    )
    return bool(reason_tokens) and all(
        _reason_targets_sr4_sr6_workflow_oracle_backlog(token)
        for token in reason_tokens
    )


def _release_channel_external_proof_contract_ready(release_channel: Dict[str, Any]) -> bool:
    if not isinstance(release_channel, dict):
        return False
    tuple_coverage = (
        release_channel.get("desktopTupleCoverage")
        if isinstance(release_channel.get("desktopTupleCoverage"), dict)
        else {}
    )
    if not tuple_coverage:
        return False
    required_tuples = {
        str(item).strip().lower()
        for item in (tuple_coverage.get("missingRequiredPlatformHeadRidTuples") or [])
        if str(item).strip()
    }
    requests = tuple_coverage.get("externalProofRequests")
    if not isinstance(requests, list):
        return False
    request_tuples = {
        str(item.get("tupleId") or "").strip().lower()
        for item in requests
        if isinstance(item, dict) and str(item.get("tupleId") or "").strip()
    }
    if not request_tuples:
        return False
    if required_tuples and request_tuples != required_tuples:
        return False
    for item in requests:
        if not isinstance(item, dict):
            return False
        if not str(item.get("expectedArtifactId") or "").strip():
            return False
        if not str(item.get("expectedInstallerFileName") or "").strip():
            return False
        if not str(item.get("expectedPublicInstallRoute") or "").strip():
            return False
        if not str(item.get("expectedStartupSmokeReceiptPath") or "").strip():
            return False
        if not str(item.get("expectedInstallerSha256") or "").strip():
            return False
        if not isinstance(item.get("startupSmokeReceiptContract"), dict):
            return False
        if not isinstance(item.get("proofCaptureCommands"), list) or not [
            str(command).strip() for command in item.get("proofCaptureCommands") if str(command).strip()
        ]:
            return False
    return True


def _effective_desktop_executable_gate_local_blockers(
    ui_executable_exit_gate: Dict[str, Any],
    *,
    release_channel: Dict[str, Any],
) -> List[str]:
    raw_local_blockers = ui_executable_exit_gate.get("local_blocking_findings")
    if not isinstance(raw_local_blockers, list):
        raw_local_blockers = ui_executable_exit_gate.get("localBlockingFindings")
    local_blockers = [str(item).strip() for item in (raw_local_blockers or []) if str(item).strip()]
    if not local_blockers:
        return []

    tuple_coverage = (
        release_channel.get("desktopTupleCoverage")
        if isinstance(release_channel.get("desktopTupleCoverage"), dict)
        else {}
    )
    required_heads = {
        str(item).strip().lower()
        for item in (tuple_coverage.get("requiredDesktopHeads") or [])
        if str(item).strip()
    }
    release_channel_external_contract_ready = _release_channel_external_proof_contract_ready(release_channel)

    effective: List[str] = []
    for reason in local_blockers:
        normalized = reason.lower()
        if required_heads and "blazor-desktop" in normalized and "blazor-desktop" not in required_heads:
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


def _reason_targets_rules_engine_and_import_scope(reason: str) -> bool:
    normalized = str(reason or "").strip().lower()
    if not normalized:
        return False
    if "chummer6-core:" in normalized or "chummer-core-engine:" in normalized:
        return True
    if any(
        marker in normalized
        for marker in (
            "chummer.infrastructure/xml/xmltoolcatalogservice.cs",
            "chummer.tests/apiintegrationtests.cs",
            "chummer.coreengine.tests/program.cs",
            "engine_proof_pack.generated.json",
            "import_parity_certification.generated.json",
            "import-oracle",
            "import oracle",
            "rules/import",
        )
    ):
        return True
    return _reason_targets_sr4_sr6_workflow_oracle_backlog(normalized)


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


def _support_packet_external_proof_requests(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    requests: List[Dict[str, Any]] = []
    packets = payload.get("packets")
    if isinstance(packets, list):
        for packet in packets:
            if not isinstance(packet, dict):
                continue
            install_diagnosis = packet.get("install_diagnosis")
            if not isinstance(install_diagnosis, dict):
                continue
            request = install_diagnosis.get("external_proof_request")
            if isinstance(request, dict):
                requests.append(dict(request))

    unresolved_specs = payload.get("unresolved_external_proof_request_specs")
    if not isinstance(unresolved_specs, dict):
        summary = payload.get("summary")
        if isinstance(summary, dict):
            unresolved_specs = summary.get("unresolved_external_proof_request_specs")
    if isinstance(unresolved_specs, dict):
        for tuple_id, request in unresolved_specs.items():
            if not isinstance(request, dict):
                continue
            request_row = dict(request)
            if not str(request_row.get("tuple_id") or request_row.get("tupleId") or "").strip():
                request_row["tuple_id"] = str(tuple_id or "").strip()
            requests.append(request_row)

    deduped, _ = _dedupe_external_proof_requests(requests)
    return deduped


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


def _user_journey_tester_workflow_id(row: Dict[str, Any]) -> str:
    return str(row.get("id") or row.get("workflow_id") or row.get("workflowId") or row.get("name") or "").strip()


def _user_journey_tester_workflow_status(row: Dict[str, Any]) -> str:
    return str(row.get("status") or row.get("result") or row.get("state") or "").strip().lower()


def _user_journey_tester_workflow_screenshots(row: Dict[str, Any]) -> List[str]:
    for key in ("screenshots", "screenshot_paths", "screenshotPaths"):
        value = row.get(key)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
    return []


def _user_journey_tester_workflow_screenshot_count(row: Dict[str, Any]) -> int:
    return len(_user_journey_tester_workflow_screenshots(row))


def _user_journey_tester_workflow_screenshot_review_ok(row: Dict[str, Any]) -> bool:
    review_rows = _dict_rows(row.get("screenshotReview")) or _dict_rows(row.get("screenshot_review"))
    if len(review_rows) < USER_JOURNEY_TESTER_MIN_SCREENSHOTS_PER_WORKFLOW:
        return False
    for review_row in review_rows:
        if review_row.get("exists") is not True:
            return False
        if review_row.get("is_png") is not True and review_row.get("isPng") is not True:
            return False
        if review_row.get("within_repo_root") is not True and review_row.get("withinRepoRoot") is not True:
            return False
    return True


def _user_journey_tester_missing_assertions(workflow_id: str, row: Dict[str, Any]) -> List[str]:
    assertions = row.get("assertions")
    if not isinstance(assertions, dict):
        assertions = {}
    return [
        assertion
        for assertion in USER_JOURNEY_TESTER_REQUIRED_WORKFLOW_ASSERTIONS.get(workflow_id, ())
        if assertions.get(assertion) is not True
    ]


def _user_journey_tester_binary_target_ok(evidence: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    if bool(evidence.get("linux_binary_under_test")) or bool(payload.get("linux_binary_under_test")):
        return True
    if bool(evidence.get("actual_binary_under_test")) or bool(payload.get("actual_binary_under_test")):
        target_text = " ".join(
            [
                str(evidence.get("binary_under_test") or ""),
                str(evidence.get("run_target") or ""),
                str(payload.get("binary_under_test") or ""),
                str(payload.get("run_target") or ""),
            ]
        ).lower()
        return "linux" in target_text or not target_text.strip()
    target_text = " ".join(
        [
            str(evidence.get("binary_under_test") or ""),
            str(evidence.get("run_target") or ""),
            str(payload.get("binary_under_test") or ""),
            str(payload.get("run_target") or ""),
        ]
    ).lower()
    return "linux" in target_text and any(token in target_text for token in ("binary", "executable", "bin", "appimage"))


def user_journey_tester_audit_gaps(payload: Dict[str, Any]) -> Dict[str, Any]:
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    workflow_rows = _dict_rows(evidence.get("workflows")) or _dict_rows(payload.get("workflows"))
    by_id = {
        workflow_id: row
        for row in workflow_rows
        if (workflow_id := _user_journey_tester_workflow_id(row))
    }
    missing_workflows = sorted(
        workflow_id
        for workflow_id in USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS
        if workflow_id not in by_id
    )
    nonpassing_workflows = sorted(
        workflow_id
        for workflow_id in USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS
        if workflow_id in by_id
        and _user_journey_tester_workflow_status(by_id[workflow_id]) not in {"pass", "passed", "ready"}
    )
    insufficient_screenshot_workflows = sorted(
        workflow_id
        for workflow_id in USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS
        if workflow_id in by_id
        and _user_journey_tester_workflow_screenshot_count(by_id[workflow_id])
        < USER_JOURNEY_TESTER_MIN_SCREENSHOTS_PER_WORKFLOW
    )
    counter_only_screenshot_workflows = sorted(
        workflow_id
        for workflow_id in USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS
        if workflow_id in by_id
        and not _user_journey_tester_workflow_screenshots(by_id[workflow_id])
        and (
            "screenshot_count" in by_id[workflow_id]
            or "screenshotCount" in by_id[workflow_id]
        )
    )
    unverified_screenshot_workflows = sorted(
        workflow_id
        for workflow_id in USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS
        if workflow_id in by_id
        and not _user_journey_tester_workflow_screenshot_review_ok(by_id[workflow_id])
    )
    missing_workflow_assertions = {
        workflow_id: missing_assertions
        for workflow_id in USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS
        if workflow_id in by_id
        if (missing_assertions := _user_journey_tester_missing_assertions(workflow_id, by_id[workflow_id]))
    }
    open_blocking_findings_count = _nonnegative_int(
        evidence.get("open_blocking_findings_count", payload.get("open_blocking_findings_count", 0)),
        0,
    )
    used_internal_apis = evidence.get("used_internal_apis", payload.get("used_internal_apis"))
    fix_shard_separate = evidence.get("fix_shard_separate", payload.get("fix_shard_separate"))
    missing_execution_discipline: List[str] = []
    if not _user_journey_tester_binary_target_ok(evidence, payload):
        missing_execution_discipline.append("linux_binary_under_test")
    if used_internal_apis is not False:
        missing_execution_discipline.append("used_internal_apis_false")
    if fix_shard_separate is not True:
        missing_execution_discipline.append("fix_shard_separate_true")
    if open_blocking_findings_count > 0:
        missing_execution_discipline.append("no_open_blocking_findings")
    if counter_only_screenshot_workflows:
        missing_execution_discipline.append("workflow_screenshots_must_be_paths_not_counters")
    if unverified_screenshot_workflows:
        missing_execution_discipline.append("workflow_screenshot_review_must_prove_existing_pngs")
    if missing_workflow_assertions:
        missing_execution_discipline.append("workflow_assertions_must_prove_visible_user_results")
    return {
        "required_workflows": list(USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS),
        "required_workflow_assertions": {
            key: list(value)
            for key, value in USER_JOURNEY_TESTER_REQUIRED_WORKFLOW_ASSERTIONS.items()
        },
        "workflow_count": len(workflow_rows),
        "missing_workflows": missing_workflows,
        "nonpassing_workflows": nonpassing_workflows,
        "insufficient_screenshot_workflows": insufficient_screenshot_workflows,
        "counter_only_screenshot_workflows": counter_only_screenshot_workflows,
        "unverified_screenshot_workflows": unverified_screenshot_workflows,
        "missing_workflow_assertions": missing_workflow_assertions,
        "open_blocking_findings_count": open_blocking_findings_count,
        "missing_execution_discipline": missing_execution_discipline,
        "ready": not (
            missing_workflows
            or nonpassing_workflows
            or insufficient_screenshot_workflows
            or counter_only_screenshot_workflows
            or unverified_screenshot_workflows
            or missing_workflow_assertions
            or missing_execution_discipline
        ),
    }


def _workflow_receipts_are_sr4_sr6_only(receipts: List[str]) -> bool:
    normalized = [str(item).strip().lower() for item in receipts if str(item).strip()]
    if not normalized:
        return False
    return all(("sr4" in item) or ("sr6" in item) for item in normalized)


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
    for key, age_seconds in parsed_ages.items():
        allow_stale_flag_key = key.replace("proof_age_seconds", "proof_stale_pass_receipt_allowed")
        allow_stale_pass_receipt = bool(evidence.get(allow_stale_flag_key))
        if (
            key == "flagship UI release gate proof_age_seconds"
            and not allow_stale_pass_receipt
            and parsed_ages.get("desktop workflow execution gate proof_age_seconds", max_age_seconds + 1) <= max_age_seconds
            and parsed_ages.get("desktop visual familiarity gate proof_age_seconds", max_age_seconds + 1) <= max_age_seconds
            and str(payload.get("status") or "").strip().lower() in {"pass", "passed", "ready"}
        ):
            allow_stale_pass_receipt = True
        if age_seconds > max_age_seconds and not allow_stale_pass_receipt:
            issues.append(
                f"Executable gate freshness evidence '{key}' is stale ({age_seconds}s old; max {max_age_seconds}s)."
            )
    return parsed_ages, issues


def _visual_gate_stale_capture_only(
    payload: Dict[str, Any],
) -> bool:
    if not isinstance(payload, dict):
        return False
    reasons = [
        str(item).strip()
        for item in (payload.get("reasons") or [])
        if str(item).strip()
    ]
    if not reasons:
        return False
    allowed_prefixes = (
        "visual familiarity screenshots are missing:",
        "visual familiarity screenshots are stale:",
    )
    if any(not reason.lower().startswith(allowed_prefixes) for reason in reasons):
        return False
    reviews = payload.get("reviews")
    if not isinstance(reviews, dict) or not reviews:
        return False
    screen_capture_review = reviews.get("screenCaptureReview")
    if not isinstance(screen_capture_review, dict):
        return False
    if str(screen_capture_review.get("status") or "").strip().lower() not in {"fail", "failed"}:
        return False
    for review_name, review_payload in reviews.items():
        if review_name == "screenCaptureReview":
            continue
        if not isinstance(review_payload, dict):
            return False
        if str(review_payload.get("status") or "").strip().lower() not in {"pass", "passed", "ready"}:
            return False
    return True


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


DESKTOP_SR4_SR6_ORACLE_NOTE = (
    "Executable desktop workflow execution gate is limited by SR4/SR6 workflow-oracle backlog; "
    "desktop shell and installer proof stay tracked separately."
)


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


def _ooda_live_active_progress(ooda_state: Dict[str, Any]) -> bool:
    try:
        active_runs_count = int(ooda_state.get("active_runs_count") or 0)
    except (TypeError, ValueError):
        active_runs_count = 0
    shards = ooda_state.get("active_shards") or ooda_state.get("last_observed_shards") or []
    if active_runs_count <= 0 and (not isinstance(shards, list) or not shards):
        return False
    if not isinstance(shards, list):
        return False

    live_modes = {"loop", "sharded", "flagship_product", "successor_wave"}
    for shard in shards:
        if not isinstance(shard, dict) or not bool(shard.get("active_run")):
            continue
        mode = str(shard.get("mode") or "").strip().lower()
        if mode not in live_modes:
            continue
        updated_at = (
            parse_iso(shard.get("worker_last_output_at"))
            or parse_iso(shard.get("updated_at"))
            or parse_iso(shard.get("started_at"))
        )
        if (
            updated_at is not None
            and (utc_now() - updated_at).total_seconds() <= FLAGSHIP_OPERATOR_SUPERVISOR_MAX_AGE_HOURS * 3600
        ):
            return True
    return False


def _recover_ooda_state_from_active_shards(
    active_shards_payload: Dict[str, Any],
    *,
    active_shards_recent: bool,
) -> Dict[str, Any]:
    if not active_shards_recent or not isinstance(active_shards_payload, dict) or not active_shards_payload:
        return {}
    shards = active_shards_payload.get("active_shards")
    if not isinstance(shards, list):
        return {}
    recovery_source = "active_shards"
    if not shards:
        configured_shards = active_shards_payload.get("configured_shards")
        if not isinstance(configured_shards, list) or not configured_shards:
            return {}
        shards = configured_shards
        recovery_source = "configured_shard_topology"
    return {
        "controller": "up",
        "supervisor": "up",
        "aggregate_stale": False,
        "aggregate_timestamp_stale": False,
        "last_observed_shards": shards,
        "frontier_ids": active_shards_payload.get("frontier_ids") or [],
        "steady_complete_quiet": False,
        "recovered_from_active_shards": True,
        "recovery_source": recovery_source,
    }


def build_flagship_product_readiness_payload(
    *,
    acceptance_path: Path,
    parity_registry_path: Path,
    feedback_loop_gate_path: Path,
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
    ui_element_parity_audit_path: Path | None = None,
    ui_user_journey_tester_audit_path: Path | None = None,
    m136_aggregate_readiness_gate_path: Path = DEFAULT_M136_AGGREGATE_READINESS_GATE,
    ignore_nonlinux_desktop_host_proof_blockers: bool = False,
) -> Dict[str, Any]:
    effective_acceptance_path, acceptance = load_acceptance_with_fallback(acceptance_path)
    effective_parity_registry_path, parity_registry = load_parity_registry_with_fallback(parity_registry_path)
    design_product_root = acceptance_path.parent
    effective_feedback_loop_gate_path, feedback_loop_gate = load_optional_yaml_with_fallback(
        feedback_loop_gate_path,
        CANONICAL_FEEDBACK_LOOP_RELEASE_GATE,
    )
    effective_feedback_progress_email_workflow_path, feedback_progress_email_workflow = load_optional_yaml_with_fallback(
        design_product_root / DEFAULT_FEEDBACK_PROGRESS_EMAIL_WORKFLOW.name,
        CANONICAL_FEEDBACK_PROGRESS_EMAIL_WORKFLOW,
    )
    effective_flagship_parity_registry_path, flagship_parity_registry = load_optional_yaml_with_fallback(
        design_product_root / DEFAULT_FLAGSHIP_PARITY_REGISTRY.name,
        CANONICAL_FLAGSHIP_PARITY_REGISTRY,
    )
    effective_flagship_readiness_planes_path, flagship_readiness_planes = load_optional_yaml_with_fallback(
        design_product_root / DEFAULT_FLAGSHIP_READINESS_PLANES.name,
        CANONICAL_FLAGSHIP_READINESS_PLANES,
    )
    effective_dense_workbench_budget_path, dense_workbench_budget = load_optional_yaml_with_fallback(
        design_product_root / DEFAULT_DENSE_WORKBENCH_BUDGET.name,
        CANONICAL_DENSE_WORKBENCH_BUDGET,
    )
    effective_veteran_first_minute_gate_path, veteran_first_minute_gate = load_optional_yaml_with_fallback(
        design_product_root / DEFAULT_VETERAN_FIRST_MINUTE_GATE.name,
        CANONICAL_VETERAN_FIRST_MINUTE_GATE,
    )
    effective_primary_route_registry_path, primary_route_registry = load_optional_yaml_with_fallback(
        design_product_root / DEFAULT_PRIMARY_ROUTE_REGISTRY.name,
        CANONICAL_PRIMARY_ROUTE_REGISTRY,
    )
    flagship_bar_mirror_path = design_product_root / DEFAULT_FLAGSHIP_BAR.name
    horizons_overview_mirror_path = design_product_root / DEFAULT_HORIZONS_OVERVIEW.name
    horizons_mirror_dir = design_product_root / DEFAULT_HORIZONS_DIR.name
    required_desktop_canon = (
        (
            "surface_design_review_loop",
            design_product_root / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md",
            "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md",
        ),
        (
            "chummer5a_familiarity_bridge",
            design_product_root / "CHUMMER5A_FAMILIARITY_BRIDGE.md",
            "CHUMMER5A_FAMILIARITY_BRIDGE.md",
        ),
        (
            "desktop_executable_exit_gates",
            design_product_root / "DESKTOP_EXECUTABLE_EXIT_GATES.md",
            "DESKTOP_EXECUTABLE_EXIT_GATES.md",
        ),
        (
            "legacy_client_and_adjacent_parity",
            design_product_root / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md",
            "LEGACY_CLIENT_AND_ADJACENT_PARITY.md",
        ),
        (
            "public_release_experience",
            design_product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml",
            "PUBLIC_RELEASE_EXPERIENCE.yaml",
        ),
    )
    status_plane = load_yaml(status_plane_path)
    repo_root = repo_root_for_published_path(status_plane_path)
    progress_report = load_json(progress_report_path)
    progress_history = load_json(progress_history_path)
    journey_gates = load_json(journey_gates_path)
    support_packets = load_json(support_packets_path)
    m136_aggregate_readiness_gate = load_json(m136_aggregate_readiness_gate_path)
    m136_aggregate_readiness_gate_audit = _m136_aggregate_readiness_gate_audit(m136_aggregate_readiness_gate)
    effective_external_proof_runbook_path = (
        external_proof_runbook_path if external_proof_runbook_path is not None else support_packets_path.parent / DEFAULT_EXTERNAL_PROOF_RUNBOOK.name
    )
    external_proof_runbook = load_text(effective_external_proof_runbook_path)
    runbook_generated_at = extract_runbook_field(external_proof_runbook, "generated_at")
    runbook_plan_generated_at = extract_runbook_field(external_proof_runbook, "plan_generated_at")
    runbook_release_generated_at = extract_runbook_field(external_proof_runbook, "release_channel_generated_at")
    runbook_command_bundle_sha256 = extract_runbook_field(external_proof_runbook, "command_bundle_sha256")
    runbook_command_bundle_file_count = _nonnegative_int(
        extract_runbook_field(external_proof_runbook, "command_bundle_file_count"),
        0,
    )
    parity_lab_docs_root = (repo_root or ROOT) / "docs" / "chummer5a-oracle"
    effective_parity_lab_capture_pack_path, parity_lab_capture_pack = load_optional_yaml_with_fallback(
        parity_lab_docs_root / DEFAULT_PARITY_LAB_CAPTURE_PACK.name,
        DEFAULT_PARITY_LAB_CAPTURE_PACK,
    )
    effective_veteran_workflow_pack_path, veteran_workflow_pack = load_optional_yaml_with_fallback(
        parity_lab_docs_root / DEFAULT_VETERAN_WORKFLOW_PACK.name,
        DEFAULT_VETERAN_WORKFLOW_PACK,
    )
    effective_external_proof_commands_dir = (
        DEFAULT_EXTERNAL_PROOF_COMMANDS_DIR
        if external_proof_runbook_path is None and effective_external_proof_runbook_path == DEFAULT_EXTERNAL_PROOF_RUNBOOK
        else effective_external_proof_runbook_path.parent / "external-proof-commands"
    )
    external_command_bundle = external_proof_command_bundle_fingerprint(effective_external_proof_commands_dir)
    effective_supervisor_state_path, supervisor_state = _select_best_supervisor_state(supervisor_state_path)
    effective_active_shards_path, active_shards_payload = _load_active_shards_payload(effective_supervisor_state_path)
    runtime_focus_profiles = _runtime_env_list(
        "CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE",
        repo_root=repo_root,
    )
    configured_shards_rows = (
        active_shards_payload.get("configured_shards") if isinstance(active_shards_payload, dict) else []
    )
    if not isinstance(configured_shards_rows, list):
        configured_shards_rows = []
    active_shards_rows = active_shards_payload.get("active_shards") if isinstance(active_shards_payload, dict) else []
    if not isinstance(active_shards_rows, list):
        active_shards_rows = []
    if not configured_shards_rows:
        configured_shards_rows = list(active_shards_rows)
    try:
        active_shards_count = int(
            (active_shards_payload.get("active_run_count") if isinstance(active_shards_payload, dict) else 0) or 0
        )
    except (TypeError, ValueError):
        active_shards_count = 0
    if active_shards_count <= 0:
        active_shards_count = sum(
            1
            for item in active_shards_rows
            if isinstance(item, dict)
            and (
                str(item.get("active_run_id") or "").strip()
                or bool(item.get("active"))
            )
        )
    configured_shards_count = len(configured_shards_rows)
    active_shards_generated_at = str(
        (active_shards_payload.get("generated_at") if isinstance(active_shards_payload, dict) else "")
        or ""
    ).strip()
    active_shards_manifest_kind = str(
        (active_shards_payload.get("manifest_kind") if isinstance(active_shards_payload, dict) else "")
        or ""
    ).strip()
    active_shards_generated_dt = parse_iso(active_shards_generated_at)
    active_shards_recent = (
        active_shards_generated_dt is not None
        and (utc_now() - active_shards_generated_dt).total_seconds() <= FLAGSHIP_OPERATOR_SUPERVISOR_MAX_AGE_HOURS * 3600
    )
    supervisor_state = dict(supervisor_state or {})
    recovered_supervisor_from_active_shards = False
    recovered_supervisor_focus_profiles_from_runtime_env = False
    selected_supervisor_mode = str(supervisor_state.get("mode") or "").strip().lower()
    selected_supervisor_updated_at = parse_iso(str(supervisor_state.get("updated_at") or ""))
    selected_supervisor_stale_or_missing = (
        selected_supervisor_updated_at is None
        or (utc_now() - selected_supervisor_updated_at).total_seconds() > FLAGSHIP_OPERATOR_SUPERVISOR_MAX_AGE_HOURS * 3600
    )
    supervisor_completion_status_before_recovery = _supervisor_completion_status(supervisor_state)
    configured_flagship_topology_ready = (
        active_shards_recent
        and active_shards_manifest_kind == "configured_shard_topology"
        and configured_shards_count > 0
        and supervisor_completion_status_before_recovery in {"pass", "passed"}
    )
    if active_shards_recent and (active_shards_count > 0 or configured_flagship_topology_ready) and (
        not selected_supervisor_mode
        or selected_supervisor_stale_or_missing
        or selected_supervisor_mode not in {"loop", "sharded", "flagship_product", "complete", "successor_wave"}
    ):
        if supervisor_completion_status_before_recovery not in {"pass", "passed"}:
            supervisor_state.pop("completion_audit", None)
        supervisor_state["mode"] = "sharded"
        supervisor_state["updated_at"] = active_shards_generated_at
        supervisor_state["active_runs_count"] = active_shards_count
        recovered_supervisor_from_active_shards = True
    if runtime_focus_profiles and (recovered_supervisor_from_active_shards or not list(supervisor_state.get("focus_profiles") or [])):
        supervisor_state["focus_profiles"] = list(runtime_focus_profiles)
        recovered_supervisor_focus_profiles_from_runtime_env = True
    ooda_state = load_json(ooda_state_path)
    recovered_ooda_from_active_shards = False
    recovered_ooda_source = ""
    ooda_needs_manifest_recovery = bool(
        ooda_state
        and active_shards_recent
        and active_shards_manifest_kind == "configured_shard_topology"
        and (active_shards_count > 0 or configured_flagship_topology_ready)
        and (bool(ooda_state.get("aggregate_stale")) or bool(ooda_state.get("aggregate_timestamp_stale")))
    )
    if not ooda_state or ooda_needs_manifest_recovery:
        recovered_ooda_state = _recover_ooda_state_from_active_shards(
            active_shards_payload,
            active_shards_recent=active_shards_recent,
        )
        if recovered_ooda_state:
            ooda_state = recovered_ooda_state
            recovered_ooda_from_active_shards = True
            recovered_ooda_source = str(recovered_ooda_state.get("recovery_source") or "").strip()
    ui_local_release_proof = load_json(ui_local_release_proof_path)
    ui_linux_exit_gate = load_json(ui_linux_exit_gate_path)
    ui_windows_exit_gate = load_json(ui_windows_exit_gate_path)
    ui_workflow_parity_proof = load_json(ui_workflow_parity_proof_path)
    ui_executable_exit_gate = load_json(ui_executable_exit_gate_path)
    ui_workflow_execution_gate = load_json(ui_workflow_execution_gate_path)
    ui_visual_familiarity_exit_gate = load_json(ui_visual_familiarity_exit_gate_path)
    effective_ui_element_parity_audit_path = (
        ui_element_parity_audit_path
        if ui_element_parity_audit_path is not None
        else ui_visual_familiarity_exit_gate_path.with_name(DEFAULT_UI_ELEMENT_PARITY_AUDIT.name)
    )
    ui_element_parity_audit_required = (
        ui_element_parity_audit_path is not None or effective_ui_element_parity_audit_path.is_file()
    )
    ui_element_parity_audit = (
        load_json(effective_ui_element_parity_audit_path) if ui_element_parity_audit_required else {}
    )
    ui_element_parity_audit_summary = _ui_element_parity_audit_summary(ui_element_parity_audit)
    ui_element_parity_audit_analysis = _ui_element_parity_audit_release_blockers(ui_element_parity_audit)
    ui_element_parity_audit_missing_required_ids = _as_string_list(
        ui_element_parity_audit_analysis.get("missing_required_ids")
    )
    ui_element_parity_audit_unresolved_rows = list(
        ui_element_parity_audit_analysis.get("unresolved_release_blocking_rows") or []
    )
    ui_element_parity_audit_unresolved_ids = _as_string_list(
        ui_element_parity_audit_analysis.get("unresolved_release_blocking_ids")
    )
    ui_element_parity_audit_release_blocking_ready = bool(
        ui_element_parity_audit_analysis.get("release_blocking_ready")
    )
    ui_user_journey_tester_audit = load_json(ui_user_journey_tester_audit_path) if ui_user_journey_tester_audit_path else {}
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
    local_blocker_routes = _journey_local_blocker_routes(
        journeys,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
    )
    local_blocker_route_rows = [
        dict(item)
        for item in (local_blocker_routes.get("routes") or [])
        if isinstance(item, dict)
    ]
    local_blocker_unrouted_reasons = [
        str(item).strip()
        for item in (local_blocker_routes.get("unrouted_reasons") or [])
        if str(item).strip()
    ]
    local_blocker_total_count = int(local_blocker_routes.get("total_local_blocker_count") or 0)
    local_blocker_routed_count = int(local_blocker_routes.get("routed_local_blocker_count") or 0)
    local_blocker_unrouted_count = int(local_blocker_routes.get("unrouted_local_blocker_count") or 0)
    local_blocker_owner_repo_counts = {
        str(key): int(value)
        for key, value in (local_blocker_routes.get("owner_repo_counts") or {}).items()
        if str(key).strip()
    }
    journey_local_blocker_counts = {
        str(key): int(value)
        for key, value in (local_blocker_routes.get("journey_local_blocker_counts") or {}).items()
        if str(key).strip()
    }
    local_blocker_autofix_routing_ready = (
        local_blocker_total_count == 0
        or local_blocker_unrouted_count == 0
    )
    runtime_healing_summary = _effective_runtime_healing_summary(
        status_plane,
        status_plane_path=status_plane_path,
    )
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
    executable_gate_raw_reasons = [
        str(item).strip()
        for item in (ui_executable_exit_gate.get("reasons") or [])
        if str(item).strip()
    ]
    if ui_executable_exit_gate:
        executable_gate_freshness_proof_ages, executable_gate_freshness_issues_list = executable_gate_freshness_issues(
            ui_executable_exit_gate
        )
    visual_gate_recovered_from_executable_gate = False
    visual_gate_effective_ready = proof_passed(
        ui_visual_familiarity_exit_gate,
        expected_contract="chummer6-ui.desktop_visual_familiarity_exit_gate",
        accepted_statuses=("passed", "pass", "ready"),
    )
    if (
        not visual_gate_effective_ready
        and proof_passed(
            ui_executable_exit_gate,
            expected_contract="chummer6-ui.desktop_executable_exit_gate",
            accepted_statuses=("passed", "pass", "ready"),
        )
        and not executable_gate_freshness_issues_list
        and executable_gate_freshness_proof_ages.get("desktop visual familiarity gate proof_age_seconds", DESKTOP_EXECUTABLE_GATE_PROOF_MAX_AGE_SECONDS + 1)
        <= DESKTOP_EXECUTABLE_GATE_PROOF_MAX_AGE_SECONDS
        and _visual_gate_stale_capture_only(ui_visual_familiarity_exit_gate)
    ):
        visual_gate_effective_ready = True
        visual_gate_recovered_from_executable_gate = True
    if proof_passed(ui_local_release_proof, expected_contract="chummer6-ui.local_release_proof"):
        desktop_positives += 1
    else:
        desktop_reasons.append("UI local release proof is missing or not passed.")
    ignored_only_executable_gate = False
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
        executable_gate_reasons = list(executable_gate_raw_reasons)
        executable_gate_sr4_sr6_workflow_oracle_reasons = [
            reason
            for reason in executable_gate_reasons
            if _reason_targets_sr4_sr6_workflow_oracle_backlog(reason)
        ]
        if executable_gate_sr4_sr6_workflow_oracle_reasons:
            executable_gate_reasons = [
                reason
                for reason in executable_gate_reasons
                if reason not in set(executable_gate_sr4_sr6_workflow_oracle_reasons)
            ]
        if ignore_nonlinux_desktop_host_proof_blockers:
            executable_gate_reasons = [
                reason
                for reason in executable_gate_reasons
                if not _reason_targets_ignored_desktop_host_platform(reason)
            ]
        if _release_channel_external_proof_contract_ready(release_channel):
            executable_gate_reasons = [
                reason
                for reason in executable_gate_reasons
                if not (
                    "desktoptuplecoverage.externalproofrequests" in reason.lower()
                    or "proofcapturecommands" in reason.lower()
                    or "missing-tuple external proof contract" in reason.lower()
                )
            ]
        effective_executable_gate_local_blockers = _effective_desktop_executable_gate_local_blockers(
            ui_executable_exit_gate,
            release_channel=release_channel,
        )
        raw_executable_gate_local_blockers = _as_string_list(
            ui_executable_exit_gate.get("local_blocking_findings")
            or ui_executable_exit_gate.get("localBlockingFindings")
        )
        ignored_executable_gate_local_blockers = {
            reason
            for reason in raw_executable_gate_local_blockers
            if reason not in set(effective_executable_gate_local_blockers)
        }
        if ignored_executable_gate_local_blockers:
            executable_gate_reasons = [
                reason
                for reason in executable_gate_reasons
                if reason not in ignored_executable_gate_local_blockers
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
        if executable_gate_sr4_sr6_workflow_oracle_reasons and (
            not executable_gate_reasons
            or all(
                reason == "Release channel status cannot be publishable while required desktop tuple coverage is incomplete."
                for reason in executable_gate_reasons
            )
        ):
            ignored_only_executable_gate = True
        if ignored_only_executable_gate and proof_passed(
            ui_linux_exit_gate,
            expected_contract="chummer6-ui.linux_desktop_exit_gate",
        ):
            desktop_positives += 1
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
        workflow_execution_sr4_sr6_only = _workflow_receipts_are_sr4_sr6_only(
            unresolved_workflow_execution_receipts
        )
        if unresolved_workflow_execution_receipts and not workflow_execution_sr4_sr6_only:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Executable desktop workflow execution gate reports unresolved family/execution receipt drift (missing/failing/weak)."
            )
        elif unresolved_workflow_execution_receipts:
            desktop_positives += 1
        else:
            desktop_positives += 1
    else:
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
        workflow_execution_sr4_sr6_only = _workflow_receipts_are_sr4_sr6_only(
            unresolved_workflow_execution_receipts
        )
        if workflow_execution_sr4_sr6_only:
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Executable desktop workflow execution gate proof is missing or not passed. Catalog parity without click-through receipts does not pass."
            )
    user_journey_tester_audit_required = ui_user_journey_tester_audit_path is not None
    user_journey_tester_audit_gap_payload = user_journey_tester_audit_gaps(ui_user_journey_tester_audit)
    if user_journey_tester_audit_required:
        if proof_passed(
            ui_user_journey_tester_audit,
            expected_contract="chummer6-ui.user_journey_tester_audit",
            accepted_statuses=("passed", "pass", "ready"),
        ) and bool(user_journey_tester_audit_gap_payload.get("ready")):
            desktop_positives += 1
        else:
            desktop_hard_fail = True
            desktop_reasons.append(
                "Dedicated user-journey tester audit is missing or not passed. "
                "A separate tester shard must run the Linux binary like a user and prove visible workflow results."
            )
            if user_journey_tester_audit_gap_payload.get("missing_workflows"):
                desktop_reasons.append(
                    "User-journey tester audit is missing required workflows: "
                    + ", ".join(user_journey_tester_audit_gap_payload["missing_workflows"])
                    + "."
                )
            if user_journey_tester_audit_gap_payload.get("nonpassing_workflows"):
                desktop_reasons.append(
                    "User-journey tester audit reports non-passing workflows: "
                    + ", ".join(user_journey_tester_audit_gap_payload["nonpassing_workflows"])
                    + "."
                )
            if user_journey_tester_audit_gap_payload.get("insufficient_screenshot_workflows"):
                desktop_reasons.append(
                    "User-journey tester audit lacks multiple screenshots for workflows: "
                    + ", ".join(user_journey_tester_audit_gap_payload["insufficient_screenshot_workflows"])
                    + "."
                )
            if user_journey_tester_audit_gap_payload.get("counter_only_screenshot_workflows"):
                desktop_reasons.append(
                    "User-journey tester audit uses screenshot counters without actual screenshot paths for workflows: "
                    + ", ".join(user_journey_tester_audit_gap_payload["counter_only_screenshot_workflows"])
                    + "."
                )
            if user_journey_tester_audit_gap_payload.get("unverified_screenshot_workflows"):
                desktop_reasons.append(
                    "User-journey tester audit lacks verified existing PNG screenshot review for workflows: "
                    + ", ".join(user_journey_tester_audit_gap_payload["unverified_screenshot_workflows"])
                    + "."
                )
            if user_journey_tester_audit_gap_payload.get("missing_workflow_assertions"):
                missing_assertion_summary = [
                    f"{workflow_id}: {', '.join(assertions)}"
                    for workflow_id, assertions in sorted(
                        user_journey_tester_audit_gap_payload["missing_workflow_assertions"].items()
                    )
                ]
                desktop_reasons.append(
                    "User-journey tester audit lacks required user-visible assertions: "
                    + "; ".join(missing_assertion_summary)
                    + "."
                )
            if user_journey_tester_audit_gap_payload.get("missing_execution_discipline"):
                desktop_reasons.append(
                    "User-journey tester audit lacks required execution discipline: "
                    + ", ".join(user_journey_tester_audit_gap_payload["missing_execution_discipline"])
                    + "."
                )
    if visual_gate_effective_ready:
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
            key: _visual_evidence_status(visual_evidence, key)
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
                if not (
                    _milestone2_visual_requirement_satisfied(visual_required_tests_set, group)
                    or _milestone2_visual_requirement_semantically_satisfied(visual_evidence, group[0])
                )
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
    windows_exit_gate_recovered_from_executable_gate = False
    if windows_exit_gate_passed(ui_windows_exit_gate):
        desktop_positives += 1
    elif aggregate_windows_exit_gate_passed(ui_executable_exit_gate):
        desktop_positives += 1
        windows_exit_gate_recovered_from_executable_gate = True
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
    sr4_workflow_parity_external_only = _desktop_parity_receipt_is_external_only_missing_api_surface_contract(
        sr4_workflow_parity_proof
    )
    sr6_workflow_parity_external_only = _desktop_parity_receipt_is_external_only_missing_api_surface_contract(
        sr6_workflow_parity_proof
    )
    sr4_workflow_parity_effective_ready = proof_passed(
        sr4_workflow_parity_proof,
        expected_contract="chummer6-ui.sr4_desktop_workflow_parity",
        accepted_statuses=("passed", "pass", "ready"),
    ) or sr4_workflow_parity_external_only
    sr6_workflow_parity_effective_ready = proof_passed(
        sr6_workflow_parity_proof,
        expected_contract="chummer6-ui.sr6_desktop_workflow_parity",
        accepted_statuses=("passed", "pass", "ready"),
    ) or sr6_workflow_parity_external_only
    sr4_sr6_frontier_receipt_external_only = _desktop_parity_receipt_is_external_only_missing_api_surface_contract(
        sr4_sr6_frontier_receipt
    )
    sr4_sr6_frontier_effective_ready = proof_passed(
        sr4_sr6_frontier_receipt,
        expected_contract="chummer6-ui.sr4_sr6_desktop_parity_frontier",
        accepted_statuses=("passed", "pass", "ready"),
    ) or sr4_sr6_frontier_receipt_external_only or (
        sr4_workflow_parity_effective_ready and sr6_workflow_parity_effective_ready
    )
    if sr4_workflow_parity_effective_ready:
        desktop_positives += 1
    else:
        desktop_reasons.append(
            "SR4 desktop workflow parity proof is missing or not passed. Chummer4 parity must remain open until a real desktop parity gate lands."
        )
    if sr6_workflow_parity_effective_ready:
        desktop_positives += 1
    else:
        desktop_reasons.append(
            "SR6 desktop workflow parity proof is missing or not passed. Cumulative carry-forward workflows are not complete yet."
        )
    if sr4_sr6_frontier_effective_ready:
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
    linux_statuses = dict((executable_gate_evidence or {}).get("linux_statuses") or {})
    windows_statuses = dict((executable_gate_evidence or {}).get("windows_statuses") or {})
    macos_statuses = dict((executable_gate_evidence or {}).get("macos_statuses") or {})
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
    required_heads_for_pair_matrix = tuple_coverage_required_heads or executable_required_heads
    effective_required_tuple_heads = required_heads_for_pair_matrix or list(promoted_tuple_heads)
    missing_required_tuple_heads = [head for head in required_heads_for_pair_matrix if head not in set(promoted_tuple_heads)]
    visual_required_heads = _normalized_token_list((executable_gate_evidence or {}).get("visual_familiarity_required_desktop_heads"))
    workflow_required_heads = _normalized_token_list((executable_gate_evidence or {}).get("workflow_execution_required_desktop_heads"))
    visual_head_proofs = _normalized_status_map((executable_gate_evidence or {}).get("visual_familiarity_head_proofs"))
    workflow_head_proofs = _normalized_status_map((executable_gate_evidence or {}).get("workflow_execution_head_proofs"))
    missing_visual_required_inventory_heads = [
        head for head in required_heads_for_pair_matrix if head not in set(visual_required_heads)
    ]
    missing_workflow_required_inventory_heads = [
        head for head in required_heads_for_pair_matrix if head not in set(workflow_required_heads)
    ]
    missing_visual_passing_head_proofs = [
        head for head in required_heads_for_pair_matrix if visual_head_proofs.get(head) not in {"pass", "passed", "ready"}
    ]
    missing_workflow_passing_head_proofs = [
        head for head in required_heads_for_pair_matrix if workflow_head_proofs.get(head) not in {"pass", "passed", "ready"}
    ]
    unpromoted_desktop_shelf_installers = sorted(
        {
            str(item).strip()
            for item in _as_string_list((executable_gate_evidence or {}).get("unpromoted_desktop_shelf_installers"))
            if str(item).strip()
        }
    )
    effective_unpromoted_desktop_shelf_installers = list(unpromoted_desktop_shelf_installers)
    if ignore_nonlinux_desktop_host_proof_blockers:
        effective_unpromoted_desktop_shelf_installers = [
            token
            for token in effective_unpromoted_desktop_shelf_installers
            if not _reason_targets_ignored_desktop_host_platform(token)
        ]
    required_platforms_for_pair_matrix = tuple_coverage_required_platforms or ["linux", "windows", "macos"]
    if ignore_nonlinux_desktop_host_proof_blockers:
        required_platforms_for_pair_matrix = [platform for platform in required_platforms_for_pair_matrix if platform == "linux"]
    required_platform_set = set(required_platforms_for_pair_matrix)
    linux_platform_required = "linux" in required_platform_set
    windows_platform_required = "windows" in required_platform_set
    macos_platform_required = "macos" in required_platform_set
    required_promoted_tuple_keys_by_platform: Dict[str, List[str]] = {
        platform: sorted(
            tuple_key
            for tuple_key in promoted_tuple_keys_by_platform.get(platform, [])
            if str(tuple_key).strip()
            and str(tuple_key).split(":", 1)[0].strip().lower() in set(effective_required_tuple_heads)
        )
        for platform in promoted_tuple_keys_by_platform
    }
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
    stale_linux_receipt_tuples_overlapping_promoted_tuples = sorted(
        set(stale_linux_gate_receipt_tuple_keys_without_promoted_tuples).intersection(
            set(required_promoted_tuple_keys_by_platform["linux"])
        )
    )
    stale_windows_receipt_tuples_overlapping_promoted_tuples = sorted(
        set(stale_windows_gate_receipt_tuple_keys_without_promoted_tuples).intersection(
            set(required_promoted_tuple_keys_by_platform["windows"])
        )
    )
    stale_macos_receipt_tuples_overlapping_promoted_tuples = sorted(
        set(stale_macos_gate_receipt_tuple_keys_without_promoted_tuples).intersection(
            set(required_promoted_tuple_keys_by_platform["macos"])
        )
    )
    tuple_coverage_declared = bool(release_channel_tuple_coverage)
    release_channel_rollout_state = str(release_channel.get("rolloutState") or "").strip().lower()
    release_channel_supportability_state = str(release_channel.get("supportabilityState") or "").strip().lower()

    has_linux_public_installer = bool(required_promoted_tuple_keys_by_platform["linux"])
    has_windows_public_installer = bool(required_promoted_tuple_keys_by_platform["windows"])
    has_macos_public_installer = bool(required_promoted_tuple_keys_by_platform["macos"])
    has_any_public_installer = any(
        (
            linux_platform_required and has_linux_public_installer,
            windows_platform_required and has_windows_public_installer,
            macos_platform_required and has_macos_public_installer,
        )
    )
    if release_channel_published_and_proven and release_channel_freshness_ok and has_avalonia_public_artifact:
        desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Release channel is not simultaneously published, release-proven, and Avalonia-desktop-backed."
        )
    if linux_platform_required and not has_linux_public_installer:
        desktop_reasons.append("Release channel does not publish any promoted Linux installer media.")
    if windows_platform_required and not ignore_nonlinux_desktop_host_proof_blockers and not has_windows_public_installer:
        desktop_reasons.append("Release channel does not publish any promoted Windows installer media.")
    if (
        not linux_statuses
        and required_promoted_tuple_keys_by_platform["linux"] == ["avalonia:linux-x64"]
        and proof_passed(ui_linux_exit_gate, expected_contract="chummer6-ui.linux_desktop_exit_gate")
    ):
        linux_statuses = {"avalonia:linux-x64": "pass"}
    if (
        not windows_statuses
        and required_promoted_tuple_keys_by_platform["windows"] == ["avalonia:win-x64"]
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
        return len(expected_keys), passing_count, sorted(set(missing_or_failing)), stale_expected

    linux_tuple_count, linux_passing_status_count, linux_missing_or_failing_keys, linux_stale_promoted_keys = _tuple_proof_stats(
        linux_statuses, required_promoted_tuple_keys_by_platform["linux"]
    )
    windows_tuple_count, windows_passing_status_count, windows_missing_or_failing_keys, windows_stale_promoted_keys = _tuple_proof_stats(
        windows_statuses, required_promoted_tuple_keys_by_platform["windows"]
    )
    macos_tuple_count, macos_passing_status_count, macos_missing_or_failing_keys, macos_stale_promoted_keys = _tuple_proof_stats(
        macos_statuses, required_promoted_tuple_keys_by_platform["macos"]
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
    linux_exit_gate_satisfied_by_executable_gate = (
        proof_passed(
            ui_executable_exit_gate,
            expected_contract="chummer6-ui.desktop_executable_exit_gate",
            accepted_statuses=("passed", "pass", "ready"),
        )
        and required_promoted_tuple_keys_by_platform["linux"] == ["avalonia:linux-x64"]
        and str(linux_statuses.get("avalonia:linux-x64") or "").strip().lower() in {"pass", "passed", "ready"}
        and not linux_missing_or_failing_keys
        and not linux_stale_promoted_keys
        and int(
            ui_executable_exit_gate.get("local_blocking_findings_count")
            or ui_executable_exit_gate.get("localBlockingFindingsCount")
            or 0
        )
        == 0
    )
    linux_gate_effective_ready = proof_passed(
        ui_linux_exit_gate,
        expected_contract="chummer6-ui.linux_desktop_exit_gate",
    ) or linux_exit_gate_satisfied_by_executable_gate
    if not linux_platform_required:
        linux_gate_effective_ready = True
    if linux_gate_effective_ready:
        desktop_positives += 1
    else:
        desktop_hard_fail = True
        desktop_reasons.append("Linux desktop exit gate proof is missing or not passed.")

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
    if effective_unpromoted_desktop_shelf_installers:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Desktop shelf contains installer artifacts not represented in release-channel promoted tuples: "
            + ", ".join(effective_unpromoted_desktop_shelf_installers)
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
    ignored_nonlinux_host_proof_blockers = bool(ignore_nonlinux_desktop_host_proof_blockers) and (
        has_windows_public_installer or has_macos_public_installer
    ) and (
        any(_reason_targets_ignored_desktop_host_platform(reason) for reason in executable_gate_raw_reasons)
        or bool(windows_missing_or_failing_keys)
        or bool(macos_missing_or_failing_keys)
        or bool(windows_stale_promoted_keys)
        or bool(macos_stale_promoted_keys)
        or bool(stale_windows_receipt_tuples_overlapping_promoted_tuples)
        or bool(stale_macos_receipt_tuples_overlapping_promoted_tuples)
    )
    if ignored_nonlinux_host_proof_blockers:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Non-Linux desktop host-proof blockers cannot be ignored while public Windows or macOS installer media exists."
        )
    install_journey = dict(journeys.get("install_claim_restore_continue") or {})
    build_journey = dict(journeys.get("build_explain_publish") or {})
    build_journey_effective: Dict[str, Any] = {}
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
    effective_executable_local_blocking_findings = _effective_desktop_executable_gate_local_blockers(
        ui_executable_exit_gate,
        release_channel=release_channel,
    )
    if effective_executable_local_blocking_findings:
        executable_local_blocking_findings_count = len(effective_executable_local_blocking_findings)
    elif (
        isinstance(ui_executable_exit_gate.get("local_blocking_findings"), list)
        or isinstance(ui_executable_exit_gate.get("localBlockingFindings"), list)
    ):
        executable_local_blocking_findings_count = 0
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
    build_journey_effective = _effective_journey_readiness(
        "build_explain_publish",
        build_journey,
        release_proof=release_proof,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
        ignore_nonlinux_platform_host_blockers=False,
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
    install_journey_effective = _effective_journey_readiness(
        "install_claim_restore_continue",
        install_journey,
        release_proof=release_proof,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
        ignore_nonlinux_platform_host_blockers=False,
    )
    install_journey_desktop_scoped_blocked = _journey_is_desktop_scoped_blocked(
        "install_claim_restore_continue",
        install_journey,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
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
    report_cluster_effective = _effective_journey_readiness(
        "report_cluster_release_notify",
        report_cluster_journey,
        release_proof=release_proof,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
        ignore_nonlinux_platform_host_blockers=False,
    )
    report_cluster_desktop_scoped_blocked = _journey_is_desktop_scoped_blocked(
        "report_cluster_release_notify",
        report_cluster_journey,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
    )
    install_journey_effective_state = str(install_journey_effective.get("effective_state") or "").strip()
    build_journey_effective_state = str(build_journey_effective.get("effective_state") or "").strip()
    campaign_recap_journey = journeys.get("campaign_session_recover_recap") or {}
    campaign_recap_effective = _effective_journey_readiness(
        "campaign_session_recover_recap",
        campaign_recap_journey,
        release_proof=release_proof,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
        ignore_nonlinux_platform_host_blockers=False,
    )
    campaign_recap_mobile_effective = _owner_scoped_journey_effective_readiness(
        "campaign_session_recover_recap",
        campaign_recap_effective,
        journey_local_blocker_counts=journey_local_blocker_counts,
        journey_local_blocker_route_rows=local_blocker_route_rows,
        coverage_owner_repos=("chummer6-mobile", "chummer6-hub-registry"),
    )
    conflict_journey = journeys.get("recover_from_sync_conflict") or {}
    conflict_effective = _effective_journey_readiness(
        "recover_from_sync_conflict",
        conflict_journey,
        release_proof=release_proof,
        ui_executable_exit_gate=ui_executable_exit_gate,
        release_channel=release_channel,
        ignore_nonlinux_platform_host_blockers=False,
    )
    conflict_mobile_effective = _owner_scoped_journey_effective_readiness(
        "recover_from_sync_conflict",
        conflict_effective,
        journey_local_blocker_counts=journey_local_blocker_counts,
        journey_local_blocker_route_rows=local_blocker_route_rows,
        coverage_owner_repos=("chummer6-mobile", "chummer6-hub-registry"),
    )
    campaign_recap_ui_kit_effective = _owner_scoped_journey_effective_readiness(
        "campaign_session_recover_recap",
        campaign_recap_effective,
        journey_local_blocker_counts=journey_local_blocker_counts,
        journey_local_blocker_route_rows=local_blocker_route_rows,
        coverage_owner_repos=("chummer6-ui-kit", "chummer6-ui", "chummer6-mobile"),
    )
    if (
        install_journey_state == "ready"
        or install_journey_desktop_scoped_blocked
        or install_journey_effective_state == "ready"
    ):
        desktop_positives += 1
    else:
        if install_journey_effective_external_only:
            desktop_reasons.append(
                "Install/claim/restore journey is blocked by external platform-host constraints; capture the missing host proof lane and ingest receipts."
            )
        else:
            desktop_reasons.append(
                f"Install/claim/restore journey is {install_journey_effective_state or install_journey_state or 'missing'}, not ready."
            )
    if build_journey_effective_state == "ready":
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
            desktop_reasons.append(
                f"Build/explain/publish journey is {build_journey_effective_state or build_journey_state or 'missing'}, not ready."
            )
    if parity_unresolved_families:
        desktop_hard_fail = True
        parity_family_text = ", ".join(
            f"{row['id']} ({row['status']})" for row in (parity_desktop_families or parity_unresolved_families)
        )
        desktop_reasons.append(
            "No-step-back parity registry still has unresolved non-plugin families: "
            f"{parity_family_text}."
        )
    if ui_element_parity_audit_required and not ui_element_parity_audit:
        desktop_hard_fail = True
        desktop_reasons.append("Chummer5A UI element parity audit is missing.")
    if ui_element_parity_audit_missing_required_ids:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Chummer5A UI element parity audit is missing required release-blocking rows: "
            + _summarize_ids(ui_element_parity_audit_missing_required_ids)
            + "."
        )
    if ui_element_parity_audit_unresolved_rows:
        desktop_hard_fail = True
        desktop_reasons.append(
            "Chummer5A UI element parity audit still has unresolved release-blocking rows: "
            + ", ".join(
                f"{row['label']} ({row['visual_parity']}/{row['behavioral_parity']})"
                for row in ui_element_parity_audit_unresolved_rows
            )
            + "."
        )
    if (
        ui_element_parity_audit_summary["visual_no_count"] > 0
        or ui_element_parity_audit_summary["behavioral_no_count"] > 0
    ):
        desktop_hard_fail = True
        desktop_reasons.append(
            "Chummer5A UI element parity audit still reports open parity gaps: "
            f"visual_no_count={ui_element_parity_audit_summary['visual_no_count']}, "
            f"behavioral_no_count={ui_element_parity_audit_summary['behavioral_no_count']}."
        )
    elif ui_element_parity_audit_required or ui_element_parity_audit:
        desktop_positives += 1
    ui_stage = str(ui_project.get("readiness_stage") or "").strip()
    ui_promotion = project_posture(ui_project)
    ui_flagship_promotion_ready = (
        compare_order(ui_stage, "publicly_promoted", STAGE_ORDER) >= 0
        and compare_order(ui_promotion, "public", PROMOTION_ORDER) >= 0
    ) or (
        compare_order(ui_stage, "repo_local_complete", STAGE_ORDER) >= 0
        and compare_order(ui_promotion, "public", PROMOTION_ORDER) >= 0
        and proof_passed(ui_local_release_proof, expected_contract="chummer6-ui.local_release_proof")
    )
    if ui_flagship_promotion_ready:
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
            "ui_executable_exit_gate_ignored_nonlinux_only": ignored_only_executable_gate,
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
            "ui_linux_exit_gate_recovered_from_executable_gate": linux_exit_gate_satisfied_by_executable_gate,
            "ui_linux_exit_gate_effective_ready": linux_gate_effective_ready,
            "ui_windows_exit_gate_status": str(ui_windows_exit_gate.get("status") or "").strip(),
            "ui_windows_exit_gate_recovered_from_executable_gate": windows_exit_gate_recovered_from_executable_gate,
            "ui_windows_exit_gate_effective_ready": (
                windows_exit_gate_passed(ui_windows_exit_gate)
                or windows_exit_gate_recovered_from_executable_gate
            ),
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
            "ui_workflow_execution_gate_unresolved_receipts_sr4_sr6_only": bool(
                workflow_execution_sr4_sr6_only
            ),
            "ui_user_journey_tester_audit_required": user_journey_tester_audit_required,
            "ui_user_journey_tester_audit_status": str(ui_user_journey_tester_audit.get("status") or "").strip(),
            "ui_user_journey_tester_audit_path": (
                report_path(ui_user_journey_tester_audit_path) if ui_user_journey_tester_audit_path else ""
            ),
            "ui_user_journey_tester_audit_required_workflows": list(USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS),
            "ui_user_journey_tester_audit_required_workflow_assertions": {
                key: list(value)
                for key, value in USER_JOURNEY_TESTER_REQUIRED_WORKFLOW_ASSERTIONS.items()
            },
            "ui_user_journey_tester_audit_workflow_count": int(
                user_journey_tester_audit_gap_payload.get("workflow_count") or 0
            ),
            "ui_user_journey_tester_audit_missing_workflows": list(
                user_journey_tester_audit_gap_payload.get("missing_workflows") or []
            ),
            "ui_user_journey_tester_audit_nonpassing_workflows": list(
                user_journey_tester_audit_gap_payload.get("nonpassing_workflows") or []
            ),
            "ui_user_journey_tester_audit_insufficient_screenshot_workflows": list(
                user_journey_tester_audit_gap_payload.get("insufficient_screenshot_workflows") or []
            ),
            "ui_user_journey_tester_audit_counter_only_screenshot_workflows": list(
                user_journey_tester_audit_gap_payload.get("counter_only_screenshot_workflows") or []
            ),
            "ui_user_journey_tester_audit_unverified_screenshot_workflows": list(
                user_journey_tester_audit_gap_payload.get("unverified_screenshot_workflows") or []
            ),
            "ui_user_journey_tester_audit_missing_workflow_assertions": dict(
                user_journey_tester_audit_gap_payload.get("missing_workflow_assertions") or {}
            ),
            "ui_user_journey_tester_audit_missing_execution_discipline": list(
                user_journey_tester_audit_gap_payload.get("missing_execution_discipline") or []
            ),
            "ui_user_journey_tester_audit_open_blocking_findings_count": int(
                user_journey_tester_audit_gap_payload.get("open_blocking_findings_count") or 0
            ),
            "ui_user_journey_tester_audit_ready": bool(user_journey_tester_audit_gap_payload.get("ready")),
            "ui_visual_familiarity_exit_gate_status": str(ui_visual_familiarity_exit_gate.get("status") or "").strip(),
            "ui_visual_familiarity_exit_gate_effective_ready": visual_gate_effective_ready,
            "ui_visual_familiarity_exit_gate_recovered_from_executable_gate": visual_gate_recovered_from_executable_gate,
            "ui_visual_familiarity_exit_gate_path": report_path(ui_visual_familiarity_exit_gate_path),
            "ui_element_parity_audit_required": ui_element_parity_audit_required,
            "ui_element_parity_audit_path": report_path(effective_ui_element_parity_audit_path),
            "ui_element_parity_audit_present": bool(ui_element_parity_audit),
            "ui_element_parity_audit_visual_no_count": ui_element_parity_audit_summary["visual_no_count"],
            "ui_element_parity_audit_behavioral_no_count": ui_element_parity_audit_summary["behavioral_no_count"],
            "ui_element_parity_audit_total_elements": ui_element_parity_audit_summary["total_elements"],
            "ui_element_parity_audit_required_release_blocking_ids": list(
                UI_ELEMENT_PARITY_AUDIT_RELEASE_BLOCKING_IDS
            ),
            "ui_element_parity_audit_missing_required_ids": ui_element_parity_audit_missing_required_ids,
            "ui_element_parity_audit_unresolved_release_blocking_ids": ui_element_parity_audit_unresolved_ids,
            "ui_element_parity_audit_unresolved_release_blocking_rows": ui_element_parity_audit_unresolved_rows,
            "ui_element_parity_audit_release_blocking_ready": ui_element_parity_audit_release_blocking_ready,
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
            "sr4_workflow_parity_external_only_missing_api_surface_contract": sr4_workflow_parity_external_only,
            "sr4_workflow_parity_path": report_path(sr4_workflow_parity_proof_path),
            "sr6_workflow_parity_status": str(sr6_workflow_parity_proof.get("status") or "").strip(),
            "sr6_workflow_parity_external_only_missing_api_surface_contract": sr6_workflow_parity_external_only,
            "sr6_workflow_parity_path": report_path(sr6_workflow_parity_proof_path),
            "sr4_sr6_frontier_receipt_status": str(sr4_sr6_frontier_receipt.get("status") or "").strip(),
            "sr4_sr6_frontier_receipt_external_only_missing_api_surface_contract": (
                sr4_sr6_frontier_receipt_external_only
                or (sr4_workflow_parity_effective_ready and sr6_workflow_parity_effective_ready)
            ),
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
            "ui_executable_gate_required_promoted_heads": required_heads_for_pair_matrix,
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
            "ui_executable_gate_unpromoted_desktop_shelf_installers": effective_unpromoted_desktop_shelf_installers,
            "ui_executable_gate_unpromoted_desktop_shelf_installers_raw": unpromoted_desktop_shelf_installers,
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
            "install_claim_restore_continue_effective": install_journey_effective_state,
            "build_explain_publish": build_journey_state,
            "build_explain_publish_effective": build_journey_effective_state,
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
            "ui_executable_exit_gate_effective_local_blocking_findings": effective_executable_local_blocking_findings,
            "ui_executable_exit_gate_effective_local_blocking_findings_count": len(
                effective_executable_local_blocking_findings
            ),
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
    build_journey_rules_scope_local_blockers = [
        reason
        for reason in build_journey_local_blockers
        if _reason_targets_rules_engine_and_import_scope(reason)
    ]
    build_journey_rules_scope_external_blockers = [
        reason
        for reason in build_journey_external_blockers
        if _reason_targets_rules_engine_and_import_scope(reason)
    ]
    build_journey_rules_scope_blockers = (
        build_journey_rules_scope_local_blockers + build_journey_rules_scope_external_blockers
    )
    if compare_order(core_stage, "boundary_pure", STAGE_ORDER) >= 0:
        rules_positives += 1
    else:
        rules_reasons.append(f"Core project readiness is {core_stage or 'unknown'}, below boundary-pure rules posture.")
    if (
        build_journey_effective_state == "ready"
        or build_journey_state == "ready"
        or (
            build_journey_state == "blocked"
            and (build_journey_local_blockers or build_journey_external_blockers)
            and not build_journey_rules_scope_blockers
        )
    ):
        rules_positives += 1
    else:
        rules_reasons.append(
            f"Build/explain/publish journey is {build_journey_effective_state or build_journey_state or 'missing'}, not ready."
        )
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
            "build_explain_publish_effective": build_journey_effective_state,
            "build_explain_publish_local_blocking_reason_count": len(build_journey_local_blockers),
            "build_explain_publish_external_blocking_reason_count": len(build_journey_external_blockers),
            "build_explain_publish_rules_scope_blocking_reason_count": len(build_journey_rules_scope_blockers),
            "build_explain_publish_rules_scope_blocking_reasons": build_journey_rules_scope_blockers,
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
    if str(release_channel.get("status") or "").strip().lower() == "published" and str(release_proof.get("status") or "").strip().lower() in {"pass", "passed", "ready"}:
        hub_positives += 1
    else:
        hub_reasons.append("Registry release channel is not in a published-and-proven state.")
    if (
        install_journey_state == "ready"
        or install_journey_desktop_scoped_blocked
        or str(install_journey_effective.get("effective_state") or "").strip() == "ready"
    ):
        hub_positives += 1
    else:
        hub_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if (
        report_cluster_state == "ready"
        or report_cluster_desktop_scoped_blocked
        or str(report_cluster_effective.get("effective_state") or "").strip() == "ready"
    ):
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
            "install_claim_restore_continue_desktop_scoped_blocked": install_journey_desktop_scoped_blocked,
            "install_claim_restore_continue_effective_state": str(install_journey_effective.get("effective_state") or "").strip(),
            "install_claim_restore_continue_release_proof_override": bool(install_journey_effective.get("release_proof_override")),
            "report_cluster_release_notify": report_cluster_state,
            "report_cluster_release_notify_desktop_scoped_blocked": report_cluster_desktop_scoped_blocked,
            "report_cluster_release_notify_effective_state": str(report_cluster_effective.get("effective_state") or "").strip(),
            "report_cluster_release_notify_release_proof_override": bool(report_cluster_effective.get("release_proof_override")),
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
    campaign_recap_state = str(campaign_recap_journey.get("state") or "").strip()
    campaign_recap_mobile_effective_state = str(
        campaign_recap_mobile_effective.get("owner_scoped_effective_state")
        or campaign_recap_mobile_effective.get("effective_state")
        or ""
    ).strip()
    conflict_state = str(conflict_journey.get("state") or "").strip()
    conflict_mobile_effective_state = str(
        conflict_mobile_effective.get("owner_scoped_effective_state")
        or conflict_mobile_effective.get("effective_state")
        or ""
    ).strip()
    mobile_local_release_passed = proof_passed(
        mobile_local_release_proof, expected_contract="chummer6-mobile.local_release_proof"
    )
    ui_local_release_passed = proof_passed(
        ui_local_release_proof, expected_contract="chummer6-ui.local_release_proof"
    )
    if mobile_local_release_passed:
        mobile_positives += 1
    else:
        mobile_reasons.append("Mobile local release proof is missing or not passed.")
    if campaign_recap_state == "ready" or campaign_recap_mobile_effective_state == "ready":
        mobile_positives += 1
    else:
        mobile_reasons.append(f"Campaign/recover/recap journey is {campaign_recap_state or 'missing'}, not ready.")
    mobile_stage = str(mobile_project.get("readiness_stage") or "").strip()
    mobile_promotion = project_posture(mobile_project)
    conflict_mobile_public_proof_ready = (
        conflict_state == "warning"
        and not _as_string_list(conflict_journey.get("blocking_reasons"))
        and not _as_string_list(conflict_journey.get("local_blocking_reasons"))
        and not _as_string_list(conflict_journey.get("external_blocking_reasons"))
        and not [dict(item) for item in (conflict_journey.get("external_proof_requests") or []) if isinstance(item, dict)]
        and compare_order(mobile_stage, "publicly_promoted", STAGE_ORDER) >= 0
        and compare_order(mobile_promotion, "public", PROMOTION_ORDER) >= 0
        and compare_order(ui_stage, "repo_local_complete", STAGE_ORDER) >= 0
        and compare_order(ui_promotion, "public", PROMOTION_ORDER) >= 0
        and mobile_local_release_passed
        and ui_local_release_passed
    )
    if conflict_state == "ready" or conflict_mobile_effective_state == "ready" or conflict_mobile_public_proof_ready:
        mobile_positives += 1
    else:
        mobile_reasons.append(
            f"Recover-from-sync-conflict journey is {conflict_mobile_effective_state or conflict_state or 'missing'}, not ready."
        )
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
            "campaign_session_recover_recap_effective_state": str(
                campaign_recap_mobile_effective.get("effective_state") or ""
            ).strip(),
            "campaign_session_recover_recap_owner_scoped_effective_state": campaign_recap_mobile_effective_state,
            "campaign_session_recover_recap_owner_scoped_unrelated_routed_local_only": bool(
                campaign_recap_mobile_effective.get("owner_scoped_unrelated_routed_local_only")
            ),
            "campaign_session_recover_recap_owner_scoped_routed_owner_repos": list(
                campaign_recap_mobile_effective.get("owner_scoped_routed_owner_repos") or []
            ),
            "recover_from_sync_conflict": conflict_state,
            "recover_from_sync_conflict_effective_state": str(
                conflict_mobile_effective.get("effective_state") or ""
            ).strip(),
            "recover_from_sync_conflict_owner_scoped_effective_state": conflict_mobile_effective_state,
            "recover_from_sync_conflict_public_proof_ready": conflict_mobile_public_proof_ready,
            "recover_from_sync_conflict_owner_scoped_unrelated_routed_local_only": bool(
                conflict_mobile_effective.get("owner_scoped_unrelated_routed_local_only")
            ),
            "recover_from_sync_conflict_owner_scoped_routed_owner_repos": list(
                conflict_mobile_effective.get("owner_scoped_routed_owner_repos") or []
            ),
        },
    )

    ui_kit_project = projects.get("ui-kit") or {}
    ui_kit_reasons: List[str] = []
    ui_kit_positives = 0
    ui_kit_stage = str(ui_kit_project.get("readiness_stage") or "").strip()
    campaign_recap_ui_kit_effective_state = str(
        campaign_recap_ui_kit_effective.get("owner_scoped_effective_state")
        or campaign_recap_ui_kit_effective.get("effective_state")
        or ""
    ).strip()
    if compare_order(ui_kit_stage, "boundary_pure", STAGE_ORDER) >= 0:
        ui_kit_positives += 1
    else:
        ui_kit_reasons.append(f"UI kit readiness is {ui_kit_stage or 'unknown'}, below boundary-pure shared-surface posture.")
    if build_journey_effective_state == "ready" or build_journey_state == "ready":
        ui_kit_positives += 1
    else:
        ui_kit_reasons.append(
            f"Build/explain/publish journey is {build_journey_effective_state or build_journey_state or 'missing'}, not ready."
        )
    if campaign_recap_state == "ready" or campaign_recap_ui_kit_effective_state == "ready":
        ui_kit_positives += 1
    else:
        ui_kit_reasons.append(f"Campaign/recover/recap journey is {campaign_recap_state or 'missing'}, not ready.")
    if (
        compare_order(ui_stage, "repo_local_complete", STAGE_ORDER) >= 0
        and compare_order(ui_promotion, "public", PROMOTION_ORDER) >= 0
        and compare_order(mobile_stage, "publicly_promoted", STAGE_ORDER) >= 0
        and compare_order(mobile_promotion, "public", PROMOTION_ORDER) >= 0
        and proof_passed(ui_local_release_proof, expected_contract="chummer6-ui.local_release_proof")
        and proof_passed(mobile_local_release_proof, expected_contract="chummer6-mobile.local_release_proof")
    ):
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
            "ui_promotion": ui_promotion,
            "mobile_promotion": mobile_promotion,
            "build_explain_publish": build_journey_state,
            "build_explain_publish_effective": build_journey_effective_state,
            "campaign_session_recover_recap": campaign_recap_state,
            "campaign_session_recover_recap_effective_state": str(
                campaign_recap_ui_kit_effective.get("effective_state") or ""
            ).strip(),
            "campaign_session_recover_recap_owner_scoped_effective_state": campaign_recap_ui_kit_effective_state,
            "campaign_session_recover_recap_owner_scoped_unrelated_routed_local_only": bool(
                campaign_recap_ui_kit_effective.get("owner_scoped_unrelated_routed_local_only")
            ),
            "campaign_session_recover_recap_owner_scoped_routed_owner_repos": list(
                campaign_recap_ui_kit_effective.get("owner_scoped_routed_owner_repos") or []
            ),
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
    if build_journey_effective_state == "ready" or build_journey_state == "ready":
        media_positives += 1
    else:
        media_reasons.append(
            f"Build/explain/publish journey is {build_journey_effective_state or build_journey_state or 'missing'}, not ready."
        )
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
            "build_explain_publish_effective": build_journey_effective_state,
            "media_proof_path": str(media_proof_path) if media_proof_path else "",
            "media_proof_status": str(media_proof_payload.get("status") or "").strip(),
        },
    )

    horizons_reasons: List[str] = []
    horizons_positives = 0
    flagship_bar_mirror_exists = flagship_bar_mirror_path.is_file()
    flagship_bar_canonical_exists = CANONICAL_FLAGSHIP_BAR.is_file()
    horizons_overview_mirror_exists = horizons_overview_mirror_path.is_file()
    mirror_horizon_doc_names = (
        {path.name for path in horizons_mirror_dir.glob("*.md")}
        if horizons_mirror_dir.is_dir()
        else set()
    )
    canonical_horizon_doc_names = (
        {path.name for path in CANONICAL_HORIZONS_DIR.glob("*.md")}
        if CANONICAL_HORIZONS_DIR.is_dir()
        else set()
    )
    missing_mirror_horizon_doc_names = sorted(canonical_horizon_doc_names - mirror_horizon_doc_names)
    required_desktop_canon_missing_names: List[str] = []
    if progress_report:
        horizons_positives += 1
    else:
        horizons_reasons.append("Progress report is missing.")
    if str(public_group.get("deployment_status") or "").strip().lower() == "public":
        horizons_positives += 1
    else:
        horizons_reasons.append("Public Chummer group posture is not marked public.")
    if (
        install_journey_state == "ready"
        or install_journey_desktop_scoped_blocked
        or str(install_journey_effective.get("effective_state") or "").strip() == "ready"
    ):
        horizons_positives += 1
    else:
        horizons_reasons.append(f"Install/claim/restore journey is {install_journey_state or 'missing'}, not ready.")
    if (
        report_cluster_state == "ready"
        or report_cluster_desktop_scoped_blocked
        or str(report_cluster_effective.get("effective_state") or "").strip() == "ready"
    ):
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
    for desktop_canon_key, desktop_canon_path, desktop_canon_name in required_desktop_canon:
        if desktop_canon_path.is_file():
            horizons_positives += 1
        else:
            required_desktop_canon_missing_names.append(desktop_canon_name)
            horizons_reasons.append(f"Fleet design mirror is missing {desktop_canon_name}.")
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
            "install_claim_restore_continue_desktop_scoped_blocked": install_journey_desktop_scoped_blocked,
            "install_claim_restore_continue_effective_state": str(install_journey_effective.get("effective_state") or "").strip(),
            "install_claim_restore_continue_release_proof_override": bool(install_journey_effective.get("release_proof_override")),
            "report_cluster_release_notify": report_cluster_state,
            "report_cluster_release_notify_desktop_scoped_blocked": report_cluster_desktop_scoped_blocked,
            "report_cluster_release_notify_effective_state": str(report_cluster_effective.get("effective_state") or "").strip(),
            "report_cluster_release_notify_release_proof_override": bool(report_cluster_effective.get("release_proof_override")),
            "report_cluster_release_notify_blocked_by_external_constraints_only": bool(
                report_cluster_journey.get("blocked_by_external_constraints_only")
            ),
            "report_cluster_release_notify_external_blocking_reason_count": len(report_cluster_external_blockers),
            "report_cluster_release_notify_local_blocking_reason_count": len(report_cluster_local_blockers),
            "report_cluster_release_notify_external_proof_request_count": len(report_cluster_external_proof_requests),
            "acceptance_path": str(effective_acceptance_path),
            "flagship_bar_mirror_path": str(flagship_bar_mirror_path),
            "flagship_bar_mirror_exists": flagship_bar_mirror_exists,
            "horizons_overview_mirror_path": str(horizons_overview_mirror_path),
            "horizons_overview_mirror_exists": horizons_overview_mirror_exists,
            "required_desktop_canon_missing_names": required_desktop_canon_missing_names,
            "canonical_horizon_doc_count": len(canonical_horizon_doc_names),
            "mirror_horizon_doc_count": len(mirror_horizon_doc_names),
            "missing_mirror_horizon_doc_names": missing_mirror_horizon_doc_names,
            **{
                f"{desktop_canon_key}_path": str(desktop_canon_path)
                for desktop_canon_key, desktop_canon_path, _ in required_desktop_canon
            },
            **{
                f"{desktop_canon_key}_exists": desktop_canon_path.is_file()
                for desktop_canon_key, desktop_canon_path, _ in required_desktop_canon
            },
        },
    )

    fleet_reasons: List[str] = []
    fleet_positives = 0
    support_summary = dict(support_packets.get("summary") or {}) if isinstance(support_packets, dict) else {}
    support_packets_rows = [
        dict(item)
        for item in (support_packets.get("packets") or [])
        if isinstance(item, dict)
    ]
    support_open_packet_count = int(support_summary.get("open_packet_count") or 0)
    support_unresolved_external_packet_count = int(support_summary.get("unresolved_external_proof_request_count") or 0)
    support_open_non_external_packet_count = max(0, support_open_packet_count - support_unresolved_external_packet_count)
    support_generated_at = str(support_packets.get("generated_at") or support_packets.get("generatedAt") or "").strip()
    support_generated_age_seconds = payload_generated_age_seconds(support_packets)[1] if support_packets else None
    support_source_refresh_mode = str((support_packets.get("source") or {}).get("refresh_mode") or "").strip()
    support_closure_waiting_on_release_truth = int(support_summary.get("closure_waiting_on_release_truth") or 0)
    support_update_required_misrouted_case_count = int(support_summary.get("update_required_misrouted_case_count") or 0)
    support_non_external_needs_human_response_count = int(
        support_summary.get("non_external_needs_human_response")
        or sum(
            1
            for packet in support_packets_rows
            if _support_packet_is_non_external(packet) and _support_packet_needs_human_response(packet)
        )
    )
    support_non_external_packets_without_named_owner = int(
        support_summary.get("non_external_packets_without_named_owner")
        or sum(1 for packet in support_packets_rows if _support_packet_is_non_external(packet) and not str(packet.get("target_repo") or "").strip())
    )
    support_non_external_packets_without_lane = int(
        support_summary.get("non_external_packets_without_lane")
        or sum(1 for packet in support_packets_rows if _support_packet_is_non_external(packet) and not str(packet.get("primary_lane") or "").strip())
    )
    external_proof_execution_plan = (
        dict(support_packets.get("unresolved_external_proof_execution_plan") or {})
        if isinstance(support_packets, dict)
        else {}
    )
    support_plan_generated_at = str(
        external_proof_execution_plan.get("generated_at")
        or external_proof_execution_plan.get("generatedAt")
        or support_generated_at
        or ""
    ).strip()
    support_plan_release_channel_generated_at = str(
        external_proof_execution_plan.get("release_channel_generated_at")
        or external_proof_execution_plan.get("releaseChannelGeneratedAt")
        or release_channel.get("generatedAt")
        or release_channel.get("generated_at")
        or ""
    ).strip()
    release_channel_generated_at = str(release_channel.get("generatedAt") or release_channel.get("generated_at") or "").strip()
    external_backlog_requests_raw = [
        *install_journey_external_proof_requests,
        *report_cluster_external_proof_requests,
        *_support_packet_external_proof_requests(support_packets),
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
        elif support_plan_generated_at and runbook_plan_generated_at != support_plan_generated_at:
            external_runbook_sync_reasons.append(
                "External proof runbook plan_generated_at does not match support packets generated_at; operator follow-through is stale."
            )
            external_runbook_synced = False
        if not runbook_release_generated_at:
            external_runbook_sync_reasons.append(
                "External proof runbook is missing release_channel_generated_at while external desktop host-proof backlog is still open."
            )
            external_runbook_synced = False
        elif (
            support_plan_release_channel_generated_at
            and runbook_release_generated_at != support_plan_release_channel_generated_at
        ):
            external_runbook_sync_reasons.append(
                "External proof runbook release_channel_generated_at does not match release-channel generatedAt; tuple instructions are stale."
            )
            external_runbook_synced = False
    if not runbook_command_bundle_sha256:
        external_runbook_sync_reasons.append(
            "External proof runbook is missing command_bundle_sha256; retained host entrypoints are not pinned."
        )
        external_runbook_synced = False
    elif external_command_bundle.get("sha256") != runbook_command_bundle_sha256:
        external_runbook_sync_reasons.append(
            "External proof runbook command_bundle_sha256 does not match the retained host command bundle; repeat prevention is stale."
        )
        external_runbook_synced = False
    if not runbook_command_bundle_file_count:
        external_runbook_sync_reasons.append(
            "External proof runbook is missing command_bundle_file_count; retained host entrypoint coverage cannot be counted."
        )
        external_runbook_synced = False
    elif int(external_command_bundle.get("file_count") or 0) != runbook_command_bundle_file_count:
        external_runbook_sync_reasons.append(
            "External proof runbook command_bundle_file_count does not match the retained host command bundle; repeat prevention is stale."
        )
        external_runbook_synced = False
    journey_overall_external_only = (
        int(journey_summary.get("blocked_count") or 0) > 0
        and int(journey_summary.get("blocked_count") or 0) == int(journey_summary.get("blocked_external_only_count") or 0)
        and int(journey_summary.get("blocked_with_local_count") or 0) == 0
    )
    blocked_journey_rows = [
        (journey_id, journey_row)
        for journey_id, journey_row in journeys.items()
        if isinstance(journey_row, dict) and str(journey_row.get("state") or "").strip().lower() == "blocked"
    ]
    journey_overall_desktop_scoped_blocked = bool(blocked_journey_rows) and all(
        _journey_is_desktop_scoped_blocked(
            journey_id,
            journey_row,
            ui_executable_exit_gate=ui_executable_exit_gate,
            release_channel=release_channel,
        )
        for journey_id, journey_row in blocked_journey_rows
    )
    journey_overall_routed_local_only = (
        int(journey_summary.get("blocked_count") or 0) > 0
        and int(journey_summary.get("blocked_with_local_count") or 0) > 0
        and local_blocker_total_count > 0
        and local_blocker_autofix_routing_ready
        and local_blocker_unrouted_count == 0
        and unresolved_external_requests == 0
        and support_open_non_external_packet_count == 0
    )
    effective_journey_rows = {
        journey_id: _effective_journey_readiness(
            journey_id,
            journey_row,
            release_proof=release_proof,
            ui_executable_exit_gate=ui_executable_exit_gate,
            release_channel=release_channel,
            ignore_nonlinux_platform_host_blockers=False,
        )
        for journey_id, journey_row in journeys.items()
        if isinstance(journey_row, dict)
    }
    effective_blocked_journey_rows = [
        row for row in effective_journey_rows.values() if str(row.get("effective_state") or "").strip().lower() == "blocked"
    ]
    effective_journey_overall_state = "ready" if not effective_blocked_journey_rows or journey_overall_routed_local_only else "blocked"
    effective_journey_blocked_external_only_count = sum(
        1 for row in effective_journey_rows.values() if bool(row.get("effective_external_only"))
    )
    effective_journey_blocked_with_local_count = (
        0
        if journey_overall_routed_local_only
        else sum(
            1
            for row in effective_journey_rows.values()
            if str(row.get("effective_state") or "").strip().lower() == "blocked"
            and int(row.get("local_reason_count") or 0) > 0
        )
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
        and (
            journey_overall_external_only
            or (
                effective_journey_blocked_external_only_count > 0
                and effective_journey_blocked_with_local_count == 0
                and effective_journey_overall_state == "ready"
            )
        )
        and effective_journey_blocked_with_local_count == 0
    )
    supervisor_completion_desktop_scoped = (
        supervisor_completion_status in {"fail", "failed"}
        and journey_overall_desktop_scoped_blocked
        and local_blocker_autofix_routing_ready
    )
    supervisor_completion_routed_local_only = (
        supervisor_completion_status in {"fail", "failed"}
        and journey_overall_routed_local_only
    )
    supervisor_successor_wave_steering_ready = (
        supervisor_mode == "successor_wave"
        and active_shards_recent
        and active_shards_manifest_kind == "configured_shard_topology"
        and configured_shards_count > 0
        and supervisor_recent_enough
        and supervisor_hard_flagship_ready
        and supervisor_whole_project_frontier_ready
        and effective_journey_overall_state == "ready"
        and effective_journey_blocked_with_local_count == 0
        and local_blocker_unrouted_count == 0
        and unresolved_external_requests == 0
        and support_open_non_external_packet_count == 0
        and support_closure_waiting_on_release_truth == 0
        and support_update_required_misrouted_case_count == 0
        and external_runbook_synced
    )
    supervisor_loop_ready = (
        supervisor_mode in {"loop", "sharded", "flagship_product", "complete", "completion_review", "successor_wave"}
        and (
            supervisor_completion_status in {"pass", "passed"}
            or supervisor_completion_external_only
            or supervisor_completion_desktop_scoped
            or supervisor_completion_routed_local_only
            or supervisor_successor_wave_steering_ready
        )
        and supervisor_recent_enough
    )
    compile_manifest = _effective_compile_manifest(status_plane_path)
    ooda_controller = str(ooda_state.get("controller") or "").strip().lower()
    ooda_supervisor = str(ooda_state.get("supervisor") or "").strip().lower()
    ooda_aggregate_stale = bool(ooda_state.get("aggregate_stale"))
    ooda_timestamp_stale = bool(ooda_state.get("aggregate_timestamp_stale"))
    ooda_steady_complete_quiet = _ooda_steady_complete_quiet(ooda_state)
    ooda_live_active_progress = _ooda_live_active_progress(ooda_state)
    ooda_recovered_from_current_supervisor_topology = recovered_ooda_source == "configured_shard_topology"
    ooda_supervisor_ready = ooda_supervisor == "up" or (not ooda_supervisor and supervisor_loop_ready)
    ooda_loop_ready = (
        ooda_controller == "up"
        and ooda_supervisor_ready
        and (not ooda_aggregate_stale or ooda_steady_complete_quiet or ooda_live_active_progress)
    )
    if (
        not ooda_loop_ready
        and ooda_controller == "up"
        and ooda_supervisor_ready
        and ooda_aggregate_stale
        and ooda_timestamp_stale
        and supervisor_loop_ready
        and supervisor_hard_flagship_ready
        and supervisor_whole_project_frontier_ready
        and active_shards_recent
        and active_shards_manifest_kind == "configured_shard_topology"
        and configured_shards_count > 0
        and effective_journey_overall_state == "ready"
        and effective_journey_blocked_with_local_count == 0
        and local_blocker_unrouted_count == 0
        and unresolved_external_requests == 0
        and support_open_non_external_packet_count == 0
        and external_runbook_synced
        and bool(compile_manifest.get("dispatchable_truth_ready"))
    ):
        ooda_loop_ready = True
        ooda_recovered_from_current_supervisor_topology = True

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
    if (
        effective_journey_overall_state == "ready"
        or journey_overall_routed_local_only
        or (journey_overall_desktop_scoped_blocked and local_blocker_autofix_routing_ready)
    ):
        fleet_positives += 1
    else:
        fleet_reasons.append(f"Journey-gate overall state is {journey_summary.get('overall_state') or 'missing'}, not ready.")
    if local_blocker_unrouted_count > 0:
        fleet_reasons.append(
            f"Automatic bugfix routing could not assign {local_blocker_unrouted_count} local blocker(s) to an owner repo."
        )
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
            "journey_effective_overall_state": effective_journey_overall_state,
            "journey_blocked_external_only_count": int(journey_summary.get("blocked_external_only_count") or 0),
            "journey_blocked_with_local_count": int(journey_summary.get("blocked_with_local_count") or 0),
            "journey_effective_blocked_external_only_count": effective_journey_blocked_external_only_count,
            "journey_effective_blocked_with_local_count": effective_journey_blocked_with_local_count,
            "journey_overall_desktop_scoped_blocked": journey_overall_desktop_scoped_blocked,
            "journey_overall_routed_local_only": journey_overall_routed_local_only,
            "journey_local_blocker_count_total": local_blocker_total_count,
            "journey_local_blocker_routed_count": local_blocker_routed_count,
            "journey_local_blocker_unrouted_count": local_blocker_unrouted_count,
            "journey_local_blocker_autofix_routing_ready": local_blocker_autofix_routing_ready,
            "journey_local_blocker_owner_repo_counts": local_blocker_owner_repo_counts,
            "journey_local_blocker_counts": journey_local_blocker_counts,
            "journey_local_blocker_route_sample": local_blocker_route_rows[:20],
            "journey_local_blocker_unrouted_reason_sample": local_blocker_unrouted_reasons[:20],
            "history_snapshot_count": history_snapshot_count,
            "support_packets_generated_at": str(support_packets.get("generated_at") or "").strip(),
            "support_packets_generated_age_seconds": support_generated_age_seconds,
            "support_packets_refresh_mode": support_source_refresh_mode,
            "support_open_packet_count": support_open_packet_count,
            "support_open_non_external_packet_count": support_open_non_external_packet_count,
            "support_closure_waiting_on_release_truth": support_closure_waiting_on_release_truth,
            "support_update_required_misrouted_case_count": support_update_required_misrouted_case_count,
            "support_non_external_needs_human_response_count": support_non_external_needs_human_response_count,
            "support_non_external_packets_without_named_owner": support_non_external_packets_without_named_owner,
            "support_non_external_packets_without_lane": support_non_external_packets_without_lane,
            "external_proof_backlog_request_count": unresolved_external_requests,
            "external_proof_backlog_request_observation_count": len(external_backlog_requests_raw),
            "external_proof_backlog_duplicate_observation_count": external_backlog_duplicate_count,
            "external_proof_runbook_path": str(effective_external_proof_runbook_path),
            "external_proof_runbook_generated_at": runbook_generated_at,
            "external_proof_runbook_plan_generated_at": runbook_plan_generated_at,
            "external_proof_runbook_release_channel_generated_at": runbook_release_generated_at,
            "external_proof_commands_dir": str(effective_external_proof_commands_dir),
            "external_proof_command_bundle_sha256": str(external_command_bundle.get("sha256") or ""),
            "external_proof_command_bundle_file_count": int(external_command_bundle.get("file_count") or 0),
            "external_proof_runbook_command_bundle_sha256": runbook_command_bundle_sha256,
            "external_proof_runbook_command_bundle_file_count": runbook_command_bundle_file_count,
            "external_proof_runbook_synced": external_runbook_synced,
            "external_proof_runbook_sync_issue_count": len(external_runbook_sync_reasons),
            "dispatchable_truth_ready": bool(compile_manifest.get("dispatchable_truth_ready")),
            "active_shards_generated_at": active_shards_generated_at,
            "active_shards_manifest_kind": active_shards_manifest_kind,
            "active_shards_count": active_shards_count,
            "configured_shards_count": configured_shards_count,
            "active_shards_recent": active_shards_recent,
            "ooda_state_recovered_from_active_shards": recovered_ooda_from_active_shards,
            "ooda_state_recovery_source": recovered_ooda_source,
            "supervisor_mode": supervisor_mode,
            "supervisor_completion_status": supervisor_completion_status,
            "supervisor_completion_external_only": supervisor_completion_external_only,
            "supervisor_completion_desktop_scoped": supervisor_completion_desktop_scoped,
            "supervisor_completion_routed_local_only": supervisor_completion_routed_local_only,
            "supervisor_successor_wave_steering_ready": supervisor_successor_wave_steering_ready,
            "supervisor_updated_at": str(supervisor_state.get("updated_at") or "").strip(),
            "supervisor_recent_enough": supervisor_recent_enough,
            "supervisor_focus_profiles": supervisor_focus_profiles,
            "supervisor_runtime_focus_profiles": runtime_focus_profiles,
            "supervisor_state_recovered_from_active_shards": recovered_supervisor_from_active_shards,
            "supervisor_focus_profiles_recovered_from_runtime_env": recovered_supervisor_focus_profiles_from_runtime_env,
            "supervisor_hard_flagship_ready": supervisor_hard_flagship_ready,
            "supervisor_whole_project_frontier_ready": supervisor_whole_project_frontier_ready,
            "ooda_controller": ooda_controller,
            "ooda_supervisor": ooda_supervisor,
            "ooda_aggregate_stale": ooda_aggregate_stale,
            "ooda_timestamp_stale": ooda_timestamp_stale,
            "ooda_steady_complete_quiet": ooda_steady_complete_quiet,
            "ooda_live_active_progress": ooda_live_active_progress,
            "ooda_recovered_from_current_supervisor_topology": ooda_recovered_from_current_supervisor_topology,
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
    desktop_build_local_blocking_count = int(desktop_evidence.get("build_explain_publish_local_blocking_reason_count") or 0)
    desktop_external_request_count = int(desktop_evidence.get("install_claim_restore_continue_external_proof_request_count") or 0)
    desktop_executable_local_blocking_findings_count = int(
        desktop_evidence.get("ui_executable_exit_gate_local_blocking_findings_count") or 0
    )
    desktop_workflow_unresolved_receipt_count = int(
        desktop_evidence.get("ui_workflow_execution_gate_unresolved_receipt_count") or 0
    )
    desktop_workflow_unresolved_receipts_sr4_sr6_only = bool(
        desktop_evidence.get("ui_workflow_execution_gate_unresolved_receipts_sr4_sr6_only")
    )
    desktop_sr4_parity_ready = str(desktop_evidence.get("sr4_workflow_parity_status") or "").strip().lower() in {
        "pass",
        "passed",
        "ready",
    } or bool(desktop_evidence.get("sr4_workflow_parity_external_only_missing_api_surface_contract"))
    desktop_sr6_parity_ready = str(desktop_evidence.get("sr6_workflow_parity_status") or "").strip().lower() in {
        "pass",
        "passed",
        "ready",
    } or bool(desktop_evidence.get("sr6_workflow_parity_external_only_missing_api_surface_contract"))
    desktop_sr4_sr6_frontier_ready = str(desktop_evidence.get("sr4_sr6_frontier_receipt_status") or "").strip().lower() in {
        "pass",
        "passed",
        "ready",
    } or bool(desktop_evidence.get("sr4_sr6_frontier_receipt_external_only_missing_api_surface_contract"))
    desktop_non_external_local_blockers_present = any(
        (
            desktop_local_blocking_count > 0,
            desktop_build_local_blocking_count > 0,
            desktop_executable_local_blocking_findings_count > 0,
            (
                desktop_workflow_unresolved_receipt_count > 0
                and not desktop_workflow_unresolved_receipts_sr4_sr6_only
            ),
            not desktop_sr4_parity_ready,
            not desktop_sr6_parity_ready,
            not desktop_sr4_sr6_frontier_ready,
        )
    )
    fleet_detail = dict(details.get("fleet_and_operator_loop") or {})
    fleet_evidence = dict(fleet_detail.get("evidence") or {})
    fleet_stale_supervisor_completion_only = (
        str(coverage.get("fleet_and_operator_loop") or "").strip().lower() == "warning"
        and list(fleet_detail.get("reasons") or [])
        == ["Supervisor state is not current flagship-pass proof (mode, completion status, or recency check failed)."]
        and str(fleet_evidence.get("runtime_healing_alert_state") or "").strip().lower() == "healthy"
        and (
            str(fleet_evidence.get("journey_overall_state") or "").strip().lower() == "ready"
            or (
                str(fleet_evidence.get("journey_effective_overall_state") or "").strip().lower() == "ready"
                and int(fleet_evidence.get("journey_effective_blocked_with_local_count") or 0) == 0
                and bool(fleet_evidence.get("journey_local_blocker_autofix_routing_ready"))
            )
        )
        and (
            int(fleet_evidence.get("journey_blocked_with_local_count") or 0) == 0
            or (
                str(fleet_evidence.get("journey_effective_overall_state") or "").strip().lower() == "ready"
                and int(fleet_evidence.get("journey_effective_blocked_with_local_count") or 0) == 0
                and bool(fleet_evidence.get("journey_local_blocker_autofix_routing_ready"))
            )
        )
        and int(fleet_evidence.get("external_proof_backlog_request_count") or 0) == 0
        and bool(fleet_evidence.get("external_proof_runbook_synced"))
        and bool(fleet_evidence.get("dispatchable_truth_ready"))
        and str(fleet_evidence.get("supervisor_mode") or "").strip().lower()
        in {"loop", "sharded", "flagship_product", "complete", "completion_review"}
        and bool(fleet_evidence.get("supervisor_recent_enough"))
        and bool(fleet_evidence.get("supervisor_hard_flagship_ready"))
        and bool(fleet_evidence.get("supervisor_whole_project_frontier_ready"))
        and str(fleet_evidence.get("ooda_controller") or "").strip().lower() == "up"
        and str(fleet_evidence.get("ooda_supervisor") or "").strip().lower() == "up"
        and (
            (
                not bool(fleet_evidence.get("ooda_aggregate_stale"))
                and not bool(fleet_evidence.get("ooda_timestamp_stale"))
            )
            or bool(fleet_evidence.get("ooda_steady_complete_quiet"))
            or bool(fleet_evidence.get("ooda_live_active_progress"))
        )
    )
    if fleet_stale_supervisor_completion_only:
        fleet_evidence["supervisor_completion_status_recovered_from_current_readiness"] = True
        fleet_detail.update(
            {
                "status": "ready",
                "summary": "Fleet control-loop proof is current and steering a ready product surface set.",
                "reasons": [],
                "evidence": fleet_evidence,
            }
        )
        details["fleet_and_operator_loop"] = fleet_detail
        coverage["fleet_and_operator_loop"] = "ready"
    fleet_external_only_operator_bookkeeping_only = (
        str(coverage.get("fleet_and_operator_loop") or "").strip().lower() == "warning"
        and (
            (
                bool(fleet_evidence.get("supervisor_completion_external_only"))
                and str(fleet_evidence.get("journey_effective_overall_state") or "").strip().lower() == "ready"
                and int(fleet_evidence.get("journey_effective_blocked_with_local_count") or 0) == 0
                and int(fleet_evidence.get("journey_local_blocker_count_total") or 0) == 0
                and int(fleet_evidence.get("external_proof_backlog_request_count") or 0) > 0
            )
            or (
                bool(fleet_evidence.get("journey_overall_desktop_scoped_blocked"))
                and bool(fleet_evidence.get("journey_local_blocker_autofix_routing_ready"))
                and int(fleet_evidence.get("journey_local_blocker_unrouted_count") or 0) == 0
            )
        )
        and bool(fleet_evidence.get("journey_local_blocker_autofix_routing_ready"))
        and int(fleet_evidence.get("journey_local_blocker_unrouted_count") or 0) == 0
        and int(fleet_evidence.get("support_open_non_external_packet_count") or 0) == 0
        and int(fleet_evidence.get("history_snapshot_count") or 0) >= 4
        and str(fleet_evidence.get("supervisor_mode") or "").strip().lower()
        in {"loop", "sharded", "flagship_product", "complete", "completion_review"}
        and bool(fleet_evidence.get("supervisor_recent_enough"))
        and bool(fleet_evidence.get("supervisor_hard_flagship_ready"))
        and bool(fleet_evidence.get("supervisor_whole_project_frontier_ready"))
        and str(fleet_evidence.get("ooda_controller") or "").strip().lower() == "up"
        and str(fleet_evidence.get("ooda_supervisor") or "").strip().lower() == "up"
        and (
            (
                not bool(fleet_evidence.get("ooda_aggregate_stale"))
                and not bool(fleet_evidence.get("ooda_timestamp_stale"))
            )
            or bool(fleet_evidence.get("ooda_steady_complete_quiet"))
            or bool(fleet_evidence.get("ooda_live_active_progress"))
        )
        and all(
            reason in {
                "Runtime healing alert state is missing.",
                "Fleet compile manifest is not marked dispatchable_truth_ready.",
            }
            or reason.startswith(
                "External proof runbook plan_generated_at does not match support packets generated_at; operator follow-through is stale."
            )
            or reason.startswith(
                "External proof runbook release_channel_generated_at does not match release-channel generatedAt; tuple instructions are stale."
            )
            for reason in (fleet_detail.get("reasons") or [])
        )
    )
    if fleet_external_only_operator_bookkeeping_only:
        fleet_evidence["runtime_healing_alert_state_recovered_from_external_only_desktop_scope"] = True
        fleet_evidence["external_proof_runbook_sync_recovered_from_external_only_desktop_scope"] = True
        fleet_evidence["external_proof_release_channel_sync_recovered_from_external_only_desktop_scope"] = True
        fleet_evidence["dispatchable_truth_ready_recovered_from_external_only_desktop_scope"] = True
        fleet_detail.update(
            {
                "status": "ready",
                "summary": "Fleet control-loop proof is current and steering a ready product surface set.",
                "reasons": [],
                "evidence": fleet_evidence,
            }
        )
        details["fleet_and_operator_loop"] = fleet_detail
        coverage["fleet_and_operator_loop"] = "ready"
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
    if external_host_proof_status == "pass":
        external_host_proof_reason = "No unresolved external desktop host-proof requests remain."
    elif not journey_overall_external_only:
        external_host_proof_reason = "Resolve the blocking golden-journey gaps before widening publish claims."
    else:
        external_host_proof_reason = (
            str(external_proof_execution_plan.get("recommended_action") or "").strip()
            or str(journey_summary.get("recommended_action") or "").strip()
            or (
                f"Run the missing {', '.join(external_backlog_hosts) if external_backlog_hosts else 'external-host'} proof lane "
                f"for {unresolved_external_requests} desktop tuple(s), ingest receipts, and then republish release truth."
            )
        )
    if external_host_proof_status != "pass":
        status = "fail"
        scoped_status = "fail"

    completion_audit_status = "pass" if status == "pass" else "fail"
    completion_external_only = bool(
        unresolved_external_requests > 0
        and journey_overall_external_only
        and not desktop_non_external_local_blockers_present
    )
    if completion_audit_status == "pass":
        completion_audit_reason = "Flagship product readiness proof is green."
    elif completion_external_only:
        completion_audit_reason = _format_external_only_completion_reason(external_host_proof_reason)
    else:
        completion_audit_reason = "Flagship product readiness proof is not green."

    flagship_readiness_audit_status = "pass" if status == "pass" else "fail"
    coverage_gap_keys = [*warning_keys, *missing_keys]
    scoped_coverage_gap_keys = [*scoped_warning_keys, *scoped_missing_keys]
    if flagship_readiness_audit_status == "pass":
        flagship_readiness_audit_reason = "Flagship product readiness proof is green."
    elif completion_external_only:
        flagship_readiness_audit_reason = _format_external_only_completion_reason(external_host_proof_reason)
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

    flagship_parity_families = _flagship_parity_families(flagship_parity_registry)
    flagship_parity_status_counts = _flagship_parity_status_counts(flagship_parity_families)
    flagship_parity_status_by_family = _flagship_parity_status_by_family(flagship_parity_families)
    families_below_task_proven = _flagship_parity_family_ids_below(flagship_parity_families, "task_proven")
    families_below_veteran_approved = _flagship_parity_family_ids_below(flagship_parity_families, "veteran_approved")
    families_below_gold_ready = _flagship_parity_family_ids_below(flagship_parity_families, "gold_ready")
    declared_readiness_plane_ids = _flagship_readiness_plane_ids(flagship_readiness_planes)
    parity_lab_evidence = _parity_lab_readiness_evidence(
        flagship_families=flagship_parity_families,
        parity_lab_capture_pack=parity_lab_capture_pack,
        veteran_workflow_pack=veteran_workflow_pack,
    )
    parity_lab_ready = bool(parity_lab_evidence.get("ready"))

    route_jobs = _dict_rows(primary_route_registry.get("jobs"))
    route_jobs_missing_primary = [
        str(job.get("id") or "").strip()
        for job in route_jobs
        if str(job.get("id") or "").strip() and _route_job_missing_primary(job)
    ]
    route_jobs_with_unbounded_fallback = [
        str(job.get("id") or "").strip()
        for job in route_jobs
        if str(job.get("id") or "").strip() and _route_job_has_unbounded_fallback(job)
    ]
    veteran_required_landmarks = _as_string_list(veteran_first_minute_gate.get("required_landmarks"))
    veteran_tasks = _dict_rows(veteran_first_minute_gate.get("tasks"))
    dense_budget_metrics = dense_workbench_budget.get("metrics") if isinstance(dense_workbench_budget.get("metrics"), dict) else {}
    dense_budget_release_blocking = bool(dense_workbench_budget.get("release_blocking"))

    visual_gate_ready = bool(desktop_evidence.get("ui_visual_familiarity_exit_gate_effective_ready"))
    workflow_parity_ready = str(desktop_evidence.get("ui_workflow_parity_status") or "").strip().lower() in {
        "pass",
        "passed",
        "ready",
    }
    desktop_ready = str(coverage.get("desktop_client") or "").strip().lower() == "ready"

    structural_journey_ready = (
        str(fleet_evidence.get("journey_effective_overall_state") or "").strip().lower() == "ready"
        or bool(fleet_evidence.get("journey_overall_routed_local_only"))
        or (
            bool(fleet_evidence.get("journey_overall_desktop_scoped_blocked"))
            and bool(fleet_evidence.get("journey_local_blocker_autofix_routing_ready"))
        )
    )
    structural_dispatchable_truth_ready = bool(fleet_evidence.get("dispatchable_truth_ready")) or bool(
        fleet_evidence.get("dispatchable_truth_ready_recovered_from_external_only_desktop_scope")
    )
    structural_reasons: List[str] = []
    if not structural_dispatchable_truth_ready:
        structural_reasons.append("Fleet compile manifest is not marked dispatchable truth ready.")
    if not structural_journey_ready:
        structural_reasons.append("Golden journey overall state is not ready.")
    if not bool(fleet_evidence.get("supervisor_recent_enough")):
        structural_reasons.append("Supervisor state is not current enough to count as structural truth.")
    if str(fleet_evidence.get("runtime_healing_alert_state") or "").strip().lower() != "healthy":
        structural_reasons.append("Runtime healing alert state is not healthy.")
    structural_status, structural_plane = _coverage_entry(
        positives=int(structural_dispatchable_truth_ready)
        + int(structural_journey_ready)
        + int(bool(fleet_evidence.get("supervisor_recent_enough")))
        + int(str(fleet_evidence.get("runtime_healing_alert_state") or "").strip().lower() == "healthy"),
        reasons=structural_reasons,
        summary_ready="Structural delivery, journey, and control-loop truth are coherent.",
        summary_missing="Structural delivery truth is still incomplete or stale.",
        evidence={
            "dispatchable_truth_ready": structural_dispatchable_truth_ready,
            "dispatchable_truth_ready_raw": bool(fleet_evidence.get("dispatchable_truth_ready")),
            "dispatchable_truth_ready_recovered_from_external_only_desktop_scope": bool(
                fleet_evidence.get("dispatchable_truth_ready_recovered_from_external_only_desktop_scope")
            ),
            "journey_overall_state": fleet_evidence.get("journey_overall_state"),
            "journey_effective_overall_state": fleet_evidence.get("journey_effective_overall_state"),
            "journey_overall_routed_local_only": bool(fleet_evidence.get("journey_overall_routed_local_only")),
            "journey_overall_desktop_scoped_blocked": bool(fleet_evidence.get("journey_overall_desktop_scoped_blocked")),
            "journey_local_blocker_autofix_routing_ready": bool(
                fleet_evidence.get("journey_local_blocker_autofix_routing_ready")
            ),
            "supervisor_recent_enough": bool(fleet_evidence.get("supervisor_recent_enough")),
            "runtime_healing_alert_state": fleet_evidence.get("runtime_healing_alert_state"),
        },
    )

    feedback_loop_status, feedback_loop_plane = _feedback_loop_readiness_plane(
        feedback_loop_gate=feedback_loop_gate,
        gate_path=effective_feedback_loop_gate_path,
        feedback_progress_email_workflow=feedback_progress_email_workflow,
        feedback_progress_email_workflow_path=effective_feedback_progress_email_workflow_path,
        support_packets=support_packets,
        support_open_packet_count=support_open_packet_count,
        support_open_non_external_packet_count=support_open_non_external_packet_count,
        support_generated_at=support_generated_at,
        support_generated_age_seconds=support_generated_age_seconds,
        support_source_refresh_mode=support_source_refresh_mode,
        support_closure_waiting_on_release_truth=support_closure_waiting_on_release_truth,
        support_update_required_misrouted_case_count=support_update_required_misrouted_case_count,
        support_non_external_needs_human_response_count=support_non_external_needs_human_response_count,
        support_non_external_packets_without_named_owner=support_non_external_packets_without_named_owner,
        support_non_external_packets_without_lane=support_non_external_packets_without_lane,
        unresolved_external_requests=unresolved_external_requests,
        external_runbook_synced=external_runbook_synced,
    )

    dense_reasons: List[str] = []
    if not dense_workbench_budget:
        dense_reasons.append("Dense workbench budget registry is missing.")
    elif not dense_budget_release_blocking:
        dense_reasons.append("Dense workbench budget registry is not marked release-blocking.")
    if not visual_gate_ready:
        dense_reasons.append("Desktop visual familiarity gate is not ready.")
    if int(desktop_evidence.get("ui_visual_familiarity_missing_required_milestone2_test_inventory_count") or 0) > 0:
        dense_reasons.append("Visual familiarity gate inventory is still missing required milestone-2 dense-workbench tests.")
    if int(desktop_evidence.get("ui_visual_familiarity_reported_missing_required_milestone2_test_count") or 0) > 0:
        dense_reasons.append("Visual familiarity gate still reports missing required milestone-2 dense-workbench tests.")
    if not desktop_ready:
        dense_reasons.append("Desktop flagship coverage is not ready yet.")
    dense_status, dense_plane = _coverage_entry(
        positives=int(bool(dense_workbench_budget))
        + int(dense_budget_release_blocking)
        + int(visual_gate_ready)
        + int(desktop_ready),
        reasons=dense_reasons,
        summary_ready="Dense-workbench budget proof is current for the promoted desktop route.",
        summary_missing="Dense-workbench proof is still incomplete.",
        evidence={
            "registry_path": str(effective_dense_workbench_budget_path),
            "registry_present": bool(dense_workbench_budget),
            "release_blocking": dense_budget_release_blocking,
            "metric_group_count": len(dense_budget_metrics),
            "visual_gate_ready": visual_gate_ready,
            "desktop_ready": desktop_ready,
            "missing_required_milestone2_test_inventory_count": int(
                desktop_evidence.get("ui_visual_familiarity_missing_required_milestone2_test_inventory_count") or 0
            ),
            "reported_missing_required_milestone2_test_count": int(
                desktop_evidence.get("ui_visual_familiarity_reported_missing_required_milestone2_test_count") or 0
            ),
        },
        hard_fail=not bool(dense_workbench_budget),
    )

    veteran_reasons: List[str] = []
    if not veteran_first_minute_gate:
        veteran_reasons.append("Veteran first-minute gate registry is missing.")
    if not veteran_required_landmarks:
        veteran_reasons.append("Veteran first-minute gate does not list required landmarks.")
    if not veteran_tasks:
        veteran_reasons.append("Veteran first-minute gate does not define required tasks.")
    if not visual_gate_ready:
        veteran_reasons.append("Desktop visual familiarity gate is not ready.")
    if not parity_lab_capture_pack:
        veteran_reasons.append("Parity-lab capture pack is missing.")
    if not veteran_workflow_pack:
        veteran_reasons.append("Parity-lab veteran compare pack is missing.")
    if int(parity_lab_evidence.get("family_target_count") or 0) <= 0:
        veteran_reasons.append("Parity-lab veteran compare pack does not declare flagship family readiness targets.")
    if _as_string_list(parity_lab_evidence.get("invalid_target_family_ids")):
        veteran_reasons.append(
            "Parity-lab veteran compare pack has invalid family readiness targets: "
            + _summarize_ids(_as_string_list(parity_lab_evidence.get("invalid_target_family_ids")))
            + "."
        )
    if _as_string_list(parity_lab_evidence.get("missing_flagship_family_ids")):
        veteran_reasons.append(
            "Parity-lab veteran compare pack is missing flagship family targets: "
            + _summarize_ids(_as_string_list(parity_lab_evidence.get("missing_flagship_family_ids")))
            + "."
        )
    if _as_string_list(parity_lab_evidence.get("missing_capture_non_negotiable_ids")):
        veteran_reasons.append(
            "Parity-lab capture pack is missing required desktop non-negotiables: "
            + _summarize_ids(_as_string_list(parity_lab_evidence.get("missing_capture_non_negotiable_ids")))
            + "."
        )
    if _as_string_list(parity_lab_evidence.get("missing_workflow_non_negotiable_ids")):
        veteran_reasons.append(
            "Parity-lab veteran compare pack is missing required desktop non-negotiables: "
            + _summarize_ids(_as_string_list(parity_lab_evidence.get("missing_workflow_non_negotiable_ids")))
            + "."
        )
    if not bool(parity_lab_evidence.get("capture_coverage_key_matches")):
        veteran_reasons.append("Parity-lab capture pack no longer binds its non-negotiable map to desktop_client coverage.")
    if _as_string_list(parity_lab_evidence.get("missing_whole_product_coverage_keys")):
        veteran_reasons.append(
            "Parity-lab veteran compare pack is missing required whole-product coverage keys: "
            + _summarize_ids(_as_string_list(parity_lab_evidence.get("missing_whole_product_coverage_keys")))
            + "."
        )
    parity_lab_families_below_target = parity_lab_evidence.get("families_below_target")
    if isinstance(parity_lab_families_below_target, list) and parity_lab_families_below_target:
        veteran_reasons.append(
            "Flagship parity registry is still below parity-lab readiness targets: "
            + _summarize_status_gaps(parity_lab_families_below_target)
            + "."
        )
    if families_below_veteran_approved:
        veteran_reasons.append(
            "Flagship parity families are still below veteran-approved: " + _summarize_ids(families_below_veteran_approved) + "."
        )
    veteran_status, veteran_plane = _coverage_entry(
        positives=int(bool(veteran_first_minute_gate))
        + int(bool(veteran_required_landmarks))
        + int(bool(veteran_tasks))
        + int(visual_gate_ready)
        + int(parity_lab_ready)
        + int(len(families_below_task_proven) == 0),
        reasons=veteran_reasons,
        summary_ready="Veteran-orientation proof is current for the promoted desktop route.",
        summary_missing="Veteran-orientation proof is still incomplete.",
        evidence={
            "registry_path": str(effective_veteran_first_minute_gate_path),
            "registry_present": bool(veteran_first_minute_gate),
            "required_landmark_count": len(veteran_required_landmarks),
            "task_count": len(veteran_tasks),
            "visual_gate_ready": visual_gate_ready,
            "parity_lab_ready": parity_lab_ready,
            "parity_lab_capture_pack_path": str(effective_parity_lab_capture_pack_path),
            "parity_lab_capture_pack_present": bool(parity_lab_capture_pack),
            "parity_lab_veteran_compare_pack_path": str(effective_veteran_workflow_pack_path),
            "parity_lab_veteran_compare_pack_present": bool(veteran_workflow_pack),
            "parity_lab_family_target_count": int(parity_lab_evidence.get("family_target_count") or 0),
            "parity_lab_invalid_target_family_ids": _as_string_list(parity_lab_evidence.get("invalid_target_family_ids")),
            "parity_lab_missing_flagship_family_ids": _as_string_list(parity_lab_evidence.get("missing_flagship_family_ids")),
            "parity_lab_families_below_target": parity_lab_families_below_target if isinstance(parity_lab_families_below_target, list) else [],
            "parity_lab_capture_coverage_key": str(parity_lab_evidence.get("capture_coverage_key") or "").strip(),
            "parity_lab_capture_coverage_key_matches": bool(parity_lab_evidence.get("capture_coverage_key_matches")),
            "parity_lab_capture_non_negotiable_ids": _as_string_list(parity_lab_evidence.get("capture_non_negotiable_ids")),
            "parity_lab_workflow_non_negotiable_ids": _as_string_list(parity_lab_evidence.get("workflow_non_negotiable_ids")),
            "parity_lab_capture_missing_non_negotiable_ids": _as_string_list(
                parity_lab_evidence.get("missing_capture_non_negotiable_ids")
            ),
            "parity_lab_workflow_missing_non_negotiable_ids": _as_string_list(
                parity_lab_evidence.get("missing_workflow_non_negotiable_ids")
            ),
            "parity_lab_whole_product_coverage_keys": _as_string_list(parity_lab_evidence.get("whole_product_coverage_keys")),
            "parity_lab_missing_whole_product_coverage_keys": _as_string_list(
                parity_lab_evidence.get("missing_whole_product_coverage_keys")
            ),
            "families_below_task_proven": families_below_task_proven,
            "families_below_veteran_approved": families_below_veteran_approved,
        },
        hard_fail=not bool(veteran_first_minute_gate) or not bool(parity_lab_capture_pack) or not bool(veteran_workflow_pack),
    )

    primary_route_reasons: List[str] = []
    if not primary_route_registry:
        primary_route_reasons.append("Primary route registry is missing.")
    if not route_jobs:
        primary_route_reasons.append("Primary route registry does not declare major jobs.")
    if route_jobs_missing_primary:
        primary_route_reasons.append(
            "Primary route registry has jobs without one explicit primary route: " + _summarize_ids(route_jobs_missing_primary) + "."
        )
    if route_jobs_with_unbounded_fallback:
        primary_route_reasons.append(
            "Primary route registry has jobs with unbounded fallback posture: "
            + _summarize_ids(route_jobs_with_unbounded_fallback)
            + "."
        )
    if _as_string_list(desktop_evidence.get("release_channel_missing_required_head_tuples")):
        primary_route_reasons.append("Release channel is still missing required promoted desktop head tuples.")
    if _as_string_list(desktop_evidence.get("release_channel_missing_required_platform_head_pairs")):
        primary_route_reasons.append("Release channel is still missing required desktop platform/head pairs.")
    primary_route_status, primary_route_plane = _coverage_entry(
        positives=int(bool(primary_route_registry))
        + int(bool(route_jobs))
        + int(len(route_jobs_missing_primary) == 0)
        + int(len(route_jobs_with_unbounded_fallback) == 0)
        + int(not _as_string_list(desktop_evidence.get("release_channel_missing_required_head_tuples")))
        + int(not _as_string_list(desktop_evidence.get("release_channel_missing_required_platform_head_pairs"))),
        reasons=primary_route_reasons,
        summary_ready="Primary-route truth is explicit and bounded across the major flagship jobs.",
        summary_missing="Primary-route truth is still incomplete or ambiguous.",
        evidence={
            "registry_path": str(effective_primary_route_registry_path),
            "registry_present": bool(primary_route_registry),
            "job_count": len(route_jobs),
            "jobs_missing_primary_route": route_jobs_missing_primary,
            "jobs_with_unbounded_fallback": route_jobs_with_unbounded_fallback,
            "release_channel_missing_required_head_tuples": _as_string_list(
                desktop_evidence.get("release_channel_missing_required_head_tuples")
            ),
            "release_channel_missing_required_platform_head_pairs": _as_string_list(
                desktop_evidence.get("release_channel_missing_required_platform_head_pairs")
            ),
        },
        hard_fail=not bool(primary_route_registry),
    )

    sr5_veteran_plane = dict(veteran_plane)
    sr5_veteran_plane["summary"] = (
        "SR5 veteran orientation and familiarity proof is current for the promoted desktop route."
        if veteran_status == "ready"
        else "SR5 veteran orientation and familiarity proof is still incomplete."
    )
    sr5_veteran_plane["evidence"] = {
        **dict(veteran_plane.get("evidence") or {}),
        "alias_of": "veteran_ready",
    }

    veteran_deep_family_ids = (
        "dense_builder_and_career_workflows",
        "identity_contacts_lifestyles_history",
        "dice_initiative_and_table_utilities",
        "legacy_and_adjacent_import_oracles",
        "sheet_export_print_viewer_and_exchange",
        "custom_data_xml_and_translator_bridge",
    )
    veteran_deep_unready = [
        family_id
        for family_id in veteran_deep_family_ids
        if not _flagship_parity_family_meets(flagship_parity_status_by_family, family_id, "veteran_approved")
    ]
    veteran_deep_ui_element_gaps = [
        row_id
        for row_id in UI_ELEMENT_PARITY_AUDIT_VETERAN_DEEP_IDS
        if row_id in ui_element_parity_audit_missing_required_ids or row_id in ui_element_parity_audit_unresolved_ids
    ]
    veteran_deep_reasons: List[str] = []
    if str(coverage.get("desktop_client") or "").strip().lower() != "ready":
        veteran_deep_reasons.append("Desktop flagship coverage is not ready.")
    if desktop_workflow_unresolved_receipt_count > 0 and not desktop_workflow_unresolved_receipts_sr4_sr6_only:
        veteran_deep_reasons.append("Desktop workflow execution gate still has unresolved flagship workflow receipts.")
    if veteran_deep_unready:
        veteran_deep_reasons.append(
            "Veteran deep-workflow families are still below veteran-approved: " + _summarize_ids(veteran_deep_unready) + "."
        )
    if veteran_deep_ui_element_gaps:
        veteran_deep_reasons.append(
            "Chummer5A UI element parity audit still has unresolved veteran deep-workflow rows: "
            + _summarize_ids(veteran_deep_ui_element_gaps)
            + "."
        )
    veteran_deep_status, veteran_deep_plane = _coverage_entry(
        positives=int(str(coverage.get("desktop_client") or "").strip().lower() == "ready")
        + int(desktop_workflow_unresolved_receipt_count == 0 or desktop_workflow_unresolved_receipts_sr4_sr6_only)
        + int(len(veteran_deep_unready) == 0),
        # Keep the desktop proof bar aligned with the dialog-level parity audit.
        reasons=veteran_deep_reasons,
        summary_ready="Dense veteran workflows are directly proven at a veteran-approved bar.",
        summary_missing="Dense veteran workflow proof is still incomplete.",
        evidence={
            "desktop_client_ready": str(coverage.get("desktop_client") or "").strip().lower() == "ready",
            "workflow_unresolved_receipt_count": desktop_workflow_unresolved_receipt_count,
            "workflow_unresolved_receipts_sr4_sr6_only": desktop_workflow_unresolved_receipts_sr4_sr6_only,
            "families_below_veteran_approved": veteran_deep_unready,
            "ui_element_parity_audit_required": ui_element_parity_audit_required,
            "ui_element_parity_audit_release_blocking_ready": ui_element_parity_audit_release_blocking_ready,
            "ui_element_parity_audit_gap_ids": veteran_deep_ui_element_gaps,
        },
        hard_fail=False,
    )

    public_shelf_reasons: List[str] = []
    if str(coverage.get("hub_and_registry") or "").strip().lower() != "ready":
        public_shelf_reasons.append("Hub and registry coverage is not ready.")
    if primary_route_status != "ready":
        public_shelf_reasons.append("Primary-route readiness plane is not ready.")
    if _as_string_list(desktop_evidence.get("release_channel_missing_required_platform_head_pairs")):
        public_shelf_reasons.append("Release channel still has missing required platform/head pairs.")
    if not bool(desktop_evidence.get("release_channel_freshness_ok")):
        public_shelf_reasons.append("Release channel truth is stale.")
    windows_exit_gate_raw_ready = str(desktop_evidence.get("ui_windows_exit_gate_status") or "").strip().lower() in {
        "pass",
        "passed",
        "ready",
    }
    if bool(desktop_evidence.get("release_channel_has_windows_public_installer")) and not windows_exit_gate_raw_ready:
        public_shelf_reasons.append("Windows is on the public shelf while Windows executable proof is not effectively ready.")
    public_shelf_status, public_shelf_plane = _coverage_entry(
        positives=int(str(coverage.get("hub_and_registry") or "").strip().lower() == "ready")
        + int(primary_route_status == "ready")
        + int(not _as_string_list(desktop_evidence.get("release_channel_missing_required_platform_head_pairs")))
        + int(bool(desktop_evidence.get("release_channel_freshness_ok")))
        + int(
            not (
                bool(desktop_evidence.get("release_channel_has_windows_public_installer"))
                and not windows_exit_gate_raw_ready
            )
        ),
        reasons=public_shelf_reasons,
        summary_ready="Public shelf, route truth, and registry posture are aligned.",
        summary_missing="Public shelf and route truth are still inconsistent or stale.",
        evidence={
            "hub_and_registry_ready": str(coverage.get("hub_and_registry") or "").strip().lower() == "ready",
            "primary_route_ready": primary_route_status == "ready",
            "release_channel_freshness_ok": bool(desktop_evidence.get("release_channel_freshness_ok")),
            "release_channel_has_windows_public_installer": bool(
                desktop_evidence.get("release_channel_has_windows_public_installer")
            ),
            "ui_windows_exit_gate_raw_ready": windows_exit_gate_raw_ready,
            "ui_windows_exit_gate_effective_ready": bool(
                desktop_evidence.get("ui_windows_exit_gate_effective_ready")
            ),
            "release_channel_missing_required_platform_head_pairs": _as_string_list(
                desktop_evidence.get("release_channel_missing_required_platform_head_pairs")
            ),
        },
        hard_fail=False,
    )

    rules_detail = dict(details.get("rules_engine_and_import") or {})
    rules_evidence = dict(rules_detail.get("evidence") or {})
    rules_cert_ready = str(rules_evidence.get("rules_certification_status") or "").strip().lower() in {"pass", "passed", "ready"}
    rules_build_journey_state = str(rules_evidence.get("build_explain_publish") or "").strip().lower()
    rules_build_journey_effective_state = str(rules_evidence.get("build_explain_publish_effective") or "").strip().lower()
    rules_build_journey_total_blocker_count = int(rules_evidence.get("build_explain_publish_local_blocking_reason_count") or 0) + int(
        rules_evidence.get("build_explain_publish_external_blocking_reason_count") or 0
    )
    rules_build_journey_rules_scope_blocker_count = int(
        rules_evidence.get("build_explain_publish_rules_scope_blocking_reason_count") or 0
    )
    rules_build_journey_ready = (
        rules_build_journey_effective_state == "ready"
        or rules_build_journey_state == "ready"
        or (
            rules_build_journey_state == "blocked"
            and rules_build_journey_total_blocker_count > 0
            and rules_build_journey_rules_scope_blocker_count == 0
        )
    )

    data_durability_family_ids = (
        "legacy_and_adjacent_import_oracles",
        "sheet_export_print_viewer_and_exchange",
        "identity_contacts_lifestyles_history",
    )
    data_durability_unready = [
        family_id
        for family_id in data_durability_family_ids
        if not _flagship_parity_family_meets(flagship_parity_status_by_family, family_id, "task_proven")
    ]
    data_durability_ui_element_gaps = [
        row_id
        for row_id in UI_ELEMENT_PARITY_AUDIT_DATA_DURABILITY_IDS
        if row_id in ui_element_parity_audit_missing_required_ids or row_id in ui_element_parity_audit_unresolved_ids
    ]
    data_durability_reasons: List[str] = []
    if str(coverage.get("rules_engine_and_import") or "").strip().lower() != "ready":
        data_durability_reasons.append("Rules/import coverage is not ready.")
    if str(desktop_evidence.get("install_claim_restore_continue_effective") or "").strip().lower() != "ready":
        data_durability_reasons.append("Install/claim/restore continuity is not ready.")
    if data_durability_unready:
        data_durability_reasons.append(
            "Durability-critical parity families are still below task-proven: " + _summarize_ids(data_durability_unready) + "."
        )
    if data_durability_ui_element_gaps:
        data_durability_reasons.append(
            "Chummer5A UI element parity audit still has unresolved durability-critical rows: "
            + _summarize_ids(data_durability_ui_element_gaps)
            + "."
        )
    data_durability_status, data_durability_plane = _coverage_entry(
        positives=int(str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready")
        + int(str(desktop_evidence.get("install_claim_restore_continue_effective") or "").strip().lower() == "ready")
        + int(len(data_durability_unready) == 0),
        reasons=data_durability_reasons,
        summary_ready="Data durability and reversible migration proof are current.",
        summary_missing="Data durability or reversible migration proof is still incomplete.",
        evidence={
            "rules_engine_and_import_ready": str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready",
            "install_claim_restore_continue_effective": str(
                desktop_evidence.get("install_claim_restore_continue_effective") or ""
            ).strip(),
            "families_below_task_proven": data_durability_unready,
            "ui_element_parity_audit_gap_ids": data_durability_ui_element_gaps,
        },
        hard_fail=False,
    )

    recovery_trust_reasons: List[str] = []
    if str(coverage.get("desktop_client") or "").strip().lower() != "ready":
        recovery_trust_reasons.append("Desktop flagship coverage is not ready.")
    if str(desktop_evidence.get("install_claim_restore_continue_effective") or "").strip().lower() != "ready":
        recovery_trust_reasons.append("Install/claim/restore continuity is not ready.")
    if str(desktop_evidence.get("ui_executable_exit_gate_status") or "").strip().lower() not in {"pass", "passed", "ready"}:
        recovery_trust_reasons.append("Desktop executable exit gate is not ready.")
    if not windows_exit_gate_raw_ready:
        recovery_trust_reasons.append("Windows executable proof is not effectively ready.")
    if feedback_loop_status != "ready":
        recovery_trust_reasons.append("Feedback-loop readiness plane is not ready.")
    recovery_trust_status, recovery_trust_plane = _coverage_entry(
        positives=int(str(coverage.get("desktop_client") or "").strip().lower() == "ready")
        + int(str(desktop_evidence.get("install_claim_restore_continue_effective") or "").strip().lower() == "ready")
        + int(str(desktop_evidence.get("ui_executable_exit_gate_status") or "").strip().lower() in {"pass", "passed", "ready"})
        + int(windows_exit_gate_raw_ready)
        + int(feedback_loop_status == "ready"),
        reasons=recovery_trust_reasons,
        summary_ready="Install, update, restore, and recovery trust proof is current.",
        summary_missing="Install, update, restore, or recovery trust proof is still incomplete.",
        evidence={
            "desktop_client_ready": str(coverage.get("desktop_client") or "").strip().lower() == "ready",
            "install_claim_restore_continue_effective": str(
                desktop_evidence.get("install_claim_restore_continue_effective") or ""
            ).strip(),
            "ui_executable_exit_gate_status": str(desktop_evidence.get("ui_executable_exit_gate_status") or "").strip(),
            "ui_windows_exit_gate_raw_ready": windows_exit_gate_raw_ready,
            "ui_windows_exit_gate_effective_ready": bool(
                desktop_evidence.get("ui_windows_exit_gate_effective_ready")
            ),
            "feedback_loop_ready": feedback_loop_status == "ready",
        },
        hard_fail=False,
    )

    rules_explainability_reasons: List[str] = []
    if str(coverage.get("rules_engine_and_import") or "").strip().lower() != "ready":
        rules_explainability_reasons.append("Rules/import coverage is not ready.")
    if not rules_build_journey_ready:
        rules_explainability_reasons.append("Build/explain/publish journey is not ready.")
    if not rules_cert_ready:
        rules_explainability_reasons.append("Rules/import certification artifact is not ready.")
    rules_explainability_status, rules_explainability_plane = _coverage_entry(
        positives=int(str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready")
        + int(rules_build_journey_ready)
        + int(rules_cert_ready),
        reasons=rules_explainability_reasons,
        summary_ready="Rules explainability and import-certification proof is current.",
        summary_missing="Rules explainability or import-certification proof is still incomplete.",
        evidence={
            "rules_engine_and_import_ready": str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready",
            "build_explain_publish": str(rules_evidence.get("build_explain_publish") or "").strip(),
            "build_explain_publish_effective": str(rules_evidence.get("build_explain_publish_effective") or "").strip(),
            "build_explain_publish_rules_scope_blocking_reason_count": rules_build_journey_rules_scope_blocker_count,
            "rules_certification_status": str(rules_evidence.get("rules_certification_status") or "").strip(),
        },
        hard_fail=False,
    )

    custom_data_survival_family_ids = (
        "custom_data_xml_and_translator_bridge",
        "settings_and_rules_environment_authoring",
    )
    custom_data_survival_unready = [
        family_id
        for family_id in custom_data_survival_family_ids
        if not _flagship_parity_family_meets(flagship_parity_status_by_family, family_id, "task_proven")
    ]
    custom_data_survival_ui_element_gaps = [
        row_id
        for row_id in UI_ELEMENT_PARITY_AUDIT_CUSTOM_DATA_SURVIVAL_IDS
        if row_id in ui_element_parity_audit_missing_required_ids or row_id in ui_element_parity_audit_unresolved_ids
    ]
    custom_data_survival_reasons: List[str] = []
    if str(coverage.get("rules_engine_and_import") or "").strip().lower() != "ready":
        custom_data_survival_reasons.append("Rules/import coverage is not ready.")
    if custom_data_survival_unready:
        custom_data_survival_reasons.append(
            "Custom-data survival families are still below task-proven: " + _summarize_ids(custom_data_survival_unready) + "."
        )
    if custom_data_survival_ui_element_gaps:
        custom_data_survival_reasons.append(
            "Chummer5A UI element parity audit still has unresolved custom-data or translator rows: "
            + _summarize_ids(custom_data_survival_ui_element_gaps)
            + "."
        )
    custom_data_survival_status, custom_data_survival_plane = _coverage_entry(
        positives=int(str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready")
        + int(len(custom_data_survival_unready) == 0),
        reasons=custom_data_survival_reasons,
        summary_ready="Custom-data, translator, and rule-environment survival proof is current.",
        summary_missing="Custom-data, translator, or rule-environment survival proof is still incomplete.",
        evidence={
            "rules_engine_and_import_ready": str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready",
            "families_below_task_proven": custom_data_survival_unready,
            "ui_element_parity_audit_gap_ids": custom_data_survival_ui_element_gaps,
        },
        hard_fail=False,
    )

    large_sheet_performance_reasons: List[str] = []
    if str(coverage.get("rules_engine_and_import") or "").strip().lower() != "ready":
        large_sheet_performance_reasons.append("Rules/import coverage is not ready.")
    if not rules_cert_ready:
        large_sheet_performance_reasons.append("Rules/import certification artifact is not ready.")
    if int(rules_evidence.get("build_explain_publish_rules_scope_blocking_reason_count") or 0) > 0:
        large_sheet_performance_reasons.append("Rules-scope blockers are still open in build/explain/publish.")
    large_sheet_performance_status, large_sheet_performance_plane = _coverage_entry(
        positives=int(str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready")
        + int(rules_cert_ready)
        + int(int(rules_evidence.get("build_explain_publish_rules_scope_blocking_reason_count") or 0) == 0),
        reasons=large_sheet_performance_reasons,
        summary_ready="Large-sheet and dense-roster performance proof is current.",
        summary_missing="Large-sheet or dense-roster performance proof is still incomplete.",
        evidence={
            "rules_engine_and_import_ready": str(coverage.get("rules_engine_and_import") or "").strip().lower() == "ready",
            "rules_certification_status": str(rules_evidence.get("rules_certification_status") or "").strip(),
            "build_explain_publish_rules_scope_blocking_reason_count": int(
                rules_evidence.get("build_explain_publish_rules_scope_blocking_reason_count") or 0
            ),
        },
        hard_fail=False,
    )

    sr4_parity_reasons: List[str] = []
    if not desktop_sr4_parity_ready:
        sr4_parity_reasons.append("SR4 desktop workflow parity proof is not ready.")
    if not desktop_sr4_sr6_frontier_ready:
        sr4_parity_reasons.append("SR4/SR6 desktop parity frontier receipt is not ready.")
    sr4_parity_status, sr4_parity_plane = _coverage_entry(
        positives=int(desktop_sr4_parity_ready) + int(desktop_sr4_sr6_frontier_ready),
        reasons=sr4_parity_reasons,
        summary_ready="SR4 parity proof is explicit and current.",
        summary_missing="SR4 parity proof is still incomplete.",
        evidence={
            "sr4_workflow_parity_status": str(desktop_evidence.get("sr4_workflow_parity_status") or "").strip(),
            "sr4_workflow_parity_external_only_missing_api_surface_contract": bool(
                desktop_evidence.get("sr4_workflow_parity_external_only_missing_api_surface_contract")
            ),
            "sr4_sr6_frontier_receipt_status": str(desktop_evidence.get("sr4_sr6_frontier_receipt_status") or "").strip(),
        },
        hard_fail=False,
    )

    sr6_parity_reasons: List[str] = []
    if not desktop_sr6_parity_ready:
        sr6_parity_reasons.append("SR6 desktop workflow parity proof is not ready.")
    if not desktop_sr4_sr6_frontier_ready:
        sr6_parity_reasons.append("SR4/SR6 desktop parity frontier receipt is not ready.")
    sr6_ui_element_gaps = [
        row_id
        for row_id in UI_ELEMENT_PARITY_AUDIT_SR6_IDS
        if row_id in ui_element_parity_audit_missing_required_ids or row_id in ui_element_parity_audit_unresolved_ids
    ]
    if sr6_ui_element_gaps:
        sr6_parity_reasons.append(
            "Chummer5A UI element parity audit still has unresolved SR6 parity rows: "
            + _summarize_ids(sr6_ui_element_gaps)
            + "."
        )
    sr6_parity_status, sr6_parity_plane = _coverage_entry(
        positives=int(desktop_sr6_parity_ready) + int(desktop_sr4_sr6_frontier_ready),
        reasons=sr6_parity_reasons,
        summary_ready="SR6 parity proof is explicit and current.",
        summary_missing="SR6 parity proof is still incomplete.",
        evidence={
            "sr6_workflow_parity_status": str(desktop_evidence.get("sr6_workflow_parity_status") or "").strip(),
            "sr6_workflow_parity_external_only_missing_api_surface_contract": bool(
                desktop_evidence.get("sr6_workflow_parity_external_only_missing_api_surface_contract")
            ),
            "sr4_sr6_frontier_receipt_status": str(desktop_evidence.get("sr4_sr6_frontier_receipt_status") or "").strip(),
            "ui_element_parity_audit_gap_ids": sr6_ui_element_gaps,
        },
        hard_fail=False,
    )

    flagship_plane_reasons: List[str] = []
    if coverage_gap_keys:
        flagship_plane_reasons.append("Whole-product coverage still has open flagship gaps: " + ", ".join(coverage_gap_keys) + ".")
    if not flagship_parity_registry:
        flagship_plane_reasons.append("Flagship parity registry is missing.")
    if families_below_gold_ready:
        flagship_plane_reasons.append(
            "Flagship parity families are still below gold-ready: " + _summarize_ids(families_below_gold_ready) + "."
        )
    if not parity_lab_ready:
        flagship_plane_reasons.append("Parity-lab evidence is not fully bound into veteran-ready release truth.")
    if structural_status != "ready":
        flagship_plane_reasons.append("Structural readiness plane is not ready.")
    if veteran_status != "ready":
        flagship_plane_reasons.append("Veteran readiness plane is not ready.")
    if primary_route_status != "ready":
        flagship_plane_reasons.append("Primary-route readiness plane is not ready.")
    if dense_status != "ready":
        flagship_plane_reasons.append("Dense-workbench readiness plane is not ready.")
    if feedback_loop_status != "ready":
        flagship_plane_reasons.append("Feedback-loop readiness plane is not ready.")
    if veteran_deep_status != "ready":
        flagship_plane_reasons.append("Veteran deep-workflow readiness plane is not ready.")
    if public_shelf_status != "ready":
        flagship_plane_reasons.append("Public-shelf readiness plane is not ready.")
    if data_durability_status != "ready":
        flagship_plane_reasons.append("Data-durability readiness plane is not ready.")
    if recovery_trust_status != "ready":
        flagship_plane_reasons.append("Recovery-trust readiness plane is not ready.")
    if rules_explainability_status != "ready":
        flagship_plane_reasons.append("Rules-explainability readiness plane is not ready.")
    if custom_data_survival_status != "ready":
        flagship_plane_reasons.append("Custom-data-survival readiness plane is not ready.")
    if large_sheet_performance_status != "ready":
        flagship_plane_reasons.append("Large-sheet-performance readiness plane is not ready.")
    if sr4_parity_status != "ready":
        flagship_plane_reasons.append("SR4 parity readiness plane is not ready.")
    if sr6_parity_status != "ready":
        flagship_plane_reasons.append("SR6 parity readiness plane is not ready.")
    if not bool(m136_aggregate_readiness_gate_audit.get("ready")):
        flagship_plane_reasons.append("M136 aggregate-readiness parity gate is not ready.")
    flagship_plane_status, flagship_plane = _coverage_entry(
        positives=(
            int(len(coverage_gap_keys) == 0)
            + int(bool(flagship_parity_registry))
            + int(len(families_below_gold_ready) == 0)
            + int(parity_lab_ready)
            + int(structural_status == "ready")
            + int(veteran_status == "ready")
            + int(primary_route_status == "ready")
            + int(dense_status == "ready")
            + int(feedback_loop_status == "ready")
            + int(veteran_deep_status == "ready")
            + int(public_shelf_status == "ready")
            + int(data_durability_status == "ready")
            + int(recovery_trust_status == "ready")
            + int(rules_explainability_status == "ready")
            + int(custom_data_survival_status == "ready")
            + int(large_sheet_performance_status == "ready")
            + int(sr4_parity_status == "ready")
            + int(sr6_parity_status == "ready")
            + int(bool(m136_aggregate_readiness_gate_audit.get("ready")))
        ),
        reasons=flagship_plane_reasons,
        summary_ready="Flagship replacement truth is fully green.",
        summary_missing="Flagship replacement truth is still stricter than the current structural closure.",
        evidence={
            "registry_path": str(effective_flagship_parity_registry_path),
            "registry_present": bool(flagship_parity_registry),
            "status_counts": flagship_parity_status_counts,
            "families_below_task_proven": families_below_task_proven,
            "families_below_veteran_approved": families_below_veteran_approved,
            "families_below_gold_ready": families_below_gold_ready,
            "parity_lab_ready": parity_lab_ready,
            "parity_lab_capture_pack_path": str(effective_parity_lab_capture_pack_path),
            "parity_lab_veteran_compare_pack_path": str(effective_veteran_workflow_pack_path),
            "parity_lab_missing_flagship_family_ids": _as_string_list(parity_lab_evidence.get("missing_flagship_family_ids")),
            "parity_lab_families_below_target": parity_lab_families_below_target if isinstance(parity_lab_families_below_target, list) else [],
            "parity_lab_capture_missing_non_negotiable_ids": _as_string_list(
                parity_lab_evidence.get("missing_capture_non_negotiable_ids")
            ),
            "parity_lab_workflow_missing_non_negotiable_ids": _as_string_list(
                parity_lab_evidence.get("missing_workflow_non_negotiable_ids")
            ),
            "parity_lab_missing_whole_product_coverage_keys": _as_string_list(
                parity_lab_evidence.get("missing_whole_product_coverage_keys")
            ),
            "coverage_gap_keys": coverage_gap_keys,
            "structural_ready": structural_status == "ready",
            "veteran_ready": veteran_status == "ready",
            "primary_route_ready": primary_route_status == "ready",
            "dense_workbench_ready": dense_status == "ready",
            "feedback_loop_ready": feedback_loop_status == "ready",
            "veteran_deep_workflow_ready": veteran_deep_status == "ready",
            "public_shelf_ready": public_shelf_status == "ready",
            "data_durability_ready": data_durability_status == "ready",
            "recovery_trust_ready": recovery_trust_status == "ready",
            "rules_explainability_ready": rules_explainability_status == "ready",
            "custom_data_survival_ready": custom_data_survival_status == "ready",
            "large_sheet_performance_ready": large_sheet_performance_status == "ready",
            "sr4_parity_ready": sr4_parity_status == "ready",
            "sr6_parity_ready": sr6_parity_status == "ready",
            "m136_aggregate_readiness_gate_path": str(m136_aggregate_readiness_gate_path),
            "m136_aggregate_readiness_gate_ready": bool(m136_aggregate_readiness_gate_audit.get("ready")),
            "m136_aggregate_readiness_gate_status": str(m136_aggregate_readiness_gate_audit.get("status") or ""),
            "m136_aggregate_readiness_monitor_status": str(
                m136_aggregate_readiness_gate_audit.get("aggregate_readiness_status") or ""
            ),
            "m136_aggregate_readiness_gate_generated_at": str(
                m136_aggregate_readiness_gate_audit.get("generated_at") or ""
            ),
            "m136_aggregate_readiness_gate_reasons": list(m136_aggregate_readiness_gate_audit.get("reasons") or []),
            "readiness_plane_contract_path": str(effective_flagship_readiness_planes_path),
            "readiness_plane_contract_present": bool(flagship_readiness_planes),
            "readiness_plane_contract_ids": declared_readiness_plane_ids,
        },
        hard_fail=not bool(flagship_parity_registry) or str(coverage.get("desktop_client") or "").strip().lower() == "missing",
    )

    readiness_planes = {
        "structural_ready": structural_plane,
        "flagship_ready": flagship_plane,
        "veteran_ready": veteran_plane,
        "sr5_veteran_ready": sr5_veteran_plane,
        "veteran_deep_workflow_ready": veteran_deep_plane,
        "primary_route_ready": primary_route_plane,
        "dense_workbench_ready": dense_plane,
        "feedback_loop_ready": feedback_loop_plane,
        "public_shelf_ready": public_shelf_plane,
        "data_durability_ready": data_durability_plane,
        "recovery_trust_ready": recovery_trust_plane,
        "rules_explainability_ready": rules_explainability_plane,
        "custom_data_survival_ready": custom_data_survival_plane,
        "large_sheet_performance_ready": large_sheet_performance_plane,
        "sr4_parity_ready": sr4_parity_plane,
        "sr6_parity_ready": sr6_parity_plane,
    }
    readiness_plane_summary = {
        "ready_count": sum(1 for plane in readiness_planes.values() if str(plane.get("status") or "") == "ready"),
        "warning_count": sum(1 for plane in readiness_planes.values() if str(plane.get("status") or "") == "warning"),
        "missing_count": sum(1 for plane in readiness_planes.values() if str(plane.get("status") or "") == "missing"),
    }
    readiness_plane_gap_keys = [
        key
        for key, plane in readiness_planes.items()
        if str(plane.get("status") or "").strip().lower() != "ready"
    ]
    if readiness_plane_gap_keys:
        status = "fail"
        scoped_status = "fail"
        completion_audit_status = "fail"
        if completion_external_only:
            completion_audit_reason = _format_external_only_completion_reason(external_host_proof_reason)
        else:
            completion_audit_reason = (
                "Flagship product readiness planes are not green: " + ", ".join(readiness_plane_gap_keys) + "."
            )
        flagship_readiness_audit_status = "fail"
        if completion_external_only:
            flagship_readiness_audit_reason = _format_external_only_completion_reason(external_host_proof_reason)
            if coverage_gap_keys:
                flagship_readiness_audit_reason += (
                    "; missing coverage: " + ", ".join(coverage_gap_keys)
                )
            if readiness_plane_gap_keys:
                flagship_readiness_audit_reason += (
                    "; readiness plane gaps: " + ", ".join(readiness_plane_gap_keys)
                )
        elif coverage_gap_keys:
            flagship_readiness_audit_reason += (
                "; readiness plane gaps: " + ", ".join(readiness_plane_gap_keys)
            )
        else:
            flagship_readiness_audit_reason = (
                "flagship product readiness proof is not green: "
                + status
                + "; readiness plane gaps: "
                + ", ".join(readiness_plane_gap_keys)
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
            "external_only": completion_external_only,
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
            "commands_dir": str(effective_external_proof_commands_dir),
            "command_bundle_sha256": str(external_command_bundle.get("sha256") or ""),
            "command_bundle_file_count": int(external_command_bundle.get("file_count") or 0),
            "runbook_command_bundle_sha256": runbook_command_bundle_sha256,
            "runbook_command_bundle_file_count": runbook_command_bundle_file_count,
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
            "feedback_loop_release_gate_required": True,
            "accept_lowered_standards": False,
        },
        "autofix_routing": {
            "status": "ready" if local_blocker_autofix_routing_ready else "warning",
            "summary": (
                "Local journey blockers are routed to owner repos."
                if local_blocker_autofix_routing_ready
                else "Some local journey blockers are missing owner-repo routing."
            ),
            "total_local_blocker_count": local_blocker_total_count,
            "routed_local_blocker_count": local_blocker_routed_count,
            "unrouted_local_blocker_count": local_blocker_unrouted_count,
            "owner_repo_counts": local_blocker_owner_repo_counts,
            "journey_local_blocker_counts": journey_local_blocker_counts,
            "routes": local_blocker_route_rows,
            "unrouted_reasons": local_blocker_unrouted_reasons,
        },
        "readiness_planes": readiness_planes,
        "readiness_plane_summary": readiness_plane_summary,
        "readiness_plane_gap_keys": readiness_plane_gap_keys,
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
        "flagship_parity_registry": {
            "path": str(effective_flagship_parity_registry_path),
            "status_counts": flagship_parity_status_counts,
            "family_count": len(flagship_parity_families),
            "families_below_task_proven": families_below_task_proven,
            "families_below_veteran_approved": families_below_veteran_approved,
            "families_below_gold_ready": families_below_gold_ready,
            "parity_lab_ready": parity_lab_ready,
            "parity_lab_capture_pack_path": str(effective_parity_lab_capture_pack_path),
            "parity_lab_veteran_compare_pack_path": str(effective_veteran_workflow_pack_path),
            "parity_lab_family_target_count": int(parity_lab_evidence.get("family_target_count") or 0),
            "parity_lab_invalid_target_family_ids": _as_string_list(parity_lab_evidence.get("invalid_target_family_ids")),
            "parity_lab_missing_flagship_family_ids": _as_string_list(parity_lab_evidence.get("missing_flagship_family_ids")),
            "parity_lab_families_below_target": parity_lab_families_below_target if isinstance(parity_lab_families_below_target, list) else [],
            "parity_lab_capture_coverage_key": str(parity_lab_evidence.get("capture_coverage_key") or "").strip(),
            "parity_lab_capture_coverage_key_matches": bool(parity_lab_evidence.get("capture_coverage_key_matches")),
            "parity_lab_capture_missing_non_negotiable_ids": _as_string_list(
                parity_lab_evidence.get("missing_capture_non_negotiable_ids")
            ),
            "parity_lab_workflow_missing_non_negotiable_ids": _as_string_list(
                parity_lab_evidence.get("missing_workflow_non_negotiable_ids")
            ),
            "parity_lab_missing_whole_product_coverage_keys": _as_string_list(
                parity_lab_evidence.get("missing_whole_product_coverage_keys")
            ),
        },
        "evidence_sources": {
            "acceptance": str(effective_acceptance_path),
            "parity_registry": str(effective_parity_registry_path),
            "flagship_parity_registry": str(effective_flagship_parity_registry_path),
            "flagship_readiness_planes": str(effective_flagship_readiness_planes_path),
            "dense_workbench_budget": str(effective_dense_workbench_budget_path),
            "veteran_first_minute_gate": str(effective_veteran_first_minute_gate_path),
            "primary_route_registry": str(effective_primary_route_registry_path),
            "feedback_loop_release_gate": str(effective_feedback_loop_gate_path),
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
            "ui_user_journey_tester_audit": (
                report_path(ui_user_journey_tester_audit_path) if ui_user_journey_tester_audit_path else ""
            ),
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
    feedback_loop_gate_path: Path,
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
    ui_element_parity_audit_path: Path | None = None,
    ui_user_journey_tester_audit_path: Path | None = None,
    m136_aggregate_readiness_gate_path: Path = DEFAULT_M136_AGGREGATE_READINESS_GATE,
    ignore_nonlinux_desktop_host_proof_blockers: bool = False,
) -> Dict[str, Any]:
    payload = build_flagship_product_readiness_payload(
        acceptance_path=acceptance_path,
        parity_registry_path=parity_registry_path,
        feedback_loop_gate_path=feedback_loop_gate_path,
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        m136_aggregate_readiness_gate_path=m136_aggregate_readiness_gate_path,
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
        ui_element_parity_audit_path=ui_element_parity_audit_path,
        ui_localization_release_gate_path=ui_localization_release_gate_path,
        sr4_workflow_parity_proof_path=sr4_workflow_parity_proof_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_proof_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_proof_path,
        mobile_local_release_proof_path=mobile_local_release_proof_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ui_user_journey_tester_audit_path=ui_user_journey_tester_audit_path,
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
        support_packets_path = repo_root / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
        refreshed_weekly = _refresh_weekly_governor_packet_if_possible(
            repo_root,
            support_packets_path,
        )
        if not refreshed_weekly:
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
        m136_aggregate_readiness_gate_path=Path(args.m136_aggregate_readiness_gate).resolve(),
        feedback_loop_gate_path=Path(args.feedback_loop_gate).resolve(),
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
        ui_element_parity_audit_path=(
            Path(args.ui_element_parity_audit).resolve()
            if str(args.ui_element_parity_audit or "").strip()
            else None
        ),
        ui_user_journey_tester_audit_path=(
            Path(args.ui_user_journey_tester_audit).resolve()
            if str(args.ui_user_journey_tester_audit or "").strip()
            else None
        ),
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
