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

    failures: list[str] = []
    raw_support_summary = support_packets.get("summary")
    raw_journey_summary = journey_gates.get("summary")
    raw_tuple_coverage = release_channel.get("desktopTupleCoverage")
    if not isinstance(raw_support_summary, dict):
        failures.append("support packets summary is missing or not an object")
    if not isinstance(raw_journey_summary, dict):
        failures.append("journey gates summary is missing or not an object")
    if not isinstance(raw_tuple_coverage, dict):
        failures.append("release channel desktopTupleCoverage is missing or not an object")

    support_summary = dict(raw_support_summary or {})
    journey_summary = dict(raw_journey_summary or {})
    tuple_coverage = dict(raw_tuple_coverage or {})
    support_plan = dict(support_packets.get("unresolved_external_proof_execution_plan") or {})
    if not isinstance(support_packets.get("unresolved_external_proof_execution_plan"), dict):
        failures.append("support packets unresolved_external_proof_execution_plan is missing or not an object")

    missing_platforms_raw = tuple_coverage.get("missingRequiredPlatforms")
    missing_head_pairs_raw = tuple_coverage.get("missingRequiredPlatformHeadPairs")
    missing_tuples_raw = tuple_coverage.get("missingRequiredPlatformHeadRidTuples")
    if "missingRequiredPlatforms" not in tuple_coverage:
        failures.append("release channel desktopTupleCoverage.missingRequiredPlatforms is missing")
    elif not isinstance(missing_platforms_raw, list):
        failures.append("release channel desktopTupleCoverage.missingRequiredPlatforms is not an array")
    if "missingRequiredPlatformHeadPairs" not in tuple_coverage:
        failures.append("release channel desktopTupleCoverage.missingRequiredPlatformHeadPairs is missing")
    elif not isinstance(missing_head_pairs_raw, list):
        failures.append(
            "release channel desktopTupleCoverage.missingRequiredPlatformHeadPairs is not an array"
        )
    if "missingRequiredPlatformHeadRidTuples" not in tuple_coverage:
        failures.append(
            "release channel desktopTupleCoverage.missingRequiredPlatformHeadRidTuples is missing"
        )
    elif not isinstance(missing_tuples_raw, list):
        failures.append(
            "release channel desktopTupleCoverage.missingRequiredPlatformHeadRidTuples is not an array"
        )

    support_summary_key_types = {
        "unresolved_external_proof_request_count": (int, float, str),
        "unresolved_external_proof_request_hosts": list,
        "unresolved_external_proof_request_tuples": list,
        "unresolved_external_proof_request_host_counts": dict,
        "unresolved_external_proof_request_tuple_counts": dict,
    }
    for key, expected in support_summary_key_types.items():
        if key not in support_summary:
            failures.append(f"support packets summary.{key} is missing")
            continue
        if not isinstance(support_summary.get(key), expected):
            failures.append(f"support packets summary.{key} has invalid type")
    if "unresolved_external_proof_request_specs" not in support_summary:
        failures.append("support packets summary.unresolved_external_proof_request_specs is missing")
    elif not isinstance(support_summary.get("unresolved_external_proof_request_specs"), (dict, list)):
        failures.append("support packets summary.unresolved_external_proof_request_specs has invalid type")

    journey_summary_key_types = {
        "blocked_external_only_count": (int, float, str),
        "blocked_external_only_hosts": list,
        "blocked_external_only_tuples": list,
        "blocked_external_only_host_counts": dict,
    }
    for key, expected in journey_summary_key_types.items():
        if key not in journey_summary:
            failures.append(f"journey gates summary.{key} is missing")
            continue
        if not isinstance(journey_summary.get(key), expected):
            failures.append(f"journey gates summary.{key} has invalid type")

    support_plan_key_types = {
        "request_count": (int, float, str),
        "hosts": list,
        "host_groups": dict,
    }
    for key, expected in support_plan_key_types.items():
        if key not in support_plan:
            failures.append(f"support packets unresolved_external_proof_execution_plan.{key} is missing")
            continue
        if not isinstance(support_plan.get(key), expected):
            failures.append(
                f"support packets unresolved_external_proof_execution_plan.{key} has invalid type"
            )

    journey_rows = [
        dict(item)
        for item in (journey_gates.get("journeys") or [])
        if isinstance(item, dict)
    ]

    unresolved_count = int(support_summary.get("unresolved_external_proof_request_count") or 0)
    blocked_external_only_count = int(journey_summary.get("blocked_external_only_count") or 0)
    support_plan_request_count = int(support_plan.get("request_count") or 0)
    support_host_count_map = dict(support_summary.get("unresolved_external_proof_request_host_counts") or {})
    support_tuple_count_map = dict(support_summary.get("unresolved_external_proof_request_tuple_counts") or {})
    journey_host_count_map = dict(journey_summary.get("blocked_external_only_host_counts") or {})
    support_plan_hosts = sorted(
        {
            str(item).strip()
            for item in (support_plan.get("hosts") or [])
            if str(item).strip()
        }
    )
    support_plan_host_groups = dict(support_plan.get("host_groups") or {})
    support_plan_hosts_with_backlog = sorted(
        {
            str(raw_host).strip()
            for raw_host, raw_group in support_plan_host_groups.items()
            if str(raw_host).strip()
            and isinstance(raw_group, dict)
            and (
                int(raw_group.get("request_count") or 0) > 0
                or any(str(item).strip() for item in (raw_group.get("tuples") or []))
                or any(isinstance(item, dict) for item in (raw_group.get("requests") or []))
            )
        }
    )
    support_generated_at = str(
        support_packets.get("generated_at") or support_packets.get("generatedAt") or ""
    ).strip()
    support_plan_generated_at = str(
        support_plan.get("generated_at") or support_plan.get("generatedAt") or ""
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
    missing_platforms = [
        str(item).strip()
        for item in (missing_platforms_raw or [])
        if str(item).strip()
    ]
    missing_head_pairs = [
        str(item).strip()
        for item in (missing_head_pairs_raw or [])
        if str(item).strip()
    ]
    missing_tuples = [
        str(item).strip()
        for item in (missing_tuples_raw or [])
        if str(item).strip()
    ]
    unresolved_tuples = [
        str(item).strip()
        for item in (support_summary.get("unresolved_external_proof_request_tuples") or [])
        if str(item).strip()
    ]
    unresolved_hosts = [
        str(item).strip()
        for item in (support_summary.get("unresolved_external_proof_request_hosts") or [])
        if str(item).strip()
    ]
    unresolved_specs_raw = support_summary.get("unresolved_external_proof_request_specs")
    unresolved_specs = sorted(
        {
            str(item).strip()
            for item in (
                unresolved_specs_raw.keys()
                if isinstance(unresolved_specs_raw, dict)
                else (unresolved_specs_raw or [])
            )
            if str(item).strip()
        }
    )
    unresolved_backlog_raw = support_packets.get("unresolved_external_proof")
    unresolved_entries: list[dict[str, Any]] = []
    unresolved_backlog_count = 0
    unresolved_backlog_hosts: list[str] = []
    unresolved_backlog_tuples: list[str] = []
    unresolved_backlog_host_counts: dict[str, Any] = {}
    unresolved_backlog_tuple_counts: dict[str, Any] = {}
    unresolved_backlog_specs: dict[str, Any] = {}
    if isinstance(unresolved_backlog_raw, list):
        unresolved_entries = [dict(item) for item in unresolved_backlog_raw if isinstance(item, dict)]
        unresolved_backlog_count = len(unresolved_entries)
        unresolved_backlog_hosts = sorted(
            {
                str(item.get("required_host") or item.get("host") or "").strip()
                for item in unresolved_entries
                if str(item.get("required_host") or item.get("host") or "").strip()
            }
        )
        unresolved_backlog_tuples = sorted(
            {
                str(item.get("tuple_id") or item.get("tupleId") or "").strip()
                for item in unresolved_entries
                if str(item.get("tuple_id") or item.get("tupleId") or "").strip()
            }
        )
    elif isinstance(unresolved_backlog_raw, dict):
        unresolved_backlog_count = int(unresolved_backlog_raw.get("count") or 0)
        unresolved_backlog_hosts = sorted(
            {
                str(item).strip()
                for item in (unresolved_backlog_raw.get("hosts") or [])
                if str(item).strip()
            }
        )
        unresolved_backlog_tuples = sorted(
            {
                str(item).strip()
                for item in (unresolved_backlog_raw.get("tuples") or [])
                if str(item).strip()
            }
        )
        unresolved_backlog_host_counts = dict(unresolved_backlog_raw.get("host_counts") or {})
        unresolved_backlog_tuple_counts = dict(unresolved_backlog_raw.get("tuple_counts") or {})
        unresolved_backlog_specs = dict(unresolved_backlog_raw.get("specs") or {})
    elif unresolved_backlog_raw is not None:
        failures.append("support packets unresolved_external_proof has invalid type (expected array or object)")
    blocked_external_only_tuples = [
        str(item).strip()
        for item in (journey_summary.get("blocked_external_only_tuples") or [])
        if str(item).strip()
    ]
    blocked_external_only_hosts = [
        str(item).strip()
        for item in (journey_summary.get("blocked_external_only_hosts") or [])
        if str(item).strip()
    ]
    journey_rows_with_external_requests = sorted(
        {
            str(row.get("id") or "").strip() or "<unknown>"
            for row in journey_rows
            if isinstance(row.get("external_proof_requests"), list) and row.get("external_proof_requests")
        }
    )
    journey_rows_with_malformed_external_requests = sorted(
        {
            str(row.get("id") or "").strip() or "<unknown>"
            for row in journey_rows
            if (
                "external_proof_requests" in row
                and not isinstance(row.get("external_proof_requests"), list)
                and row.get("external_proof_requests") not in (None, "")
            )
        }
    )

    if unresolved_count > 0:
        failures.append(
            f"support packets unresolved_external_proof_request_count={unresolved_count} (expected 0)"
        )
    if support_plan_request_count > 0:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.request_count="
            f"{support_plan_request_count} (expected 0)"
        )
    if blocked_external_only_count > 0:
        failures.append(
            f"journey gates blocked_external_only_count={blocked_external_only_count} (expected 0)"
        )
    if support_host_count_map:
        failures.append(
            "support packets unresolved_external_proof_request_host_counts is not empty: "
            + ", ".join(f"{host}:{count}" for host, count in sorted(support_host_count_map.items()))
        )
    if support_tuple_count_map:
        failures.append(
            "support packets unresolved_external_proof_request_tuple_counts is not empty: "
            + ", ".join(f"{tuple_id}:{count}" for tuple_id, count in sorted(support_tuple_count_map.items()))
        )
    if journey_host_count_map:
        failures.append(
            "journey gates blocked_external_only_host_counts is not empty: "
            + ", ".join(f"{host}:{count}" for host, count in sorted(journey_host_count_map.items()))
        )
    if support_plan_hosts:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.hosts is not empty: "
            + ", ".join(support_plan_hosts)
        )
    if support_plan_hosts_with_backlog:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.host_groups still contain backlog: "
            + ", ".join(support_plan_hosts_with_backlog)
        )
    if missing_platforms:
        failures.append(
            "release channel missingRequiredPlatforms is not empty: "
            + ", ".join(missing_platforms)
        )
    if missing_head_pairs:
        failures.append(
            "release channel missingRequiredPlatformHeadPairs is not empty: "
            + ", ".join(missing_head_pairs)
        )
    if missing_tuples:
        failures.append(
            "release channel missingRequiredPlatformHeadRidTuples is not empty: "
            + ", ".join(missing_tuples)
        )
    if unresolved_tuples:
        failures.append(
            "support packets unresolved_external_proof_request_tuples is not empty: "
            + ", ".join(unresolved_tuples)
        )
    if unresolved_hosts:
        failures.append(
            "support packets unresolved_external_proof_request_hosts is not empty: "
            + ", ".join(unresolved_hosts)
        )
    if unresolved_specs:
        failures.append(
            "support packets unresolved_external_proof_request_specs is not empty: "
            + ", ".join(unresolved_specs)
        )
    if unresolved_backlog_count > 0:
        failures.append(
            "support packets unresolved_external_proof.count="
            f"{unresolved_backlog_count} (expected 0)"
        )
    if unresolved_backlog_hosts:
        failures.append(
            "support packets unresolved_external_proof.hosts is not empty: "
            + ", ".join(unresolved_backlog_hosts)
        )
    if unresolved_backlog_tuples:
        failures.append(
            "support packets unresolved_external_proof.tuples is not empty: "
            + ", ".join(unresolved_backlog_tuples)
        )
    if unresolved_backlog_host_counts:
        failures.append(
            "support packets unresolved_external_proof.host_counts is not empty: "
            + ", ".join(f"{host}:{count}" for host, count in sorted(unresolved_backlog_host_counts.items()))
        )
    if unresolved_backlog_tuple_counts:
        failures.append(
            "support packets unresolved_external_proof.tuple_counts is not empty: "
            + ", ".join(f"{tuple_id}:{count}" for tuple_id, count in sorted(unresolved_backlog_tuple_counts.items()))
        )
    if unresolved_backlog_specs:
        failures.append(
            "support packets unresolved_external_proof.specs is not empty: "
            + ", ".join(sorted(unresolved_backlog_specs.keys()))
        )
    if unresolved_entries:
        failures.append(
            "support packets unresolved_external_proof still contains unresolved entries: "
            + ", ".join(sorted({str(item.get("tuple_id") or item.get("tupleId") or "").strip() or "<unknown>" for item in unresolved_entries}))
        )
    if blocked_external_only_tuples:
        failures.append(
            "journey gates blocked_external_only_tuples is not empty: "
            + ", ".join(blocked_external_only_tuples)
        )
    if blocked_external_only_hosts:
        failures.append(
            "journey gates blocked_external_only_hosts is not empty: "
            + ", ".join(blocked_external_only_hosts)
        )
    if journey_rows_with_external_requests:
        failures.append(
            "journey gates still report external_proof_requests in journey rows: "
            + ", ".join(journey_rows_with_external_requests)
        )
    if journey_rows_with_malformed_external_requests:
        failures.append(
            "journey gates have malformed external_proof_requests payload in journey rows: "
            + ", ".join(journey_rows_with_malformed_external_requests)
        )
    if missing_tuples and unresolved_tuples and sorted(set(missing_tuples)) != sorted(set(unresolved_tuples)):
        failures.append(
            "support packets unresolved_external_proof_request_tuples does not match release channel missingRequiredPlatformHeadRidTuples"
        )
    if missing_tuples and blocked_external_only_tuples and sorted(set(missing_tuples)) != sorted(set(blocked_external_only_tuples)):
        failures.append(
            "journey gates blocked_external_only_tuples does not match release channel missingRequiredPlatformHeadRidTuples"
        )
    if not release_generated_at:
        failures.append(
            "release channel generatedAt/generated_at is missing (cannot prove closure freshness)"
        )
    if not support_generated_at:
        failures.append(
            "support packets generated_at/generatedAt is missing (cannot prove closure freshness)"
        )
    if not support_plan_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.generated_at/generatedAt is missing"
        )
    if support_plan_generated_at and support_generated_at and support_plan_generated_at != support_generated_at:
        failures.append(
            "support packets unresolved_external_proof_execution_plan.generated_at "
            f"({support_plan_generated_at}) does not match support packets generated_at ({support_generated_at})"
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
