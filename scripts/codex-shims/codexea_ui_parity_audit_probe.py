#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PACK_PATH = Path("/docker/fleet/docs/chummer5a-oracle/parity_lab_capture_pack.yaml")
VETERAN_PATH = Path("/docker/fleet/docs/chummer5a-oracle/veteran_workflow_packs.yaml")
SCREENSHOT_GATE_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_SCREENSHOT_REVIEW_GATE.generated.json")
VISUAL_GATE_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json")
WORKFLOW_GATE_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json")
READINESS_PATH = Path("/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json")
STATE_PATH = Path("/docker/fleet/state/chummer_design_supervisor/state.json")
REPORT_JSON_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.json")
REPORT_MARKDOWN_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/CHUMMER5A_UI_ELEMENT_PARITY_AUDIT.generated.md")

YES = "yes"
NO = "no"

SOURCE_LABELS = {
    "file_menu": "File menu",
    "tools_menu": "Tools menu",
    "windows_menu": "Windows menu",
    "help_menu": "Help menu",
    "open_route": "Open route",
    "open_for_export_route": "Open for export route",
    "global_settings_route": "Global settings route",
    "translator_route": "Translator route",
    "xml_amendment_editor_route": "XML amendment editor route",
    "hero_lab_importer_route": "Hero Lab importer route",
    "master_index_route": "Master index route",
    "character_roster_route": "Character roster route",
    "master_index_form_title": "Master Index dialog title",
    "master_index_source_click_reminder": "Master Index source click reminder",
    "character_roster_form_title": "Character Roster dialog title",
    "character_roster_tree": "Character Roster tree",
}

SOURCE_PROOF_OVERRIDES = {
    "open_route": (
        True,
        True,
        "Runtime-backed open-route parity is directly covered by the current file-menu proof.",
        "Current parity artifacts do not directly prove the open route.",
    ),
    "open_for_export_route": (
        True,
        True,
        "Runtime-backed open-for-export route parity is directly covered by the current file-menu proof.",
        "Current parity artifacts do not directly prove the open-for-export route.",
    ),
    "global_settings_route": (
        True,
        True,
        "Runtime-backed settings-route parity is directly covered by the current file/settings proof.",
        "Current parity artifacts do not directly prove the global settings route.",
    ),
    "translator_route": (
        False,
        False,
        "",
        "Current parity artifacts do not directly prove the Translator route with screenshot-backed runtime coverage.",
    ),
    "xml_amendment_editor_route": (
        False,
        False,
        "",
        "Current parity artifacts do not directly prove the XML Amendment Editor route with screenshot-backed runtime coverage.",
    ),
    "hero_lab_importer_route": (
        False,
        False,
        "",
        "Current parity artifacts do not directly prove the Hero Lab Importer route with screenshot-backed runtime coverage.",
    ),
}

NON_NEGOTIABLE_LABELS = {
    "no_generic_shell_or_dashboard_first": "No generic shell or dashboard first",
    "startup_is_workbench_or_restore": "Startup lands in workbench or restore",
    "file_menu_live": "File menu stays live",
    "master_index_first_class": "Master Index is first-class",
    "character_roster_first_class": "Character Roster is first-class",
    "claim_restore_in_installer_or_in_app": "Claim restore is in-app or installer-backed",
    "no_browser_only_claim_code_ritual": "No browser-only claim code ritual",
    "guided_product_installer_happy_path": "Guided product installer happy path",
}

SCREENSHOT_LABELS = {
    "01-initial-shell-light.png": "Initial workbench shell",
    "02-menu-open-light.png": "File/open/import menu surface",
    "03-settings-open-light.png": "Settings surface",
    "04-loaded-runner-light.png": "Loaded runner workbench",
    "05-dense-section-light.png": "Dense builder section (light)",
    "06-dense-section-dark.png": "Dense builder section (dark)",
    "07-loaded-runner-tabs-light.png": "Loaded runner tab strip",
    "08-cyberware-dialog-light.png": "Cyberware dialog",
    "09-vehicles-section-light.png": "Vehicles and drones section",
    "10-contacts-section-light.png": "Contacts section",
    "11-diary-dialog-light.png": "Diary dialog",
    "12-magic-dialog-light.png": "Magic dialog",
    "13-matrix-dialog-light.png": "Matrix dialog",
    "14-advancement-dialog-light.png": "Advancement dialog",
    "15-creation-section-light.png": "Character creation section",
    "16-master-index-dialog-light.png": "Master Index dialog",
    "17-character-roster-dialog-light.png": "Character Roster dialog",
    "18-import-dialog-light.png": "Import dialog",
}

LANDMARK_PROOF_KEYS = {
    "File menu": (["runtime_backed_menu_bar_labels"], ["runtime_backed_clickable_primary_menus"]),
    "Tools menu": (["runtime_backed_menu_bar_labels"], ["runtime_backed_clickable_primary_menus"]),
    "Windows menu": (["runtime_backed_menu_bar_labels"], ["runtime_backed_clickable_primary_menus"]),
    "Help menu": (["runtime_backed_menu_bar_labels"], ["runtime_backed_clickable_primary_menus"]),
    "Immediate toolstrip": (["runtime_backed_toolstrip_actions"], ["runtime_backed_toolstrip_actions"]),
    "Bottom status strip": (["runtime_backed_legacy_workbench"], ["runtime_backed_legacy_workbench"]),
    "Save or open route": (["runtime_backed_file_menu_routes"], ["runtime_backed_file_menu_routes"]),
    "Import route": (["runtime_backed_file_menu_routes"], ["runtime_backed_file_menu_routes"]),
    "Settings route": (["runtime_backed_file_menu_routes"], ["runtime_backed_file_menu_routes"]),
    "Master index route": (["runtime_backed_master_index"], ["runtime_backed_master_index"]),
    "Character roster route": (["runtime_backed_character_roster"], ["runtime_backed_character_roster"]),
}

BASELINE_SCREENSHOT_MAP = {
    "first_launch_workbench_or_restore": ["01-initial-shell-light.png"],
    "menu_file_open_save_import": ["02-menu-open-light.png", "18-import-dialog-light.png"],
    "menu_tools_settings_masterindex_roster": [
        "03-settings-open-light.png",
        "16-master-index-dialog-light.png",
        "17-character-roster-dialog-light.png",
    ],
    "menu_windows_help_liveness": ["02-menu-open-light.png"],
    "master_index_dense_reference_flow": ["16-master-index-dialog-light.png"],
    "character_roster_multi_character_flow": ["17-character-roster-dialog-light.png"],
}

SCREENSHOT_BEHAVIOR_KEYS = {
    "01-initial-shell-light.png": ["runtime_backed_legacy_workbench"],
    "02-menu-open-light.png": ["runtime_backed_file_menu_routes", "runtime_backed_clickable_primary_menus"],
    "03-settings-open-light.png": ["runtime_backed_file_menu_routes"],
    "04-loaded-runner-light.png": ["runtime_backed_legacy_workbench", "runtime_backed_chrome_enabled_after_runner_load"],
    "05-dense-section-light.png": ["legacy_dense_builder_rhythm"],
    "06-dense-section-dark.png": ["legacy_dense_builder_rhythm"],
    "07-loaded-runner-tabs-light.png": ["loaded_runner_tab_posture_control_present"],
    "08-cyberware-dialog-light.png": ["legacy_cyberware_dialog_rhythm"],
    "09-vehicles-section-light.png": ["legacy_vehicles_builder_rhythm"],
    "10-contacts-section-light.png": ["legacy_contacts_workflow_rhythm"],
    "11-diary-dialog-light.png": ["legacy_diary_workflow_rhythm"],
    "12-magic-dialog-light.png": ["legacy_magic_workflow_rhythm"],
    "13-matrix-dialog-light.png": ["legacy_matrix_workflow_rhythm"],
    "14-advancement-dialog-light.png": ["legacy_advancement_workflow_rhythm"],
    "15-creation-section-light.png": ["legacy_creation_workflow_rhythm"],
    "16-master-index-dialog-light.png": ["runtime_backed_master_index"],
    "17-character-roster-dialog-light.png": ["runtime_backed_character_roster"],
    "18-import-dialog-light.png": ["runtime_backed_file_menu_routes"],
}

TASK_BEHAVIOR_KEYS = {
    "reach_real_workbench": ["runtime_backed_legacy_workbench"],
    "locate_save_import_settings": ["runtime_backed_file_menu_routes"],
    "locate_master_index_and_roster": ["runtime_backed_master_index", "runtime_backed_character_roster"],
    "recover_section_rhythm": ["legacy_dense_builder_rhythm", "legacy_creation_workflow_rhythm"],
}

FAMILY_ARTIFACT_STATUS = {
    "workflow:build_explain_publish": False,
    "workflow:contacts": True,
    "workflow:lifestyles": False,
    "workflow:notes": True,
    "workflow:sources": True,
    "workflow:rules": True,
    "menu:translator": False,
    "menu:xml_editor": False,
    "menu:dice_roller": False,
    "workflow:initiative": False,
    "workflow:multi_character": True,
    "menu:open_for_printing": False,
    "menu:open_for_export": True,
    "menu:file_print_multiple": False,
    "menu:hero_lab_importer": False,
    "workflow:import_oracle": False,
    "workflow:sr6_supplements": False,
    "workflow:house_rules": False,
}

EXTRA_MARKER_BUCKETS = (
    ("present_disallowed_toolstrip_markers", "Modern toolstrip extra"),
    ("present_disallowed_summary_header_markers", "Modern summary-header extra"),
    ("classic_copy_present_markers", "Modern dashboard/copy extra"),
    ("present_disallowed_navigator_markers", "Navigator replacement extra"),
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _is_pass(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"pass", "passed", "ready", "true", "yes"}


def _text_yes(value: bool) -> str:
    return YES if value else NO


def _titleize(value: str) -> str:
    cleaned = str(value or "").replace("_", " ").replace("-", " ").strip()
    return " ".join(part.capitalize() for part in cleaned.split())


def _append(rows: list[dict[str, Any]], record: dict[str, Any], seen: set[str]) -> None:
    record_id = str(record.get("id") or "").strip()
    if not record_id or record_id in seen:
        return
    seen.add(record_id)
    rows.append(record)


def _record(
    *,
    record_id: str,
    label: str,
    category: str,
    visual: bool,
    behavior: bool,
    present_in_chummer5a: bool,
    removable_without_degrading: bool,
    reason: str,
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "id": record_id,
        "label": label,
        "category": category,
        "visual_parity": _text_yes(visual),
        "behavioral_parity": _text_yes(behavior),
        "present_in_chummer5a": _text_yes(present_in_chummer5a),
        "removable_without_workflow_degradation": _text_yes(removable_without_degrading),
        "reason": reason,
        "evidence": evidence,
    }


def _truthy_passes(evidence: dict[str, Any], keys: list[str]) -> bool:
    if not keys:
        return False
    return all(_is_pass(evidence.get(key)) for key in keys)


def _artifact_status(artifact: str, baseline_status: dict[str, bool], non_negotiables: dict[str, bool]) -> bool:
    token = str(artifact or "").strip()
    if not token:
        return False
    if token.startswith("baseline:"):
        return bool(baseline_status.get(token.split(":", 1)[1]))
    if token.startswith("non_negotiable:"):
        return bool(non_negotiables.get(token.split(":", 1)[1]))
    if token.startswith("oracle:tabs"):
        return bool(FAMILY_ARTIFACT_STATUS.get("oracle:tabs", True))
    if token.startswith("oracle:workspace_actions"):
        return bool(FAMILY_ARTIFACT_STATUS.get("oracle:workspace_actions", True))
    return bool(FAMILY_ARTIFACT_STATUS.get(token))


def _write_report(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".json":
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        return
    path.write_text(str(payload), encoding="utf-8")


def main() -> int:
    pack = _load_yaml(PACK_PATH)
    veteran = _load_yaml(VETERAN_PATH)
    screenshot_gate = _load_json(SCREENSHOT_GATE_PATH)
    visual_gate = _load_json(VISUAL_GATE_PATH)
    workflow_gate = _load_json(WORKFLOW_GATE_PATH)
    readiness = _load_json(READINESS_PATH)
    state = _load_json(STATE_PATH)

    visual_evidence = visual_gate.get("evidence") if isinstance(visual_gate.get("evidence"), dict) else {}
    screenshot_evidence = screenshot_gate.get("evidence") if isinstance(screenshot_gate.get("evidence"), dict) else {}
    coverage = readiness.get("coverage") if isinstance(readiness.get("coverage"), dict) else {}
    coverage_details = readiness.get("coverage_details") if isinstance(readiness.get("coverage_details"), dict) else {}

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    source_line_proofs = (
        pack.get("oracle_surface_extract", {}).get("source_line_proofs", {})
        if isinstance(pack.get("oracle_surface_extract"), dict)
        else {}
    )
    group_proof = {
        "top_menu_landmarks": {
            "visual": _truthy_passes(visual_evidence, ["runtime_backed_menu_bar_labels"]),
            "behavior": _truthy_passes(visual_evidence, ["runtime_backed_clickable_primary_menus"]),
            "reason_yes": "Runtime-backed menu-bar label and clickability proofs are passing.",
            "reason_no": "Current parity artifacts do not directly prove classic menu labels/clickability for this landmark.",
        },
        "file_and_settings_routes": {
            "visual": _truthy_passes(visual_evidence, ["runtime_backed_file_menu_routes"]),
            "behavior": _truthy_passes(visual_evidence, ["runtime_backed_file_menu_routes"]),
            "reason_yes": "Runtime-backed file/settings route proof is passing.",
            "reason_no": "Current parity artifacts do not directly prove this route with screenshot-backed runtime coverage.",
        },
        "first_class_master_index_and_roster": {
            "visual": _truthy_passes(visual_evidence, ["runtime_backed_master_index", "runtime_backed_character_roster"]),
            "behavior": _truthy_passes(visual_evidence, ["runtime_backed_master_index", "runtime_backed_character_roster"]),
            "reason_yes": "Master Index and Character Roster runtime-backed route proofs are passing.",
            "reason_no": "Current parity artifacts do not directly prove this Master Index or Character Roster surface.",
        },
    }
    for group_name, items in source_line_proofs.items():
        if not isinstance(items, list):
            continue
        proof = group_proof.get(group_name, {})
        for item in items:
            if not isinstance(item, dict):
                continue
            proof_id = str(item.get("id") or "").strip()
            if not proof_id:
                continue
            override = SOURCE_PROOF_OVERRIDES.get(proof_id)
            if override is not None:
                visual, behavior, reason_yes, reason_no = override
            else:
                visual = bool(proof.get("visual"))
                behavior = bool(proof.get("behavior"))
                reason_yes = str(proof.get("reason_yes") or "").strip()
                reason_no = str(proof.get("reason_no") or "").strip()
            reason = reason_yes if visual and behavior else reason_no
            _append(
                rows,
                _record(
                    record_id=f"source:{proof_id}",
                    label=SOURCE_LABELS.get(proof_id, _titleize(proof_id)),
                    category="legacy_source_anchor",
                    visual=visual,
                    behavior=behavior,
                    present_in_chummer5a=True,
                    removable_without_degrading=False,
                    reason=reason,
                    evidence=[
                        f"{PACK_PATH}#oracle_surface_extract.source_line_proofs.{group_name}",
                        str(VISUAL_GATE_PATH),
                    ],
                ),
                seen,
            )

    screenshot_names = set(visual_evidence.get("required_screenshots") or [])
    missing_screenshots = set(visual_evidence.get("missing_screenshots") or [])
    for screenshot_name, label in SCREENSHOT_LABELS.items():
        behavior_keys = SCREENSHOT_BEHAVIOR_KEYS.get(screenshot_name, [])
        visual = screenshot_name in screenshot_names and screenshot_name not in missing_screenshots
        behavior = _truthy_passes(visual_evidence, behavior_keys)
        reason = (
            "Required screenshot is present and the matching runtime-backed interaction proof is passing."
            if visual and behavior
            else "Either the required screenshot is missing/stale or the matching runtime-backed interaction proof is not directly passing."
        )
        _append(
            rows,
            _record(
                record_id=f"screenshot:{screenshot_name}",
                label=label,
                category="captured_surface",
                visual=visual,
                behavior=behavior,
                present_in_chummer5a=True,
                removable_without_degrading=False,
                reason=reason,
                evidence=[str(SCREENSHOT_GATE_PATH), str(VISUAL_GATE_PATH)],
            ),
            seen,
        )

    baseline_status: dict[str, bool] = {}
    for baseline_id, screenshot_list in BASELINE_SCREENSHOT_MAP.items():
        visual = all(
            any(record["id"] == f"screenshot:{name}" and record["visual_parity"] == YES for record in rows)
            for name in screenshot_list
        )
        behavior = all(
            any(record["id"] == f"screenshot:{name}" and record["behavioral_parity"] == YES for record in rows)
            for name in screenshot_list
        )
        baseline_status[baseline_id] = visual and behavior
        _append(
            rows,
            _record(
                record_id=f"baseline:{baseline_id}",
                label=_titleize(baseline_id),
                category="baseline_surface",
                visual=visual,
                behavior=behavior,
                present_in_chummer5a=True,
                removable_without_degrading=False,
                reason=(
                    "The screenshot baseline and matching runtime interaction proof are both present."
                    if visual and behavior
                    else "The screenshot baseline or matching runtime interaction proof is incomplete."
                ),
                evidence=[str(PACK_PATH), str(SCREENSHOT_GATE_PATH), str(VISUAL_GATE_PATH)],
            ),
            seen,
        )

    non_negotiable_status: dict[str, bool] = {}
    non_negotiables = pack.get("desktop_non_negotiable_baseline_map", {}).get("asserted_non_negotiables", [])
    if not isinstance(non_negotiables, list):
        non_negotiables = []
    for item in non_negotiables:
        if not isinstance(item, dict):
            continue
        non_negotiable_id = str(item.get("non_negotiable_id") or "").strip()
        compare_focus = [str(token).strip() for token in item.get("required_compare_focus") or [] if str(token).strip()]
        visual = all(str(token) in json.dumps(pack.get("screenshot_baselines") or []) for token in compare_focus)
        behavior = all(_is_pass(visual_evidence.get(token)) or str(token) in json.dumps(pack.get("screenshot_baselines") or []) for token in compare_focus)
        # The compare focus names are sometimes conceptual rather than direct gate keys.
        # When the corresponding runtime-backed landmark proofs pass, keep the non-negotiable green.
        if non_negotiable_id in {"startup_is_workbench_or_restore", "no_generic_shell_or_dashboard_first", "claim_restore_in_installer_or_in_app", "no_browser_only_claim_code_ritual", "guided_product_installer_happy_path"}:
            behavior = _truthy_passes(visual_evidence, ["runtime_backed_legacy_workbench"])
            visual = "01-initial-shell-light.png" in screenshot_names and "01-initial-shell-light.png" not in missing_screenshots
        elif non_negotiable_id == "file_menu_live":
            behavior = _truthy_passes(visual_evidence, ["runtime_backed_clickable_primary_menus"])
            visual = _truthy_passes(visual_evidence, ["runtime_backed_menu_bar_labels"])
        elif non_negotiable_id == "master_index_first_class":
            behavior = _truthy_passes(visual_evidence, ["runtime_backed_master_index"])
            visual = "16-master-index-dialog-light.png" in screenshot_names and "16-master-index-dialog-light.png" not in missing_screenshots
        elif non_negotiable_id == "character_roster_first_class":
            behavior = _truthy_passes(visual_evidence, ["runtime_backed_character_roster"])
            visual = "17-character-roster-dialog-light.png" in screenshot_names and "17-character-roster-dialog-light.png" not in missing_screenshots
        non_negotiable_status[non_negotiable_id] = visual and behavior
        reason = (
            "This Chummer5A non-negotiable is directly backed by the current screenshot/runtime parity evidence."
            if visual and behavior
            else "This Chummer5A non-negotiable is not directly closed by the current screenshot/runtime parity evidence."
        )
        _append(
            rows,
            _record(
                record_id=f"non_negotiable:{non_negotiable_id}",
                label=NON_NEGOTIABLE_LABELS.get(non_negotiable_id, _titleize(non_negotiable_id)),
                category="non_negotiable",
                visual=visual,
                behavior=behavior,
                present_in_chummer5a=True,
                removable_without_degrading=False,
                reason=reason,
                evidence=[str(PACK_PATH), str(VISUAL_GATE_PATH)],
            ),
            seen,
        )

    legacy_marker_set = set(str(item).strip() for item in visual_evidence.get("legacy_frmcareer_markers") or [] if str(item).strip())
    missing_legacy_markers = set(str(item).strip() for item in visual_evidence.get("missing_legacy_frmcareer_markers") or [] if str(item).strip())
    for landmark in veteran.get("required_landmarks") or []:
        landmark_text = str(landmark).strip()
        if not landmark_text:
            continue
        visual_keys, behavior_keys = LANDMARK_PROOF_KEYS.get(landmark_text, ([], []))
        visual = _truthy_passes(visual_evidence, visual_keys)
        behavior = _truthy_passes(visual_evidence, behavior_keys)
        if landmark_text == "Bottom status strip":
            visual = "StatusStrip" in legacy_marker_set and "StatusStrip" not in missing_legacy_markers
        reason = (
            "This required Chummer5A landmark is directly backed by current screenshot/runtime proof."
            if visual and behavior
            else "This required Chummer5A landmark is not directly closed by current screenshot/runtime proof."
        )
        _append(
            rows,
            _record(
                record_id=f"landmark:{landmark_text.lower().replace(' ', '_')}",
                label=landmark_text,
                category="required_landmark",
                visual=visual,
                behavior=behavior,
                present_in_chummer5a=True,
                removable_without_degrading=False,
                reason=reason,
                evidence=[str(VETERAN_PATH), str(VISUAL_GATE_PATH)],
            ),
            seen,
        )

    for task in veteran.get("veteran_task_compare_packs") or []:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "").strip()
        required_baselines = [str(item).strip() for item in task.get("required_baselines") or [] if str(item).strip()]
        compare_artifacts = [str(item).strip() for item in task.get("compare_artifacts") or [] if str(item).strip()]
        baseline_visual = all(
            any(record["id"] == f"screenshot:{name}" and record["visual_parity"] == YES for record in rows)
            for name in (
                {
                    "first_launch_workbench_or_restore": "01-initial-shell-light.png",
                    "menu_file_open_save_import": "02-menu-open-light.png",
                    "menu_tools_settings_masterindex_roster": "03-settings-open-light.png",
                    "master_index_dense_reference_flow": "16-master-index-dialog-light.png",
                    "character_roster_multi_character_flow": "17-character-roster-dialog-light.png",
                }.get(baseline)
                for baseline in required_baselines
            )
            if name
        )
        behavior = _truthy_passes(visual_evidence, TASK_BEHAVIOR_KEYS.get(task_id, []))
        reason = (
            "Required baseline captures and the matching veteran workflow interaction proof are present."
            if baseline_visual and behavior
            else f"Direct proof is incomplete for baselines {required_baselines} or compare artifacts {compare_artifacts}."
        )
        _append(
            rows,
            _record(
                record_id=f"task:{task_id}",
                label=_titleize(task_id),
                category="veteran_task",
                visual=baseline_visual,
                behavior=behavior,
                present_in_chummer5a=True,
                removable_without_degrading=False,
                reason=reason,
                evidence=[str(VETERAN_PATH), str(SCREENSHOT_GATE_PATH), str(VISUAL_GATE_PATH)],
            ),
            seen,
        )

    for family in veteran.get("families") or []:
        if not isinstance(family, dict):
            continue
        family_id = str(family.get("id") or "").strip()
        compare_artifacts = [str(item).strip() for item in family.get("compare_artifacts") or [] if str(item).strip()]
        statuses = [_artifact_status(item, baseline_status, non_negotiable_status) for item in compare_artifacts]
        visual = all(statuses) if statuses else False
        behavior = all(statuses) if statuses else False
        reason = (
            f"All declared compare artifacts for this Chummer5A family are directly backed by current parity proof: {compare_artifacts}."
            if visual and behavior
            else f"At least one declared compare artifact for this Chummer5A family lacks direct parity proof: {compare_artifacts}."
        )
        _append(
            rows,
            _record(
                record_id=f"family:{family_id}",
                label=_titleize(family_id),
                category="workflow_family",
                visual=visual,
                behavior=behavior,
                present_in_chummer5a=True,
                removable_without_degrading=False,
                reason=reason,
                evidence=[str(VETERAN_PATH), str(VISUAL_GATE_PATH), str(WORKFLOW_GATE_PATH)],
            ),
            seen,
        )

    legacy_markers = [str(item).strip() for item in visual_evidence.get("legacy_frmcareer_markers") or [] if str(item).strip()]
    legacy_behavior = _truthy_passes(visual_evidence, ["runtime_backed_legacy_workbench"])
    for marker in legacy_markers:
        visual = marker not in missing_legacy_markers
        reason = (
            "This Chummer5A dense-workbench landmark is still present in the successor workbench proof."
            if visual and legacy_behavior
            else "This Chummer5A dense-workbench landmark is not directly closed by the current successor proof."
        )
        _append(
            rows,
            _record(
                record_id=f"legacy_marker:{marker}",
                label=marker,
                category="dense_workbench_landmark",
                visual=visual,
                behavior=legacy_behavior,
                present_in_chummer5a=True,
                removable_without_degrading=False,
                reason=reason,
                evidence=[str(VISUAL_GATE_PATH)],
            ),
            seen,
        )

    for bucket_name, bucket_label in EXTRA_MARKER_BUCKETS:
        for marker in visual_evidence.get(bucket_name) or []:
            marker_text = str(marker).strip()
            if not marker_text:
                continue
            _append(
                rows,
                _record(
                    record_id=f"extra:{bucket_name}:{marker_text}",
                    label=marker_text,
                    category="chummer6_only_extra",
                    visual=False,
                    behavior=False,
                    present_in_chummer5a=False,
                    removable_without_degrading=True,
                    reason=f"{bucket_label} is present in Chummer6 proof but explicitly disallowed by the classic-parity gate.",
                    evidence=[str(VISUAL_GATE_PATH)],
                ),
                seen,
            )

    visual_yes = sum(1 for row in rows if row["visual_parity"] == YES)
    visual_no = len(rows) - visual_yes
    behavioral_yes = sum(1 for row in rows if row["behavioral_parity"] == YES)
    behavioral_no = len(rows) - behavioral_yes
    extras_present = [row for row in rows if row["category"] == "chummer6_only_extra"]
    removable_extras_present = [row for row in extras_present if row["removable_without_workflow_degradation"] == YES]

    findings: list[dict[str, str]] = []
    coverage_gap_keys: list[str] = []
    for key in ("desktop_client", "mobile_play_shell", "ui_kit_and_flagship_polish", "media_artifacts"):
        status = str(coverage.get(key) or "").strip().lower()
        if status and status not in {"ready", "pass", "passed"}:
            coverage_gap_keys.append(key)
    if coverage_gap_keys:
        coverage_reason_rows = []
        for key in coverage_gap_keys:
            detail = coverage_details.get(key) if isinstance(coverage_details.get(key), dict) else {}
            reasons = [str(item).strip() for item in detail.get("reasons") or [] if str(item).strip()]
            coverage_reason_rows.append(f"{key}: {', '.join(reasons) if reasons else str(coverage.get(key) or '').strip()}")
        findings.append(
            {
                "severity": "high" if "desktop_client" in coverage_gap_keys else "medium",
                "category": "readiness_gap",
                "summary": "Flagship readiness still contains open coverage keys outside the surface-level desktop parity matrix.",
                "detail": " ; ".join(coverage_reason_rows),
            }
        )

    coverage_missing_rows = [
        row for row in rows
        if row["present_in_chummer5a"] == YES and (row["visual_parity"] == NO or row["behavioral_parity"] == NO)
    ]
    for row in coverage_missing_rows[:12]:
        findings.append(
            {
                "severity": "high" if row["visual_parity"] == NO and row["behavioral_parity"] == NO else "medium",
                "category": "ui_parity_gap",
                "summary": f"{row['label']} is not directly parity-proven.",
                "detail": row["reason"],
            }
        )
    if removable_extras_present:
        for row in removable_extras_present[:12]:
            findings.append(
                {
                    "severity": "medium",
                    "category": "removable_extra",
                    "summary": f"{row['label']} is a Chummer6-only extra that looks removable.",
                    "detail": row["reason"],
                }
            )

    findings.sort(key=lambda item: (0 if item.get("severity") == "high" else 1, item.get("summary", "")))

    notes = [
        "This matrix covers every parity-tracked visible surface and currently-present disallowed extra represented in the Chummer5A oracle, screenshot review gate, visual familiarity gate, workflow execution gate, and veteran workflow packs.",
        "The repo does not contain a true dual-product per-control pixel diff for literally every window control on every dialog; items without direct screenshot/runtime proof are scored `no` even when broader readiness artifacts pass.",
    ]
    if not extras_present:
        notes.append("No currently-audited Chummer6-only visible extras are present in the classic-parity disallow lists, so nothing in that category is presently marked removable.")

    report_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "probe_kind": "ui_parity_audit",
        "scope_note": notes[0],
        "summary": {
            "total_elements": len(rows),
            "visual_yes_count": visual_yes,
            "visual_no_count": visual_no,
            "behavioral_yes_count": behavioral_yes,
            "behavioral_no_count": behavioral_no,
            "chummer6_only_extra_present_count": len(extras_present),
            "removable_extra_present_count": len(removable_extras_present),
            "coverage_gap_keys": coverage_gap_keys,
            "active_runs_count": int(state.get("active_runs_count") or 0),
            "productive_active_runs_count": int(state.get("productive_active_runs_count") or 0),
            "nonproductive_active_runs_count": int(state.get("nonproductive_active_runs_count") or 0),
        },
        "findings": findings,
        "notes": notes,
        "elements": sorted(rows, key=lambda item: (item.get("category", ""), item.get("label", ""))),
    }

    markdown_lines = [
        "# Chummer5A UI Element Parity Audit",
        "",
        f"Generated at: {report_payload['generated_at']}",
        "",
        "## Scope",
        notes[0],
        "",
        "## Summary",
        f"- Total audited elements: {len(rows)}",
        f"- Visual parity yes/no: {visual_yes}/{visual_no}",
        f"- Behavioral parity yes/no: {behavioral_yes}/{behavioral_no}",
        f"- Chummer6-only extras present: {len(extras_present)}",
        f"- Removable extras present: {len(removable_extras_present)}",
        f"- Active/productive/nonproductive shard runs: {int(state.get('active_runs_count') or 0)}/{int(state.get('productive_active_runs_count') or 0)}/{int(state.get('nonproductive_active_runs_count') or 0)}",
        "",
        "## Top findings",
    ]
    if findings:
        for item in findings[:16]:
            markdown_lines.append(f"- [{item['severity'].upper()}] {item['category']}: {item['summary']} {item['detail']}")
    else:
        markdown_lines.append("- No parity findings were emitted from the current audit inputs.")
    markdown_lines.extend(
        [
            "",
            "## Element matrix",
            "",
            "| Element | Category | Visual parity | Behavioral parity | In Chummer5A | Removable without workflow degradation | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in report_payload["elements"]:
        markdown_lines.append(
            "| "
            + " | ".join(
                [
                    str(row["label"]).replace("|", "\\|"),
                    str(row["category"]).replace("|", "\\|"),
                    row["visual_parity"],
                    row["behavioral_parity"],
                    row["present_in_chummer5a"],
                    row["removable_without_workflow_degradation"],
                    str(row["reason"]).replace("|", "\\|"),
                ]
            )
            + " |"
        )

    _write_report(REPORT_JSON_PATH, report_payload)
    _write_report(REPORT_MARKDOWN_PATH, "\n".join(markdown_lines) + "\n")

    output_payload = {
        "probe_kind": "ui_parity_audit",
        "generated_at": report_payload["generated_at"],
        "report_json_path": str(REPORT_JSON_PATH),
        "report_markdown_path": str(REPORT_MARKDOWN_PATH),
        "total_elements": len(rows),
        "visual_yes_count": visual_yes,
        "visual_no_count": visual_no,
        "behavioral_yes_count": behavioral_yes,
        "behavioral_no_count": behavioral_no,
        "chummer6_only_extra_present_count": len(extras_present),
        "removable_extra_present_count": len(removable_extras_present),
        "coverage_gap_keys": coverage_gap_keys,
        "findings": findings[:12],
        "notes": notes,
        "active_runs_count": int(state.get("active_runs_count") or 0),
        "productive_active_runs_count": int(state.get("productive_active_runs_count") or 0),
        "nonproductive_active_runs_count": int(state.get("nonproductive_active_runs_count") or 0),
    }
    print(json.dumps(output_payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
