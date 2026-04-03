from __future__ import annotations

import json
import subprocess
import sys
import datetime as dt
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
    assert evidence["release_channel_required_tuple_platforms"] == ["linux", "windows", "macos"]
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
    assert payload["evidence_sources"]["supervisor_state"].endswith("/state.json")


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
