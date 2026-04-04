from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_journey_gates.py")
REGISTRY = Path("/docker/fleet/.codex-design/product/GOLDEN_JOURNEY_RELEASE_GATES.yaml")
UTC = dt.timezone.utc
MODULE_SPEC = importlib.util.spec_from_file_location("materialize_journey_gates_module", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
JOURNEY_GATES_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(JOURNEY_GATES_MODULE)


def fresh_timestamp(hours_ago: int = 1) -> str:
    return (dt.datetime.now(UTC) - dt.timedelta(hours=hours_ago)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_release_channel_external_proof_requests_normalize_and_dedupe() -> None:
    payload = {
        "desktopTupleCoverage": {
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:win-x64:windows",
                    "requiredHost": "windows",
                    "requiredProofs": ["startup_smoke_receipt", "promoted_installer_artifact", "startup_smoke_receipt"],
                    "expectedArtifactId": "avalonia-win-x64-installer",
                    "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                    "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                },
                {
                    "tupleId": "avalonia:win-x64:windows",
                    "platform": "windows",
                    "requiredProofs": ["promoted_installer_artifact"],
                },
                {
                    "tupleId": "blazor-desktop:osx-arm64:macos",
                    "platform": "macos",
                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                },
            ]
        }
    }

    requests = JOURNEY_GATES_MODULE._release_channel_external_proof_requests(payload)
    assert [row.get("tuple_id") for row in requests] == [
        "avalonia:win-x64:windows",
        "blazor-desktop:osx-arm64:macos",
    ]
    assert requests[0]["required_host"] == "windows"
    assert requests[0]["required_proofs"] == ["promoted_installer_artifact"]
    assert requests[0]["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]
    assert requests[1]["required_host"] == "macos"
    assert requests[1]["required_proofs"] == ["promoted_installer_artifact", "startup_smoke_receipt"]
    assert requests[1]["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=macos-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-blazor-desktop-osx-arm64-installer.dmg blazor-desktop osx-arm64 Chummer.Blazor.Desktop /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]


def test_materialize_journey_gates_emits_warning_when_target_posture_lags(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-ui, chummer6-hub]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 2
      target_history_snapshots: 4
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
          target_stage: publicly_promoted
          minimum_deployment_posture: protected_preview
          target_deployment_posture: public
        - project_id: hub
          minimum_stage: pre_repo_local_complete
          target_stage: publicly_promoted
          minimum_deployment_posture: protected_preview
          target_deployment_posture: public
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: pre_repo_local_complete
    deployment_promotion_stage: protected_preview
    deployment_access_posture: public
  - id: hub
    readiness_stage: pre_repo_local_complete
    deployment_promotion_stage: protected_preview
    deployment_access_posture: public
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0},
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.journey_gates"
    assert payload["summary"]["overall_state"] == "warning"
    assert payload["summary"]["warning_count"] == 1
    assert payload["journeys"][0]["state"] == "warning"
    assert any("below target stage" in reason for reason in payload["journeys"][0]["warning_reasons"])
    assert not any("promotion posture" in reason for reason in payload["journeys"][0]["warning_reasons"])


def test_materialize_journey_gates_blocks_on_missing_required_project(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Honest closure stays tied to release truth.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [chummer6-hub, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 2
      require_support_freshness: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
          target_stage: publicly_promoted
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: boundary_pure
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0},
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert "required project hub is missing" in " ".join(payload["journeys"][0]["blocking_reasons"])


def test_materialize_journey_gates_blocks_on_empty_status_plane_inventory(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-ui, chummer6-hub]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 2
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects: []
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0},
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reasons = payload["journeys"][0]["blocking_reasons"]
    assert any("status-plane project inventory is empty" in reason for reason in reasons)
    assert not any("required project ui is missing" in reason for reason in reasons)
    assert not any("required project hub is missing" in reason for reason in reasons)


def test_materialize_journey_gates_blocks_when_repo_source_proof_marker_is_missing(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: build_explain_publish
    title: Build, explain, publish
    user_promise: Build and explain stay grounded.
    canonical_journeys:
      - journeys/build-and-inspect-a-character.md
    owner_repos: [chummer6-hub, chummer6-ui, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 2
      repo_source_proof:
        - repo: chummer6-ui
          path: Chummer.Blazor/Components/Shell/SectionPane.razor
          must_contain: [not-a-real-marker]
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: pre_repo_local_complete
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert any("repo proof chummer6-ui:Chummer.Blazor/Components/Shell/SectionPane.razor is missing required marker" in reason for reason in payload["journeys"][0]["blocking_reasons"])


def test_materialize_journey_gates_marks_external_only_blockers_when_all_blocking_reasons_are_host_constraints(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-ui, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 1
      repo_source_proof:
        - repo: chummer6-ui
          path: Chummer.Blazor/Components/Shell/SectionPane.razor
          must_contain:
            - current host cannot run promoted macOS installer smoke in synthetic host-constraint test
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert journey["blocked_by_external_constraints_only"] is True
    assert journey["signals"]["external_blocking_reason_count"] == 1
    assert journey["signals"]["local_blocking_reason_count"] == 0
    assert payload["summary"]["blocked_external_only_count"] == 1
    assert payload["summary"]["blocked_with_local_count"] == 0
    assert "platform-host proof lane" in journey["recommended_action"]


def test_materialize_journey_gates_marks_mixed_blockers_when_local_and_external_reasons_coexist(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-ui, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 1
      repo_source_proof:
        - repo: chummer6-ui
          path: Chummer.Blazor/Components/Shell/SectionPane.razor
          must_contain:
            - current host cannot run promoted macOS installer smoke in synthetic host-constraint test
            - synthetic local blocker marker not present
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert journey["blocked_by_external_constraints_only"] is False
    assert journey["signals"]["external_blocking_reason_count"] == 1
    assert journey["signals"]["local_blocking_reason_count"] == 1
    assert payload["summary"]["blocked_external_only_count"] == 0
    assert payload["summary"]["blocked_with_local_count"] == 1


def test_materialize_journey_gates_blocks_when_repo_source_proof_json_field_mismatches(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-ui, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 1
      repo_source_proof:
        - repo: chummer6-ui
          path: .codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json
          json_must_equal:
            status: pass
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert any(
        "field 'status' expected 'pass' but was 'fail'" in reason
        for reason in payload["journeys"][0]["blocking_reasons"]
    )


def test_install_journey_surfaces_release_channel_external_proof_requests(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-hub-registry, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 1
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            desktopTupleCoverage.missingRequiredPlatformHeadRidTuples: []
      required_project_posture:
        - project_id: hub-registry
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub-registry
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    request = next(item for item in journey["external_proof_requests"] if item["tuple_id"] == "avalonia:win-x64:windows")
    assert request["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]
    assert any(
        "external proof request: capture promoted_installer_artifact, startup_smoke_receipt" in reason
        for reason in journey["external_blocking_reasons"]
    )
    assert any(
        "Expected targets: artifactId avalonia-win-x64-installer, installer chummer-avalonia-win-x64-installer.exe, "
        "public route /downloads/install/avalonia-win-x64-installer, "
        "startup-smoke receipt startup-smoke/startup-smoke-avalonia-win-x64.receipt.json."
        in reason
        for reason in journey["external_blocking_reasons"]
    )
def test_materialize_journey_gates_blocks_when_repo_source_proof_json_field_not_in_allowed_set(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-hub-registry, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 1
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_be_one_of:
            status: [draft, archived]
      required_project_posture:
        - project_id: hub-registry
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub-registry
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert any(
        "field 'status' expected one of ['draft', 'archived'] but was 'published'" in reason
        for reason in payload["journeys"][0]["blocking_reasons"]
    )


def test_materialize_journey_gates_blocks_when_repo_source_proof_json_field_not_non_empty_string(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-hub-registry, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 1
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_be_non_empty_string:
            message: true
      required_project_posture:
        - project_id: hub-registry
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub-registry
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert any(
        "field 'message' must be a non-empty string but was None" in reason
        for reason in payload["journeys"][0]["blocking_reasons"]
    )


def test_materialize_journey_gates_blocks_when_repo_source_proof_is_stale(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-ui, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 1
      repo_source_proof:
        - repo: chummer6-ui
          path: .codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json
          must_contain:
            - '"contract_name": "chummer6-ui.desktop_executable_exit_gate"'
          max_age_hours: 0.000001
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert any("is stale (" in reason for reason in payload["journeys"][0]["blocking_reasons"])


def test_materialize_journey_gates_blocks_when_update_required_cases_are_not_proven_routed_to_downloads(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Honest closure stays tied to release truth.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [chummer6-hub, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 2
      require_support_freshness: true
      require_support_update_required_routes_to_downloads: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {
                    "closure_waiting_on_release_truth": 0,
                    "needs_human_response": 0,
                    "update_required_case_count": 2,
                    "update_required_routed_to_downloads_count": 1,
                    "update_required_misrouted_case_count": 1,
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert any(
        "support packets include update-required cases not routed to /downloads." in reason
        for reason in payload["journeys"][0]["blocking_reasons"]
    )


def test_materialize_journey_gates_blocks_when_support_packet_install_truth_contract_is_incomplete(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Honest closure stays tied to release truth.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [chummer6-hub, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 2
      require_support_freshness: true
      require_support_install_truth_contract: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {
                    "closure_waiting_on_release_truth": 0,
                    "needs_human_response": 0,
                    "update_required_case_count": 0,
                    "update_required_routed_to_downloads_count": 0,
                    "update_required_misrouted_case_count": 0,
                },
                "packets": [
                    {
                        "packet_id": "support_packet_bad_contract",
                        "status": "new",
                        "install_truth_state": "promoted_tuple_match",
                        "install_diagnosis": {
                            "registry_channel_id": "preview",
                            "registry_release_version": "",
                        },
                        "fix_confirmation": {"state": "awaiting_reporter_verification"},
                        "recovery_path": {"action_id": "", "href": "/downloads"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    journey = payload["journeys"][0]
    assert payload["summary"]["overall_state"] == "blocked"
    assert journey["signals"]["support_install_truth_contract_violation_count"] == 5
    assert any(
        "support packet support_packet_bad_contract is missing install_diagnosis.registry_release_version." in reason
        for reason in journey["blocking_reasons"]
    )
    assert any(
        "support packet support_packet_bad_contract is missing install_diagnosis.registry_release_channel_status." in reason
        for reason in journey["blocking_reasons"]
    )
    assert any(
        "support packet support_packet_bad_contract is missing recovery_path.action_id." in reason
        for reason in journey["blocking_reasons"]
    )


def test_materialize_journey_gates_blocks_when_support_recovery_route_contract_drifts(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Honest closure stays tied to release truth.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [chummer6-hub, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 2
      require_support_freshness: true
      require_support_recovery_path_contract: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {
                    "closure_waiting_on_release_truth": 0,
                    "needs_human_response": 0,
                    "update_required_case_count": 0,
                    "update_required_routed_to_downloads_count": 0,
                    "update_required_misrouted_case_count": 0,
                },
                "packets": [
                    {
                        "packet_id": "support_packet_bad_recovery",
                        "status": "fixed",
                        "install_truth_state": "promoted_tuple_match",
                        "fix_confirmation": {
                            "state": "awaiting_reporter_verification",
                            "installed_version": "run-2026.04.01",
                            "fixed_version": "run-2026.04.02",
                            "fixed_channel": "preview",
                            "update_required": True,
                        },
                        "recovery_path": {"action_id": "open_support_timeline", "href": "/account/support"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    journey = payload["journeys"][0]
    assert payload["summary"]["overall_state"] == "blocked"
    assert journey["signals"]["support_recovery_route_contract_violation_count"] == 1
    assert any(
        "support packet support_packet_bad_recovery requires download recovery when update_required is true."
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_materialize_journey_gates_blocks_when_mobile_local_release_proof_marker_is_missing(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: recover_from_sync_conflict
    title: Recover from sync conflict
    user_promise: Conflict and drift stay visible.
    canonical_journeys:
      - journeys/recover-from-sync-conflict.md
    owner_repos: [chummer6-mobile, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report]
      minimum_history_snapshots: 2
      repo_source_proof:
        - repo: chummer6-mobile
          path: .codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json
          must_contain: [not-a-real-mobile-marker]
      required_project_posture:
        - project_id: mobile
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: mobile
    readiness_stage: publicly_promoted
    deployment_promotion_stage: promoted_preview
    deployment_access_posture: public
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 4}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 4}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": generated_at, "summary": {}, "packets": []}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "blocked"
    assert any(
        "repo proof chummer6-mobile:.codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json is missing required marker" in reason
        for reason in payload["journeys"][0]["blocking_reasons"]
    )


def test_materialize_journey_gates_are_ready_when_promoted_preview_targets_and_history_are_boring(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: install_claim_restore_continue
    title: Install, claim, restore, continue
    user_promise: A person can install, claim, restore, and continue.
    canonical_journeys:
      - journeys/install-and-update.md
    owner_repos: [chummer6-ui, chummer6-hub, chummer6-mobile, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 2
      target_history_snapshots: 4
      required_project_posture:
        - project_id: ui
          minimum_stage: pre_repo_local_complete
          target_stage: publicly_promoted
          minimum_deployment_posture: protected_preview
          target_deployment_posture: public
        - project_id: hub
          minimum_stage: pre_repo_local_complete
          target_stage: publicly_promoted
          minimum_deployment_posture: protected_preview
          target_deployment_posture: public
        - project_id: mobile
          minimum_stage: pre_repo_local_complete
          target_stage: publicly_promoted
          minimum_deployment_posture: protected_preview
          target_deployment_posture: public
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: ui
    readiness_stage: publicly_promoted
    deployment_promotion_stage: promoted_preview
    deployment_access_posture: public
  - id: hub
    readiness_stage: publicly_promoted
    deployment_promotion_stage: promoted_preview
    deployment_access_posture: public
  - id: mobile
    readiness_stage: publicly_promoted
    deployment_promotion_stage: promoted_preview
    deployment_access_posture: public
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 4}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 4}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0},
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["overall_state"] == "ready"
    assert payload["summary"]["warning_count"] == 0
    assert payload["summary"]["blocked_count"] == 0


def test_build_explain_publish_gate_requires_ui_kit_build_and_explain_markers() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    journeys = registry.get("journey_gates") or []
    build_explain_publish = next(
        row for row in journeys if isinstance(row, dict) and row.get("id") == "build_explain_publish"
    )
    proofs = build_explain_publish.get("fleet_gate", {}).get("repo_source_proof") or []

    def proof_for(repo: str, path: str) -> dict:
        return next(
            row
            for row in proofs
            if isinstance(row, dict)
            and row.get("repo") == repo
            and row.get("path") == path
        )

    core_api = proof_for("chummer6-core", "Chummer.Tests/ApiIntegrationTests.cs")
    assert 'response["referenceSourceLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["settingsLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["sourceToggleLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["sourceSelectionLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["customDataLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["customDataAuthoringLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["xmlBridgeLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["translatorLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["importOracleLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["importOracleMissingSources"]' in core_api.get("must_contain", [])
    assert 'response["adjacentSr6OracleReceiptPosture"]' in core_api.get("must_contain", [])
    assert 'response["adjacentSr6OracleSourcesCovered"]' in core_api.get("must_contain", [])
    assert 'response["adjacentSr6OracleLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["sr6SuccessorLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["onlineStorageLanePosture"]' in core_api.get("must_contain", [])
    assert 'response["onlineStorageReceiptPosture"]' in core_api.get("must_contain", [])
    assert 'response["onlineStorageLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'firstSourcebook["referenceSnapshotPosture"]' in core_api.get("must_contain", [])

    core_tool_catalog = proof_for("chummer6-core", "Chummer.Infrastructure/Xml/XmlToolCatalogService.cs")
    assert "BuildReferenceSourceLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildSettingsLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildSourceToggleLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildSourceSelectionLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildCustomDataLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildCustomDataAuthoringLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildXmlBridgeLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildTranslatorLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildImportOracleLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildAdjacentSr6OracleLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "ImportOracleMissingSources" in core_tool_catalog.get("must_contain", [])
    assert "ResolveAdjacentSr6OracleCoverage" in core_tool_catalog.get("must_contain", [])
    assert "BuildSr6SuccessorLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildOnlineStorageSummary" in core_tool_catalog.get("must_contain", [])
    assert "BuildOnlineStorageLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "ResolveReferenceSnapshotPosture" in core_tool_catalog.get("must_contain", [])

    core_engine = proof_for("chummer6-core", "Chummer.CoreEngine.Tests/Program.cs")
    assert "BuildLabWorkspaceProjectionFactoryProjectsIntakeState" in core_engine.get("must_contain", [])
    assert "RuntimeLockDiffIsDeterministicAndParameterized" in core_engine.get("must_contain", [])
    assert "target.foundry-export" in core_engine.get("must_contain", [])
    assert "target.json-exchange" in core_engine.get("must_contain", [])
    assert "target.sheet-viewer" in core_engine.get("must_contain", [])
    assert "target.print-pdf-export" in core_engine.get("must_contain", [])
    assert "target.replay-timeline" in core_engine.get("must_contain", [])
    assert "target.session-recap" in core_engine.get("must_contain", [])
    assert "target.run-module" in core_engine.get("must_contain", [])

    hub_handoff = proof_for("chummer6-hub", "Chummer.Tests/PublicLandingBuildLabHandoffViewTests.cs")
    assert "handoff.RuleEnvironmentDiff" in hub_handoff.get("must_contain", [])
    assert "handoff.RuleEnvironmentDiff.BeforeScope" in hub_handoff.get("must_contain", [])
    assert "handoff.RuleEnvironmentDiff.AfterScope" in hub_handoff.get("must_contain", [])

    hub_interop = proof_for("chummer6-hub", "Chummer.Run.AI/Services/Interop/InteropExportService.cs")
    assert "chummer.portable-dossier.v1" in hub_interop.get("must_contain", [])
    assert "chummer.portable-campaign.v1" in hub_interop.get("must_contain", [])
    assert "foundry-vtt.scene-ledger.v1" in hub_interop.get("must_contain", [])
    assert "ReceiptSummary" in hub_interop.get("must_contain", [])
    assert "nextSafeAction" in hub_interop.get("must_contain", [])

    media_creator = proof_for(
        "chummer6-media-factory",
        "src/Chummer.Media.Factory.Runtime/Assets/CreatorPublicationPlannerService.cs",
    )
    assert (
        'PreserveLaneLine("JSON exchange:", handoff.ExchangeParityLines, selectedParityLines);'
        in media_creator.get("must_contain", [])
    )
    assert (
        'PreserveLaneLine("Foundry exchange:", handoff.ExchangeParityLines, selectedParityLines);'
        in media_creator.get("must_contain", [])
    )
    assert (
        'PreserveLaneLine("Sheet viewer:", handoff.ExchangeParityLines, selectedParityLines);'
        in media_creator.get("must_contain", [])
    )
    assert (
        'PreserveLaneLine("Print PDF:", handoff.ExchangeParityLines, selectedParityLines);'
        in media_creator.get("must_contain", [])
    )
    assert (
        'PreserveLaneLine("Character template export:", handoff.ExchangeParityLines, selectedParityLines);'
        in media_creator.get("must_contain", [])
    )
    assert (
        'PreserveLaneLine("Replay timeline:", handoff.PortabilityPillarLines, selectedPortabilityLines);'
        in media_creator.get("must_contain", [])
    )
    assert (
        'PreserveLaneLine("Session recap:", handoff.PortabilityPillarLines, selectedPortabilityLines);'
        in media_creator.get("must_contain", [])
    )
    assert (
        'PreserveLaneLine("Run module:", handoff.PortabilityPillarLines, selectedPortabilityLines);'
        in media_creator.get("must_contain", [])
    )

    media_verify = proof_for("chummer6-media-factory", "Chummer.Media.Factory.Runtime.Verify/Program.cs")
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("JSON exchange:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("Foundry exchange:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("Sheet viewer:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("Print PDF:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("Character template export:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("Replay timeline:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("Session recap:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )
    assert (
        'Assert(creatorPublicationPlan.EvidenceLines.Any(static line => line.Contains("Run module:", StringComparison.Ordinal)),'
        in media_verify.get("must_contain", [])
    )

    boundary = proof_for("chummer6-ui", "Chummer.Presentation/UiKit/ChummerPatternBoundary.cs")
    assert "BlazorUiKitAdapter.AdaptDenseTableHeader" in boundary.get("must_contain", [])
    assert "BlazorUiKitAdapter.AdaptExplainChip" in boundary.get("must_contain", [])
    assert "BlazorUiKitAdapter.AdaptSpiderStatusCard" in boundary.get("must_contain", [])
    assert "BlazorUiKitAdapter.AdaptArtifactStatusCard" in boundary.get("must_contain", [])

    handoff = proof_for("chummer6-ui", "Chummer.Blazor/Components/Shared/BuildLabHandoffPanel.razor")
    assert "ChummerPatternBoundary.ExplainChipClass" in handoff.get("must_contain", [])
    assert "ChummerPatternBoundary.ArtifactStatusCardClass" in handoff.get("must_contain", [])

    rules = proof_for("chummer6-ui", "Chummer.Blazor/Components/Shared/RulesNavigatorPanel.razor")
    assert "ChummerPatternBoundary.ExplainChipClass" in rules.get("must_contain", [])

    dialog_factory = proof_for("chummer6-ui", "Chummer.Presentation/Overview/DesktopDialogFactory.cs")
    assert 'new DesktopDialogField("masterIndexSourceSelectionReceipt"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexCustomDataAuthoringReceipt"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexImportOracleReceipt"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexAdjacentSr6OracleLane"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexOnlineStorageLane"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexOnlineStorageCoverage"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexOnlineStorageReceipt"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexSr6SupplementLane"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexSr6DesignerCoverage"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexHouseRuleLane"' in dialog_factory.get("must_contain", [])
    assert 'new DesktopDialogField("masterIndexSr6SuccessorReceipt"' in dialog_factory.get("must_contain", [])

    dialog_factory_tests = proof_for("chummer6-ui", "Chummer.Tests/Presentation/DesktopDialogFactoryTests.cs")
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexSourceSelectionReceipt")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexCustomDataAuthoringReceipt")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexImportOracleReceipt")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexAdjacentSr6OracleLane")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexOnlineStorageLane")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexOnlineStorageCoverage")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexOnlineStorageReceipt")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexSr6SupplementLane")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexSr6DesignerCoverage")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexHouseRuleLane")'
        in dialog_factory_tests.get("must_contain", [])
    )
    assert (
        'DesktopDialogFieldValueParser.GetValue(dialog, "masterIndexSr6SuccessorReceipt")'
        in dialog_factory_tests.get("must_contain", [])
    )


def test_campaign_session_recover_recap_gate_requires_workspace_v4_and_gm_offline_markers() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    journeys = registry.get("journey_gates") or []
    continuity_gate = next(
        row for row in journeys if isinstance(row, dict) and row.get("id") == "campaign_session_recover_recap"
    )
    assert "chummer6-core" in (continuity_gate.get("owner_repos") or [])
    proofs = continuity_gate.get("fleet_gate", {}).get("repo_source_proof") or []

    def proof_for(repo: str, path: str) -> dict:
        return next(
            row
            for row in proofs
            if isinstance(row, dict)
            and row.get("repo") == repo
            and row.get("path") == path
        )

    hub_spine = proof_for("chummer6-hub", "Chummer.Run.Api/Services/Community/CampaignSpineService.cs")
    assert "governed faction, heat, contact, and reputation signal(s)" in hub_spine.get("must_contain", [])
    assert (
        "governed aftermath package(s) keep return, replay review, and next-session carry-forward"
        in hub_spine.get("must_contain", [])
    )
    assert (
        "travel-prefetch receipt(s) keep the exact offline inventory deliberate and reviewable per claimed device."
        in hub_spine.get("must_contain", [])
    )

    hub_workspace_tests = proof_for("chummer6-hub", "Chummer.Tests/CampaignWorkspaceServerPlaneServiceTests.cs")
    assert 'Title: "Neon Cradle diary, contacts, and heat return packet"' in hub_workspace_tests.get("must_contain", [])
    assert 'Kind: "campaign_diary_packet"' in hub_workspace_tests.get("must_contain", [])
    assert 'Kind: "heat_pressure_lane"' in hub_workspace_tests.get("must_contain", [])
    assert 'Kind: "downtime_brief"' in hub_workspace_tests.get("must_contain", [])
    assert 'Kind: "opposition_packet"' in hub_workspace_tests.get("must_contain", [])
    assert 'Kind: "roster_movement_packet"' in hub_workspace_tests.get("must_contain", [])
    assert 'Kind: "event_control_packet"' in hub_workspace_tests.get("must_contain", [])
    assert 'InvokeBuildTokens("next-session-return-loops")' in hub_workspace_tests.get("must_contain", [])
    assert "PrepLibraryQueryMatchingSupportsCompactGovernedPacketForms" in hub_workspace_tests.get(
        "must_contain",
        [],
    )
    assert 'InvokeBuildTokens("preplibrarypacket")' in hub_workspace_tests.get("must_contain", [])
    assert 'InvokeBuildTokens("oppositionpackets")' in hub_workspace_tests.get("must_contain", [])
    assert 'InvokeBuildTokens("rostermovementpacket")' in hub_workspace_tests.get("must_contain", [])
    assert 'InvokeBuildTokens("eventcontrolpackets")' in hub_workspace_tests.get("must_contain", [])
    assert (
        "PrepLibraryQueryMatchingCollapsesCompactMobileCompanionReturnLoopForms"
        in hub_workspace_tests.get("must_contain", [])
    )
    assert 'InvokeBuildTokens("mobilecompanionreturnloop")' in hub_workspace_tests.get("must_contain", [])
    assert 'InvokeBuildTokens("campaignmobilecompanionsreturnlanes")' in hub_workspace_tests.get("must_contain", [])

    hub_gm_ops_verify = proof_for("chummer6-hub", "tests/RunServicesVerification/GmOpsBoardVerification.cs")
    assert 'EventType: "heat.alert"' in hub_gm_ops_verify.get("must_contain", [])
    assert 'AdditionalTags: ["opposition", "packet"]' in hub_gm_ops_verify.get("must_contain", [])
    assert 'AdditionalTags: ["opposition", "roster"]' in hub_gm_ops_verify.get("must_contain", [])

    hub_gm_ops_service = proof_for("chummer6-hub", "Chummer.Run.AI/Services/Ops/GmOpsBoardService.cs")
    assert 'return "continuity_return";' in hub_gm_ops_service.get("must_contain", [])
    assert '"sync drift",' in hub_gm_ops_service.get("must_contain", [])
    assert '"out-of-sync",' in hub_gm_ops_service.get("must_contain", [])
    assert '"safehouse",' in hub_gm_ops_service.get("must_contain", [])
    assert '"cache stale",' in hub_gm_ops_service.get("must_contain", [])

    hub_gm_ops_tests = proof_for("chummer6-hub", "Chummer.Tests/GmOpsBoardServiceTests.cs")
    assert (
        "GetProjection_UnresolvedItemsTreatOfflineSafehouseTravelCacheStaleSignalsAsContinuityReturnDomain"
        in hub_gm_ops_tests.get("must_contain", [])
    )
    assert (
        "GetProjection_UnresolvedItemsTreatOfflineSyncDriftSignalsAsContinuityReturnDomainWithoutOpenKeyword"
        in hub_gm_ops_tests.get("must_contain", [])
    )
    assert (
        "ListPrepAssets_QuerySupportsGameMasterOpsShorthandAcrossWhitespaceAndPunctuation"
        in hub_gm_ops_tests.get("must_contain", [])
    )

    hub_offline_verify = proof_for("chummer6-hub", "tests/RunServicesVerification/OfflineSyncVerification.cs")
    assert "offline_sync_snapshot_v1" in hub_offline_verify.get("must_contain", [])
    assert (
        "Snapshot should include reusable campaign prep assets for offline library continuity."
        in hub_offline_verify.get("must_contain", [])
    )

    core_workspace_service = proof_for("chummer6-core", "Chummer.Application/Workspaces/WorkspaceService.cs")
    assert (
        "Portable package keeps profile, progress, attributes, skills, inventory, qualities, and contacts on the same governed receipt."
        in core_workspace_service.get("must_contain", [])
    )
    assert (
        "Use the workspace normally or export a portable package when you need a governed cross-surface handoff."
        in core_workspace_service.get("must_contain", [])
    )

    core_heat_service = proof_for("chummer6-core", "Chummer.Application/Simulation/DefaultRelationshipHeatService.cs")
    assert "public HeatComputationResult ComputeHeat(HeatComputationInput input)" in core_heat_service.get(
        "must_contain",
        [],
    )
    assert '< 70m => "heat.high",' in core_heat_service.get("must_contain", [])
    assert "public DowntimeProgressionResult ComputeDowntimeProgression(DowntimeProgressionInput input)" in (
        core_heat_service.get("must_contain", [])
    )

    core_migration_compliance = proof_for("chummer6-core", "Chummer.Tests/Compliance/MigrationComplianceTests.cs")
    assert (
        "public void Relationship_and_heat_simulation_contracts_lock_in_computation_primitives()"
        in core_migration_compliance.get("must_contain", [])
    )
    assert (
        'StringAssert.Contains(simulationContractsText, "public sealed record DowntimeProgressionInput");'
        in core_migration_compliance.get("must_contain", [])
    )
    assert (
        'StringAssert.Contains(simulationServiceText, "heat.low");' in core_migration_compliance.get("must_contain", [])
    )

    core_engine_program = proof_for("chummer6-core", "Chummer.CoreEngine.Tests/Program.cs")
    assert "private static void RelationshipHeatSimulationStaysDeterministic()" in core_engine_program.get(
        "must_contain",
        [],
    )
    assert (
        'AssertEx.Equal("heat.high", heat.ThresholdKey, "Relationship heat should resolve the deterministic threshold band.");'
        in core_engine_program.get("must_contain", [])
    )

    ui_parity_audit = proof_for("chummer6-ui", "scripts/audit-ui-parity.sh")
    assert "dice_roller" in ui_parity_audit.get("must_contain", [])
    assert "character_roster" in ui_parity_audit.get("must_contain", [])

    ui_dialog_factory = proof_for("chummer6-ui", "Chummer.Presentation/Overview/DesktopDialogFactory.cs")
    assert '"dice_roller" => new DesktopDialogState(' in ui_dialog_factory.get("must_contain", [])
    assert '"character_roster" => new DesktopDialogState(' in ui_dialog_factory.get("must_contain", [])
    assert '"dialog.dice_roller"' in ui_dialog_factory.get("must_contain", [])
    assert '"dialog.character_roster"' in ui_dialog_factory.get("must_contain", [])

    ui_gm_board = proof_for("chummer6-ui", "Chummer.Blazor/Components/Shared/GmBoardFeed.razor")
    assert "<header class=\"trace-section-title\">Initiative Rail</header>" in ui_gm_board.get("must_contain", [])
    assert "<div class=\"gm-board-initiative-strip\">" in ui_gm_board.get("must_contain", [])
    assert "data-gm-board-initiative-pill=" in ui_gm_board.get("must_contain", [])

    ui_roster_watch_folder = proof_for("chummer6-ui", "Chummer/Forms/Utility Forms/CharacterRoster.cs")
    assert (
        "new FileSystemWatcher(GlobalSettings.CharacterRosterPath, \"*.chum5*\")"
        in ui_roster_watch_folder.get("must_contain", [])
    )
    assert (
        "Log.Trace(\"Populating CharacterRosterTreeNode Watch Folder (MainThread).\")"
        in ui_roster_watch_folder.get("must_contain", [])
    )

    hub_dashboard_contracts = proof_for("chummer6-hub", "Chummer.Run.Contracts/CompatCore/Presentation/WorkflowSurfaceContracts.cs")
    assert 'public const string Dashboard = "dashboard";' in hub_dashboard_contracts.get("must_contain", [])
    assert 'public const string SessionDashboard = "session-dashboard";' in hub_dashboard_contracts.get("must_contain", [])

    mobile_local_release_proof = proof_for(
        "chummer6-mobile",
        ".codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json",
    )
    assert 'Assert(projection.ContinuityRailSummary.Contains(\\"Downtime:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.ContinuityRailSummary.Contains(\\"Diary:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.ContinuityRailSummary.Contains(\\"Contacts:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.ContinuityRailSummary.Contains(\\"Heat:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.ContinuityRailSummary.Contains(\\"Aftermath:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.ContinuityRailSummary.Contains(\\"Return:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsSummary.Contains(\\"Opposition:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsSummary.Contains(\\"Roster movement:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsSummary.Contains(\\"Prep library:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsSummary.Contains(\\"Event controls:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsLabels.Any(item => item.Contains(\\"Opposition lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsLabels.Any(item => item.Contains(\\"Roster movement lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsLabels.Any(item => item.Contains(\\"Prep library lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsLabels.Any(item => item.Contains(\\"Event controls lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.GmOperationsLabels.Any(item => item.Contains(\\"Governance lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(projection.OfflineTruthSummary.Contains(\\"Stale:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(plan.TravelCompanionSummary.Contains(\\"Cached:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(plan.TravelCompanionSummary.Contains(\\"Stale:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(plan.TravelCompanionSummary.Contains(\\"Offline actions:\\", StringComparison.Ordinal)' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(plan.TravelCompanionLabels.Any(item => item.Contains(\\"Cached lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(plan.TravelCompanionLabels.Any(item => item.Contains(\\"Stale lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'Assert(plan.TravelCompanionLabels.Any(item => item.Contains(\\"Offline action lane:\\", StringComparison.Ordinal))' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"workspace-continuity-rail\\"' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"workspace-continuity-rail-list\\"' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"workspace-gm-ops\\"' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"workspace-gm-ops-list\\"' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"workspace-offline-truth\\"' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"restore-offline-truth\\"' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"restore-travel-companion\\"' in mobile_local_release_proof.get("must_contain", [])
    assert 'id=\\"restore-travel-companion-labels\\"' in mobile_local_release_proof.get("must_contain", [])

    required_project_posture = continuity_gate.get("fleet_gate", {}).get("required_project_posture") or []
    core_posture = next(
        row for row in required_project_posture if isinstance(row, dict) and row.get("project_id") == "core"
    )
    assert core_posture.get("minimum_stage") == "boundary_pure"
    assert core_posture.get("target_stage") == "boundary_pure"

    executive_assistant_skill_catalog = proof_for("executive-assistant", "SKILLS.md")
    assert "`gm_ops_briefing`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`opposition_packet`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`roster_movement_plan`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`prep_library_packet`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`event_control_brief`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_downtime_plan`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_diary_packet`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_contacts_update`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_heat_brief`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_aftermath_packet`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_return_loop_brief`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_safehouse_readiness_brief`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_travel_continuity_packet`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_offline_continuity_brief`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_mobile_companion_brief`" in executive_assistant_skill_catalog.get("must_contain", [])
    assert "`campaign_workspace_v4_brief`" in executive_assistant_skill_catalog.get("must_contain", [])

    executive_assistant_runtime_contracts = proof_for(
        "executive-assistant",
        "ea/app/services/task_contracts.py",
    )
    assert '"gm_ops_briefing",' in executive_assistant_runtime_contracts.get("must_contain", [])
    assert '"campaign_workspace_v4_brief",' in executive_assistant_runtime_contracts.get("must_contain", [])
    assert '"gm_ops_briefing": "gm_ops_brief",' in executive_assistant_runtime_contracts.get("must_contain", [])
    assert (
        '"campaign_workspace_v4_brief": "campaign_workspace_v4_brief",'
        in executive_assistant_runtime_contracts.get("must_contain", [])
    )
    assert (
        "W3_CONTRACT_SKILL_MEMORY_READS: dict[str, tuple[str, ...]] = {"
        in executive_assistant_runtime_contracts.get("must_contain", [])
    )
    assert '"campaign_workspace_v4_brief": (' in executive_assistant_runtime_contracts.get("must_contain", [])
    assert '"offline_actions",' in executive_assistant_runtime_contracts.get("must_contain", [])
    assert (
        "W3_CONTRACT_SKILL_MEMORY_WRITES: dict[str, str] = {"
        in executive_assistant_runtime_contracts.get("must_contain", [])
    )
    assert (
        '"campaign_workspace_v4_brief": "campaign_workspace_v4_fact",'
        in executive_assistant_runtime_contracts.get("must_contain", [])
    )
    assert '"workflow_template": "tool_then_artifact",' in executive_assistant_runtime_contracts.get("must_contain", [])
    assert (
        '"pre_artifact_capability_key": "structured_generate",'
        in executive_assistant_runtime_contracts.get("must_contain", [])
    )
    assert '"memory_reads": list(memory_reads),' in executive_assistant_runtime_contracts.get("must_contain", [])
    assert (
        '"memory_writes": [memory_write_key] if memory_write_key else [],'
        in executive_assistant_runtime_contracts.get("must_contain", [])
    )
    assert (
        '"primary": ["Gemini Vortex", "AI Magicx", "BrowserAct"],'
        in executive_assistant_runtime_contracts.get("must_contain", [])
    )

    executive_assistant_runtime_policy_tests = proof_for(
        "executive-assistant",
        "tests/test_task_contract_runtime_policy.py",
    )
    assert (
        "def test_builtin_w3_campaign_and_gm_contracts_resolve_with_groundwork_runtime_policy("
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        "def test_builtin_w3_gm_ops_contract_projects_lane_memory_metadata() -> None:"
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        "def test_builtin_w3_mobile_continuity_contract_projects_safehouse_travel_offline_reads() -> None:"
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        "def test_builtin_w3_workspace_v4_contract_projects_unified_campaign_gm_and_offline_reads() -> None:"
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert '("gm_ops_briefing", "gm_ops_brief"),' in executive_assistant_runtime_policy_tests.get("must_contain", [])
    assert (
        '("campaign_workspace_v4_brief", "campaign_workspace_v4_brief"),'
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        'assert runtime_policy.workflow_template_key == "tool_then_artifact"'
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        'assert runtime_policy.pre_artifact_capability_key == "structured_generate"'
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        'assert runtime_policy.skill_catalog.memory_writes == ("gm_ops_brief_fact",)'
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        'assert runtime_policy.skill_catalog.memory_writes == ("campaign_mobile_companion_fact",)'
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )
    assert (
        'assert runtime_policy.skill_catalog.memory_writes == ("campaign_workspace_v4_fact",)'
        in executive_assistant_runtime_policy_tests.get("must_contain", [])
    )


def test_install_claim_restore_continue_requires_fresh_desktop_executable_exit_gate_proof() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    journeys = registry.get("journey_gates") or []
    install_gate = next(
        row for row in journeys if isinstance(row, dict) and row.get("id") == "install_claim_restore_continue"
    )
    proofs = install_gate.get("fleet_gate", {}).get("repo_source_proof") or []
    desktop_exit_proof = next(
        row
        for row in proofs
        if isinstance(row, dict)
        and row.get("repo") == "chummer6-ui"
        and row.get("path") == ".codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
    )
    assert desktop_exit_proof.get("json_must_equal") == {
        "local_blocking_findings_count": 0,
        "evidence.hub_registry_root_trusted_for_startup_smoke_proof": True,
        "evidence.flagship_status": "pass",
        "evidence.visual_familiarity_status": "pass",
        "evidence.workflow_execution_status": "pass",
        "evidence.receipt_scope.windows_gate:avalonia:win-x64.within_repo_root": True,
        "evidence.receipt_scope.windows_gate:blazor-desktop:win-x64.within_repo_root": True,
        "evidence.receipt_scope.linux_gate:avalonia:linux-x64.within_repo_root": True,
        "evidence.receipt_scope.linux_gate:blazor-desktop:linux-x64.within_repo_root": True,
        "evidence.receipt_scope.macos_gate:avalonia:osx-arm64.within_repo_root": True,
        "evidence.receipt_scope.macos_gate:blazor-desktop:osx-arm64.within_repo_root": True,
    }
    assert desktop_exit_proof.get("max_age_hours") == 48
    assert desktop_exit_proof.get("generated_at_fields") == ["generated_at", "generatedAt"]
    required_markers = desktop_exit_proof.get("must_contain", [])
    assert '"local_blocking_findings_count": 0' in required_markers
    assert '"windows_gate:avalonia:win-x64"' in required_markers
    assert '"windows_gate:blazor-desktop:win-x64"' in required_markers
    assert '"linux_gate:avalonia:linux-x64"' in required_markers
    assert '"linux_gate:blazor-desktop:linux-x64"' in required_markers
    assert '"macos_gate:avalonia:osx-arm64"' in required_markers
    assert '"macos_gate:blazor-desktop:osx-arm64"' in required_markers

    release_channel_proof = next(
        row
        for row in proofs
        if isinstance(row, dict)
        and row.get("repo") == "chummer6-hub-registry"
        and row.get("path") == ".codex-studio/published/RELEASE_CHANNEL.generated.json"
    )
    assert release_channel_proof.get("json_must_equal") == {
        "releaseProof.status": "passed",
        "desktopTupleCoverage.missingRequiredPlatforms": [],
        "desktopTupleCoverage.missingRequiredPlatformHeadPairs": [],
        "desktopTupleCoverage.missingRequiredPlatformHeadRidTuples": [],
    }
    assert release_channel_proof.get("json_must_be_one_of") == {"status": ["published", "publishable"]}
    assert release_channel_proof.get("json_must_be_non_empty_string") == {
        "contract_name": True,
        "releaseProof.generatedAt": True,
        "rolloutReason": True,
        "supportabilitySummary": True,
        "knownIssueSummary": True,
        "fixAvailabilitySummary": True,
    }
    assert release_channel_proof.get("max_age_hours") == 48
    assert release_channel_proof.get("generated_at_fields") == ["generated_at", "generatedAt"]
    release_channel_markers = release_channel_proof.get("must_contain", [])
    assert '"desktopTupleCoverage"' in release_channel_markers
    assert '"releaseProof"' in release_channel_markers
    assert '"status": "passed"' in release_channel_markers
    assert '"missingRequiredPlatforms"' in release_channel_markers
    assert '"missingRequiredPlatformHeadPairs"' in release_channel_markers
    assert '"missingRequiredPlatformHeadRidTuples"' in release_channel_markers

    hub_local_release_proof = next(
        row
        for row in proofs
        if isinstance(row, dict)
        and row.get("repo") == "chummer6-hub"
        and row.get("path") == ".codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json"
    )
    assert hub_local_release_proof.get("max_age_hours") == 48
    assert hub_local_release_proof.get("generated_at_fields") == ["generated_at", "generatedAt"]

    mobile_local_release_proof = next(
        row
        for row in proofs
        if isinstance(row, dict)
        and row.get("repo") == "chummer6-mobile"
        and row.get("path") == ".codex-studio/published/MOBILE_LOCAL_RELEASE_PROOF.generated.json"
    )
    assert mobile_local_release_proof.get("max_age_hours") == 48
    assert mobile_local_release_proof.get("generated_at_fields") == ["generated_at", "generatedAt"]


def test_report_cluster_release_notify_requires_support_install_truth_contract() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    journeys = registry.get("journey_gates") or []
    support_gate = next(
        row for row in journeys if isinstance(row, dict) and row.get("id") == "report_cluster_release_notify"
    )
    fleet_gate = support_gate.get("fleet_gate") or {}
    assert fleet_gate.get("require_support_freshness") is True
    assert fleet_gate.get("require_support_closure_waiting_zero") is True
    assert fleet_gate.get("require_support_update_required_routes_to_downloads") is True
    assert fleet_gate.get("require_support_install_truth_contract") is True
    assert fleet_gate.get("require_support_recovery_path_contract") is True
    proofs = [row for row in (fleet_gate.get("repo_source_proof") or []) if isinstance(row, dict)]
    release_channel_proof = next(
        row
        for row in proofs
        if row.get("repo") == "chummer6-hub-registry"
        and row.get("path") == ".codex-studio/published/RELEASE_CHANNEL.generated.json"
    )
    assert release_channel_proof.get("json_must_be_one_of") == {"status": ["published", "publishable"]}
    assert release_channel_proof.get("must_contain") == ['"desktopTupleCoverage"', '"externalProofRequests"']
    assert release_channel_proof.get("max_age_hours") == 48
    assert release_channel_proof.get("generated_at_fields") == ["generated_at", "generatedAt"]


def test_materialize_journey_gates_blocks_when_support_tuple_gap_lacks_external_proof_contract(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Support closure stays install-specific.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 1
      require_support_install_truth_contract: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {"external_proof_required_case_count": 0},
                "packets": [
                    {
                        "packet_id": "packet-a",
                        "status": "accepted",
                        "install_truth_state": "tuple_not_on_promoted_shelf",
                        "install_diagnosis": {
                            "registry_channel_id": "preview",
                            "registry_release_channel_status": "published",
                            "registry_release_version": "1.2.3",
                            "registry_release_proof_status": "passed",
                        },
                        "fix_confirmation": {"state": "no_fix_recorded", "update_required": False},
                        "recovery_path": {"action_id": "open_downloads", "href": "/downloads"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reasons = payload["journeys"][0]["blocking_reasons"]
    assert any("external_proof_required" in reason for reason in reasons)


def test_materialize_journey_gates_accepts_support_external_proof_contract_when_present(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Support closure stays install-specific.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 1
      require_support_install_truth_contract: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {
                    "external_proof_required_case_count": 1,
                    "external_proof_required_host_counts": {"windows": 1},
                    "external_proof_required_tuple_counts": {"avalonia:win-x64:windows": 1},
                },
                "packets": [
                    {
                        "packet_id": "packet-a",
                        "status": "accepted",
                        "install_truth_state": "tuple_not_on_promoted_shelf",
                        "install_diagnosis": {
                            "registry_channel_id": "preview",
                            "registry_release_channel_status": "published",
                            "registry_release_version": "1.2.3",
                            "registry_release_proof_status": "passed",
                            "external_proof_required": True,
                            "external_proof_request": {
                                "tuple_id": "avalonia:win-x64:windows",
                                "channel_id": "preview",
                                "required_host": "windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "startup_smoke_receipt_contract": {
                                    "status_any_of": ["pass", "passed", "ready"],
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                },
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                    "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                                ],
                            },
                        },
                        "fix_confirmation": {"state": "no_fix_recorded", "update_required": False},
                        "recovery_path": {"action_id": "open_downloads", "href": "/downloads"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    journey = payload["journeys"][0]
    assert journey["state"] == "ready"
    assert journey["signals"]["support_external_proof_required_case_count"] == 1


def test_materialize_journey_gates_blocks_when_support_external_proof_request_is_missing_expected_targets(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Support closure stays install-specific.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 1
      require_support_install_truth_contract: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {"external_proof_required_case_count": 1},
                "packets": [
                    {
                        "packet_id": "packet-a",
                        "status": "accepted",
                        "install_truth_state": "tuple_not_on_promoted_shelf",
                        "install_diagnosis": {
                            "registry_channel_id": "preview",
                            "registry_release_channel_status": "published",
                            "registry_release_version": "1.2.3",
                            "registry_release_proof_status": "passed",
                            "external_proof_required": True,
                            "external_proof_request": {
                                "tuple_id": "avalonia:win-x64:windows",
                                "channel_id": "preview",
                                "required_host": "windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "startup_smoke_receipt_contract": {
                                    "status_any_of": ["pass", "passed", "ready"],
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                },
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                    "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                                ],
                            },
                        },
                        "fix_confirmation": {"state": "no_fix_recorded", "update_required": False},
                        "recovery_path": {"action_id": "open_downloads", "href": "/downloads"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reasons = payload["journeys"][0]["blocking_reasons"]
    assert any("expected_public_install_route" in reason for reason in reasons)


def test_materialize_journey_gates_blocks_when_support_external_proof_commands_do_not_match_host_or_installer(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Support closure stays install-specific.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 1
      require_support_install_truth_contract: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {"external_proof_required_case_count": 1},
                "packets": [
                    {
                        "packet_id": "packet-a",
                        "status": "accepted",
                        "install_truth_state": "tuple_not_on_promoted_shelf",
                        "install_diagnosis": {
                            "registry_channel_id": "preview",
                            "registry_release_channel_status": "published",
                            "registry_release_version": "1.2.3",
                            "registry_release_proof_status": "passed",
                            "external_proof_required": True,
                            "external_proof_request": {
                                "tuple_id": "avalonia:win-x64:windows",
                                "channel_id": "preview",
                                "required_host": "windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "startup_smoke_receipt_contract": {
                                    "status_any_of": ["pass", "passed", "ready"],
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                },
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=linux-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-wrong-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke"
                                ],
                            },
                        },
                        "fix_confirmation": {"state": "no_fix_recorded", "update_required": False},
                        "recovery_path": {"action_id": "open_downloads", "href": "/downloads"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reasons = payload["journeys"][0]["blocking_reasons"]
    assert any("does not reference expected installer file" in reason for reason in reasons)
    assert any("does not declare expected host token" in reason for reason in reasons)


def test_materialize_journey_gates_blocks_when_support_external_proof_required_summary_host_or_tuple_counts_drift(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"
    generated_at = fresh_timestamp()

    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report, cluster, release, notify
    user_promise: Support closure stays install-specific.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 1
      require_support_install_truth_contract: true
      required_project_posture:
        - project_id: hub
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        f"""
contract_name: fleet.status_plane
schema_version: 1
generated_at: '{generated_at}'
projects:
  - id: hub
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": generated_at, "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": generated_at, "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "summary": {
                    "external_proof_required_case_count": 1,
                    "external_proof_required_host_counts": {"macos": 1},
                    "external_proof_required_tuple_counts": {"avalonia:osx-arm64:macos": 1},
                },
                "packets": [
                    {
                        "packet_id": "packet-a",
                        "status": "accepted",
                        "install_truth_state": "tuple_not_on_promoted_shelf",
                        "install_diagnosis": {
                            "registry_channel_id": "preview",
                            "registry_release_channel_status": "published",
                            "registry_release_version": "1.2.3",
                            "registry_release_proof_status": "passed",
                            "external_proof_required": True,
                            "external_proof_request": {
                                "tuple_id": "avalonia:win-x64:windows",
                                "channel_id": "preview",
                                "required_host": "windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "startup_smoke_receipt_contract": {
                                    "status_any_of": ["pass", "passed", "ready"],
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                },
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                    "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                                ],
                            },
                        },
                        "fix_confirmation": {"state": "no_fix_recorded", "update_required": False},
                        "recovery_path": {"action_id": "open_downloads", "href": "/downloads"},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--registry",
            str(registry),
            "--status-plane",
            str(status_plane),
            "--progress-report",
            str(progress_report),
            "--progress-history",
            str(progress_history),
            "--support-packets",
            str(support_packets),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    reasons = payload["journeys"][0]["blocking_reasons"]
    assert any("external_proof_required_host_counts does not match" in reason for reason in reasons)
    assert any("external_proof_required_tuple_counts does not match" in reason for reason in reasons)
