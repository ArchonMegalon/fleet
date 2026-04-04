from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_journey_gates.py")
MODULE_SPEC = importlib.util.spec_from_file_location("materialize_journey_gates_module_external_contract", SCRIPT)
assert MODULE_SPEC and MODULE_SPEC.loader
JOURNEY_GATES_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(JOURNEY_GATES_MODULE)


def test_external_proof_requests_include_startup_smoke_contract_fields() -> None:
    payload = {
        "channelId": "stable",
        "desktopTupleCoverage": {
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:win-x64:windows",
                    "requiredHost": "windows",
                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                }
            ]
        }
    }

    requests = JOURNEY_GATES_MODULE._release_channel_external_proof_requests(payload)
    assert requests[0]["channel_id"] == "stable"
    assert requests[0]["head_id"] == "avalonia"
    assert requests[0]["rid"] == "win-x64"
    assert requests[0]["platform"] == "windows"
    assert requests[0]["startup_smoke_receipt_contract"] == {
        "status_any_of": ["pass", "passed", "ready"],
        "ready_checkpoint": "pre_ui_event_loop",
        "head_id": "avalonia",
        "platform": "windows",
        "rid": "win-x64",
        "host_class_contains": "windows",
    }
    assert requests[0]["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]


def test_external_proof_requests_project_contract_into_install_journey(tmp_path: Path) -> None:
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
        json.dumps({"generated_at": "2026-04-04T18:00:00Z", "summary": {}, "packets": []}, indent=2) + "\n",
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
    request = next(item for item in journey["external_proof_requests"] if item["tuple_id"] == "avalonia:win-x64:windows")
    assert request["startup_smoke_receipt_contract"]["ready_checkpoint"] == "pre_ui_event_loop"
    assert request["startup_smoke_receipt_contract"]["host_class_contains"] == "windows"
    assert request["proof_capture_commands"] == [
        "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
    ]


def test_external_proof_reasons_reject_noncanonical_tuple_spec_fields() -> None:
    payload = {
        "channelId": "stable",
        "desktopTupleCoverage": {
            "complete": False,
            "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
            "externalProofRequests": [
                {
                    "tupleId": "avalonia:win-x64:windows",
                    "requiredHost": "windows",
                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    "expectedArtifactId": "wrong-artifact",
                    "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                    "expectedPublicInstallRoute": "/downloads/install/not-canonical",
                    "expectedStartupSmokeReceiptPath": "startup-smoke/not-canonical.receipt.json",
                    "startupSmokeReceiptContract": {
                        "statusAnyOf": ["pass", "passed", "ready"],
                        "readyCheckpoint": "pre_ui_event_loop",
                        "headId": "avalonia",
                        "platform": "windows",
                        "rid": "win-x64",
                        "hostClassContains": "linux",
                    },
                    "proofCaptureCommands": [
                        "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh"
                    ],
                }
            ],
        },
    }

    reasons = JOURNEY_GATES_MODULE._release_channel_external_proof_reasons(payload)
    assert any("expectedArtifactId' must match tuple-derived canonical value" in reason for reason in reasons)
    assert any("expectedPublicInstallRoute' must match tuple-derived canonical value" in reason for reason in reasons)
    assert any("expectedStartupSmokeReceiptPath' must match tuple-derived canonical value" in reason for reason in reasons)
    assert any("startupSmokeReceiptContract' must match tuple-derived canonical value" in reason for reason in reasons)
    assert any("proofCaptureCommands' must match tuple-derived canonical command sequence" in reason for reason in reasons)


def test_install_journey_blocks_when_support_external_proof_backlog_summary_drifts(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "stable",
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "unresolved_external_proof_request_count": 0,
                    "unresolved_external_proof_request_host_counts": {},
                    "unresolved_external_proof_request_tuple_counts": {},
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "unresolved_external_proof_request_count does not match release-channel external proof backlog"
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_backlog_hosts_or_tuples_lists_drift(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["macos"],
                    "unresolved_external_proof_request_tuples": ["avalonia:osx-arm64:macos"],
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "unresolved_external_proof_request_hosts does not match release-channel external proof backlog" in reason
        for reason in journey["blocking_reasons"]
    )
    assert any(
        "unresolved_external_proof_request_tuples does not match release-channel external proof backlog" in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_backlog_specs_drift(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "required_host": "windows",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expected_artifact_id": "avalonia-win-x64-installer",
                            "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                            "expected_public_install_route": "/downloads/install/WRONG-route",
                            "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startup_smoke_receipt_contract": {
                                "ready_checkpoint": "pre_ui_event_loop",
                                "head_id": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "host_class_contains": "windows",
                                "status_any_of": ["pass", "passed", "ready"],
                            },
                            "proof_capture_commands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    },
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "unresolved_external_proof_request_specs does not match release-channel external proof backlog" in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_summary_tuple_metadata_drifts(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "preview",
                            "tuple_entry_count": 2,
                            "tuple_unique": False,
                            "required_host": "windows",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expected_artifact_id": "avalonia-win-x64-installer",
                            "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                            "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                            "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startup_smoke_receipt_contract": {
                                "ready_checkpoint": "pre_ui_event_loop",
                                "head_id": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "host_class_contains": "windows",
                                "status_any_of": ["pass", "passed", "ready"],
                            },
                            "proof_capture_commands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    },
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "unresolved_external_proof_request_specs does not match release-channel external proof backlog" in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_execution_plan_drifts(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "external_proof_required_host_counts": {},
                    "external_proof_required_tuple_counts": {},
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "preview",
                            "tuple_entry_count": 1,
                            "tuple_unique": True,
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
                        }
                    },
                },
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "tuple_entry_count": 1,
                                    "tuple_unique": False,
                                    "channel_id": "preview",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "required_proofs": [
                                        "promoted_installer_artifact",
                                        "startup_smoke_receipt",
                                    ],
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
                                }
                            ],
                        }
                    },
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "unresolved_external_proof_execution_plan does not match release-channel external proof backlog" in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_summary_tuple_unique_field_is_missing(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "complete": False,
                    "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                    "missingRequiredPlatforms": ["windows"],
                    "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        },
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        },
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "preview",
                            "tuple_entry_count": 2,
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
                        }
                    },
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert int(journey["signals"]["support_install_truth_contract_violation_count"]) > 0


def test_install_journey_blocks_when_support_external_proof_execution_plan_tuple_unique_field_is_missing(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "complete": False,
                    "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                    "missingRequiredPlatforms": ["windows"],
                    "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        },
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        },
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "external_proof_required_host_counts": {},
                    "external_proof_required_tuple_counts": {},
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "preview",
                            "tuple_entry_count": 2,
                            "tuple_unique": False,
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
                        }
                    },
                },
                "unresolved_external_proof_execution_plan": {
                    "request_count": 1,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 1,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "tuple_entry_count": 2,
                                    "channel_id": "preview",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "required_proofs": [
                                        "promoted_installer_artifact",
                                        "startup_smoke_receipt",
                                    ],
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
                                }
                            ],
                        }
                    },
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert int(journey["signals"]["support_install_truth_contract_violation_count"]) > 0


def test_report_journey_projects_release_channel_external_backlog_without_json_must_equal(tmp_path: Path) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    registry.write_text(
        """
product: chummer
surface: release_control
version: 1
journey_gates:
  - id: report_cluster_release_notify
    title: Report
    user_promise: Report flow.
    canonical_journeys:
      - journeys/claim-install-and-close-a-support-case.md
    owner_repos: [chummer6-hub-registry, fleet]
    scorecard_refs: {}
    fleet_gate:
      required_artifacts: [status_plane, progress_report, support_packets]
      minimum_history_snapshots: 1
      require_support_install_truth_contract: true
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_be_one_of:
            status: [published, publishable]
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "required_host": "windows",
                            "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expected_artifact_id": "",
                            "expected_installer_file_name": "",
                            "expected_public_install_route": "",
                            "expected_startup_smoke_receipt_path": "",
                            "startup_smoke_receipt_contract": {
                                "ready_checkpoint": "pre_ui_event_loop",
                                "head_id": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "host_class_contains": "windows",
                                "status_any_of": ["pass", "passed", "ready"],
                            },
                            "proof_capture_commands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    },
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "externalProofRequests.expectedArtifactId' must be explicit for tuple avalonia:win-x64:windows"
        in reason
        for reason in journey["blocking_reasons"]
    )
    assert any(
        "externalProofRequests.proofCaptureCommands' must be explicit for tuple avalonia:win-x64:windows"
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_tuple_fields_drift_from_release_channel(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 1,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                },
                "packets": [
                    {
                        "packet_id": "packet-a",
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
                                "expected_public_install_route": "/downloads/install/wrong-route",
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "external_proof_request.expected_public_install_route must match release-channel tuple truth"
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_tuple_uniqueness_fields_drift(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 1,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                },
                "packets": [
                    {
                        "packet_id": "packet-a",
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
                                "tuple_entry_count": 2,
                                "tuple_unique": False,
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "external_proof_request.tuple_entry_count must match release-channel tuple truth" in reason
        for reason in journey["blocking_reasons"]
    )
    assert any(
        "external_proof_request.tuple_unique must match release-channel tuple truth" in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_tuple_unique_field_is_missing(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        },
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        },
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 1,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                },
                "packets": [
                    {
                        "packet_id": "packet-a",
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
                                "tuple_entry_count": 2,
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "is missing boolean install_diagnosis.external_proof_request.tuple_unique." in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_tuple_entry_count_field_is_boolean(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 1,
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                },
                "packets": [
                    {
                        "packet_id": "packet-a",
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
                                "tuple_entry_count": True,
                                "tuple_unique": True,
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "is missing integer install_diagnosis.external_proof_request.tuple_entry_count." in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_commands_include_noncanonical_extras(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 1,
                    "external_proof_required_host_counts": {"windows": 1},
                    "external_proof_required_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "",
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
                        }
                    },
                },
                "packets": [
                    {
                        "packet_id": "packet-a",
                        "install_truth_state": "tuple_not_on_promoted_shelf",
                        "install_diagnosis": {
                            "registry_channel_id": "",
                            "registry_release_channel_status": "published",
                            "registry_release_version": "1.2.3",
                            "registry_release_proof_status": "passed",
                            "external_proof_required": True,
                            "external_proof_request": {
                                "tuple_id": "avalonia:win-x64:windows",
                                "channel_id": "",
                                "tuple_entry_count": 1,
                                "tuple_unique": True,
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
                                    "echo noncanonical extra command",
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "external_proof_request.proof_capture_commands must exactly match release-channel tuple truth command sequence"
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_accepts_case_backed_external_proof_summary_with_operator_packets(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "external_proof_required_host_counts": {},
                    "external_proof_required_tuple_counts": {},
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
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
                        }
                    },
                },
                "packets": [
                    {
                        "packet_id": "operator-proof-packet",
                        "support_case_backed": False,
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
                                "tuple_entry_count": 1,
                                "tuple_unique": True,
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "missingRequiredPlatformHeadRidTuples' must be an explicit list" in reason
        for reason in journey["blocking_reasons"]
    )
    assert not any(
        "external_proof_required_case_count does not match packet install_diagnosis facts" in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_packet_external_proof_tuple_missing_from_release_backlog(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "complete": False,
                    "missingRequiredPlatformHeadRidTuples": [],
                    "externalProofRequests": [],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 1,
                    "external_proof_required_host_counts": {"windows": 1},
                    "external_proof_required_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_count": 0,
                    "unresolved_external_proof_request_host_counts": {},
                    "unresolved_external_proof_request_tuple_counts": {},
                    "unresolved_external_proof_request_hosts": [],
                    "unresolved_external_proof_request_tuples": [],
                    "unresolved_external_proof_request_specs": {},
                },
                "packets": [
                    {
                        "packet_id": "packet-1",
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
                                "tuple_entry_count": 1,
                                "tuple_unique": True,
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "external proof tuple 'avalonia:win-x64:windows' is not present in release-channel external proof backlog"
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_required_host_count_is_boolean(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "complete": False,
                    "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 1,
                    "external_proof_required_host_counts": {"windows": True},
                    "external_proof_required_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "preview",
                            "required_host": "windows",
                            "tuple_entry_count": 1,
                            "tuple_unique": True,
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
                        }
                    },
                },
                "packets": [
                    {
                        "packet_id": "packet-1",
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
                                "tuple_entry_count": 1,
                                "tuple_unique": True,
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "support packet summary external_proof_required_host_counts does not match packet install_diagnosis facts."
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_required_case_count_is_boolean(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "complete": False,
                    "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": True,
                    "external_proof_required_host_counts": {"windows": 1},
                    "external_proof_required_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "preview",
                            "required_host": "windows",
                            "tuple_entry_count": 1,
                            "tuple_unique": True,
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
                        }
                    },
                },
                "packets": [
                    {
                        "packet_id": "packet-1",
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
                                "tuple_entry_count": 1,
                                "tuple_unique": True,
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

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert any(
        "support packet summary external_proof_required_case_count does not match packet install_diagnosis facts."
        in reason
        for reason in journey["blocking_reasons"]
    )


def test_install_journey_blocks_when_support_external_proof_execution_plan_request_count_is_boolean(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    progress_report = tmp_path / "PROGRESS_REPORT.generated.json"
    progress_history = tmp_path / "PROGRESS_HISTORY.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    release_channel = tmp_path / ".codex-studio/published/RELEASE_CHANNEL.generated.json"

    release_channel.parent.mkdir(parents=True, exist_ok=True)
    release_channel.write_text(
        json.dumps(
            {
                "channelId": "preview",
                "status": "published",
                "desktopTupleCoverage": {
                    "complete": False,
                    "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                    "missingRequiredPlatforms": ["windows"],
                    "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                    "externalProofRequests": [
                        {
                            "tupleId": "avalonia:win-x64:windows",
                            "requiredHost": "windows",
                            "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                            "expectedArtifactId": "avalonia-win-x64-installer",
                            "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                            "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                            "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                            "startupSmokeReceiptContract": {
                                "statusAnyOf": ["pass", "passed", "ready"],
                                "readyCheckpoint": "pre_ui_event_loop",
                                "headId": "avalonia",
                                "platform": "windows",
                                "rid": "win-x64",
                                "hostClassContains": "windows",
                            },
                            "proofCaptureCommands": [
                                "cd /docker/chummercomplete/chummer6-ui && CHUMMER_DESKTOP_STARTUP_SMOKE_HOST_CLASS=windows-host ./scripts/run-desktop-startup-smoke.sh /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe avalonia win-x64 Chummer.Avalonia.exe /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke",
                                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                            ],
                        }
                    ],
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
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
      repo_source_proof:
        - repo: chummer6-hub-registry
          path: .codex-studio/published/RELEASE_CHANNEL.generated.json
          json_must_equal:
            status: published
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
                "summary": {
                    "external_proof_required_case_count": 0,
                    "external_proof_required_host_counts": {},
                    "external_proof_required_tuple_counts": {},
                    "unresolved_external_proof_request_count": 1,
                    "unresolved_external_proof_request_host_counts": {"windows": 1},
                    "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
                    "unresolved_external_proof_request_hosts": ["windows"],
                    "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                    "unresolved_external_proof_request_specs": {
                        "avalonia:win-x64:windows": {
                            "channel_id": "preview",
                            "tuple_entry_count": 1,
                            "tuple_unique": True,
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
                        }
                    },
                },
                "unresolved_external_proof_execution_plan": {
                    "request_count": True,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": True,
                            "tuples": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "tuple_entry_count": 1,
                                    "tuple_unique": True,
                                    "channel_id": "preview",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
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
                                }
                            ],
                        }
                    },
                },
                "packets": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    original_roots = JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.get("chummer6-hub-registry")
    JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = (tmp_path,)
    try:
        payload = JOURNEY_GATES_MODULE.build_payload(
            registry_path=registry,
            status_plane_path=status_plane,
            progress_report_path=progress_report,
            progress_history_path=progress_history,
            support_packets_path=support_packets,
        )
    finally:
        if original_roots is None:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES.pop("chummer6-hub-registry", None)
        else:
            JOURNEY_GATES_MODULE.REPO_ROOT_CANDIDATES["chummer6-hub-registry"] = original_roots

    journey = payload["journeys"][0]
    assert journey["state"] == "blocked"
    assert int(journey["signals"]["support_install_truth_contract_violation_count"]) > 0
    assert any(
        "unresolved_external_proof_execution_plan does not match release-channel external proof backlog." in reason
        for reason in journey["blocking_reasons"]
    )
