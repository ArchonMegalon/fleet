from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_journey_gates.py")
REGISTRY = Path("/docker/fleet/.codex-design/product/GOLDEN_JOURNEY_RELEASE_GATES.yaml")
UTC = dt.timezone.utc


def fresh_timestamp(hours_ago: int = 1) -> str:
    return (dt.datetime.now(UTC) - dt.timedelta(hours=hours_ago)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    assert journey["signals"]["support_install_truth_contract_violation_count"] == 4
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
    assert 'response["customDataLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["xmlBridgeLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["translatorLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["importOracleLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["importOracleMissingSources"]' in core_api.get("must_contain", [])
    assert 'response["adjacentSr6OracleReceiptPosture"]' in core_api.get("must_contain", [])
    assert 'response["adjacentSr6OracleSourcesCovered"]' in core_api.get("must_contain", [])
    assert 'response["sr6SuccessorLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'response["onlineStorageLanePosture"]' in core_api.get("must_contain", [])
    assert 'response["onlineStorageReceiptPosture"]' in core_api.get("must_contain", [])
    assert 'response["onlineStorageLaneReceipt"]' in core_api.get("must_contain", [])
    assert 'firstSourcebook["referenceSnapshotPosture"]' in core_api.get("must_contain", [])

    core_tool_catalog = proof_for("chummer6-core", "Chummer.Infrastructure/Xml/XmlToolCatalogService.cs")
    assert "BuildReferenceSourceLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildSettingsLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildSourceToggleLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildCustomDataLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildXmlBridgeLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildTranslatorLaneReceipt" in core_tool_catalog.get("must_contain", [])
    assert "BuildImportOracleLaneReceipt" in core_tool_catalog.get("must_contain", [])
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


def test_campaign_session_recover_recap_gate_requires_workspace_v4_and_gm_offline_markers() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    journeys = registry.get("journey_gates") or []
    continuity_gate = next(
        row for row in journeys if isinstance(row, dict) and row.get("id") == "campaign_session_recover_recap"
    )
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
    assert 'InvokeBuildTokens("next-session-return-loops")' in hub_workspace_tests.get("must_contain", [])

    hub_gm_ops_verify = proof_for("chummer6-hub", "tests/RunServicesVerification/GmOpsBoardVerification.cs")
    assert 'EventType: "heat.alert"' in hub_gm_ops_verify.get("must_contain", [])
    assert 'AdditionalTags: ["opposition", "packet"]' in hub_gm_ops_verify.get("must_contain", [])
    assert 'AdditionalTags: ["opposition", "roster"]' in hub_gm_ops_verify.get("must_contain", [])

    hub_offline_verify = proof_for("chummer6-hub", "tests/RunServicesVerification/OfflineSyncVerification.cs")
    assert "offline_sync_snapshot_v1" in hub_offline_verify.get("must_contain", [])
    assert (
        "Snapshot should include reusable campaign prep assets for offline library continuity."
        in hub_offline_verify.get("must_contain", [])
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
        "status": "pass",
        "blocking_findings_count": 0,
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
    assert '"status": "pass"' in required_markers
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
