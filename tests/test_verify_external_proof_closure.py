from __future__ import annotations

import argparse
import importlib.util
import os
import json
import subprocess
import sys
from typing import Any
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/verify_external_proof_closure.py")
MATERIALIZE_EXTERNAL_PROOF_RUNBOOK_SCRIPT = Path("/docker/fleet/scripts/materialize_external_proof_runbook.py")


def _load_verify_external_proof_closure_module():
    previous_sys_path = list(sys.path)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("verify_external_proof_closure", SCRIPT)
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


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _replace_value_recursively(payload: Any, old: str, new: str) -> Any:
    if isinstance(payload, dict):
        return {
            (new if str(key) == old else key): _replace_value_recursively(value, old, new)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_replace_value_recursively(item, old, new) for item in payload]
    if payload == old:
        return new
    return payload


def _write_external_proof_bundle(
    *,
    runbook_path: Path,
    commands_dir: Path,
    support_generated_at: str,
    release_generated_at: str,
) -> None:
    runbook_path.write_text(
        "\n".join(
            [
                "# External Proof Runbook",
                "",
                f"- generated_at: {support_generated_at}",
                f"- plan_generated_at: {support_generated_at}",
                f"- release_channel_generated_at: {release_generated_at}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    commands_dir.mkdir(parents=True, exist_ok=True)
    post_capture = commands_dir / "republish-after-host-proof.sh"
    post_capture.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "cd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh",
                (
                    "cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/materialize_public_release_channel.py "
                    "--proof /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json "
                    "--ui-localization-release-gate /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCALIZATION_RELEASE_GATE.generated.json"
                ),
                "cd /docker/chummercomplete/chummer-hub-registry && python3 scripts/verify_public_release_channel.py .codex-studio/published/RELEASE_CHANNEL.generated.json",
                "cd /docker/fleet && python3 scripts/materialize_status_plane.py --out .codex-studio/published/STATUS_PLANE.generated.yaml",
                "cd /docker/fleet && python3 scripts/verify_status_plane_semantics.py --status-plane .codex-studio/published/STATUS_PLANE.generated.yaml",
                "cd /docker/fleet && python3 scripts/materialize_public_progress_report.py --out .codex-studio/published/PROGRESS_REPORT.generated.json",
                "cd /docker/fleet && python3 scripts/materialize_support_case_packets.py --out .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
                "cd /docker/fleet && python3 scripts/materialize_journey_gates.py --out .codex-studio/published/JOURNEY_GATES.generated.json",
                "cd /docker/fleet && python3 scripts/materialize_external_proof_runbook.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --out .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md",
                "cd /docker/fleet && python3 scripts/verify_external_proof_closure.py --support-packets .codex-studio/published/SUPPORT_CASE_PACKETS.generated.json --journey-gates .codex-studio/published/JOURNEY_GATES.generated.json --release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json --external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md --external-proof-commands-dir .codex-studio/published/external-proof-commands",
                "cd /docker/fleet && python3 scripts/materialize_flagship_product_readiness.py --out .codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
                "cd /docker/chummercomplete/chummer-design && python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py --out products/chummer/WEEKLY_PRODUCT_PULSE.generated.json",
                "cd /docker/fleet && python3 scripts/chummer_design_supervisor.py status >/dev/null",
                "",
            ]
        ),
        encoding="utf-8",
    )
    post_capture.chmod(0o755)


def _write_open_windows_external_proof_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    deadline_ts = _iso_z(now + timedelta(hours=24))
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "startup_smoke_receipt_contract": {
                            "ready_checkpoint": "pre_ui_event_loop",
                            "head_id": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "host_class_contains": "windows",
                            "status_any_of": ["pass", "ready"],
                        },
                        "proof_capture_commands": [
                            "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                        ],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": deadline_ts,
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": deadline_ts,
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                                ],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                        "startupSmokeReceiptContract": {
                            "readyCheckpoint": "pre_ui_event_loop",
                            "headId": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                            "hostClassContains": "windows",
                            "statusAnyOf": ["pass", "ready"],
                        },
                        "proofCaptureCommands": [
                            "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                        ],
                    }
                ],
            },
        },
    )
    materialize_result = subprocess.run(
        [
            sys.executable,
            str(MATERIALIZE_EXTERNAL_PROOF_RUNBOOK_SCRIPT),
            "--support-packets",
            str(support_packets),
            "--out",
            str(runbook),
            "--commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert materialize_result.returncode == 0, materialize_result.stderr
    return support_packets, journey_gates, release_channel, runbook, commands_dir


def _write_closed_external_gaps_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "host_counts": {},
                "tuple_counts": {},
                "hosts": [],
                "tuples": [],
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": support_ts,
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )
    return support_packets, journey_gates, release_channel


def test_coerce_external_bundle_paths_uses_defaults_for_default_core_inputs() -> None:
    module = _load_verify_external_proof_closure_module()
    args = argparse.Namespace(
        support_packets=module.DEFAULT_SUPPORT_PACKETS,
        journey_gates=module.DEFAULT_JOURNEY_GATES,
        release_channel=module.DEFAULT_RELEASE_CHANNEL,
        external_proof_runbook=None,
        external_proof_commands_dir=None,
    )

    runbook_path, commands_dir = module._coerce_external_bundle_paths(args)

    assert runbook_path == module.DEFAULT_EXTERNAL_PROOF_RUNBOOK.resolve()
    assert commands_dir == module.DEFAULT_EXTERNAL_PROOF_COMMANDS_DIR.resolve()


def test_coerce_external_bundle_paths_does_not_force_defaults_for_custom_core_inputs(
    tmp_path: Path,
) -> None:
    module = _load_verify_external_proof_closure_module()
    args = argparse.Namespace(
        support_packets=tmp_path / "SUPPORT_CASE_PACKETS.generated.json",
        journey_gates=tmp_path / "JOURNEY_GATES.generated.json",
        release_channel=tmp_path / "RELEASE_CHANNEL.generated.json",
        external_proof_runbook=None,
        external_proof_commands_dir=None,
    )

    runbook_path, commands_dir = module._coerce_external_bundle_paths(args)

    assert runbook_path is None
    assert commands_dir is None


def test_verify_external_proof_closure_script_runs_without_pythonpath(tmp_path: Path) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_env_without_pythonpath(),
    )

    assert result.returncode == 1
    assert "No module named 'scripts.external_proof_paths'" not in result.stderr
    assert "journey gates still report external_proof_requests in journey rows" in result.stderr


def test_verify_external_proof_closure_json_mode_outputs_structured_failures(tmp_path: Path) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )
    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    requests = (
        payload.get("unresolved_external_proof_execution_plan", {})
        .get("host_groups", {})
        .get("windows", {})
        .get("requests")
    )
    assert isinstance(requests, list) and requests
    requests[0]["required_proofs"] = ["bogus-proof-token"]
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    report = json.loads(result.stdout.strip())
    assert report["status"] == "failed"
    assert report["failure_count"] >= 1
    assert report["failures"]
    assert isinstance(report["failures"], list)
    assert any("unsupported required proof token(s)" in failure for failure in report["failures"])


def test_verify_external_proof_closure_json_mode_outputs_success_payload(tmp_path: Path) -> None:
    support_packets, journey_gates, release_channel = _write_closed_external_gaps_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip())
    assert report["status"] == "passed"
    assert report["failure_count"] == 0
    assert report["failures"] == []


def test_verify_external_proof_closure_quiet_mode_suppresses_success_message(tmp_path: Path) -> None:
    support_packets, journey_gates, release_channel = _write_closed_external_gaps_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "External-proof closure check passed." not in result.stdout
    assert result.stdout == ""


def test_verify_external_proof_closure_quiet_mode_emits_minimal_failure_output(tmp_path: Path) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )
    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    spec = (
        payload.get("summary", {}).get("unresolved_external_proof_request_specs", {}).get(
            "avalonia:win-x64:windows"
        )
    )
    assert isinstance(spec, dict)
    spec["required_host"] = "beos"
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--quiet",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "External-proof closure check failed:" not in result.stderr
    assert result.stdout == ""
    assert "required_host (beos)" in result.stderr or "required_host is invalid: beos" in result.stderr


def test_materialize_external_proof_runbook_script_runs_without_pythonpath() -> None:
    result = subprocess.run(
        [sys.executable, str(MATERIALIZE_EXTERNAL_PROOF_RUNBOOK_SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=_env_without_pythonpath(),
    )

    assert result.returncode == 0


def test_verify_external_proof_closure_fails_when_tuple_ids_are_malformed(tmp_path: Path) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    invalid_tuple_id = "avalonia:win-x64"
    for path in (support_packets, journey_gates, release_channel):
        data = _replace_value_recursively(
            json.loads(path.read_text(encoding="utf-8")),
            "avalonia:win-x64:windows",
            invalid_tuple_id,
        )
        _write_json(path, data)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "contains invalid tupleId values" in result.stderr


def test_verify_external_proof_closure_fails_when_support_request_tuple_id_is_missing(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    requests = (
        payload.get("unresolved_external_proof_execution_plan", {})
        .get("host_groups", {})
        .get("windows", {})
        .get("requests")
    )
    assert isinstance(requests, list) and requests
    assert isinstance(requests[0], dict)
    requests[0].pop("tuple_id", None)
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "request rows are missing tuple_id" in result.stderr


def test_verify_external_proof_closure_fails_when_support_plan_host_group_has_duplicate_tuple_ids(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    host_groups = (
        payload.get("unresolved_external_proof_execution_plan", {}).get("host_groups") or {}
    )
    windows_group = host_groups.get("windows")
    assert isinstance(windows_group, dict)
    tuples = windows_group.get("tuples")
    assert isinstance(tuples, list) and tuples
    tuples.append(tuples[0])
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "support packets unresolved_external_proof_execution_plan.host_groups contain duplicate tuple_ids" in result.stderr


def test_verify_external_proof_closure_fails_when_support_plan_has_duplicate_request_tuple_ids(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    requests = (
        payload.get("unresolved_external_proof_execution_plan", {})
        .get("host_groups", {})
        .get("windows", {})
        .get("requests")
    )
    assert isinstance(requests, list) and requests
    requests.append(requests[0].copy())
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "support packets unresolved_external_proof_execution_plan.request rows contain duplicate tuple_id values" in result.stderr


def test_verify_external_proof_closure_fails_when_support_request_required_host_mismatches_group_host(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    requests = (
        payload.get("unresolved_external_proof_execution_plan", {})
        .get("host_groups", {})
        .get("windows", {})
        .get("requests")
    )
    assert isinstance(requests, list) and requests
    requests[0]["required_host"] = "macos"
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support packets unresolved_external_proof_execution_plan.request rows have invalid requiredHost values"
        in result.stderr
    )
    assert "avalonia:win-x64:windows: requiredHost (macos) does not match group host (windows)" in result.stderr


def test_verify_external_proof_closure_fails_when_support_request_specs_have_invalid_required_values(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    specs = (
        payload.get("summary", {}).get("unresolved_external_proof_request_specs", {})
    )
    assert isinstance(specs, dict) and specs
    spec = specs.get("avalonia:win-x64:windows")
    assert isinstance(spec, dict)
    spec["required_host"] = "beos"
    spec["required_proofs"] = ["promoted_installer_artifact"]

    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support packets unresolved_external_proof_request_specs contain invalid required_host values"
        in result.stderr
    )
    assert (
        "support packets unresolved_external_proof_request_specs are missing required_proofs for tuples"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_support_plan_host_group_host_is_unsupported(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    support_plan = payload.get("unresolved_external_proof_execution_plan")
    assert isinstance(support_plan, dict)
    host_groups = support_plan.get("host_groups")
    assert isinstance(host_groups, dict)
    host_groups["beos"] = host_groups.pop("windows")
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support packets unresolved_external_proof_execution_plan.host_groups contain unsupported host values"
        in result.stderr
    )
    assert "beos" in result.stderr


def test_verify_external_proof_closure_fails_when_support_plan_host_group_has_empty_host_key(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    support_plan = payload.get("unresolved_external_proof_execution_plan")
    assert isinstance(support_plan, dict)
    host_groups = support_plan.get("host_groups")
    assert isinstance(host_groups, dict)
    host_groups[""] = host_groups.pop("windows")
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support packets unresolved_external_proof_execution_plan.host_groups contains an empty host key"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_support_plan_request_has_invalid_required_proofs_type(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    requests = (
        payload.get("unresolved_external_proof_execution_plan", {})
        .get("host_groups", {})
        .get("windows", {})
        .get("requests")
    )
    assert isinstance(requests, list) and requests
    requests[0]["required_proofs"] = [123]
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support packets unresolved_external_proof_execution_plan.host_groups.windows.requests[0].required_proofs contains a non-string required_proofs token"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_support_plan_request_has_unknown_required_proof_token(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    requests = (
        payload.get("unresolved_external_proof_execution_plan", {})
        .get("host_groups", {})
        .get("windows", {})
        .get("requests")
    )
    assert isinstance(requests, list) and requests
    requests[0]["required_proofs"] = ["startup_smoke_receipt", "bogus-proof-token"]
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support packets unresolved_external_proof_execution_plan.host_groups.windows.requests[0].required_proofs contains unsupported required proof token(s): bogus-proof-token"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_support_request_specs_have_invalid_required_proofs_type(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    specs = (
        payload.get("summary", {}).get("unresolved_external_proof_request_specs", {})
    )
    assert isinstance(specs, dict)
    spec = specs.get("avalonia:win-x64:windows")
    assert isinstance(spec, dict)
    spec["required_proofs"] = [123]
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "summary.unresolved_external_proof_request_specs.avalonia:win-x64:windows.required_proofs contains a non-string required_proofs token"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_support_request_specs_have_unknown_required_proof_token(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )

    payload = json.loads(support_packets.read_text(encoding="utf-8"))
    specs = (
        payload.get("summary", {}).get("unresolved_external_proof_request_specs", {})
    )
    assert isinstance(specs, dict)
    spec = specs.get("avalonia:win-x64:windows")
    assert isinstance(spec, dict)
    spec["required_proofs"] = ["promoted_installer_artifact", "bogus-proof-token"]
    _write_json(support_packets, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "summary.unresolved_external_proof_request_specs.avalonia:win-x64:windows.required_proofs contains unsupported required proof token(s): bogus-proof-token"
        in result.stderr
    )


def test_verify_external_proof_closure_passes_when_all_external_gaps_are_closed(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "host_counts": {},
                "tuple_counts": {},
                "hosts": [],
                "tuples": [],
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": support_ts,
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            }
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            }
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "External-proof closure check passed." in result.stdout


def test_verify_external_proof_closure_passes_with_explicit_runbook_and_commands_bundle(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "host_counts": {},
                "tuple_counts": {},
                "hosts": [],
                "tuples": [],
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": support_ts}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "External-proof closure check passed." in result.stdout


def test_verify_external_proof_closure_fails_when_post_capture_script_drops_required_republish_tokens(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "host_counts": {},
                "tuple_counts": {},
                "hosts": [],
                "tuples": [],
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": support_ts}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    (commands_dir / "republish-after-host-proof.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\necho republish\n",
        encoding="utf-8",
    )
    (commands_dir / "republish-after-host-proof.sh").chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "external proof commands script is missing required republish token: "
        "generate-releases-manifest.sh"
    ) in result.stderr
    assert (
        "external proof commands script is missing required republish token: "
        "materialize_public_release_channel.py"
    ) in result.stderr
    assert (
        "external proof commands script is missing required republish token: "
        "--proof /docker/chummercomplete/chummer6-ui/.codex-studio/published/UI_LOCAL_RELEASE_PROOF.generated.json"
    ) in result.stderr


def test_verify_external_proof_closure_fails_when_post_capture_script_drops_fail_fast_header(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "host_counts": {},
                "tuple_counts": {},
                "hosts": [],
                "tuples": [],
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": support_ts}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    post_capture = commands_dir / "republish-after-host-proof.sh"
    post_capture.write_text(
        post_capture.read_text(encoding="utf-8").replace("set -euo pipefail\n", ""),
        encoding="utf-8",
    )
    post_capture.chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "external proof commands script is missing fail-fast token: set -euo pipefail"
    ) in result.stderr


def test_verify_external_proof_closure_fails_when_post_capture_script_only_mentions_fail_fast_in_comments(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "host_counts": {},
                "tuple_counts": {},
                "hosts": [],
                "tuples": [],
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": support_ts}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    post_capture = commands_dir / "republish-after-host-proof.sh"
    post_capture.write_text(
        post_capture.read_text(encoding="utf-8").replace("set -euo pipefail", "# set -euo pipefail"),
        encoding="utf-8",
    )
    post_capture.chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "external proof commands script is missing fail-fast token: set -euo pipefail"
    ) in result.stderr


def test_verify_external_proof_closure_fails_when_backlog_open_and_host_command_scripts_are_missing(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                    }
                },
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "proof_capture_commands": ["echo capture"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                            }
                        ],
                    }
                },
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "release_channel_generated_at": release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing required host script" in result.stderr
    assert "capture-windows-proof.sh" in result.stderr
    assert "validate-windows-proof.sh" in result.stderr
    assert "bundle-windows-proof.sh" in result.stderr
    assert "ingest-windows-proof-bundle.sh" in result.stderr


def test_verify_external_proof_closure_fails_when_windows_validation_wrapper_omits_wrapped_validation_command(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": ["cd /docker/chummercomplete/chummer6-ui && echo capture-proof"],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                                ],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": ["cd /docker/chummercomplete/chummer6-ui && echo capture-proof"],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\ncd /docker/chummercomplete/chummer6-ui && echo capture-proof\n",
        encoding="utf-8",
    )
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe\n"
        "python3 -c 'print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": "
        "\\\"windows\\\"}\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text(
        "bash -lc 'cd /docker/chummercomplete/chummer6-ui && echo capture-proof'\n",
        encoding="utf-8",
    )
    validate_ps1.write_text(
        "bash -lc 'python3 -c ''print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'''\n"
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'\n"
        "bash -lc 'python3 -c ''print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": \\\"windows\\\"}\")'''\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "windows validation wrapper is missing wrapped validation command" in result.stderr
    assert (
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_validation_scripts_omit_receipt_contract_checks(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho capture\n", encoding="utf-8")
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text("bash -lc 'echo capture'\n", encoding="utf-8")
    validate_ps1.write_text(
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing startup-smoke receipt contract checks" in result.stderr
    assert "head_id=avalonia" in result.stderr


def test_verify_external_proof_closure_fails_when_validation_scripts_omit_installer_digest_contract_checks(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho capture\n", encoding="utf-8")
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": "
        "\\\"windows\\\"}\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text("bash -lc 'echo capture'\n", encoding="utf-8")
    validate_ps1.write_text(
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'\n"
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing installer digest contract checks" in result.stderr
    assert "sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in result.stderr


def test_verify_external_proof_closure_fails_when_capture_scripts_omit_required_proof_capture_commands(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": [
                            "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                        ],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                                ],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": ["cd /docker/chummercomplete/chummer6-ui && echo capture-proof"],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe\n"
        "python3 -c 'print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": "
        "\\\"windows\\\"}\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text("bash -lc 'echo wrong-capture'\n", encoding="utf-8")
    validate_ps1.write_text(
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'\n"
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "capture script is missing tuple proof_capture_commands entry" in result.stderr
    assert "cd /docker/chummercomplete/chummer6-ui && echo capture-proof" in result.stderr


def test_verify_external_proof_closure_fails_when_capture_script_omits_expected_install_route_token(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["macos"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:osx-arm64:macos": {
                        "required_host": "macos",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-osx-arm64-installer",
                        "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
                        "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": ["echo capture-proof"],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:osx-arm64:macos"],
                "unresolved_external_proof_request_host_counts": {"macos": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:osx-arm64:macos": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"macos": 1},
                "tuple_counts": {"avalonia:osx-arm64:macos": 1},
                "hosts": ["macos"],
                "tuples": ["avalonia:osx-arm64:macos"],
                "specs": {"avalonia:osx-arm64:macos": {"required_host": "macos"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["macos"],
                "host_groups": {
                    "macos": {
                        "request_count": 1,
                        "tuples": ["avalonia:osx-arm64:macos"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:osx-arm64:macos",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-osx-arm64-installer",
                                "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
                                "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "macos",
                                    "rid": "osx-arm64",
                                    "host_class_contains": "macos",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:osx-arm64:macos"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["macos"],
                "blocked_external_only_tuples": ["avalonia:osx-arm64:macos"],
                "blocked_external_only_host_counts": {"macos": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["macos"],
                "missingRequiredPlatformHeadPairs": ["avalonia:macos"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:osx-arm64:macos",
                        "requiredHost": "macos",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expectedArtifactId": "avalonia-osx-arm64-installer",
                        "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                        "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                        "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": ["echo capture-proof"],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )

    capture_script = commands_dir / "capture-macos-proof.sh"
    validate_script = commands_dir / "validate-macos-proof.sh"
    capture_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "echo capture-proof\n"
        "echo installer-preflight-sha256-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
        "echo /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg\n",
        encoding="utf-8",
    )
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg\n"
        "python3 -c 'print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"macos\\\", \\\"rid\\\": \\\"osx-arm64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": \\\"macos\\\"}\")'\n"
        "python3 -c 'print(\"release-channel-contract-mismatch:tuple=avalonia:osx-arm64:macos expected_artifact=avalonia-osx-arm64-installer expected_route=/downloads/install/avalonia-osx-arm64-installer\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "capture script is missing expected public install route token" in result.stderr
    assert "/downloads/install/avalonia-osx-arm64-installer" in result.stderr


def test_verify_external_proof_closure_fails_when_capture_script_omits_digest_preflight_marker(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["macos"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:osx-arm64:macos": {
                        "required_host": "macos",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-osx-arm64-installer",
                        "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
                        "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": ["echo capture-proof"],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:osx-arm64:macos"],
                "unresolved_external_proof_request_host_counts": {"macos": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:osx-arm64:macos": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"macos": 1},
                "tuple_counts": {"avalonia:osx-arm64:macos": 1},
                "hosts": ["macos"],
                "tuples": ["avalonia:osx-arm64:macos"],
                "specs": {"avalonia:osx-arm64:macos": {"required_host": "macos"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["macos"],
                "host_groups": {
                    "macos": {
                        "request_count": 1,
                        "tuples": ["avalonia:osx-arm64:macos"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:osx-arm64:macos",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-osx-arm64-installer",
                                "expected_installer_file_name": "chummer-avalonia-osx-arm64-installer.dmg",
                                "expected_public_install_route": "/downloads/install/avalonia-osx-arm64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "macos",
                                    "rid": "osx-arm64",
                                    "host_class_contains": "macos",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:osx-arm64:macos"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["macos"],
                "blocked_external_only_tuples": ["avalonia:osx-arm64:macos"],
                "blocked_external_only_host_counts": {"macos": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["macos"],
                "missingRequiredPlatformHeadPairs": ["avalonia:macos"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:osx-arm64:macos"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:osx-arm64:macos",
                        "requiredHost": "macos",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expectedArtifactId": "avalonia-osx-arm64-installer",
                        "expectedInstallerFileName": "chummer-avalonia-osx-arm64-installer.dmg",
                        "expectedPublicInstallRoute": "/downloads/install/avalonia-osx-arm64-installer",
                        "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json",
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": ["echo capture-proof"],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )

    capture_script = commands_dir / "capture-macos-proof.sh"
    validate_script = commands_dir / "validate-macos-proof.sh"
    capture_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "echo capture-proof\n"
        "echo /downloads/install/avalonia-osx-arm64-installer\n"
        "echo /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg\n",
        encoding="utf-8",
    )
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-osx-arm64-installer.dmg\n"
        "python3 -c 'print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-osx-arm64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"macos\\\", \\\"rid\\\": \\\"osx-arm64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": \\\"macos\\\"}\")'\n"
        "python3 -c 'print(\"release-channel-contract-mismatch:tuple=avalonia:osx-arm64:macos expected_artifact=avalonia-osx-arm64-installer expected_route=/downloads/install/avalonia-osx-arm64-installer\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "capture script is missing installer digest preflight checks" in result.stderr
    assert "installer-preflight-sha256-mismatch" in result.stderr


def test_verify_external_proof_closure_fails_when_empty_validation_script_would_otherwise_mask_tuple_checks(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": [
                            "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                        ],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                                ],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": ["cd /docker/chummercomplete/chummer6-ui && echo capture-proof"],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")
    validate_script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n", encoding="utf-8")
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text("bash -lc 'echo wrong-capture'\n", encoding="utf-8")
    validate_ps1.write_text("bash -lc 'echo empty-validation'\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "capture script is missing tuple proof_capture_commands entry" in result.stderr
    assert "missing installer digest contract checks" in result.stderr
    assert "missing startup-smoke receipt contract checks" in result.stderr


def test_verify_external_proof_closure_fails_when_windows_capture_wrapper_omits_tuple_commands(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    tuple_capture_command = "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": [tuple_capture_command],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": [tuple_capture_command],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": [tuple_capture_command],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        f"{tuple_capture_command}\n",
        encoding="utf-8",
    )
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe\n"
        "python3 -c 'print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": "
        "\\\"windows\\\"}\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text("bash -lc 'echo wrong-capture-wrapper'\n", encoding="utf-8")
    validate_ps1.write_text(
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'\n"
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "windows capture wrapper is missing tuple proof_capture_commands entry" in result.stderr
    assert tuple_capture_command in result.stderr


def test_verify_external_proof_closure_fails_when_windows_validation_wrapper_omits_contract_tokens(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    tuple_capture_command = "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": [tuple_capture_command],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": [tuple_capture_command],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": [tuple_capture_command],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        f"{tuple_capture_command}\n",
        encoding="utf-8",
    )
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe\n"
        "python3 -c 'print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": "
        "\\\"windows\\\"}\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text(
        "bash -lc 'cd /docker/chummercomplete/chummer6-ui && echo capture-proof'\n",
        encoding="utf-8",
    )
    validate_ps1.write_text(
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'\n"
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "windows validation wrapper is missing installer digest contract checks" in result.stderr
    assert "windows validation wrapper is missing startup-smoke receipt contract checks" in result.stderr
    assert "windows validation wrapper is missing startup-smoke contract token" in result.stderr


def test_verify_external_proof_closure_fails_when_windows_wrappers_omit_fail_fast_tokens(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"
    tuple_capture_command = "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": [tuple_capture_command],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "proofCaptureCommands": [tuple_capture_command],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        f"{tuple_capture_command}\n",
        encoding="utf-8",
    )
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\necho validate\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text(
        "bash -lc 'cd /docker/chummercomplete/chummer6-ui && echo capture-proof'\n",
        encoding="utf-8",
    )
    validate_ps1.write_text(
        "bash -lc 'echo validate'\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "windows capture wrapper is missing fail-fast token" in result.stderr
    assert "windows validation wrapper is missing fail-fast token" in result.stderr


def test_verify_external_proof_closure_fails_when_windows_wrappers_only_mention_fail_fast_tokens_in_comments(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, runbook, commands_dir = (
        _write_open_windows_external_proof_fixture(tmp_path)
    )
    for wrapper_name in ("capture-windows-proof.ps1", "validate-windows-proof.ps1"):
        wrapper_path = commands_dir / wrapper_name
        wrapper_path.write_text(
            wrapper_path.read_text(encoding="utf-8")
            .replace("$ErrorActionPreference = 'Stop'", "# $ErrorActionPreference = 'Stop'")
            .replace(
                "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
                "# if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
            ),
            encoding="utf-8",
        )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "external proof windows capture wrapper is missing fail-fast token: "
        "$ErrorActionPreference = 'Stop'"
    ) in result.stderr
    assert (
        "external proof windows validation wrapper is missing fail-fast token: "
        "$ErrorActionPreference = 'Stop'"
    ) in result.stderr


def test_verify_external_proof_closure_fails_with_open_external_gaps(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 2,
                "unresolved_external_proof_request_tuples": [
                    "avalonia:osx-arm64:macos",
                    "blazor-desktop:win-x64:windows",
                ],
                "unresolved_external_proof_request_host_counts": {"macos": 1, "windows": 1},
                "unresolved_external_proof_request_tuple_counts": {
                    "avalonia:osx-arm64:macos": 1,
                    "blazor-desktop:win-x64:windows": 1,
                },
            }
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": "2026-04-05T01:22:01Z",
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_tuples": ["avalonia:osx-arm64:macos"],
                "blocked_external_only_host_counts": {"macos": 1},
            }
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["macos"],
                "missingRequiredPlatformHeadPairs": ["avalonia:macos"],
                "missingRequiredPlatformHeadRidTuples": [
                    "avalonia:osx-arm64:macos",
                ],
            }
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "External-proof closure check failed:" in result.stderr
    assert "unresolved_external_proof_request_count=2" in result.stderr
    assert "blocked_external_only_count=1" in result.stderr
    assert "avalonia:osx-arm64:macos" in result.stderr


def test_verify_external_proof_closure_fails_when_release_platform_or_head_pair_backlog_remains(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {"count": 0, "hosts": [], "tuples": [], "host_counts": {}, "tuple_counts": {}, "specs": {}},
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": "2026-04-05T01:22:01Z",
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["blazor-desktop:windows"],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missingRequiredPlatforms is not empty: windows" in result.stderr
    assert "missingRequiredPlatformHeadPairs is not empty: blazor-desktop:windows" in result.stderr


def test_verify_external_proof_closure_fails_when_release_platform_or_head_pair_fields_are_missing_or_wrong_type(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {"count": 0, "hosts": [], "tuples": [], "host_counts": {}, "tuple_counts": {}, "specs": {}},
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatformHeadPairs": "avalonia:windows",
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "desktopTupleCoverage.missingRequiredPlatforms is missing" in result.stderr
    assert "desktopTupleCoverage.missingRequiredPlatformHeadPairs is not an array" in result.stderr


def test_verify_external_proof_closure_fails_when_backlog_lists_are_non_empty_despite_zero_counts(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": [
                {
                    "tuple_id": "avalonia:win-x64:windows",
                }
            ],
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    }
                },
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {
                        "support_packets_generated_at": "2026-04-05T01:22:01Z",
                    },
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )


def test_verify_external_proof_closure_fails_when_external_requests_exist_without_missing_tuples(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {"count": 0, "hosts": [], "tuples": [], "host_counts": {}, "tuple_counts": {}, "specs": {}},
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "externalProofRequests must be empty when missingRequiredPlatformHeadRidTuples is empty"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_external_request_proofs_are_incomplete(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {"required_proofs": ["promoted_installer_artifact"]}
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_proofs": ["promoted_installer_artifact"]}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    }
                },
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "requiredProofs is missing required tokens: startup_smoke_receipt" in result.stderr

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "unresolved_external_proof_request_tuples is not empty" in result.stderr
    assert "blocked_external_only_tuples is not empty" in result.stderr
    assert "unresolved_external_proof_execution_plan.request_count=1" in result.stderr
    assert "unresolved_external_proof_execution_plan.hosts is not empty: windows" in result.stderr
    assert "unresolved_external_proof_execution_plan.host_groups still contain backlog: windows" in result.stderr
    assert "unresolved_external_proof_request_host_counts is not empty: windows:1" in result.stderr
    assert "blocked_external_only_host_counts is not empty: windows:1" in result.stderr
    assert "external_proof_requests in journey rows" in result.stderr


def test_verify_external_proof_closure_fails_when_release_channel_request_has_invalid_required_proofs_type(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = _write_open_windows_external_proof_fixture(
        tmp_path
    )

    payload = json.loads(release_channel.read_text(encoding="utf-8"))
    requests = (
        payload.get("desktopTupleCoverage", {})
        .get("externalProofRequests")
    )
    assert isinstance(requests, list) and requests
    requests[0]["requiredProofs"] = [123]
    _write_json(release_channel, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "desktopTupleCoverage.externalProofRequests[0].requiredProofs contains a non-string required_proofs token"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_release_channel_request_has_unknown_required_proof_token(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, _, _ = _write_open_windows_external_proof_fixture(
        tmp_path
    )

    payload = json.loads(release_channel.read_text(encoding="utf-8"))
    requests = (
        payload.get("desktopTupleCoverage", {})
        .get("externalProofRequests")
    )
    assert isinstance(requests, list) and requests
    requests[0]["requiredProofs"] = ["startup_smoke_receipt", "bogus-proof-token"]
    _write_json(release_channel, payload)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "release channel desktopTupleCoverage.externalProofRequests[0].requiredProofs contains unsupported required proof token(s): bogus-proof-token"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_unresolved_backlog_dict_remains_with_zero_summaries(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": {},
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                    }
                },
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": "2026-04-05T01:22:01Z",
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "unresolved_external_proof.count=1" in result.stderr
    assert "unresolved_external_proof.hosts is not empty: windows" in result.stderr
    assert "unresolved_external_proof.tuples is not empty: avalonia:win-x64:windows" in result.stderr
    assert "unresolved_external_proof.host_counts is not empty: windows:1" in result.stderr
    assert "unresolved_external_proof.tuple_counts is not empty: avalonia:win-x64:windows:1" in result.stderr
    assert "unresolved_external_proof.specs is not empty: avalonia:win-x64:windows" in result.stderr


def test_verify_external_proof_closure_fails_when_cross_plane_timestamps_drift(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": "2026-04-05T01:22:02Z",
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:50Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "release_channel_generated_at (2026-04-05T01:21:51Z) does not match release channel generatedAt (2026-04-05T01:21:50Z)"
        in result.stderr
    )
    assert "journey gates evidence.support_packets_generated_at values do not match support packets generated_at" in result.stderr


def test_verify_external_proof_closure_fails_when_execution_plan_backlog_remains_with_zero_summaries(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": [],
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": ["macos"],
                "host_groups": {
                    "macos": {
                        "request_count": 1,
                        "tuples": ["avalonia:osx-arm64:macos"],
                        "requests": [{"tuple_id": "avalonia:osx-arm64:macos"}],
                    }
                },
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": "2026-04-05T01:22:01Z",
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            }
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "unresolved_external_proof_execution_plan.hosts is not empty: macos" in result.stderr
    assert "unresolved_external_proof_execution_plan.host_groups still contain backlog: macos" in result.stderr


def test_verify_external_proof_closure_fails_when_execution_plan_generated_at_drifts(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:02Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": "2026-04-05T01:22:01Z",
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            }
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "unresolved_external_proof_execution_plan.generated_at (2026-04-05T01:22:02Z) "
        "does not match support packets generated_at (2026-04-05T01:22:01Z)"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_release_coverage_field_is_missing(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_specs": {},
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {"count": 0, "hosts": [], "tuples": [], "host_counts": {}, "tuple_counts": {}, "specs": {}},
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {},
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "desktopTupleCoverage.missingRequiredPlatformHeadRidTuples is missing" in result.stderr


def test_verify_external_proof_closure_fails_when_journey_external_proof_requests_is_malformed(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_specs": {},
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {"count": 0, "hosts": [], "tuples": [], "host_counts": {}, "tuple_counts": {}, "specs": {}},
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": {"tuple_id": "avalonia:win-x64:windows"},
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "malformed external_proof_requests payload in journey rows: install_claim_restore_continue" in result.stderr


def test_verify_external_proof_closure_fails_when_unresolved_external_proof_shape_is_invalid(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_specs": {},
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": "invalid-shape",
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "unresolved_external_proof has invalid type" in result.stderr


def test_verify_external_proof_closure_fail_closes_malformed_top_level_objects_without_traceback(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": [1],
            "unresolved_external_proof_execution_plan": [1],
        },
    )
    _write_json(
        journey_gates,
        {
            "summary": [1],
            "journeys": [],
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": [1],
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "support packets summary is missing or not an object" in result.stderr
    assert "journey gates summary is missing or not an object" in result.stderr
    assert "release channel desktopTupleCoverage is missing or not an object" in result.stderr
    assert "support packets unresolved_external_proof_execution_plan is missing or not an object" in result.stderr


def test_verify_external_proof_closure_fail_closes_invalid_numeric_count_strings_without_traceback(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": "not-a-number",
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": {},
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": "also-invalid",
                "hosts": [],
                "tuples": [],
                "host_counts": {},
                "tuple_counts": {},
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": "still-invalid",
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"}}],
            "summary": {
                "blocked_external_only_count": "bad",
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "summary.unresolved_external_proof_request_count has invalid numeric value" in result.stderr
    assert "summary.blocked_external_only_count has invalid numeric value" in result.stderr
    assert "unresolved_external_proof_execution_plan.request_count has invalid numeric value" in result.stderr
    assert "unresolved_external_proof.count has invalid numeric value" in result.stderr


def test_verify_external_proof_closure_fail_closes_invalid_map_shapes_without_traceback(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": "invalid-map",
                "unresolved_external_proof_request_tuple_counts": "invalid-map",
            },
            "unresolved_external_proof": {
                "count": 0,
                "hosts": [],
                "tuples": [],
                "host_counts": "invalid-map",
                "tuple_counts": "invalid-map",
                "specs": "invalid-map",
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": "invalid-map",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [{"evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"}}],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": "invalid-map",
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "summary.unresolved_external_proof_request_host_counts has invalid type" in result.stderr
    assert "summary.unresolved_external_proof_request_tuple_counts has invalid type" in result.stderr
    assert "summary.blocked_external_only_host_counts has invalid type" in result.stderr
    assert "unresolved_external_proof_execution_plan.host_groups has invalid type" in result.stderr
    assert "unresolved_external_proof.host_counts has invalid type" in result.stderr
    assert "unresolved_external_proof.tuple_counts has invalid type" in result.stderr
    assert "unresolved_external_proof.specs has invalid type" in result.stderr


def test_verify_external_proof_closure_fails_when_some_journey_rows_omit_support_generated_at(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "hosts": [],
                "tuples": [],
                "host_counts": {},
                "tuple_counts": {},
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                },
                {
                    "id": "report_cluster_release_notify",
                    "evidence": {},
                },
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "journey gates evidence.support_packets_generated_at is missing in journey rows: report_cluster_release_notify"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_journey_blocking_reasons_are_present_without_blockers(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "hosts": [],
                "tuples": [],
                "host_counts": {},
                "tuple_counts": {},
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "blocking_reasons": ["release channel tuple proof is stale"],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "journey gates blockers is missing in journey rows: install_claim_restore_continue"
        in result.stderr
    )


def test_verify_external_proof_closure_fail_closes_invalid_timestamp_formats(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "not-a-timestamp",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": {},
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "hosts": [],
                "tuples": [],
                "host_counts": {},
                "tuple_counts": {},
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "not-a-timestamp",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "also-not-a-timestamp",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "evidence": {
                        "support_packets_generated_at": "not-a-timestamp",
                    }
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "also-not-a-timestamp",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "generatedAt/generated_at is not a valid ISO-8601 timestamp" in result.stderr
    assert "execution_plan.generated_at/generatedAt is not a valid ISO-8601 timestamp" in result.stderr
    assert "release_channel_generated_at is not a valid ISO-8601 timestamp" in result.stderr
    assert "support_packets_generated_at includes invalid ISO-8601 timestamps: not-a-timestamp" in result.stderr


def test_verify_external_proof_closure_fails_when_journey_support_timestamp_is_missing_everywhere(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "hosts": [],
                "tuples": [],
                "host_counts": {},
                "tuple_counts": {},
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "evidence": {},
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "evidence.support_packets_generated_at is missing from all journey rows" in result.stderr


def test_verify_external_proof_closure_fails_when_open_backlog_omits_deadline_metadata(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    }
                },
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "capture_deadline_hours must be a positive integer while external-proof backlog is open" in result.stderr
    assert "capture_deadline_utc is missing while external-proof backlog is open" in result.stderr


def test_verify_external_proof_closure_fails_when_request_deadline_mismatches_plan_deadline(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "request_count": 1,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "capture_deadline_utc": "2026-04-06T02:22:01Z",
                            }
                        ],
                    }
                },
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "request capture_deadline_utc values do not match plan capture_deadline_utc" in result.stderr


def test_verify_external_proof_closure_fails_when_open_plan_request_has_no_capture_commands(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:21:51Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "capture_deadline_utc": "2026-04-06T01:21:51Z",
                                "proof_capture_commands": [],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "unresolved_external_proof_execution_plan request rows are missing proof_capture_commands for tuples: "
        "avalonia:win-x64:windows"
    ) in result.stderr


def test_verify_external_proof_closure_fails_when_open_plan_request_omits_expected_fields(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["macos"],
                "unresolved_external_proof_request_specs": ["blazor-desktop:osx-arm64:macos|macos|docker"],
                "unresolved_external_proof_request_tuples": ["blazor-desktop:osx-arm64:macos"],
                "unresolved_external_proof_request_host_counts": {"macos": 1},
                "unresolved_external_proof_request_tuple_counts": {"blazor-desktop:osx-arm64:macos": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"macos": 1},
                "tuple_counts": {"blazor-desktop:osx-arm64:macos": 1},
                "hosts": ["macos"],
                "tuples": ["blazor-desktop:osx-arm64:macos"],
                "specs": {"blazor-desktop:osx-arm64:macos": {"required_host": "macos"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:21:51Z",
                "request_count": 1,
                "hosts": ["macos"],
                "host_groups": {
                    "macos": {
                        "request_count": 1,
                        "tuples": ["blazor-desktop:osx-arm64:macos"],
                        "requests": [
                            {
                                "tuple_id": "blazor-desktop:osx-arm64:macos",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "",
                                "expected_installer_file_name": "",
                                "expected_public_install_route": "",
                                "expected_startup_smoke_receipt_path": "",
                                "capture_deadline_utc": "2026-04-06T01:21:51Z",
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "blazor-desktop:osx-arm64:macos"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["macos"],
                "blocked_external_only_tuples": ["blazor-desktop:osx-arm64:macos"],
                "blocked_external_only_host_counts": {"macos": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["macos"],
                "missingRequiredPlatformHeadPairs": ["blazor-desktop:macos"],
                "missingRequiredPlatformHeadRidTuples": ["blazor-desktop:osx-arm64:macos"],
                "externalProofRequests": [
                    {
                        "tupleId": "blazor-desktop:osx-arm64:macos",
                        "requiredHost": "macos",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "unresolved_external_proof_execution_plan request rows are missing expected fields: "
        "blazor-desktop:osx-arm64:macos:expected_artifact_id, "
        "blazor-desktop:osx-arm64:macos:expected_installer_file_name, "
        "blazor-desktop:osx-arm64:macos:expected_public_install_route, "
        "blazor-desktop:osx-arm64:macos:expected_startup_smoke_receipt_path"
    ) in result.stderr


def test_verify_external_proof_closure_fails_when_external_request_sha256_is_malformed(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expectedInstallerSha256": "not-a-sha",
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "expectedInstallerSha256 must be a 64-character lowercase sha256 hex digest" in result.stderr


def test_verify_external_proof_closure_fails_when_support_projection_drifts_from_release_request(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    expected_sha = "a" * 64
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "b" * 64,
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "c" * 64,
                                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": expected_sha,
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support external-proof projections drift from release channel desktopTupleCoverage.externalProofRequests for fields: "
        "avalonia:win-x64:windows:expected_installer_sha256"
    ) in result.stderr


def test_verify_external_proof_closure_fails_when_support_projection_drifts_on_installer_relative_path(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    expected_sha = "a" * 64
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_installer_relative_path": "quarantine/chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": expected_sha,
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_installer_relative_path": "quarantine/chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": expected_sha,
                                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expectedArtifactId": "avalonia-win-x64-installer",
                        "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                        "expectedInstallerRelativePath": "files/chummer-avalonia-win-x64-installer.exe",
                        "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                        "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expectedInstallerSha256": expected_sha,
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support external-proof projections drift from release channel desktopTupleCoverage.externalProofRequests for fields: "
        "avalonia:win-x64:windows:expected_installer_relative_path"
    ) in result.stderr


def test_verify_external_proof_closure_fails_when_support_projection_drifts_on_startup_smoke_receipt_contract(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    expected_sha = "a" * 64
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": expected_sha,
                        "startup_smoke_receipt_contract": {
                            "status_any_of": ["passed"],
                            "head_id": "blazor-desktop",
                            "platform": "windows",
                            "rid": "win-x64",
                        },
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": expected_sha,
                                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                                "startup_smoke_receipt_contract": {
                                    "status_any_of": ["passed"],
                                    "head_id": "blazor-desktop",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                },
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": expected_sha,
                        "startupSmokeReceiptContract": {
                            "statusAnyOf": ["passed"],
                            "headId": "avalonia",
                            "platform": "windows",
                            "rid": "win-x64",
                        },
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support external-proof projections drift from release channel desktopTupleCoverage.externalProofRequests for fields: "
    ) in result.stderr
    assert "avalonia:win-x64:windows:startup_smoke_receipt_contract" in result.stderr


def test_verify_external_proof_closure_fails_when_support_projection_drifts_on_proof_capture_commands(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    expected_sha = "a" * 64
    _write_json(
        support_packets,
        {
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": expected_sha,
                        "proof_capture_commands": ["echo stale-capture-command"],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": "2026-04-05T01:22:01Z",
                "release_channel_generated_at": "2026-04-05T01:21:51Z",
                "capture_deadline_hours": 24,
                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": expected_sha,
                                "capture_deadline_utc": "2026-04-06T01:22:01Z",
                                "proof_capture_commands": ["echo stale-capture-command"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": "2026-04-05T01:22:01Z"},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": expected_sha,
                        "proofCaptureCommands": ["echo release-capture-command"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support external-proof projections drift from release channel desktopTupleCoverage.externalProofRequests for fields: "
    ) in result.stderr
    assert "avalonia:win-x64:windows:proof_capture_commands" in result.stderr


def test_verify_external_proof_closure_fails_when_core_evidence_is_stale(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    stale_release_ts = _iso_z(datetime.now(timezone.utc) - timedelta(hours=4))
    stale_support_ts = _iso_z(datetime.now(timezone.utc) - timedelta(hours=3))
    _write_json(
        support_packets,
        {
            "generated_at": stale_support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
                "unresolved_external_proof_request_host_counts": {},
                "unresolved_external_proof_request_tuple_counts": {},
            },
            "unresolved_external_proof": {
                "count": 0,
                "hosts": [],
                "tuples": [],
                "host_counts": {},
                "tuple_counts": {},
                "specs": {},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": stale_support_ts,
                "request_count": 0,
                "hosts": [],
                "host_groups": {},
                "release_channel_generated_at": stale_release_ts,
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "evidence": {"support_packets_generated_at": stale_support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 0,
                "blocked_external_only_hosts": [],
                "blocked_external_only_tuples": [],
                "blocked_external_only_host_counts": {},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": stale_release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": [],
                "missingRequiredPlatformHeadPairs": [],
                "missingRequiredPlatformHeadRidTuples": [],
                "externalProofRequests": [],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--max-artifact-age-hours",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "release channel generatedAt/generated_at is stale" in result.stderr
    assert "support packets generated_at/generatedAt is stale" in result.stderr
    assert "journey gates evidence.support_packets_generated_at is stale" in result.stderr


def test_verify_external_proof_closure_fails_when_deadline_utc_does_not_match_generated_plus_hours(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    release_ts = datetime.now(timezone.utc) - timedelta(seconds=30)
    support_ts = datetime.now(timezone.utc)
    wrong_deadline_ts = support_ts + timedelta(hours=26)
    _write_json(
        support_packets,
        {
            "generated_at": _iso_z(support_ts),
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": _iso_z(support_ts),
                "release_channel_generated_at": _iso_z(release_ts),
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(wrong_deadline_ts),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "capture_deadline_utc": _iso_z(wrong_deadline_ts),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": _iso_z(support_ts)},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": _iso_z(release_ts),
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "capture_deadline_utc does not match "
        "support packets unresolved_external_proof_execution_plan.release_channel_generated_at plus capture_deadline_hours"
    ) in result.stderr


def test_verify_external_proof_closure_accepts_deadline_anchored_to_release_channel_timestamp(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    release_ts = datetime.now(timezone.utc) - timedelta(minutes=5)
    support_ts = datetime.now(timezone.utc)
    release_anchored_deadline_ts = release_ts + timedelta(hours=24)
    _write_json(
        support_packets,
        {
            "generated_at": _iso_z(support_ts),
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": _iso_z(support_ts),
                "release_channel_generated_at": _iso_z(release_ts),
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(release_anchored_deadline_ts),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "capture_deadline_utc": _iso_z(release_anchored_deadline_ts),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": _iso_z(support_ts)},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": _iso_z(release_ts),
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "support packets unresolved_external_proof_request_count=1 (expected 0)" in result.stderr
    assert "capture_deadline_utc does not match" not in result.stderr


def test_verify_external_proof_closure_fails_when_open_backlog_deadline_has_passed(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    release_ts = datetime.now(timezone.utc) - timedelta(hours=2)
    support_ts = datetime.now(timezone.utc) - timedelta(minutes=5)
    expired_deadline_ts = datetime.now(timezone.utc) - timedelta(minutes=2)
    _write_json(
        support_packets,
        {
            "generated_at": _iso_z(support_ts),
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": _iso_z(support_ts),
                "release_channel_generated_at": _iso_z(release_ts),
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(expired_deadline_ts),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "capture_deadline_utc": _iso_z(expired_deadline_ts),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": _iso_z(support_ts)},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": _iso_z(release_ts),
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "capture_deadline_utc has passed while external-proof backlog remains open" in result.stderr


def test_verify_external_proof_closure_checks_required_hosts_from_release_channel_when_plan_hosts_drift(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": [],
                "host_groups": {},
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing required host script" in result.stderr
    assert "capture-windows-proof.sh" in result.stderr
    assert "validate-windows-proof.sh" in result.stderr


def test_verify_external_proof_closure_fails_when_external_backlog_rows_omit_expected_sha256(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": ["avalonia:win-x64:windows|windows|docker"],
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "proof_capture_commands": ["echo capture"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "request rows are missing expected_installer_sha256 for tuples: avalonia:win-x64:windows" in result.stderr
    assert "rows are missing expectedInstallerSha256 for tuples: avalonia:win-x64:windows" in result.stderr


def test_verify_external_proof_closure_fails_when_validation_scripts_omit_release_channel_contract_checks(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    release_ts = _iso_z(now - timedelta(minutes=1))
    support_ts = _iso_z(now)
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    runbook = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    commands_dir = tmp_path / "external-proof-commands"

    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                        "proof_capture_commands": ["cd /docker/chummercomplete/chummer6-ui && echo capture-proof"],
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "startup_smoke_receipt_contract": {
                                    "ready_checkpoint": "pre_ui_event_loop",
                                    "head_id": "avalonia",
                                    "platform": "windows",
                                    "rid": "win-x64",
                                    "host_class_contains": "windows",
                                    "status_any_of": ["pass", "ready"],
                                },
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": [
                                    "cd /docker/chummercomplete/chummer6-ui && echo capture-proof"
                                ],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                        "proofCaptureCommands": ["cd /docker/chummercomplete/chummer6-ui && echo capture-proof"],
                    }
                ],
            },
        },
    )
    _write_external_proof_bundle(
        runbook_path=runbook,
        commands_dir=commands_dir,
        support_generated_at=support_ts,
        release_generated_at=release_ts,
    )
    capture_script = commands_dir / "capture-windows-proof.sh"
    validate_script = commands_dir / "validate-windows-proof.sh"
    capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    capture_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\ncd /docker/chummercomplete/chummer6-ui && echo capture-proof\n",
        encoding="utf-8",
    )
    validate_script.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe\n"
        "python3 -c 'print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'\n"
        "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json\n"
        "python3 -c 'print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": "
        "\\\"windows\\\"}\")'\n",
        encoding="utf-8",
    )
    capture_script.chmod(0o755)
    validate_script.chmod(0o755)
    capture_ps1.write_text(
        "bash -lc 'cd /docker/chummercomplete/chummer6-ui && echo capture-proof'\n",
        encoding="utf-8",
    )
    validate_ps1.write_text(
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'\n"
        "bash -lc 'python3 -c ''print(\"installer-contract-mismatch:sha256=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\")'''\n"
        "bash -lc 'test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json'\n"
        "bash -lc 'python3 -c ''print(\"receipt-contract-mismatch:{\\\"head_id\\\": \\\"avalonia\\\", \\\"platform\\\": \\\"windows\\\", "
        "\\\"rid\\\": \\\"win-x64\\\", \\\"ready_checkpoint\\\": \\\"pre_ui_event_loop\\\", \\\"host_class_contains\\\": \\\"windows\\\"}\")'''\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing release-channel tuple contract checks" in result.stderr
    assert "expected_artifact_id=avalonia-win-x64-installer" in result.stderr
    assert "expected_public_install_route=/downloads/install/avalonia-win-x64-installer" in result.stderr


def test_verify_external_proof_closure_fails_when_bundle_script_omits_archive_creation_token(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, runbook, commands_dir = _write_open_windows_external_proof_fixture(
        tmp_path
    )
    bundle_script = commands_dir / "bundle-windows-proof.sh"
    bundle_payload = bundle_script.read_text(encoding="utf-8")
    bundle_script.write_text(
        bundle_payload.replace("tar -czf", "echo bundle-archive-disabled"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external proof bundle script is missing bundle archive creation command" in result.stderr
    assert "tar -czf" in result.stderr


def test_verify_external_proof_closure_fails_when_finalize_script_is_missing_required_host_tokens(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, runbook, commands_dir = _write_open_windows_external_proof_fixture(
        tmp_path
    )
    finalize_script = commands_dir / "finalize-external-host-proof.sh"
    finalize_payload = finalize_script.read_text(encoding="utf-8")
    finalize_script.write_text(
        finalize_payload.replace("./validate-windows-proof.sh", "echo validate-step-disabled"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external proof finalize script is missing required host token" in result.stderr
    assert "./validate-windows-proof.sh" in result.stderr


def test_verify_external_proof_closure_fails_when_ingest_script_omits_expected_file_existence_check(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, runbook, commands_dir = _write_open_windows_external_proof_fixture(
        tmp_path
    )
    ingest_script = commands_dir / "ingest-windows-proof-bundle.sh"
    ingest_payload = ingest_script.read_text(encoding="utf-8")
    ingest_script.write_text(
        ingest_payload.replace(
            "test -s \"$TARGET_ROOT/files/chummer-avalonia-win-x64-installer.exe\"",
            "echo installer-file-check-disabled",
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external proof ingest script is missing expected installer existence check token" in result.stderr
    assert "test -s \"$TARGET_ROOT/files/chummer-avalonia-win-x64-installer.exe\"" in result.stderr


def test_verify_external_proof_closure_fails_when_ingest_script_omits_archive_path_safety_validation_token(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, runbook, commands_dir = _write_open_windows_external_proof_fixture(
        tmp_path
    )
    ingest_script = commands_dir / "ingest-windows-proof-bundle.sh"
    ingest_payload = ingest_script.read_text(encoding="utf-8")
    ingest_script.write_text(
        ingest_payload.replace("member.name.startswith(", "member_name_startswith("),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external proof ingest script is missing archive path-safety validation token" in result.stderr
    assert "member.name.startswith(" in result.stderr


def test_verify_external_proof_closure_fails_when_ingest_script_omits_installer_digest_contract_checks(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, runbook, commands_dir = _write_open_windows_external_proof_fixture(
        tmp_path
    )
    ingest_script = commands_dir / "ingest-windows-proof-bundle.sh"
    ingest_payload = ingest_script.read_text(encoding="utf-8")
    ingest_script.write_text(
        ingest_payload.replace("installer-contract-mismatch", "installer-digest-check-disabled"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external proof ingest script is missing installer digest contract checks" in result.stderr
    assert "installer-contract-mismatch" in result.stderr


def test_verify_external_proof_closure_fails_when_ingest_script_omits_receipt_contract_checks(
    tmp_path: Path,
) -> None:
    support_packets, journey_gates, release_channel, runbook, commands_dir = _write_open_windows_external_proof_fixture(
        tmp_path
    )
    ingest_script = commands_dir / "ingest-windows-proof-bundle.sh"
    ingest_payload = ingest_script.read_text(encoding="utf-8")
    ingest_script.write_text(
        ingest_payload.replace("receipt-contract-mismatch", "receipt-contract-check-disabled"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
            "--external-proof-runbook",
            str(runbook),
            "--external-proof-commands-dir",
            str(commands_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "external proof ingest script is missing startup-smoke receipt contract checks" in result.stderr
    assert "receipt-contract-mismatch" in result.stderr


def test_verify_external_proof_closure_fails_when_support_backlog_has_absolute_expected_installer_relative_path(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    now = datetime.now(timezone.utc)
    support_ts = _iso_z(now)
    release_ts = _iso_z(now - timedelta(minutes=1))
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_installer_relative_path": "/tmp/avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_installer_relative_path": "/tmp/avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
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
                        "expectedInstallerSha256": "a" * 64,
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "support packets unresolved_external_proof_execution_plan request rows have invalid expected_installer_relative_path values"
        in result.stderr
    )


def test_verify_external_proof_closure_fails_when_release_channel_request_has_invalid_startup_smoke_receipt_relative_path(
    tmp_path: Path,
) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    now = datetime.now(timezone.utc)
    support_ts = _iso_z(now)
    release_ts = _iso_z(now - timedelta(minutes=1))
    _write_json(
        support_packets,
        {
            "generated_at": support_ts,
            "summary": {
                "unresolved_external_proof_request_count": 1,
                "unresolved_external_proof_request_hosts": ["windows"],
                "unresolved_external_proof_request_specs": {
                    "avalonia:win-x64:windows": {
                        "required_host": "windows",
                        "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expected_artifact_id": "avalonia-win-x64-installer",
                        "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                        "expected_installer_relative_path": "files/chummer-avalonia-win-x64-installer.exe",
                        "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                        "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expected_installer_sha256": "a" * 64,
                    }
                },
                "unresolved_external_proof_request_tuples": ["avalonia:win-x64:windows"],
                "unresolved_external_proof_request_host_counts": {"windows": 1},
                "unresolved_external_proof_request_tuple_counts": {"avalonia:win-x64:windows": 1},
            },
            "unresolved_external_proof": {
                "count": 1,
                "host_counts": {"windows": 1},
                "tuple_counts": {"avalonia:win-x64:windows": 1},
                "hosts": ["windows"],
                "tuples": ["avalonia:win-x64:windows"],
                "specs": {"avalonia:win-x64:windows": {"required_host": "windows"}},
            },
            "unresolved_external_proof_execution_plan": {
                "generated_at": support_ts,
                "release_channel_generated_at": release_ts,
                "capture_deadline_hours": 24,
                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                "request_count": 1,
                "hosts": ["windows"],
                "host_groups": {
                    "windows": {
                        "request_count": 1,
                        "tuples": ["avalonia:win-x64:windows"],
                        "requests": [
                            {
                                "tuple_id": "avalonia:win-x64:windows",
                                "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                "expected_artifact_id": "avalonia-win-x64-installer",
                                "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                "expected_installer_relative_path": "files/chummer-avalonia-win-x64-installer.exe",
                                "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                "expected_installer_sha256": "a" * 64,
                                "capture_deadline_utc": _iso_z(now + timedelta(hours=24)),
                                "proof_capture_commands": ["echo capture-proof"],
                            }
                        ],
                    }
                },
            },
        },
    )
    _write_json(
        journey_gates,
        {
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "external_proof_requests": [{"tuple_id": "avalonia:win-x64:windows"}],
                    "evidence": {"support_packets_generated_at": support_ts},
                }
            ],
            "summary": {
                "blocked_external_only_count": 1,
                "blocked_external_only_hosts": ["windows"],
                "blocked_external_only_tuples": ["avalonia:win-x64:windows"],
                "blocked_external_only_host_counts": {"windows": 1},
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": release_ts,
            "desktopTupleCoverage": {
                "missingRequiredPlatforms": ["windows"],
                "missingRequiredPlatformHeadPairs": ["avalonia:windows"],
                "missingRequiredPlatformHeadRidTuples": ["avalonia:win-x64:windows"],
                "externalProofRequests": [
                    {
                        "tupleId": "avalonia:win-x64:windows",
                        "requiredHost": "windows",
                        "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                        "expectedArtifactId": "avalonia-win-x64-installer",
                        "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                        "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                        "expectedStartupSmokeReceiptPath": "../startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                        "expectedInstallerSha256": "a" * 64,
                    }
                ],
            },
        },
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--support-packets",
            str(support_packets),
            "--journey-gates",
            str(journey_gates),
            "--release-channel",
            str(release_channel),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert (
        "release channel desktopTupleCoverage.externalProofRequests rows have invalid expectedStartupSmokeReceiptPath values"
        in result.stderr
    )
