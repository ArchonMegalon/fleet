from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/verify_external_proof_closure.py")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_verify_external_proof_closure_passes_when_all_external_gaps_are_closed(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "summary": {
                "unresolved_external_proof_request_count": 0,
            }
        },
    )
    _write_json(
        journey_gates,
        {
            "summary": {
                "blocked_external_only_count": 0,
            }
        },
    )
    _write_json(
        release_channel,
        {
            "desktopTupleCoverage": {
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

    assert result.returncode == 0, result.stderr
    assert "External-proof closure check passed." in result.stdout


def test_verify_external_proof_closure_fails_with_open_external_gaps(tmp_path: Path) -> None:
    support_packets = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    journey_gates = tmp_path / "JOURNEY_GATES.generated.json"
    release_channel = tmp_path / "RELEASE_CHANNEL.generated.json"
    _write_json(
        support_packets,
        {
            "summary": {
                "unresolved_external_proof_request_count": 2,
            }
        },
    )
    _write_json(
        journey_gates,
        {
            "summary": {
                "blocked_external_only_count": 1,
            }
        },
    )
    _write_json(
        release_channel,
        {
            "desktopTupleCoverage": {
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
