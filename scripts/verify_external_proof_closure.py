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
    support_plan = dict(support_packets.get("unresolved_external_proof_execution_plan") or {})
    journey_rows = [
        dict(item)
        for item in (journey_gates.get("journeys") or [])
        if isinstance(item, dict)
    ]

    unresolved_count = int(support_summary.get("unresolved_external_proof_request_count") or 0)
    blocked_external_only_count = int(journey_summary.get("blocked_external_only_count") or 0)
    support_generated_at = str(
        support_packets.get("generated_at") or support_packets.get("generatedAt") or ""
    ).strip()
    release_generated_at = str(
        release_channel.get("generatedAt") or release_channel.get("generated_at") or ""
    ).strip()
    support_plan_release_generated_at = str(
        support_plan.get("release_channel_generated_at") or support_plan.get("releaseChannelGeneratedAt") or ""
    ).strip()
    journey_support_generated_ats = sorted(
        {
            str((row.get("evidence") or {}).get("support_packets_generated_at") or "").strip()
            for row in journey_rows
            if str((row.get("evidence") or {}).get("support_packets_generated_at") or "").strip()
        }
    )
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
    if not release_generated_at:
        failures.append(
            "release channel generatedAt/generated_at is missing (cannot prove closure freshness)"
        )
    if not support_generated_at:
        failures.append(
            "support packets generated_at/generatedAt is missing (cannot prove closure freshness)"
        )
    if not support_plan_release_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.release_channel_generated_at is missing"
        )
    if support_plan_release_generated_at and release_generated_at and support_plan_release_generated_at != release_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.release_channel_generated_at "
            f"({support_plan_release_generated_at}) does not match release channel generatedAt ({release_generated_at})"
        )
    if journey_support_generated_ats and support_generated_at and journey_support_generated_ats != [support_generated_at]:
        failures.append(
            "journey gates evidence.support_packets_generated_at values do not match support packets generated_at: "
            + ", ".join(journey_support_generated_ats)
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
