from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/materialize_external_proof_runbook.py")


def test_materialize_external_proof_runbook_groups_requests_by_host(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 2,
                    "hosts": ["macos", "windows"],
                    "generated_at": "2026-04-05T00:00:00Z",
                    "release_channel_generated_at": "2026-04-05T00:00:00Z",
                    "capture_deadline_hours": 24,
                    "capture_deadline_utc": "2026-04-06T00:00:00Z",
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
                                    "expected_installer_sha256": "a" * 64,
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "startup_smoke_receipt_contract": {
                                        "ready_checkpoint": "pre_ui_event_loop",
                                        "head_id": "avalonia",
                                        "platform": "windows",
                                        "rid": "win-x64",
                                        "host_class_contains": "windows",
                                        "status_any_of": ["pass", "ready"],
                                    },
                                    "capture_deadline_utc": "2026-04-06T00:00:00Z",
                                    "proof_capture_commands": [
                                        "echo windows-proof",
                                        "echo refresh-manifest",
                                    ],
                                }
                            ],
                        },
                        "macos": {
                            "request_count": 1,
                            "tuples": ["blazor-desktop:osx-arm64:macos"],
                            "requests": [
                                {
                                    "tuple_id": "blazor-desktop:osx-arm64:macos",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "blazor-desktop-osx-arm64-installer",
                                    "expected_installer_file_name": "chummer-blazor-desktop-osx-arm64-installer.dmg",
                                    "expected_public_install_route": "/downloads/install/blazor-desktop-osx-arm64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-osx-arm64.receipt.json",
                                    "startup_smoke_receipt_contract": {
                                        "ready_checkpoint": "pre_ui_event_loop",
                                        "head_id": "blazor-desktop",
                                        "platform": "macos",
                                        "rid": "osx-arm64",
                                        "host_class_contains": "macos",
                                        "status_any_of": ["pass", "ready"],
                                    },
                                    "capture_deadline_utc": "2026-04-06T00:00:00Z",
                                    "proof_capture_commands": [
                                        "echo macos-proof",
                                        "echo refresh-manifest",
                                    ],
                                }
                            ],
                        },
                    },
                }
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
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    commands_dir = out.parent / "external-proof-commands"
    windows_capture = commands_dir / "capture-windows-proof.sh"
    windows_validate = commands_dir / "validate-windows-proof.sh"
    windows_capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    windows_validate_ps1 = commands_dir / "validate-windows-proof.ps1"
    macos_capture = commands_dir / "capture-macos-proof.sh"
    macos_validate = commands_dir / "validate-macos-proof.sh"
    post_capture = commands_dir / "republish-after-host-proof.sh"

    assert "# External Proof Runbook" in payload
    assert "## Generated Command Files" in payload
    assert f"commands_dir: `{commands_dir}`" in payload
    assert "## Host: windows" in payload
    assert "## Host: macos" in payload
    assert "shell_hint: Run canonical commands in Git Bash (or WSL bash)." in payload
    assert "shell_hint: Run commands in a POSIX shell (bash/zsh) on the required host." in payload
    assert "plan_generated_at: 2026-04-05T00:00:00Z" in payload
    assert "capture_deadline_hours: 24" in payload
    assert "capture_deadline_utc: 2026-04-06T00:00:00Z" in payload
    assert "`avalonia:win-x64:windows`" in payload
    assert "`blazor-desktop:osx-arm64:macos`" in payload
    assert "capture_deadline_state: `pending`" in payload or "capture_deadline_state: `overdue`" in payload
    assert "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/avalonia-win-x64-installer" in payload
    assert "${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/blazor-desktop-osx-arm64-installer" in payload
    assert "echo windows-proof" in payload
    assert "echo macos-proof" in payload
    assert payload.count("`echo refresh-manifest`") == 2
    assert payload.count("\necho refresh-manifest\n") == 2
    assert "### Commands (Host Consolidated)" in payload
    assert "### Commands (Host Validation)" in payload
    assert "### Commands (PowerShell Wrappers)" in payload
    assert "### Commands (PowerShell Validation Wrappers)" in payload
    assert "```powershell" in payload
    assert "bash -lc 'echo windows-proof'" in payload
    assert "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" in payload
    assert "hashlib.sha256" in payload
    assert "installer-contract-mismatch" in payload
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in payload
    assert "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/startup-smoke/startup-smoke-avalonia-win-x64.receipt.json" in payload
    assert "receipt-contract-mismatch" in payload
    assert "readyCheckpoint" in payload
    assert "hostClass" in payload
    assert "\"head_id\": \"avalonia\"" in payload
    assert "bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'" in payload
    assert "  commands:" in payload
    assert "## After Host Proof Capture" in payload
    assert "python3 scripts/materialize_support_case_packets.py" in payload
    assert "python3 scripts/materialize_status_plane.py" in payload
    assert "python3 scripts/verify_status_plane_semantics.py" in payload
    assert "python3 scripts/materialize_public_release_channel.py" in payload
    assert "--proof " not in payload
    assert "--ui-localization-release-gate " not in payload
    assert "python3 scripts/verify_public_release_channel.py" in payload
    assert "--release-channel /docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json" in payload
    assert payload.index("python3 scripts/materialize_status_plane.py") < payload.index(
        "python3 scripts/materialize_journey_gates.py"
    )
    assert payload.index("python3 scripts/materialize_public_progress_report.py") < payload.index(
        "python3 scripts/materialize_journey_gates.py"
    )
    assert "python3 scripts/materialize_journey_gates.py" in payload
    assert "python3 scripts/verify_external_proof_closure.py" in payload
    assert "--external-proof-runbook .codex-studio/published/EXTERNAL_PROOF_RUNBOOK.generated.md" in payload
    assert "--external-proof-commands-dir .codex-studio/published/external-proof-commands" in payload
    assert "python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py" in payload
    assert windows_capture.is_file()
    assert windows_validate.is_file()
    assert windows_capture_ps1.is_file()
    assert windows_validate_ps1.is_file()
    assert macos_capture.is_file()
    assert macos_validate.is_file()
    assert post_capture.is_file()
    assert os.access(windows_capture, os.X_OK)
    assert os.access(macos_capture, os.X_OK)
    assert os.access(post_capture, os.X_OK)
    assert "echo windows-proof" in windows_capture.read_text(encoding="utf-8")
    assert "echo macos-proof" in macos_capture.read_text(encoding="utf-8")
    assert "test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe" in windows_validate.read_text(
        encoding="utf-8"
    )
    assert "installer-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "receipt-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "bash -lc 'echo windows-proof'" in windows_capture_ps1.read_text(encoding="utf-8")
    assert "python3 scripts/materialize_support_case_packets.py" in post_capture.read_text(encoding="utf-8")
    assert "--proof " not in post_capture.read_text(encoding="utf-8")
    assert "--ui-localization-release-gate " not in post_capture.read_text(encoding="utf-8")


def test_materialize_external_proof_runbook_preserves_per_tuple_command_sequences(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 2,
                    "hosts": ["windows"],
                    "host_groups": {
                        "windows": {
                            "request_count": 2,
                            "tuples": [
                                "avalonia:win-x64:windows",
                                "blazor-desktop:win-x64:windows",
                            ],
                            "requests": [
                                {
                                    "tuple_id": "avalonia:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "avalonia-win-x64-installer",
                                    "expected_installer_file_name": "chummer-avalonia-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "proof_capture_commands": [
                                        "echo tuple-1-proof",
                                        "echo refresh-manifest",
                                    ],
                                },
                                {
                                    "tuple_id": "blazor-desktop:win-x64:windows",
                                    "required_proofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expected_artifact_id": "blazor-desktop-win-x64-installer",
                                    "expected_installer_file_name": "chummer-blazor-desktop-win-x64-installer.exe",
                                    "expected_public_install_route": "/downloads/install/blazor-desktop-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-blazor-desktop-win-x64.receipt.json",
                                    "proof_capture_commands": [
                                        "echo tuple-2-proof",
                                        "echo refresh-manifest",
                                    ],
                                },
                            ],
                        }
                    },
                }
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
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    assert payload.count("`echo refresh-manifest`") == 2
    assert payload.count("\necho refresh-manifest\n") == 1
    assert payload.count("${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/") >= 4
    assert payload.count("\nbash -lc '") >= 5
    assert "    - `echo tuple-1-proof`" in payload
    assert "    - `echo tuple-2-proof`" in payload
    assert payload.count("\ncd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh\n") == 1
    assert "### Commands (Host Validation)" in payload
    assert payload.count("\ncd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-") == 2


def test_materialize_external_proof_runbook_reports_no_backlog(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "request_count": 0,
                    "hosts": [],
                    "host_groups": {},
                }
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
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    commands_dir = out.parent / "external-proof-commands"
    assert "unresolved_request_count: 0" in payload
    assert "## Generated Command Files" in payload
    assert f"commands_dir: `{commands_dir}`" in payload
    assert "No unresolved external-proof requests are currently queued." in payload
    assert (commands_dir / "republish-after-host-proof.sh").is_file()


def test_materialize_external_proof_runbook_accepts_camel_case_plan_fields(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    out = tmp_path / "EXTERNAL_PROOF_RUNBOOK.generated.md"
    support_packets.write_text(
        json.dumps(
            {
                "unresolved_external_proof_execution_plan": {
                    "requestCount": 1,
                    "hosts": ["windows"],
                    "generatedAt": "2026-04-05T00:00:00Z",
                    "releaseChannelGeneratedAt": "2026-04-05T00:00:00Z",
                    "captureDeadlineHours": 24,
                    "captureDeadlineUtc": "2026-04-06T00:00:00Z",
                    "hostGroups": {
                        "windows": {
                            "requestCount": 1,
                            "tupleIds": ["avalonia:win-x64:windows"],
                            "requests": [
                                {
                                    "tupleId": "avalonia:win-x64:windows",
                                    "requiredProofs": ["promoted_installer_artifact", "startup_smoke_receipt"],
                                    "expectedArtifactId": "avalonia-win-x64-installer",
                                    "expectedInstallerFileName": "chummer-avalonia-win-x64-installer.exe",
                                    "expectedInstallerSha256": "a" * 64,
                                    "expectedPublicInstallRoute": "/downloads/install/avalonia-win-x64-installer",
                                    "expectedStartupSmokeReceiptPath": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
                                    "startupSmokeReceiptContract": {
                                        "readyCheckpoint": "pre_ui_event_loop",
                                        "headId": "avalonia",
                                        "platform": "windows",
                                        "rid": "win-x64",
                                        "hostClassContains": "windows",
                                        "statusAnyOf": ["pass", "ready"],
                                    },
                                    "captureDeadlineUtc": "2026-04-06T00:00:00Z",
                                    "proofCaptureCommands": [
                                        "echo windows-proof",
                                        "echo refresh-manifest",
                                    ],
                                }
                            ],
                        }
                    },
                }
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
            "--support-packets",
            str(support_packets),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = out.read_text(encoding="utf-8")
    commands_dir = out.parent / "external-proof-commands"
    windows_capture = commands_dir / "capture-windows-proof.sh"
    windows_validate = commands_dir / "validate-windows-proof.sh"
    windows_capture_ps1 = commands_dir / "capture-windows-proof.ps1"
    windows_validate_ps1 = commands_dir / "validate-windows-proof.ps1"

    assert "plan_generated_at: 2026-04-05T00:00:00Z" in payload
    assert "release_channel_generated_at: 2026-04-05T00:00:00Z" in payload
    assert "capture_deadline_hours: 24" in payload
    assert "capture_deadline_utc: 2026-04-06T00:00:00Z" in payload
    assert "`avalonia:win-x64:windows`" in payload
    assert "echo windows-proof" in windows_capture.read_text(encoding="utf-8")
    assert "installer-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "receipt-contract-mismatch" in windows_validate.read_text(encoding="utf-8")
    assert "bash -lc 'echo windows-proof'" in windows_capture_ps1.read_text(encoding="utf-8")
    assert "bash -lc 'cd /docker/chummercomplete/chummer6-ui && test -s /docker/chummercomplete/chummer6-ui/Docker/Downloads/files/chummer-avalonia-win-x64-installer.exe'" in windows_validate_ps1.read_text(encoding="utf-8")
