#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m128-fleet-add-freshness-and-contradiction-monitors-for-telemetry-p"
FRONTIER_ID = 6911125913
MILESTONE_ID = 128
WORK_TASK_ID = "128.5"
WAVE_ID = "W18"
QUEUE_TITLE = "Add freshness and contradiction monitors for telemetry, privacy, retention, localization, support, and crash proof planes."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [105, 106, 111, 121, 124]
OWNED_SURFACES = ["add_freshness_and_contradiction_monitors:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M128_FLEET_TRUST_PLANE_MONITORS.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M128_FLEET_TRUST_PLANE_MONITORS.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
NEXT90_GUIDE = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
LOCALIZATION_SYSTEM = PRODUCT_MIRROR / "LOCALIZATION_AND_LANGUAGE_SYSTEM.md"
TELEMETRY_MODEL = PRODUCT_MIRROR / "PRODUCT_USAGE_TELEMETRY_MODEL.md"
TELEMETRY_SCHEMA = PRODUCT_MIRROR / "PRODUCT_USAGE_TELEMETRY_EVENT_SCHEMA.md"
PRIVACY_BOUNDARIES = PRODUCT_MIRROR / "PRIVACY_AND_RETENTION_BOUNDARIES.md"
CRASH_REPORTING = PRODUCT_MIRROR / "FEEDBACK_AND_CRASH_REPORTING_SYSTEM.md"
SUPPORT_STATUS = PRODUCT_MIRROR / "FEEDBACK_AND_CRASH_STATUS_MODEL.md"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
SUPPORT_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
WEEKLY_PRODUCT_PULSE = PUBLISHED / "WEEKLY_PRODUCT_PULSE.generated.json"

GUIDE_MARKERS = {
    "wave_18": "## Wave 18 - finish release operations, localization, privacy, and support trust",
    "milestone_128": "### 128. Localization, accessibility, telemetry, privacy, support, and crash trust completion",
    "exit_contract": "Exit: promoted desktop, mobile, Hub, public, support, and artifact surfaces satisfy localization, accessibility, dense-data, telemetry, privacy, retention, support, and crash-status contracts.",
}
LOCALIZATION_MARKERS = {
    "shipping_locale_set": "## Shipping locale set",
    "restart_safe": "changing language requires restart",
    "support_critical_scope": "The following surfaces are first-class localization scope from day one of the desktop wave:",
    "deterministic_fallback": "deterministic fallback",
}
TELEMETRY_MODEL_MARKERS = {
    "opt_out_default": "Chummer should treat product-improvement telemetry as opt-out, not opt-in.",
    "tier_2_default": "### Tier 2: pseudonymous hosted product telemetry",
    "crash_debug_opt_out": "after a crash, the crash handler may temporarily arm crash-focused debug uplift for the next launch and recovery flow",
    "trust_control": "### 12. Telemetry trust and control",
}
TELEMETRY_SCHEMA_MARKERS = {
    "posture": "The default product-improvement telemetry plane is opt-out.",
    "bounded_envelope": "Every Tier-2 hosted telemetry event must fit this bounded envelope:",
    "ui_settings": "### `chummer6-ui` settings",
    "delivery_safety": "## Delivery safety rules",
}
PRIVACY_MARKERS = {
    "product_usage_telemetry": "### Product usage telemetry",
    "raw_events_30_days": "raw hosted product-improvement event envelopes: retain for 30 days or less, then collapse into bounded daily rollups",
    "rollups_18_months": "install-linked daily usage rollups: retain for 18 months",
    "debug_uplift_30_days": "delete or summarize within 30 days",
}
CRASH_REPORTING_MARKERS = {
    "three_lanes": "1. crash reporting",
    "hub_owned_intake": "captures the crash locally and sends a redacted crash envelope to a Hub-owned intake endpoint.",
    "fleet_secondary": "may consume the normalized crash work item for clustering, repro, test generation, candidate patch drafting, and PR preparation.",
    "release_truth_boundary": "That does not make Fleet the support database, and it does not allow direct client-to-Fleet raw crash transport as the primary seam.",
}
SUPPORT_STATUS_MARKERS = {
    "status_spine": "## Status spine",
    "closure_rule": "Notify a reporter that the issue is fixed only when Registry truth says the fix has reached that reporter's channel.",
    "released_to_reporter_channel": "`released_to_reporter_channel`, `user_notified`, and `closed` only count as healthy closure when support packets and registry release truth agree.",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M128 trust-plane monitor packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--next90-guide", default=str(NEXT90_GUIDE))
    parser.add_argument("--localization-system", default=str(LOCALIZATION_SYSTEM))
    parser.add_argument("--telemetry-model", default=str(TELEMETRY_MODEL))
    parser.add_argument("--telemetry-schema", default=str(TELEMETRY_SCHEMA))
    parser.add_argument("--privacy-boundaries", default=str(PRIVACY_BOUNDARIES))
    parser.add_argument("--crash-reporting", default=str(CRASH_REPORTING))
    parser.add_argument("--support-status", default=str(SUPPORT_STATUS))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--weekly-product-pulse", default=str(WEEKLY_PRODUCT_PULSE))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        if "\nitems:\n" not in raw:
            return {}
        try:
            payload = yaml.safe_load("items:\n" + raw.split("\nitems:\n", 1)[1]) or {}
        except yaml.YAMLError:
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


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": _sha256_file(path), "generated_at": _normalize_text(payload.get("generated_at"))}


def _runtime_source_link(path: Path) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": "", "generated_at": ""}


def _text_source_link(path: Path) -> Dict[str, Any]:
    return {"path": _display_path(path), "sha256": _sha256_file(path), "generated_at": ""}


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("package_id")) == package_id:
            return dict(row)
    return {}


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and int(row.get("id") or 0) == milestone_id:
            return dict(row)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in milestone.get("work_tasks") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == work_task_id:
            return dict(row)
    return {}


def _parse_iso_utc(value: str) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def _age_seconds(value: str, *, now: dt.datetime) -> int | None:
    parsed = _parse_iso_utc(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds()))


def _marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _queue_alignment(queue_item: Dict[str, Any], design_queue_item: Dict[str, Any], work_task: Dict[str, Any], milestone: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    if not queue_item:
        issues.append("Fleet queue row is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TASK,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "repo": "fleet",
        "wave": WAVE_ID,
        "frontier_id": FRONTIER_ID,
    }
    for field, expected_value in expected.items():
        expected_text = _normalize_text(expected_value)
        if queue_item and _normalize_text(queue_item.get(field)) != expected_text:
            issues.append(f"Fleet queue {field} drifted.")
        if design_queue_item and _normalize_text(design_queue_item.get(field)) != expected_text:
            issues.append(f"Design queue {field} drifted.")
    if queue_item and _normalize_list(queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Fleet queue allowed_paths drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Design queue allowed_paths drifted.")
    if queue_item and _normalize_list(queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Fleet queue owned_surfaces drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Design queue owned_surfaces drifted.")
    if work_task:
        if _normalize_text(work_task.get("owner")) != "fleet":
            issues.append("Canonical registry work task owner drifted.")
        if _normalize_text(work_task.get("title")) != WORK_TASK_TITLE:
            issues.append("Canonical registry work task title drifted.")
    if milestone and [int(value) for value in milestone.get("dependencies") or []] != WORK_TASK_DEPENDENCIES:
        issues.append("Canonical registry milestone dependencies drifted from M128 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _section_between(text: str, start_heading: str) -> str:
    marker = f"## {start_heading}"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    parts = tail.split("\n## ", 1)
    return parts[0]


def _localization_runtime_monitor(localization_text: str, flagship_payload: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    shipping_section = _section_between(localization_text, "Shipping locale set")
    document_locales = sorted({match.lower() for match in re.findall(r"`([A-Za-z]{2}-[A-Za-z]{2})`", shipping_section)})
    desktop_evidence = dict(((flagship_payload.get("coverage_details") or {}).get("desktop_client") or {}).get("evidence") or {})
    runtime_locales = sorted({value.lower() for value in _normalize_list(desktop_evidence.get("ui_localization_release_gate_shipping_locales"))})
    gate_status = _normalize_text(desktop_evidence.get("ui_localization_release_gate_status")) or "unknown"
    if not document_locales:
        issues.append("Localization canon does not expose a shipping locale set.")
    if not runtime_locales:
        issues.append("Flagship readiness is missing runtime localization shipping locales.")
    if document_locales and runtime_locales and document_locales != runtime_locales:
        runtime_blockers.append(
            "Localization shipping locale set drifted between canon and runtime gate: "
            + ", ".join(document_locales)
            + " != "
            + ", ".join(runtime_locales)
        )
    if gate_status != "pass":
        runtime_blockers.append(f"UI localization release gate status is {gate_status}.")
    untranslated_locale_count = int(desktop_evidence.get("ui_localization_release_gate_untranslated_locale_count") or 0)
    if untranslated_locale_count > 0:
        runtime_blockers.append(f"UI localization release gate still has {untranslated_locale_count} untranslated locale(s).")
    backlog_finding_count = int(desktop_evidence.get("ui_localization_release_gate_translation_backlog_finding_count") or 0)
    if backlog_finding_count > 0:
        warnings.append(f"UI localization release gate still reports {backlog_finding_count} translation backlog finding(s).")
    return {
        "state": "pass" if not issues else "fail",
        "document_locales": document_locales,
        "runtime_locales": runtime_locales,
        "gate_status": gate_status,
        "untranslated_locale_count": untranslated_locale_count,
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def _telemetry_posture_monitor(model_text: str, schema_text: str, privacy_text: str) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    opt_out_model = "opt-out, not opt-in" in model_text
    opt_out_schema = "opt-out." in schema_text and "default product-improvement telemetry plane is opt-out" in schema_text.lower()
    opt_out_privacy = "opt-out by default" in privacy_text
    pseudonymous_model = "pseudonymous hosted product telemetry" in model_text
    pseudonymous_privacy = "pseudonymous by default" in privacy_text
    if not (opt_out_model and opt_out_schema and opt_out_privacy):
        issues.append("Telemetry default posture drifted across model, schema, and privacy canon.")
    if not (pseudonymous_model and pseudonymous_privacy):
        issues.append("Telemetry pseudonymous posture drifted across model and privacy canon.")
    if "clear any unsent Tier-2 spool within 24 hours" not in schema_text:
        warnings.append("Telemetry schema no longer states the 24-hour unsent Tier-2 spool clear rule.")
    return {
        "state": "pass" if not issues else "fail",
        "telemetry_default_posture": "opt_out_default" if not issues else "drifted",
        "pseudonymous_posture": "aligned" if pseudonymous_model and pseudonymous_privacy else "drifted",
        "issues": issues,
        "warnings": warnings,
    }


def _retention_monitor(privacy_text: str, reporting_text: str, support_status_text: str) -> Dict[str, Any]:
    issues: List[str] = []
    warnings: List[str] = []
    if "raw crash envelopes: retain for 90 days" not in privacy_text:
        issues.append("Privacy canon no longer defines the 90-day raw crash envelope retention rule.")
    if "raw hosted product-improvement event envelopes: retain for 30 days or less" not in privacy_text:
        issues.append("Privacy canon no longer defines the 30-day raw telemetry retention rule.")
    if "install-linked daily usage rollups: retain for 18 months" not in privacy_text:
        issues.append("Privacy canon no longer defines the 18-month telemetry rollup retention rule.")
    if "the recovery dialog must offer a remembered opt-out" not in reporting_text:
        issues.append("Crash reporting canon no longer requires remembered opt-out after crash-triggered debug uplift.")
    if "released_to_reporter_channel" not in support_status_text:
        warnings.append("Support status canon no longer names released_to_reporter_channel explicitly.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
    }


def _support_crash_runtime_monitor(
    flagship_payload: Dict[str, Any],
    support_packets: Dict[str, Any],
    weekly_pulse: Dict[str, Any],
    *,
    now: dt.datetime,
) -> Dict[str, Any]:
    issues: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []

    feedback_plane = dict((flagship_payload.get("readiness_planes") or {}).get("feedback_loop_ready") or {})
    feedback_evidence = dict(feedback_plane.get("evidence") or {})
    feedback_status = _normalize_text(feedback_plane.get("status")) or "unknown"
    support_summary = dict(support_packets.get("summary") or {})
    support_source = dict(support_packets.get("source") or {})
    weekly_closure = dict((weekly_pulse.get("supporting_signals") or {}).get("closure_health") or {})

    if feedback_status != "ready":
        runtime_blockers.append(f"Flagship readiness feedback loop plane is {feedback_status}.")

    support_generated_at = _normalize_text(support_packets.get("generated_at"))
    feedback_support_generated_at = _normalize_text(feedback_evidence.get("support_generated_at"))
    if support_generated_at and feedback_support_generated_at and support_generated_at != feedback_support_generated_at:
        runtime_blockers.append("Support packet generated_at drifted from flagship feedback-loop evidence.")

    comparisons = (
        ("open_packet_count", int(support_summary.get("open_packet_count") or 0), int(feedback_evidence.get("support_open_packet_count") or 0)),
        ("open_non_external_packet_count", int(support_summary.get("open_non_external_packet_count") or 0), int(feedback_evidence.get("support_open_non_external_packet_count") or 0)),
        ("closure_waiting_on_release_truth", int(support_summary.get("closure_waiting_on_release_truth") or 0), int(feedback_evidence.get("closure_waiting_on_release_truth") or 0)),
        ("update_required_misrouted_case_count", int(support_summary.get("update_required_misrouted_case_count") or 0), int(feedback_evidence.get("update_required_misrouted_case_count") or 0)),
        ("non_external_needs_human_response", int(support_summary.get("non_external_needs_human_response") or 0), int(feedback_evidence.get("non_external_needs_human_response") or 0)),
        ("non_external_packets_without_named_owner", int(support_summary.get("non_external_packets_without_named_owner") or 0), int(feedback_evidence.get("non_external_packets_without_named_owner") or 0)),
        ("non_external_packets_without_lane", int(support_summary.get("non_external_packets_without_lane") or 0), int(feedback_evidence.get("non_external_packets_without_lane") or 0)),
        ("unresolved_external_proof_request_count", int(support_summary.get("unresolved_external_proof_request_count") or 0), int(feedback_evidence.get("unresolved_external_proof_request_count") or 0)),
    )
    for label, support_value, flagship_value in comparisons:
        if support_value != flagship_value:
            runtime_blockers.append(f"Support packet {label} drifted from flagship feedback-loop evidence ({support_value} != {flagship_value}).")

    weekly_pairs = (
        ("open_case_count", int(support_summary.get("open_case_count") or 0), int(weekly_closure.get("open_case_count") or 0)),
        ("waiting_closure_count", int(support_summary.get("closure_waiting_on_release_truth") or 0), int(weekly_closure.get("waiting_closure_count") or 0)),
        ("pending_human_response_count", int(support_summary.get("non_external_needs_human_response") or 0), int(weekly_closure.get("pending_human_response_count") or 0)),
        ("materialized_packet_count", int(support_summary.get("operator_packet_count") or 0), int(weekly_closure.get("materialized_packet_count") or 0)),
        ("design_impact_count", int(support_summary.get("design_impact_count") or 0), int(weekly_closure.get("design_impact_count") or 0)),
    )
    for label, support_value, weekly_value in weekly_pairs:
        if support_value != weekly_value:
            runtime_blockers.append(f"Weekly pulse closure_health {label} drifted from support packets ({weekly_value} != {support_value}).")

    threshold_hours = int(((feedback_evidence.get("thresholds") or {}).get("max_support_packet_age_hours")) or 24)
    support_age_seconds = _age_seconds(support_generated_at, now=now)
    if support_age_seconds is None:
        issues.append("Support packets generated_at is missing or invalid.")
    elif support_age_seconds > threshold_hours * 3600:
        runtime_blockers.append(
            f"Support packet freshness exceeded threshold ({support_age_seconds}s > {threshold_hours * 3600}s)."
        )

    refresh_mode = _normalize_text(support_source.get("refresh_mode")) or _normalize_text(feedback_evidence.get("support_source_refresh_mode"))
    refresh_error = _normalize_text(support_source.get("refresh_error"))
    source_mirror_generated_at = _normalize_text(support_source.get("source_mirror_generated_at"))
    if refresh_mode == "source_mirror_fallback":
        warning = "Support packets are running on source_mirror_fallback."
        if source_mirror_generated_at:
            warning += f" Mirror source generated_at={source_mirror_generated_at}."
        warnings.append(warning)
    if refresh_error:
        warnings.append(f"Support packet source refresh_error: {refresh_error}")

    return {
        "state": "pass" if not issues else "fail",
        "feedback_loop_status": feedback_status,
        "support_generated_at": support_generated_at,
        "support_generated_age_seconds": support_age_seconds,
        "support_source_refresh_mode": refresh_mode,
        "source_mirror_generated_at": source_mirror_generated_at,
        "weekly_closure_state": _normalize_text(weekly_closure.get("state")),
        "runtime_blockers": runtime_blockers,
        "warnings": warnings,
        "issues": issues,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    next90_guide_path: Path,
    localization_system_path: Path,
    telemetry_model_path: Path,
    telemetry_schema_path: Path,
    privacy_boundaries_path: Path,
    crash_reporting_path: Path,
    support_status_path: Path,
    flagship_readiness_path: Path,
    support_packets_path: Path,
    weekly_product_pulse_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    next90_guide = _read_text(next90_guide_path)
    localization_system = _read_text(localization_system_path)
    telemetry_model = _read_text(telemetry_model_path)
    telemetry_schema = _read_text(telemetry_schema_path)
    privacy_boundaries = _read_text(privacy_boundaries_path)
    crash_reporting = _read_text(crash_reporting_path)
    support_status = _read_text(support_status_path)
    flagship_readiness = _read_json(flagship_readiness_path)
    support_packets = _read_json(support_packets_path)
    weekly_product_pulse = _read_json(weekly_product_pulse_path)
    reference_now = _parse_iso_utc(generated_at) or dt.datetime.now(dt.timezone.utc)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    guide_monitor = _marker_monitor(next90_guide, GUIDE_MARKERS, label="Next90 guide canon")
    localization_marker_monitor = _marker_monitor(localization_system, LOCALIZATION_MARKERS, label="Localization canon")
    telemetry_model_monitor = _marker_monitor(telemetry_model, TELEMETRY_MODEL_MARKERS, label="Telemetry model canon")
    telemetry_schema_monitor = _marker_monitor(telemetry_schema, TELEMETRY_SCHEMA_MARKERS, label="Telemetry schema canon")
    privacy_monitor = _marker_monitor(privacy_boundaries, PRIVACY_MARKERS, label="Privacy canon")
    crash_reporting_monitor = _marker_monitor(crash_reporting, CRASH_REPORTING_MARKERS, label="Crash reporting canon")
    support_status_monitor = _marker_monitor(support_status, SUPPORT_STATUS_MARKERS, label="Support status canon")
    localization_runtime_monitor = _localization_runtime_monitor(localization_system, flagship_readiness)
    telemetry_posture_monitor = _telemetry_posture_monitor(telemetry_model, telemetry_schema, privacy_boundaries)
    retention_monitor = _retention_monitor(privacy_boundaries, crash_reporting, support_status)
    support_crash_runtime_monitor = _support_crash_runtime_monitor(
        flagship_readiness,
        support_packets,
        weekly_product_pulse,
        now=reference_now,
    )

    blockers: List[str] = []
    runtime_blockers: List[str] = []
    warnings: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("next90_guide", guide_monitor),
        ("localization_markers", localization_marker_monitor),
        ("telemetry_model_markers", telemetry_model_monitor),
        ("telemetry_schema_markers", telemetry_schema_monitor),
        ("privacy_markers", privacy_monitor),
        ("crash_reporting_markers", crash_reporting_monitor),
        ("support_status_markers", support_status_monitor),
        ("localization_runtime_monitor", localization_runtime_monitor),
        ("telemetry_posture_monitor", telemetry_posture_monitor),
        ("retention_monitor", retention_monitor),
        ("support_crash_runtime_monitor", support_crash_runtime_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")
        for runtime_blocker in section.get("runtime_blockers") or []:
            runtime_blockers.append(f"{section_name}: {runtime_blocker}")
        warnings.extend(section.get("warnings") or [])

    trust_plane_status = "blocked" if runtime_blockers else "warning" if warnings else "pass"
    closeout_warnings = list(runtime_blockers) + warnings

    return {
        "contract_name": "fleet.next90_m128_trust_plane_monitors",
        "generated_at": generated_at,
        "status": "pass" if not blockers else "blocked",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "canonical_alignment": canonical_alignment,
        "canonical_monitors": {
            "next90_guide": guide_monitor,
            "localization_markers": localization_marker_monitor,
            "telemetry_model_markers": telemetry_model_monitor,
            "telemetry_schema_markers": telemetry_schema_monitor,
            "privacy_markers": privacy_monitor,
            "crash_reporting_markers": crash_reporting_monitor,
            "support_status_markers": support_status_monitor,
        },
        "runtime_monitors": {
            "localization_runtime": localization_runtime_monitor,
            "telemetry_posture": telemetry_posture_monitor,
            "retention_alignment": retention_monitor,
            "support_and_crash_runtime": support_crash_runtime_monitor,
        },
        "monitor_summary": {
            "trust_plane_status": trust_plane_status,
            "runtime_blocker_count": len(runtime_blockers),
            "warning_count": len(warnings),
            "shipping_locale_count": len(localization_runtime_monitor.get("runtime_locales") or []),
            "support_generated_at": support_crash_runtime_monitor.get("support_generated_at"),
            "feedback_loop_status": support_crash_runtime_monitor.get("feedback_loop_status"),
            "runtime_blockers": runtime_blockers,
        },
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": closeout_warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "queue_staging": _source_link(queue_path, queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "next90_guide": _text_source_link(next90_guide_path),
            "localization_system": _text_source_link(localization_system_path),
            "telemetry_model": _text_source_link(telemetry_model_path),
            "telemetry_schema": _text_source_link(telemetry_schema_path),
            "privacy_boundaries": _text_source_link(privacy_boundaries_path),
            "crash_reporting": _text_source_link(crash_reporting_path),
            "support_status": _text_source_link(support_status_path),
            "flagship_readiness": _runtime_source_link(flagship_readiness_path),
            "support_packets": _runtime_source_link(support_packets_path),
            "weekly_product_pulse": _runtime_source_link(weekly_product_pulse_path),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    summary = dict(payload.get("monitor_summary") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M128 trust-plane monitors",
        "",
        f"- status: {payload.get('status')}",
        f"- trust_plane_status: {summary.get('trust_plane_status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Runtime summary",
        f"- feedback_loop_status: {summary.get('feedback_loop_status')}",
        f"- support_generated_at: {summary.get('support_generated_at')}",
        f"- runtime_blocker_count: {summary.get('runtime_blocker_count')}",
        f"- warning_count: {summary.get('warning_count')}",
        "",
        "## Package closeout",
        f"- state: {closeout.get('state') or 'blocked'}",
    ]
    if closeout.get("warnings"):
        lines.append("- warnings:")
        lines.extend([f"  - {warning}" for warning in closeout.get("warnings") or []])
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        queue_path=Path(args.queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        next90_guide_path=Path(args.next90_guide).resolve(),
        localization_system_path=Path(args.localization_system).resolve(),
        telemetry_model_path=Path(args.telemetry_model).resolve(),
        telemetry_schema_path=Path(args.telemetry_schema).resolve(),
        privacy_boundaries_path=Path(args.privacy_boundaries).resolve(),
        crash_reporting_path=Path(args.crash_reporting).resolve(),
        support_status_path=Path(args.support_status).resolve(),
        flagship_readiness_path=Path(args.flagship_readiness).resolve(),
        support_packets_path=Path(args.support_packets).resolve(),
        weekly_product_pulse_path=Path(args.weekly_product_pulse).resolve(),
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
