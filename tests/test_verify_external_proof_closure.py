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
            }
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
