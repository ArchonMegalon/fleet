#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


DEFAULT_SUPPORT_PACKETS = Path("/docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json")
DEFAULT_JOURNEY_GATES = Path("/docker/fleet/.codex-studio/published/JOURNEY_GATES.generated.json")
DEFAULT_RELEASE_CHANNEL = Path(
    "/docker/chummercomplete/chummer-hub-registry/.codex-studio/published/RELEASE_CHANNEL.generated.json"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail closed when desktop external-proof closure is still incomplete across support packets, "
            "journey gates, or release-channel tuple coverage."
        )
    )
    parser.add_argument("--support-packets", type=Path, default=DEFAULT_SUPPORT_PACKETS)
    parser.add_argument("--journey-gates", type=Path, default=DEFAULT_JOURNEY_GATES)
    parser.add_argument("--release-channel", type=Path, default=DEFAULT_RELEASE_CHANNEL)
    return parser.parse_args()


def _load_json(path: Path, *, label: str) -> Dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"{label} not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} root must be a JSON object: {path}")
    return payload


def main() -> int:
    args = _parse_args()
    support_packets = _load_json(args.support_packets, label="support packets")
    journey_gates = _load_json(args.journey_gates, label="journey gates")
    release_channel = _load_json(args.release_channel, label="release channel")

    support_summary = dict(support_packets.get("summary") or {})
    journey_summary = dict(journey_gates.get("summary") or {})
    tuple_coverage = dict(release_channel.get("desktopTupleCoverage") or {})

    unresolved_count = int(support_summary.get("unresolved_external_proof_request_count") or 0)
    blocked_external_only_count = int(journey_summary.get("blocked_external_only_count") or 0)
    missing_tuples = [
        str(item).strip()
        for item in (tuple_coverage.get("missingRequiredPlatformHeadRidTuples") or [])
        if str(item).strip()
    ]

    failures: list[str] = []
    if unresolved_count > 0:
        failures.append(
            f"support packets unresolved_external_proof_request_count={unresolved_count} (expected 0)"
        )
    if blocked_external_only_count > 0:
        failures.append(
            f"journey gates blocked_external_only_count={blocked_external_only_count} (expected 0)"
        )
    if missing_tuples:
        failures.append(
            "release channel missingRequiredPlatformHeadRidTuples is not empty: "
            + ", ".join(missing_tuples)
        )

    if failures:
        print("External-proof closure check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("External-proof closure check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
