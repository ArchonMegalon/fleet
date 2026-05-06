#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

try:
    from scripts.next90_queue_staging import read_next90_queue_staging_yaml
except ModuleNotFoundError:
    from next90_queue_staging import read_next90_queue_staging_yaml

try:
    from scripts.materialize_support_case_packets import (
        NEXT_90_QUEUE_STAGING_PATH,
        SUCCESSOR_FRONTIER_ID,
        SUCCESSOR_MILESTONE_ID,
        SUCCESSOR_PACKAGE_ID,
        SUCCESSOR_REGISTRY_PATH,
        SUCCESSOR_DISALLOWED_PROOF_MARKERS,
        _find_successor_queue_item,
        _followthrough_packet_row,
        _followthrough_row_gate_evidence,
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
        SUCCESSOR_DISALLOWED_PROOF_MARKERS,
        _find_successor_queue_item,
        _followthrough_packet_row,
        _followthrough_row_gate_evidence,
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
    "feedback_loop_ready",
    "install_truth_ready",
    "release_receipt_ready",
    "release_receipt_id_present",
    "fixed_version_receipted",
    "fixed_channel_receipted",
    "fixed_receipt_installation_bound",
    "installed_build_receipt_id_present",
    "installed_build_receipt_installation_bound",
    "installed_build_receipt_version_matches",
    "installed_build_receipt_channel_matches",
    "installed_build_receipt_tuple_bound",
}
REQUIRED_GATE_COUNT_NAMES = REQUIRED_GATE_NAMES | {
    "install_receipt_ready",
    "installed_build_receipted",
    "current_install_on_fixed_build",
}
REQUIRED_ACTION_GROUPS = {
    "feedback",
    "fix_available",
    "please_test",
    "recovery",
    "blocked_missing_install_receipts",
    "blocked_receipt_mismatch",
    "hold_until_fix_receipt",
}
REQUIRED_WEEKLY_SUPPORT_KEYS = {
    "reporter_followthrough_ready_count",
    "feedback_followthrough_ready_count",
    "fix_available_ready_count",
    "please_test_ready_count",
    "recovery_loop_ready_count",
    "reporter_followthrough_blocked_missing_install_receipts_count",
    "reporter_followthrough_blocked_receipt_mismatch_count",
    "reporter_followthrough_hold_until_fix_receipt_count",
    "followthrough_receipt_gates_ready_count",
    "followthrough_receipt_gates_blocked_missing_install_receipts_count",
    "followthrough_receipt_gates_blocked_receipt_mismatch_count",
    "followthrough_receipt_gates_hold_until_fix_receipt_count",
    "followthrough_receipt_gates_installation_bound_count",
    "followthrough_receipt_gates_installed_build_receipted_count",
    "feedback_followthrough_ready_count",
    "reporter_followthrough_plan_ready_count",
    "reporter_followthrough_plan_blocked_missing_install_receipts_count",
    "reporter_followthrough_plan_blocked_receipt_mismatch_count",
    "reporter_followthrough_plan_hold_until_fix_receipt_count",
}
REQUIRED_SUPPORT_SUMMARY_KEYS = {
    "reporter_followthrough_ready_count",
    "feedback_followthrough_ready_count",
    "fix_available_ready_count",
    "please_test_ready_count",
    "recovery_loop_ready_count",
    "reporter_followthrough_blocked_missing_install_receipts_count",
    "reporter_followthrough_blocked_receipt_mismatch_count",
    "reporter_followthrough_hold_until_fix_receipt_count",
}
REQUIRED_PLAN_COUNT_KEYS = {
    "ready_count",
    "feedback_ready_count",
    "fix_available_ready_count",
    "please_test_ready_count",
    "recovery_loop_ready_count",
    "blocked_missing_install_receipts_count",
    "blocked_receipt_mismatch_count",
    "hold_until_fix_receipt_count",
}
REQUIRED_SUPPORT_SOURCE_KEYS = {
    "install_receipt_feed_state",
    "install_receipt_source_count",
    "install_receipt_indexed_count",
    "install_receipt_hydrated_case_count",
    "install_receipt_missing_case_count",
    "fix_receipt_feed_state",
    "fix_receipt_source_count",
    "fix_receipt_indexed_count",
    "fix_receipt_hydrated_case_count",
    "fix_receipt_missing_case_count",
}
REQUIRED_WEEKLY_WORKER_GUARD_RULE_MARKERS = (
    "repo-local files",
    "generated packets",
    "tests",
    "not operator telemetry",
    "active-run helper commands",
)
REQUIRED_SUPPORT_VERIFICATION_EMPTY_LIST_KEYS = {
    "issues",
    "missing_registry_evidence_markers",
    "missing_queue_proof_markers",
    "missing_design_queue_source_proof_markers",
    "missing_queue_design_source_proof_markers",
    "missing_registry_proof_anchor_paths",
    "missing_queue_proof_anchor_paths",
    "missing_design_queue_source_proof_anchor_paths",
    "disallowed_registry_evidence_entries",
    "disallowed_queue_proof_entries",
    "disallowed_design_queue_source_proof_entries",
}
REQUIRED_SUPPORT_VERIFICATION_MATCH_KEYS = {
    "allowed_paths",
    "owned_surfaces",
    "repo",
    "registry_path",
    "queue_staging_path",
    "required_queue_proof_markers",
    "required_registry_evidence_markers",
    "registry_dependencies",
    "registry_status",
    "registry_title",
    "registry_wave",
    "registry_work_task_id",
    "registry_work_task_count",
    "registry_work_task_title",
    "registry_work_task_status",
    "queue_task",
    "queue_wave",
    "queue_repo",
    "queue_milestone_id",
    "queue_status",
    "queue_title",
    "queue_frontier_id",
    "queue_completion_action",
    "queue_do_not_reopen_reason",
    "queue_item_count",
    "design_queue_source_path",
    "design_queue_source_item_count",
    "design_queue_source_item_found",
    "design_queue_source_title",
    "design_queue_source_task",
    "design_queue_source_wave",
    "design_queue_source_repo",
    "design_queue_source_milestone_id",
    "design_queue_source_status",
    "design_queue_source_frontier_id",
    "design_queue_source_completion_action",
    "design_queue_source_do_not_reopen_reason",
}
REQUIRED_RULE_MARKERS = (
    "feedback",
    "install truth",
    "installation-bound installed-build receipts",
    "fixed-version receipts",
    "fixed-channel receipts",
    "release-channel receipts",
)
REQUIRED_RECEIPT_BACKED_ACTION_GROUPS = {
    "feedback",
    "fix_available",
    "please_test",
    "recovery",
}
REQUIRED_ACTION_NEXT_ACTIONS = {
    "feedback": {"send_feedback_progress"},
    "fix_available": {"send_fix_available", "send_fix_available_with_update"},
    "please_test": {"send_please_test"},
    "recovery": {"send_recovery"},
}
DISALLOWED_WORKER_PROOF_MARKERS = SUCCESSOR_DISALLOWED_PROOF_MARKERS
REQUIRED_WEEKLY_WORKER_GUARD_MARKERS = set(DISALLOWED_WORKER_PROOF_MARKERS)
REQUIRED_WEEKLY_WORKER_GUARD_MARKERS.update(
    {
        "operator telemetry",
        "active-run telemetry",
        "active-run helper",
        "active run helper",
    }
)
REQUIRED_QUEUE_NEGATIVE_PROOF_MARKERS = {
    "standalone verifier rejects missing receipt-gate names",
    "no-PYTHONPATH bootstrap guard includes the standalone M102 verifier",
    "telemetry command proof markers fail the standalone verifier and shared successor authority check",
    "runtime handoff frontier metadata proof markers fail the standalone verifier and shared successor authority check",
    "weekly support-packet source sha256 drift fails the standalone verifier",
    "future-dated support and weekly generated_at receipts fail the standalone verifier",
    "standalone verifier rejects fix-available, please-test, feedback, or recovery action-group rows that omit their own install-aware receipt gates",
    "standalone verifier rejects ready action-group rows whose install receipt, release receipt, fixed receipt, or installed-build values disagree even when stale generated booleans claim ready",
    "completed queue action guard requires verify_closed_package_only and package-specific do_not_reopen_reason on Fleet and design queue rows",
}
REQUIRED_DISTINCT_QUEUE_PROOF_ENTRIES = {
    VERIFIER_PROOF_MARKER,
    TEST_PROOF_MARKER,
    "python3 tests/test_materialize_support_case_packets.py exits 0",
    "python3 scripts/verify_next90_m102_fleet_reporter_receipts.py exits 0",
    "python3 tests/test_verify_next90_m102_fleet_reporter_receipts.py exits 0",
    "standalone verifier rejects missing receipt-gate names, missing weekly receipt counters, and active-run telemetry helper proof entries",
    "no-PYTHONPATH bootstrap guard includes the standalone M102 verifier",
    "telemetry command proof markers fail the standalone verifier and shared successor authority check",
    "runtime handoff frontier metadata proof markers fail the standalone verifier and shared successor authority check",
    "weekly support-packet source sha256 drift fails the standalone verifier",
    "future-dated support and weekly generated_at receipts fail the standalone verifier",
    "standalone verifier rejects fix-available, please-test, feedback, or recovery action-group rows that omit their own install-aware receipt gates",
    "standalone verifier rejects ready action-group rows whose install receipt, release receipt, fixed receipt, or installed-build values disagree even when stale generated booleans claim ready",
    "weekly governor recomputes followthrough readiness from row-level install, release, installed-build, and fix receipt truth instead of stale summary counters or partial ready rows",
    "fix-available action rows keep `send_fix_available` versus `send_fix_available_with_update` aligned with receipt-backed `update_required`, and the standalone verifier rejects drift",
    "completed queue action guard requires verify_closed_package_only and package-specific do_not_reopen_reason on Fleet and design queue rows",
}
GENERATED_AT_MAX_FUTURE_SKEW_SECONDS = 300


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
        if path.name.endswith("NEXT_90_DAY_QUEUE_STAGING.generated.yaml"):
            payload = read_next90_queue_staging_yaml(path)
        else:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
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


def _future_timestamp_drifts(timestamps: Dict[str, dt.datetime | None]) -> Dict[str, str]:
    now = dt.datetime.now(UTC)
    max_future = now + dt.timedelta(seconds=GENERATED_AT_MAX_FUTURE_SKEW_SECONDS)
    return {
        name: parsed.isoformat().replace("+00:00", "Z")
        for name, parsed in sorted(timestamps.items())
        if parsed is not None and parsed > max_future
    }


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


def _disallowed_input_paths(paths: Iterable[Path]) -> List[str]:
    return _disallowed_proof_entries(str(path) for path in paths)


def _missing_distinct_queue_proof_entries(entries: Iterable[str]) -> List[str]:
    normalized_entries = {_normalize_text(entry) for entry in entries if _normalize_text(entry)}
    return sorted(marker for marker in REQUIRED_DISTINCT_QUEUE_PROOF_ENTRIES if marker not in normalized_entries)


def _action_group_receipt_issues(action_groups: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for group_name in sorted(REQUIRED_RECEIPT_BACKED_ACTION_GROUPS):
        rows = action_groups.get(group_name)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                issues.append(f"{group_name}[{index}] is not a receipt-backed row")
                continue
            row_label = _normalize_text(row.get("packet_id")) or f"{group_name}[{index}]"
            next_action = _normalize_text(row.get("next_action")).lower()
            expected_next_actions = REQUIRED_ACTION_NEXT_ACTIONS.get(group_name, set())
            if group_name == "fix_available" and "update_required" in row:
                expected_next_actions = {
                    "send_fix_available_with_update"
                    if bool(row.get("update_required"))
                    else "send_fix_available"
                }
            if expected_next_actions and next_action not in expected_next_actions:
                issues.append(
                    f"{group_name} row {row_label} routes to {next_action or 'missing_next_action'} "
                    f"instead of receipt-backed {', '.join(sorted(expected_next_actions))}"
                )
            base_missing: List[str] = []
            if not bool(row.get("feedback_loop_ready")):
                base_missing.append("feedback_loop_ready")
            if not bool(row.get("install_receipt_ready")):
                base_missing.append("install_receipt_ready")
            if _normalize_text(row.get("install_truth_state")).lower() != "promoted_tuple_match":
                base_missing.append("install_truth_state=promoted_tuple_match")
            if _normalize_text(row.get("release_receipt_state")).lower() != "release_receipt_ready":
                base_missing.append("release_receipt_ready")
            if not _normalize_text(row.get("release_receipt_id")):
                base_missing.append("release_receipt_id")
            if _normalize_text(row.get("release_receipt_source")) != "release_channel":
                base_missing.append("release_receipt_source=release_channel")
            if not _normalize_text(row.get("release_receipt_channel")):
                base_missing.append("release_receipt_channel")
            if not _normalize_text(row.get("release_receipt_version")):
                base_missing.append("release_receipt_version")
            if not bool(row.get("installed_build_receipted")):
                base_missing.append("installed_build_receipted")
            if bool(row.get("installed_build_receipted")) and not bool(row.get("installed_build_receipt_identity_matches")):
                base_missing.append("installed_build_receipt_tuple_bound")
            base_install_fields = (
                "installation_id",
                "installed_build_receipt_id",
                "installed_build_receipt_installation_id",
                "installed_build_receipt_version",
                "installed_build_receipt_channel",
                "installed_build_receipt_source",
                "installed_build_receipt_installation_source",
                "installed_build_receipt_version_source",
                "installed_build_receipt_channel_source",
            )
            if _normalize_text(row.get("installed_build_receipt_id")):
                base_install_fields += (
                    "installed_build_receipt_head_id",
                    "installed_build_receipt_platform",
                    "installed_build_receipt_rid",
                    "installed_build_receipt_tuple_id",
                )
            for field in base_install_fields:
                if not _normalize_text(row.get(field)):
                    base_missing.append(field)
            for field in (
                "installed_build_receipt_source",
                "installed_build_receipt_installation_source",
                "installed_build_receipt_version_source",
                "installed_build_receipt_channel_source",
            ):
                if _normalize_text(row.get(field)) != "install_receipts":
                    base_missing.append(f"{field}=install_receipts")
            if base_missing:
                issues.append(
                    f"{group_name} row {row_label} is missing install-aware receipt gates: "
                    + ", ".join(sorted(set(base_missing)))
                )
            value_mismatches: List[str] = []
            installation_id = _normalize_text(row.get("installation_id")).lower()
            installed_version = _normalize_text(row.get("installed_version")).lower()
            release_channel = _normalize_text(row.get("release_channel")).lower()
            head_id = _normalize_text(row.get("head_id")).lower()
            platform = _normalize_text(row.get("platform")).lower()
            arch = _normalize_text(row.get("arch")).lower()
            release_receipt_channel = _normalize_text(row.get("release_receipt_channel")).lower()
            installed_build_receipt_installation_id = _normalize_text(
                row.get("installed_build_receipt_installation_id")
            ).lower()
            installed_build_receipt_version = _normalize_text(row.get("installed_build_receipt_version")).lower()
            installed_build_receipt_channel = _normalize_text(row.get("installed_build_receipt_channel")).lower()
            installed_build_receipt_head_id = _normalize_text(row.get("installed_build_receipt_head_id")).lower()
            installed_build_receipt_platform = _normalize_text(row.get("installed_build_receipt_platform")).lower()
            installed_build_receipt_rid = _normalize_text(row.get("installed_build_receipt_rid")).lower()
            installed_build_receipt_tuple_id = _normalize_text(row.get("installed_build_receipt_tuple_id")).lower()
            expected_rid = ""
            if platform:
                normalized_arch = {"amd64": "x64", "x86_64": "x64"}.get(arch, arch)
                if platform == "windows":
                    expected_rid = "win-arm64" if normalized_arch == "arm64" else "win-x64"
                elif platform == "linux":
                    expected_rid = "linux-arm64" if normalized_arch == "arm64" else "linux-x64"
                elif platform == "macos":
                    expected_rid = "osx-x64" if normalized_arch == "x64" else "osx-arm64"
            expected_tuple_id = (
                f"{head_id}:{expected_rid}:{platform}"
                if head_id and expected_rid and platform
                else ""
            )
            if (
                installation_id
                and installed_build_receipt_installation_id
                and installed_build_receipt_installation_id != installation_id
            ):
                value_mismatches.append("installed_build_receipt_installation_id!=installation_id")
            if installed_version and installed_build_receipt_version and installed_build_receipt_version != installed_version:
                value_mismatches.append("installed_build_receipt_version!=installed_version")
            if (
                release_receipt_channel
                and installed_build_receipt_channel
                and installed_build_receipt_channel != release_receipt_channel
            ):
                value_mismatches.append("installed_build_receipt_channel!=release_receipt_channel")
            if release_channel and release_receipt_channel and release_channel != release_receipt_channel:
                value_mismatches.append("release_channel!=release_receipt_channel")
            if installed_build_receipt_head_id and head_id and installed_build_receipt_head_id != head_id:
                value_mismatches.append("installed_build_receipt_head_id!=head_id")
            if installed_build_receipt_platform and platform and installed_build_receipt_platform != platform:
                value_mismatches.append("installed_build_receipt_platform!=platform")
            if installed_build_receipt_rid and expected_rid and installed_build_receipt_rid != expected_rid:
                value_mismatches.append("installed_build_receipt_rid!=expected_rid")
            if (
                installed_build_receipt_tuple_id
                and expected_tuple_id
                and installed_build_receipt_tuple_id != expected_tuple_id
            ):
                value_mismatches.append("installed_build_receipt_tuple_id!=expected_tuple_id")
            if value_mismatches:
                issues.append(
                    f"{group_name} row {row_label} has install-aware receipt value mismatches: "
                    + ", ".join(sorted(set(value_mismatches)))
                )
            row_has_fix_truth = bool(
                _normalize_text(row.get("fixed_version"))
                or _normalize_text(row.get("fixed_channel"))
                or bool(row.get("fixed_version_receipted"))
                or bool(row.get("fixed_channel_receipted"))
            )
            if group_name in {"fix_available", "please_test", "recovery"} or (
                group_name == "feedback" and row_has_fix_truth
            ):
                fix_missing: List[str] = []
                if not _normalize_text(row.get("fixed_version")):
                    fix_missing.append("fixed_version")
                if not _normalize_text(row.get("fixed_channel")):
                    fix_missing.append("fixed_channel")
                if not bool(row.get("fixed_version_receipted")):
                    fix_missing.append("fixed_version_receipted")
                if not bool(row.get("fixed_channel_receipted")):
                    fix_missing.append("fixed_channel_receipted")
                for field in (
                    "fixed_version_receipt_id",
                    "fixed_channel_receipt_id",
                    "fixed_receipt_installation_id",
                    "fixed_receipt_installation_source",
                    "fixed_version_receipt_source",
                    "fixed_channel_receipt_source",
                ):
                    if not _normalize_text(row.get(field)):
                        fix_missing.append(field)
                if not bool(row.get("fixed_receipt_installation_matches")):
                    fix_missing.append("fixed_receipt_installation_bound")
                for field in (
                    "fixed_version_receipt_source",
                    "fixed_channel_receipt_source",
                    "fixed_receipt_installation_source",
                ):
                    if _normalize_text(row.get(field)) != "fix_receipts":
                        fix_missing.append(f"{field}=fix_receipts")
                if fix_missing:
                    issues.append(
                        f"{group_name} row {row_label} is missing fix receipt gates: "
                        + ", ".join(sorted(set(fix_missing)))
                    )
                fix_value_mismatches: List[str] = []
                fixed_version = _normalize_text(row.get("fixed_version")).lower()
                fixed_channel = _normalize_text(row.get("fixed_channel")).lower()
                fixed_receipt_installation_id = _normalize_text(row.get("fixed_receipt_installation_id")).lower()
                release_receipt_version = _normalize_text(row.get("release_receipt_version")).lower()
                if fixed_version and release_receipt_version and fixed_version != release_receipt_version:
                    fix_value_mismatches.append("fixed_version!=release_receipt_version")
                if fixed_channel and release_receipt_channel and fixed_channel != release_receipt_channel:
                    fix_value_mismatches.append("fixed_channel!=release_receipt_channel")
                if fixed_receipt_installation_id and installation_id and fixed_receipt_installation_id != installation_id:
                    fix_value_mismatches.append("fixed_receipt_installation_id!=installation_id")
                if (
                    group_name == "please_test"
                    and fixed_version
                    and installed_version
                    and installed_version != fixed_version
                ):
                    fix_value_mismatches.append("installed_version!=fixed_version")
                if fix_value_mismatches:
                    issues.append(
                        f"{group_name} row {row_label} has fix receipt value mismatches: "
                        + ", ".join(sorted(set(fix_value_mismatches)))
                    )
            if group_name == "please_test" and not bool(row.get("current_install_on_fixed_build")):
                issues.append(f"please_test row {row_label} is not on the fixed installed build")
            if group_name == "recovery" and not bool(row.get("recovery_loop_ready")):
                issues.append(f"recovery row {row_label} is missing recovery_loop_ready")
    return issues


def _receipt_feed_source_issues(support_source: Dict[str, Any], action_groups: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    missing_source_keys = sorted(REQUIRED_SUPPORT_SOURCE_KEYS - set(support_source.keys()))
    if missing_source_keys:
        issues.append("support packet source is missing install/fix receipt feed metadata")
        return issues

    ready_rows = [
        row
        for group_name in sorted(REQUIRED_RECEIPT_BACKED_ACTION_GROUPS)
        for row in (action_groups.get(group_name) or [])
        if isinstance(row, dict)
    ]
    if not ready_rows:
        return issues

    if _normalize_text(support_source.get("refresh_mode")) == "cached_packets_fallback":
        issues.append("ready reporter followthrough exists from cached packet fallback instead of refreshed receipt truth")
    if _normalize_text(support_source.get("seeded_from_cached_packets_generated_at")):
        issues.append("ready reporter followthrough exists from cached packet fallback instead of refreshed receipt truth")

    fix_bearing_rows = [
        row
        for row in ready_rows
        if (
            _normalize_text(row.get("fixed_version"))
            or _normalize_text(row.get("fixed_channel"))
            or bool(row.get("fixed_version_receipted"))
            or bool(row.get("fixed_channel_receipted"))
        )
    ]

    if _normalize_text(support_source.get("install_receipt_feed_state")) != "provided":
        issues.append("ready reporter followthrough exists without an authoritative install receipt feed")
    install_receipt_source_count = _as_int(support_source.get("install_receipt_source_count"))
    install_receipt_indexed_count = _as_int(support_source.get("install_receipt_indexed_count"))
    install_receipt_hydrated_case_count = _as_int(support_source.get("install_receipt_hydrated_case_count"))
    if install_receipt_source_count <= 0:
        issues.append("ready reporter followthrough exists without install receipt source rows")
    if _as_int(support_source.get("install_receipt_indexed_count")) <= 0:
        issues.append("ready reporter followthrough exists without indexed install receipts")
    if install_receipt_indexed_count > install_receipt_source_count:
        issues.append("ready reporter followthrough indexes more install receipts than the source feed provides")
    if install_receipt_hydrated_case_count <= 0:
        issues.append("ready reporter followthrough exists without hydrated install receipt cases")
    if install_receipt_hydrated_case_count > install_receipt_indexed_count:
        issues.append("ready reporter followthrough hydrates more install receipt cases than the indexed receipts allow")

    if fix_bearing_rows:
        if _normalize_text(support_source.get("fix_receipt_feed_state")) != "provided":
            issues.append("fix-bearing reporter followthrough exists without an authoritative fix receipt feed")
        fix_receipt_source_count = _as_int(support_source.get("fix_receipt_source_count"))
        fix_receipt_indexed_count = _as_int(support_source.get("fix_receipt_indexed_count"))
        fix_receipt_hydrated_case_count = _as_int(support_source.get("fix_receipt_hydrated_case_count"))
        if fix_receipt_source_count <= 0:
            issues.append("fix-bearing reporter followthrough exists without fix receipt source rows")
        if fix_receipt_indexed_count <= 0:
            issues.append("fix-bearing reporter followthrough exists without indexed fix receipts")
        if fix_receipt_indexed_count > fix_receipt_source_count:
            issues.append("fix-bearing reporter followthrough indexes more fix receipts than the source feed provides")
        if fix_receipt_hydrated_case_count <= 0:
            issues.append("fix-bearing reporter followthrough exists without hydrated fix receipt cases")
        if fix_receipt_hydrated_case_count > fix_receipt_indexed_count:
            issues.append("fix-bearing reporter followthrough hydrates more fix receipt cases than the indexed receipts allow")

    return issues


def _action_group_rows(action_groups: Dict[str, Any], group_name: str) -> List[Dict[str, Any]]:
    rows = action_groups.get(group_name)
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _distinct_packet_count(rows: Iterable[Dict[str, Any]]) -> int:
    return len(
        {
            _normalize_text(row.get("packet_id"))
            for row in rows
            if _normalize_text(row.get("packet_id"))
        }
    )


def _recomputed_row_truth(row: Dict[str, Any]) -> Dict[str, bool]:
    installation_id = _normalize_text(row.get("installation_id"))
    install_truth_ready = bool(
        installation_id
        and bool(row.get("install_receipt_ready"))
        and _normalize_text(row.get("install_truth_state")).lower() == "promoted_tuple_match"
    )
    release_receipt_ready = bool(
        _normalize_text(row.get("release_receipt_state")).lower() == "release_receipt_ready"
        and _normalize_text(row.get("release_receipt_id"))
        and _normalize_text(row.get("release_receipt_source")) == "release_channel"
        and _normalize_text(row.get("release_receipt_channel"))
        and _normalize_text(row.get("release_receipt_version"))
    )
    installed_build_receipt_ready = bool(
        install_truth_ready
        and release_receipt_ready
        and bool(row.get("installed_build_receipted"))
        and _normalize_text(row.get("installed_build_receipt_id"))
        and _normalize_text(row.get("installed_build_receipt_installation_id"))
        and _normalize_text(row.get("installed_build_receipt_version"))
        and _normalize_text(row.get("installed_build_receipt_channel"))
        and _normalize_text(row.get("installed_build_receipt_source")) == "install_receipts"
        and _normalize_text(row.get("installed_build_receipt_installation_source")) == "install_receipts"
        and _normalize_text(row.get("installed_build_receipt_version_source")) == "install_receipts"
        and _normalize_text(row.get("installed_build_receipt_channel_source")) == "install_receipts"
        and bool(row.get("installed_build_receipt_installation_matches"))
        and bool(row.get("installed_build_receipt_version_matches"))
        and bool(row.get("installed_build_receipt_channel_matches"))
        and bool(row.get("installed_build_receipt_identity_matches"))
    )
    has_fix_truth = bool(
        _normalize_text(row.get("fixed_version"))
        or _normalize_text(row.get("fixed_channel"))
        or bool(row.get("fixed_version_receipted"))
        or bool(row.get("fixed_channel_receipted"))
    )
    fix_receipts_ready = bool(
        not has_fix_truth
        or (
            _normalize_text(row.get("fixed_version"))
            and _normalize_text(row.get("fixed_channel"))
            and bool(row.get("fixed_version_receipted"))
            and bool(row.get("fixed_channel_receipted"))
            and _normalize_text(row.get("fixed_version_receipt_id"))
            and _normalize_text(row.get("fixed_channel_receipt_id"))
            and _normalize_text(row.get("fixed_receipt_installation_id"))
            and _normalize_text(row.get("fixed_version_receipt_source")) == "fix_receipts"
            and _normalize_text(row.get("fixed_channel_receipt_source")) == "fix_receipts"
            and _normalize_text(row.get("fixed_receipt_installation_source")) == "fix_receipts"
            and bool(row.get("fixed_receipt_installation_matches"))
        )
    )
    feedback_loop_ready = bool(
        install_truth_ready and release_receipt_ready and installed_build_receipt_ready and fix_receipts_ready
    )
    fix_available_ready = bool(has_fix_truth and feedback_loop_ready)
    please_test_ready = bool(fix_available_ready and bool(row.get("current_install_on_fixed_build")))
    recovery_loop_ready = bool(
        fix_available_ready
        and _normalize_text(((row.get("recovery_path") or {}).get("action_id"))).lower()
        in {"open_downloads", "open_support_timeline", "open_account_access"}
    )
    return {
        "feedback_loop_ready": feedback_loop_ready,
        "fix_available_ready": fix_available_ready,
        "please_test_ready": please_test_ready,
        "recovery_loop_ready": recovery_loop_ready,
    }


def _row_ready_for_group(row_truth: Dict[str, Any], group_name: str) -> bool:
    if group_name == "feedback":
        return bool(row_truth.get("feedback_loop_ready"))
    if group_name == "fix_available":
        return bool(row_truth.get("fix_available_ready")) and not bool(row_truth.get("please_test_ready"))
    if group_name == "please_test":
        return bool(row_truth.get("please_test_ready"))
    if group_name == "recovery":
        return bool(row_truth.get("recovery_loop_ready"))
    return False


def _computed_plan_counts(action_groups: Dict[str, Any]) -> Dict[str, int]:
    ready_group_names = ("feedback", "fix_available", "please_test", "recovery")
    rows_by_key: Dict[str, Dict[str, Any]] = {}
    ready_keys: set[str] = set()
    ready_group_counts = {name: 0 for name in ready_group_names}
    for group_name in ready_group_names:
        for index, row in enumerate(_action_group_rows(action_groups, group_name)):
            packet_id = _normalize_text(row.get("packet_id"))
            row_key = packet_id or f"{group_name}:{index}"
            merged_row = dict(rows_by_key.get(row_key) or {})
            merged_row.update(row)
            rows_by_key[row_key] = merged_row
            row_truth = _recomputed_row_truth(merged_row)
            if _row_ready_for_group(row_truth, group_name):
                ready_keys.add(row_key)
                ready_group_counts[group_name] += 1
    return {
        "ready_count": len(ready_keys),
        "feedback_ready_count": ready_group_counts["feedback"],
        "fix_available_ready_count": ready_group_counts["fix_available"],
        "please_test_ready_count": ready_group_counts["please_test"],
        "recovery_loop_ready_count": ready_group_counts["recovery"],
        "blocked_missing_install_receipts_count": len(
            _action_group_rows(action_groups, "blocked_missing_install_receipts")
        ),
        "blocked_receipt_mismatch_count": len(_action_group_rows(action_groups, "blocked_receipt_mismatch")),
        "hold_until_fix_receipt_count": len(_action_group_rows(action_groups, "hold_until_fix_receipt")),
    }


def _computed_gate_counts(packets: List[Dict[str, Any]]) -> Dict[str, int]:
    followthrough_rows = [
        _followthrough_packet_row(packet, packet.get("reporter_followthrough") or {})
        for packet in packets
        if bool(packet.get("support_case_backed")) and isinstance(packet.get("reporter_followthrough"), dict)
    ]
    gate_evidence_rows = [_followthrough_row_gate_evidence(row) for row in followthrough_rows]
    return {
        key: sum(1 for row in gate_evidence_rows if bool(row.get(key)))
        for key in sorted(REQUIRED_GATE_COUNT_NAMES)
    }


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
    blocked_input_paths = _disallowed_input_paths(
        (
            support_packets_path,
            weekly_governor_packet_path,
            weekly_governor_markdown_path,
        )
    )

    if blocked_input_paths:
        issues.append("verifier inputs cite active-run telemetry or helper paths")

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
    missing_queue_negative_proof_markers = _contains_all_markers(
        "\n".join(queue_proof),
        REQUIRED_QUEUE_NEGATIVE_PROOF_MARKERS,
    )
    if missing_queue_negative_proof_markers:
        issues.append("successor queue proof is missing standalone verifier negative-proof markers")
    missing_distinct_queue_proof_entries = _missing_distinct_queue_proof_entries(queue_proof)
    if missing_distinct_queue_proof_entries:
        issues.append("successor queue proof collapses required command or negative-proof entries")
    blocked_registry_evidence_entries = _disallowed_proof_entries(registry_evidence)
    blocked_queue_proof_entries = _disallowed_proof_entries(queue_proof)
    blocked_design_queue_source_proof_entries = _normalize_list(
        successor.get("disallowed_design_queue_source_proof_entries")
    )
    blocked_proof_entries = (
        blocked_registry_evidence_entries
        + blocked_queue_proof_entries
        + blocked_design_queue_source_proof_entries
    )
    if blocked_registry_evidence_entries:
        issues.append("successor registry evidence cites active-run telemetry or helper commands")
    if blocked_queue_proof_entries:
        issues.append("successor queue proof cites active-run telemetry or helper commands")
    if blocked_design_queue_source_proof_entries:
        issues.append("successor design queue source proof cites active-run telemetry or helper commands")

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
    missing_support_verification_empty_list_keys = sorted(
        key for key in REQUIRED_SUPPORT_VERIFICATION_EMPTY_LIST_KEYS if key not in support_verification
    )
    if support_verification_nonempty_lists or missing_support_verification_empty_list_keys:
        issues.append("SUPPORT_CASE_PACKETS.generated.json successor verification carries stale proof gaps")
    support_blocked_proof_entries = (
        support_verification_nonempty_lists.get("disallowed_registry_evidence_entries", [])
        + support_verification_nonempty_lists.get("disallowed_queue_proof_entries", [])
        + support_verification_nonempty_lists.get("disallowed_design_queue_source_proof_entries", [])
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
    support_packet_rows = support_packets.get("packets")
    if not isinstance(support_packet_rows, list):
        support_packet_rows = []
    computed_gate_counts = _computed_gate_counts(
        [packet for packet in support_packet_rows if isinstance(packet, dict)]
    )
    gate_count_mismatches = {
        key: {
            "receipt_backed_followthrough_rows": expected,
            "followthrough_receipt_gates": _as_int(gate_counts.get(key)),
        }
        for key, expected in computed_gate_counts.items()
        if key in gate_counts and _as_int(gate_counts.get(key)) != expected
    }
    if gate_count_mismatches:
        issues.append("followthrough receipt gate counters disagree with receipt-backed followthrough rows")
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
    missing_plan_count_keys = sorted(REQUIRED_PLAN_COUNT_KEYS - set(plan.keys()))
    if missing_plan_count_keys:
        issues.append("reporter followthrough plan is missing receipt-backed loop counters")
    computed_plan_counts = _computed_plan_counts(action_groups)
    plan_count_mismatches = {
        "ready_count": {
            "receipt_backed_action_groups": computed_plan_counts["ready_count"],
            "reporter_followthrough_plan": _as_int(plan.get("ready_count")),
        }
    } if _as_int(plan.get("ready_count")) != computed_plan_counts["ready_count"] else {}
    for plan_key, computed_key in (
        ("feedback_ready_count", "feedback_ready_count"),
        ("fix_available_ready_count", "fix_available_ready_count"),
        ("please_test_ready_count", "please_test_ready_count"),
        ("recovery_loop_ready_count", "recovery_loop_ready_count"),
        ("blocked_missing_install_receipts_count", "blocked_missing_install_receipts_count"),
        ("blocked_receipt_mismatch_count", "blocked_receipt_mismatch_count"),
        ("hold_until_fix_receipt_count", "hold_until_fix_receipt_count"),
    ):
        if plan_key in plan and _as_int(plan.get(plan_key)) != computed_plan_counts[computed_key]:
            plan_count_mismatches[plan_key] = {
                "receipt_backed_action_groups": computed_plan_counts[computed_key],
                "reporter_followthrough_plan": _as_int(plan.get(plan_key)),
            }
    if plan_count_mismatches:
        issues.append("reporter followthrough plan counts disagree with receipt-backed action groups")
    action_group_receipt_issues = _action_group_receipt_issues(action_groups)
    if action_group_receipt_issues:
        issues.append("reporter followthrough action groups contain rows without receipt gates")
    receipt_gate_plan_count_mismatches = {
        "ready_count": {
            "receipt_backed_action_groups": computed_plan_counts["ready_count"],
            "followthrough_receipt_gates": _as_int(receipt_gates.get("ready_count")),
        }
    } if _as_int(receipt_gates.get("ready_count")) != computed_plan_counts["ready_count"] else {}
    for receipt_gate_key, computed_key in (
        ("blocked_missing_install_receipts_count", "blocked_missing_install_receipts_count"),
        ("blocked_receipt_mismatch_count", "blocked_receipt_mismatch_count"),
        ("hold_until_fix_receipt_count", "hold_until_fix_receipt_count"),
    ):
        if receipt_gate_key in receipt_gates and _as_int(receipt_gates.get(receipt_gate_key)) != computed_plan_counts[computed_key]:
            receipt_gate_plan_count_mismatches[receipt_gate_key] = {
                "receipt_backed_action_groups": computed_plan_counts[computed_key],
                "followthrough_receipt_gates": _as_int(receipt_gates.get(receipt_gate_key)),
            }
    if receipt_gate_plan_count_mismatches:
        issues.append("followthrough receipt gate counts disagree with receipt-backed action groups")
    support_source = support_packets.get("source")
    if not isinstance(support_source, dict):
        support_source = {}
    receipt_feed_source_issues = _receipt_feed_source_issues(support_source, action_groups)
    if receipt_feed_source_issues:
        issues.append("support packet source receipt-feed metadata does not back ready followthrough")

    support_summary = support_packets.get("summary")
    if not isinstance(support_summary, dict):
        support_summary = {}
        issues.append("SUPPORT_CASE_PACKETS.generated.json summary is missing")
    missing_support_summary_keys = sorted(REQUIRED_SUPPORT_SUMMARY_KEYS - set(support_summary.keys()))
    if missing_support_summary_keys:
        issues.append("SUPPORT_CASE_PACKETS.generated.json summary is missing receipt-gated followthrough keys")
    expected_support_summary_counts = {
        "reporter_followthrough_ready_count": computed_plan_counts["ready_count"],
        "feedback_followthrough_ready_count": computed_plan_counts["feedback_ready_count"],
        "fix_available_ready_count": computed_plan_counts["fix_available_ready_count"],
        "please_test_ready_count": computed_plan_counts["please_test_ready_count"],
        "recovery_loop_ready_count": computed_plan_counts["recovery_loop_ready_count"],
        "reporter_followthrough_blocked_missing_install_receipts_count": _as_int(
            computed_plan_counts["blocked_missing_install_receipts_count"]
        ),
        "reporter_followthrough_blocked_receipt_mismatch_count": _as_int(
            computed_plan_counts["blocked_receipt_mismatch_count"]
        ),
        "reporter_followthrough_hold_until_fix_receipt_count": _as_int(
            computed_plan_counts["hold_until_fix_receipt_count"]
        ),
    }
    support_summary_count_mismatches = {
        key: {
            "receipt_backed_plan": expected,
            "support_packet_summary": _as_int(support_summary.get(key)),
        }
        for key, expected in expected_support_summary_counts.items()
        if key in support_summary and _as_int(support_summary.get(key)) != expected
    }
    if support_summary_count_mismatches:
        issues.append("SUPPORT_CASE_PACKETS.generated.json summary disagrees with receipt-backed followthrough plan")

    weekly_sources = weekly.get("source_input_health")
    if not isinstance(weekly_sources, dict):
        weekly_sources = weekly.get("input_health")
    support_input = {}
    source_path_hygiene = {}
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
        if isinstance(required_inputs.get("source_path_hygiene"), dict):
            source_path_hygiene = required_inputs.get("source_path_hygiene") or {}
    if not support_input:
        issues.append("weekly governor support-packets input is missing")
    elif support_input.get("successor_package_verification_status") != "pass":
        issues.append("weekly governor support-packets input does not report successor verification pass")
    elif _disallowed_input_paths((Path(_normalize_text(support_input.get("source_path"))),)):
        issues.append("weekly governor support-packets input path cites active-run telemetry or helper paths")
    elif _normalize_text(support_input.get("source_path")) != str(support_packets_path):
        issues.append("weekly governor support-packets input path disagrees with verified support packet")
    else:
        weekly_support_sha256 = _normalize_text(support_input.get("source_sha256")).lower()
        actual_support_sha256 = _sha256_file(support_packets_path)
        if not weekly_support_sha256:
            issues.append("weekly governor support-packets input is missing source_sha256")
        elif weekly_support_sha256 != actual_support_sha256:
            issues.append("weekly governor support-packets input sha256 disagrees with verified support packet")
    missing_weekly_source_path_markers: List[str] = []
    if source_path_hygiene:
        source_path_markers = set(_normalize_list(source_path_hygiene.get("blocked_markers")))
        missing_weekly_source_path_markers = sorted(
            marker for marker in REQUIRED_WEEKLY_WORKER_GUARD_MARKERS if marker not in source_path_markers
        )
        if _normalize_text(source_path_hygiene.get("state")).lower() != "pass":
            issues.append("weekly governor source-path hygiene is not pass")
        if _normalize_list(source_path_hygiene.get("disallowed_source_paths")):
            issues.append("weekly governor source-path hygiene reports disallowed source paths")
        if missing_weekly_source_path_markers:
            issues.append("weekly governor source-path hygiene is missing blocked helper markers")
    else:
        issues.append("weekly governor source-path hygiene input is missing")

    repeat_prevention = weekly.get("repeat_prevention") if isinstance(weekly.get("repeat_prevention"), dict) else {}
    worker_command_guard = (
        repeat_prevention.get("worker_command_guard")
        if isinstance(repeat_prevention.get("worker_command_guard"), dict)
        else {}
    )
    missing_weekly_worker_guard_markers: List[str] = []
    if worker_command_guard:
        worker_guard_markers = set(_normalize_list(worker_command_guard.get("blocked_markers")))
        missing_weekly_worker_guard_markers = sorted(
            marker for marker in REQUIRED_WEEKLY_WORKER_GUARD_MARKERS if marker not in worker_guard_markers
        )
        if _normalize_text(worker_command_guard.get("status")) != "active_run_helpers_forbidden":
            issues.append("weekly governor worker command guard is not active")
        if missing_weekly_worker_guard_markers:
            issues.append("weekly governor worker command guard is missing blocked helper markers")
        missing_worker_guard_rule_markers = _contains_all_markers(
            _normalize_text(worker_command_guard.get("rule")),
            REQUIRED_WEEKLY_WORKER_GUARD_RULE_MARKERS,
        )
        if missing_worker_guard_rule_markers:
            issues.append("weekly governor worker command guard rule drifted")
    else:
        issues.append("weekly governor worker command guard is missing")
    support_generated_at = _parse_iso_utc(support_packets.get("generated_at"))
    receipt_gates_generated_at = _parse_iso_utc(receipt_gates.get("generated_at"))
    reporter_plan_generated_at = _parse_iso_utc(plan.get("generated_at"))
    weekly_generated_at = _parse_iso_utc(weekly.get("generated_at"))
    markdown_values = _markdown_label_values(weekly_markdown)
    markdown_generated_at = _markdown_generated_at(weekly_markdown)
    if not support_generated_at:
        issues.append("SUPPORT_CASE_PACKETS.generated.json generated_at is missing or invalid")
    if not receipt_gates_generated_at:
        issues.append("followthrough receipt gates generated_at is missing or invalid")
    if not reporter_plan_generated_at:
        issues.append("reporter followthrough plan generated_at is missing or invalid")
    if (
        support_generated_at
        and receipt_gates_generated_at
        and receipt_gates_generated_at != support_generated_at
    ):
        issues.append("followthrough receipt gates generated_at disagrees with support packet")
    if (
        support_generated_at
        and reporter_plan_generated_at
        and reporter_plan_generated_at != support_generated_at
    ):
        issues.append("reporter followthrough plan generated_at disagrees with support packet")
    if not weekly_generated_at:
        issues.append("WEEKLY_GOVERNOR_PACKET.generated.json generated_at is missing or invalid")
    if support_generated_at and weekly_generated_at and weekly_generated_at < support_generated_at:
        issues.append("weekly governor packet predates support-packet receipt gates")
    weekly_markdown_generated_at_parsed = _parse_iso_utc(markdown_generated_at)
    future_timestamp_drifts = _future_timestamp_drifts(
        {
            "support_packets.generated_at": support_generated_at,
            "followthrough_receipt_gates.generated_at": receipt_gates_generated_at,
            "reporter_followthrough_plan.generated_at": reporter_plan_generated_at,
            "weekly_governor_packet.generated_at": weekly_generated_at,
            "weekly_governor_markdown.generated_at": weekly_markdown_generated_at_parsed,
        }
    )
    if future_timestamp_drifts:
        issues.append("generated receipt timestamps are future-dated")
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
        "reporter_followthrough_ready_count": computed_plan_counts["ready_count"],
        "feedback_followthrough_ready_count": computed_plan_counts["feedback_ready_count"],
        "fix_available_ready_count": computed_plan_counts["fix_available_ready_count"],
        "please_test_ready_count": computed_plan_counts["please_test_ready_count"],
        "recovery_loop_ready_count": computed_plan_counts["recovery_loop_ready_count"],
        "reporter_followthrough_blocked_missing_install_receipts_count": _as_int(
            computed_plan_counts["blocked_missing_install_receipts_count"]
        ),
        "reporter_followthrough_blocked_receipt_mismatch_count": _as_int(
            computed_plan_counts["blocked_receipt_mismatch_count"]
        ),
        "reporter_followthrough_hold_until_fix_receipt_count": _as_int(
            computed_plan_counts["hold_until_fix_receipt_count"]
        ),
        "reporter_followthrough_plan_ready_count": computed_plan_counts["ready_count"],
        "reporter_followthrough_plan_blocked_missing_install_receipts_count": _as_int(
            computed_plan_counts["blocked_missing_install_receipts_count"]
        ),
        "reporter_followthrough_plan_blocked_receipt_mismatch_count": _as_int(
            computed_plan_counts["blocked_receipt_mismatch_count"]
        ),
        "reporter_followthrough_plan_hold_until_fix_receipt_count": _as_int(
            computed_plan_counts["hold_until_fix_receipt_count"]
        ),
        "followthrough_receipt_gates_hold_until_fix_receipt_count": _as_int(
            receipt_gates.get("hold_until_fix_receipt_count")
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

    if not weekly_markdown:
        issues.append("WEEKLY_GOVERNOR_PACKET.generated.md is missing or unreadable")
    elif markdown_generated_at != _normalize_text(weekly.get("generated_at")):
        issues.append("weekly governor markdown generated timestamp disagrees with JSON packet")
    expected_markdown_counts = {
        "Reporter followthrough ready": computed_plan_counts["ready_count"],
        "Feedback followthrough ready": computed_plan_counts["feedback_ready_count"],
        "Fix-available ready": computed_plan_counts["fix_available_ready_count"],
        "Please-test ready": computed_plan_counts["please_test_ready_count"],
        "Recovery-loop ready": computed_plan_counts["recovery_loop_ready_count"],
        "Followthrough blocked on install receipts": _as_int(
            receipt_gates.get("blocked_missing_install_receipts_count")
        ),
        "Followthrough receipt mismatches": _as_int(receipt_gates.get("blocked_receipt_mismatch_count")),
        "Followthrough waiting on fix receipt": _as_int(computed_plan_counts["hold_until_fix_receipt_count"]),
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
        "successor_authority_issues": successor.get("issues", []),
        "queue_proof_entry_count": len(queue_proof),
        "blocked_proof_entries": blocked_proof_entries,
        "blocked_input_paths": blocked_input_paths,
        "blocked_registry_evidence_entries": blocked_registry_evidence_entries,
        "blocked_queue_proof_entries": blocked_queue_proof_entries,
        "blocked_design_queue_source_proof_entries": blocked_design_queue_source_proof_entries,
        "support_packet_blocked_proof_entries": support_blocked_proof_entries,
        "support_packet_stale_proof_gaps": support_verification_nonempty_lists,
        "missing_support_packet_proof_gap_fields": missing_support_verification_empty_list_keys,
        "support_packet_successor_field_mismatches": support_verification_field_mismatches,
        "missing_gate_names": missing_gate_names,
        "missing_gate_counts": missing_gate_counts,
        "gate_count_mismatches": gate_count_mismatches,
        "missing_action_groups": missing_action_groups,
        "missing_plan_count_keys": missing_plan_count_keys,
        "plan_count_mismatches": plan_count_mismatches,
        "receipt_gate_plan_count_mismatches": receipt_gate_plan_count_mismatches,
        "action_group_receipt_issues": action_group_receipt_issues,
        "receipt_feed_source_issues": receipt_feed_source_issues,
        "missing_support_source_keys": sorted(REQUIRED_SUPPORT_SOURCE_KEYS - set(support_source.keys())),
        "missing_support_summary_keys": missing_support_summary_keys,
        "support_summary_count_mismatches": support_summary_count_mismatches,
        "missing_weekly_support_keys": missing_weekly_keys,
        "missing_weekly_source_path_hygiene_markers": missing_weekly_source_path_markers,
        "missing_weekly_worker_guard_markers": missing_weekly_worker_guard_markers,
        "missing_queue_negative_proof_markers": missing_queue_negative_proof_markers,
        "missing_distinct_queue_proof_entries": missing_distinct_queue_proof_entries,
        "weekly_count_mismatches": weekly_count_mismatches,
        "future_timestamp_drifts": future_timestamp_drifts,
        "missing_weekly_markdown_labels": missing_markdown_labels,
        "weekly_markdown_count_mismatches": weekly_markdown_count_mismatches,
        "support_packets_generated_at": _normalize_text(support_packets.get("generated_at")),
        "followthrough_receipt_gates_generated_at": _normalize_text(receipt_gates.get("generated_at")),
        "reporter_followthrough_plan_generated_at": _normalize_text(plan.get("generated_at")),
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
