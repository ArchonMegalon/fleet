from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
import traceback

import yaml


DOCS_ROOT = Path("/docker/fleet/docs/chummer5a-oracle")
README_PATH = DOCS_ROOT / "README.md"
CAPTURE_PACK_PATH = DOCS_ROOT / "parity_lab_capture_pack.yaml"
WORKFLOW_PACK_PATH = DOCS_ROOT / "veteran_workflow_packs.yaml"
LEGACY_ORACLE_PATH = Path("/docker/chummer5a/docs/PARITY_ORACLE.json")
VETERAN_GATE_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/VETERAN_FIRST_MINUTE_GATE.yaml")
FLAGSHIP_PARITY_REGISTRY_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_PARITY_REGISTRY.yaml")
SUCCESSOR_REGISTRY_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml")
SUCCESSOR_QUEUE_PATH = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
DESIGN_SUCCESSOR_QUEUE_PATH = Path(
    "/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
)
READINESS_PATH = Path("/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json")
DESKTOP_EXECUTABLE_EXIT_GATE_PATH = Path(
    "/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
)
DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE_PATH = Path(
    "/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
)
M103_CLOSEOUT_NOTE_PATH = Path("/docker/fleet/feedback/2026-04-18-next90-m103-ea-parity-lab-closeout.md")
READINESS_SYNC_MAX_AGE_SECONDS = 24 * 60 * 60
ACTIVE_RUN_SYNC_MAX_AGE_SECONDS = 15 * 60


def _yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _parse_iso_utc(raw: str) -> datetime:
    normalized = raw.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc_text(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value or "").strip()


def _run_id_timestamp(run_id: str) -> datetime | None:
    raw = str(run_id or "").strip()
    if not raw:
        return None
    match = re.match(r"^(\d{8}T\d{6}Z)-shard-\d+$", raw)
    if match is None:
        return None
    stamp = match.group(1)
    try:
        return _parse_iso_utc(stamp)
    except ValueError:
        return None


def _task_local_telemetry_path_from_sync_context(*, capture_pack: dict, workflow_pack: dict) -> Path:
    capture_sync = dict(capture_pack.get("sync_context") or {})
    workflow_sync = dict(workflow_pack.get("sync_context") or {})

    capture_path = Path(str(capture_sync.get("task_local_telemetry_path") or "").strip())
    workflow_path = Path(str(workflow_sync.get("task_local_telemetry_path") or "").strip())

    assert str(capture_path), "capture pack task_local_telemetry_path missing"
    assert str(workflow_path), "workflow pack task_local_telemetry_path missing"
    assert capture_path == workflow_path
    return capture_path


def _handoff_path_for_task_local_telemetry(task_local_telemetry_path: Path) -> Path:
    run_root = task_local_telemetry_path.parent
    assert run_root.name, f"run root missing for {task_local_telemetry_path}"
    runs_root = run_root.parent
    assert runs_root.name == "runs", f"unexpected run root parent for {task_local_telemetry_path}"
    shard_root = runs_root.parent
    assert shard_root.name.startswith("shard-"), f"unexpected shard root for {task_local_telemetry_path}"
    return shard_root / "ACTIVE_RUN_HANDOFF.generated.md"


def _assert_shard_handoff_present_for_task_local_telemetry(task_local_telemetry_path: Path) -> None:
    handoff_path = _handoff_path_for_task_local_telemetry(task_local_telemetry_path)
    assert handoff_path.exists(), str(handoff_path)

    handoff_text = handoff_path.read_text(encoding="utf-8")
    shard_id = task_local_telemetry_path.parent.parent.parent.name
    assert f"Shard: {shard_id}" in handoff_text, handoff_path
    state_root_line = next((line for line in handoff_text.splitlines() if line.startswith("State root: ")), "")
    assert state_root_line, handoff_path
    assert state_root_line.endswith(f"/{shard_id}"), handoff_path
    assert "- Run id:" in handoff_text, handoff_path


def _handoff_first_output_at(handoff_path: Path) -> str:
    handoff_text = handoff_path.read_text(encoding="utf-8")
    return next(
        (line.split(": ", 1)[1].strip() for line in handoff_text.splitlines() if line.startswith("- First output at: ")),
        "",
    )


def _active_run_id_from_handoff(handoff_path: Path) -> str:
    handoff_text = handoff_path.read_text(encoding="utf-8")
    return next(
        (line.split(": ", 1)[1].strip() for line in handoff_text.splitlines() if line.startswith("- Run id: ")),
        "",
    )


def _expected_task_local_snapshot(task_local_telemetry: dict) -> dict:
    queue_item = dict(task_local_telemetry.get("queue_item") or {})
    frontier_brief = list(task_local_telemetry.get("frontier_briefs") or [])
    frontier_id = 0
    if frontier_brief:
        head = str(frontier_brief[0]).strip().split(" ", 1)[0]
        if head.isdigit():
            frontier_id = int(head)
    return {
        "mode": str(task_local_telemetry.get("mode") or ""),
        "scope_label": str(task_local_telemetry.get("scope_label") or ""),
        "slice_summary": str(task_local_telemetry.get("slice_summary") or ""),
        "status_query_supported": bool(task_local_telemetry.get("status_query_supported")),
        "polling_disabled": bool(task_local_telemetry.get("polling_disabled")),
        "package_id": str(queue_item.get("package_id") or ""),
        "frontier_id": frontier_id,
        "milestone_id": int(queue_item.get("milestone_id") or 0),
        "owned_surfaces": list(queue_item.get("owned_surfaces") or []),
        "allowed_paths": list(queue_item.get("allowed_paths") or []),
    }


def _successor_queue_m103_item(path: Path) -> dict:
    queue = _yaml(path)
    items = [dict(item) for item in (queue.get("items") or [])]
    matches = [item for item in items if str(item.get("package_id") or "").strip() == "next90-m103-ea-parity-lab"]
    assert len(matches) == 1
    return matches[0]


def _successor_registry_m103_task() -> dict:
    registry = _yaml(SUCCESSOR_REGISTRY_PATH)
    milestones = [dict(item) for item in (registry.get("milestones") or [])]
    milestone = next((item for item in milestones if int(item.get("id") or 0) == 103), None)
    assert milestone is not None
    work_tasks = [dict(item) for item in (milestone.get("work_tasks") or [])]
    task = next((item for item in work_tasks if str(item.get("id") or "").strip() == "103.1"), None)
    assert task is not None
    return task


def test_ea_parity_lab_capture_pack_exists_and_tracks_queue_package_contract() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)

    assert capture_pack.get("contract_name") == "executive_assistant.parity_lab_capture_pack"
    assert int(capture_pack.get("schema_version") or 0) == 1

    milestone = dict(capture_pack.get("milestone") or {})
    assert int(milestone.get("id") or 0) == 103
    assert milestone.get("package_id") == "next90-m103-ea-parity-lab"
    assert list(milestone.get("owned_surfaces") or []) == ["parity_lab:capture"]


def test_ea_capture_pack_is_provenanced_to_live_chummer5a_oracle_files() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    source_of_truth = dict(capture_pack.get("source_of_truth") or {})

    assert source_of_truth.get("legacy_oracle_repo") == "/docker/chummer5a"
    files = [Path(item) for item in (source_of_truth.get("legacy_oracle_files") or [])]
    assert files
    for path in files:
        assert path.exists(), str(path)


def test_ea_capture_pack_oracle_inventory_matches_chummer5a_parity_oracle_json() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    inventory = dict(capture_pack.get("oracle_inventory") or {})
    parity_oracle = _json(LEGACY_ORACLE_PATH)

    assert int(inventory.get("tabs_count") or 0) == len(list(parity_oracle.get("tabs") or []))
    assert int(inventory.get("workspace_actions_count") or 0) == len(list(parity_oracle.get("workspaceActions") or []))
    assert int(inventory.get("desktop_controls_count") or 0) == len(list(parity_oracle.get("desktopControls") or []))
    assert list(inventory.get("required_top_menus") or []) == ["File", "Tools", "Windows", "Help"]


def test_ea_capture_pack_includes_import_export_fixtures_with_live_anchors() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)

    fixture_rows = [dict(row) for row in (capture_pack.get("import_export_fixtures") or [])]
    assert fixture_rows

    fixture_ids = {str(row.get("id") or "").strip() for row in fixture_rows}
    assert {
        "open_for_printing_menu_route",
        "open_for_export_menu_route",
        "print_multiple_menu_route",
        "hero_lab_importer_menu_route",
    } <= fixture_ids

    for row in fixture_rows:
        anchor = dict(row.get("source_anchor") or {})
        source_path = Path(str(anchor.get("file") or "").strip())
        source_line = int(anchor.get("line") or 0)
        expected = str(anchor.get("expected_substring") or "").strip()
        compare_focus = {str(item).strip() for item in (row.get("compare_focus") or []) if str(item).strip()}

        assert source_path.exists(), str(source_path)
        assert source_line > 0
        assert expected
        assert compare_focus

        source_lines = source_path.read_text(encoding="utf-8").splitlines()
        assert source_line <= len(source_lines), f"{source_path}:{source_line}"
        assert expected in source_lines[source_line - 1], f"{source_path}:{source_line}"


def test_ea_capture_pack_includes_required_landmarks_in_screenshot_lanes() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    veteran_gate = _yaml(VETERAN_GATE_PATH)

    baseline_rows = list(capture_pack.get("screenshot_baselines") or [])
    assert baseline_rows

    represented_landmarks = {
        str(landmark).strip()
        for row in baseline_rows
        for landmark in (dict(row).get("required_landmarks") or [])
        if str(landmark).strip()
    }
    required_landmarks = {
        str(landmark).strip()
        for landmark in (veteran_gate.get("required_landmarks") or [])
        if str(landmark).strip()
    }

    assert required_landmarks <= represented_landmarks


def test_ea_capture_pack_maps_baselines_to_live_visual_screenshot_artifacts() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    ui_exit_gate = _json(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)

    artifact_root = dict(capture_pack.get("screenshot_artifact_baselines") or {})
    screenshot_dir = Path(str(artifact_root.get("screenshot_dir") or "").strip())
    rows = [dict(row) for row in (artifact_root.get("baseline_to_screenshot") or [])]
    baseline_ids = {
        str(dict(row).get("id") or "").strip()
        for row in (capture_pack.get("screenshot_baselines") or [])
        if str(dict(row).get("id") or "").strip()
    }
    required_receipt_screenshots = {
        str(item).strip()
        for item in ((ui_exit_gate.get("evidence") or {}).get("visual_familiarity.required_screenshots_normalized") or [])
        if str(item).strip()
    }

    assert artifact_root.get("visual_receipt_path") == str(DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE_PATH)
    assert artifact_root.get("required_receipt_key") == "visual_familiarity.required_screenshots_normalized"
    assert artifact_root.get("screenshot_dir") == str(
        ((ui_exit_gate.get("evidence") or {}).get("visual_familiarity_screenshot_dir") or "").strip()
    )
    assert screenshot_dir.exists(), str(screenshot_dir)
    assert rows

    mapped_baselines = {str(row.get("baseline_id") or "").strip() for row in rows}
    assert baseline_ids <= mapped_baselines

    for row in rows:
        baseline_id = str(row.get("baseline_id") or "").strip()
        screenshot = str(row.get("screenshot") or "").strip()
        assert baseline_id in baseline_ids
        assert screenshot in required_receipt_screenshots
        assert (screenshot_dir / screenshot).exists(), str(screenshot_dir / screenshot)


def test_ea_veteran_workflow_pack_carries_required_first_minute_tasks() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    veteran_gate = _yaml(VETERAN_GATE_PATH)

    assert workflow_pack.get("contract_name") == "executive_assistant.veteran_compare_packs"

    task_rows = list(workflow_pack.get("required_first_minute_tasks") or [])
    required_task_ids = {str(dict(row).get("id") or "").strip() for row in (veteran_gate.get("tasks") or [])}
    packed_task_ids = {str(dict(row).get("id") or "").strip() for row in task_rows}

    assert required_task_ids <= packed_task_ids


def test_ea_veteran_task_compare_packs_cover_each_required_first_minute_task() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    required_tasks = {
        str(dict(row).get("id") or "").strip()
        for row in (workflow_pack.get("required_first_minute_tasks") or [])
        if str(dict(row).get("id") or "").strip()
    }
    baseline_ids = {
        str(dict(row).get("id") or "").strip()
        for row in (capture_pack.get("screenshot_baselines") or [])
        if str(dict(row).get("id") or "").strip()
    }

    compare_rows = [dict(row) for row in (workflow_pack.get("veteran_task_compare_packs") or [])]
    compare_ids = {str(row.get("task_id") or "").strip() for row in compare_rows if str(row.get("task_id") or "").strip()}

    assert compare_rows
    assert compare_ids == required_tasks
    for row in compare_rows:
        assert str(row.get("summary") or "").strip()
        baselines = {str(item).strip() for item in (row.get("required_baselines") or []) if str(item).strip()}
        landmarks = {str(item).strip() for item in (row.get("required_landmarks") or []) if str(item).strip()}
        artifacts = {str(item).strip() for item in (row.get("compare_artifacts") or []) if str(item).strip()}
        assert baselines
        assert baselines <= baseline_ids
        assert landmarks
        assert artifacts


def test_ea_veteran_workflow_pack_includes_required_workflow_maps() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    parity_oracle = _json(LEGACY_ORACLE_PATH)

    map_rows = [dict(row) for row in (workflow_pack.get("workflow_maps") or [])]
    assert map_rows

    map_by_id = {str(row.get("id") or "").strip(): row for row in map_rows}
    assert {"build_explain_publish", "import_export_round_trip"} <= set(map_by_id)

    available_actions = {str(item).strip() for item in (parity_oracle.get("workspaceActions") or []) if str(item).strip()}
    fixture_ids = {str(dict(row).get("id") or "").strip() for row in (capture_pack.get("import_export_fixtures") or [])}

    build_map = dict(map_by_id["build_explain_publish"])
    build_actions = {str(item).strip() for item in (build_map.get("oracle_actions") or []) if str(item).strip()}
    assert {"build", "validate", "sources"} <= build_actions
    assert build_actions <= available_actions

    round_trip_map = dict(map_by_id["import_export_round_trip"])
    assert round_trip_map.get("fixture_manifest") == str(CAPTURE_PACK_PATH)
    round_trip_actions = {str(item).strip() for item in (round_trip_map.get("oracle_actions") or []) if str(item).strip()}
    assert round_trip_actions
    assert round_trip_actions <= available_actions

    round_trip_artifacts = {
        str(item).strip()
        for item in (round_trip_map.get("compare_artifacts") or [])
        if str(item).strip()
    }
    fixture_refs = {
        artifact.split("fixture:", 1)[1]
        for artifact in round_trip_artifacts
        if artifact.startswith("fixture:")
    }
    assert fixture_refs
    assert fixture_refs <= fixture_ids


def test_ea_veteran_workflow_pack_covers_every_flagship_parity_family() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    parity_registry = _yaml(FLAGSHIP_PARITY_REGISTRY_PATH)

    packed_family_ids = {str(dict(row).get("id") or "").strip() for row in (workflow_pack.get("families") or [])}
    required_family_ids = {str(dict(row).get("id") or "").strip() for row in (parity_registry.get("families") or [])}

    assert required_family_ids
    assert required_family_ids <= packed_family_ids


def test_ea_veteran_workflow_pack_includes_family_local_m142_proof_packs() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)

    pack_rows = [dict(row) for row in (workflow_pack.get("family_local_proof_packs") or [])]
    pack_by_family = {str(row.get("family_id") or "").strip(): row for row in pack_rows}

    assert {
        "dense_builder_and_career_workflows",
        "dice_initiative_and_table_utilities",
        "identity_contacts_lifestyles_history",
    } <= set(pack_by_family)

    dense = pack_by_family["dense_builder_and_career_workflows"]
    assert list(dense.get("compare_artifacts") or []) == [
        "oracle:tabs",
        "oracle:workspace_actions",
        "workflow:build_explain_publish",
    ]
    assert list(dict(dense.get("screenshot_pack") or {}).get("screenshots") or []) == [
        "05-dense-section-light.png",
        "06-dense-section-dark.png",
        "07-loaded-runner-tabs-light.png",
    ]
    assert any(
        str(item).endswith("UI_LOCAL_RELEASE_PROOF.generated.json")
        for item in (dict(dense.get("interaction_pack") or {}).get("runtime_receipts") or [])
    )

    dice = pack_by_family["dice_initiative_and_table_utilities"]
    assert list(dice.get("compare_artifacts") or []) == ["menu:dice_roller", "workflow:initiative"]
    assert any(
        str(item).endswith("NEXT90_M121_UI_GM_RUNBOARD_ROUTE.generated.json")
        for item in (dict(dice.get("interaction_pack") or {}).get("runtime_receipts") or [])
    )
    assert "ResolveRunboardInitiativeSummary" in set(
        str(item).strip() for item in (dict(dice.get("interaction_pack") or {}).get("required_tokens") or [])
    )

    identity = pack_by_family["identity_contacts_lifestyles_history"]
    assert list(dict(identity.get("screenshot_pack") or {}).get("screenshots") or []) == [
        "10-contacts-section-light.png",
        "11-diary-dialog-light.png",
    ]
    assert "workflow:lifestyles" in set(
        str(item).strip() for item in (dict(identity.get("interaction_pack") or {}).get("required_tokens") or [])
    )


def test_ea_veteran_workflow_pack_includes_route_specific_m143_compare_packs() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)

    pack_rows = [dict(row) for row in (workflow_pack.get("route_specific_compare_packs") or [])]
    pack_by_family = {str(row.get("family_id") or "").strip(): row for row in pack_rows}

    assert {
        "sheet_export_print_viewer_and_exchange",
        "sr6_supplements_designers_and_house_rules",
    } <= set(pack_by_family)

    sheet = pack_by_family["sheet_export_print_viewer_and_exchange"]
    assert list(sheet.get("compare_artifacts") or []) == [
        "menu:open_for_printing",
        "menu:open_for_export",
        "menu:file_print_multiple",
    ]
    sheet_routes = {
        str(route.get("route_id") or "").strip(): dict(route)
        for route in (sheet.get("route_proofs") or [])
        if isinstance(route, dict)
    }
    assert set(sheet_routes) == {
        "menu:open_for_printing",
        "menu:open_for_export",
        "menu:file_print_multiple",
    }
    assert any(
        str(item).endswith("NEXT90_M143_EXPORT_PRINT_SUPPLEMENT_RULE_ENVIRONMENT_RECEIPTS.md")
        for item in (dict(sheet.get("artifact_proofs") or {}).get("output_receipts") or [])
    )
    assert "WorkspaceExchangeDeterministicReceipt" in set(
        str(item).strip() for item in (dict(sheet.get("artifact_proofs") or {}).get("required_output_tokens") or [])
    )

    sr6 = pack_by_family["sr6_supplements_designers_and_house_rules"]
    assert list(sr6.get("compare_artifacts") or []) == [
        "workflow:sr6_supplements",
        "workflow:house_rules",
    ]
    sr6_routes = {
        str(route.get("route_id") or "").strip(): dict(route)
        for route in (sr6.get("route_proofs") or [])
        if isinstance(route, dict)
    }
    assert set(sr6_routes) == {
        "workflow:sr6_supplements",
        "workflow:house_rules",
        "surface:rule_environment_studio",
    }
    assert "Sr6SuccessorLaneDeterministicReceipt" in set(
        str(item).strip() for item in (sr6_routes["workflow:sr6_supplements"].get("required_tokens") or [])
    )
    assert list(dict(sr6.get("artifact_proofs") or {}).get("required_screenshot_markers") or []) == [
        "sr6_rule_environment",
        "sr6_supplements",
        "house_rules",
    ]


def test_ea_veteran_workflow_pack_asserts_desktop_non_negotiables() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    non_negotiables = dict(workflow_pack.get("desktop_non_negotiables_asserted") or {})

    assert non_negotiables.get("no_generic_shell_or_dashboard_first") is True
    assert non_negotiables.get("startup_is_workbench_or_restore") is True
    assert non_negotiables.get("file_menu_live") is True
    assert non_negotiables.get("master_index_first_class") is True
    assert non_negotiables.get("character_roster_first_class") is True
    assert non_negotiables.get("claim_restore_in_installer_or_in_app") is True
    assert non_negotiables.get("no_browser_only_claim_code_ritual") is True
    assert non_negotiables.get("guided_product_installer_happy_path") is True


def test_ea_capture_pack_maps_desktop_non_negotiables_to_concrete_baselines_and_compare_focus() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)

    non_negotiables = dict(workflow_pack.get("desktop_non_negotiables_asserted") or {})
    required_non_negotiable_ids = {key for key, enabled in non_negotiables.items() if enabled is True}

    baselines = list(capture_pack.get("screenshot_baselines") or [])
    baseline_ids = {str(dict(row).get("id") or "").strip() for row in baselines}
    compare_focus_by_baseline = {
        str(dict(row).get("id") or "").strip(): {
            str(item).strip()
            for item in (dict(row).get("compare_focus") or [])
            if str(item).strip()
        }
        for row in baselines
    }

    mapping_root = dict(capture_pack.get("desktop_non_negotiable_baseline_map") or {})
    assert mapping_root.get("coverage_key") == "desktop_client"
    mapping_rows = list(mapping_root.get("asserted_non_negotiables") or [])
    assert mapping_rows
    mapped_ids = {str(dict(row).get("non_negotiable_id") or "").strip() for row in mapping_rows}

    assert required_non_negotiable_ids <= mapped_ids

    for row in mapping_rows:
        row_dict = dict(row)
        non_negotiable_id = str(row_dict.get("non_negotiable_id") or "").strip()
        if not non_negotiable_id:
            continue
        required_baselines = {
            str(item).strip()
            for item in (row_dict.get("required_baselines") or [])
            if str(item).strip()
        }
        required_focus = {
            str(item).strip()
            for item in (row_dict.get("required_compare_focus") or [])
            if str(item).strip()
        }

        assert required_baselines, non_negotiable_id
        assert required_focus, non_negotiable_id
        assert required_baselines <= baseline_ids

        available_focus = set()
        for baseline_id in required_baselines:
            available_focus.update(compare_focus_by_baseline.get(baseline_id, set()))
        assert required_focus <= available_focus, non_negotiable_id


def test_ea_veteran_workflow_pack_declares_non_negotiable_capture_crosswalk() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)

    asserted_non_negotiables = {
        key for key, enabled in dict(workflow_pack.get("desktop_non_negotiables_asserted") or {}).items() if enabled is True
    }
    crosswalk = dict(workflow_pack.get("desktop_non_negotiables_capture_crosswalk") or {})
    assert crosswalk.get("baseline_manifest") == str(CAPTURE_PACK_PATH)
    assert crosswalk.get("map_path") == "desktop_non_negotiable_baseline_map.asserted_non_negotiables"
    assert crosswalk.get("screenshot_artifact_map_path") == "screenshot_artifact_baselines.baseline_to_screenshot"

    required_ids = {str(item).strip() for item in (crosswalk.get("required_non_negotiable_ids") or []) if str(item).strip()}
    assert required_ids == asserted_non_negotiables


def test_ea_veteran_workflow_pack_records_current_external_host_proof_blockers() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    readiness = _json(READINESS_PATH)
    ui_exit_gate = _json(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)
    readiness_generated_at = _parse_iso_utc(str(readiness.get("generated_at") or "").strip())
    workflow_generated_at = _parse_iso_utc(str(workflow_pack.get("generated_at") or "").strip())
    promoted_tuple_packs = {
        str(dict(row).get("tuple") or "").strip()
        for row in (((workflow_pack.get("desktop_client_coverage") or {}).get("tuple_compare_packs")) or [])
        if str(dict(row).get("tuple") or "").strip()
    }
    exit_blocker = ((workflow_pack.get("exit_readiness") or {}).get("blocker") or {})

    local_gate_findings = [str(item).strip() for item in (exit_blocker.get("local_executable_gate_findings") or []) if str(item).strip()]
    ui_local_findings = [
        str(item).strip() for item in (ui_exit_gate.get("local_blocking_findings") or []) if str(item).strip()
    ]
    assert local_gate_findings == ui_local_findings

    blocker_tuples = {
        str(item).strip()
        for item in (
            exit_blocker.get("unresolved_external_host_proof_tuples")
            or []
        )
        if str(item).strip()
    }

    readiness_tuples = {
        str(item).strip()
        for item in ((readiness.get("external_host_proof") or {}).get("unresolved_tuples") or [])
        if str(item).strip()
    }

    # The live readiness file can move after the pack sync; both tuple sets must remain valid promoted desktop tuples.
    assert blocker_tuples <= promoted_tuple_packs
    assert readiness_tuples <= promoted_tuple_packs
    assert (readiness_generated_at - workflow_generated_at).total_seconds() <= READINESS_SYNC_MAX_AGE_SECONDS


def test_ea_pack_timestamps_match_live_readiness_snapshot() -> None:
    readiness = _json(READINESS_PATH)
    readiness_timestamp = _parse_iso_utc(str(readiness.get("generated_at") or "").strip())

    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)

    capture_timestamp = _parse_iso_utc(str(capture_pack.get("generated_at") or "").strip())
    workflow_timestamp = _parse_iso_utc(str(workflow_pack.get("generated_at") or "").strip())

    # Readiness receipts can move after the pack is synced; the pack should stay within the current operating day and never claim future freshness.
    for timestamp in (capture_timestamp, workflow_timestamp):
        assert timestamp <= readiness_timestamp
        assert (readiness_timestamp - timestamp).total_seconds() <= READINESS_SYNC_MAX_AGE_SECONDS


def test_ea_pack_sync_context_matches_worker_safe_inputs() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    task_local_telemetry_path = _task_local_telemetry_path_from_sync_context(
        capture_pack=capture_pack,
        workflow_pack=workflow_pack,
    )
    _assert_shard_handoff_present_for_task_local_telemetry(task_local_telemetry_path)

    readiness = _json(READINESS_PATH)
    ui_exit_gate = _json(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)
    task_local_telemetry = _json(task_local_telemetry_path)

    capture_sync = dict(capture_pack.get("sync_context") or {})
    workflow_sync = dict(workflow_pack.get("sync_context") or {})

    assert capture_sync.get("task_local_telemetry_path") == str(task_local_telemetry_path)
    assert workflow_sync.get("task_local_telemetry_path") == str(task_local_telemetry_path)
    assert task_local_telemetry_path.exists()

    expected_snapshot = _expected_task_local_snapshot(task_local_telemetry)
    assert dict(capture_sync.get("task_local_telemetry_snapshot") or {}) == expected_snapshot
    assert dict(workflow_sync.get("task_local_telemetry_snapshot") or {}) == expected_snapshot

    assert capture_sync.get("readiness_path") == str(READINESS_PATH)
    assert workflow_sync.get("readiness_path") == str(READINESS_PATH)
    readiness_ts = _parse_iso_utc(str(readiness.get("generated_at") or "").strip())
    for sync_ts in (
        _parse_iso_utc(str(capture_sync.get("readiness_generated_at") or "").strip()),
        _parse_iso_utc(str(workflow_sync.get("readiness_generated_at") or "").strip()),
    ):
        assert sync_ts <= readiness_ts
        assert (readiness_ts - sync_ts).total_seconds() <= READINESS_SYNC_MAX_AGE_SECONDS

    assert workflow_sync.get("desktop_executable_exit_gate_path") == str(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)
    ui_exit_gate_ts = _parse_iso_utc(str(ui_exit_gate.get("generated_at") or "").strip())
    workflow_ui_sync_ts = _parse_iso_utc(str(workflow_sync.get("desktop_executable_exit_gate_generated_at") or "").strip())
    assert workflow_ui_sync_ts <= ui_exit_gate_ts
    assert (ui_exit_gate_ts - workflow_ui_sync_ts).total_seconds() <= 15 * 60

    handoff_path = _handoff_path_for_task_local_telemetry(task_local_telemetry_path)
    assert capture_sync.get("runtime_handoff_path") == str(handoff_path)
    assert workflow_sync.get("runtime_handoff_path") == str(handoff_path)
    capture_first_output = str(capture_sync.get("runtime_handoff_first_output_at") or "").strip()
    workflow_first_output = str(workflow_sync.get("runtime_handoff_first_output_at") or "").strip()
    assert capture_first_output
    assert workflow_first_output == capture_first_output
    _parse_iso_utc(capture_first_output)


def test_ea_closed_package_proof_points_at_fleet_owned_artifacts() -> None:
    queue_item = _successor_queue_m103_item(SUCCESSOR_QUEUE_PATH)
    design_queue_item = _successor_queue_m103_item(DESIGN_SUCCESSOR_QUEUE_PATH)
    registry_task = _successor_registry_m103_task()

    expected_paths = {
        str(README_PATH),
        str(CAPTURE_PACK_PATH),
        str(WORKFLOW_PACK_PATH),
        str(M103_CLOSEOUT_NOTE_PATH),
        str(Path(__file__)),
    }
    forbidden_prefixes = (
        "/docker/EA/docs/chummer5a_parity_lab",
        "/docker/EA/.codex-studio/published/CHUMMER5A_PARITY_ORACLE_PACK.generated.json",
    )

    assert queue_item.get("status") == "complete"
    assert queue_item.get("completion_action") == "verify_closed_package_only"
    assert list(queue_item.get("allowed_paths") or []) == ["skills", "tests", "feedback", "docs"]
    assert list(queue_item.get("owned_surfaces") or []) == ["parity_lab:capture", "veteran_compare_packs"]
    queue_proof = {str(item).strip() for item in (queue_item.get("proof") or []) if str(item).strip()}
    assert expected_paths <= queue_proof
    assert "python3 tests/test_ea_parity_lab_capture_pack.py" in queue_proof
    assert not [item for item in queue_proof if item.startswith(forbidden_prefixes)]

    assert design_queue_item.get("status") == "complete"
    assert design_queue_item.get("completion_action") == "verify_closed_package_only"
    assert list(design_queue_item.get("allowed_paths") or []) == ["skills", "tests", "feedback", "docs"]
    assert list(design_queue_item.get("owned_surfaces") or []) == ["parity_lab:capture", "veteran_compare_packs"]
    design_queue_proof = {
        str(item).strip() for item in (design_queue_item.get("proof") or []) if str(item).strip()
    }
    assert expected_paths <= design_queue_proof
    assert "python3 tests/test_ea_parity_lab_capture_pack.py" in design_queue_proof
    assert not [item for item in design_queue_proof if item.startswith(forbidden_prefixes)]

    assert registry_task.get("status") == "complete"
    registry_evidence = {str(item).strip() for item in (registry_task.get("evidence") or []) if str(item).strip()}
    evidence_text = "\n".join(sorted(registry_evidence))
    for expected_path in expected_paths:
        assert expected_path in evidence_text
    assert "python3 tests/test_ea_parity_lab_capture_pack.py exits 0 in /docker/fleet." in evidence_text
    assert not [item for item in registry_evidence if item.startswith(forbidden_prefixes)]


def test_ea_capture_pack_declares_worker_run_guard_against_supervisor_helper_evidence() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    task_local_telemetry_path = _task_local_telemetry_path_from_sync_context(
        capture_pack=capture_pack,
        workflow_pack=workflow_pack,
    )
    task_local_telemetry = _json(task_local_telemetry_path)

    guard = dict(capture_pack.get("worker_run_guard") or {})
    blocked = {str(item).strip().lower() for item in (guard.get("blocked_helper_evidence") or []) if str(item).strip()}
    allowed = {str(item).strip().lower() for item in (guard.get("allowed_evidence_sources") or []) if str(item).strip()}
    workflow_notes = " ".join(
        str(item).strip().lower()
        for item in ((workflow_pack.get("task_local_frontier_context") or {}).get("notes") or [])
        if str(item).strip()
    )

    assert guard.get("implementation_only") is True
    assert guard.get("polling_disabled") is True
    assert task_local_telemetry.get("mode") == "implementation_only"
    assert task_local_telemetry.get("polling_disabled") is True
    assert task_local_telemetry.get("status_query_supported") is False
    assert "supervisor status helpers" in blocked
    assert "supervisor eta helpers" in blocked
    assert "active-run operator status snippets" in blocked
    assert "task-local telemetry file" in allowed
    assert "shard runtime handoff" in allowed
    assert "chummer5a oracle source files" in allowed
    assert "published readiness receipt" in allowed
    assert "ui desktop executable exit-gate receipt" in allowed
    assert "implementation-only" in workflow_notes
    assert "supervisor helper outputs are not package evidence" in workflow_notes


def test_ea_pack_targets_the_current_active_worker_run() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    task_local_telemetry_path = _task_local_telemetry_path_from_sync_context(
        capture_pack=capture_pack,
        workflow_pack=workflow_pack,
    )
    handoff_path = _handoff_path_for_task_local_telemetry(task_local_telemetry_path)
    assert handoff_path.exists(), str(handoff_path)
    active_run_id = _active_run_id_from_handoff(handoff_path)
    assert active_run_id, handoff_path
    shard_id = task_local_telemetry_path.parent.parent.parent.name
    assert shard_id.startswith("shard-")
    assert active_run_id.endswith(f"-{shard_id}")
    recorded_run_id = task_local_telemetry_path.parent.name
    assert recorded_run_id.endswith(f"-{shard_id}")
    assert task_local_telemetry_path.parent.name.endswith(f"-{shard_id}")
    assert task_local_telemetry_path.parent.name.endswith(f"-{task_local_telemetry_path.parent.parent.parent.name}")
    assert task_local_telemetry_path.exists(), str(task_local_telemetry_path)
    recorded_run_ts = _run_id_timestamp(recorded_run_id)
    active_run_ts = _run_id_timestamp(active_run_id)
    assert recorded_run_ts is not None
    assert active_run_ts is not None
    if recorded_run_id == active_run_id:
        assert recorded_run_ts == active_run_ts
        return

    active_task_local_telemetry_path = task_local_telemetry_path.parent.parent / active_run_id / task_local_telemetry_path.name
    assert active_task_local_telemetry_path.exists(), str(active_task_local_telemetry_path)
    recorded_task_local_telemetry = _json(task_local_telemetry_path)
    active_task_local_telemetry = _json(active_task_local_telemetry_path)
    assert _expected_task_local_snapshot(active_task_local_telemetry) == _expected_task_local_snapshot(
        recorded_task_local_telemetry
    )
    delta_seconds = (active_run_ts - recorded_run_ts).total_seconds()
    assert 0 <= delta_seconds <= ACTIVE_RUN_SYNC_MAX_AGE_SECONDS


def test_ea_veteran_workflow_pack_records_successor_wave_context_and_live_ready_frontier_coverage() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    readiness = _json(READINESS_PATH)
    task_local_telemetry_path = _task_local_telemetry_path_from_sync_context(
        capture_pack=_yaml(CAPTURE_PACK_PATH),
        workflow_pack=workflow_pack,
    )
    task_local_telemetry = _json(task_local_telemetry_path)

    task_local_context = dict(workflow_pack.get("task_local_frontier_context") or {})
    assert task_local_context.get("assignment_kind") == "successor_wave_package"
    assert int(task_local_context.get("frontier_id") or 0) == _expected_task_local_snapshot(task_local_telemetry).get("frontier_id")
    assert list(task_local_context.get("focus_profiles") or []) == list(task_local_telemetry.get("focus_profiles") or [])
    assert list(task_local_context.get("focus_owners") or []) == list(task_local_telemetry.get("focus_owners") or [])
    assert list(task_local_context.get("focus_texts") or []) == list(task_local_telemetry.get("focus_texts") or [])
    assert list(task_local_context.get("frontier_briefs") or []) == list(task_local_telemetry.get("frontier_briefs") or [])

    coverage_root = dict(workflow_pack.get("whole_product_frontier_coverage") or {})
    assert coverage_root.get("source_readiness_path") == str(READINESS_PATH)
    assert list(coverage_root.get("package_relevant_coverage_keys") or []) == [
        "fleet_and_operator_loop",
        "desktop_client",
    ]

    lanes = [dict(row) for row in (coverage_root.get("lanes") or [])]
    lane_by_key = {str(row.get("coverage_key") or "").strip(): row for row in lanes}
    assert set(lane_by_key) == {"fleet_and_operator_loop", "desktop_client"}

    readiness_coverage = dict(readiness.get("coverage") or {})
    readiness_details = dict(readiness.get("coverage_details") or {})
    for coverage_key in ("fleet_and_operator_loop", "desktop_client"):
        lane = lane_by_key[coverage_key]
        assert lane.get("live_readiness_status") == readiness_coverage.get(coverage_key)
        assert lane.get("live_readiness_summary") == str(
            dict(readiness_details.get(coverage_key) or {}).get("summary") or ""
        )
        assert str(lane.get("package_relevance") or "").strip()


def test_ea_readme_current_sync_line_matches_manifests_and_handoff() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    task_local_telemetry_path = _task_local_telemetry_path_from_sync_context(
        capture_pack=capture_pack,
        workflow_pack=workflow_pack,
    )

    readme = README_PATH.read_text(encoding="utf-8")
    handoff_path = Path(str(dict(capture_pack.get("sync_context") or {}).get("runtime_handoff_path") or "").strip())
    handoff_first_output_at = _iso_utc_text(dict(capture_pack.get("sync_context") or {}).get("runtime_handoff_first_output_at"))
    run_id = task_local_telemetry_path.parent.name
    readiness_generated_at = _iso_utc_text(dict(capture_pack.get("sync_context") or {}).get("readiness_generated_at"))
    desktop_gate_generated_at = _iso_utc_text(
        dict(workflow_pack.get("sync_context") or {}).get("desktop_executable_exit_gate_generated_at")
    )

    assert run_id in readme
    assert readiness_generated_at in readme
    assert handoff_first_output_at in readme
    assert desktop_gate_generated_at in readme


def test_ea_readme_current_readiness_note_matches_live_receipt() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    readiness = _json(READINESS_PATH)

    warning_keys = [str(item).strip() for item in (readiness.get("warning_keys") or []) if str(item).strip()]
    missing_keys = [str(item).strip() for item in (readiness.get("missing_keys") or []) if str(item).strip()]
    ready_keys = {str(item).strip() for item in (readiness.get("ready_keys") or []) if str(item).strip()}

    if not warning_keys and not missing_keys:
        assert "live proof is green" in readme
        assert "no missing or warning coverage keys remain" in readme
        for coverage_key in (
            "desktop_client",
            "mobile_play_shell",
            "ui_kit_and_flagship_polish",
            "media_artifacts",
            "fleet_and_operator_loop",
        ):
            assert coverage_key in ready_keys
            assert coverage_key in readme
        assert "still keeps `desktop_client` missing" not in readme
        assert "also warns on `mobile_play_shell`" not in readme


def test_ea_capture_pack_oracle_line_proofs_match_live_chummer5a_sources() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    extract = dict(capture_pack.get("oracle_surface_extract") or {})
    line_groups = dict(extract.get("source_line_proofs") or {})
    rows = [
        dict(row)
        for group in line_groups.values()
        if isinstance(group, list)
        for row in group
    ]
    assert rows

    for row in rows:
        source_path = Path(str(row.get("file") or "").strip())
        source_line = int(row.get("line") or 0)
        expected = str(row.get("expected_substring") or "")

        assert source_path.exists(), str(source_path)
        assert source_line > 0
        assert expected

        source_lines = source_path.read_text(encoding="utf-8").splitlines()
        assert source_line <= len(source_lines), f"{source_path}:{source_line}"
        assert expected in source_lines[source_line - 1], f"{source_path}:{source_line}"


def test_ea_desktop_tuple_maps_are_consistent_across_capture_and_workflow_packs() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)

    capture_map = dict(capture_pack.get("desktop_proof_tuple_baseline_map") or {})
    capture_rows = list(capture_map.get("promoted_tuple_compare_packs") or [])
    workflow_rows = list(
        (dict(workflow_pack.get("desktop_client_coverage") or {}).get("tuple_compare_packs")) or []
    )
    capture_tuples = {str(dict(row).get("tuple") or "").strip() for row in capture_rows}
    workflow_tuples = {str(dict(row).get("tuple") or "").strip() for row in workflow_rows}

    assert capture_tuples
    assert capture_tuples == workflow_tuples

    required_baseline_ids = {
        "first_launch_workbench_or_restore",
        "menu_file_open_save_import",
        "menu_tools_settings_masterindex_roster",
        "master_index_dense_reference_flow",
        "character_roster_multi_character_flow",
    }
    required_tuples = {
        "avalonia:linux-x64:linux",
        "avalonia:osx-arm64:macos",
        "avalonia:win-x64:windows",
    }
    assert required_tuples <= capture_tuples

    for row in capture_rows + workflow_rows:
        row_baselines = {str(item).strip() for item in (dict(row).get("required_baselines") or [])}
        assert required_baseline_ids <= row_baselines

    capture_unresolved = {
        str(item).strip()
        for item in (capture_map.get("current_unresolved_external_host_proof_tuples") or [])
        if str(item).strip()
    }
    workflow_unresolved = {
        str(item).strip()
        for item in (
            (dict(workflow_pack.get("desktop_client_coverage") or {}).get("current_unresolved_external_host_proof_tuples"))
            or []
        )
        if str(item).strip()
    }
    assert capture_unresolved == workflow_unresolved


def test_ea_tuple_blockers_match_current_readiness_external_host_proof() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    readiness = _json(READINESS_PATH)
    readiness_generated_at = _parse_iso_utc(str(readiness.get("generated_at") or "").strip())
    workflow_generated_at = _parse_iso_utc(str(workflow_pack.get("generated_at") or "").strip())

    workflow_blockers = {
        str(item).strip()
        for item in (
            ((workflow_pack.get("exit_readiness") or {}).get("blocker") or {}).get("unresolved_external_host_proof_tuples")
            or []
        )
        if str(item).strip()
    }
    readiness_blockers = {
        str(item).strip()
        for item in ((readiness.get("external_host_proof") or {}).get("unresolved_tuples") or [])
        if str(item).strip()
    }
    promoted_tuple_packs = {
        str(dict(row).get("tuple") or "").strip()
        for row in (((workflow_pack.get("desktop_client_coverage") or {}).get("tuple_compare_packs")) or [])
        if str(dict(row).get("tuple") or "").strip()
    }

    assert workflow_blockers <= promoted_tuple_packs
    assert readiness_blockers <= promoted_tuple_packs
    assert (readiness_generated_at - workflow_generated_at).total_seconds() <= READINESS_SYNC_MAX_AGE_SECONDS


def test_ea_veteran_workflow_pack_declares_whole_product_frontier_coverage_keys() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)

    coverage_root = dict(workflow_pack.get("whole_product_frontier_coverage") or {})
    expected_keys = {
        str(item).strip()
        for item in (coverage_root.get("package_relevant_coverage_keys") or [])
        if str(item).strip()
    }
    lane_rows = [dict(row) for row in (coverage_root.get("lanes") or [])]
    lane_keys = {str(row.get("coverage_key") or "").strip() for row in lane_rows if str(row.get("coverage_key") or "").strip()}

    assert lane_keys == expected_keys
    assert lane_keys == {"fleet_and_operator_loop", "desktop_client"}


def test_ea_veteran_whole_product_frontier_lanes_have_status_blockers_and_owner_refs() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    readiness = _json(READINESS_PATH)

    coverage_root = dict(workflow_pack.get("whole_product_frontier_coverage") or {})
    lane_rows = [dict(row) for row in (coverage_root.get("lanes") or [])]
    assert lane_rows
    readiness_coverage = dict(readiness.get("coverage") or {})
    readiness_details = dict(readiness.get("coverage_details") or {})

    for row in lane_rows:
        coverage_key = str(row.get("coverage_key") or "").strip()
        live_readiness_status = str(row.get("live_readiness_status") or "").strip()
        live_readiness_summary = str(row.get("live_readiness_summary") or "").strip()
        package_relevance = str(row.get("package_relevance") or "").strip()

        assert coverage_key
        assert live_readiness_status == readiness_coverage.get(coverage_key)
        assert live_readiness_summary == str(dict(readiness_details.get(coverage_key) or {}).get("summary") or "")
        assert package_relevance


def test_ea_desktop_frontier_lane_matches_current_unresolved_external_host_tuple() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    readiness = _json(READINESS_PATH)
    lane_rows = [dict(row) for row in ((workflow_pack.get("whole_product_frontier_coverage") or {}).get("lanes") or [])]
    desktop_lane = next(row for row in lane_rows if str(row.get("coverage_key") or "").strip() == "desktop_client")
    assert desktop_lane.get("live_readiness_status") == ((readiness.get("coverage") or {}).get("desktop_client"))
    assert desktop_lane.get("live_readiness_summary") == str(
        dict((readiness.get("coverage_details") or {}).get("desktop_client") or {}).get("summary") or ""
    )

    notes = " ".join(
        str(item).strip() for item in ((workflow_pack.get("task_local_frontier_context") or {}).get("notes") or []) if str(item).strip()
    ).lower()
    assert "does not carry per-lane release-readiness status" in notes
    assert "can include missing or warning lanes" in notes


def test_ea_live_desktop_executable_gate_snapshot_matches_ui_receipt() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    ui_exit_gate = _json(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)

    snapshot = dict(workflow_pack.get("live_desktop_executable_gate_snapshot") or {})
    assert snapshot.get("source_path") == str(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)
    assert snapshot.get("status") == ui_exit_gate.get("status")
    assert snapshot.get("blocked_by_external_constraints_only") == ui_exit_gate.get(
        "blocked_by_external_constraints_only"
    )
    snapshot_generated_at = snapshot.get("generated_at")
    snapshot_ts = snapshot_generated_at if isinstance(snapshot_generated_at, str) else str(snapshot_generated_at)
    ui_ts = _parse_iso_utc(str(ui_exit_gate.get("generated_at") or "").strip())
    recorded_ts = _parse_iso_utc(snapshot_ts)
    assert recorded_ts <= ui_ts
    assert (ui_ts - recorded_ts).total_seconds() <= 15 * 60

    total_count = int(snapshot.get("blocking_findings_count") or 0)
    local_count = int(snapshot.get("local_blocking_findings_count") or 0)
    external_count = int(snapshot.get("external_blocking_findings_count") or 0)
    assert total_count == local_count + external_count
    if str(ui_exit_gate.get("status") or "").strip().lower() == "fail":
        assert total_count > 0
        assert local_count > 0 or external_count > 0
    else:
        assert total_count == 0
        assert external_count == 0
    assert local_count >= 0


def test_ea_live_desktop_executable_gate_snapshot_marker_families_remain_grounded() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    ui_exit_gate = _json(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)

    snapshot = dict(workflow_pack.get("live_desktop_executable_gate_snapshot") or {})
    local_findings = {str(item).strip() for item in (ui_exit_gate.get("local_blocking_findings") or []) if str(item).strip()}
    external_findings = {str(item).strip() for item in (ui_exit_gate.get("external_blocking_findings") or []) if str(item).strip()}

    local_text = " ".join(sorted(local_findings)).lower()
    external_text = " ".join(sorted(external_findings)).lower()

    local_families = [dict(family) for family in (snapshot.get("local_blocker_families") or [])]
    if local_findings:
        assert local_families
    else:
        assert not local_families

    for family_dict in local_families:
        family_id = str(family_dict.get("id") or "").strip()
        markers = {str(item).strip().lower() for item in (family_dict.get("keyword_markers") or []) if str(item).strip()}
        assert family_id
        assert markers
        for marker in markers:
            assert marker in local_text, family_id

    for family in (snapshot.get("external_blocker_families") or []):
        family_dict = dict(family)
        family_id = str(family_dict.get("id") or "").strip()
        markers = {str(item).strip().lower() for item in (family_dict.get("keyword_markers") or []) if str(item).strip()}
        assert family_id
        assert markers
        for marker in markers:
            assert marker in external_text, family_id


def test_ea_veteran_workflow_pack_visual_screenshot_snapshot_matches_ui_receipt() -> None:
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    ui_exit_gate = _json(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)

    snapshot = dict(workflow_pack.get("visual_familiarity_screenshot_snapshot") or {})
    screenshot_dir = Path(str(snapshot.get("screenshot_dir") or "").strip())
    snapshot_required = {str(item).strip() for item in (snapshot.get("required_screenshots") or []) if str(item).strip()}
    receipt_required = {
        str(item).strip()
        for item in ((ui_exit_gate.get("evidence") or {}).get("visual_familiarity.required_screenshots_normalized") or [])
        if str(item).strip()
    }
    missing = {str(item).strip() for item in (snapshot.get("missing_screenshots") or []) if str(item).strip()}

    assert snapshot.get("source_path") == str(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)
    assert snapshot.get("screenshot_dir") == str(
        ((ui_exit_gate.get("evidence") or {}).get("visual_familiarity_screenshot_dir") or "").strip()
    )
    assert screenshot_dir.exists(), str(screenshot_dir)
    assert snapshot_required == receipt_required
    assert not missing
    for screenshot in snapshot_required:
        assert (screenshot_dir / screenshot).exists(), str(screenshot_dir / screenshot)


def test_ea_tuple_compare_packs_cover_promoted_avalonia_desktop_gate_tuples() -> None:
    capture_pack = _yaml(CAPTURE_PACK_PATH)
    workflow_pack = _yaml(WORKFLOW_PACK_PATH)
    ui_exit_gate = _json(DESKTOP_EXECUTABLE_EXIT_GATE_PATH)

    gate_tuples = {
        str(item).strip()
        for item in (
            ((ui_exit_gate.get("evidence") or {}).get("desktopTupleCoverage.requiredDesktopPlatformHeadRidTuples_normalized"))
            or []
        )
        if str(item).strip().startswith("avalonia:")
    }
    capture_tuples = {
        str(dict(row).get("tuple") or "").strip()
        for row in ((capture_pack.get("desktop_proof_tuple_baseline_map") or {}).get("promoted_tuple_compare_packs") or [])
        if str(dict(row).get("tuple") or "").strip()
    }
    workflow_tuples = {
        str(dict(row).get("tuple") or "").strip()
        for row in ((workflow_pack.get("desktop_client_coverage") or {}).get("tuple_compare_packs") or [])
        if str(dict(row).get("tuple") or "").strip()
    }

    assert gate_tuples
    assert gate_tuples <= capture_tuples
    assert gate_tuples <= workflow_tuples


def _run_direct() -> int:
    failures = 0
    ran = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        ran += 1
        try:
            fn()
        except Exception:
            failures += 1
            print(f"FAIL: {name}")
            traceback.print_exc()
        else:
            print(f"PASS: {name}")
    print(f"ran={ran} failed={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_run_direct())
