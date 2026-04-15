#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

try:
    from scripts.materialize_support_case_packets import (
        NEXT_90_QUEUE_STAGING_PATH,
        SUCCESSOR_FRONTIER_ID,
        SUCCESSOR_MILESTONE_ID,
        SUCCESSOR_PACKAGE_ID,
        SUCCESSOR_REGISTRY_PATH,
        _find_successor_queue_item,
        _normalize_list,
        _normalize_text,
        _successor_package_verification,
    )
except ModuleNotFoundError:
    from materialize_support_case_packets import (
        NEXT_90_QUEUE_STAGING_PATH,
        SUCCESSOR_FRONTIER_ID,
        SUCCESSOR_MILESTONE_ID,
        SUCCESSOR_PACKAGE_ID,
        SUCCESSOR_REGISTRY_PATH,
        _find_successor_queue_item,
        _normalize_list,
        _normalize_text,
        _successor_package_verification,
    )


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
DEFAULT_SUPPORT_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
DEFAULT_WEEKLY_GOVERNOR_PACKET = PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"
DEFAULT_WEEKLY_GOVERNOR_MARKDOWN = PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.md"
VERIFIER_PROOF_MARKER = "/docker/fleet/scripts/verify_next90_m102_fleet_reporter_receipts.py"
TEST_PROOF_MARKER = "/docker/fleet/tests/test_verify_next90_m102_fleet_reporter_receipts.py"
UTC = dt.timezone.utc
REQUIRED_GATE_NAMES = {
    "install_truth_ready",
    "release_receipt_ready",
    "fixed_version_receipted",
    "fixed_channel_receipted",
    "installed_build_receipt_id_present",
    "installed_build_receipt_installation_bound",
    "installed_build_receipt_version_matches",
    "installed_build_receipt_channel_matches",
}
REQUIRED_GATE_COUNT_NAMES = REQUIRED_GATE_NAMES | {
    "install_receipt_ready",
    "installed_build_receipted",
    "current_install_on_fixed_build",
}
REQUIRED_ACTION_GROUPS = {
    "fix_available",
    "please_test",
    "recovery",
    "blocked_missing_install_receipts",
    "blocked_receipt_mismatch",
    "hold_until_fix_receipt",
}
REQUIRED_WEEKLY_SUPPORT_KEYS = {
    "followthrough_receipt_gates_ready_count",
    "followthrough_receipt_gates_blocked_missing_install_receipts_count",
    "followthrough_receipt_gates_blocked_receipt_mismatch_count",
    "followthrough_receipt_gates_installation_bound_count",
    "followthrough_receipt_gates_installed_build_receipted_count",
    "reporter_followthrough_plan_ready_count",
    "reporter_followthrough_plan_blocked_missing_install_receipts_count",
    "reporter_followthrough_plan_blocked_receipt_mismatch_count",
}
REQUIRED_SUPPORT_VERIFICATION_EMPTY_LIST_KEYS = {
    "missing_registry_evidence_markers",
    "missing_queue_proof_markers",
    "missing_registry_proof_anchor_paths",
    "missing_queue_proof_anchor_paths",
    "disallowed_registry_evidence_entries",
    "disallowed_queue_proof_entries",
}
REQUIRED_SUPPORT_VERIFICATION_MATCH_KEYS = {
    "allowed_paths",
    "owned_surfaces",
    "required_queue_proof_markers",
    "required_registry_evidence_markers",
    "registry_work_task_status",
    "queue_status",
    "queue_frontier_id",
    "design_queue_source_path",
    "design_queue_source_item_found",
    "design_queue_source_status",
    "design_queue_source_frontier_id",
}
REQUIRED_RULE_MARKERS = (
    "install truth",
    "installation-bound installed-build receipts",
    "fixed-version receipts",
    "fixed-channel receipts",
    "release-channel receipts",
)
DISALLOWED_WORKER_PROOF_MARKERS = (
    "/var/lib/codex-fleet",
    "ACTIVE_RUN_HANDOFF.generated.md",
    "TASK_LOCAL_TELEMETRY.generated.json",
    "run_ooda_design_supervisor_until_quiet",
    "ooda_design_supervisor.py",
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the closed next90-m102 Fleet reporter receipt package without "
            "refreshing support packets or invoking active-run telemetry helpers."
        )
    )
    parser.add_argument("--support-packets", default=str(DEFAULT_SUPPORT_PACKETS))
    parser.add_argument("--weekly-governor-packet", default=str(DEFAULT_WEEKLY_GOVERNOR_PACKET))
    parser.add_argument("--weekly-governor-markdown", default=str(DEFAULT_WEEKLY_GOVERNOR_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY_PATH))
    parser.add_argument("--queue-staging", default=str(NEXT_90_QUEUE_STAGING_PATH))
    parser.add_argument("--json", action="store_true", help="emit machine-readable verification output")
    return parser.parse_args(argv)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _contains_all_markers(text: str, markers: Iterable[str]) -> List[str]:
    lower = text.lower()
    return [marker for marker in markers if marker.lower() not in lower]


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _markdown_label_values(markdown: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        clean_key = key.strip()
        if clean_key:
            values[clean_key] = value.strip()
    return values


def _markdown_generated_at(markdown: str) -> str:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("Generated:"):
            return line.split(":", 1)[1].strip()
    return ""


def _parse_iso_utc(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _queue_proof_entries(queue_path: Path) -> List[str]:
    queue = _read_yaml(queue_path)
    item = _find_successor_queue_item(queue)
    return _normalize_list(item.get("proof")) if item else []


def _registry_evidence_entries(registry_path: Path) -> List[str]:
    registry = _read_yaml(registry_path)
    milestone = next(
        (
            row
            for row in (registry.get("milestones") or [])
            if isinstance(row, dict) and row.get("id") == SUCCESSOR_MILESTONE_ID
        ),
        {},
    )
    work_task = next(
        (
            row
            for row in (milestone.get("work_tasks") or [])
            if isinstance(row, dict) and _normalize_text(row.get("id")) == "102.4"
        ),
        {},
    )
    return _normalize_list(work_task.get("evidence")) if work_task else []


def _disallowed_proof_entries(entries: Iterable[str]) -> List[str]:
    blocked: List[str] = []
    for entry in entries:
        entry_lower = entry.lower()
        for marker in DISALLOWED_WORKER_PROOF_MARKERS:
            if marker.lower() in entry_lower:
                blocked.append(entry)
                break
    return blocked


def verify(
    *,
    support_packets_path: Path,
    weekly_governor_packet_path: Path,
    weekly_governor_markdown_path: Path,
    successor_registry_path: Path,
    queue_staging_path: Path,
) -> Dict[str, Any]:
    issues: List[str] = []
    support_packets = _read_json(support_packets_path)
    weekly = _read_json(weekly_governor_packet_path)
    weekly_markdown = _read_text(weekly_governor_markdown_path)
    successor = _successor_package_verification(successor_registry_path, queue_staging_path)
    registry_evidence = _registry_evidence_entries(successor_registry_path)
    queue_proof = _queue_proof_entries(queue_staging_path)

    if successor.get("status") != "pass":
        issues.append("successor package authority is not pass")
    if successor.get("package_id") != SUCCESSOR_PACKAGE_ID:
        issues.append("successor package id drifted")
    if _normalize_text(successor.get("frontier_id")) != SUCCESSOR_FRONTIER_ID:
        issues.append("successor frontier id drifted")
    if successor.get("milestone_id") != SUCCESSOR_MILESTONE_ID:
        issues.append("successor milestone id drifted")
    for key in ("missing_registry_evidence_markers", "missing_queue_proof_markers", "missing_registry_proof_anchor_paths", "missing_queue_proof_anchor_paths"):
        if successor.get(key):
            issues.append(f"successor authority reports {key}")

    if VERIFIER_PROOF_MARKER not in "\n".join(queue_proof):
        issues.append("successor queue proof does not name the standalone M102 verifier")
    if TEST_PROOF_MARKER not in "\n".join(queue_proof):
        issues.append("successor queue proof does not name the standalone M102 verifier tests")
    blocked_registry_evidence_entries = _disallowed_proof_entries(registry_evidence)
    blocked_queue_proof_entries = _disallowed_proof_entries(queue_proof)
    blocked_proof_entries = blocked_registry_evidence_entries + blocked_queue_proof_entries
    if blocked_registry_evidence_entries:
        issues.append("successor registry evidence cites active-run telemetry or helper commands")
    if blocked_queue_proof_entries:
        issues.append("successor queue proof cites active-run telemetry or helper commands")

    receipt_gates = support_packets.get("followthrough_receipt_gates")
    if not isinstance(receipt_gates, dict):
        issues.append("SUPPORT_CASE_PACKETS.generated.json is missing followthrough_receipt_gates")
        receipt_gates = {}
    plan = support_packets.get("reporter_followthrough_plan")
    if not isinstance(plan, dict):
        issues.append("SUPPORT_CASE_PACKETS.generated.json is missing reporter_followthrough_plan")
        plan = {}
    support_verification = support_packets.get("successor_package_verification")
    if not isinstance(support_verification, dict) or support_verification.get("status") != "pass":
        issues.append("SUPPORT_CASE_PACKETS.generated.json successor_package_verification is not pass")
        support_verification = {}
    if _normalize_text(support_verification.get("package_id")) != SUCCESSOR_PACKAGE_ID:
        issues.append("SUPPORT_CASE_PACKETS.generated.json successor package id drifted")
    if _normalize_text(support_verification.get("frontier_id")) != SUCCESSOR_FRONTIER_ID:
        issues.append("SUPPORT_CASE_PACKETS.generated.json successor frontier id drifted")
    if support_verification.get("milestone_id") != SUCCESSOR_MILESTONE_ID:
        issues.append("SUPPORT_CASE_PACKETS.generated.json successor milestone id drifted")
    support_verification_nonempty_lists = {
        key: _normalize_list(support_verification.get(key))
        for key in REQUIRED_SUPPORT_VERIFICATION_EMPTY_LIST_KEYS
        if _normalize_list(support_verification.get(key))
    }
    if support_verification_nonempty_lists:
        issues.append("SUPPORT_CASE_PACKETS.generated.json successor verification carries stale proof gaps")
    support_blocked_proof_entries = (
        support_verification_nonempty_lists.get("disallowed_registry_evidence_entries", [])
        + support_verification_nonempty_lists.get("disallowed_queue_proof_entries", [])
    )
    if support_blocked_proof_entries:
        issues.append("SUPPORT_CASE_PACKETS.generated.json exposes active-run telemetry or helper proof entries")
    support_verification_field_mismatches = {
        key: {
            "support_packets": support_verification.get(key),
            "computed_successor_authority": successor.get(key),
        }
        for key in sorted(REQUIRED_SUPPORT_VERIFICATION_MATCH_KEYS)
        if support_verification.get(key) != successor.get(key)
    }
    if support_verification_field_mismatches:
        issues.append("SUPPORT_CASE_PACKETS.generated.json successor verification closure fields drifted")
    if _normalize_text(receipt_gates.get("package_id")) != SUCCESSOR_PACKAGE_ID:
        issues.append("followthrough_receipt_gates package id drifted")
    if _normalize_text(plan.get("package_id")) != SUCCESSOR_PACKAGE_ID:
        issues.append("reporter_followthrough_plan package id drifted")

    required_gates = set(_normalize_list(receipt_gates.get("required_gates")))
    missing_gate_names = sorted(REQUIRED_GATE_NAMES - required_gates)
    if missing_gate_names:
        issues.append("followthrough receipt gates are missing required gate names")
    gate_counts = receipt_gates.get("gate_counts") if isinstance(receipt_gates.get("gate_counts"), dict) else {}
    missing_gate_counts = sorted(REQUIRED_GATE_COUNT_NAMES - set(gate_counts.keys()))
    if missing_gate_counts:
        issues.append("followthrough receipt gates are missing required gate counters")
    gate_rule_missing = _contains_all_markers(_normalize_text(receipt_gates.get("source_rule")), REQUIRED_RULE_MARKERS)
    if gate_rule_missing:
        issues.append("followthrough receipt gate rule is missing receipt markers")

    action_groups = plan.get("action_groups") if isinstance(plan.get("action_groups"), dict) else {}
    missing_action_groups = sorted(REQUIRED_ACTION_GROUPS - set(action_groups.keys()))
    if missing_action_groups:
        issues.append("reporter followthrough plan is missing action groups")
    plan_rule_missing = _contains_all_markers(_normalize_text(plan.get("source_rule")), REQUIRED_RULE_MARKERS)
    if plan_rule_missing:
        issues.append("reporter followthrough plan rule is missing receipt markers")

    weekly_sources = weekly.get("source_input_health")
    if not isinstance(weekly_sources, dict):
        weekly_sources = weekly.get("input_health")
    support_input = {}
    if isinstance(weekly_sources, dict):
        required_inputs = (
            weekly_sources.get("required_inputs")
            if isinstance(weekly_sources.get("required_inputs"), dict)
            else {}
        )
        if isinstance(required_inputs.get("support_packets"), dict):
            support_input = required_inputs.get("support_packets") or {}
        elif isinstance(weekly_sources.get("support_packets"), dict):
            support_input = weekly_sources.get("support_packets") or {}
    if not support_input:
        issues.append("weekly governor support-packets input is missing")
    elif support_input.get("successor_package_verification_status") != "pass":
        issues.append("weekly governor support-packets input does not report successor verification pass")
    support_generated_at = _parse_iso_utc(support_packets.get("generated_at"))
    weekly_generated_at = _parse_iso_utc(weekly.get("generated_at"))
    if not support_generated_at:
        issues.append("SUPPORT_CASE_PACKETS.generated.json generated_at is missing or invalid")
    if not weekly_generated_at:
        issues.append("WEEKLY_GOVERNOR_PACKET.generated.json generated_at is missing or invalid")
    if support_generated_at and weekly_generated_at and weekly_generated_at < support_generated_at:
        issues.append("weekly governor packet predates support-packet receipt gates")
    truth_inputs = weekly.get("truth_inputs") if isinstance(weekly.get("truth_inputs"), dict) else {}
    support_summary = truth_inputs.get("support_summary") if isinstance(truth_inputs.get("support_summary"), dict) else {}
    missing_weekly_keys = sorted(REQUIRED_WEEKLY_SUPPORT_KEYS - set(support_summary.keys()))
    if missing_weekly_keys:
        issues.append("weekly governor support summary is missing receipt-gated followthrough keys")
    expected_weekly_counts = {
        "followthrough_receipt_gates_ready_count": _as_int(receipt_gates.get("ready_count")),
        "followthrough_receipt_gates_blocked_missing_install_receipts_count": _as_int(
            receipt_gates.get("blocked_missing_install_receipts_count")
        ),
        "followthrough_receipt_gates_blocked_receipt_mismatch_count": _as_int(
            receipt_gates.get("blocked_receipt_mismatch_count")
        ),
        "followthrough_receipt_gates_installation_bound_count": _as_int(
            gate_counts.get("installed_build_receipt_installation_bound")
        ),
        "followthrough_receipt_gates_installed_build_receipted_count": _as_int(
            gate_counts.get("installed_build_receipted")
        ),
        "reporter_followthrough_plan_ready_count": _as_int(plan.get("ready_count")),
        "reporter_followthrough_plan_blocked_missing_install_receipts_count": _as_int(
            plan.get("blocked_missing_install_receipts_count")
        ),
        "reporter_followthrough_plan_blocked_receipt_mismatch_count": _as_int(
            plan.get("blocked_receipt_mismatch_count")
        ),
    }
    weekly_count_mismatches = {
        key: {
            "support_packets": expected,
            "weekly_governor_packet": _as_int(support_summary.get(key)),
        }
        for key, expected in expected_weekly_counts.items()
        if key in support_summary and _as_int(support_summary.get(key)) != expected
    }
    if weekly_count_mismatches:
        issues.append("weekly governor support summary disagrees with support-packet receipt gates")

    markdown_values = _markdown_label_values(weekly_markdown)
    markdown_generated_at = _markdown_generated_at(weekly_markdown)
    if not weekly_markdown:
        issues.append("WEEKLY_GOVERNOR_PACKET.generated.md is missing or unreadable")
    elif markdown_generated_at != _normalize_text(weekly.get("generated_at")):
        issues.append("weekly governor markdown generated timestamp disagrees with JSON packet")
    expected_markdown_counts = {
        "Reporter followthrough ready": _as_int(plan.get("ready_count")),
        "Fix-available ready": len(action_groups.get("fix_available") or []),
        "Please-test ready": len(action_groups.get("please_test") or []),
        "Recovery-loop ready": len(action_groups.get("recovery") or []),
        "Followthrough blocked on install receipts": _as_int(
            receipt_gates.get("blocked_missing_install_receipts_count")
        ),
        "Followthrough receipt mismatches": _as_int(receipt_gates.get("blocked_receipt_mismatch_count")),
        "Receipt-gated followthrough ready": _as_int(receipt_gates.get("ready_count")),
        "Receipt-gated installed-build receipts": _as_int(gate_counts.get("installed_build_receipted")),
    }
    missing_markdown_labels = sorted(
        label for label in expected_markdown_counts if label not in markdown_values
    )
    if missing_markdown_labels:
        issues.append("weekly governor markdown is missing receipt-gated followthrough labels")
    weekly_markdown_count_mismatches = {
        label: {
            "support_packets": expected,
            "weekly_governor_markdown": _as_int(markdown_values.get(label)),
        }
        for label, expected in expected_markdown_counts.items()
        if label in markdown_values and _as_int(markdown_values.get(label)) != expected
    }
    if weekly_markdown_count_mismatches:
        issues.append("weekly governor markdown disagrees with support-packet receipt gates")

    return {
        "status": "pass" if not issues else "fail",
        "package_id": SUCCESSOR_PACKAGE_ID,
        "frontier_id": SUCCESSOR_FRONTIER_ID,
        "milestone_id": SUCCESSOR_MILESTONE_ID,
        "support_packets_path": str(support_packets_path),
        "weekly_governor_packet_path": str(weekly_governor_packet_path),
        "weekly_governor_markdown_path": str(weekly_governor_markdown_path),
        "successor_registry_path": str(successor_registry_path),
        "queue_staging_path": str(queue_staging_path),
        "successor_authority_status": successor.get("status", ""),
        "queue_proof_entry_count": len(queue_proof),
        "blocked_proof_entries": blocked_proof_entries,
        "blocked_registry_evidence_entries": blocked_registry_evidence_entries,
        "blocked_queue_proof_entries": blocked_queue_proof_entries,
        "support_packet_blocked_proof_entries": support_blocked_proof_entries,
        "support_packet_stale_proof_gaps": support_verification_nonempty_lists,
        "support_packet_successor_field_mismatches": support_verification_field_mismatches,
        "missing_gate_names": missing_gate_names,
        "missing_gate_counts": missing_gate_counts,
        "missing_action_groups": missing_action_groups,
        "missing_weekly_support_keys": missing_weekly_keys,
        "weekly_count_mismatches": weekly_count_mismatches,
        "missing_weekly_markdown_labels": missing_markdown_labels,
        "weekly_markdown_count_mismatches": weekly_markdown_count_mismatches,
        "support_packets_generated_at": _normalize_text(support_packets.get("generated_at")),
        "weekly_governor_packet_generated_at": _normalize_text(weekly.get("generated_at")),
        "weekly_governor_markdown_generated_at": markdown_generated_at,
        "issues": issues,
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    result = verify(
        support_packets_path=Path(args.support_packets),
        weekly_governor_packet_path=Path(args.weekly_governor_packet),
        weekly_governor_markdown_path=Path(args.weekly_governor_markdown),
        successor_registry_path=Path(args.successor_registry),
        queue_staging_path=Path(args.queue_staging),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["status"] == "pass":
        print(f"{SUCCESSOR_PACKAGE_ID}: pass")
    else:
        for issue in result["issues"]:
            print(f"FAIL: {issue}", file=sys.stderr)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
