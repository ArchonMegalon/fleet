from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SUPPORT_SCRIPT = Path("/docker/fleet/scripts/materialize_support_case_packets.py")
JOURNEY_SCRIPT = Path("/docker/fleet/scripts/materialize_journey_gates.py")


def test_support_packets_project_startup_smoke_receipt_contract(tmp_path: Path) -> None:
    intake = tmp_path / "SUPPORT_INTAKE.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    out_path = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"

    intake.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-04T18:00:00Z",
                "cases": [
                    {
                        "id": "case-1",
                        "status": "accepted",
                        "kind": "install",
                        "targetRepo": "chummer6-ui",
                        "releaseChannel": "docker",
                        "headId": "avalonia",
                        "platform": "windows",
                        "arch": "x64",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "docker",
                "status": "published",
                "desktopTupleCoverage": {
                    "promotedInstallerTuples": [],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "head": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "startupSmokeReceiptContract": {
                                "status_any_of": ["pass", "passed", "ready"],
                                "ready_checkpoint": "pre_ui_event_loop",
                                "head_id": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "host_class_contains": "windows",
                            },
                        }
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SUPPORT_SCRIPT),
            "--source",
            str(intake),
            "--release-channel",
            str(release_channel),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    request = payload["packets"][0]["install_diagnosis"]["external_proof_request"]
    assert request["startup_smoke_receipt_contract"]["ready_checkpoint"] == "pre_ui_event_loop"
    assert request["startup_smoke_receipt_contract"]["host_class_contains"] == "windows"
    assert request["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]


def test_journey_gate_requires_support_startup_smoke_receipt_contract(tmp_path: Path) -> None:
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
    owner_repos: [chummer6-hub-registry, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 1
      require_support_install_truth_contract: true
      required_project_posture:
        - project_id: hub-registry
          minimum_stage: pre_repo_local_complete
""".strip()
        + "\n",
        encoding="utf-8",
    )
    status_plane.write_text(
        """
contract_name: fleet.status_plane
schema_version: 1
generated_at: '2026-04-04T18:00:00Z'
projects:
  - id: hub-registry
    readiness_stage: pre_repo_local_complete
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    progress_report.write_text(
        json.dumps({"generated_at": "2026-04-04T18:00:00Z", "history_snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    progress_history.write_text(
        json.dumps({"generated_at": "2026-04-04T18:00:00Z", "snapshot_count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    support_packets.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-04T18:00:00Z",
                "summary": {"external_proof_required_case_count": 1},
                "packets": [
                    {
                        "packet_id": "case-1",
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
                                "required_host": "windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
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
            str(JOURNEY_SCRIPT),
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
    blocking = payload["journeys"][0]["blocking_reasons"]
    assert any(
        "external_proof_request.startup_smoke_receipt_contract" in reason
        for reason in blocking
    )
