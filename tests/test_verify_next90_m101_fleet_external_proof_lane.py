from __future__ import annotations

import importlib.util
import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/verify_next90_m101_fleet_external_proof_lane.py")
RUNBOOK_MATERIALIZER = Path("/docker/fleet/scripts/materialize_external_proof_runbook.py")


def _load_module():
    previous_sys_path = list(sys.path)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("verify_next90_m101_fleet_external_proof_lane", SCRIPT)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = previous_sys_path


def _env_without_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _touch_lane_bundle(commands_dir: Path) -> None:
    for host in ("linux", "macos", "windows"):
        for name in (
            f"preflight-{host}-proof.sh",
            f"capture-{host}-proof.sh",
            f"validate-{host}-proof.sh",
            f"bundle-{host}-proof.sh",
            f"ingest-{host}-proof-bundle.sh",
        ):
            _write_executable(
                commands_dir / name,
                "#!/usr/bin/env bash\nset -euo pipefail\necho ok >/dev/null\n",
            )
        _write_executable(
            commands_dir / f"run-{host}-proof-lane.sh",
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    f"./preflight-{host}-proof.sh",
                    f"./capture-{host}-proof.sh",
                    f"./validate-{host}-proof.sh",
                    f"./bundle-{host}-proof.sh",
                    "",
                ]
            ),
        )
    for name in (
        "preflight-windows-proof.ps1",
        "capture-windows-proof.ps1",
        "validate-windows-proof.ps1",
        "bundle-windows-proof.ps1",
        "ingest-windows-proof-bundle.ps1",
        "run-windows-proof-lane.ps1",
    ):
        _write_executable(
            commands_dir / name,
            "$ErrorActionPreference = 'Stop'\nif ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }\n",
        )
    _write_executable(
        commands_dir / "finalize-external-host-proof.sh",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "./validate-linux-proof.sh",
                "./ingest-linux-proof-bundle.sh",
                "./validate-macos-proof.sh",
                "./ingest-macos-proof-bundle.sh",
                "./validate-windows-proof.sh",
                "./ingest-windows-proof-bundle.sh",
                "./republish-after-host-proof.sh",
                "",
            ]
        ),
    )
    (commands_dir / "host-proof-bundles").mkdir(parents=True, exist_ok=True)


def _package_row(module) -> dict:
    return {
        "title": module.QUEUE_TITLE,
        "task": module.QUEUE_TASK,
        "package_id": module.PACKAGE_ID,
        "frontier_id": module.FRONTIER_ID,
        "milestone_id": module.MILESTONE_ID,
        "wave": module.WAVE,
        "repo": "fleet",
        "status": "complete",
        "completion_action": module.COMPLETION_ACTION,
        "do_not_reopen_reason": module.DO_NOT_REOPEN_REASON,
        "proof": list(module.REQUIRED_QUEUE_PROOF_MARKERS),
        "allowed_paths": list(module.ALLOWED_PATHS),
        "owned_surfaces": list(module.OWNED_SURFACES),
    }


def _registry_payload(module) -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": module.MILESTONE_ID,
                "title": module.MILESTONE_TITLE,
                "wave": module.WAVE,
                "owners": ["chummer6-ui", "chummer6-hub-registry", "fleet", "chummer6-design"],
                "status": "in_progress",
                "work_tasks": [
                    {
                        "id": module.WORK_TASK_ID,
                        "owner": "fleet",
                        "title": module.WORK_TASK_TITLE,
                        "status": "complete",
                        "evidence": list(module.REQUIRED_REGISTRY_EVIDENCE_MARKERS),
                    }
                ],
            }
        ],
    }


def _queue_payload(module, *, registry_path: Path, design_queue_path: Path) -> dict:
    return {
        "mode": "append",
        "program_wave": "next_90_day_product_advance",
        "status": "live_parallel_successor",
        "source_registry_path": str(registry_path),
        "source_design_queue_path": str(design_queue_path),
        "items": [_package_row(module)],
    }


def _design_queue_payload(module, *, registry_path: Path) -> dict:
    return {
        "mode": "append",
        "program_wave": "next_90_day_product_advance",
        "status": "live_parallel_successor",
        "source_registry_path": str(registry_path),
        "items": [_package_row(module)],
    }


def _readiness_payload(
    module,
    *,
    runbook_path: Path,
    commands_dir: Path,
    command_bundle: dict,
    support_generated_at: str,
    release_generated_at: str,
    runbook_generated_at: str,
    runbook_command_bundle_sha256: str,
    runbook_command_bundle_file_count: int,
) -> dict:
    command_bundle_sha256 = str(command_bundle.get("sha256") or "")
    command_bundle_file_count = int(command_bundle.get("file_count") or 0)
    return {
        "generated_at": runbook_generated_at,
        "status": "pass",
        "ready_keys": ["desktop_client", "fleet_and_operator_loop"],
        "external_host_proof": {
            "status": "pass",
            "reason": module.EXPECTED_EXTERNAL_HOST_REASON,
            "runbook_path": str(runbook_path),
            "runbook_generated_at": runbook_generated_at,
            "runbook_plan_generated_at": support_generated_at,
            "runbook_release_channel_generated_at": release_generated_at,
            "commands_dir": str(commands_dir),
            "command_bundle_sha256": command_bundle_sha256,
            "command_bundle_file_count": command_bundle_file_count,
            "runbook_command_bundle_sha256": runbook_command_bundle_sha256,
            "runbook_command_bundle_file_count": runbook_command_bundle_file_count,
            "runbook_synced": True,
            "runbook_sync_reasons": [],
            "unresolved_request_count": 0,
            "unresolved_hosts": [],
            "unresolved_tuples": [],
        },
        "coverage_details": {
            "fleet_and_operator_loop": {
                "status": "ready",
                "evidence": {
                    "external_proof_backlog_request_count": 0,
                    "external_proof_backlog_request_observation_count": 0,
                    "external_proof_backlog_duplicate_observation_count": 0,
                    "external_proof_runbook_path": str(runbook_path),
                    "external_proof_runbook_generated_at": runbook_generated_at,
                    "external_proof_runbook_plan_generated_at": support_generated_at,
                    "external_proof_runbook_release_channel_generated_at": release_generated_at,
                    "external_proof_commands_dir": str(commands_dir),
                    "external_proof_command_bundle_sha256": command_bundle_sha256,
                    "external_proof_command_bundle_file_count": command_bundle_file_count,
                    "external_proof_runbook_command_bundle_sha256": runbook_command_bundle_sha256,
                    "external_proof_runbook_command_bundle_file_count": runbook_command_bundle_file_count,
                    "external_proof_runbook_sync_issue_count": 0,
                    "external_proof_runbook_synced": True,
                    "journey_effective_blocked_external_only_count": 0,
                    "journey_overall_state": "ready",
                },
            }
        },
    }


def _closed_fixture(tmp_path: Path):
    module = _load_module()
    now = datetime.now(timezone.utc)
    release_generated_at = _iso_z(now - timedelta(minutes=2))
    support_generated_at = _iso_z(now - timedelta(minutes=1))
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    readiness = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    closeout = tmp_path / "2026-04-19-next90-m101-fleet-external-proof-lane-closeout.md"

    _write_json(
        release_channel,
        {
            "generatedAt": release_generated_at,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )
    _write_json(
        support_packets,
        {
            "generated_at": support_generated_at,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_specs": {},
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "host_counts": {},
                "hosts": [],
                "specs": {},
                "tuple_counts": {},
                "tuples": [],
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_generated_at,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(_load_module()._parse_iso_utc(release_generated_at) + timedelta(hours=24)),
                "release_channel_generated_at": release_generated_at,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "summary": {
                "overall_state": "ready",
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_host_counts": {},
                "blocked_external_only_tuples": [],
            },
            "journeys": [
                {
                    "id": journey_id,
                    "state": "ready",
                    "blockers": [],
                    "blocking_reasons": [],
                    "external_blocking_reasons": [],
                    "blocked_by_external_constraints_only": False,
                    "external_proof_requests": [],
                    "evidence": {
                        "support_packets_generated_at": support_generated_at,
                        "external_proof_requests": [],
                    },
                }
                for journey_id in module.RELEVANT_JOURNEY_IDS
            ],
        },
    )
    materialize = subprocess.run(
        [
            sys.executable,
            str(RUNBOOK_MATERIALIZER),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--out",
            str(runbook),
            "--commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize.returncode == 0, materialize.stderr
    runbook_body = runbook.read_text(encoding="utf-8")
    loaded_module = _load_module()
    runbook_generated_at = loaded_module._extract_runbook_field(runbook_body, "generated_at")
    runbook_command_bundle_sha256 = loaded_module._extract_runbook_field(runbook_body, "command_bundle_sha256")
    runbook_command_bundle_file_count = int(
        loaded_module._extract_runbook_field(runbook_body, "command_bundle_file_count")
    )
    command_bundle = loaded_module._command_bundle_fingerprint(commands_dir)
    _write_json(
        readiness,
        _readiness_payload(
            module,
            runbook_path=runbook,
            commands_dir=commands_dir,
            command_bundle=command_bundle,
            support_generated_at=support_generated_at,
            release_generated_at=release_generated_at,
            runbook_generated_at=runbook_generated_at,
            runbook_command_bundle_sha256=runbook_command_bundle_sha256,
            runbook_command_bundle_file_count=runbook_command_bundle_file_count,
        ),
    )
    _write_yaml(registry, _registry_payload(module))
    _write_yaml(design_queue, _design_queue_payload(module, registry_path=registry))
    _write_yaml(queue, _queue_payload(module, registry_path=registry, design_queue_path=design_queue))
    closeout.write_text(
        "\n".join(
            [
                "# Next90 M101 Fleet External Proof Lane Closeout",
                "",
                f"Package: `{module.PACKAGE_ID}`",
                f"Milestone: `{module.MILESTONE_ID}`",
                f"Frontier: `{module.FRONTIER_ID}`",
                "Status: complete",
                "",
                "Future shards must verify the completed package instead of reopening native-host proof capture and ingest from worker-local telemetry, helper commands, or copied queue rows.",
                "The canonical completed-package frontier for this Fleet proof lane remains pinned in the queue and registry evidence above.",
                "Worker-assignment frontier ids from active successor runs are scheduler-local context only and must never replace the canonical package frontier in closure proof.",
                "",
                "- support-packet external-proof backlog stays zero",
                "- journey gates keep external-only blockers at zero",
                "- flagship readiness keeps `external_host_proof.status=pass`",
                "- the zero-backlog command bundle still retains per-host preflight, capture, validate, bundle, ingest, and run entrypoints for Linux, macOS, and Windows",
                "- the retained command bundle keeps `host-proof-bundles/linux`, `host-proof-bundles/macos`, and `host-proof-bundles/windows` present so ingest can resume without rebuilding the lane",
                "- the finalize entrypoint still republishes after the per-host validate and ingest lanes remain available",
                "- the standalone verifier and bootstrap no-PYTHONPATH guard stay runnable without ambient worker state",
                "- root-level registry milestone, Fleet queue, and design queue metadata cannot cite worker-local telemetry or helper commands as closure proof",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "module": module,
        "support_packets": support_packets,
        "journey_gates": journey_gates,
        "release_channel": release_channel,
        "runbook": runbook,
        "commands_dir": commands_dir,
        "readiness": readiness,
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "closeout": closeout,
    }


def _run_verifier(fixture: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(fixture["support_packets"]),
            "--journey-gates",
            str(fixture["journey_gates"]),
            "--release-channel",
            str(fixture["release_channel"]),
            "--external-proof-runbook",
            str(fixture["runbook"]),
            "--external-proof-commands-dir",
            str(fixture["commands_dir"]),
            "--flagship-readiness",
            str(fixture["readiness"]),
            "--successor-registry",
            str(fixture["registry"]),
            "--queue-staging",
            str(fixture["queue"]),
            "--design-queue-staging",
            str(fixture["design_queue"]),
            "--closeout-note",
            str(fixture["closeout"]),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


class VerifyNext90M101FleetExternalProofLaneTests(unittest.TestCase):
    def test_verify_script_runs_without_pythonpath(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=False,
            capture_output=True,
            text=True,
            env=_env_without_pythonpath(),
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("No module named", result.stdout + result.stderr)

    def test_verifier_passes_with_closed_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            result = _run_verifier(fixture)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("verified next90-m101-fleet-external-proof-lane", result.stdout)

    def test_verifier_fails_when_zero_backlog_ingest_loses_manifest_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            ingest_script = fixture["commands_dir"] / "ingest-linux-proof-bundle.sh"
            ingest_script.write_text(
                "#!/usr/bin/env bash\nset -euo pipefail\necho ingest-placeholder\n",
                encoding="utf-8",
            )
            result = _run_verifier(fixture)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof zero-backlog ingest script for linux missing required token",
                result.stderr,
            )
            self.assertIn("external-proof-bundle-manifest-missing", result.stderr)

    def test_verifier_fails_when_zero_backlog_ingest_loses_absolute_archive_member_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            ingest_script = fixture["commands_dir"] / "ingest-linux-proof-bundle.sh"
            ingest_payload = ingest_script.read_text(encoding="utf-8")
            ingest_script.write_text(
                ingest_payload.replace("assert not bad, ", "assert True or bad, "),
                encoding="utf-8",
            )
            result = _run_verifier(fixture)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof zero-backlog ingest script for linux missing required token: assert not bad",
                result.stderr,
            )

    def test_verifier_fails_when_zero_backlog_bundle_loses_manifest_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            bundle_script = fixture["commands_dir"] / "bundle-macos-proof.sh"
            bundle_payload = bundle_script.read_text(encoding="utf-8")
            bundle_script.write_text(
                bundle_payload.replace("external-proof-manifest.json", "external-proof-placeholder.json"),
                encoding="utf-8",
            )
            result = _run_verifier(fixture)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof zero-backlog bundle script for macos missing required token: external-proof-manifest.json",
                result.stderr,
            )

    def test_verifier_fails_when_zero_backlog_bundle_does_not_write_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            bundle_script = fixture["commands_dir"] / "bundle-linux-proof.sh"
            bundle_payload = bundle_script.read_text(encoding="utf-8")
            bundle_script.write_text(
                bundle_payload.replace(
                    'tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .',
                    "echo archive-disabled",
                ),
                encoding="utf-8",
            )
            result = _run_verifier(fixture)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof zero-backlog bundle script for linux missing required token: "
                'tar -czf "$BUNDLE_ARCHIVE" -C "$BUNDLE_ROOT" .',
                result.stderr,
            )

    def test_verifier_fails_when_finalize_republishes_before_host_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            finalize_script = fixture["commands_dir"] / "finalize-external-host-proof.sh"
            finalize_script.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        "./validate-linux-proof.sh",
                        "./republish-after-host-proof.sh",
                        "./ingest-linux-proof-bundle.sh",
                        "./validate-macos-proof.sh",
                        "./ingest-macos-proof-bundle.sh",
                        "./validate-windows-proof.sh",
                        "./ingest-windows-proof-bundle.sh",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = _run_verifier(fixture)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof finalize script must ingest linux before republish",
                result.stderr,
            )

    def test_verifier_fails_when_zero_backlog_bundle_drops_host_lane_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            (fixture["commands_dir"] / "run-macos-proof-lane.sh").unlink()
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("external proof command artifact is missing", result.stderr)
            self.assertIn("run-macos-proof-lane.sh", result.stderr)

    def test_verifier_fails_when_retained_host_bundle_directory_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            retained_dir = fixture["commands_dir"] / "host-proof-bundles" / "macos"
            for child in sorted(retained_dir.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                else:
                    child.rmdir()
            retained_dir.rmdir()

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof retained host bundle directory is missing for macos",
                result.stderr,
            )

    def test_verifier_fails_when_retained_host_bundle_manifest_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            manifest_path = (
                fixture["commands_dir"]
                / "host-proof-bundles"
                / "windows"
                / "external-proof-manifest.json"
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "host": "windows",
                        "request_count": 1,
                        "requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof retained host bundle manifest is not zero-backlog for windows",
                result.stderr,
            )

    def test_verifier_fails_when_runbook_denies_retained_bundle_directory_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            runbook_payload = fixture["runbook"].read_text(encoding="utf-8")
            fixture["runbook"].write_text(
                runbook_payload.replace(
                    "- retained_bundle_directory_present: `true`",
                    "- retained_bundle_directory_present: `false`",
                    1,
                ),
                encoding="utf-8",
            )

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external proof runbook does not report retained bundle directory present",
                result.stderr,
            )

    def test_verifier_fails_when_zero_backlog_runbook_drops_retained_host_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            runbook_payload = fixture["runbook"].read_text(encoding="utf-8")
            fixture["runbook"].write_text(
                runbook_payload.replace("## Retained Host Lanes\n\n", "", 1).replace("### Host: linux\n\n", "", 1),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("retained host lanes section", result.stderr)

    def test_verifier_fails_when_closeout_note_drops_canonical_frontier_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            closeout_payload = fixture["closeout"].read_text(encoding="utf-8")
            fixture["closeout"].write_text(
                closeout_payload.replace(
                    "Worker-assignment frontier ids from active successor runs are scheduler-local context only and must never replace the canonical package frontier in closure proof.\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("closeout note missing marker", result.stderr)

    def test_verifier_fails_when_closeout_note_drops_finalize_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            closeout_payload = fixture["closeout"].read_text(encoding="utf-8")
            fixture["closeout"].write_text(
                closeout_payload.replace(
                    "- the finalize entrypoint still republishes after the per-host validate and ingest lanes remain available\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("closeout note missing marker", result.stderr)

    def test_verifier_fails_when_registry_work_task_metadata_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            registry = yaml.safe_load(fixture["registry"].read_text(encoding="utf-8"))
            work_task = registry["milestones"][0]["work_tasks"][0]
            work_task["operator_note"] = "Closed from TASK_LOCAL_TELEMETRY.generated.json"
            _write_yaml(fixture["registry"], registry)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("registry work task cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_registry_milestone_metadata_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            registry = yaml.safe_load(fixture["registry"].read_text(encoding="utf-8"))
            registry["milestones"][0]["operator_note"] = "Closed from ACTIVE_RUN_HANDOFF.generated.md"
            _write_yaml(fixture["registry"], registry)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("registry milestone cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_queue_root_metadata_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            queue = yaml.safe_load(fixture["queue"].read_text(encoding="utf-8"))
            queue["operator_note"] = "Closed by chummer_design_supervisor.py eta"
            _write_yaml(fixture["queue"], queue)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("queue staging cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_design_queue_root_metadata_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            design_queue = yaml.safe_load(fixture["design_queue"].read_text(encoding="utf-8"))
            design_queue["operator_note"] = "Closed by --telemetry-answer"
            _write_yaml(fixture["design_queue"], design_queue)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("design queue staging cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_queue_item_metadata_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            queue = yaml.safe_load(fixture["queue"].read_text(encoding="utf-8"))
            queue["items"][0]["operator_note"] = "Closed from ACTIVE_RUN_HANDOFF.generated.md"
            _write_yaml(fixture["queue"], queue)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("queue item cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_queue_proof_cites_generic_operator_telemetry_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            queue = yaml.safe_load(fixture["queue"].read_text(encoding="utf-8"))
            queue["items"][0]["proof"].append("closed by operator-telemetry helper output")
            _write_yaml(fixture["queue"], queue)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("queue proof cites active-run telemetry/helper proof", result.stderr)

    def test_disallowed_entries_detects_encoded_worker_helper_markers(self) -> None:
        module = _load_module()
        base64_marker = base64.b64encode(b"closed by chummer_design_supervisor.py status").decode("ascii")
        nested_base64_marker = base64.b64encode(base64_marker.encode("ascii")).decode("ascii")
        hex_marker = b"closed by TASK_LOCAL_TELEMETRY.generated.json".hex()
        url_marker = "closed%20by%20ACTIVE_RUN_HANDOFF.generated.md"
        html_marker = "closed by TASK_LOCAL_&#84;ELEMETRY.generated.json"

        self.assertEqual(module._disallowed_entries([base64_marker]), [base64_marker])
        self.assertEqual(module._disallowed_entries([nested_base64_marker]), [nested_base64_marker])
        self.assertEqual(module._disallowed_entries([hex_marker]), [hex_marker])
        self.assertEqual(module._disallowed_entries([url_marker]), [url_marker])
        self.assertEqual(module._disallowed_entries([html_marker]), [html_marker])

    def test_verifier_fails_when_queue_proof_cites_html_entity_encoded_worker_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            queue = yaml.safe_load(fixture["queue"].read_text(encoding="utf-8"))
            queue["items"][0]["proof"].append("closed by TASK_LOCAL_&#84;ELEMETRY.generated.json")
            _write_yaml(fixture["queue"], queue)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("queue proof cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_queue_proof_cites_encoded_worker_helper_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            queue = yaml.safe_load(fixture["queue"].read_text(encoding="utf-8"))
            encoded_marker = base64.b64encode(
                b"closed by chummer_design_supervisor.py status"
            ).decode("ascii")
            queue["items"][0]["proof"].append(encoded_marker)
            _write_yaml(fixture["queue"], queue)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("queue proof cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_design_queue_item_metadata_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            design_queue = yaml.safe_load(fixture["design_queue"].read_text(encoding="utf-8"))
            design_queue["items"][0]["operator_note"] = "Closed by chummer_design_supervisor.py status"
            _write_yaml(fixture["design_queue"], design_queue)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("design queue item cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_runbook_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            with fixture["runbook"].open("a", encoding="utf-8") as handle:
                handle.write("\nWorker note: TASK_LOCAL_TELEMETRY.generated.json proved this lane.\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("external proof runbook cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_support_packet_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            support_packets = json.loads(fixture["support_packets"].read_text(encoding="utf-8"))
            support_packets["summary"]["operator_note"] = "Closed by supervisor eta helper output"
            support_packets["unresolved_external_proof"][
                "operator_note"
            ] = "Closed from ACTIVE_RUN_HANDOFF.generated.md"
            support_packets["unresolved_external_proof_execution_plan"][
                "operator_note"
            ] = "Closed from TASK_LOCAL_TELEMETRY.generated.json"
            _write_json(fixture["support_packets"], support_packets)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "support packets summary cites active-run telemetry/helper proof",
                result.stderr,
            )
            self.assertIn(
                "support packets unresolved_external_proof cites active-run telemetry/helper proof",
                result.stderr,
            )
            self.assertIn(
                "support packets external-proof execution plan cites active-run telemetry/helper proof",
                result.stderr,
            )

    def test_verifier_fails_when_journey_gate_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            journey_gates = json.loads(fixture["journey_gates"].read_text(encoding="utf-8"))
            journey_gates["summary"]["operator_note"] = "Closed from chummer_design_supervisor.py eta"
            journey_gates["journeys"][0]["operator_note"] = "Closed by --telemetry-answer"
            _write_json(fixture["journey_gates"], journey_gates)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "journey gates summary cites active-run telemetry/helper proof",
                result.stderr,
            )
            self.assertIn(
                "journey gate rows cite active-run telemetry/helper proof",
                result.stderr,
            )

    def test_verifier_fails_when_retained_command_cites_worker_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            command_path = fixture["commands_dir"] / "run-linux-proof-lane.sh"
            with command_path.open("a", encoding="utf-8") as handle:
                handle.write("\n# Never close this from chummer_design_supervisor.py status output.\n")

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("external proof command cites active-run telemetry/helper proof", result.stderr)
            self.assertIn("run-linux-proof-lane.sh", result.stderr)

    def test_verifier_fails_when_readiness_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            readiness = json.loads(fixture["readiness"].read_text(encoding="utf-8"))
            readiness["external_host_proof"]["operator_note"] = "Closed from ACTIVE_RUN_HANDOFF.generated.md"
            readiness["coverage_details"]["fleet_and_operator_loop"]["evidence"][
                "operator_note"
            ] = "Closed by chummer_design_supervisor.py status"
            _write_json(fixture["readiness"], readiness)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "flagship readiness external_host_proof cites active-run telemetry/helper proof",
                result.stderr,
            )
            self.assertIn("fleet coverage evidence cites active-run telemetry/helper proof", result.stderr)

    def test_verifier_fails_when_release_channel_reopens_external_proof_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            release_channel = json.loads(fixture["release_channel"].read_text(encoding="utf-8"))
            release_channel["desktopTupleCoverage"]["externalProofRequests"] = [
                {
                    "tupleId": "avalonia:osx-arm64:macos",
                    "requiredHost": "macos",
                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                }
            ]
            _write_json(fixture["release_channel"], release_channel)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "release channel desktopTupleCoverage.externalProofRequests is not empty",
                result.stderr,
            )

    def test_verifier_fails_when_release_channel_cites_worker_local_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            release_channel = json.loads(fixture["release_channel"].read_text(encoding="utf-8"))
            release_channel["desktopTupleCoverage"][
                "operator_note"
            ] = "Closed from TASK_LOCAL_TELEMETRY.generated.json"
            _write_json(fixture["release_channel"], release_channel)

            result = _run_verifier(fixture)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "release channel desktopTupleCoverage cites active-run telemetry/helper proof",
                result.stderr,
            )

    def test_verifier_fails_when_readiness_command_bundle_fingerprint_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            readiness = json.loads(fixture["readiness"].read_text(encoding="utf-8"))
            readiness["external_host_proof"]["command_bundle_sha256"] = "0" * 64
            readiness["coverage_details"]["fleet_and_operator_loop"]["evidence"][
                "external_proof_command_bundle_sha256"
            ] = "0" * 64
            _write_json(fixture["readiness"], readiness)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "external_host_proof.command_bundle_sha256 drifted from retained command bundle",
                result.stderr,
            )
            self.assertIn(
                "fleet coverage external_proof_command_bundle_sha256 drifted from retained command bundle",
                result.stderr,
            )

    def test_file_token_guard_reports_missing_bootstrap_token(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verify_script_bootstrap_no_pythonpath.py"
            path.write_text(
                "\n".join(
                    [
                        "verify_external_proof_closure.py",
                        "materialize_external_proof_runbook.py",
                        "materialize_proof_orchestration.py",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            issues: list[str] = []

            module._require_file_tokens(
                path,
                module.REQUIRED_BOOTSTRAP_GUARD_TOKENS,
                issues,
                label="pythonpath bootstrap guard script",
            )

            self.assertIn(
                "pythonpath bootstrap guard script missing required token: "
                "verify_next90_m101_fleet_external_proof_lane.py",
                issues,
            )

    def test_verifier_fails_when_design_queue_assignment_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            design_queue = yaml.safe_load(fixture["design_queue"].read_text(encoding="utf-8"))
            design_queue["items"][0]["task"] = "drifted task"
            _write_yaml(fixture["design_queue"], design_queue)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("design-owned queue source row does not match Fleet queue field: task", result.stderr)

    def test_verifier_fails_when_design_queue_source_registry_path_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _closed_fixture(Path(tmp))
            design_queue = yaml.safe_load(fixture["design_queue"].read_text(encoding="utf-8"))
            design_queue["source_registry_path"] = "/tmp/drifted-registry.yaml"
            _write_yaml(fixture["design_queue"], design_queue)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(fixture["support_packets"]),
                    "--journey-gates",
                    str(fixture["journey_gates"]),
                    "--release-channel",
                    str(fixture["release_channel"]),
                    "--external-proof-runbook",
                    str(fixture["runbook"]),
                    "--external-proof-commands-dir",
                    str(fixture["commands_dir"]),
                    "--flagship-readiness",
                    str(fixture["readiness"]),
                    "--successor-registry",
                    str(fixture["registry"]),
                    "--queue-staging",
                    str(fixture["queue"]),
                    "--design-queue-staging",
                    str(fixture["design_queue"]),
                    "--closeout-note",
                    str(fixture["closeout"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("design queue staging source_registry_path drifted from successor registry", result.stderr)


if __name__ == "__main__":
    unittest.main()
