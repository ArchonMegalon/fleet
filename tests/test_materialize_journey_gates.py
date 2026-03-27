from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_journey_gates.py")


def test_materialize_journey_gates_emits_warning_when_target_posture_lags(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"

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
        """
contract_name: fleet.status_plane
schema_version: 1
generated_at: '2026-03-27T13:25:43Z'
projects:
  - id: ui
    readiness_stage: pre_repo_local_complete
    deployment_promotion_stage: protected_preview
  - id: hub
    readiness_stage: pre_repo_local_complete
    deployment_promotion_stage: protected_preview
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": "2026-03-27T13:25:43Z", "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": "2026-03-27T13:25:43Z", "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-27T13:25:43Z",
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


def test_materialize_journey_gates_blocks_on_missing_required_project(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"

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
        """
contract_name: fleet.status_plane
schema_version: 1
generated_at: '2026-03-27T13:25:43Z'
projects: []
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": "2026-03-27T13:25:43Z", "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": "2026-03-27T13:25:43Z", "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-27T13:25:43Z",
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


def test_materialize_journey_gates_blocks_when_repo_source_proof_marker_is_missing(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out_path = tmp_path / "JOURNEY_GATES.generated.json"

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
        """
contract_name: fleet.status_plane
schema_version: 1
generated_at: '2026-03-27T13:25:43Z'
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
        json.dumps({"generated_at": "2026-03-27T13:25:43Z", "history_snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": "2026-03-27T13:25:43Z", "snapshot_count": 2}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps({"generated_at": "2026-03-27T13:25:43Z", "summary": {}, "packets": []}, indent=2) + "\n",
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
