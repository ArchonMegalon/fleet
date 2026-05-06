from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m144_fleet_desktop_proof_integrity_closeout_gates.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _registry() -> dict:
    return {"milestones": [{"id": 144, "work_tasks": [{"id": "144.4", "owner": "fleet"}]}]}


def _queue_item() -> dict:
    return {
        "title": "Fail closeout when desktop-client readiness is green without matching executable-gate, startup-smoke, and release-channel tuple proof.",
        "task": "Fail closeout when desktop-client readiness is green without matching executable-gate, startup-smoke, and release-channel tuple proof.",
        "package_id": "next90-m144-fleet-fail-closeout-when-desktop-client-readiness-is-green-without-matching",
        "milestone_id": 144,
        "work_task_id": "144.4",
        "frontier_id": 4185937434,
        "wave": "W22P",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["fail_closeout_when_desktop_client_readiness_is_green_wit:fleet"],
    }


def _fixture_tree(
    tmp_path: Path,
    *,
    stale_versions: bool,
    startup_smoke_digest_matches_release: bool = True,
    stale_flagship_tuple_evidence: bool = False,
    linux_tuple_missing_from_executable_gate: bool = False,
    omit_flagship_promoted_tuple_inventory: bool = False,
    unreadable_startup_smoke_receipt: bool = False,
) -> dict[str, Path]:
    registry = tmp_path / "registry.yaml"
    fleet_queue = tmp_path / "fleet_queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    guide = tmp_path / "guide.md"
    flagship = tmp_path / "flagship.json"
    windows_gate = tmp_path / "windows_gate.json"
    executable_gate = tmp_path / "executable_gate.json"
    release_channel = tmp_path / "release_channel.json"
    startup_smoke = tmp_path / "startup_smoke.receipt.json"

    release_version = "run-2" if stale_versions else "run-1"
    stale_version = "run-1"
    startup_smoke_version = stale_version if stale_versions else release_version
    digest = "abc123"
    startup_digest = digest if startup_smoke_digest_matches_release else "digest-mismatch"
    artifact_id = "avalonia-win-x64-installer"

    _write_yaml(registry, _registry())
    _write_yaml(fleet_queue, {"items": [_queue_item()]})
    _write_yaml(design_queue, {"items": [_queue_item()]})
    _write_text(
        guide,
        "## Wave 22P - close human-tested parity proof and desktop executable trust before successor breadth\n"
        "### 144. Desktop executable proof integrity and publishable flagship-route closure\n"
        "Exit: Windows, Linux, and macOS promoted desktop tuples have matching startup-smoke receipts, executable-gate proof, release-channel tuple truth, and `desktop_client` readiness with no stale or inherited trust.\n",
    )
    if not unreadable_startup_smoke_receipt:
        _write_json(
            startup_smoke,
            {
                "status": "pass",
                "platform": "windows",
                "rid": "win-x64",
                "arch": "x64",
                "channel": "preview",
                "version": startup_smoke_version,
                "artifactDigest": f"sha256:{startup_digest}",
                "artifactPath": "/tmp/chummer-avalonia-win-x64-installer.exe",
                "readyCheckpoint": "pre_ui_event_loop",
                "completedAtUtc": "2026-05-05T12:00:00Z",
            },
        )
    _write_json(
        windows_gate,
        {
            "generated_at": "2026-05-05T12:05:00Z",
            "status": "passed",
            "checks": {
                "installer_exists": True,
                "installer_sha256": digest,
                "installer_size_bytes": 123,
                "release_channel_version": release_version,
                "release_channel_windows_artifact": {
                    "artifactId": artifact_id,
                    "sha256": digest,
                    "sizeBytes": 123,
                    "version": release_version,
                    "releaseVersion": release_version,
                },
                "startup_smoke_receipt_found": True,
                "startup_smoke_receipt_path": str(startup_smoke),
                "startup_smoke_status": "pass",
                "startup_smoke_version": startup_smoke_version,
                "startup_smoke_artifact_digest": f"sha256:{startup_digest}",
                "expected_startup_smoke_artifact_digest": f"sha256:{digest}",
                "startup_smoke_ready_checkpoint": "pre_ui_event_loop",
                "startup_smoke_age_seconds": 60,
                "startup_smoke_max_age_seconds": 604800,
            },
        },
    )
    linux_statuses = {} if linux_tuple_missing_from_executable_gate else {"avalonia:linux-x64": "pass"}
    windows_statuses = {"avalonia:win-x64": "pass"}
    flagship_linux_statuses = {"avalonia:linux-x64": "stale"} if stale_flagship_tuple_evidence else dict(linux_statuses)
    flagship_windows_statuses = {"avalonia:win-x64": "stale"} if stale_flagship_tuple_evidence else dict(windows_statuses)
    _write_json(
        executable_gate,
        {
            "generated_at": "2026-05-05T12:06:00Z",
            "status": "pass",
            "local_blocking_findings_count": 0,
            "evidence": {
                "release_channel_version": release_version,
                "desktopTupleCoverage.missingRequiredPlatforms_normalized": [],
                "desktopTupleCoverage.missingRequiredPlatformHeadPairs_normalized": [],
                "desktopTupleCoverage.missingRequiredPlatformHeadRidTuples_normalized": [],
                "linux_statuses": linux_statuses,
                "windows_statuses": windows_statuses,
                "macos_statuses": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generated_at": "2026-05-05T12:10:00Z",
            "status": "published",
            "version": release_version,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "complete": True,
                "promotedInstallerTuples": [
                    {
                        "tupleId": "avalonia:windows:win-x64",
                        "platform": "windows",
                        "head": "avalonia",
                        "rid": "win-x64",
                        "artifactId": artifact_id,
                    },
                    {
                        "tupleId": "avalonia:linux:linux-x64",
                        "platform": "linux",
                        "head": "avalonia",
                        "rid": "linux-x64",
                        "artifactId": "avalonia-linux-x64-installer",
                    },
                ],
            },
            "artifacts": [
                {
                    "artifactId": artifact_id,
                    "platform": "windows",
                    "head": "avalonia",
                    "kind": "installer",
                    "sha256": digest,
                    "sizeBytes": 123,
                    "version": release_version,
                    "releaseVersion": release_version,
                },
                {
                    "artifactId": "avalonia-linux-x64-installer",
                    "platform": "linux",
                    "head": "avalonia",
                    "kind": "installer",
                    "sha256": "linux123",
                    "sizeBytes": 456,
                    "version": release_version,
                    "releaseVersion": release_version,
                },
            ],
        },
    )
    _write_json(
        flagship,
        {
            "generated_at": "2026-05-05T12:07:00Z",
            "status": "pass",
            "coverage": {"desktop_client": "ready"},
            "coverage_details": {
                "desktop_client": {
                    "status": "ready",
                    "evidence": {
                        "ui_windows_exit_gate_status": "passed",
                        "ui_executable_exit_gate_status": "pass",
                        "ui_executable_exit_gate_local_blocking_findings_count": 0,
                        "release_channel_version": release_version,
                        "release_channel_linux_promoted_tuples": [] if omit_flagship_promoted_tuple_inventory else ["avalonia:linux-x64"],
                        "release_channel_windows_promoted_tuples": [] if omit_flagship_promoted_tuple_inventory else ["avalonia:win-x64"],
                        "release_channel_macos_promoted_tuples": [],
                        "ui_executable_gate_linux_statuses": flagship_linux_statuses,
                        "ui_executable_gate_windows_statuses": flagship_windows_statuses,
                        "ui_executable_gate_macos_statuses": {},
                        "ui_executable_gate_linux_missing_or_failing_keys": [],
                        "ui_executable_gate_windows_missing_or_failing_keys": [],
                        "ui_executable_gate_macos_missing_or_failing_keys": [],
                        "ui_executable_gate_linux_stale_promoted_tuple_keys": (
                            ["avalonia:linux-x64"] if stale_flagship_tuple_evidence else []
                        ),
                        "ui_executable_gate_windows_stale_promoted_tuple_keys": (
                            ["avalonia:win-x64"] if stale_flagship_tuple_evidence else []
                        ),
                        "ui_executable_gate_macos_stale_promoted_tuple_keys": [],
                    },
                }
            },
        },
    )
    return {
        "registry": registry,
        "fleet_queue": fleet_queue,
        "design_queue": design_queue,
        "guide": guide,
        "flagship": flagship,
        "windows_gate": windows_gate,
        "executable_gate": executable_gate,
        "release_channel": release_channel,
        "startup_smoke": startup_smoke,
    }


class MaterializeNext90M144FleetDesktopProofIntegrityCloseoutGatesTest(unittest.TestCase):
    def test_materializer_passes_when_desktop_readiness_matches_live_tuple_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=False)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["monitor_summary"]["desktop_proof_integrity_closeout_status"] == "pass"

    def test_materializer_passes_when_release_version_rotates_without_byte_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "pass"
            assert payload["package_closeout"]["ready"] is True

    def test_materializer_blocks_when_release_version_rotates_and_digest_proof_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=True, startup_smoke_digest_matches_release=False)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["status"] == "fail"
            assert payload["monitor_summary"]["desktop_proof_integrity_closeout_status"] == "blocked"
            assert (
                "Windows startup-smoke receipt version `run-1` does not prove the live RELEASE_CHANNEL version `run-2`."
                in payload["monitor_summary"]["runtime_blockers"]
            )

    def test_materializer_blocks_when_executable_gate_omits_linux_promoted_tuple_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=False, linux_tuple_missing_from_executable_gate=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["monitor_summary"]["desktop_proof_integrity_closeout_status"] == "blocked"
            assert (
                "DESKTOP_EXECUTABLE_EXIT_GATE is missing passing Linux tuple proof for promoted tuple(s): avalonia:linux-x64."
                in payload["monitor_summary"]["runtime_blockers"]
            )

    def test_materializer_blocks_when_flagship_green_carries_stale_tuple_status_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=False, stale_flagship_tuple_evidence=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["monitor_summary"]["desktop_proof_integrity_closeout_status"] == "blocked"
            assert (
                "FLAGSHIP_PRODUCT_READINESS desktop_client evidence carries stale Linux executable tuple statuses."
                in payload["monitor_summary"]["runtime_blockers"]
            )

    def test_materializer_blocks_when_flagship_green_omits_promoted_tuple_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=False, omit_flagship_promoted_tuple_inventory=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["monitor_summary"]["desktop_proof_integrity_closeout_status"] == "blocked"
            assert (
                "FLAGSHIP_PRODUCT_READINESS desktop_client evidence is missing Linux promoted tuple inventory."
                in payload["monitor_summary"]["runtime_blockers"]
            )

    def test_materializer_blocks_when_startup_smoke_receipt_path_is_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=False, unreadable_startup_smoke_receipt=True)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            assert payload["monitor_summary"]["desktop_proof_integrity_closeout_status"] == "blocked"
            assert (
                "Windows startup-smoke receipt path resolves to no readable receipt payload."
                in payload["monitor_summary"]["runtime_blockers"]
            )


if __name__ == "__main__":
    unittest.main()
