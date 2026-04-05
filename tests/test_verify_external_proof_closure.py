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
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 0,
                "unresolved_external_proof_request_hosts": [],
                "unresolved_external_proof_request_specs": [],
                "unresolved_external_proof_request_tuples": [],
            },
            "unresolved_external_proof": [],
            "unresolved_external_proof_execution_plan": {
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
            }
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
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
            "generated_at": "2026-04-05T01:22:01Z",
            "summary": {
                "unresolved_external_proof_request_count": 2,
                "unresolved_external_proof_request_tuples": [
                    "avalonia:osx-arm64:macos",
                    "blazor-desktop:win-x64:windows",
                ],
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
            }
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
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
            },
            "unresolved_external_proof": [
                {
                    "tuple_id": "avalonia:win-x64:windows",
                }
            ],
            "unresolved_external_proof_execution_plan": {
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
            },
        },
    )
    _write_json(
        release_channel,
        {
            "generatedAt": "2026-04-05T01:21:51Z",
            "desktopTupleCoverage": {
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
    assert "unresolved_external_proof_request_tuples is not empty" in result.stderr
    assert "blocked_external_only_tuples is not empty" in result.stderr
    assert "external_proof_requests in journey rows" in result.stderr


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
