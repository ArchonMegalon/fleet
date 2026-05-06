#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

try:
    from scripts.next90_queue_staging import read_next90_queue_staging_yaml
except ModuleNotFoundError:
    from next90_queue_staging import read_next90_queue_staging_yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m120-fleet-launch-pulse"
FRONTIER_ID = 2614855152
MILESTONE_ID = 120
WORK_TASK_ID = "120.3"
WAVE_ID = "W14"
QUEUE_TITLE = "Compile launch pulse and adoption health into governor packets"
QUEUE_TASK = (
    "Produce launch pulse, adoption health, support risk, proof freshness, and public followthrough packets from "
    "governed release truth."
)
WORK_TASK_TITLE = "Compile launch pulse, adoption health, support risk, and proof freshness into governor-ready public status packets."
WORK_TASK_DEPENDENCIES = ["101", "106", "111", "116", "117", "119"]
OWNED_SURFACES = ["launch_pulse", "adoption_health:governor"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M120_FLEET_LAUNCH_PULSE.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M120_FLEET_LAUNCH_PULSE.generated.md"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
WEEKLY_GOVERNOR_PACKET = PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"
WEEKLY_PRODUCT_PULSE = PRODUCT_MIRROR / "WEEKLY_PRODUCT_PULSE.generated.json"
SUPPORT_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
PROGRESS_REPORT = PUBLISHED / "PROGRESS_REPORT.generated.json"
FLAGSHIP_PRODUCT_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
JOURNEY_GATES = PUBLISHED / "JOURNEY_GATES.generated.json"
PROOF_ORCHESTRATION = PUBLISHED / "PROOF_ORCHESTRATION.generated.json"
STATUS_PLANE = PUBLISHED / "STATUS_PLANE.generated.yaml"

SOURCE_AGE_LIMIT_SECONDS = {
    "weekly_governor_packet": 172800,
    "weekly_product_pulse": 172800,
    "support_packets": 172800,
    "progress_report": 172800,
    "flagship_readiness": 172800,
    "journey_gates": 172800,
    "proof_orchestration": 172800,
    "status_plane": 172800,
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the Fleet m120 launch pulse and governor-owned adoption/public followthrough packet."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--weekly-governor-packet", default=str(WEEKLY_GOVERNOR_PACKET))
    parser.add_argument("--weekly-product-pulse", default=str(WEEKLY_PRODUCT_PULSE))
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--progress-report", default=str(PROGRESS_REPORT))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_PRODUCT_READINESS))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    parser.add_argument("--proof-orchestration", default=str(PROOF_ORCHESTRATION))
    parser.add_argument("--status-plane", default=str(STATUS_PLANE))
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
        if path.name.endswith("NEXT_90_DAY_QUEUE_STAGING.generated.yaml"):
            payload = read_next90_queue_staging_yaml(path)
        else:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_iso_utc(value: Any) -> dt.datetime | None:
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _age_seconds(generated_at: str) -> int | None:
    dt_at = _parse_iso_utc(generated_at)
    if not dt_at:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    return int((now - dt_at.astimezone(dt.timezone.utc)).total_seconds())


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


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    if _normalize_text(queue.get("package_id")) == package_id:
        return dict(queue)
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
    }
    for field, expected_value in expected.items():
        queue_value = _normalize_text(queue_item.get(field)) if queue_item else ""
        design_value = _normalize_text(design_queue_item.get(field)) if design_queue_item else ""
        expected_text = _normalize_text(expected_value)
        if queue_value != expected_text and queue_item:
            issues.append(f"Fleet queue {field} drifted.")
        if design_value != expected_text and design_queue_item:
            issues.append(f"Design queue {field} drifted.")

    if queue_item and _normalize_list(queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Fleet queue allowed_paths drifted.")
    if queue_item and _normalize_list(queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Fleet queue owned_surfaces drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Design queue allowed_paths drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Design queue owned_surfaces drifted.")
    if work_task:
        if _normalize_text(work_task.get("owner")) != "fleet":
            issues.append("Canonical registry work task owner drifted.")
        if _normalize_text(work_task.get("title")) != WORK_TASK_TITLE:
            issues.append("Canonical registry work task title drifted.")
    if milestone and _normalize_list(milestone.get("dependencies") or []) != WORK_TASK_DEPENDENCIES:
        issues.append("Canonical registry milestone dependencies drifted from m120 requirement set.")

    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")) if queue_item else "",
        "design_queue_status": _normalize_text(design_queue_item.get("status")) if design_queue_item else "",
        "registry_status": _normalize_text(milestone.get("status")) if milestone else "",
        "work_task_status": _normalize_text(work_task.get("status")) if work_task else "",
        "work_task_title": _normalize_text(work_task.get("title")) if work_task else "",
        "queue_completion_action": _normalize_text(queue_item.get("completion_action")) if queue_item else "",
        "design_queue_completion_action": _normalize_text(design_queue_item.get("completion_action")) if design_queue_item else "",
    }


def _truth_texts(weekly_governor_packet: Dict[str, Any], weekly_product_pulse: Dict[str, Any]) -> Dict[str, Any]:
    decision_alignment = dict(weekly_governor_packet.get("decision_alignment") or {})
    governor_decisions = list(weekly_governor_packet.get("governor_decisions") or [])
    pulse_decisions = list(weekly_product_pulse.get("governor_decisions") or [])

    pulse_launch_rows = [
        dict(row)
        for row in pulse_decisions
        if isinstance(row, dict) and _normalize_text(row.get("action")) in {"launch_expand", "freeze_launch"}
    ]
    pulse_launch_row = pulse_launch_rows[0] if pulse_launch_rows else {}
    governor_launch = _normalize_text(
        next((str(row.get("action") or "") for row in governor_decisions if _normalize_text(row.get("state")) in {"active", "allowed"}), "")
    )
    if not governor_launch:
        governor_launch = _normalize_text(weekly_governor_packet.get("decision_board", {}).get("current_launch_action"))
    if not governor_launch:
        governor_launch = _normalize_text(decision_alignment.get("actual_action"))

    pulse_action = _normalize_text(pulse_launch_row.get("action"))
    alignment_ok = (
        bool(governor_launch)
        and bool(pulse_action)
        and governor_launch == pulse_action
        and _normalize_text(decision_alignment.get("status")) == "pass"
        and _normalize_text(decision_alignment.get("expected_action")) == governor_launch
    )

    pulse_launch_reasons: List[str] = []
    if _normalize_text(pulse_launch_row.get("reason")):
        pulse_launch_reasons.append(_normalize_text(pulse_launch_row.get("reason")))
    pulse_launch_reasons.extend(_normalize_list(pulse_launch_row.get("cited_signals")))

    launch_gate_ledger = dict(weekly_governor_packet.get("decision_gate_ledger") or {})
    freeze_gate_rows = launch_gate_ledger.get("freeze_launch") if isinstance(launch_gate_ledger.get("freeze_launch"), list) else []
    launch_expand_rows = launch_gate_ledger.get("launch_expand") if isinstance(launch_gate_ledger.get("launch_expand"), list) else []

    focus_shift_reason = _normalize_text((weekly_governor_packet.get("decision_board") or {}).get("focus_shift", {}).get("reason"))
    public_status_copy = dict(weekly_governor_packet.get("public_status_copy") or {})

    return {
        "decision_alignment": {
            "actual_action": _normalize_text(decision_alignment.get("actual_action")),
            "expected_action": _normalize_text(decision_alignment.get("expected_action")),
            "status": _normalize_text(decision_alignment.get("status")),
        },
        "alignment_ok": alignment_ok,
        "governor_launch_action": governor_launch,
        "pulse_launch_action": pulse_action,
        "pulse_launch_reason": _normalize_text(pulse_launch_row.get("reason")),
        "pulse_governor_reasons": pulse_launch_reasons,
        "focus_shift_reason": focus_shift_reason,
        "freeze_gate_state": _normalize_text((freeze_gate_rows[0] if freeze_gate_rows else {}).get("state")),
        "launch_expand_gate_state": _normalize_text((launch_expand_rows[0] if launch_expand_rows else {}).get("state")),
        "public_status_copy": public_status_copy,
    }


def _support_risk(source: Dict[str, Any]) -> Dict[str, Any]:
    summary = dict(source.get("summary") or {})
    open_case_count = int(summary.get("open_packet_count") or 0)
    human = int(summary.get("needs_human_response") or 0)
    update_required = int(summary.get("update_required_case_count") or 0)
    closure_waiting = int(summary.get("closure_waiting_on_release_truth") or 0)
    support_pack_count = len(list(source.get("packets") or []))

    if open_case_count == 0 and human == 0 and update_required == 0 and closure_waiting == 0:
        state = "low"
        summary_text = "Support followthrough pressure is currently low."
    elif open_case_count > 0 or human > 0:
        state = "high"
        summary_text = "Support followthrough still has open cases and operator-facing support risk."
    else:
        state = "watch"
        summary_text = "Support followthrough risk is non-blocking but should be monitored until all closure counters clear."
    return {
        "state": state,
        "summary": summary_text,
        "counts": {
            "open_packet_count": open_case_count,
            "needs_human_response": human,
            "update_required_case_count": update_required,
            "closure_waiting_on_release_truth": closure_waiting,
            "packet_count": support_pack_count,
        },
    }


def _adoption_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    supporting = dict(payload.get("supporting_signals") or {})
    row = dict(supporting.get("adoption_health") or {})
    state = _normalize_text(row.get("state") or row.get("status") or "unknown").lower()
    if not state:
        state = "unknown"
    if state == "clear":
        gate_state = "pass"
        summary = _normalize_text(row.get("summary") or "Adoption health is clear.")
    elif state in {"clear_with_watch", "watch", "moving"}:
        gate_state = "watch"
        summary = _normalize_text(row.get("summary") or "Adoption-health indicators are not fully stable yet.")
    else:
        gate_state = "blocked"
        summary = _normalize_text(row.get("summary") or "Adoption-health source is missing or not currently aligned to release truth.")

    return {
        "state": gate_state,
        "raw_state": state,
        "summary": summary,
        "source": {
            "local_release_proof_status": _normalize_text(row.get("local_release_proof_status")),
            "proven_journey_count": int(row.get("proven_journey_count") or 0),
            "proven_route_count": int(row.get("proven_route_count") or 0),
            "history_snapshot_count": int(row.get("history_snapshot_count") or 0),
            "successor_dependency_summary": dict(payload.get("supporting_signals", {}).get("successor_dependency_posture") or {}),
        },
        "pulse_as_of": _normalize_text(payload.get("as_of")),
    }


def _proof_freshness(rows: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    missing = 0
    stale = 0
    for name, row in rows.items():
        status = _normalize_text(row.get("status"))
        if status in {"missing", "future"}:
            missing += 1
        elif status == "stale":
            stale += 1

    if missing or stale:
        overall = "blocked"
    else:
        overall = "pass"
    return {
        "state": overall,
        "missing_input_count": missing,
        "stale_input_count": stale,
        "source_rows": rows,
    }


def _source_rows(paths: Dict[str, Path], payloads: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for name, path in paths.items():
        payload = payloads.get(name) or {}
        row: Dict[str, Any] = {
            "path": _display_path(path),
            "exists": path.is_file(),
        }
        generated_at = _normalize_text(payload.get("generated_at"))
        row["generated_at"] = generated_at
        row["generated_at_sha256"] = _sha256_text(generated_at + name)
        if row["exists"]:
            row["sha256"] = _sha256_file(path)
            row["max_age_seconds"] = SOURCE_AGE_LIMIT_SECONDS.get(name)
            age = _age_seconds(generated_at)
            row["age_seconds"] = age if age is not None else -1
            if age is None:
                row["status"] = "missing"
            elif age < 0:
                row["status"] = "future"
            elif age > int(row["max_age_seconds"]):
                row["status"] = "stale"
            else:
                row["status"] = "pass"
        else:
            row["sha256"] = ""
            row["max_age_seconds"] = SOURCE_AGE_LIMIT_SECONDS.get(name)
            row["age_seconds"] = None
            row["status"] = "missing"
        if row["status"] == "pass":
            row["state"] = "pass"
        elif row["status"] == "missing":
            row["state"] = "blocked"
        else:
            row["state"] = "watch"
        rows[name] = row
    return rows


def _public_followthrough(payloads: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    progress = dict(payloads.get("progress_report") or {})
    flagship = dict(payloads.get("flagship_readiness") or {})
    journey = dict(payloads.get("journey_gates") or {})
    status_plane = dict(payloads.get("status_plane") or {})

    progress_overall = _normalize_text(
        progress.get("overall_status")
        or progress.get("status")
        or progress.get("overall_report_status")
        or progress.get("contract_name")
    )
    progress_ready = progress_overall in {"complete", "pass", "ready"}
    flagship_pass = _normalize_text(flagship.get("status")) == "pass"
    journey_ready = _normalize_text(dict(journey.get("summary") or {}).get("overall_state")) == "ready"
    final_claim = _normalize_text(status_plane.get("whole_product_final_claim_status")) == "pass"

    state = "pass" if progress_ready and flagship_pass and final_claim else "watch"
    if not progress_ready:
        state = "blocked"

    reasons: List[str] = []
    if not progress_ready:
        reasons.append("Progress report is not complete.")
    if not flagship_pass:
        reasons.append("Flagship readiness packet is not pass.")
    if not journey_ready:
        reasons.append("Journey gates are not ready.")
    if not final_claim:
        reasons.append("Status-plane final claim is not pass.")

    return {
        "state": state,
        "summary": "; ".join(reasons) or "Public followthrough inputs are aligned for governor-facing operator packaging.",
        "progress_report": {
            "overall_status": progress_overall,
            "percent_complete": progress.get("percent_complete"),
            "momentum": dict(progress.get("momentum") or {}),
            "top_risks": progress.get("top_risks") or [],
        },
        "flagship_readiness_status": _normalize_text(flagship.get("status")),
        "journey_gates_overall_state": _normalize_text(dict(journey.get("summary") or {}).get("overall_state")),
        "final_claim_state": _normalize_text(status_plane.get("whole_product_final_claim_status")),
        "public_followthrough_reasons": reasons,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    weekly_governor_packet_path: Path,
    weekly_product_pulse_path: Path,
    support_packets_path: Path,
    progress_report_path: Path,
    flagship_readiness_path: Path,
    journey_gates_path: Path,
    proof_orchestration_path: Path,
    status_plane_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    weekly_governor_packet = _read_json(weekly_governor_packet_path)
    weekly_product_pulse = _read_json(weekly_product_pulse_path)
    support_packets = _read_json(support_packets_path)
    progress_report = _read_json(progress_report_path)
    flagship_readiness = _read_json(flagship_readiness_path)
    journey_gates = _read_json(journey_gates_path)
    proof_orchestration = _read_json(proof_orchestration_path)
    status_plane = _read_yaml(status_plane_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)
    queue_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)

    payloads: Dict[str, Dict[str, Any]] = {
        "weekly_governor_packet": weekly_governor_packet,
        "weekly_product_pulse": weekly_product_pulse,
        "support_packets": support_packets,
        "progress_report": progress_report,
        "flagship_readiness": flagship_readiness,
        "journey_gates": journey_gates,
        "proof_orchestration": proof_orchestration,
        "status_plane": status_plane,
    }
    source_paths = {
        "weekly_governor_packet": weekly_governor_packet_path,
        "weekly_product_pulse": weekly_product_pulse_path,
        "support_packets": support_packets_path,
        "progress_report": progress_report_path,
        "flagship_readiness": flagship_readiness_path,
        "journey_gates": journey_gates_path,
        "proof_orchestration": proof_orchestration_path,
        "status_plane": status_plane_path,
    }
    source_input_rows = _source_rows(source_paths, payloads)
    proof_freshness = _proof_freshness(source_input_rows)

    launch_truth = _truth_texts(weekly_governor_packet, weekly_product_pulse)
    adoption = _adoption_health(weekly_product_pulse)
    support_risk_state = _support_risk(support_packets)
    followthrough = _public_followthrough(payloads)

    launch_pulse = {
        "state": "pass" if launch_truth["alignment_ok"] and launch_truth["decision_alignment"]["status"] == "pass" else "watch",
        "alignment_ok": launch_truth["alignment_ok"],
        "governor_action": launch_truth["governor_launch_action"],
        "pulse_action": launch_truth["pulse_launch_action"],
        "decision_alignment": launch_truth["decision_alignment"],
        "focus_shift_reason": launch_truth["focus_shift_reason"],
        "public_status_copy_state": _normalize_text((launch_truth["public_status_copy"] or {}).get("state")),
        "public_status_headline": _normalize_text((launch_truth["public_status_copy"] or {}).get("headline")),
        "public_status_body": _normalize_text((launch_truth["public_status_copy"] or {}).get("body")),
    }

    blocked = any(
        (
            queue_alignment["state"] != "pass",
            launch_pulse["state"] != "pass",
            adoption["state"] == "blocked",
            support_risk_state["state"] == "high",
            proof_freshness["state"] == "blocked",
            followthrough["state"] == "blocked",
        )
    )

    status = "blocked" if blocked else "pass"

    next_actions: List[str] = []
    if queue_alignment["state"] != "pass":
        next_actions.append("Repair queue and registry scope drift for next90-m120-fleet-launch-pulse before trusting this packet.")
    if launch_pulse["state"] != "pass":
        next_actions.append("Align weekly pulse launch action, governor launch action, and launch board evidence before promoting launch posture.")
    if adoption["state"] in {"watch", "blocked"}:
        next_actions.append("Stabilize adoption-health signals in weekly product pulse before promoting launch-facing copy and proof claims.")
    if support_risk_state["state"] in {"watch", "high"}:
        next_actions.append("Reduce support risk counters before treating launch followthrough packets as fully stable.")
    if proof_freshness["state"] != "pass":
        next_actions.append("Refresh stale or missing source proofs used by launch pulse and adoption compilation.")
    if followthrough["state"] in {"watch", "blocked"}:
        next_actions.append("Reconcile progress/flagship/journey/public-final-claim posture before final operator-facing public followthrough claims.")
    if not next_actions:
        next_actions.append("Keep packet fresh from governed source truth and raise only when source truth drifts.")

    return {
        "generated_at": generated_at or _utc_now(),
        "contract_name": "fleet.next90_m120_launch_pulse",
        "status": status,
        "status_reason": "All sources are aligned and governed from release truth."
        if status == "pass"
        else "Source alignment, launch action alignment, adoption health, support risk, freshness, or followthrough signals are not currently stable.",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave_id": WAVE_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "as_of": _normalize_text(weekly_governor_packet.get("as_of") or weekly_product_pulse.get("as_of"))
        or _normalize_text(progress_report.get("as_of") or support_packets.get("generated_at"))
        or _utc_now(),
        "agreement": {
            "queue_scope_matches_package": queue_alignment["state"] == "pass",
            "registry_scope_matches_package": queue_alignment["state"] == "pass",
            "fleet_queue_status": queue_alignment["fleet_queue_status"],
            "design_queue_status": queue_alignment["design_queue_status"],
            "registry_status": queue_alignment["registry_status"],
            "work_task_status": queue_alignment["work_task_status"],
            "registry_work_task_title": queue_alignment["work_task_title"],
            "queue_closure_matches_package": (
                _normalize_text(queue_alignment["queue_completion_action"]) == _normalize_text(work_task.get("completion_action", ""))
                if queue_alignment["queue_completion_action"] or work_task.get("completion_action")
                else True
            ),
            "registry_closure_matches_package": (
                _normalize_text(queue_alignment["design_queue_completion_action"]) == _normalize_text(work_task.get("completion_action", ""))
                if queue_alignment["design_queue_completion_action"] or work_task.get("completion_action")
                else True
            ),
        },
        "launch_pulse": launch_pulse,
        "adoption_health": adoption,
        "support_risk": support_risk_state,
        "proof_freshness": proof_freshness,
        "public_followthrough": followthrough,
        "source_packet_links": {
            "weekly_governor_packet": {
                "contract_name": _normalize_text(weekly_governor_packet.get("contract_name")),
                "path": _display_path(weekly_governor_packet_path),
                "current_launch_action": launch_truth["governor_launch_action"],
            },
            "weekly_product_pulse": {
                "contract_name": _normalize_text(weekly_product_pulse.get("contract_name")),
                "path": _display_path(weekly_product_pulse_path),
                "as_of": _normalize_text(weekly_product_pulse.get("as_of")),
                "pulse_action": launch_truth["pulse_launch_action"],
            },
            "support_case_packets": {
                "contract_name": _normalize_text(support_packets.get("contract_name")),
                "path": _display_path(support_packets_path),
                "successor_package_verification": dict(support_packets.get("successor_package_verification") or {}),
            },
            "flagship_readiness": {
                "path": _display_path(flagship_readiness_path),
                "status": _normalize_text(flagship_readiness.get("status")),
                "scoped_status": _normalize_text(flagship_readiness.get("scoped_status")),
            },
        },
        "source_inputs": {
            "weekly_governor_packet": _display_path(weekly_governor_packet_path),
            "weekly_product_pulse": _display_path(weekly_product_pulse_path),
            "support_packets": _display_path(support_packets_path),
            "progress_report": _display_path(progress_report_path),
            "flagship_readiness": _display_path(flagship_readiness_path),
            "journey_gates": _display_path(journey_gates_path),
            "proof_orchestration": _display_path(proof_orchestration_path),
            "status_plane": _display_path(status_plane_path),
            "registry": _display_path(registry_path),
            "queue_staging": _display_path(queue_path),
            "design_queue_staging": _display_path(design_queue_path),
            "successor_frontier_id": FRONTIER_ID,
        },
        "source_input_health": source_input_rows,
        "next_actions": next_actions,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    launch = dict(payload.get("launch_pulse") or {})
    adoption = dict(payload.get("adoption_health") or {})
    support = dict(payload.get("support_risk") or {})
    freshness = dict(payload.get("proof_freshness") or {})
    followthrough = dict(payload.get("public_followthrough") or {})
    agreement = dict(payload.get("agreement") or {})

    return "\n".join(
        [
            "# Fleet M120 launch-pulse and governor followthrough packet",
            "",
            f"- Generated at: `{payload.get('generated_at')}`",
            f"- Status: `{payload.get('status')}`",
            f"- Status reason: {payload.get('status_reason')}",
            f"- As of: `{payload.get('as_of')}`",
            f"- Queue scope aligned: `{agreement.get('queue_scope_matches_package')}`",
            f"- Registry scope aligned: `{agreement.get('registry_scope_matches_package')}`",
            f"- Launch action match: `{launch.get('alignment_ok')}`",
            f"- Governor launch action: `{launch.get('governor_action')}`",
            f"- Pulse launch action: `{launch.get('pulse_action')}`",
            f"- Launch state: `{launch.get('state')}`",
            f"- Adoption health: `{adoption.get('state')}` ({adoption.get('raw_state')})",
            f"- Support risk: `{support.get('state')}`",
            f"- Proof freshness: `{freshness.get('state')}`",
            f"- Public followthrough: `{followthrough.get('state')}`",
            "",
            "## Next actions",
            *[f"- {item}" for item in (payload.get("next_actions") or [])],
            "",
        ]
    ) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        registry_path=Path(args.successor_registry),
        queue_path=Path(args.queue_staging),
        design_queue_path=Path(args.design_queue_staging),
        weekly_governor_packet_path=Path(args.weekly_governor_packet),
        weekly_product_pulse_path=Path(args.weekly_product_pulse),
        support_packets_path=Path(args.support_packets),
        progress_report_path=Path(args.progress_report),
        flagship_readiness_path=Path(args.flagship_readiness),
        journey_gates_path=Path(args.journey_gates),
        proof_orchestration_path=Path(args.proof_orchestration),
        status_plane_path=Path(args.status_plane),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown_output = Path(args.markdown_output)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")
    print(f"wrote m120 launch pulse packet: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
