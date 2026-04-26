from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import datetime as dt
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_flagship_product_readiness.py")
SUPPORT_CASE_PACKETS_SCRIPT = Path("/docker/fleet/scripts/materialize_support_case_packets.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("materialize_flagship_product_readiness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_support_case_packets_module():
    previous_sys_path = list(sys.path)
    sys.path.insert(0, str(SUPPORT_CASE_PACKETS_SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location(
            "materialize_support_case_packets_for_readiness_e2e",
            SUPPORT_CASE_PACKETS_SCRIPT,
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = previous_sys_path


def _write_json(path: Path, payload: dict) -> None:
    if isinstance(payload, dict):
        contract_name = str(payload.get("contract_name") or "").strip()
        status = str(payload.get("status") or "").strip().lower()
        if contract_name == "chummer6-ui.desktop_executable_exit_gate" and status in {"pass", "passed", "ready"}:
            evidence = payload.get("evidence")
            if not isinstance(evidence, dict):
                evidence = {}
            evidence.setdefault("flagship UI release gate proof_age_seconds", 30)
            evidence.setdefault("desktop workflow execution gate proof_age_seconds", 30)
            evidence.setdefault("desktop visual familiarity gate proof_age_seconds", 30)
            payload["evidence"] = evidence
            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            payload.setdefault("generated_at", now_iso)
            payload.setdefault("generatedAt", now_iso)
        if "releaseProof" in payload and "artifacts" in payload:
            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            payload.setdefault("generated_at", now_iso)
            payload.setdefault("generatedAt", now_iso)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_horizon_mirror(product_root: Path, module) -> None:
    product_root.mkdir(parents=True, exist_ok=True)
    (product_root / "HORIZONS.md").write_text("# Horizons\n", encoding="utf-8")
    (product_root / "FLAGSHIP_PRODUCT_BAR.md").write_text("# Flagship Bar\n", encoding="utf-8")
    (product_root / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").write_text("# Surface Review\n", encoding="utf-8")
    (product_root / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("# Familiarity Bridge\n", encoding="utf-8")
    (product_root / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("# Desktop Exit Gates\n", encoding="utf-8")
    (product_root / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("# Legacy Parity\n", encoding="utf-8")
    _write_yaml(product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"product": "chummer"})
    horizons_dir = product_root / "horizons"
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for canonical_doc in module.CANONICAL_HORIZONS_DIR.glob("*.md"):
        (horizons_dir / canonical_doc.name).write_text(f"# {canonical_doc.stem}\n", encoding="utf-8")


def _write_synced_external_runbook(module, runbook_path: Path, commands_dir: Path, generated_at: str) -> None:
    commands_dir.mkdir(parents=True, exist_ok=True)
    command_path = commands_dir / "noop-proof.sh"
    command_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    command_path.chmod(0o755)
    command_bundle = module.external_proof_command_bundle_fingerprint(commands_dir)
    runbook_path.parent.mkdir(parents=True, exist_ok=True)
    runbook_path.write_text(
        "\n".join(
            [
                "# External Proof Runbook",
                f"- generated_at: {generated_at}",
                f"- plan_generated_at: {generated_at}",
                f"- release_channel_generated_at: {generated_at}",
                f"- command_bundle_sha256: {command_bundle['sha256']}",
                f"- command_bundle_file_count: {command_bundle['file_count']}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _base_acceptance() -> dict:
    return {
        "product": "chummer",
        "version": 1,
        "source_documents": ["FLAGSHIP_PRODUCT_BAR.md", "PUBLIC_RELEASE_EXPERIENCE.yaml", "METRICS_AND_SLOS.yaml"],
        "acceptance_axes": [{"id": "primary_path_clarity"}, {"id": "authored_ruleset_experience"}],
    }


def _flagship_parity_registry_payload(*, release_status: str) -> dict:
    return {
        "families": [
            {
                "id": "shell_workbench_orientation",
                "legacy_parity_status": "covered",
                "release_status": release_status,
            }
        ]
    }


def _parity_lab_capture_pack_payload(module, *, coverage_key: str = "desktop_client", missing_non_negotiable_ids=()) -> dict:
    required_ids = sorted(set(module.PARITY_LAB_REQUIRED_NON_NEGOTIABLE_IDS) - {str(item).strip() for item in missing_non_negotiable_ids})
    return {
        "desktop_non_negotiable_baseline_map": {
            "coverage_key": coverage_key,
            "asserted_non_negotiables": [{"non_negotiable_id": item} for item in required_ids],
        }
    }


def _veteran_compare_pack_payload(
    module,
    *,
    readiness_target: str = "veteran_approved",
    missing_non_negotiable_ids=(),
    whole_product_coverage_keys=None,
) -> dict:
    required_ids = sorted(set(module.PARITY_LAB_REQUIRED_NON_NEGOTIABLE_IDS) - {str(item).strip() for item in missing_non_negotiable_ids})
    coverage_keys = list(whole_product_coverage_keys or sorted(module.PARITY_LAB_REQUIRED_WHOLE_PRODUCT_COVERAGE_KEYS))
    return {
        "families": [
            {
                "id": "shell_workbench_orientation",
                "readiness_target": readiness_target,
            }
        ],
        "desktop_non_negotiables_asserted": {item: True for item in required_ids},
        "whole_product_frontier_coverage": {"package_relevant_coverage_keys": coverage_keys},
    }


def _materialize_flagship_readiness_with_parity_lab(
    tmp_path: Path,
    module,
    *,
    release_status: str = "gold_ready",
    readiness_target: str = "veteran_approved",
    capture_coverage_key: str = "desktop_client",
    missing_capture_non_negotiable_ids=(),
    missing_workflow_non_negotiable_ids=(),
    whole_product_coverage_keys=None,
    windows_exit_gate_status: str = "passed",
    active_shards_payload=None,
    ooda_state_payload=None,
    synced_external_runbook: bool = False,
    journey_gates_payload: dict | None = None,
    user_journey_tester_audit_payload: dict | None = None,
) -> dict:
    out_path = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    flagship_parity_registry_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PARITY_REGISTRY.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    external_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    external_commands_dir = tmp_path / ".codex-studio" / "published" / "external-proof-commands"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    active_shards_path = tmp_path / "state" / "chummer_design_supervisor" / "active_shards.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_user_journey_tester_audit_path = tmp_path / "ui" / "USER_JOURNEY_TESTER_AUDIT.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"
    parity_lab_capture_pack_path = tmp_path / "docs" / "chummer5a-oracle" / "parity_lab_capture_pack.yaml"
    veteran_compare_pack_path = tmp_path / "docs" / "chummer5a-oracle" / "veteran_workflow_packs.yaml"
    current_iso = _now_iso()

    _write_yaml(acceptance_path, _base_acceptance())
    _write_horizon_mirror(acceptance_path.parent, module)
    _write_yaml(flagship_parity_registry_path, _flagship_parity_registry_payload(release_status=release_status))
    _write_yaml(
        parity_lab_capture_pack_path,
        _parity_lab_capture_pack_payload(
            module,
            coverage_key=capture_coverage_key,
            missing_non_negotiable_ids=missing_capture_non_negotiable_ids,
        ),
    )
    _write_yaml(
        veteran_compare_pack_path,
        _veteran_compare_pack_payload(
            module,
            readiness_target=readiness_target,
            missing_non_negotiable_ids=missing_workflow_non_negotiable_ids,
            whole_product_coverage_keys=whole_product_coverage_keys,
        ),
    )
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, journey_gates_payload or _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    if synced_external_runbook:
        _write_synced_external_runbook(module, external_runbook_path, external_commands_dir, current_iso)
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    supervisor_state = _base_supervisor_state()
    supervisor_state["updated_at"] = current_iso
    supervisor_state["focus_profiles"] = ["top_flagship_grade", "whole_project_frontier"]
    _write_json(supervisor_state_path, supervisor_state)
    if active_shards_payload is not None:
        active_shards = dict(active_shards_payload)
        active_shards.setdefault("generated_at", current_iso)
        _write_json(active_shards_path, active_shards)
    _write_json(ooda_state_path, ooda_state_payload or _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": windows_exit_gate_status,
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        _desktop_executable_exit_gate_pass_payload(
            heads=("avalonia",),
            platforms=("linux", "windows", "macos"),
            generated_at=current_iso,
        ),
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass", "evidence": {}},
    )
    _write_json(ui_visual_familiarity_exit_gate_path, _desktop_visual_familiarity_pass_payload(module))
    _write_json(
        ui_user_journey_tester_audit_path,
        user_journey_tester_audit_payload or _user_journey_tester_audit_pass_payload(module),
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia",),
            platforms=("linux", "windows", "macos"),
            journeys_passed=("install_claim_restore_continue",),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--ui-user-journey-tester-audit",
            str(ui_user_journey_tester_audit_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_materialize_flagship_product_readiness_recovers_windows_gate_from_aggregate_executable_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    payload = _materialize_flagship_readiness_with_parity_lab(
        tmp_path,
        module,
        windows_exit_gate_status="failed",
    )

    assert payload["coverage"]["desktop_client"] == "ready"
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_windows_exit_gate_status"] == "failed"
    assert evidence["ui_windows_exit_gate_recovered_from_executable_gate"] is True
    assert evidence["ui_windows_exit_gate_effective_ready"] is True
    assert payload["coverage_details"]["desktop_client"]["reasons"] == []


def test_materialize_flagship_product_readiness_recovers_stale_ooda_from_current_supervisor_topology(
    tmp_path: Path,
) -> None:
    module = _load_module()
    stale_ooda = _base_ooda_state()
    stale_ooda["aggregate_stale"] = True
    stale_ooda["aggregate_timestamp_stale"] = True

    payload = _materialize_flagship_readiness_with_parity_lab(
        tmp_path,
        module,
        active_shards_payload={
            "active_run_count": 0,
            "active_shards": [],
            "configured_shard_count": 13,
            "configured_shards": [{"name": "shard-1"}, {"name": "shard-2"}],
            "manifest_kind": "configured_shard_topology",
        },
        ooda_state_payload=stale_ooda,
        synced_external_runbook=True,
    )

    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    fleet_detail = payload["coverage_details"]["fleet_and_operator_loop"]
    assert fleet_detail["reasons"] == []
    evidence = fleet_detail["evidence"]
    assert evidence["ooda_controller"] == "up"
    assert evidence["ooda_supervisor"] == "up"
    assert evidence["ooda_state_recovered_from_active_shards"] is True
    assert evidence["ooda_state_recovery_source"] == "configured_shard_topology"
    assert evidence["ooda_aggregate_stale"] is False
    assert evidence["ooda_timestamp_stale"] is False
    assert evidence["ooda_recovered_from_current_supervisor_topology"] is True


def test_materialize_flagship_product_readiness_treats_owner_scoped_routed_campaign_blocker_as_ready(
    tmp_path: Path,
) -> None:
    module = _load_module()
    journey_gates = _base_journey_gates()
    for row in journey_gates["journeys"]:
        if row["id"] == "campaign_session_recover_recap":
            row.update(
                {
                    "state": "blocked",
                    "local_blocking_reasons": [
                        "repo proof chummer6-hub:Chummer.Run.Api/Services/Community/CampaignSpineService.cs is missing required marker 'governed faction, heat, contact, and reputation signal(s)'."
                    ],
                    "blocking_reasons": [
                        "repo proof chummer6-hub:Chummer.Run.Api/Services/Community/CampaignSpineService.cs is missing required marker 'governed faction, heat, contact, and reputation signal(s)'."
                    ],
                    "blockers": [
                        "repo proof chummer6-hub:Chummer.Run.Api/Services/Community/CampaignSpineService.cs is missing required marker 'governed faction, heat, contact, and reputation signal(s)'."
                    ],
                    "owner_repos": ["chummer6-hub", "chummer6-mobile", "chummer6-ui", "fleet"],
                }
            )
            break
    journey_gates["summary"]["overall_state"] = "blocked"
    journey_gates["summary"]["blocked_count"] = 1
    journey_gates["summary"]["blocked_with_local_count"] = 1
    journey_gates["summary"]["blocked_external_only_count"] = 0

    payload = _materialize_flagship_readiness_with_parity_lab(
        tmp_path,
        module,
        journey_gates_payload=journey_gates,
        synced_external_runbook=True,
    )

    assert payload["status"] == "pass"
    assert payload["coverage"]["mobile_play_shell"] == "ready"
    assert payload["coverage"]["ui_kit_and_flagship_polish"] == "ready"
    assert payload["readiness_planes"]["structural_ready"]["status"] == "ready"
    mobile_evidence = payload["coverage_details"]["mobile_play_shell"]["evidence"]
    assert mobile_evidence["campaign_session_recover_recap"] == "blocked"
    assert mobile_evidence["campaign_session_recover_recap_owner_scoped_effective_state"] == "ready"
    assert mobile_evidence["campaign_session_recover_recap_owner_scoped_unrelated_routed_local_only"] is True
    assert mobile_evidence["campaign_session_recover_recap_owner_scoped_routed_owner_repos"] == ["chummer6-hub"]
    ui_kit_evidence = payload["coverage_details"]["ui_kit_and_flagship_polish"]["evidence"]
    assert ui_kit_evidence["campaign_session_recover_recap_owner_scoped_effective_state"] == "ready"
    assert ui_kit_evidence["campaign_session_recover_recap_owner_scoped_unrelated_routed_local_only"] is True
    structural_evidence = payload["readiness_planes"]["structural_ready"]["evidence"]
    assert structural_evidence["journey_overall_state"] == "blocked"
    assert structural_evidence["journey_effective_overall_state"] == "ready"


def _base_feedback_loop_gate() -> dict:
    return {
        "version": 1,
        "release_blocking": True,
        "thresholds": {
            "max_support_packet_age_hours": 24,
            "max_open_non_external_packets": 0,
            "max_closure_waiting_on_release_truth": 0,
            "max_update_required_misrouted_cases": 0,
            "max_non_external_needs_human_response": 0,
            "require_named_owner_on_non_external_packets": True,
            "require_named_lane_on_non_external_packets": True,
            "allow_cached_packet_refresh_for_gold": False,
            "allow_external_backlog_only_with_synced_runbook": True,
            "require_feedback_progress_email_workflow": True,
            "require_feedback_progress_email_e2e_gate": True,
            "require_feedback_progress_email_decision_awards": True,
            "required_feedback_progress_sender_email": "wageslave@chummer.run",
            "require_feedback_discovery_gateway": True,
            "require_feedback_discovery_ltd_registry": True,
            "required_feedback_discovery_route": "karma_forge_discovery",
            "required_feedback_discovery_first_part_steps": [
                "public_signal",
                "structured_prescreen",
                "adaptive_interview",
            ],
            "required_feedback_discovery_tools": [
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
            ],
        },
    }


def _base_feedback_discovery_plan() -> dict:
    return {
        "workflow_ready": True,
        "candidate_count": 1,
        "karma_forge_candidate_count": 1,
        "first_part_routed_count": 1,
        "missing_route_count": 0,
        "missing_next_action_count": 0,
        "route_counts": {"karma_forge_discovery": 1},
        "ltd_registry_path": "/tmp/LTD_RUNTIME_AND_PROJECTION_REGISTRY.yaml",
        "ltd_registry_key": "ltd_runtime_and_projection_registry",
        "ltd_product_system": "discovery_system",
        "ltd_discovery_system_ready": True,
        "ltd_discovery_system_missing_tools": [],
        "ltd_discovery_system_tools": [
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
        ],
        "required_first_part_steps": [
            "public_signal",
            "structured_prescreen",
            "adaptive_interview",
        ],
        "required_tools": [
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
        ],
    }


def _base_support_packets_payload(generated_at: str, *, summary: dict | None = None) -> dict:
    payload = {
        "generated_at": generated_at,
        "feedback_discovery_plan": _base_feedback_discovery_plan(),
    }
    if summary is not None:
        payload["summary"] = summary
    return payload


def _e2e_feedback_loop_gate_with_one_open_discovery_case() -> dict:
    gate = _base_feedback_loop_gate()
    gate["thresholds"] = dict(gate["thresholds"])
    gate["thresholds"]["max_open_non_external_packets"] = 1
    gate["thresholds"]["max_closure_waiting_on_release_truth"] = 1
    gate["thresholds"]["max_non_external_needs_human_response"] = 1
    return gate


def _base_feedback_progress_email_workflow() -> dict:
    return {
        "delivery_plane": {
            "sender_identity": {
                "from_email": "wageslave@chummer.run",
            },
            "dispatch_contract": {
                "tool_name": "connector.dispatch",
                "action_kind": "delivery.send",
                "channel": "email",
                "preferred_provider": "emailit",
                "required_receipt_state": "sent",
                "required_receipt_transport": "emailit",
                "required_receipt_fields": [
                    "delivery_id",
                    "stage_id",
                    "case_id",
                    "recipient",
                    "from_email",
                    "subject",
                    "provider",
                ],
            },
        },
        "decision_awards": {
            "accepted": {"label": "Clad Feedbacker"},
            "denied": {"label": "Denied"},
        },
        "stages": [
            {"id": "request_received"},
            {"id": "audited_decision"},
            {"id": "fix_available"},
        ],
        "e2e_gate": {
            "fail_closed": True,
            "required_stage_sequence": [
                "request_received",
                "audited_decision",
                "fix_available",
            ],
        },
    }


def _base_status_plane() -> dict:
    return {
        "runtime_healing": {"summary": {"alert_state": "healthy"}},
        "projects": [
            {"id": "core", "readiness_stage": "boundary_pure"},
            {
                "id": "ui",
                "readiness_stage": "publicly_promoted",
                "deployment_status": "public",
                "deployment_promotion_stage": "public",
            },
            {
                "id": "hub",
                "readiness_stage": "publicly_promoted",
                "deployment_status": "public",
                "deployment_promotion_stage": "public",
            },
            {"id": "hub-registry", "readiness_stage": "boundary_pure"},
            {
                "id": "mobile",
                "readiness_stage": "publicly_promoted",
                "deployment_status": "public",
                "deployment_promotion_stage": "public",
            },
            {"id": "ui-kit", "readiness_stage": "boundary_pure"},
            {"id": "media-factory", "readiness_stage": "boundary_pure"},
        ],
        "groups": [{"id": "chummer-vnext", "deployment_status": "public"}],
    }


def _base_journey_gates() -> dict:
    return {
        "summary": {"overall_state": "ready"},
        "journeys": [
            {"id": "install_claim_restore_continue", "state": "ready"},
            {"id": "build_explain_publish", "state": "ready"},
            {"id": "campaign_session_recover_recap", "state": "ready"},
            {"id": "recover_from_sync_conflict", "state": "ready"},
            {"id": "report_cluster_release_notify", "state": "ready"},
        ],
    }


def _base_supervisor_state() -> dict:
    return {
        "updated_at": "2026-04-01T08:00:00Z",
        "mode": "flagship_product",
        "completion_audit": {"status": "pass"},
    }


def _base_ooda_state() -> dict:
    return {
        "controller": "up",
        "supervisor": "up",
        "aggregate_stale": False,
        "aggregate_timestamp_stale": False,
    }


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _desktop_executable_exit_gate_pass_payload(
    *,
    heads: tuple[str, ...] = ("avalonia",),
    platforms: tuple[str, ...] = ("linux", "windows", "macos"),
    generated_at: str | None = None,
) -> dict:
    rid_by_platform = {
        "linux": "linux-x64",
        "windows": "win-x64",
        "macos": "osx-arm64",
    }
    enabled_heads = [head for head in heads if str(head).strip()]
    enabled_platforms = [platform for platform in platforms if platform in rid_by_platform]
    evidence = {
        "heads_requiring_flagship_proof": enabled_heads,
        "visual_familiarity_required_desktop_heads": enabled_heads,
        "workflow_execution_required_desktop_heads": enabled_heads,
        "visual_familiarity_head_proofs": {head: "pass" for head in enabled_heads},
        "workflow_execution_head_proofs": {head: "pass" for head in enabled_heads},
    }
    for platform in enabled_platforms:
        evidence[f"{platform}_statuses"] = {
            f"{head}:{rid_by_platform[platform]}": "pass"
            for head in enabled_heads
        }
    if "windows" in enabled_platforms:
        evidence["windows_gates"] = {
            f"{head}:{rid_by_platform['windows']}": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            }
            for head in enabled_heads
        }
    stamp = generated_at or _now_iso()
    return {
        "contract_name": "chummer6-ui.desktop_executable_exit_gate",
        "status": "pass",
        "generated_at": stamp,
        "generatedAt": stamp,
        "local_blocking_findings_count": 0,
        "evidence": evidence,
    }


def _desktop_visual_familiarity_pass_payload(module) -> dict:
    return {
        "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
        "status": "pass",
        "evidence": {
            "required_tests": list(module.DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TESTS),
            "missing_tests": [],
            "missing_required_legacy_interaction_keys": [],
            "runtimeBackedLegacyWorkbench": "pass",
            "runtimeBackedFileMenuRoutes": "pass",
            "runtimeBackedMasterIndex": "pass",
            "runtimeBackedCharacterRoster": "pass",
            "legacyMainframeVisualSimilarity": "pass",
        },
    }


def _user_journey_tester_audit_pass_payload(module) -> dict:
    return {
        "contract_name": "chummer6-ui.user_journey_tester_audit",
        "status": "pass",
        "evidence": {
            "linux_binary_under_test": True,
            "used_internal_apis": False,
            "fix_shard_separate": True,
            "open_blocking_findings_count": 0,
            "workflows": [
                {
                    "id": workflow_id,
                    "status": "pass",
                    "screenshots": [
                        f"{workflow_id}-before.png",
                        f"{workflow_id}-after.png",
                    ],
                }
                for workflow_id in module.USER_JOURNEY_TESTER_REQUIRED_WORKFLOWS
            ],
        },
    }


def _release_channel_payload(
    *,
    heads: tuple[str, ...] = ("avalonia",),
    platforms: tuple[str, ...] = ("linux", "windows", "macos"),
    journeys_passed: tuple[str, ...] = (),
    generated_at: str | None = None,
) -> dict:
    rid_by_platform = {
        "linux": "linux-x64",
        "windows": "win-x64",
        "macos": "osx-arm64",
    }
    enabled_heads = [head for head in heads if str(head).strip()]
    enabled_platforms = [platform for platform in platforms if platform in rid_by_platform]
    payload = {
        "status": "published",
        "channelId": "docker",
        "rolloutState": "promoted_preview",
        "supportabilityState": "preview_supported",
        "releaseProof": {"status": "passed"},
        "desktopTupleCoverage": {
            "requiredDesktopPlatforms": enabled_platforms,
            "requiredDesktopHeads": enabled_heads,
            "promotedPlatformHeads": {
                platform: enabled_heads
                for platform in enabled_platforms
            },
            "missingRequiredPlatforms": [],
            "missingRequiredHeads": [],
            "missingRequiredPlatformHeadPairs": [],
        },
        "artifacts": [
            {
                "head": head,
                "platform": platform,
                "rid": rid_by_platform[platform],
                "kind": "installer",
                "channelId": "docker",
            }
            for platform in enabled_platforms
            for head in enabled_heads
        ],
    }
    if journeys_passed:
        payload["releaseProof"]["journeysPassed"] = list(journeys_passed)
    stamp = generated_at or _now_iso()
    payload["generated_at"] = stamp
    payload["generatedAt"] = stamp
    return payload


def test_format_external_only_completion_reason_dedupes_prefixed_detail() -> None:
    module = _load_module()
    reason = module._format_external_only_completion_reason(
        "Only external host-proof gaps remain: run the missing macos, windows proof lane for 4 desktop tuple(s), ingest receipts, and then republish release truth."
    )
    assert reason == (
        "Only external host-proof gaps remain: run the missing macos, windows proof lane for 4 desktop tuple(s), ingest receipts, and then republish release truth."
    )


def test_format_external_only_completion_reason_handles_empty_detail() -> None:
    module = _load_module()
    reason = module._format_external_only_completion_reason("")
    assert reason == "Only external host-proof gaps remain."


def test_parse_args_inherits_ignore_nonlinux_desktop_host_proof_blockers_from_env(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE", "standard")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", "1")
    args = module.parse_args(["--out", str(Path("/tmp/flagship.json"))])
    assert args.ignore_nonlinux_desktop_host_proof_blockers is True


def test_parse_args_disables_ignore_nonlinux_desktop_host_proof_blockers_for_hard_flagship_env(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE", "top_flagship_grade,whole_project_frontier")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", "1")
    args = module.parse_args(["--out", str(Path("/tmp/flagship.json"))])
    assert args.ignore_nonlinux_desktop_host_proof_blockers is False


def test_parse_args_inherits_ignore_nonlinux_desktop_host_proof_blockers_from_runtime_env_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_module()
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS=1\n", encoding="utf-8")
    monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", raising=False)
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE", "standard")
    monkeypatch.setattr(module, "RUNTIME_ENV_CANDIDATES", (runtime_env,))
    args = module.parse_args(["--repo-root", str(tmp_path), "--out", str(Path("/tmp/flagship.json"))])
    assert args.ignore_nonlinux_desktop_host_proof_blockers is True


def test_release_channel_external_proof_contract_ready_accepts_current_required_tuple_shape() -> None:
    module = _load_module()
    release_channel = {
        "desktopTupleCoverage": {
            "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:osx-arm64:macos",
                    "expectedArtifactId": "avalonia-osx-arm64-installer",
                    "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                    "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                    "expectedInstallerSha256": "abc123",
                    "startupSmokeReceiptContract": {"headId": "avalonia"},
                    "proofCaptureCommands": ["capture", "refresh"],
                }
            ],
        }
    }

    assert module._release_channel_external_proof_contract_ready(release_channel) is True


def test_effective_desktop_executable_gate_local_blockers_ignores_fallback_only_and_canonical_contract_drift() -> None:
    module = _load_module()
    release_channel = {
        "desktopTupleCoverage": {
            "requiredDesktopHeads": ["avalonia"],
            "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:osx-arm64:macos",
                    "expectedArtifactId": "avalonia-osx-arm64-installer",
                    "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                    "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                    "expectedInstallerSha256": "abc123",
                    "startupSmokeReceiptContract": {"headId": "avalonia"},
                    "proofCaptureCommands": ["capture", "refresh"],
                }
            ],
        }
    }
    ui_gate = {
        "localBlockingFindings": [
            "Release channel desktopTupleCoverage.externalProofRequests row(s) proofCaptureCommands must match canonical host-proof capture commands.",
            "Release channel desktopTupleCoverage.externalProofRequests object rows do not match canonical missing-tuple external proof contract.",
            "Linux desktop runtime unit tests are not passing for promoted head 'blazor-desktop'.",
        ]
    }

    blockers = module._effective_desktop_executable_gate_local_blockers(
        ui_gate,
        release_channel=release_channel,
    )

    assert blockers == []


def test_effective_desktop_executable_gate_local_blockers_ignores_nonlinux_startup_smoke_receipt_drift() -> None:
    module = _load_module()
    release_channel = {
        "desktopTupleCoverage": {
            "requiredDesktopHeads": ["avalonia"],
            "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:osx-arm64:macos",
                    "expectedArtifactId": "avalonia-osx-arm64-installer",
                    "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                    "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                    "expectedInstallerSha256": "abc123",
                    "startupSmokeReceiptContract": {"headId": "avalonia"},
                    "proofCaptureCommands": ["capture", "refresh"],
                }
            ],
        }
    }
    ui_gate = {
        "localBlockingFindings": [
            "macOS startup smoke receipt channelId does not match release-channel channelId for promoted head 'avalonia' (osx-arm64).",
            "macOS startup smoke receipt version does not match release channel version for promoted head 'avalonia' (osx-arm64).",
            "macOS startup smoke receipt is stale for promoted head 'avalonia' (osx-arm64) (277440s old).",
        ]
    }

    blockers = module._effective_desktop_executable_gate_local_blockers(
        ui_gate,
        release_channel=release_channel,
    )

    assert blockers == []


def test_executable_gate_freshness_issues_allows_stale_flagship_receipt_when_fresher_dependency_proofs_cover_it() -> None:
    module = _load_module()

    parsed_ages, issues = module.executable_gate_freshness_issues(
        {
            "status": "pass",
            "evidence": {
                "flagship UI release gate proof_age_seconds": 100034,
                "desktop workflow execution gate proof_age_seconds": 6,
                "desktop visual familiarity gate proof_age_seconds": 6,
            },
        },
        max_age_seconds=86400,
    )

    assert parsed_ages == {
        "flagship UI release gate proof_age_seconds": 100034,
        "desktop workflow execution gate proof_age_seconds": 6,
        "desktop visual familiarity gate proof_age_seconds": 6,
    }
    assert issues == []


def test_reason_targets_rules_engine_and_import_scope_distinguishes_core_from_noncore() -> None:
    module = _load_module()

    assert (
        module._reason_targets_rules_engine_and_import_scope(
            "repo proof chummer6-core:Chummer.Infrastructure/Xml/XmlToolCatalogService.cs is missing required marker."
        )
        is True
    )
    assert (
        module._reason_targets_rules_engine_and_import_scope(
            "repo proof file is missing: chummer6-media-factory:src/Chummer.Media.Factory.Runtime/Assets/CreatorPublicationPlannerService.cs."
        )
        is False
    )


def test_feedback_loop_readiness_plane_marks_clean_release_truth_backed_closure_ready() -> None:
    module = _load_module()
    status, plane = module._feedback_loop_readiness_plane(
        feedback_loop_gate=_base_feedback_loop_gate(),
        gate_path=Path("/tmp/FEEDBACK_LOOP_RELEASE_GATE.yaml"),
        feedback_progress_email_workflow=_base_feedback_progress_email_workflow(),
        feedback_progress_email_workflow_path=Path("/tmp/FEEDBACK_PROGRESS_EMAIL_WORKFLOW.yaml"),
        support_packets={
            "generated_at": "2026-04-12T10:00:00Z",
            "source": {},
            "feedback_discovery_plan": _base_feedback_discovery_plan(),
        },
        support_open_packet_count=0,
        support_open_non_external_packet_count=0,
        support_generated_at="2026-04-12T10:00:00Z",
        support_generated_age_seconds=60,
        support_source_refresh_mode="",
        support_closure_waiting_on_release_truth=0,
        support_update_required_misrouted_case_count=0,
        support_non_external_needs_human_response_count=0,
        support_non_external_packets_without_named_owner=0,
        support_non_external_packets_without_lane=0,
        unresolved_external_requests=0,
        external_runbook_synced=True,
    )

    assert status == "ready"
    assert plane["status"] == "ready"
    assert plane["evidence"]["support_open_non_external_packet_count"] == 0
    assert plane["evidence"]["feedback_progress_email_sender"] == "wageslave@chummer.run"
    assert plane["evidence"]["feedback_discovery_gateway_ready"] is True
    assert plane["evidence"]["feedback_discovery_ltd_system_ready"] is True
    assert plane["evidence"]["feedback_discovery_route_counts"] == {"karma_forge_discovery": 1}


def test_feedback_loop_readiness_plane_flags_release_truth_and_owner_gaps() -> None:
    module = _load_module()
    status, plane = module._feedback_loop_readiness_plane(
        feedback_loop_gate=_base_feedback_loop_gate(),
        gate_path=Path("/tmp/FEEDBACK_LOOP_RELEASE_GATE.yaml"),
        feedback_progress_email_workflow={},
        feedback_progress_email_workflow_path=Path("/tmp/FEEDBACK_PROGRESS_EMAIL_WORKFLOW.yaml"),
        support_packets={"generated_at": "2026-04-12T10:00:00Z", "source": {"refresh_mode": "cached_packets_fallback"}},
        support_open_packet_count=3,
        support_open_non_external_packet_count=2,
        support_generated_at="2026-04-12T10:00:00Z",
        support_generated_age_seconds=60,
        support_source_refresh_mode="cached_packets_fallback",
        support_closure_waiting_on_release_truth=1,
        support_update_required_misrouted_case_count=1,
        support_non_external_needs_human_response_count=1,
        support_non_external_packets_without_named_owner=1,
        support_non_external_packets_without_lane=1,
        unresolved_external_requests=0,
        external_runbook_synced=True,
    )

    assert status == "warning"
    assert plane["status"] == "warning"
    assert any("release-truth-backed closure" in reason for reason in plane["reasons"])
    assert any("lack a named owner repo" in reason for reason in plane["reasons"])
    assert any("cached_packets_fallback mode" in reason for reason in plane["reasons"])
    assert any("email workflow" in reason.lower() for reason in plane["reasons"])
    assert any("discovery gateway plan" in reason.lower() for reason in plane["reasons"])


def test_feedback_loop_readiness_e2e_requires_ltd_discovery_system_exit_gate(tmp_path: Path) -> None:
    readiness_module = _load_module()
    support_module = _load_support_case_packets_module()
    feedback_source = {
        "items": [
            {
                "caseId": "feedback-karma-e2e",
                "clusterKey": "feedback:karma:e2e",
                "kind": "feedback",
                "status": "accepted",
                "title": "Campaign house rule edge economy",
                "summary": "The table needs a house rule edge economy before the next run.",
                "candidateOwnerRepo": "chummer6-hub",
            }
        ],
    }

    bad_ltd_registry = tmp_path / "bad-LTD_RUNTIME_AND_PROJECTION_REGISTRY.yaml"
    _write_yaml(
        bad_ltd_registry,
        {
            "key": "ltd_runtime_and_projection_registry",
            "product_systems": {
                "discovery_system": {
                    "tools": ["ProductLift", "Deftform"],
                    "contract": "KARMA_FORGE_DISCOVERY_LAB_WORKFLOWS.yaml",
                }
            },
        },
    )
    good_ltd_registry = tmp_path / "good-LTD_RUNTIME_AND_PROJECTION_REGISTRY.yaml"
    _write_yaml(
        good_ltd_registry,
        {
            "key": "ltd_runtime_and_projection_registry",
            "product_systems": {
                "discovery_system": {
                    "tools": _base_feedback_discovery_plan()["ltd_discovery_system_tools"],
                    "contract": "KARMA_FORGE_DISCOVERY_LAB_WORKFLOWS.yaml",
                }
            },
        },
    )

    original_ltd_paths = (
        support_module.LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH,
        support_module.CANONICAL_LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH,
    )
    try:
        support_module.LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH = bad_ltd_registry
        support_module.CANONICAL_LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH = bad_ltd_registry
        blocked_packets = support_module.build_packets_payload(
            feedback_source,
            "unit",
            release_channel_index={},
        )
        assert blocked_packets["feedback_discovery_plan"]["candidate_count"] == 1
        assert blocked_packets["feedback_discovery_plan"]["ltd_discovery_system_ready"] is False

        support_module.LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH = good_ltd_registry
        support_module.CANONICAL_LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH = good_ltd_registry
        ready_packets = support_module.build_packets_payload(
            feedback_source,
            "unit",
            release_channel_index={},
        )
        assert ready_packets["feedback_discovery_plan"]["candidate_count"] == 1
        assert ready_packets["feedback_discovery_plan"]["ltd_discovery_system_ready"] is True
    finally:
        (
            support_module.LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH,
            support_module.CANONICAL_LTD_RUNTIME_AND_PROJECTION_REGISTRY_PATH,
        ) = original_ltd_paths

    def evaluate(support_packets: dict) -> tuple[str, dict]:
        summary = support_packets["summary"]
        return readiness_module._feedback_loop_readiness_plane(
            feedback_loop_gate=_e2e_feedback_loop_gate_with_one_open_discovery_case(),
            gate_path=Path("/tmp/FEEDBACK_LOOP_RELEASE_GATE.yaml"),
            feedback_progress_email_workflow=_base_feedback_progress_email_workflow(),
            feedback_progress_email_workflow_path=Path("/tmp/FEEDBACK_PROGRESS_EMAIL_WORKFLOW.yaml"),
            support_packets=support_packets,
            support_open_packet_count=summary["open_packet_count"],
            support_open_non_external_packet_count=summary["open_non_external_packet_count"],
            support_generated_at=support_packets["generated_at"],
            support_generated_age_seconds=60,
            support_source_refresh_mode="",
            support_closure_waiting_on_release_truth=summary["closure_waiting_on_release_truth"],
            support_update_required_misrouted_case_count=summary["update_required_misrouted_case_count"],
            support_non_external_needs_human_response_count=summary["non_external_needs_human_response"],
            support_non_external_packets_without_named_owner=summary["non_external_packets_without_named_owner"],
            support_non_external_packets_without_lane=summary["non_external_packets_without_lane"],
            unresolved_external_requests=0,
            external_runbook_synced=True,
        )

    blocked_status, blocked_plane = evaluate(blocked_packets)
    ready_status, ready_plane = evaluate(ready_packets)

    assert blocked_status == "warning"
    assert any("LTD discovery system registry" in reason for reason in blocked_plane["reasons"])
    assert blocked_plane["evidence"]["feedback_discovery_gateway_ready"] is False
    assert blocked_plane["evidence"]["feedback_discovery_ltd_system_ready"] is False
    assert blocked_plane["evidence"]["feedback_discovery_ltd_missing_tools"] == [
        "Signitic",
        "FacePop",
        "Icanpreneur",
        "Lunacal",
        "MetaSurvey",
        "Teable",
        "NextStep",
        "Product Governor",
        "chummer6-design",
        "Emailit",
    ]
    assert ready_status == "ready"
    assert ready_plane["evidence"]["feedback_discovery_gateway_ready"] is True
    assert ready_plane["evidence"]["feedback_discovery_ltd_system_ready"] is True
    assert ready_plane["evidence"]["feedback_discovery_ltd_missing_tools"] == []
    assert ready_plane["evidence"]["feedback_discovery_route_counts"] == {"karma_forge_discovery": 1}


def test_journey_local_blocker_routes_expands_desktop_executable_gate_local_findings() -> None:
    module = _load_module()

    journeys = {
        "install_claim_restore_continue": {
            "state": "blocked",
            "owner_repos": ["chummer6-ui"],
            "local_blocking_reasons": [
                (
                    "repo proof chummer6-ui:.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json "
                    "field 'local_blocking_findings_count' expected 0 but was 24."
                )
            ],
        }
    }
    ui_executable_exit_gate = {
        "local_blocking_findings": [
            "Release channel desktopTupleCoverage.externalProofRequests row(s) proofCaptureCommands must match canonical host-proof capture commands.",
            "Linux gate reason (blazor-desktop): stage unit_tests failed",
            "Linux installer proof is missing install_launch_capture_path for promoted head 'blazor-desktop'.",
        ],
        "evidence": {
            "ui_executable_exit_gate_path": "/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        },
    }

    routed = module._journey_local_blocker_routes(
        journeys,
        ui_executable_exit_gate=ui_executable_exit_gate,
    )

    assert routed["total_local_blocker_count"] == 3
    assert routed["routed_local_blocker_count"] == 3
    assert routed["journey_local_blocker_counts"] == {"install_claim_restore_continue": 3}
    assert routed["owner_repo_counts"] == {"chummer6-ui": 3}
    assert sorted(row["category_id"] for row in routed["routes"]) == [
        "desktop_tuple_external_proof_command_drift",
        "linux_blazor_desktop_receipt_contract",
        "linux_blazor_desktop_unit_tests",
    ]
    assert all(
        row["evidence_path"] == "/docker/chummercomplete/chummer6-ui/.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        for row in routed["routes"]
    )
    assert all("local_blocking_findings_count" not in row["reason"] for row in routed["routes"])


def test_materialize_flagship_product_readiness_fail_closes_ignored_nonlinux_host_proof_when_public_installers_exist(
    tmp_path: Path,
) -> None:
    module = _load_module()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    design_product_root = acceptance_path.parent
    (design_product_root / "HORIZONS.md").write_text("# Horizons\n", encoding="utf-8")
    (design_product_root / "FLAGSHIP_PRODUCT_BAR.md").write_text("# Flagship Bar\n", encoding="utf-8")
    (design_product_root / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").write_text("# Surface Review\n", encoding="utf-8")
    (design_product_root / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("# Familiarity Bridge\n", encoding="utf-8")
    (design_product_root / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("# Desktop Exit Gates\n", encoding="utf-8")
    (design_product_root / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("# Legacy Parity\n", encoding="utf-8")
    _write_yaml(design_product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"product": "chummer"})
    horizons_dir = design_product_root / "horizons"
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for canonical_doc in module.CANONICAL_HORIZONS_DIR.glob("*.md"):
        (horizons_dir / canonical_doc.name).write_text(f"# {canonical_doc.stem}\n", encoding="utf-8")
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-09T12:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-09T12:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "failed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "fail",
            "generated_at": "2026-04-09T12:00:00Z",
            "local_blocking_findings_count": 0,
            "external_blocking_findings_count": 4,
            "blocked_by_external_constraints_only": True,
            "reasons": [
                "Windows desktop exit gate is missing or not passing.",
                "Windows gate reason: Windows startup smoke requires a Windows-capable host; current host cannot run promoted Windows installer smoke.",
                "macOS desktop exit gate is missing or not passing for promoted head 'avalonia' (osx-arm64).",
                "macOS startup smoke receipt is stale for promoted head 'blazor-desktop' (osx-arm64) (228089s old).",
            ],
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia", "blazor-desktop"],
                "visual_familiarity_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "workflow_execution_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "visual_familiarity_head_proofs": {
                    "avalonia": "pass",
                    "blazor-desktop": "pass",
                },
                "workflow_execution_head_proofs": {
                    "avalonia": "pass",
                    "blazor-desktop": "pass",
                },
                "linux_statuses": {
                    "avalonia:linux-x64": "pass",
                    "blazor-desktop:linux-x64": "pass",
                },
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
            "status": "pass",
            "evidence": {
                "runtimeBackedFileMenuRoutes": "pass",
                "runtimeBackedMasterIndex": "pass",
                "runtimeBackedCharacterRoster": "pass",
                "legacyMainframeVisualSimilarity": "pass",
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "blazor-desktop", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
                {"head": "blazor-desktop", "platform": "windows", "rid": "win-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "macos", "rid": "osx-arm64", "kind": "installer"},
                {"head": "blazor-desktop", "platform": "macos", "rid": "osx-arm64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
            "--ignore-nonlinux-desktop-host-proof-blockers",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_exit_gate_status"] == "fail"
    assert evidence["ui_executable_exit_gate_ignored_nonlinux_only"] is True
    assert evidence["desktop_ignore_nonlinux_desktop_host_proof_blockers"] is True
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Non-Linux desktop host-proof blockers cannot be ignored while public Windows or macOS installer media exists."
        in reasons
    )


def test_materialize_flagship_product_readiness_recovers_fleet_bucket_when_only_supervisor_completion_is_stale(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = _now_iso()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    external_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    external_commands_dir = tmp_path / ".codex-studio" / "published" / "external-proof-commands"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    external_proof_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    design_product_root = acceptance_path.parent
    (design_product_root / "HORIZONS.md").write_text("# Horizons\n", encoding="utf-8")
    (design_product_root / "FLAGSHIP_PRODUCT_BAR.md").write_text("# Flagship Bar\n", encoding="utf-8")
    (design_product_root / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").write_text("# Surface Review\n", encoding="utf-8")
    (design_product_root / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("# Familiarity Bridge\n", encoding="utf-8")
    (design_product_root / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("# Desktop Exit Gates\n", encoding="utf-8")
    (design_product_root / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("# Legacy Parity\n", encoding="utf-8")
    _write_yaml(design_product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"product": "chummer"})
    horizons_dir = design_product_root / "horizons"
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for canonical_doc in module.CANONICAL_HORIZONS_DIR.glob("*.md"):
        (horizons_dir / canonical_doc.name).write_text(f"# {canonical_doc.stem}\n", encoding="utf-8")
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    external_commands_dir.mkdir(parents=True, exist_ok=True)
    (external_commands_dir / "noop-proof.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    command_bundle = module.external_proof_command_bundle_fingerprint(external_commands_dir)
    external_runbook_path.parent.mkdir(parents=True, exist_ok=True)
    external_runbook_path.write_text(
        "\n".join(
            [
                "# External Proof Runbook",
                f"- generated_at: {current_iso}",
                f"- plan_generated_at: {current_iso}",
                f"- release_channel_generated_at: {current_iso}",
                f"- command_bundle_sha256: {command_bundle['sha256']}",
                f"- command_bundle_file_count: {command_bundle['file_count']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_json(
        supervisor_state_path,
        {
            "updated_at": current_iso,
            "mode": "sharded",
            "focus_profiles": ["top_flagship_grade", "whole_project_frontier"],
            "completion_audit": {"status": "fail"},
        },
    )
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "failed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "fail",
            "generated_at": "2026-04-09T12:00:00Z",
            "local_blocking_findings_count": 0,
            "external_blocking_findings_count": 4,
            "blocked_by_external_constraints_only": True,
            "reasons": [
                "Windows desktop exit gate is missing or not passing.",
                "Windows gate reason: Windows startup smoke requires a Windows-capable host; current host cannot run promoted Windows installer smoke.",
                "macOS desktop exit gate is missing or not passing for promoted head 'avalonia' (osx-arm64).",
                "macOS startup smoke receipt is stale for promoted head 'blazor-desktop' (osx-arm64) (228089s old).",
            ],
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia", "blazor-desktop"],
                "visual_familiarity_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "workflow_execution_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "visual_familiarity_head_proofs": {
                    "avalonia": "pass",
                    "blazor-desktop": "pass",
                },
                "workflow_execution_head_proofs": {
                    "avalonia": "pass",
                    "blazor-desktop": "pass",
                },
                "linux_statuses": {
                    "avalonia:linux-x64": "pass",
                    "blazor-desktop:linux-x64": "pass",
                },
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
            "status": "pass",
            "evidence": {
                "runtimeBackedFileMenuRoutes": "pass",
                "runtimeBackedMasterIndex": "pass",
                "runtimeBackedCharacterRoster": "pass",
                "legacyMainframeVisualSimilarity": "pass",
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia", "blazor-desktop"),
            platforms=("linux",),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
            "--ignore-nonlinux-desktop-host-proof-blockers",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "ready"
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    assert payload["coverage_details"]["fleet_and_operator_loop"]["reasons"] == []
    fleet_evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert fleet_evidence["supervisor_completion_status"] == "fail"
    assert fleet_evidence["supervisor_completion_status_recovered_from_current_readiness"] is True


def test_materialize_flagship_product_readiness_uses_effective_install_journey_and_aggregate_linux_gate(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = _now_iso()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_horizon_mirror(acceptance_path.parent, module)
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    journey_gates = _base_journey_gates()
    journey_gates["summary"] = {"overall_state": "blocked"}
    journey_gates["journeys"][0] = {
        "id": "install_claim_restore_continue",
        "state": "blocked",
        "local_blocking_reasons": [
            "repo proof chummer6-hub:.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json is stale (215485s old > 172800s max).",
        ],
        "owner_repos": ["chummer6-hub", "fleet"],
    }
    _write_json(journey_gates_path, journey_gates)
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(
        ui_local_release_path,
        {
            "contract_name": "chummer6-ui.local_release_proof",
            "status": "passed",
            "journeysPassed": ["install_claim_restore_continue"],
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "failed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        _desktop_executable_exit_gate_pass_payload(
            heads=("avalonia",),
            platforms=("linux",),
            generated_at=current_iso,
        ),
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(ui_visual_familiarity_exit_gate_path, _desktop_visual_familiarity_pass_payload(module))
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia",),
            platforms=("linux",),
            journeys_passed=("install_claim_restore_continue",),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
            "--ignore-nonlinux-desktop-host-proof-blockers",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "ready"
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_linux_exit_gate_status"] == "failed"
    assert evidence["ui_linux_exit_gate_effective_ready"] is True
    assert evidence["install_claim_restore_continue"] == "blocked"
    assert evidence["install_claim_restore_continue_effective"] == "ready"
    assert payload["coverage_details"]["desktop_client"]["reasons"] == []


def test_materialize_flagship_product_readiness_marks_real_missing_lanes(tmp_path: Path) -> None:
    module = _load_module()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    design_product_root = acceptance_path.parent
    (design_product_root / "HORIZONS.md").write_text("# Horizons\n", encoding="utf-8")
    (design_product_root / "FLAGSHIP_PRODUCT_BAR.md").write_text("# Flagship Bar\n", encoding="utf-8")
    (design_product_root / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").write_text("# Surface Review\n", encoding="utf-8")
    (design_product_root / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("# Familiarity Bridge\n", encoding="utf-8")
    (design_product_root / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("# Desktop Exit Gates\n", encoding="utf-8")
    (design_product_root / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("# Legacy Parity\n", encoding="utf-8")
    _write_yaml(design_product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"product": "chummer"})
    horizons_dir = design_product_root / "horizons"
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for canonical_doc in module.CANONICAL_HORIZONS_DIR.glob("*.md"):
        (horizons_dir / canonical_doc.name).write_text(f"# {canonical_doc.stem}\n", encoding="utf-8")
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    journey_gates = _base_journey_gates()
    install_journey = next(
        row for row in (journey_gates.get("journeys") or []) if isinstance(row, dict) and row.get("id") == "install_claim_restore_continue"
    )
    install_journey["external_proof_requests"] = [
        {
            "tuple_id": "avalonia:win-x64:windows",
            "required_host": "windows",
            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
        },
        {
            "tuple_id": "blazor-desktop:osx-arm64:macos",
            "required_host": "macos",
            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
        },
    ]
    _write_json(journey_gates_path, journey_gates)
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "macos_statuses": {
                    "avalonia:osx-arm64": "pass",
                }
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
                "artifacts": [
                    {"head": "avalonia", "platform": "linux", "kind": "installer"},
                    {"head": "avalonia", "platform": "windows", "kind": "installer"},
                    {"head": "avalonia", "platform": "macos", "kind": "installer"},
                ],
            },
        )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.flagship_product_readiness"
    assert payload["status"] == "fail"
    assert payload["coverage"]["desktop_client"] == "missing"
    assert payload["coverage"]["hub_and_registry"] == "ready"
    assert payload["coverage"]["mobile_play_shell"] == "ready"
    desktop_evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert desktop_evidence["install_claim_restore_continue_external_proof_request_count"] == 2
    assert desktop_evidence["install_claim_restore_continue_external_proof_request_hosts"] == ["macos", "windows"]
    assert desktop_evidence["install_claim_restore_continue_external_proof_request_tuples"] == [
        "avalonia:win-x64:windows",
        "blazor-desktop:osx-arm64:macos",
    ]
    assert payload["completion_audit"]["status"] == "fail"
    assert isinstance(payload["completion_audit"]["external_only"], bool)
    assert payload["completion_audit"]["unresolved_external_proof_request_count"] == 2
    assert payload["completion_audit"]["unresolved_external_proof_request_hosts"] == ["macos", "windows"]
    assert payload["completion_audit"]["unresolved_external_proof_request_tuples"] == [
        "avalonia:win-x64:windows",
        "blazor-desktop:osx-arm64:macos",
    ]


def test_materialize_flagship_product_readiness_accepts_pass_status_for_hub_release_channel(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    journey_gates = _base_journey_gates()
    for row in journey_gates["journeys"]:
        if row.get("id") in {"install_claim_restore_continue", "report_cluster_release_notify"}:
            row["state"] = "ready"
            row["blocking_reasons"] = []
            row["local_blocking_reasons"] = []
            row["external_blocking_reasons"] = []
            row["blocked_by_external_constraints_only"] = False
            row["external_proof_requests"] = []
    journey_gates["summary"]["overall_state"] = "ready"
    journey_gates["summary"]["blocked_count"] = 0
    journey_gates["summary"]["blocked_external_only_count"] = 0
    journey_gates["summary"]["blocked_with_local_count"] = 0
    _write_json(journey_gates_path, journey_gates)
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z", "summary": {}})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "pass"},
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(tmp_path / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(tmp_path / "missing-ui-linux.json"),
            "--ui-windows-exit-gate",
            str(tmp_path / "missing-ui-windows.json"),
            "--ui-workflow-parity-proof",
            str(tmp_path / "missing-ui-workflow-parity.json"),
            "--ui-executable-exit-gate",
            str(tmp_path / "missing-ui-executable.json"),
            "--ui-workflow-execution-gate",
            str(tmp_path / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(tmp_path / "missing-ui-visual.json"),
            "--ui-localization-release-gate",
            str(tmp_path / "missing-ui-localization.json"),
            "--sr4-workflow-parity-proof",
            str(tmp_path / "missing-sr4.json"),
            "--sr6-workflow-parity-proof",
            str(tmp_path / "missing-sr6.json"),
            "--sr4-sr6-frontier-receipt",
            str(tmp_path / "missing-frontier.json"),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(tmp_path / "missing-mobile.json"),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(tmp_path / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "Registry release channel is not in a published-and-proven state." not in (
        payload["coverage_details"]["hub_and_registry"]["reasons"]
    )
    assert payload["flagship_readiness_audit"]["status"] == "fail"
    assert payload["flagship_readiness_audit"]["coverage_gap_keys"]
    assert set(payload["flagship_readiness_audit"]["coverage_gap_keys"]) == set(payload["warning_keys"] + payload["missing_keys"])
    assert payload["flagship_readiness_audit"]["warning_coverage_keys"] == payload["warning_keys"]
    assert payload["flagship_readiness_audit"]["missing_coverage_keys"] == payload["missing_keys"]
    assert payload["external_host_proof"]["status"] == "pass"
    assert payload["external_host_proof"]["reason"] == "No unresolved external desktop host-proof requests remain."
    assert payload["external_host_proof"]["unresolved_request_count"] == 0
    assert payload["external_host_proof"]["unresolved_hosts"] == []
    assert payload["external_host_proof"]["unresolved_tuples"] == []
    assert payload["summary"]["warning_count"] + payload["summary"]["missing_count"] > 0
    assert set(payload["missing_keys"]).issubset(set(payload["coverage"].keys()))
    assert set(payload["missing_keys"]).isdisjoint(set(payload["warning_keys"]))


def test_materialize_flagship_product_readiness_uses_release_proof_journey_override_for_public_and_fleet_lanes(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    external_proof_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    design_product_root = acceptance_path.parent
    (design_product_root / "HORIZONS.md").write_text("# Horizons\n", encoding="utf-8")
    (design_product_root / "FLAGSHIP_PRODUCT_BAR.md").write_text("# Flagship Bar\n", encoding="utf-8")
    (design_product_root / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").write_text("# Surface Review\n", encoding="utf-8")
    (design_product_root / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("# Familiarity Bridge\n", encoding="utf-8")
    (design_product_root / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("# Desktop Exit Gates\n", encoding="utf-8")
    (design_product_root / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("# Legacy Parity\n", encoding="utf-8")
    _write_yaml(design_product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"product": "chummer"})
    horizons_dir = design_product_root / "horizons"
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for canonical_doc in module.CANONICAL_HORIZONS_DIR.glob("*.md"):
        (horizons_dir / canonical_doc.name).write_text(f"# {canonical_doc.stem}\n", encoding="utf-8")
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "blocked",
                "blocked_count": 2,
                "blocked_external_only_count": 0,
                "blocked_with_local_count": 1,
            },
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "blocked",
                    "owner_repos": ["chummer6-ui"],
                    "local_blocking_reasons": [
                        "repo proof chummer6-ui:.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json field 'local_blocking_findings_count' expected 0 but was 2."
                    ],
                    "external_blocking_reasons": [],
                    "external_proof_requests": [],
                    "blocked_by_external_constraints_only": False,
                },
                {"id": "build_explain_publish", "state": "ready"},
                {"id": "campaign_session_recover_recap", "state": "ready"},
                {"id": "recover_from_sync_conflict", "state": "ready"},
                {
                    "id": "report_cluster_release_notify",
                    "state": "blocked",
                    "local_blocking_reasons": [],
                    "external_blocking_reasons": [],
                    "external_proof_requests": [],
                    "blocked_by_external_constraints_only": False,
                },
            ],
        },
    )
    _write_json(support_packets_path, _base_support_packets_payload(current_iso, summary={}))
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        external_proof_runbook_path,
        external_proof_runbook_path.parent / "external-proof-commands",
        current_iso,
    )
    supervisor_state = _base_supervisor_state()
    supervisor_state["updated_at"] = current_iso
    supervisor_state["focus_profiles"] = ["top_flagship_grade", "whole_project_frontier"]
    _write_json(supervisor_state_path, supervisor_state)
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "fail",
            "local_blocking_findings_count": 2,
            "local_blocking_findings": [
                "Linux desktop exit gate is missing or not passing for promoted head 'avalonia'.",
                "Linux installer startup smoke receipt path is missing/unreadable for promoted head 'avalonia'.",
            ],
            "evidence": {},
        },
    )
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {
                "status": "passed",
                "journeysPassed": [
                    "install_claim_restore_continue",
                    "report_cluster_release_notify",
                ],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    module.materialize_flagship_product_readiness(
        out_path=out_path,
        mirror_path=None,
        acceptance_path=acceptance_path,
        parity_registry_path=tmp_path / "missing-parity.yaml",
        feedback_loop_gate_path=tmp_path / "missing-feedback-loop.yaml",
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        external_proof_runbook_path=external_proof_runbook_path,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_path,
        ui_linux_exit_gate_path=tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json",
        ui_windows_exit_gate_path=tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json",
        ui_workflow_parity_proof_path=tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json",
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json",
        ui_visual_familiarity_exit_gate_path=tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json",
        ui_localization_release_gate_path=tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
        sr4_workflow_parity_proof_path=tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json",
        sr6_workflow_parity_proof_path=tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json",
        sr4_sr6_frontier_receipt_path=tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json",
        hub_local_release_proof_path=hub_local_release_path,
        mobile_local_release_proof_path=mobile_local_release_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ignore_nonlinux_desktop_host_proof_blockers=False,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["hub_and_registry"] == "ready"
    assert payload["coverage"]["horizons_and_public_surface"] == "ready"
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    assert payload["coverage_details"]["hub_and_registry"]["evidence"]["install_claim_restore_continue_release_proof_override"] is True
    assert payload["coverage_details"]["hub_and_registry"]["evidence"]["report_cluster_release_notify_release_proof_override"] is True
    assert payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]["journey_overall_state"] == "blocked"
    assert payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]["journey_effective_overall_state"] == "ready"


def test_materialize_flagship_product_readiness_recovers_fleet_loop_when_only_routed_hub_stale_proofs_remain(
    tmp_path: Path,
) -> None:
    module = _load_module()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    external_proof_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    current_iso = _now_iso()
    _write_yaml(acceptance_path, _base_acceptance())
    _write_horizon_mirror(acceptance_path.parent, module)
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "blocked",
                "blocked_count": 2,
                "blocked_external_only_count": 0,
                "blocked_with_local_count": 2,
            },
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "blocked",
                    "owner_repos": ["chummer6-hub"],
                    "local_blocking_reasons": [
                        "repo proof chummer6-hub:.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json is stale (215485s old > 172800s max)."
                    ],
                    "external_blocking_reasons": [],
                    "external_proof_requests": [],
                    "blocked_by_external_constraints_only": False,
                },
                {"id": "build_explain_publish", "state": "ready"},
                {"id": "campaign_session_recover_recap", "state": "ready"},
                {"id": "recover_from_sync_conflict", "state": "ready"},
                {
                    "id": "organize_community_and_close_loop",
                    "state": "blocked",
                    "owner_repos": ["chummer6-hub"],
                    "local_blocking_reasons": [
                        "repo proof chummer6-hub:.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json is stale (215485s old > 172800s max)."
                    ],
                    "external_blocking_reasons": [],
                    "external_proof_requests": [],
                    "blocked_by_external_constraints_only": False,
                },
            ],
        },
    )
    _write_json(support_packets_path, _base_support_packets_payload(current_iso, summary={}))
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        external_proof_runbook_path,
        external_proof_runbook_path.parent / "external-proof-commands",
        current_iso,
    )
    supervisor_state = _base_supervisor_state()
    supervisor_state["updated_at"] = current_iso
    supervisor_state["focus_profiles"] = ["top_flagship_grade", "whole_project_frontier"]
    _write_json(supervisor_state_path, supervisor_state)
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        _desktop_executable_exit_gate_pass_payload(
            heads=("avalonia",),
            platforms=("linux",),
            generated_at=current_iso,
        ),
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(ui_visual_familiarity_exit_gate_path, _desktop_visual_familiarity_pass_payload(module))
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia",),
            platforms=("linux",),
            journeys_passed=("install_claim_restore_continue", "organize_community_and_close_loop"),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    module.materialize_flagship_product_readiness(
        out_path=out_path,
        mirror_path=None,
        acceptance_path=acceptance_path,
        parity_registry_path=tmp_path / "missing-parity.yaml",
        feedback_loop_gate_path=tmp_path / "missing-feedback-loop.yaml",
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        external_proof_runbook_path=external_proof_runbook_path,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_path,
        ui_linux_exit_gate_path=ui_exit_gate_path,
        ui_windows_exit_gate_path=ui_windows_exit_gate_path,
        ui_workflow_parity_proof_path=ui_workflow_parity_path,
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        ui_localization_release_gate_path=tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
        sr4_workflow_parity_proof_path=sr4_workflow_parity_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_path,
        mobile_local_release_proof_path=mobile_local_release_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ignore_nonlinux_desktop_host_proof_blockers=False,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert "flagship_ready" in payload["readiness_plane_gap_keys"]
    assert payload["completion_audit"]["status"] == "fail"
    assert "readiness planes are not green" in payload["completion_audit"]["reason"]
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    fleet_evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert fleet_evidence["journey_overall_state"] == "blocked"
    assert fleet_evidence["journey_effective_overall_state"] == "ready"
    assert fleet_evidence["journey_blocked_with_local_count"] == 2
    assert fleet_evidence["journey_effective_blocked_with_local_count"] == 0
    assert fleet_evidence["journey_local_blocker_autofix_routing_ready"] is True
    assert fleet_evidence["supervisor_completion_status"] == "pass"
    assert "supervisor_completion_status_recovered_from_current_readiness" not in fleet_evidence


def test_materialize_flagship_product_readiness_external_only_requires_no_desktop_local_blockers(
    tmp_path: Path,
) -> None:
    module = _load_module()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "blocked",
                "blocked_count": 1,
                "blocked_external_only_count": 1,
                "blocked_with_local_count": 0,
            },
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "blocked",
                    "blocked_by_external_constraints_only": True,
                    "external_proof_requests": [
                        {
                            "tuple_id": "avalonia:win-x64:windows",
                            "required_host": "windows",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ],
                    "external_blocking_reasons": ["Requires native Windows host proof capture."],
                    "local_blocking_reasons": [],
                },
                {
                    "id": "build_explain_publish",
                    "state": "blocked",
                    "blocked_by_external_constraints_only": True,
                    "external_proof_requests": [
                        {
                            "tuple_id": "avalonia:osx-arm64:macos",
                            "required_host": "macos",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ],
                    "external_blocking_reasons": ["Requires native macOS host proof capture."],
                    "local_blocking_reasons": [],
                },
                {"id": "report_cluster_release_notify", "state": "ready"},
            ],
        },
    )
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(ui_windows_exit_gate_path, {"contract_name": "chummer6-ui.windows_desktop_exit_gate", "status": "failed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "fail",
            "local_blocking_findings_count": 3,
            "reasons": ["Executable gate local blocker sample."],
            "evidence": {},
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {"linux": ["avalonia"], "windows": [], "macos": []},
                "missingRequiredPlatforms": ["windows", "macos"],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows", "avalonia:macos"],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    module.materialize_flagship_product_readiness(
        out_path=out_path,
        mirror_path=None,
        acceptance_path=acceptance_path,
        parity_registry_path=tmp_path / "missing-parity.yaml",
        feedback_loop_gate_path=tmp_path / "missing-feedback-loop.yaml",
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        external_proof_runbook_path=None,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_path,
        ui_linux_exit_gate_path=ui_exit_gate_path,
        ui_windows_exit_gate_path=ui_windows_exit_gate_path,
        ui_workflow_parity_proof_path=ui_workflow_parity_path,
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        ui_localization_release_gate_path=tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
        sr4_workflow_parity_proof_path=sr4_workflow_parity_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_path,
        mobile_local_release_proof_path=mobile_local_release_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ignore_nonlinux_desktop_host_proof_blockers=False,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["completion_audit"]["status"] == "fail"
    assert payload["completion_audit"]["external_only"] is False
    assert payload["completion_audit"]["reason"].startswith(
        "Flagship product readiness planes are not green:"
    )
    assert payload["coverage"]["desktop_client"] == "missing"
    assert payload["coverage"]["hub_and_registry"] == "ready"
    assert payload["coverage"]["horizons_and_public_surface"] == "warning"
    assert payload["coverage"]["fleet_and_operator_loop"] == "warning"
    assert "fleet_and_operator_loop" in payload["warning_keys"]
    assert "horizons_and_public_surface" in payload["warning_keys"]
    assert payload["missing_keys"] == ["desktop_client"]


def test_materialize_flagship_product_readiness_recovers_fleet_when_only_blocked_journeys_are_desktop_scoped(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    flagship_bar_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_BAR.md"
    horizons_overview_path = tmp_path / ".codex-design" / "product" / "HORIZONS.md"
    horizons_dir = tmp_path / ".codex-design" / "product" / "horizons"
    surface_design_review_loop_path = tmp_path / ".codex-design" / "product" / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md"
    familiarity_bridge_path = tmp_path / ".codex-design" / "product" / "CHUMMER5A_FAMILIARITY_BRIDGE.md"
    desktop_executable_exit_gates_path = tmp_path / ".codex-design" / "product" / "DESKTOP_EXECUTABLE_EXIT_GATES.md"
    legacy_parity_path = tmp_path / ".codex-design" / "product" / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md"
    public_release_experience_path = tmp_path / ".codex-design" / "product" / "PUBLIC_RELEASE_EXPERIENCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    external_proof_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    active_shards_path = tmp_path / "state" / "chummer_design_supervisor" / "active_shards.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    flagship_bar_path.parent.mkdir(parents=True, exist_ok=True)
    flagship_bar_path.write_text("Install and first-run experience must feel like one product.\n", encoding="utf-8")
    horizons_overview_path.write_text("# Horizons\n", encoding="utf-8")
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "FOUNDATIONS.md",
        "README.md",
        "alice.md",
        "edition-studio.md",
        "ghostwire.md",
        "jackpoint.md",
        "karma-forge.md",
        "knowledge-fabric.md",
        "local-co-processor.md",
        "nexus-pan.md",
        "onramp.md",
        "quicksilver.md",
        "run-control.md",
        "runbook-press.md",
        "runsite.md",
        "table-pulse.md",
    ):
        (horizons_dir / name).write_text(f"# {name}\n", encoding="utf-8")
    surface_design_review_loop_path.write_text("# Surface Design\n", encoding="utf-8")
    familiarity_bridge_path.write_text("# Familiarity\n", encoding="utf-8")
    desktop_executable_exit_gates_path.write_text("# Desktop Exit Gates\n", encoding="utf-8")
    legacy_parity_path.write_text("# Legacy parity\n", encoding="utf-8")
    _write_yaml(public_release_experience_path, {"flagship_release_rules": ["guided Chummer product installer path first"]})
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "blocked",
                "blocked_count": 2,
                "blocked_external_only_count": 1,
                "blocked_with_local_count": 1,
            },
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "blocked",
                    "blocked_by_external_constraints_only": False,
                    "external_proof_requests": [
                        {
                            "tuple_id": "avalonia:osx-arm64:macos",
                            "required_host": "macos",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ],
                    "external_blocking_reasons": [
                        "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' external proof request: capture promoted_installer_artifact, startup_smoke_receipt on macos host for tuple avalonia:osx-arm64:macos."
                    ],
                    "local_blocking_reasons": [
                        "repo proof chummer6-ui:.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json field 'local_blocking_findings_count' expected 0 but was 22.",
                    ],
                    "owner_repos": ["chummer6-ui"],
                },
                {"id": "build_explain_publish", "state": "ready"},
                {"id": "campaign_session_recover_recap", "state": "ready"},
                {"id": "recover_from_sync_conflict", "state": "ready"},
                {
                    "id": "report_cluster_release_notify",
                    "state": "blocked",
                    "blocked_by_external_constraints_only": True,
                    "external_proof_requests": [
                        {
                            "tuple_id": "avalonia:osx-arm64:macos",
                            "required_host": "macos",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ],
                    "external_blocking_reasons": [
                        "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' external proof request: capture promoted_installer_artifact, startup_smoke_receipt on macos host for tuple avalonia:osx-arm64:macos."
                    ],
                    "local_blocking_reasons": [],
                },
            ],
        },
    )
    _write_json(
        support_packets_path,
        {
            "generated_at": current_iso,
            "summary": {
                "open_packet_count": 1,
                "unresolved_external_proof_request_count": 1,
                "closure_waiting_on_release_truth": 0,
                "update_required_misrouted_case_count": 0,
                "non_external_needs_human_response": 0,
                "non_external_packets_without_named_owner": 0,
                "non_external_packets_without_lane": 0,
            },
        },
    )
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        external_proof_runbook_path,
        external_proof_runbook_path.parent / "external-proof-commands",
        current_iso,
    )
    _write_json(
        supervisor_state_path,
        {
            "updated_at": current_iso,
            "mode": "sharded",
            "focus_profiles": ["top_flagship_grade", "whole_project_frontier"],
            "completion_audit": {"status": "fail"},
        },
    )
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "failed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "fail",
            "generated_at": current_iso,
            "local_blocking_findings_count": 1,
            "local_blocking_findings": [
                "Linux installer proof is missing install_launch_capture_path for promoted head 'avalonia'."
            ],
            "reasons": [
                "Linux installer proof is missing install_launch_capture_path for promoted head 'avalonia'."
            ],
            "evidence": {
                "ui_executable_exit_gate_path": str(ui_executable_exit_gate_path),
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "channelId": "docker",
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": []},
                "missingRequiredPlatforms": ["macos"],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": ["avalonia:macos"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:osx-arm64:macos",
                        "requiredHost": "macos",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    module = _load_module()
    module.materialize_flagship_product_readiness(
        out_path=out_path,
        mirror_path=None,
        acceptance_path=acceptance_path,
        parity_registry_path=tmp_path / "missing-parity.yaml",
        feedback_loop_gate_path=tmp_path / "missing-feedback-loop.yaml",
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        external_proof_runbook_path=external_proof_runbook_path,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_path,
        ui_linux_exit_gate_path=ui_exit_gate_path,
        ui_windows_exit_gate_path=ui_windows_exit_gate_path,
        ui_workflow_parity_proof_path=ui_workflow_parity_path,
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        ui_localization_release_gate_path=tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
        sr4_workflow_parity_proof_path=sr4_workflow_parity_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_path,
        mobile_local_release_proof_path=mobile_local_release_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ignore_nonlinux_desktop_host_proof_blockers=False,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    fleet_evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert fleet_evidence["journey_overall_desktop_scoped_blocked"] is True
    assert fleet_evidence["supervisor_completion_desktop_scoped"] is True


def test_materialize_flagship_product_readiness_prefers_support_execution_plan_action_for_external_only_blockers(
    tmp_path: Path,
) -> None:
    module = _load_module()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "blocked",
                "blocked_count": 1,
                "blocked_external_only_count": 1,
                "blocked_with_local_count": 0,
            },
            "journeys": [
                {
                    "id": "report_cluster_release_notify",
                    "state": "blocked",
                    "blocked_by_external_constraints_only": True,
                    "external_proof_requests": [
                        {
                            "tuple_id": "avalonia:win-x64:windows",
                            "required_host": "windows",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ],
                    "external_blocking_reasons": ["Requires native Windows host proof capture."],
                    "local_blocking_reasons": [],
                },
                {"id": "install_claim_restore_continue", "state": "ready"},
                {"id": "build_explain_publish", "state": "ready"},
                {"id": "campaign_session_recover_recap", "state": "ready"},
                {"id": "recover_from_sync_conflict", "state": "ready"},
            ],
        },
    )
    _write_json(
        support_packets_path,
        {
            "generated_at": "2026-04-01T08:00:00Z",
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-01T08:00:00Z",
                "release_channel_generated_at": "2026-04-01T08:00:00Z",
                "request_count": 1,
                "hosts": ["windows"],
                "recommended_action": (
                    "Only external host-proof gaps remain: windows: transfer "
                    "/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz, "
                    "set CHUMMER_UI_REPO_ROOT and either CHUMMER_EXTERNAL_PROOF_AUTH_HEADER or the signed-in proof "
                    "cookies, run bash /docker/fleet/.codex-studio/published/external-proof-commands/preflight-windows-proof.sh, "
                    "bash /docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.sh, "
                    "bash /docker/fleet/.codex-studio/published/external-proof-commands/validate-windows-proof.sh, "
                    "bash /docker/fleet/.codex-studio/published/external-proof-commands/bundle-windows-proof.sh, "
                    "then return windows-proof-bundle.tgz and ingest it with "
                    "bash /docker/fleet/.codex-studio/published/external-proof-commands/ingest-windows-proof-bundle.sh. "
                    "Use powershell -ExecutionPolicy Bypass -File "
                    "/docker/fleet/.codex-studio/published/external-proof-commands/capture-windows-proof.ps1 if "
                    "Git Bash capture is not available."
                ),
            },
        },
    )
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(ui_windows_exit_gate_path, {"contract_name": "chummer6-ui.windows_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "local_blocking_findings_count": 0,
            "evidence": {},
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "channelId": "preview",
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {"linux": ["avalonia"], "windows": []},
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    module.materialize_flagship_product_readiness(
        out_path=out_path,
        mirror_path=None,
        acceptance_path=acceptance_path,
        parity_registry_path=tmp_path / "missing-parity.yaml",
        feedback_loop_gate_path=tmp_path / "missing-feedback-loop.yaml",
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        external_proof_runbook_path=None,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_path,
        ui_linux_exit_gate_path=ui_exit_gate_path,
        ui_windows_exit_gate_path=ui_windows_exit_gate_path,
        ui_workflow_parity_proof_path=ui_workflow_parity_path,
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        ui_localization_release_gate_path=tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
        sr4_workflow_parity_proof_path=sr4_workflow_parity_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_path,
        mobile_local_release_proof_path=mobile_local_release_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ignore_nonlinux_desktop_host_proof_blockers=False,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["external_host_proof"]["status"] == "fail"
    assert payload["external_host_proof"]["reason"].startswith(
        "Only external host-proof gaps remain: windows: transfer "
        "/docker/fleet/.codex-studio/published/external-proof-commands/windows-proof-command-pack.tgz"
    )
    assert "capture-windows-proof.sh" in payload["external_host_proof"]["reason"]


def test_journey_local_reason_is_desktop_scoped_for_executable_gate_marker_contract_rows() -> None:
    module = _load_module()

    assert module._journey_local_reason_is_desktop_scoped(
        {
            "reason": (
                "repo proof chummer6-ui:.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json "
                "is missing required marker '\"local_blocking_findings_count\": 0'."
            ),
            "category_id": "",
            "evidence_path": "",
        }
    )
    assert module._journey_local_reason_is_desktop_scoped(
        {
            "reason": (
                "repo proof chummer6-ui:.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json "
                "field 'evidence.receipt_scope.linux_gate:blazor-desktop:linux-x64.within_repo_root' expected True but was None."
            ),
            "category_id": "",
            "evidence_path": "",
        }
    )


def test_materialize_flagship_product_readiness_allows_ooda_supervisor_fallback_to_current_supervisor_loop(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    flagship_bar_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_BAR.md"
    horizons_overview_path = tmp_path / ".codex-design" / "product" / "HORIZONS.md"
    horizons_dir = tmp_path / ".codex-design" / "product" / "horizons"
    surface_design_review_loop_path = tmp_path / ".codex-design" / "product" / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md"
    familiarity_bridge_path = tmp_path / ".codex-design" / "product" / "CHUMMER5A_FAMILIARITY_BRIDGE.md"
    desktop_executable_exit_gates_path = tmp_path / ".codex-design" / "product" / "DESKTOP_EXECUTABLE_EXIT_GATES.md"
    legacy_parity_path = tmp_path / ".codex-design" / "product" / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md"
    public_release_experience_path = tmp_path / ".codex-design" / "product" / "PUBLIC_RELEASE_EXPERIENCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    external_proof_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    flagship_bar_path.parent.mkdir(parents=True, exist_ok=True)
    flagship_bar_path.write_text("Install and first-run experience must feel like one product.\n", encoding="utf-8")
    horizons_overview_path.write_text("# Horizons\n", encoding="utf-8")
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "FOUNDATIONS.md",
        "README.md",
        "alice.md",
        "edition-studio.md",
        "ghostwire.md",
        "jackpoint.md",
        "karma-forge.md",
        "knowledge-fabric.md",
        "local-co-processor.md",
        "nexus-pan.md",
        "onramp.md",
        "quicksilver.md",
        "run-control.md",
        "runbook-press.md",
        "runsite.md",
        "table-pulse.md",
    ):
        (horizons_dir / name).write_text(f"# {name}\n", encoding="utf-8")
    surface_design_review_loop_path.write_text("# Surface Design\n", encoding="utf-8")
    familiarity_bridge_path.write_text("# Familiarity\n", encoding="utf-8")
    desktop_executable_exit_gates_path.write_text("# Desktop Exit Gates\n", encoding="utf-8")
    legacy_parity_path.write_text("# Legacy parity\n", encoding="utf-8")
    _write_yaml(public_release_experience_path, {"flagship_release_rules": ["guided Chummer product installer path first"]})
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "ready",
                "blocked_count": 0,
                "blocked_external_only_count": 0,
                "blocked_with_local_count": 0,
            },
            "journeys": [
                {"id": "install_claim_restore_continue", "state": "ready"},
                {"id": "build_explain_publish", "state": "ready"},
                {"id": "campaign_session_recover_recap", "state": "ready"},
                {"id": "recover_from_sync_conflict", "state": "ready"},
                {"id": "report_cluster_release_notify", "state": "ready"},
            ],
        },
    )
    _write_json(
        support_packets_path,
        {
            "generated_at": current_iso,
            "summary": {
                "open_packet_count": 0,
                "unresolved_external_proof_request_count": 0,
                "closure_waiting_on_release_truth": 0,
                "update_required_misrouted_case_count": 0,
                "non_external_needs_human_response": 0,
                "non_external_packets_without_named_owner": 0,
                "non_external_packets_without_lane": 0,
            },
        },
    )
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        external_proof_runbook_path,
        external_proof_runbook_path.parent / "external-proof-commands",
        current_iso,
    )
    _write_json(
        supervisor_state_path,
        {
            "updated_at": current_iso,
            "mode": "sharded",
            "focus_profiles": ["top_flagship_grade", "whole_project_frontier"],
            "completion_audit": {"status": "pass"},
        },
    )
    _write_json(
        ooda_state_path,
        {
            "controller": "up",
            "aggregate_stale": False,
            "aggregate_timestamp_stale": False,
        },
    )
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "failed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "generated_at": current_iso,
            "local_blocking_findings_count": 0,
            "local_blocking_findings": [],
            "reasons": [],
            "evidence": {
                "ui_executable_exit_gate_path": str(ui_executable_exit_gate_path),
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
                "desktop_familiarity": {
                    "file_menu_live": True,
                    "master_index_first_class": True,
                    "character_roster_first_class": True,
                    "startup_opens_workbench_not_landing": True,
                },
                "install_experience": {
                    "manual_browser_claim_code_required": False,
                    "claim_flow_surface": "installer_or_in_app",
                    "product_installer_guides_head_choice": True,
                },
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "channelId": "docker",
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {"linux": ["avalonia"], "windows": ["avalonia"], "macos": ["avalonia"]},
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "macos", "rid": "osx-arm64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    module = _load_module()
    module.materialize_flagship_product_readiness(
        out_path=out_path,
        mirror_path=None,
        acceptance_path=acceptance_path,
        parity_registry_path=tmp_path / "missing-parity.yaml",
        feedback_loop_gate_path=tmp_path / "missing-feedback-loop.yaml",
        status_plane_path=status_plane_path,
        progress_report_path=progress_report_path,
        progress_history_path=progress_history_path,
        journey_gates_path=journey_gates_path,
        support_packets_path=support_packets_path,
        external_proof_runbook_path=external_proof_runbook_path,
        supervisor_state_path=supervisor_state_path,
        ooda_state_path=ooda_state_path,
        ui_local_release_proof_path=ui_local_release_path,
        ui_linux_exit_gate_path=ui_exit_gate_path,
        ui_windows_exit_gate_path=ui_windows_exit_gate_path,
        ui_workflow_parity_proof_path=ui_workflow_parity_path,
        ui_executable_exit_gate_path=ui_executable_exit_gate_path,
        ui_workflow_execution_gate_path=ui_workflow_execution_gate_path,
        ui_visual_familiarity_exit_gate_path=ui_visual_familiarity_exit_gate_path,
        ui_localization_release_gate_path=tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json",
        sr4_workflow_parity_proof_path=sr4_workflow_parity_path,
        sr6_workflow_parity_proof_path=sr6_workflow_parity_path,
        sr4_sr6_frontier_receipt_path=sr4_sr6_frontier_receipt_path,
        hub_local_release_proof_path=hub_local_release_path,
        mobile_local_release_proof_path=mobile_local_release_path,
        release_channel_path=release_channel_path,
        releases_json_path=releases_json_path,
        ignore_nonlinux_desktop_host_proof_blockers=False,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    fleet_evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    assert fleet_evidence["ooda_controller"] == "up"
    assert fleet_evidence["ooda_supervisor"] == ""


def test_materialize_flagship_product_readiness_requires_explicit_workflow_parity_proof(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(tmp_path / "ui" / "missing-parity.json"),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] in {"warning", "missing"}
    assert "Chummer5a desktop workflow parity proof is missing or not passed." in " ".join(payload["coverage_details"]["desktop_client"]["reasons"])


def test_materialize_flagship_product_readiness_requires_executable_desktop_receipts(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] in {"warning", "missing"}
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Executable desktop exit gate proof is missing or not passed." in reasons
    assert "Executable desktop workflow execution gate proof is missing or not passed." in reasons


def test_materialize_flagship_product_readiness_uses_explicit_executable_receipt_paths(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui-a" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui-a" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui-a" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui-a" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    wrong_sibling_executable_path = tmp_path / "ui-a" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    wrong_sibling_workflow_execution_path = tmp_path / "ui-a" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    wrong_sibling_visual_familiarity_path = tmp_path / "ui-a" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    explicit_executable_path = tmp_path / "ui-b" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    explicit_workflow_execution_path = tmp_path / "ui-b" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    explicit_visual_familiarity_path = tmp_path / "ui-b" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui-b" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui-b" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui-b" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(wrong_sibling_executable_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "fail"})
    _write_json(wrong_sibling_workflow_execution_path, {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "fail"})
    _write_json(wrong_sibling_visual_familiarity_path, {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "fail"})
    _write_json(
        explicit_executable_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "macos_statuses": {
                    "avalonia:osx-arm64": "pass",
                }
            },
        },
    )
    _write_json(explicit_workflow_execution_path, {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"})
    _write_json(explicit_visual_familiarity_path, {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
                "artifacts": [
                    {"head": "avalonia", "platform": "linux", "kind": "installer"},
                    {"head": "avalonia", "platform": "windows", "kind": "installer"},
                    {"head": "avalonia", "platform": "macos", "kind": "installer"},
                ],
            },
        )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(explicit_executable_path),
            "--ui-workflow-execution-gate",
            str(explicit_workflow_execution_path),
            "--ui-visual-familiarity-exit-gate",
            str(explicit_visual_familiarity_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_exit_gate_status"] == "pass"
    assert evidence["ui_executable_exit_gate_path"] == str(explicit_executable_path)
    assert evidence["ui_workflow_execution_gate_status"] == "pass"
    assert evidence["ui_workflow_execution_gate_path"] == str(explicit_workflow_execution_path)
    assert evidence["ui_workflow_execution_gate_family_missing_receipt_count"] == 0
    assert evidence["ui_workflow_execution_gate_family_failing_receipt_count"] == 0
    assert evidence["ui_workflow_execution_gate_execution_missing_receipt_count"] == 0
    assert evidence["ui_workflow_execution_gate_execution_failing_receipt_count"] == 0
    assert evidence["ui_workflow_execution_gate_execution_weak_receipt_count"] == 0
    assert evidence["ui_workflow_execution_gate_unresolved_receipt_count"] == 0
    assert evidence["ui_workflow_execution_gate_unresolved_receipts"] == []
    assert evidence["ui_visual_familiarity_exit_gate_status"] == "pass"
    assert evidence["ui_visual_familiarity_exit_gate_path"] == str(explicit_visual_familiarity_path)


def test_materialize_flagship_product_readiness_requires_macos_tuple_proof_when_macos_installer_is_public(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "kind": "installer"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Release channel publishes macOS installer media" in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["release_channel_has_macos_public_installer"] is True
    assert evidence["ui_executable_gate_macos_tuple_count"] == 1
    assert evidence["ui_executable_gate_macos_passing_tuple_count"] == 0


def test_materialize_flagship_product_readiness_requires_windows_tuple_proof_for_nondefault_promoted_head(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64"},
                {"head": "blazor-desktop", "platform": "windows", "kind": "installer", "rid": "win-x64"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Release channel publishes Windows installer media, but executable-gate evidence is missing passing Windows startup-smoke tuple proof." in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["release_channel_windows_promoted_tuples"] == ["blazor-desktop:win-x64"]
    assert evidence["ui_executable_gate_windows_tuple_count"] == 1
    assert evidence["ui_executable_gate_windows_passing_tuple_count"] == 0
    assert evidence["ui_executable_gate_windows_missing_or_failing_keys"] == ["blazor-desktop:win-x64"]


def test_materialize_flagship_product_readiness_fail_closes_stale_windows_promoted_tuple_proof(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"blazor-desktop:win-x64": "stale"},
                "macos_statuses": {},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
                "heads_requiring_flagship_proof": ["avalonia", "blazor-desktop"],
                "visual_familiarity_head_proofs": {"avalonia": "pass", "blazor-desktop": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass", "blazor-desktop": "pass"},
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64"},
                {"head": "blazor-desktop", "platform": "windows", "kind": "installer", "rid": "win-x64"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Release channel publishes Windows installer media, but executable-gate startup-smoke tuple proof is stale for tuple(s): blazor-desktop:win-x64."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_windows_stale_promoted_tuple_keys"] == ["blazor-desktop:win-x64"]
    assert evidence["ui_executable_gate_windows_missing_or_failing_keys"] == [
        "avalonia:windows",
        "blazor-desktop:win-x64",
    ]


def test_materialize_flagship_product_readiness_fail_closes_windows_artifact_channel_mismatch(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "docker"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Release channel publishes Windows installer media with artifact channel metadata that does not match top-level channelId." in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["release_channel_id"] == "preview"
    assert evidence["release_channel_windows_channel_mismatch_keys"] == ["avalonia:win-x64"]
    assert evidence["release_channel_linux_channel_mismatch_keys"] == []


def test_materialize_flagship_product_readiness_fail_closes_duplicate_windows_installer_tuples(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "heads_requiring_flagship_proof": ["avalonia"],
                "visual_familiarity_required_desktop_heads": ["avalonia"],
                "workflow_execution_required_desktop_heads": ["avalonia"],
                "visual_familiarity_head_proofs": {"avalonia": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass"},
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "docker",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "docker"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "docker", "fileName": "a.exe"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "docker", "fileName": "b.exe"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Release channel publishes duplicate Windows installer tuple metadata for promoted head/rid pair(s): avalonia:win-x64." in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["release_channel_windows_duplicate_tuple_keys"] == ["avalonia:win-x64"]
    assert evidence["release_channel_linux_duplicate_tuple_keys"] == []
    assert evidence["release_channel_macos_duplicate_tuple_keys"] == []


def test_materialize_flagship_product_readiness_fail_closes_missing_required_head_promoted_tuples(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "promoted_desktop_heads": ["avalonia", "blazor-desktop"],
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Release channel is missing promoted installer tuple proof for required desktop head(s): blazor-desktop."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_required_promoted_heads"] == ["avalonia", "blazor-desktop"]
    assert evidence["release_channel_promoted_tuple_heads"] == ["avalonia"]
    assert evidence["release_channel_missing_required_head_tuples"] == ["blazor-desktop"]


def test_materialize_flagship_product_readiness_prefers_flagship_required_head_inventory_for_tuple_gaps(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "promoted_desktop_heads": ["avalonia"],
                "flagship_required_desktop_heads": ["avalonia", "blazor-desktop"],
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Release channel is missing promoted installer tuple proof for required desktop head(s): blazor-desktop." in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_required_promoted_heads"] == ["avalonia", "blazor-desktop"]
    assert evidence["release_channel_promoted_tuple_heads"] == ["avalonia"]
    assert evidence["release_channel_missing_required_head_tuples"] == ["blazor-desktop"]


def test_materialize_flagship_product_readiness_fail_closes_missing_required_platform_head_pairs(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia", "blazor-desktop"],
                "visual_familiarity_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "workflow_execution_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "visual_familiarity_head_proofs": {"avalonia": "pass", "blazor-desktop": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass", "blazor-desktop": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass", "blazor-desktop:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass", "blazor-desktop:win-x64": "pass"},
                "macos_statuses": {"blazor-desktop:osx-arm64": "pass"},
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "rolloutState": "coverage_incomplete",
            "supportabilityState": "review_required",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "blazor-desktop", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "blazor-desktop", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "blazor-desktop", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia", "blazor-desktop"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia", "blazor-desktop"],
                    "windows": ["avalonia", "blazor-desktop"],
                    "macos": ["blazor-desktop"],
                },
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": ["avalonia:macos"],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Release channel is missing required desktop platform/head installer tuple pair(s): avalonia:macos."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["release_channel_required_tuple_platforms"] == ["linux", "macos", "windows"]
    assert evidence["release_channel_required_tuple_heads"] == ["avalonia", "blazor-desktop"]
    assert evidence["release_channel_missing_required_platform_head_pairs"] == ["avalonia:macos"]
    assert evidence["release_channel_missing_required_platform_head_pairs_derived"] == ["avalonia:macos"]
    assert evidence["ui_executable_gate_linux_missing_or_failing_keys"] == []
    assert evidence["ui_executable_gate_windows_missing_or_failing_keys"] == []
    assert evidence["ui_executable_gate_macos_missing_or_failing_keys"] == ["avalonia:macos"]
    assert evidence["release_channel_missing_required_platforms_derived"] == []
    assert evidence["release_channel_missing_required_heads_derived"] == []
    assert evidence["release_channel_tuple_coverage_reported_missing_required_platforms"] == []
    assert evidence["release_channel_tuple_coverage_reported_missing_required_heads"] == []
    assert evidence["release_channel_tuple_coverage_missing_platform_inventory_mismatch"] == []
    assert evidence["release_channel_tuple_coverage_missing_head_inventory_mismatch"] == []
    assert evidence["release_channel_rollout_state"] == "coverage_incomplete"
    assert evidence["release_channel_supportability_state"] == "review_required"
    assert evidence["release_channel_tuple_coverage_missing_pair_inventory_mismatch"] == []


def test_materialize_flagship_product_readiness_surfaces_missing_platform_head_pairs_in_platform_tuple_proof_gaps(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia", "blazor-desktop"],
                "visual_familiarity_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "workflow_execution_required_desktop_heads": ["avalonia", "blazor-desktop"],
                "visual_familiarity_head_proofs": {"avalonia": "pass", "blazor-desktop": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass", "blazor-desktop": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass", "blazor-desktop:linux-x64": "pass"},
                "windows_statuses": {},
                "macos_statuses": {},
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "rolloutState": "coverage_incomplete",
            "supportabilityState": "review_required",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "blazor-desktop", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia", "blazor-desktop"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia", "blazor-desktop"],
                    "windows": [],
                    "macos": [],
                },
                "missingRequiredPlatforms": ["macos", "windows"],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [
                    "avalonia:windows",
                    "blazor-desktop:windows",
                    "avalonia:macos",
                    "blazor-desktop:macos",
                ],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_linux_missing_or_failing_keys"] == []
    assert evidence["ui_executable_gate_windows_missing_or_failing_keys"] == [
        "avalonia:windows",
        "blazor-desktop:windows",
    ]
    assert evidence["ui_executable_gate_macos_missing_or_failing_keys"] == [
        "avalonia:macos",
        "blazor-desktop:macos",
    ]


def test_materialize_flagship_product_readiness_fail_closes_stale_passing_non_promoted_platform_gate_receipts(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia"],
                "visual_familiarity_required_desktop_heads": ["avalonia"],
                "workflow_execution_required_desktop_heads": ["avalonia"],
                "visual_familiarity_head_proofs": {"avalonia": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "macos_statuses": {"avalonia:osx-arm64": "pass"},
                "stale_windows_gate_receipts_without_promoted_tuples": [
                    {
                        "path": str(tmp_path / "ui" / "UI_WINDOWS_AVALONIA_WIN_ARM64_DESKTOP_EXIT_GATE.generated.json"),
                        "tuple": "avalonia:win-arm64",
                        "status": "pass",
                    }
                ],
                "stale_macos_gate_receipts_without_promoted_tuples": [],
                "stale_passing_platform_gate_receipts_without_promoted_tuples": ["windows:avalonia:win-arm64"],
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "rolloutState": "complete",
            "supportabilityState": "healthy",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia"],
                    "windows": ["avalonia"],
                    "macos": ["avalonia"],
                },
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Executable gate reports stale passing platform gate receipts for non-promoted desktop tuples: windows:avalonia:win-arm64."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_stale_windows_gate_receipts_without_promoted_tuples"] == [
        {
            "path": str(tmp_path / "ui" / "UI_WINDOWS_AVALONIA_WIN_ARM64_DESKTOP_EXIT_GATE.generated.json"),
            "tuple": "avalonia:win-arm64",
            "status": "pass",
        }
    ]
    assert evidence["ui_executable_gate_stale_macos_gate_receipts_without_promoted_tuples"] == []
    assert evidence["ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples"] == [
        "windows:avalonia:win-arm64"
    ]


def test_materialize_flagship_product_readiness_fail_closes_stale_linux_non_promoted_platform_gate_receipts(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia"],
                "visual_familiarity_required_desktop_heads": ["avalonia"],
                "workflow_execution_required_desktop_heads": ["avalonia"],
                "visual_familiarity_head_proofs": {"avalonia": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "macos_statuses": {"avalonia:osx-arm64": "pass"},
                "stale_linux_gate_receipts_without_promoted_tuples": [
                    {
                        "path": str(tmp_path / "ui" / "UI_LINUX_AVALONIA_LINUX_ARM64_DESKTOP_EXIT_GATE.generated.json"),
                        "tuple": "avalonia:linux-arm64",
                        "status": "pass",
                    }
                ],
                "stale_windows_gate_receipts_without_promoted_tuples": [],
                "stale_macos_gate_receipts_without_promoted_tuples": [],
                "stale_passing_platform_gate_receipts_without_promoted_tuples": ["linux:avalonia:linux-arm64"],
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "rolloutState": "complete",
            "supportabilityState": "healthy",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia"],
                    "windows": ["avalonia"],
                    "macos": ["avalonia"],
                },
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Executable gate reports stale passing platform gate receipts for non-promoted desktop tuples: linux:avalonia:linux-arm64."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_stale_linux_gate_receipts_without_promoted_tuples"] == [
        {
            "path": str(tmp_path / "ui" / "UI_LINUX_AVALONIA_LINUX_ARM64_DESKTOP_EXIT_GATE.generated.json"),
            "tuple": "avalonia:linux-arm64",
            "status": "pass",
        }
    ]
    assert evidence["ui_executable_gate_stale_linux_gate_receipt_tuple_keys_without_promoted_tuples"] == [
        "avalonia:linux-arm64"
    ]
    assert evidence["ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples"] == [
        "linux:avalonia:linux-arm64"
    ]


def test_materialize_flagship_product_readiness_fail_closes_stale_passing_inventory_mismatch(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia"],
                "visual_familiarity_required_desktop_heads": ["avalonia"],
                "workflow_execution_required_desktop_heads": ["avalonia"],
                "visual_familiarity_head_proofs": {"avalonia": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "macos_statuses": {"avalonia:osx-arm64": "pass"},
                "stale_windows_gate_receipts_without_promoted_tuples": [
                    {
                        "path": str(tmp_path / "ui" / "UI_WINDOWS_AVALONIA_WIN_ARM64_DESKTOP_EXIT_GATE.generated.json"),
                        "tuple": "avalonia:win-arm64",
                        "status": "pass",
                    }
                ],
                "stale_macos_gate_receipts_without_promoted_tuples": [],
                "stale_passing_platform_gate_receipts_without_promoted_tuples": [],
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "rolloutState": "complete",
            "supportabilityState": "healthy",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia"],
                    "windows": ["avalonia"],
                    "macos": ["avalonia"],
                },
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Executable gate stale passing non-promoted tuple inventory does not match stale receipt status rows." in reasons
    assert (
        "Executable gate reports stale passing platform gate receipts for non-promoted desktop tuples: windows:avalonia:win-arm64."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples"] == []
    assert evidence["ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples_derived"] == [
        "windows:avalonia:win-arm64"
    ]
    assert evidence["ui_executable_gate_stale_passing_platform_gate_receipts_without_promoted_tuples_mismatch"] == [
        "windows:avalonia:win-arm64"
    ]


def test_materialize_flagship_product_readiness_fail_closes_stale_non_promoted_inventory_overlapping_promoted_tuples(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia"],
                "visual_familiarity_required_desktop_heads": ["avalonia"],
                "workflow_execution_required_desktop_heads": ["avalonia"],
                "visual_familiarity_head_proofs": {"avalonia": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "macos_statuses": {"avalonia:osx-arm64": "pass"},
                "stale_windows_gate_receipts_without_promoted_tuples": [
                    {
                        "path": str(tmp_path / "ui" / "UI_WINDOWS_AVALONIA_WIN_X64_DESKTOP_EXIT_GATE.generated.json"),
                        "tuple": "avalonia:win-x64",
                        "status": "failed",
                    }
                ],
                "stale_macos_gate_receipts_without_promoted_tuples": [],
                "stale_passing_platform_gate_receipts_without_promoted_tuples": [],
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "rolloutState": "complete",
            "supportabilityState": "healthy",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia"],
                    "windows": ["avalonia"],
                    "macos": ["avalonia"],
                },
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Executable gate stale Windows non-promoted tuple inventory overlaps promoted release-channel tuples: avalonia:win-x64."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_stale_windows_gate_receipt_tuple_keys_without_promoted_tuples"] == [
        "avalonia:win-x64"
    ]
    assert evidence["ui_executable_gate_stale_windows_receipt_tuples_overlapping_promoted_tuples"] == [
        "avalonia:win-x64"
    ]


def test_materialize_flagship_product_readiness_fail_closes_unbound_executable_gate_trusted_roots(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia"],
                "visual_familiarity_required_desktop_heads": ["avalonia"],
                "workflow_execution_required_desktop_heads": ["avalonia"],
                "visual_familiarity_head_proofs": {"avalonia": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "macos_statuses": {"avalonia:osx-arm64": "pass"},
                "trusted_local_roots": [str(tmp_path / "ui"), str(tmp_path / "registry")],
                "hub_registry_root": str(tmp_path / "registry"),
                "hub_registry_release_channel_path": str(tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"),
                "hub_registry_root_trusted_for_startup_smoke_proof": False,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "rolloutState": "complete",
            "supportabilityState": "healthy",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia"],
                    "windows": ["avalonia"],
                    "macos": ["avalonia"],
                },
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert (
        "Executable gate reports expanded trusted startup-smoke roots without canonical hub-registry release-channel binding."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_has_expanded_trusted_local_roots"] is True
    assert evidence["ui_executable_gate_hub_registry_root_trusted_for_startup_smoke_proof"] is False


def test_materialize_flagship_product_readiness_fail_closes_missing_per_head_visual_workflow_inventory(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "generated_at": "2026-04-01T08:00:00Z",
            "evidence": {
                "promoted_desktop_heads": ["avalonia", "blazor-desktop"],
                "linux_statuses": {"avalonia:linux-x64": "pass", "blazor-desktop:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass", "blazor-desktop:win-x64": "pass"},
                "macos_statuses": {
                    "avalonia:osx-arm64": "pass",
                    "blazor-desktop:osx-arm64": "pass",
                },
                "flagship UI release gate proof_age_seconds": 10,
                "desktop visual familiarity gate proof_age_seconds": 10,
                "desktop workflow execution gate proof_age_seconds": 10,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass", "evidence": {}},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass", "evidence": {}},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "preview",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "blazor-desktop", "platform": "linux", "kind": "installer", "rid": "linux-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "blazor-desktop", "platform": "windows", "kind": "installer", "rid": "win-x64", "channel": "preview"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
                {"head": "blazor-desktop", "platform": "macos", "kind": "dmg", "rid": "osx-arm64", "channel": "preview"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Executable gate evidence is missing visual-familiarity required desktop head inventory." in reasons
    assert "Executable gate evidence is missing workflow-execution required desktop head inventory." in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_required_promoted_heads"] == ["avalonia", "blazor-desktop"]
    assert evidence["ui_executable_gate_visual_required_promoted_heads"] == []
    assert evidence["ui_executable_gate_workflow_required_promoted_heads"] == []
    assert evidence["ui_executable_gate_visual_missing_required_inventory_heads"] == ["avalonia", "blazor-desktop"]
    assert evidence["ui_executable_gate_workflow_missing_required_inventory_heads"] == ["avalonia", "blazor-desktop"]
    assert evidence["ui_executable_gate_visual_missing_or_failing_head_proofs"] == ["avalonia", "blazor-desktop"]
    assert evidence["ui_executable_gate_workflow_missing_or_failing_head_proofs"] == ["avalonia", "blazor-desktop"]


def test_materialize_flagship_product_readiness_surfaces_executable_gate_blockers(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "fail",
            "reasons": [
                "Windows desktop exit gate is missing or not passing.",
                "macOS startup smoke receipt path is missing or unreadable for promoted head 'avalonia' (osx-x64).",
            ],
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert "Executable gate blocker: Windows desktop exit gate is missing or not passing." in reasons
    assert (
        "Executable gate blocker: macOS startup smoke receipt path is missing or unreadable for promoted head 'avalonia' (osx-x64)."
        in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_exit_gate_reason_count"] == 2
    assert evidence["ui_executable_exit_gate_reasons"] == [
        "Windows desktop exit gate is missing or not passing.",
        "macOS startup smoke receipt path is missing or unreadable for promoted head 'avalonia' (osx-x64).",
    ]


def test_materialize_flagship_product_readiness_requires_strong_workflow_execution_receipts(tmp_path: Path) -> None:
    module = _load_module()
    current_iso = _now_iso()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        _desktop_executable_exit_gate_pass_payload(
            heads=("avalonia",),
            platforms=("linux", "windows", "macos"),
            generated_at=current_iso,
        ),
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_workflow_execution_gate",
            "status": "pass",
            "evidence": {
                "workflow_family_missing_receipts": [],
                "workflow_family_failing_receipts": [],
                "workflow_execution_missing_receipts": [],
                "workflow_execution_failing_receipts": [],
                "workflow_execution_weak_receipts": ["sr4::dense-workbench"],
            },
        },
    )
    _write_json(ui_visual_familiarity_exit_gate_path, _desktop_visual_familiarity_pass_payload(module))
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia",),
            platforms=("linux", "windows", "macos"),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "ready"
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Executable desktop workflow execution gate reports unresolved family/execution receipt drift" not in reasons
    assert "Executable desktop workflow execution gate is limited by SR4/SR6 workflow-oracle backlog" not in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_workflow_execution_gate_execution_weak_receipt_count"] == 1
    assert evidence["ui_workflow_execution_gate_unresolved_receipt_count"] == 1
    assert evidence["ui_workflow_execution_gate_unresolved_receipts"] == ["sr4::dense-workbench"]


def test_user_journey_tester_audit_requires_visible_focus_and_new_character_workflows() -> None:
    module = _load_module()

    gaps = module.user_journey_tester_audit_gaps(
        {
            "contract_name": "chummer6-ui.user_journey_tester_audit",
            "status": "pass",
            "evidence": {
                "linux_binary_under_test": True,
                "used_internal_apis": False,
                "fix_shard_separate": True,
                "open_blocking_findings_count": 0,
                "workflows": [
                    {
                        "id": "master_index_search_focus_stability",
                        "status": "pass",
                        "screenshots": ["before.png"],
                    }
                ],
            },
        }
    )

    assert gaps["ready"] is False
    assert "file_new_character_visible_workspace" in gaps["missing_workflows"]
    assert gaps["insufficient_screenshot_workflows"] == ["master_index_search_focus_stability"]


def test_materialize_flagship_product_readiness_requires_user_journey_tester_audit(tmp_path: Path) -> None:
    module = _load_module()

    payload = _materialize_flagship_readiness_with_parity_lab(
        tmp_path,
        module,
        synced_external_runbook=True,
        user_journey_tester_audit_payload={
            "contract_name": "chummer6-ui.user_journey_tester_audit",
            "status": "pass",
            "evidence": {
                "linux_binary_under_test": True,
                "used_internal_apis": False,
                "fix_shard_separate": True,
                "open_blocking_findings_count": 0,
                "workflows": [
                    {
                        "id": "master_index_search_focus_stability",
                        "status": "pass",
                        "screenshots": ["before.png", "after.png"],
                    }
                ],
            },
        },
    )

    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert any("Dedicated user-journey tester audit is missing or not passed" in reason for reason in reasons)
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_user_journey_tester_audit_required"] is True
    assert evidence["ui_user_journey_tester_audit_missing_workflows"] == [
        "file_new_character_visible_workspace",
        "major_navigation_sanity",
        "minimal_character_build_save_reload",
        "validation_or_export_smoke",
    ]


def test_materialize_flagship_product_readiness_requires_windows_payload_integrity_proof(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": False,
                "embedded_sample_marker_present": False,
            },
        },
    )
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_workflow_execution_gate_path, {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"})
    _write_json(ui_visual_familiarity_exit_gate_path, {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"})
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] in {"warning", "missing"}
    assert "Windows desktop exit gate proof is missing, not passed, or lacks embedded payload/sample integrity proof." in " ".join(
        payload["coverage_details"]["desktop_client"]["reasons"]
    )


def test_materialize_flagship_product_readiness_requires_sr4_and_sr6_parity_proofs(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_workflow_execution_gate_path, {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"})
    _write_json(ui_visual_familiarity_exit_gate_path, {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"})
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] in {"warning", "missing"}
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "SR4 desktop workflow parity proof is missing or not passed." in reasons
    assert "SR6 desktop workflow parity proof is missing or not passed." in reasons


def test_materialize_flagship_product_readiness_requires_sr4_sr6_frontier_receipt(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_workflow_execution_gate_path, {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"})
    _write_json(ui_visual_familiarity_exit_gate_path, {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"})
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] in {"warning", "missing"}
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "SR4/SR6 desktop parity frontier receipt is missing or not passed." in reasons


def test_materialize_flagship_product_readiness_requires_windows_public_desktop_proof(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_workflow_execution_gate_path, {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"})
    _write_json(ui_visual_familiarity_exit_gate_path, {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"})
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux", "kind": "installer"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] in {"warning", "missing"}
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Release channel does not publish any promoted Windows installer media." in reasons
    assert "Release channel does not publish any promoted Windows installer media." in reasons


def test_materialize_flagship_product_readiness_fail_closes_unpromoted_desktop_shelf_installers(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "heads_requiring_flagship_proof": ["avalonia"],
                "visual_familiarity_required_desktop_heads": ["avalonia"],
                "workflow_execution_required_desktop_heads": ["avalonia"],
                "visual_familiarity_head_proofs": {"avalonia": "pass"},
                "workflow_execution_head_proofs": {"avalonia": "pass"},
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "macos_statuses": {"avalonia:osx-arm64": "pass"},
                "unpromoted_desktop_shelf_installers": ["chummer-blazor-desktop-win-x64-installer.exe"],
            },
        },
    )
    _write_json(ui_workflow_execution_gate_path, {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"})
    _write_json(ui_visual_familiarity_exit_gate_path, {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"})
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "channelId": "docker",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {
                    "head": "avalonia",
                    "platform": "linux",
                    "rid": "linux-x64",
                    "kind": "installer",
                    "channel": "docker",
                    "fileName": "chummer-avalonia-linux-x64-installer.deb",
                },
                {
                    "head": "avalonia",
                    "platform": "windows",
                    "rid": "win-x64",
                    "kind": "installer",
                    "channel": "docker",
                    "fileName": "chummer-avalonia-win-x64-installer.exe",
                },
                {
                    "head": "avalonia",
                    "platform": "macos",
                    "rid": "osx-arm64",
                    "kind": "dmg",
                    "channel": "docker",
                    "fileName": "chummer-avalonia-osx-arm64-installer.dmg",
                },
            ],
            "desktopTupleCoverage": {
                "requiredDesktopPlatforms": ["linux", "windows", "macos"],
                "requiredDesktopHeads": ["avalonia"],
                "promotedPlatformHeads": {
                    "linux": ["avalonia"],
                    "windows": ["avalonia"],
                    "macos": ["avalonia"],
                },
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
                "missingRequiredPlatformHeadPairs": [],
            },
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Desktop shelf contains installer artifacts not represented in release-channel promoted tuples:" in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_unpromoted_desktop_shelf_installers"] == [
        "chummer-blazor-desktop-win-x64-installer.exe"
    ]


def test_materialize_flagship_product_readiness_refreshes_compile_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    out_path = published / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = repo_root / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(published / "STATUS_PLANE.generated.yaml", {"runtime_healing": {"summary": {"alert_state": "warning"}}, "projects": [], "groups": []})
    _write_json(published / "PROGRESS_REPORT.generated.json", {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 1})
    _write_json(published / "PROGRESS_HISTORY.generated.json", {"snapshot_count": 1})
    _write_json(published / "JOURNEY_GATES.generated.json", {"summary": {"overall_state": "warning"}, "journeys": []})
    _write_json(published / "SUPPORT_CASE_PACKETS.generated.json", {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(repo_root / "state" / "chummer_design_supervisor" / "state.json", _base_supervisor_state())
    _write_json(repo_root / "state" / "design_supervisor_ooda" / "current_8h" / "state.json", _base_ooda_state())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--out",
            str(out_path),
            "--mirror-out",
            str(repo_root / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(published / "STATUS_PLANE.generated.yaml"),
            "--progress-report",
            str(published / "PROGRESS_REPORT.generated.json"),
            "--progress-history",
            str(published / "PROGRESS_HISTORY.generated.json"),
            "--journey-gates",
            str(published / "JOURNEY_GATES.generated.json"),
            "--support-packets",
            str(published / "SUPPORT_CASE_PACKETS.generated.json"),
            "--supervisor-state",
            str(repo_root / "state" / "chummer_design_supervisor" / "state.json"),
            "--ooda-state",
            str(repo_root / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"),
            "--ui-local-release-proof",
            str(repo_root / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(repo_root / "missing-exit.json"),
            "--ui-windows-exit-gate",
            str(repo_root / "missing-ui-windows-exit.json"),
            "--ui-executable-exit-gate",
            str(repo_root / "missing-ui-executable-exit.json"),
            "--ui-workflow-execution-gate",
            str(repo_root / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(repo_root / "missing-ui-visual-familiarity-exit.json"),
            "--ui-localization-release-gate",
            str(repo_root / "missing-ui-localization-release-gate.json"),
            "--ui-workflow-parity-proof",
            str(repo_root / "missing-ui-workflow-parity.json"),
            "--sr4-workflow-parity-proof",
            str(repo_root / "missing-ui-sr4-workflow-parity.json"),
            "--sr6-workflow-parity-proof",
            str(repo_root / "missing-ui-sr6-workflow-parity.json"),
            "--sr4-sr6-frontier-receipt",
            str(repo_root / "missing-ui-sr4-sr6-frontier.json"),
            "--hub-local-release-proof",
            str(repo_root / "missing-hub.json"),
            "--mobile-local-release-proof",
            str(repo_root / "missing-mobile.json"),
            "--release-channel",
            str(repo_root / "missing-channel.json"),
            "--releases-json",
            str(repo_root / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest_payload = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    assert "FLAGSHIP_PRODUCT_READINESS.generated.json" in manifest_payload["artifacts"]


def test_materialize_flagship_product_readiness_requires_desktop_canon_in_design_mirror(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    product_dir = repo_root / ".codex-design" / "product"
    out_path = published / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = product_dir / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = product_dir / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    parity_registry_path = product_dir / "LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(parity_registry_path, {"scope": {"excluded": []}})
    (product_dir / "FLAGSHIP_PRODUCT_BAR.md").parent.mkdir(parents=True, exist_ok=True)
    (product_dir / "FLAGSHIP_PRODUCT_BAR.md").write_text("flagship bar\n", encoding="utf-8")
    (product_dir / "HORIZONS.md").write_text("horizons\n", encoding="utf-8")
    (product_dir / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("bridge\n", encoding="utf-8")
    (product_dir / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("desktop gates\n", encoding="utf-8")
    (product_dir / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("legacy parity\n", encoding="utf-8")
    _write_yaml(product_dir / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"install": {"guided": True}})
    (product_dir / "horizons" / "PLACEHOLDER.md").parent.mkdir(parents=True, exist_ok=True)
    (product_dir / "horizons" / "PLACEHOLDER.md").write_text("placeholder\n", encoding="utf-8")

    _write_yaml(published / "STATUS_PLANE.generated.yaml", _base_status_plane())
    _write_json(published / "PROGRESS_REPORT.generated.json", {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 1})
    _write_json(published / "PROGRESS_HISTORY.generated.json", {"snapshot_count": 1})
    _write_json(published / "JOURNEY_GATES.generated.json", _base_journey_gates())
    _write_json(published / "SUPPORT_CASE_PACKETS.generated.json", {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(repo_root / "state" / "chummer_design_supervisor" / "state.json", _base_supervisor_state())
    _write_json(repo_root / "state" / "design_supervisor_ooda" / "current_8h" / "state.json", _base_ooda_state())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--parity-registry",
            str(parity_registry_path),
            "--status-plane",
            str(published / "STATUS_PLANE.generated.yaml"),
            "--progress-report",
            str(published / "PROGRESS_REPORT.generated.json"),
            "--progress-history",
            str(published / "PROGRESS_HISTORY.generated.json"),
            "--journey-gates",
            str(published / "JOURNEY_GATES.generated.json"),
            "--support-packets",
            str(published / "SUPPORT_CASE_PACKETS.generated.json"),
            "--supervisor-state",
            str(repo_root / "state" / "chummer_design_supervisor" / "state.json"),
            "--ooda-state",
            str(repo_root / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"),
            "--ui-local-release-proof",
            str(repo_root / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(repo_root / "missing-exit.json"),
            "--ui-executable-exit-gate",
            str(repo_root / "missing-ui-executable-exit.json"),
            "--ui-workflow-execution-gate",
            str(repo_root / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(repo_root / "missing-ui-visual-familiarity-exit.json"),
            "--ui-workflow-parity-proof",
            str(repo_root / "missing-ui-workflow-parity.json"),
            "--sr4-workflow-parity-proof",
            str(repo_root / "missing-ui-sr4-workflow-parity.json"),
            "--sr6-workflow-parity-proof",
            str(repo_root / "missing-ui-sr6-workflow-parity.json"),
            "--sr4-sr6-frontier-receipt",
            str(repo_root / "missing-ui-sr4-sr6-frontier.json"),
            "--hub-local-release-proof",
            str(repo_root / "missing-hub.json"),
            "--mobile-local-release-proof",
            str(repo_root / "missing-mobile.json"),
            "--release-channel",
            str(repo_root / "missing-channel.json"),
            "--releases-json",
            str(repo_root / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reasons = payload["coverage_details"]["horizons_and_public_surface"]["reasons"]
    evidence = payload["coverage_details"]["horizons_and_public_surface"]["evidence"]
    assert "Fleet design mirror is missing SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md." in reasons
    assert evidence["surface_design_review_loop_exists"] is False
    assert "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md" in evidence["required_desktop_canon_missing_names"]
    assert evidence["flagship_bar_mirror_path"] == str(product_dir / "FLAGSHIP_PRODUCT_BAR.md")
    assert evidence["horizons_overview_mirror_path"] == str(product_dir / "HORIZONS.md")
    assert evidence["surface_design_review_loop_path"] == str(product_dir / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md")


def test_materialize_flagship_product_readiness_keeps_required_desktop_canon_complete_when_present(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    product_dir = repo_root / ".codex-design" / "product"
    out_path = published / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = product_dir / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = product_dir / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    parity_registry_path = product_dir / "LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(parity_registry_path, {"scope": {"excluded": []}})
    (product_dir / "FLAGSHIP_PRODUCT_BAR.md").parent.mkdir(parents=True, exist_ok=True)
    (product_dir / "FLAGSHIP_PRODUCT_BAR.md").write_text("flagship bar\n", encoding="utf-8")
    (product_dir / "HORIZONS.md").write_text("horizons\n", encoding="utf-8")
    (product_dir / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").write_text("surface review\n", encoding="utf-8")
    (product_dir / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("bridge\n", encoding="utf-8")
    (product_dir / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("desktop gates\n", encoding="utf-8")
    (product_dir / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("legacy parity\n", encoding="utf-8")
    _write_yaml(product_dir / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"install": {"guided": True}})
    (product_dir / "horizons" / "PLACEHOLDER.md").parent.mkdir(parents=True, exist_ok=True)
    (product_dir / "horizons" / "PLACEHOLDER.md").write_text("placeholder\n", encoding="utf-8")

    _write_yaml(published / "STATUS_PLANE.generated.yaml", _base_status_plane())
    _write_json(published / "PROGRESS_REPORT.generated.json", {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 1})
    _write_json(published / "PROGRESS_HISTORY.generated.json", {"snapshot_count": 1})
    _write_json(published / "JOURNEY_GATES.generated.json", _base_journey_gates())
    _write_json(published / "SUPPORT_CASE_PACKETS.generated.json", {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(repo_root / "state" / "chummer_design_supervisor" / "state.json", _base_supervisor_state())
    _write_json(repo_root / "state" / "design_supervisor_ooda" / "current_8h" / "state.json", _base_ooda_state())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--parity-registry",
            str(parity_registry_path),
            "--status-plane",
            str(published / "STATUS_PLANE.generated.yaml"),
            "--progress-report",
            str(published / "PROGRESS_REPORT.generated.json"),
            "--progress-history",
            str(published / "PROGRESS_HISTORY.generated.json"),
            "--journey-gates",
            str(published / "JOURNEY_GATES.generated.json"),
            "--support-packets",
            str(published / "SUPPORT_CASE_PACKETS.generated.json"),
            "--supervisor-state",
            str(repo_root / "state" / "chummer_design_supervisor" / "state.json"),
            "--ooda-state",
            str(repo_root / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"),
            "--ui-local-release-proof",
            str(repo_root / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(repo_root / "missing-exit.json"),
            "--ui-windows-exit-gate",
            str(repo_root / "missing-ui-windows-exit.json"),
            "--ui-executable-exit-gate",
            str(repo_root / "missing-ui-executable-exit.json"),
            "--ui-workflow-execution-gate",
            str(repo_root / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(repo_root / "missing-ui-visual-familiarity-exit.json"),
            "--ui-localization-release-gate",
            str(repo_root / "missing-ui-localization-release-gate.json"),
            "--ui-workflow-parity-proof",
            str(repo_root / "missing-ui-workflow-parity.json"),
            "--sr4-workflow-parity-proof",
            str(repo_root / "missing-ui-sr4-workflow-parity.json"),
            "--sr6-workflow-parity-proof",
            str(repo_root / "missing-ui-sr6-workflow-parity.json"),
            "--sr4-sr6-frontier-receipt",
            str(repo_root / "missing-ui-sr4-sr6-frontier.json"),
            "--hub-local-release-proof",
            str(repo_root / "missing-hub.json"),
            "--mobile-local-release-proof",
            str(repo_root / "missing-mobile.json"),
            "--release-channel",
            str(repo_root / "missing-channel.json"),
            "--releases-json",
            str(repo_root / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    evidence = payload["coverage_details"]["horizons_and_public_surface"]["evidence"]
    reasons = payload["coverage_details"]["horizons_and_public_surface"]["reasons"]
    assert evidence["required_desktop_canon_missing_names"] == []
    assert evidence["surface_design_review_loop_exists"] is True
    assert evidence["chummer5a_familiarity_bridge_exists"] is True
    assert evidence["desktop_executable_exit_gates_exists"] is True
    assert evidence["legacy_client_and_adjacent_parity_exists"] is True
    assert evidence["public_release_experience_exists"] is True
    assert "Fleet design mirror is missing SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md." not in reasons


def test_materialize_flagship_product_readiness_uses_canonical_acceptance_fallback(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    missing_acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"

    canonical_acceptance = Path("/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
    if not canonical_acceptance.is_file():
        return

    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(missing_acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(tmp_path / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(tmp_path / "missing-exit.json"),
            "--ui-executable-exit-gate",
            str(tmp_path / "missing-ui-executable-exit.json"),
            "--ui-workflow-execution-gate",
            str(tmp_path / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(tmp_path / "missing-ui-visual-familiarity-exit.json"),
            "--ui-workflow-parity-proof",
            str(tmp_path / "missing-ui-workflow-parity.json"),
            "--sr4-workflow-parity-proof",
            str(tmp_path / "missing-ui-sr4-workflow-parity.json"),
            "--sr6-workflow-parity-proof",
            str(tmp_path / "missing-ui-sr6-workflow-parity.json"),
            "--sr4-sr6-frontier-receipt",
            str(tmp_path / "missing-ui-sr4-sr6-frontier.json"),
            "--hub-local-release-proof",
            str(tmp_path / "missing-hub.json"),
            "--mobile-local-release-proof",
            str(tmp_path / "missing-mobile.json"),
            "--release-channel",
            str(tmp_path / "missing-channel.json"),
            "--releases-json",
            str(tmp_path / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["evidence_sources"]["acceptance"] == str(canonical_acceptance)
    assert payload["source_documents"]


def test_materialize_flagship_product_readiness_surfaces_unresolved_parity_families_excluding_plugins(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    parity_registry_path = tmp_path / ".codex-design" / "product" / "LEGACY_CLIENT_AND_ADJACENT_PARITY_REGISTRY.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(
        parity_registry_path,
        {
            "scope": {"excluded": ["plugin-framework"]},
            "families": [
                {"id": "legacy_and_adjacent_import_oracles", "status": "partial", "milestone_ids": [17]},
                {"id": "shell_workbench_orientation", "status": "partial", "milestone_ids": [2]},
            ],
        },
    )
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--acceptance",
            str(acceptance_path),
            "--parity-registry",
            str(parity_registry_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(tmp_path / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(tmp_path / "missing-ui-linux.json"),
            "--ui-windows-exit-gate",
            str(tmp_path / "missing-ui-windows.json"),
            "--ui-workflow-parity-proof",
            str(tmp_path / "missing-ui-workflow-parity.json"),
            "--ui-executable-exit-gate",
            str(tmp_path / "missing-ui-executable.json"),
            "--ui-workflow-execution-gate",
            str(tmp_path / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(tmp_path / "missing-ui-visual.json"),
            "--ui-localization-release-gate",
            str(tmp_path / "missing-ui-localization.json"),
            "--sr4-workflow-parity-proof",
            str(tmp_path / "missing-sr4.json"),
            "--sr6-workflow-parity-proof",
            str(tmp_path / "missing-sr6.json"),
            "--sr4-sr6-frontier-receipt",
            str(tmp_path / "missing-frontier.json"),
            "--hub-local-release-proof",
            str(tmp_path / "missing-hub.json"),
            "--mobile-local-release-proof",
            str(tmp_path / "missing-mobile.json"),
            "--release-channel",
            str(tmp_path / "missing-release-channel.json"),
            "--releases-json",
            str(tmp_path / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["parity_registry"]["excluded_scope"] == ["plugin-framework"]
    assert payload["parity_registry"]["unresolved_family_ids"] == [
        "legacy_and_adjacent_import_oracles",
        "shell_workbench_orientation",
    ]
    assert "No-step-back rules/import parity remains unresolved" in "\n".join(
        payload["coverage_details"]["rules_engine_and_import"]["reasons"]
    )


def test_materialize_flagship_product_readiness_keeps_rules_lane_ready_when_build_journey_blockers_are_noncore(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"

    journey_gates = _base_journey_gates()
    for row in journey_gates["journeys"]:
        if row.get("id") == "build_explain_publish":
            row["state"] = "blocked"
            row["blocking_reasons"] = [
                "repo proof file is missing: chummer6-media-factory:src/Chummer.Media.Factory.Runtime/Assets/CreatorPublicationPlannerService.cs.",
            ]
            row["local_blocking_reasons"] = list(row["blocking_reasons"])
            row["external_blocking_reasons"] = []
            row["blocked_by_external_constraints_only"] = False
            break
    journey_gates["summary"]["overall_state"] = "blocked"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, journey_gates)
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(tmp_path / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(tmp_path / "missing-ui-linux.json"),
            "--ui-windows-exit-gate",
            str(tmp_path / "missing-ui-windows.json"),
            "--ui-workflow-parity-proof",
            str(tmp_path / "missing-ui-workflow-parity.json"),
            "--ui-executable-exit-gate",
            str(tmp_path / "missing-ui-executable.json"),
            "--ui-workflow-execution-gate",
            str(tmp_path / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(tmp_path / "missing-ui-visual.json"),
            "--ui-localization-release-gate",
            str(tmp_path / "missing-ui-localization.json"),
            "--sr4-workflow-parity-proof",
            str(tmp_path / "missing-sr4.json"),
            "--sr6-workflow-parity-proof",
            str(tmp_path / "missing-sr6.json"),
            "--sr4-sr6-frontier-receipt",
            str(tmp_path / "missing-frontier.json"),
            "--hub-local-release-proof",
            str(tmp_path / "missing-hub.json"),
            "--mobile-local-release-proof",
            str(tmp_path / "missing-mobile.json"),
            "--release-channel",
            str(tmp_path / "missing-release-channel.json"),
            "--releases-json",
            str(tmp_path / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["rules_engine_and_import"] == "ready"
    assert payload["coverage_details"]["rules_engine_and_import"]["evidence"][
        "build_explain_publish_rules_scope_blocking_reason_count"
    ] == 0


def test_materialize_flagship_product_readiness_accepts_complete_supervisor_mode(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    supervisor_state = _base_supervisor_state()
    supervisor_state["mode"] = "complete"
    _write_json(supervisor_state_path, supervisor_state)
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] in {"ready", "warning"}


def test_materialize_flagship_product_readiness_accepts_hard_focus_successor_wave_operator_proxy(tmp_path: Path) -> None:
    module = _load_module()
    current_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    active_shards_path = tmp_path / "state" / "chummer_design_supervisor" / "active_shards.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md",
        tmp_path / ".codex-studio" / "published" / "external-proof-commands",
        current_iso,
    )
    supervisor_state = _base_supervisor_state()
    supervisor_state["updated_at"] = current_iso
    supervisor_state["mode"] = "successor_wave"
    supervisor_state["completion_audit"] = {}
    supervisor_state["focus_profiles"] = ["top_flagship_grade", "whole_project_frontier"]
    _write_json(supervisor_state_path, supervisor_state)
    _write_json(
        active_shards_path,
        {
            "generated_at": current_iso,
            "manifest_kind": "configured_shard_topology",
            "configured_shard_count": 6,
            "configured_shards": [{"name": "shard-1"}, {"name": "shard-2"}],
            "active_run_count": 0,
            "active_shards": [],
        },
    )
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert evidence["supervisor_mode"] == "successor_wave"
    assert evidence["supervisor_completion_status"] == ""
    assert evidence["supervisor_successor_wave_steering_ready"] is True


def test_materialize_flagship_product_readiness_does_not_crash_without_executable_gate_receipt(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] in {"warning", "missing"}


def test_materialize_flagship_product_readiness_prefers_best_shard_supervisor_state(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    shard_1_state_path = tmp_path / "state" / "chummer_design_supervisor" / "shard-1" / "state.json"
    shard_2_state_path = tmp_path / "state" / "chummer_design_supervisor" / "shard-2" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(
        shard_1_state_path,
        {
            "updated_at": "2026-04-01T08:00:00Z",
            "mode": "completion_review",
            "completion_audit": {"status": "fail"},
        },
    )
    _write_json(
        shard_2_state_path,
        {
            "updated_at": "2026-04-01T09:00:00Z",
            "mode": "flagship_product",
            "completion_audit": {"status": "pass"},
        },
    )
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(shard_1_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] in {"ready", "warning"}
    assert payload["evidence_sources"]["supervisor_state"].endswith("/state.json")


def test_select_best_supervisor_state_keeps_aggregate_preferred_path(tmp_path: Path) -> None:
    module = _load_module()
    aggregate_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    _write_json(
        aggregate_state_path,
        {
            "updated_at": "2026-04-01T09:00:00Z",
            "mode": "flagship_product",
            "completion_audit": {"status": "fail"},
        },
    )

    foreign_root = tmp_path / "foreign-shards"
    _write_json(
        foreign_root / "shard-9" / "state.json",
        {
            "updated_at": "2026-04-01T10:00:00Z",
            "mode": "complete",
            "completion_audit": {"status": "pass"},
        },
    )
    module.DEFAULT_SHARD_SUPERVISOR_ROOT = foreign_root

    selected_path, selected_payload = module._select_best_supervisor_state(aggregate_state_path)

    assert selected_path == aggregate_state_path
    assert selected_payload.get("mode") == "flagship_product"
    assert (selected_payload.get("completion_audit") or {}).get("status") == "fail"


def test_select_best_supervisor_state_falls_back_to_orphaned_aggregate_when_root_missing(tmp_path: Path) -> None:
    module = _load_module()
    aggregate_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    shard_state_path = tmp_path / "state" / "chummer_design_supervisor" / "shard-1" / "state.json"
    orphaned_state_path = tmp_path / "state" / "chummer_design_supervisor" / "orphaned-shard-2" / "state.json"
    module.DEFAULT_SUPERVISOR_STATE = aggregate_state_path
    module.DEFAULT_SHARD_SUPERVISOR_ROOT = aggregate_state_path.parent
    _write_json(
        shard_state_path,
        {
            "updated_at": "2026-04-01T10:00:00Z",
            "active_run": {"started_at": "2026-04-01T10:00:00Z"},
        },
    )
    _write_json(
        orphaned_state_path,
        {
            "updated_at": "2026-04-01T09:00:00Z",
            "mode": "completion_review",
            "completion_audit": {"status": "fail"},
            "focus_profiles": ["top_flagship_grade", "whole_project_frontier"],
        },
    )

    selected_path, selected_payload = module._select_best_supervisor_state(aggregate_state_path)

    assert selected_path == orphaned_state_path
    assert selected_payload.get("mode") == "completion_review"
    assert selected_payload.get("focus_profiles") == ["top_flagship_grade", "whole_project_frontier"]


def test_select_best_supervisor_state_prefers_live_shard_flagship_over_stale_aggregate_completion_review(
    tmp_path: Path,
) -> None:
    module = _load_module()
    aggregate_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    shard_state_path = tmp_path / "state" / "chummer_design_supervisor" / "shard-3" / "state.json"
    module.DEFAULT_SUPERVISOR_STATE = aggregate_state_path
    module.DEFAULT_SHARD_SUPERVISOR_ROOT = aggregate_state_path.parent
    _write_json(
        aggregate_state_path,
        {
            "updated_at": "2026-04-18T17:58:08Z",
            "mode": "completion_review",
            "completion_audit": {"status": "fail"},
            "focus_profiles": ["top_flagship_grade", "whole_project_frontier"],
        },
    )
    _write_json(
        shard_state_path,
        {
            "updated_at": "2026-04-18T18:00:05Z",
            "mode": "flagship_product",
            "completion_audit": {"status": "pass"},
            "focus_profiles": ["top_flagship_grade", "whole_project_frontier"],
            "active_run": {
                "run_id": "20260418T175833Z-shard-3",
                "started_at": "2026-04-18T17:58:33Z",
            },
            "active_runs_count": 1,
        },
    )

    selected_path, selected_payload = module._select_best_supervisor_state(aggregate_state_path)

    assert selected_path == shard_state_path
    assert selected_payload.get("mode") == "flagship_product"
    assert (selected_payload.get("completion_audit") or {}).get("status") == "pass"


def test_materialize_flagship_product_readiness_recovers_supervisor_from_active_shards_and_runtime_profile(tmp_path: Path) -> None:
    module = _load_module()
    current_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    stale_supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "orphaned-shard-14" / "state.json"
    active_shards_path = tmp_path / "state" / "chummer_design_supervisor" / "active_shards.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md",
        tmp_path / ".codex-studio" / "published" / "external-proof-commands",
        current_iso,
    )
    _write_json(
        supervisor_state_path,
        {
            "updated_at": "2026-04-01T07:59:00Z",
            "mode": "successor_wave",
            "completion_audit": {"status": "pass"},
        },
    )
    _write_json(
        stale_supervisor_state_path,
        {
            "updated_at": "2026-04-01T01:00:00Z",
            "mode": "completion_review",
            "completion_audit": {"status": "fail"},
        },
    )
    _write_json(
        active_shards_path,
        {
            "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "manifest_kind": "configured_shard_topology",
            "configured_shard_count": 2,
            "configured_shards": [{"name": "shard-1"}, {"name": "shard-2"}],
            "active_run_count": 0,
            "active_shards": [],
        },
    )
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    env = os.environ.copy()
    env["CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE"] = "top_flagship_grade,whole_project_frontier"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert evidence["supervisor_mode"] == "sharded"
    assert evidence["supervisor_completion_status"] == "pass"
    assert evidence["supervisor_state_recovered_from_active_shards"] is True
    assert evidence["supervisor_focus_profiles_recovered_from_runtime_env"] is True
    assert evidence["supervisor_focus_profiles"] == ["top_flagship_grade", "whole_project_frontier"]
    assert evidence["active_shards_recent"] is True
    assert evidence["active_shards_count"] == 0
    assert evidence["active_shards_manifest_kind"] == "configured_shard_topology"
    assert evidence["configured_shards_count"] == 2
    assert "active_shards_path" not in evidence
    assert "active_shards" not in payload["evidence_sources"]


def test_materialize_flagship_product_readiness_accepts_current_successor_wave_steering_without_completion_audit(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    active_shards_path = tmp_path / "state" / "chummer_design_supervisor" / "active_shards.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md",
        tmp_path / ".codex-studio" / "published" / "external-proof-commands",
        current_iso,
    )
    _write_json(
        supervisor_state_path,
        {
            "updated_at": current_iso,
            "mode": "successor_wave",
            "focus_profiles": ["top_flagship_grade", "whole_project_frontier", "next_90_day_successor_wave"],
            "completion_audit": {"status": "fail", "reason": "latest worker receipt is not trusted"},
        },
    )
    _write_json(
        active_shards_path,
        {
            "generated_at": current_iso,
            "manifest_kind": "configured_shard_topology",
            "configured_shards": [{"name": "shard-1"}, {"name": "shard-2"}],
            "active_run_count": 1,
            "active_shards": [{"name": "shard-1", "active_run_id": "20260417T075253Z-shard-1"}],
        },
    )
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert evidence["supervisor_mode"] == "successor_wave"
    assert evidence["supervisor_completion_status"] == "fail"
    assert evidence["supervisor_successor_wave_steering_ready"] is True


def test_materialize_flagship_product_readiness_accepts_current_completion_review_mode(
    tmp_path: Path,
) -> None:
    current_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    module = _load_module()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md",
        tmp_path / ".codex-studio" / "published" / "external-proof-commands",
        current_iso,
    )
    supervisor_state = _base_supervisor_state()
    supervisor_state["updated_at"] = current_iso
    supervisor_state["mode"] = "completion_review"
    supervisor_state["completion_audit"] = {"status": "pass", "external_only": False}
    supervisor_state["focus_profiles"] = ["top_flagship_grade", "whole_project_frontier"]
    _write_json(supervisor_state_path, supervisor_state)
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        _desktop_executable_exit_gate_pass_payload(
            heads=("avalonia",),
            platforms=("linux",),
            generated_at=current_iso,
        ),
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(ui_visual_familiarity_exit_gate_path, _desktop_visual_familiarity_pass_payload(module))
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(release_channel_path, _release_channel_payload(heads=("avalonia",), platforms=("linux",), generated_at=current_iso))
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert evidence["supervisor_mode"] == "completion_review"
    assert evidence["supervisor_completion_status"] == "pass"
    assert evidence["supervisor_recent_enough"] is True


def test_materialize_flagship_product_readiness_accepts_live_ooda_progress_when_rollup_is_stale(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = _now_iso()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    external_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    external_commands_dir = tmp_path / ".codex-studio" / "published" / "external-proof-commands"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    external_commands_dir.mkdir(parents=True, exist_ok=True)
    (external_commands_dir / "noop-proof.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    command_bundle = module.external_proof_command_bundle_fingerprint(external_commands_dir)
    external_runbook_path.parent.mkdir(parents=True, exist_ok=True)
    external_runbook_path.write_text(
        "\n".join(
            [
                "# External Proof Runbook",
                f"- generated_at: {current_iso}",
                f"- plan_generated_at: {current_iso}",
                f"- release_channel_generated_at: {current_iso}",
                f"- command_bundle_sha256: {command_bundle['sha256']}",
                f"- command_bundle_file_count: {command_bundle['file_count']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    supervisor_state = _base_supervisor_state()
    supervisor_state["updated_at"] = current_iso
    supervisor_state["mode"] = "flagship_product"
    supervisor_state["focus_profiles"] = ["top_flagship_grade", "whole_project_frontier"]
    supervisor_state["completion_audit"] = {"status": "pass"}
    _write_json(supervisor_state_path, supervisor_state)
    _write_json(
        ooda_state_path,
        {
            "controller": "up",
            "supervisor": "up",
            "aggregate_stale": True,
            "aggregate_timestamp_stale": True,
            "active_runs_count": 1,
            "active_shards": [
                {
                    "name": "shard-3",
                    "mode": "flagship_product",
                    "active_run": True,
                    "active_run_id": "20260423T145459Z-shard-3",
                    "worker_last_output_at": current_iso,
                    "updated_at": current_iso,
                }
            ],
        },
    )
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--external-proof-runbook",
            str(external_runbook_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    reasons = payload["coverage_details"]["fleet_and_operator_loop"]["reasons"]
    assert not any("OODA monitor" in reason for reason in reasons)
    assert evidence["ooda_aggregate_stale"] is True
    assert evidence["ooda_timestamp_stale"] is True
    assert evidence["ooda_live_active_progress"] is True


def test_materialize_flagship_product_readiness_accepts_loop_mode_with_last_run_pass_proxy(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    mirror_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    shard_1_state_path = tmp_path / "state" / "chummer_design_supervisor" / "shard-1" / "state.json"
    shard_2_state_path = tmp_path / "state" / "chummer_design_supervisor" / "shard-2" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    missing_ui_receipt_path = tmp_path / "ui" / "missing-receipt.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(
        shard_1_state_path,
        {
            "updated_at": "2026-04-01T09:00:00Z",
            "mode": "loop",
            "completion_audit": {},
        },
    )
    _write_json(
        shard_2_state_path,
        {
            "updated_at": "2026-04-01T08:00:00Z",
            "mode": "loop",
            "completion_audit": {},
            "last_run": {
                "accepted": True,
                "open_milestone_ids": [1, 2, 3],
                "finished_at": "2026-04-01T08:00:00Z",
            },
        },
    )
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [{"head": "avalonia", "platform": "linux"}],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            str(mirror_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(shard_1_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-executable-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-execution-gate",
            str(missing_ui_receipt_path),
            "--ui-visual-familiarity-exit-gate",
            str(missing_ui_receipt_path),
            "--ui-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr6-workflow-parity-proof",
            str(missing_ui_receipt_path),
            "--sr4-sr6-frontier-receipt",
            str(missing_ui_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] in {"ready", "warning"}
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert evidence["supervisor_completion_status"] == "pass"
    assert payload["evidence_sources"]["supervisor_state"].endswith("/state.json")


def test_materialize_flagship_product_readiness_accepts_steady_complete_quiet_ooda(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(
        ooda_state_path,
        {
            "controller": "up",
            "supervisor": "up",
            "aggregate_stale": True,
            "aggregate_timestamp_stale": True,
            "frontier_ids": [],
            "shards": [
                {"name": "shard-1", "mode": "complete", "active_run": False},
                {"name": "shard-2", "mode": "complete", "active_run": False},
            ],
        },
    )
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["fleet_and_operator_loop"] in {"ready", "warning"}
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert evidence["ooda_aggregate_stale"] is True
    assert evidence["ooda_steady_complete_quiet"] is True


def test_recover_ooda_state_from_active_shards_marks_loop_up() -> None:
    module = _load_module()

    payload = module._recover_ooda_state_from_active_shards(
        {
            "active_shards": [
                {"name": "shard-1", "mode": "flagship_product", "active_run": True},
            ],
            "frontier_ids": [3449507998],
        },
        active_shards_recent=True,
    )

    assert payload["controller"] == "up"
    assert payload["supervisor"] == "up"
    assert payload["aggregate_stale"] is False
    assert payload["aggregate_timestamp_stale"] is False
    assert payload["frontier_ids"] == [3449507998]
    assert payload["recovered_from_active_shards"] is True
    assert payload["recovery_source"] == "active_shards"


def test_recover_ooda_state_from_configured_shard_topology_marks_loop_up() -> None:
    module = _load_module()

    payload = module._recover_ooda_state_from_active_shards(
        {
            "manifest_kind": "configured_shard_topology",
            "active_shards": [],
            "configured_shards": [
                {"name": "shard-1", "mode": "flagship_product"},
                {"name": "shard-2", "mode": "flagship_product"},
            ],
        },
        active_shards_recent=True,
    )

    assert payload["controller"] == "up"
    assert payload["supervisor"] == "up"
    assert payload["aggregate_stale"] is False
    assert payload["aggregate_timestamp_stale"] is False
    assert [item["name"] for item in payload["last_observed_shards"]] == ["shard-1", "shard-2"]
    assert payload["recovered_from_active_shards"] is True
    assert payload["recovery_source"] == "configured_shard_topology"


def test_materialize_flagship_product_readiness_recovers_stale_ooda_from_configured_shard_topology(
    tmp_path: Path,
) -> None:
    module = _load_module()

    payload = _materialize_flagship_readiness_with_parity_lab(
        tmp_path,
        module,
        active_shards_payload={
            "manifest_kind": "configured_shard_topology",
            "configured_shard_count": 2,
            "configured_shards": [{"name": "shard-1"}, {"name": "shard-2"}],
            "active_run_count": 0,
            "active_shards": [],
        },
        ooda_state_payload={
            "controller": "up",
            "supervisor": "up",
            "aggregate_stale": True,
            "aggregate_timestamp_stale": True,
        },
    )

    assert payload["coverage"]["fleet_and_operator_loop"] == "warning"
    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert evidence["ooda_state_recovered_from_active_shards"] is True
    assert evidence["ooda_state_recovery_source"] == "configured_shard_topology"
    assert evidence["ooda_aggregate_stale"] is False
    assert evidence["ooda_timestamp_stale"] is False
    assert not any("OODA monitor" in reason for reason in payload["coverage_details"]["fleet_and_operator_loop"]["reasons"])


def test_materialize_flagship_product_readiness_accepts_live_ooda_progress_when_aggregate_timestamps_lag(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = _now_iso()

    payload = _materialize_flagship_readiness_with_parity_lab(
        tmp_path,
        module,
        ooda_state_payload={
            "controller": "up",
            "supervisor": "up",
            "aggregate_stale": True,
            "aggregate_timestamp_stale": True,
            "active_runs_count": 1,
            "active_shards": [
                {
                    "name": "shard-4",
                    "mode": "flagship_product",
                    "active_run": True,
                    "worker_last_output_at": current_iso,
                }
            ],
        },
    )

    evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    reasons = payload["coverage_details"]["fleet_and_operator_loop"]["reasons"]
    assert not any("OODA monitor" in reason for reason in reasons)
    assert evidence["ooda_aggregate_stale"] is True
    assert evidence["ooda_timestamp_stale"] is True
    assert evidence["ooda_live_active_progress"] is True
    assert evidence["ooda_steady_complete_quiet"] is False


def test_materialize_flagship_product_readiness_fail_closes_stale_executable_gate_freshness_evidence(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 86401,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert (
        "Executable desktop exit gate freshness evidence is missing, invalid, or stale. Per-head proof cannot be treated as current."
        in reasons
    )
    assert any(
        "desktop visual familiarity gate proof_age_seconds" in reason and "stale" in reason
        for reason in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_freshness_issue_count"] >= 1


def test_materialize_flagship_product_readiness_accepts_stale_flagship_gate_age_when_downstream_desktop_proofs_are_fresh(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = _now_iso()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    executable_gate_payload = _desktop_executable_exit_gate_pass_payload(
        heads=("avalonia",),
        platforms=("linux", "windows"),
        generated_at=current_iso,
    )
    executable_gate_payload["evidence"]["flagship UI release gate proof_age_seconds"] = 86401
    _write_json(ui_executable_exit_gate_path, executable_gate_payload)
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(ui_visual_familiarity_exit_gate_path, _desktop_visual_familiarity_pass_payload(module))
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia",),
            platforms=("linux", "windows"),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "ready"
    assert payload["coverage_details"]["desktop_client"]["reasons"] == []
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_freshness_issue_count"] == 0


def test_materialize_flagship_product_readiness_fail_closes_stale_executable_gate_generated_at(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "generated_at": "2026-03-01T08:00:00Z",
            "generatedAt": "2026-03-01T08:00:00Z",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert any("Executable desktop exit gate receipt is stale" in reason for reason in reasons)
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_gate_generated_at"] == "2026-03-01T08:00:00Z"
    assert isinstance(evidence["ui_executable_gate_age_seconds"], int)
    assert evidence["ui_executable_gate_age_seconds"] > 86400


def test_materialize_flagship_product_readiness_fail_closes_stale_release_channel_generated_at(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "generated_at": "2026-03-01T08:00:00Z",
            "generatedAt": "2026-03-01T08:00:00Z",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert any("Release channel receipt is stale" in reason for reason in reasons)
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["release_channel_generated_at"] == "2026-03-01T08:00:00Z"
    assert isinstance(evidence["release_channel_age_seconds"], int)
    assert evidence["release_channel_age_seconds"] > 86400


def test_materialize_flagship_product_readiness_keeps_executable_gate_generated_at_evidence_when_gate_fails(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "fail",
            "generated_at": "2026-04-01T08:00:00Z",
            "generatedAt": "2026-04-01T08:00:00Z",
            "reasons": ["synthetic failing gate"],
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "fail"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_exit_gate_status"] == "fail"
    assert evidence["ui_executable_gate_generated_at"] == "2026-04-01T08:00:00Z"
    assert isinstance(evidence["ui_executable_gate_age_seconds"], int)
    assert evidence["ui_executable_gate_age_seconds"] >= 0


def test_materialize_flagship_product_readiness_fail_closes_when_visual_gate_milestone2_inventory_is_incomplete(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "generated_at": "2026-04-01T08:00:00Z",
            "generatedAt": "2026-04-01T08:00:00Z",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
            "status": "pass",
            "evidence": {
                "required_tests": [
                    "Runtime_backed_shell_chrome_stays_enabled_after_runner_load",
                    "Runtime_backed_codex_tree_preserves_legacy_left_rail_navigation_posture",
                    "Loaded_runner_header_stays_tab_panel_only_without_metric_cards",
                    "Character_creation_preserves_familiar_dense_builder_rhythm",
                ],
                "missing_tests": [
                    "Magic_matrix_and_consumables_workflows_execute_with_specific_dialog_fields_and_confirm_actions"
                ],
                "required_legacy_interaction_keys": [
                    "runtimeBackedLegacyWorkbench",
                    "legacyDenseBuilderRhythm",
                ],
                "required_legacy_interaction_key_statuses": {
                    "runtimeBackedLegacyWorkbench": "pass",
                    "runtimeBackedFileMenuRoutes": "pass",
                    "runtimeBackedMasterIndex": "pass",
                    "runtimeBackedCharacterRoster": "pass",
                    "legacyMainframeVisualSimilarity": "pass",
                },
                "runtime_backed_legacy_workbench": "pass",
                "runtime_backed_file_menu_routes": "pass",
                "runtime_backed_master_index": "pass",
                "runtime_backed_character_roster": "pass",
                "legacy_mainframe_visual_similarity": "pass",
                "missing_required_legacy_interaction_keys": [],
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert any("missing required milestone-2 legacy workflow tests" in reason for reason in reasons)
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_visual_familiarity_missing_required_milestone2_test_inventory_count"] > 0
    assert evidence["ui_visual_familiarity_reported_missing_required_milestone2_test_count"] > 0


def test_materialize_flagship_product_readiness_fail_closes_when_localization_gate_reports_untranslated_shipping_locale_keys(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_localization_release_gate_path = tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "generated_at": "2026-04-01T08:00:00Z",
            "generatedAt": "2026-04-01T08:00:00Z",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
            "status": "pass",
            "evidence": {
                "required_tests": list(
                    [
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
                    ]
                ),
                "missing_tests": [],
                "required_legacy_interaction_keys": [
                    "runtimeBackedLegacyWorkbench",
                    "legacyDenseBuilderRhythm",
                ],
                "required_legacy_interaction_key_statuses": {
                    "runtimeBackedLegacyWorkbench": "pass",
                    "runtimeBackedFileMenuRoutes": "pass",
                    "runtimeBackedMasterIndex": "pass",
                    "runtimeBackedCharacterRoster": "pass",
                    "legacyMainframeVisualSimilarity": "pass",
                },
                "runtime_backed_legacy_workbench": "pass",
                "runtime_backed_file_menu_routes": "pass",
                "runtime_backed_master_index": "pass",
                "runtime_backed_character_roster": "pass",
                "legacy_mainframe_visual_similarity": "pass",
                "missing_required_legacy_interaction_keys": [],
            },
        },
    )
    _write_json(
        ui_localization_release_gate_path,
        {
            "contract_name": "chummer6-ui.localization_release_gate",
            "status": "pass",
            "default_key_count": 383,
            "shipping_locales": ["de-de", "fr-fr"],
            "locale_summary": [
                {"locale": "de-de", "override_count": 25, "default_key_count": 383, "untranslated_key_count": 358},
                {"locale": "fr-fr", "override_count": 17, "default_key_count": 383, "untranslated_key_count": 366},
            ],
            "translation_backlog_findings": [
                "de-de: 358 trust-surface keys still rely on explicit en-US fallback",
                "fr-fr: 366 trust-surface keys still rely on explicit en-US fallback",
            ],
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--ui-localization-release-gate",
            str(ui_localization_release_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert any("Localization release gate still reports untranslated shipping-locale trust-surface keys." in reason for reason in reasons)
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_localization_release_gate_status"] == "pass"
    assert evidence["ui_localization_release_gate_untranslated_locale_count"] == 2
    assert evidence["ui_localization_release_gate_untranslated_counts_by_locale"]["de-de"] == 358


def test_materialize_flagship_product_readiness_fail_closes_when_localization_gate_is_missing_shipping_locale_summary_rows(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_localization_release_gate_path = tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "generated_at": "2026-04-01T08:00:00Z",
            "generatedAt": "2026-04-01T08:00:00Z",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
            "status": "pass",
            "evidence": {
                "required_tests": list(
                    [
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
                    ]
                ),
                "missing_tests": [],
                "required_legacy_interaction_keys": [
                    "runtimeBackedLegacyWorkbench",
                    "legacyDenseBuilderRhythm",
                ],
                "missing_required_legacy_interaction_keys": [],
            },
        },
    )
    _write_json(
        ui_localization_release_gate_path,
        {
            "contract_name": "chummer6-ui.localization_release_gate",
            "status": "pass",
            "defaultKeyCount": 383,
            "shippingLocales": ["en-us", "de-de"],
            "localeSummary": [
                {"locale": "de-de", "overrideCount": 383, "untranslatedKeyCount": 0},
            ],
            "translationBacklogFindings": [],
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--ui-localization-release-gate",
            str(ui_localization_release_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "missing"
    reasons = payload["coverage_details"]["desktop_client"]["reasons"]
    assert any(
        "Localization release gate is missing locale-summary rows for declared shipping locales." in reason
        for reason in reasons
    )
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_localization_release_gate_shipping_locale_count"] == 2
    assert evidence["ui_localization_release_gate_missing_locale_summary_shipping_locale_count"] == 1
    assert evidence["ui_localization_release_gate_missing_locale_summary_shipping_locales"] == ["en-us"]


def test_materialize_flagship_product_readiness_accepts_split_magic_and_matrix_visual_inventory_variants(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(journey_gates_path, _base_journey_gates())
    _write_json(support_packets_path, {"generated_at": "2026-04-01T08:00:00Z"})
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(
        ui_executable_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_executable_exit_gate",
            "status": "pass",
            "generated_at": "2026-04-01T08:00:00Z",
            "generatedAt": "2026-04-01T08:00:00Z",
            "evidence": {
                "linux_statuses": {"avalonia:linux-x64": "pass"},
                "windows_statuses": {"avalonia:win-x64": "pass"},
                "flagship UI release gate proof_age_seconds": 30,
                "desktop workflow execution gate proof_age_seconds": 30,
                "desktop visual familiarity gate proof_age_seconds": 30,
            },
        },
    )
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
            "status": "pass",
            "evidence": {
                "required_tests": [
                    "Runtime_backed_shell_chrome_stays_enabled_after_runner_load",
                    "Runtime_backed_codex_tree_preserves_legacy_left_rail_navigation_posture",
                    "Loaded_runner_header_stays_tab_panel_only_without_metric_cards",
                    "Character_creation_preserves_familiar_dense_builder_rhythm",
                    "Advancement_and_karma_journal_workflows_preserve_familiar_progression_rhythm",
                    "Gear_builder_preserves_familiar_browse_detail_confirm_rhythm",
                    "Vehicles_and_drones_builder_preserves_familiar_browse_detail_confirm_rhythm",
                    "Cyberware_and_cyberlimb_builder_preserve_legacy_dialog_familiarity_cues",
                    "Contacts_diary_and_support_routes_execute_with_public_path_visibility",
                    "Magic_workflows_execute_with_specific_dialog_fields_and_confirm_actions",
                    "Matrix_workflows_execute_with_specific_dialog_fields_and_confirm_actions",
                ],
                "missing_tests": [],
                "required_legacy_interaction_keys": [
                    "runtimeBackedLegacyWorkbench",
                    "legacyDenseBuilderRhythm",
                ],
                "required_legacy_interaction_key_statuses": {
                    "runtimeBackedLegacyWorkbench": "pass",
                    "runtimeBackedFileMenuRoutes": "pass",
                    "runtimeBackedMasterIndex": "pass",
                    "runtimeBackedCharacterRoster": "pass",
                    "legacyMainframeVisualSimilarity": "pass",
                },
                "runtime_backed_legacy_workbench": "pass",
                "runtime_backed_file_menu_routes": "pass",
                "runtime_backed_master_index": "pass",
                "runtime_backed_character_roster": "pass",
                "legacy_mainframe_visual_similarity": "pass",
                "missing_required_legacy_interaction_keys": [],
            },
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "rid": "linux-x64", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "rid": "win-x64", "kind": "installer"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_visual_familiarity_missing_required_milestone2_test_inventory_count"] == 0
    assert evidence["ui_visual_familiarity_reported_missing_required_milestone2_test_count"] == 0


def test_materialize_flagship_product_readiness_flags_external_runbook_timestamp_drift(tmp_path: Path) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    journey_gates = _base_journey_gates()
    install_journey = next(
        row for row in (journey_gates.get("journeys") or []) if isinstance(row, dict) and row.get("id") == "install_claim_restore_continue"
    )
    install_journey["state"] = "blocked"
    install_journey["blocked_by_external_constraints_only"] = True
    install_journey["external_blocking_reasons"] = ["external-host proof lane"]
    install_journey["external_proof_requests"] = [
        {
            "tuple_id": "avalonia:win-x64:windows",
            "required_host": "windows",
            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
        }
    ]
    _write_json(journey_gates_path, journey_gates)
    _write_json(
        support_packets_path,
        {
            "generated_at": "2026-04-01T08:00:00Z",
            "summary": {
                "open_packet_count": 1,
                "unresolved_external_proof_request_count": 1,
            },
        },
    )
    runbook_path.parent.mkdir(parents=True, exist_ok=True)
    runbook_path.write_text(
        "\n".join(
            [
                "# External proof runbook",
                "- generated_at: `2026-04-01T08:00:00Z`",
                "- plan_generated_at: `2026-03-31T08:00:00Z`",
                "- release_channel_generated_at: `2026-04-01T08:00:00Z`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "passed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"},
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"},
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        {
            "generatedAt": "2026-04-01T08:00:00Z",
            "status": "published",
            "releaseProof": {"status": "passed"},
            "artifacts": [
                {"head": "avalonia", "platform": "linux", "kind": "installer"},
                {"head": "avalonia", "platform": "windows", "kind": "installer"},
                {"head": "avalonia", "platform": "macos", "kind": "dmg"},
            ],
        },
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--external-proof-runbook",
            str(runbook_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    fleet_details = payload["coverage_details"]["fleet_and_operator_loop"]
    assert any("plan_generated_at does not match support packets generated_at" in reason for reason in fleet_details["reasons"])
    assert fleet_details["evidence"]["external_proof_runbook_synced"] is False


def test_materialize_flagship_product_readiness_recovers_desktop_lane_from_effective_install_state_and_executable_linux_tuple_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    current_iso = _now_iso()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_localization_release_gate_path = tmp_path / "ui" / "UI_LOCALIZATION_RELEASE_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"

    _write_yaml(acceptance_path, _base_acceptance())
    design_product_root = acceptance_path.parent
    (design_product_root / "HORIZONS.md").write_text("# Horizons\n", encoding="utf-8")
    (design_product_root / "FLAGSHIP_PRODUCT_BAR.md").write_text("# Flagship Bar\n", encoding="utf-8")
    (design_product_root / "SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md").write_text("# Surface Review\n", encoding="utf-8")
    (design_product_root / "CHUMMER5A_FAMILIARITY_BRIDGE.md").write_text("# Familiarity Bridge\n", encoding="utf-8")
    (design_product_root / "DESKTOP_EXECUTABLE_EXIT_GATES.md").write_text("# Desktop Exit Gates\n", encoding="utf-8")
    (design_product_root / "LEGACY_CLIENT_AND_ADJACENT_PARITY.md").write_text("# Legacy Parity\n", encoding="utf-8")
    _write_yaml(design_product_root / "PUBLIC_RELEASE_EXPERIENCE.yaml", {"product": "chummer"})
    horizons_dir = design_product_root / "horizons"
    horizons_dir.mkdir(parents=True, exist_ok=True)
    for canonical_doc in module.CANONICAL_HORIZONS_DIR.glob("*.md"):
        (horizons_dir / canonical_doc.name).write_text(f"# {canonical_doc.stem}\n", encoding="utf-8")

    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    journey_gates = _base_journey_gates()
    install_journey = next(
        row for row in (journey_gates.get("journeys") or []) if isinstance(row, dict) and row.get("id") == "install_claim_restore_continue"
    )
    install_journey["state"] = "blocked"
    install_journey["local_blocking_reasons"] = [
        "repo proof chummer6-hub:.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json is stale (215485s old > 172800s max)."
    ]
    journey_gates["summary"]["overall_state"] = "blocked"
    journey_gates["summary"]["blocked_count"] = 1
    journey_gates["summary"]["blocked_with_local_count"] = 1
    _write_json(journey_gates_path, journey_gates)
    _write_json(support_packets_path, _base_support_packets_payload(current_iso, summary={}))
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    executable_gate_payload = _desktop_executable_exit_gate_pass_payload(
        heads=("avalonia",),
        platforms=("linux", "windows", "macos"),
        generated_at=current_iso,
    )
    executable_gate_payload["evidence"]["hub_registry_root_trusted_for_startup_smoke_proof"] = True
    executable_gate_payload["evidence"]["hub_registry_root"] = "/docker/chummercomplete/chummer6-hub-registry"
    executable_gate_payload["evidence"]["hub_registry_release_channel_path"] = "/docker/chummercomplete/chummer6-hub-registry/release/RELEASE_CHANNEL.generated.json"
    _write_json(ui_executable_exit_gate_path, executable_gate_payload)
    _write_json(
        ui_exit_gate_path,
        {
            "contract_name": "chummer6-ui.linux_desktop_exit_gate",
            "status": "failed",
            "reason": "stage package_linux_artifacts failed",
        },
    )
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_workflow_execution_gate",
            "status": "fail",
            "evidence": {
                "workflow_family_failing_receipts": [
                    "sr4:create-open-import-save-save-as-print-export:fail",
                    "sr6:create-open-import-save-save-as-print-export:fail",
                ],
                "workflow_family_failing_receipts_external": [
                    "sr4:create-open-import-save-save-as-print-export:external_blocker:missing_api_surface_contract",
                    "sr6:create-open-import-save-save-as-print-export:external_blocker:missing_api_surface_contract",
                ],
                "workflow_execution_failing_receipts": [
                    "sr4:create-open-import-save-save-as-print-export:fail",
                    "sr6:create-open-import-save-save-as-print-export:fail",
                ],
                "workflow_execution_failing_receipts_external": [
                    "sr4:create-open-import-save-save-as-print-export:external_blocker:missing_api_surface_contract",
                    "sr6:create-open-import-save-save-as-print-export:external_blocker:missing_api_surface_contract",
                ],
            },
        },
    )
    _write_json(
        ui_visual_familiarity_exit_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate",
            "status": "pass",
            "evidence": {
                "required_tests": list(module.DESKTOP_VISUAL_FAMILIARITY_REQUIRED_MILESTONE2_TESTS),
                "missing_tests": [],
                "missing_required_legacy_interaction_keys": [],
                "runtimeBackedLegacyWorkbench": "pass",
                "runtimeBackedFileMenuRoutes": "pass",
                "runtimeBackedMasterIndex": "pass",
                "runtimeBackedCharacterRoster": "pass",
                "legacyMainframeVisualSimilarity": "pass",
            },
        },
    )
    _write_json(
        ui_localization_release_gate_path,
        {
            "contract_name": "chummer6-ui.localization_release_gate",
            "status": "pass",
            "default_key_count": 383,
            "shipping_locales": ["en-us"],
            "locale_summary": [{"locale": "en-us", "untranslated_key_count": 0}],
            "translation_backlog_findings": [],
        },
    )
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    parity_external_only_evidence = {
        "failingParityReceiptsExternalOnly": True,
        "failingParityReceiptsExternal": {
            "api_surface": ["external_blocker=missing_api_surface_contract"]
        },
    }
    _write_json(
        sr4_workflow_parity_path,
        {
            "contract_name": "chummer6-ui.sr4_desktop_workflow_parity",
            "status": "fail",
            "evidence": parity_external_only_evidence,
        },
    )
    _write_json(
        sr6_workflow_parity_path,
        {
            "contract_name": "chummer6-ui.sr6_desktop_workflow_parity",
            "status": "fail",
            "evidence": parity_external_only_evidence,
        },
    )
    _write_json(
        sr4_sr6_frontier_receipt_path,
        {
            "contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier",
            "status": "fail",
            "evidence": parity_external_only_evidence,
        },
    )
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia",),
            platforms=("linux", "windows", "macos"),
            journeys_passed=("install_claim_restore_continue", "build_explain_publish"),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--mirror-out",
            "",
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--ui-localization-release-gate",
            str(ui_localization_release_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    desktop = payload["coverage_details"]["desktop_client"]
    assert desktop["status"] == "ready"
    assert desktop["reasons"] == []
    assert desktop["evidence"]["ui_linux_exit_gate_recovered_from_executable_gate"] is True
    assert desktop["evidence"]["install_claim_restore_continue_effective"] == "ready"


def test_journey_local_blocker_routes_assigns_repo_proof_and_owner_fallback() -> None:
    module = _load_module()
    routes = module._journey_local_blocker_routes(
        {
            "install_claim_restore_continue": {
                "local_blocking_reasons": [
                    "repo proof chummer6-ui:.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json field 'evidence.workflow_execution_status' expected 'pass' but was 'fail'.",
                ],
                "owner_repos": ["chummer6-ui", "fleet"],
            },
            "report_cluster_release_notify": {
                "local_blocking_reasons": [
                    "delivery receipt marker missing for feedback status update.",
                ],
                "owner_repos": ["executive-assistant"],
            },
        }
    )

    assert routes["total_local_blocker_count"] == 2
    assert routes["routed_local_blocker_count"] == 2
    assert routes["unrouted_local_blocker_count"] == 0
    assert routes["owner_repo_counts"]["chummer6-ui"] == 1
    assert routes["owner_repo_counts"]["executive-assistant"] == 1
    assert len(routes["routes"]) == 2
    assert routes["routes"][0]["owner_repo"] in {"chummer6-ui", "executive-assistant"}


def test_journey_local_blocker_routes_reports_unrouted_without_owner_or_repo() -> None:
    module = _load_module()
    routes = module._journey_local_blocker_routes(
        {
            "build_explain_publish": {
                "local_blocking_reasons": [
                    "unscoped blocker with no repo proof prefix and no owner repo",
                ],
                "owner_repos": [],
            }
        }
    )

    assert routes["total_local_blocker_count"] == 1
    assert routes["routed_local_blocker_count"] == 0
    assert routes["unrouted_local_blocker_count"] == 1
    assert routes["routes"] == []
    assert len(routes["unrouted_reasons"]) == 1


def test_journey_local_blocker_routes_ignores_nonrequired_desktop_exit_gate_findings() -> None:
    module = _load_module()
    routes = module._journey_local_blocker_routes(
        {
            "install_claim_restore_continue": {
                "local_blocking_reasons": [
                    "repo proof chummer6-ui:.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json field 'local_blocking_findings_count' expected 0 but was 24.",
                ],
                "owner_repos": ["chummer6-ui"],
            }
        },
        ui_executable_exit_gate={
            "local_blocking_findings": [
                "Linux desktop exit gate is missing or not passing for promoted head 'blazor-desktop'.",
                "Release channel desktopTupleCoverage.externalProofRequests object rows do not match canonical missing-tuple external proof contract.",
            ]
        },
        release_channel={
            "desktopTupleCoverage": {
                "requiredDesktopHeads": ["avalonia"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:osx-arm64:macos",
                        "requiredHost": "macos",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expectedArtifactId": "avalonia-osx-arm64-installer",
                        "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                        "expectedInstallerRelativePath": "files/chummer-avalonia-osx-arm64-installer.dmg",
                        "expectedInstallerSha256": "a" * 64,
                        "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                        "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                        "startupSmokeReceiptContract": {
                            "statusAnyOf": ["pass", "passed", "ready"],
                            "readyCheckpoint": "pre_ui_event_loop",
                            "headId": "avalonia",
                            "platform": "macos",
                            "rid": "osx-arm64",
                            "hostClassContains": "macos",
                        },
                        "proofCaptureCommands": [
                            "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg avalonia osx-arm64 Chummer.Avalonia /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                            "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                        ],
                    }
                ],
            }
        },
    )

    assert routes["total_local_blocker_count"] == 0
    assert routes["routed_local_blocker_count"] == 0
    assert routes["routes"] == []


def test_journey_local_blocker_routes_respects_explicit_empty_local_reason_list() -> None:
    module = _load_module()
    routes = module._journey_local_blocker_routes(
        {
            "install_claim_restore_continue": {
                "blocking_reasons": [
                    "repo proof chummer6-hub-registry:.codex-studio/published/RELEASE_CHANNEL.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' expected [] but was ['avalonia:osx-arm64:macos'].",
                ],
                "local_blocking_reasons": [],
                "owner_repos": ["chummer6-hub-registry"],
            }
        }
    )

    assert routes["total_local_blocker_count"] == 0
    assert routes["routed_local_blocker_count"] == 0
    assert routes["routes"] == []


def test_support_packet_external_proof_requests_reads_packets_and_summary_specs() -> None:
    module = _load_module()
    requests = module._support_packet_external_proof_requests(
        {
            "packets": [
                {
                    "install_diagnosis": {
                        "external_proof_request": {
                            "tuple_id": "avalonia:osx-arm64:macos",
                            "required_host": "macos",
                        }
                    }
                }
            ],
            "summary": {
                "unresolved_external_proof_request_specs": {
                    "avalonia:osx-arm64:macos": {
                        "required_host": "macos",
                    },
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                    },
                }
            },
        }
    )

    assert len(requests) == 2
    tuple_ids = sorted(str(item.get("tuple_id") or "") for item in requests)
    assert tuple_ids == ["avalonia:osx-arm64:macos", "avalonia:win-x64:windows"]


def test_materialize_flagship_product_readiness_external_host_proof_uses_support_packet_backlog(
    tmp_path: Path,
) -> None:
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": "2026-04-01T08:00:00Z", "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "blocked",
                "blocked_count": 1,
                "blocked_external_only_count": 0,
                "blocked_with_local_count": 1,
            },
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "blocked",
                    "local_blocking_reasons": ["repo proof chummer6-hub-registry:.codex-studio/published/RELEASE_CHANNEL.generated.json field 'releaseProof.status' expected 'passed' but was 'pass'."],
                    "external_proof_requests": [],
                },
                {"id": "report_cluster_release_notify", "state": "ready"},
            ],
        },
    )
    _write_json(
        support_packets_path,
        {
            "generated_at": "2026-04-01T08:00:00Z",
            "summary": {
                "unresolved_external_proof_request_specs": {
                    "avalonia:osx-arm64:macos": {
                        "required_host": "macos",
                    }
                }
            },
        },
    )
    _write_json(supervisor_state_path, _base_supervisor_state())
    _write_json(ooda_state_path, _base_ooda_state())

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(tmp_path / "missing-ui.json"),
            "--ui-linux-exit-gate",
            str(tmp_path / "missing-ui-linux.json"),
            "--ui-windows-exit-gate",
            str(tmp_path / "missing-ui-windows.json"),
            "--ui-workflow-parity-proof",
            str(tmp_path / "missing-ui-workflow-parity.json"),
            "--ui-executable-exit-gate",
            str(tmp_path / "missing-ui-executable.json"),
            "--ui-workflow-execution-gate",
            str(tmp_path / "missing-ui-workflow-execution.json"),
            "--ui-visual-familiarity-exit-gate",
            str(tmp_path / "missing-ui-visual.json"),
            "--ui-localization-release-gate",
            str(tmp_path / "missing-ui-localization.json"),
            "--sr4-workflow-parity-proof",
            str(tmp_path / "missing-sr4.json"),
            "--sr6-workflow-parity-proof",
            str(tmp_path / "missing-sr6.json"),
            "--sr4-sr6-frontier-receipt",
            str(tmp_path / "missing-frontier.json"),
            "--hub-local-release-proof",
            str(tmp_path / "missing-hub.json"),
            "--mobile-local-release-proof",
            str(tmp_path / "missing-mobile.json"),
            "--release-channel",
            str(tmp_path / "missing-release-channel.json"),
            "--releases-json",
            str(tmp_path / "missing-releases.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    external_host_proof = payload["external_host_proof"]
    assert external_host_proof["status"] == "fail"
    assert external_host_proof["reason"] == "Resolve the blocking golden-journey gaps before widening publish claims."
    assert external_host_proof["unresolved_request_count"] == 1
    assert external_host_proof["unresolved_hosts"] == ["macos"]
    assert external_host_proof["unresolved_tuples"] == ["avalonia:osx-arm64:macos"]


def test_materialize_flagship_product_readiness_recovers_desktop_and_fleet_from_effective_install_proof(
    tmp_path: Path,
) -> None:
    module = _load_module()
    out_path = tmp_path / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    acceptance_path = tmp_path / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml"
    status_plane_path = tmp_path / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    progress_report_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
    progress_history_path = tmp_path / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
    journey_gates_path = tmp_path / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
    support_packets_path = tmp_path / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    external_runbook_path = tmp_path / ".codex-studio" / "published" / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    compile_manifest_path = tmp_path / ".codex-studio" / "published" / "compile.manifest.json"
    supervisor_state_path = tmp_path / "state" / "chummer_design_supervisor" / "state.json"
    ooda_state_path = tmp_path / "state" / "design_supervisor_ooda" / "current_8h" / "state.json"
    ui_local_release_path = tmp_path / "ui" / "UI_LOCAL_RELEASE_PROOF.generated.json"
    ui_exit_gate_path = tmp_path / "ui" / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
    ui_windows_exit_gate_path = tmp_path / "ui" / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json"
    ui_executable_exit_gate_path = tmp_path / "ui" / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    ui_workflow_execution_gate_path = tmp_path / "ui" / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json"
    ui_visual_familiarity_exit_gate_path = tmp_path / "ui" / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json"
    ui_workflow_parity_path = tmp_path / "ui" / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_workflow_parity_path = tmp_path / "ui" / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr6_workflow_parity_path = tmp_path / "ui" / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json"
    sr4_sr6_frontier_receipt_path = tmp_path / "ui" / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json"
    hub_local_release_path = tmp_path / "hub" / "HUB_LOCAL_RELEASE_PROOF.generated.json"
    mobile_local_release_path = tmp_path / "mobile" / "MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    release_channel_path = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    releases_json_path = tmp_path / "registry" / "releases.json"
    current_iso = _now_iso()

    _write_yaml(acceptance_path, _base_acceptance())
    _write_yaml(status_plane_path, _base_status_plane())
    _write_json(progress_report_path, {"generated_at": current_iso, "history_snapshot_count": 6})
    _write_json(progress_history_path, {"snapshot_count": 6})
    _write_json(
        journey_gates_path,
        {
            "summary": {
                "overall_state": "blocked",
                "blocked_with_local_count": 1,
                "blocked_external_only_count": 0,
                "recommended_action": "Resolve the blocking golden-journey gaps before widening publish claims.",
            },
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "blocked",
                    "local_blocking_reasons": [
                        "repo proof chummer6-hub:.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json is stale (215485s old > 172800s max)."
                    ],
                    "external_blocking_reasons": [],
                    "external_proof_requests": [],
                    "blocked_by_external_constraints_only": False,
                },
                {"id": "build_explain_publish", "state": "ready"},
                {"id": "campaign_session_recover_recap", "state": "ready"},
                {"id": "recover_from_sync_conflict", "state": "ready"},
                {"id": "report_cluster_release_notify", "state": "ready"},
                {"id": "organize_community_and_close_loop", "state": "ready"},
            ],
        },
    )
    _write_json(support_packets_path, _base_support_packets_payload(current_iso))
    _write_json(compile_manifest_path, {"dispatchable_truth_ready": True})
    _write_synced_external_runbook(
        module,
        external_runbook_path,
        external_runbook_path.parent / "external-proof-commands",
        current_iso,
    )
    supervisor_state = _base_supervisor_state()
    supervisor_state["updated_at"] = current_iso
    supervisor_state["focus_profiles"] = ["top_flagship_grade", "whole_project_frontier"]
    supervisor_state["completion_audit"] = {"status": "fail"}
    _write_json(supervisor_state_path, supervisor_state)
    _write_json(ooda_state_path, _base_ooda_state())
    _write_json(ui_local_release_path, {"contract_name": "chummer6-ui.local_release_proof", "status": "passed"})
    _write_json(ui_exit_gate_path, {"contract_name": "chummer6-ui.linux_desktop_exit_gate", "status": "failed"})
    _write_json(
        ui_windows_exit_gate_path,
        {
            "contract_name": "chummer6-ui.windows_desktop_exit_gate",
            "status": "passed",
            "checks": {
                "embedded_payload_marker_present": True,
                "embedded_sample_marker_present": True,
            },
        },
    )
    _write_json(
        ui_executable_exit_gate_path,
        _desktop_executable_exit_gate_pass_payload(
            heads=("avalonia",),
            platforms=("linux", "windows", "macos"),
            generated_at=current_iso,
        ),
    )
    _write_json(
        ui_workflow_execution_gate_path,
        {
            "contract_name": "chummer6-ui.desktop_workflow_execution_gate",
            "status": "fail",
            "evidence": {
                "workflow_family_missing_receipts": [],
                "workflow_family_failing_receipts": [],
                "workflow_execution_missing_receipts": [],
                "workflow_execution_failing_receipts": [],
                "workflow_execution_weak_receipts": ["sr4::dense-workbench"],
            },
        },
    )
    _write_json(ui_visual_familiarity_exit_gate_path, _desktop_visual_familiarity_pass_payload(module))
    _write_json(ui_workflow_parity_path, {"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_workflow_parity_path, {"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"})
    _write_json(sr6_workflow_parity_path, {"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"})
    _write_json(sr4_sr6_frontier_receipt_path, {"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"})
    _write_json(hub_local_release_path, {"contract_name": "chummer6-hub.local_release_proof", "status": "passed"})
    _write_json(mobile_local_release_path, {"contract_name": "chummer6-mobile.local_release_proof", "status": "passed"})
    _write_json(
        release_channel_path,
        _release_channel_payload(
            heads=("avalonia",),
            platforms=("linux", "windows", "macos"),
            journeys_passed=("install_claim_restore_continue",),
            generated_at=current_iso,
        ),
    )
    _write_json(releases_json_path, {"status": "published"})

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path),
            "--acceptance",
            str(acceptance_path),
            "--status-plane",
            str(status_plane_path),
            "--progress-report",
            str(progress_report_path),
            "--progress-history",
            str(progress_history_path),
            "--journey-gates",
            str(journey_gates_path),
            "--support-packets",
            str(support_packets_path),
            "--supervisor-state",
            str(supervisor_state_path),
            "--ooda-state",
            str(ooda_state_path),
            "--ui-local-release-proof",
            str(ui_local_release_path),
            "--ui-linux-exit-gate",
            str(ui_exit_gate_path),
            "--ui-windows-exit-gate",
            str(ui_windows_exit_gate_path),
            "--ui-workflow-parity-proof",
            str(ui_workflow_parity_path),
            "--ui-executable-exit-gate",
            str(ui_executable_exit_gate_path),
            "--ui-workflow-execution-gate",
            str(ui_workflow_execution_gate_path),
            "--ui-visual-familiarity-exit-gate",
            str(ui_visual_familiarity_exit_gate_path),
            "--sr4-workflow-parity-proof",
            str(sr4_workflow_parity_path),
            "--sr6-workflow-parity-proof",
            str(sr6_workflow_parity_path),
            "--sr4-sr6-frontier-receipt",
            str(sr4_sr6_frontier_receipt_path),
            "--hub-local-release-proof",
            str(hub_local_release_path),
            "--mobile-local-release-proof",
            str(mobile_local_release_path),
            "--release-channel",
            str(release_channel_path),
            "--releases-json",
            str(releases_json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["coverage"]["desktop_client"] == "ready"
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    desktop_evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert desktop_evidence["install_claim_restore_continue"] == "blocked"
    assert desktop_evidence["install_claim_restore_continue_effective"] == "ready"
    assert desktop_evidence["ui_linux_exit_gate_status"] == "failed"
    assert desktop_evidence["ui_linux_exit_gate_effective_ready"] is True
    assert desktop_evidence["ui_workflow_execution_gate_unresolved_receipts_sr4_sr6_only"] is True
    fleet_evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert fleet_evidence["journey_overall_state"] == "blocked"
    assert fleet_evidence["journey_effective_overall_state"] == "ready"
    assert fleet_evidence["supervisor_completion_status"] == "fail"
    assert fleet_evidence["supervisor_completion_status_recovered_from_current_readiness"] is True


def test_flagship_product_readiness_binds_parity_lab_evidence_into_veteran_ready_truth(tmp_path: Path) -> None:
    module = _load_module()
    payload = _materialize_flagship_readiness_with_parity_lab(tmp_path, module)

    veteran_plane = payload["readiness_planes"]["veteran_ready"]
    veteran_evidence = veteran_plane["evidence"]
    flagship_plane = payload["readiness_planes"]["flagship_ready"]
    flagship_registry = payload["flagship_parity_registry"]

    assert veteran_plane["status"] == "ready"
    assert veteran_evidence["parity_lab_ready"] is True
    assert veteran_evidence["parity_lab_capture_pack_present"] is True
    assert veteran_evidence["parity_lab_veteran_compare_pack_present"] is True
    assert veteran_evidence["parity_lab_capture_coverage_key"] == "desktop_client"
    assert veteran_evidence["parity_lab_capture_coverage_key_matches"] is True
    assert veteran_evidence["parity_lab_missing_flagship_family_ids"] == []
    assert veteran_evidence["parity_lab_families_below_target"] == []
    assert veteran_evidence["parity_lab_capture_missing_non_negotiable_ids"] == []
    assert veteran_evidence["parity_lab_workflow_missing_non_negotiable_ids"] == []
    assert veteran_evidence["parity_lab_missing_whole_product_coverage_keys"] == []
    assert flagship_plane["evidence"]["parity_lab_ready"] is True
    assert flagship_registry["parity_lab_ready"] is True


def test_flagship_product_readiness_does_not_treat_unbound_parity_lab_docs_as_veteran_ready(tmp_path: Path) -> None:
    module = _load_module()
    payload = _materialize_flagship_readiness_with_parity_lab(
        tmp_path,
        module,
        capture_coverage_key="fleet_and_operator_loop",
        missing_capture_non_negotiable_ids=("master_index_first_class",),
    )

    veteran_plane = payload["readiness_planes"]["veteran_ready"]
    veteran_evidence = veteran_plane["evidence"]
    flagship_plane = payload["readiness_planes"]["flagship_ready"]

    assert veteran_plane["status"] == "warning"
    assert veteran_evidence["parity_lab_ready"] is False
    assert veteran_evidence["parity_lab_capture_coverage_key"] == "fleet_and_operator_loop"
    assert veteran_evidence["parity_lab_capture_coverage_key_matches"] is False
    assert veteran_evidence["parity_lab_capture_missing_non_negotiable_ids"] == ["master_index_first_class"]
    assert "Parity-lab capture pack is missing required desktop non-negotiables" in " ".join(veteran_plane["reasons"])
    assert "Parity-lab capture pack no longer binds its non-negotiable map to desktop_client coverage." in veteran_plane["reasons"]
    assert flagship_plane["status"] == "warning"
    assert flagship_plane["evidence"]["parity_lab_ready"] is False
