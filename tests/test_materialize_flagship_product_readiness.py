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


def _load_module():
    spec = importlib.util.spec_from_file_location("materialize_flagship_product_readiness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _base_acceptance() -> dict:
    return {
        "product": "chummer",
        "version": 1,
        "source_documents": ["FLAGSHIP_PRODUCT_BAR.md", "PUBLIC_RELEASE_EXPERIENCE.yaml", "METRICS_AND_SLOS.yaml"],
        "acceptance_axes": [{"id": "primary_path_clarity"}, {"id": "authored_ruleset_experience"}],
    }


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
        },
    }


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
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", "1")
    args = module.parse_args(["--out", str(Path("/tmp/flagship.json"))])
    assert args.ignore_nonlinux_desktop_host_proof_blockers is True


def test_parse_args_inherits_ignore_nonlinux_desktop_host_proof_blockers_from_runtime_env_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_module()
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS=1\n", encoding="utf-8")
    monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", raising=False)
    monkeypatch.setattr(module, "RUNTIME_ENV_CANDIDATES", (runtime_env,))
    args = module.parse_args(["--out", str(Path("/tmp/flagship.json"))])
    assert args.ignore_nonlinux_desktop_host_proof_blockers is True


def test_feedback_loop_readiness_plane_marks_clean_release_truth_backed_closure_ready() -> None:
    module = _load_module()
    status, plane = module._feedback_loop_readiness_plane(
        feedback_loop_gate=_base_feedback_loop_gate(),
        gate_path=Path("/tmp/FEEDBACK_LOOP_RELEASE_GATE.yaml"),
        feedback_progress_email_workflow=_base_feedback_progress_email_workflow(),
        feedback_progress_email_workflow_path=Path("/tmp/FEEDBACK_PROGRESS_EMAIL_WORKFLOW.yaml"),
        support_packets={"generated_at": "2026-04-12T10:00:00Z", "source": {}},
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


def test_materialize_flagship_product_readiness_marks_desktop_ready_when_only_ignored_nonlinux_host_proof_is_missing(
    tmp_path: Path,
) -> None:
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
    assert payload["coverage"]["desktop_client"] == "ready"
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_executable_exit_gate_status"] == "fail"
    assert evidence["ui_executable_exit_gate_ignored_nonlinux_only"] is True
    assert evidence["desktop_ignore_nonlinux_desktop_host_proof_blockers"] is True
    assert payload["coverage_details"]["desktop_client"]["reasons"] == []


def test_materialize_flagship_product_readiness_recovers_fleet_bucket_when_only_supervisor_completion_is_stale(
    tmp_path: Path,
) -> None:
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
    _write_json(support_packets_path, {"generated_at": current_iso})
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
            "desktopTupleCoverage": {
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatforms": [],
                "missingRequiredHeads": [],
            },
            "rolloutState": "local_docker_preview",
            "supportabilityState": "local_docker_proven",
            "channelId": "docker",
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
    assert payload["coverage"]["desktop_client"] == "ready"
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
    assert payload["coverage_details"]["fleet_and_operator_loop"]["reasons"] == []
    fleet_evidence = payload["coverage_details"]["fleet_and_operator_loop"]["evidence"]
    assert fleet_evidence["supervisor_completion_status"] == "fail"
    assert fleet_evidence["supervisor_completion_status_recovered_from_current_readiness"] is True


def test_materialize_flagship_product_readiness_marks_real_missing_lanes(tmp_path: Path) -> None:
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
    assert payload["flagship_readiness_audit"]["status"] == "fail"
    assert payload["flagship_readiness_audit"]["coverage_gap_keys"]
    assert set(payload["flagship_readiness_audit"]["coverage_gap_keys"]) == set(payload["warning_keys"] + payload["missing_keys"])
    assert payload["flagship_readiness_audit"]["warning_coverage_keys"] == payload["warning_keys"]
    assert payload["flagship_readiness_audit"]["missing_coverage_keys"] == payload["missing_keys"]
    assert payload["external_host_proof"]["status"] == "fail"
    assert payload["external_host_proof"]["unresolved_request_count"] == 2
    assert payload["external_host_proof"]["unresolved_hosts"] == ["macos", "windows"]
    assert payload["external_host_proof"]["unresolved_tuples"] == [
        "avalonia:win-x64:windows",
        "blazor-desktop:osx-arm64:macos",
    ]
    assert payload["summary"]["warning_count"] + payload["summary"]["missing_count"] > 0
    assert set(payload["missing_keys"]).issubset(set(payload["coverage"].keys()))
    assert set(payload["missing_keys"]).isdisjoint(set(payload["warning_keys"]))
    assert mirror_path.exists()


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
    assert evidence["release_channel_has_macos_public_installer"] is True
    assert evidence["release_channel_has_linux_public_installer"] is True
    assert evidence["release_channel_has_windows_public_installer"] is True
    assert evidence["release_channel_linux_promoted_tuples"] == ["avalonia:linux-x64"]
    assert evidence["release_channel_windows_promoted_tuples"] == ["avalonia:win-x64"]
    assert evidence["ui_executable_gate_linux_tuple_count"] == 1
    assert evidence["ui_executable_gate_linux_passing_tuple_count"] == 1
    assert evidence["ui_executable_gate_linux_missing_or_failing_keys"] == []
    assert evidence["ui_executable_gate_windows_tuple_count"] == 1
    assert evidence["ui_executable_gate_windows_passing_tuple_count"] == 1
    assert evidence["ui_executable_gate_windows_missing_or_failing_keys"] == []
    assert evidence["ui_executable_gate_macos_tuple_count"] == 1
    assert evidence["ui_executable_gate_macos_passing_tuple_count"] == 1
    assert evidence["ui_executable_gate_macos_missing_or_failing_keys"] == []


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
    _write_json(ui_executable_exit_gate_path, {"contract_name": "chummer6-ui.desktop_executable_exit_gate", "status": "pass"})
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
    reasons = " ".join(payload["coverage_details"]["desktop_client"]["reasons"])
    assert "Executable desktop workflow execution gate reports unresolved family/execution receipt drift" in reasons
    evidence = payload["coverage_details"]["desktop_client"]["evidence"]
    assert evidence["ui_workflow_execution_gate_execution_weak_receipt_count"] == 1
    assert evidence["ui_workflow_execution_gate_unresolved_receipt_count"] == 1
    assert evidence["ui_workflow_execution_gate_unresolved_receipts"] == ["sr4::dense-workbench"]


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


def test_materialize_flagship_product_readiness_recovers_supervisor_from_active_shards_and_runtime_profile(tmp_path: Path) -> None:
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
            "active_run_count": 2,
            "active_shards": [{"name": "shard-1"}, {"name": "shard-2"}],
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
    assert evidence["active_shards_manifest_kind"] == "configured_shard_topology"
    assert evidence["configured_shards_count"] == 2
    assert payload["evidence_sources"]["active_shards"].endswith("/active_shards.json")


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
