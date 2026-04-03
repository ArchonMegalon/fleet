from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_flagship_product_readiness.py")


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
            payload.setdefault("generated_at", "2026-04-01T08:00:00Z")
            payload.setdefault("generatedAt", "2026-04-01T08:00:00Z")
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
    assert payload["coverage"]["desktop_client"] == "ready"
    assert payload["coverage"]["hub_and_registry"] == "ready"
    assert payload["coverage"]["mobile_play_shell"] == "ready"
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
    assert payload["coverage"]["desktop_client"] == "ready"
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
    assert evidence["ui_executable_gate_macos_tuple_count"] == 0
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
    assert "Release channel does not publish the promoted Windows Avalonia installer." in reasons
    assert "Release channel does not publish the promoted Windows Avalonia installer." in reasons


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
    manifest_payload = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    assert "FLAGSHIP_PRODUCT_READINESS.generated.json" in manifest_payload["artifacts"]


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
    assert payload["evidence_sources"]["supervisor_state"] == str(shard_2_state_path.resolve())


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
    assert payload["evidence_sources"]["supervisor_state"] == str(shard_2_state_path.resolve())


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
    assert payload["coverage"]["fleet_and_operator_loop"] == "ready"
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
