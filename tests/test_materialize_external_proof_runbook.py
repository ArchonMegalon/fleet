from __future__ import annotations

import json
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
                                    "expected_public_install_route": "/downloads/install/avalonia-win-x64-installer",
                                    "expected_startup_smoke_receipt_path": "startup-smoke/startup-smoke-avalonia-win-x64.receipt.json",
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
    assert "# External Proof Runbook" in payload
    assert "## Host: windows" in payload
    assert "## Host: macos" in payload
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
    assert "  commands:" in payload
    assert "## After Host Proof Capture" in payload
    assert "python3 scripts/materialize_support_case_packets.py" in payload
    assert "python3 scripts/materialize_journey_gates.py" in payload
    assert "python3 scripts/verify_external_proof_closure.py" in payload
    assert "python3 scripts/ai/materialize_weekly_product_pulse_snapshot.py" in payload


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
    assert payload.count("${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}/downloads/install/") == 4
    assert "    - `echo tuple-1-proof`" in payload
    assert "    - `echo tuple-2-proof`" in payload
    assert payload.count("\ncd /docker/chummercomplete/chummer6-ui && ./scripts/generate-releases-manifest.sh\n") == 1


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
    assert "unresolved_request_count: 0" in payload
    assert "No unresolved external-proof requests are currently queued." in payload
