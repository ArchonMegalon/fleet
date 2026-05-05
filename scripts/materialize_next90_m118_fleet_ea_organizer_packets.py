#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import yaml


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"

PACKAGE_ID = "next90-m118-fleet-ea-organizer-packets"
QUEUE_TITLE = "Compile organizer health and publication readiness packets"
QUEUE_TASK = "Add fleet and EA operator-loop packets for organizer health, event prep, support risk, and publication readiness."
WORK_TASK_ID = "118.4"
MILESTONE_ID = 118
FRONTIER_ID = 4199699036
WAVE_ID = "W13"
OWNED_SURFACES = ["organizer_health_packets", "publication_readiness:operator"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]
EXPECTED_COMPLETION_ACTION = "verify_closed_package_only"
EXPECTED_DO_NOT_REOPEN_REASON = (
    "M118 Fleet organizer operator packets are complete; future shards must verify the organizer operator packet receipt, "
    "standalone verifier, registry row, queue row, and design queue row instead of reopening the organizer health and "
    "publication readiness packet slice."
)

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M118_FLEET_EA_ORGANIZER_PACKETS.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M118_FLEET_EA_ORGANIZER_PACKETS.generated.md"
SUCCESSOR_REGISTRY = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml")
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
WEEKLY_GOVERNOR_PACKET = PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"
SUPPORT_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
HUB_LOCAL_RELEASE_PROOF = Path("/docker/chummercomplete/chummer6-hub/.codex-studio/published/HUB_LOCAL_RELEASE_PROOF.generated.json")
HUB_ORGANIZER_VERIFIER = Path("/docker/chummercomplete/chummer.run-services/scripts/verify_next90_m118_hub_organizer_ops.py")
HUB_CREATOR_PUBLICATION_VERIFIER = Path("/docker/chummercomplete/chummer.run-services/scripts/verify_next90_m116_hub_creator_publication.py")
EA_OPERATOR_SAFE_PACK = Path("/docker/EA/docs/chummer_operator_safe_packets/CHUMMER_OPERATOR_SAFE_PACKET_PACK.yaml")
EA_ORGANIZER_PACKET_PACK = Path("/docker/EA/docs/chummer_organizer_packets/CHUMMER_ORGANIZER_PACKET_PACK.yaml")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize Fleet M118 organizer health and publication readiness packets.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--weekly-governor-packet", default=str(WEEKLY_GOVERNOR_PACKET))
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--hub-local-release-proof", default=str(HUB_LOCAL_RELEASE_PROOF))
    parser.add_argument("--hub-organizer-verifier", default=str(HUB_ORGANIZER_VERIFIER))
    parser.add_argument("--hub-creator-publication-verifier", default=str(HUB_CREATOR_PUBLICATION_VERIFIER))
    parser.add_argument("--ea-operator-safe-pack", default=str(EA_OPERATOR_SAFE_PACK))
    parser.add_argument("--ea-organizer-packet-pack", default=str(EA_ORGANIZER_PACKET_PACK))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [_normalize_text(item) for item in value if _normalize_text(item)]


def _unique_strings(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        normalized = _normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


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


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _is_freeze_publication_posture(decision_alignment: Dict[str, Any], public_status_copy: Dict[str, Any]) -> bool:
    action = _normalize_text(decision_alignment.get("actual_action"))
    public_state = _normalize_text(public_status_copy.get("state"))
    return action.startswith("freeze_") or public_state.startswith("freeze_")


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for item in queue.get("items") or []:
        if isinstance(item, dict) and _normalize_text(item.get("package_id")) == package_id:
            return dict(item)
    return {}


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for milestone in registry.get("milestones") or []:
        if isinstance(milestone, dict) and int(milestone.get("id") or 0) == milestone_id:
            return dict(milestone)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for item in milestone.get("work_tasks") or []:
        if isinstance(item, dict) and _normalize_text(item.get("id")) == work_task_id:
            return dict(item)
    return {}


def _pack_contract_status(
    path: Path,
    *,
    expected_package_id: str,
    expected_milestone_id: int,
    required_surfaces: List[str],
    contract_prefix: str,
    required_sections: List[str],
) -> Dict[str, Any]:
    result = {
        "path": str(path),
        "exists": path.is_file(),
        "state": "blocked",
        "issues": [],
        "summary": "",
    }
    if not path.is_file():
        result["summary"] = "Packet contract file is missing."
        return result

    payload = _read_yaml(path)
    issues: List[str] = []
    if not payload:
        issues.append("packet YAML is missing or invalid")
    if _normalize_text(payload.get("package_id")) != expected_package_id:
        issues.append("package_id drifted")
    if int(payload.get("milestone_id") or 0) != expected_milestone_id:
        issues.append("milestone_id drifted")
    contract_name = _normalize_text(payload.get("contract_name"))
    if not contract_name.startswith(contract_prefix):
        issues.append("contract_name drifted")
    owned_surfaces = _normalize_list(payload.get("owned_surfaces"))
    for surface in required_surfaces:
        if surface not in owned_surfaces:
            issues.append(f"owned_surfaces missing {surface}")
    for section in required_sections:
        if not isinstance(payload.get(section), dict):
            issues.append(f"{section} section is missing")

    result["issues"] = issues
    result["state"] = "ready" if not issues else "blocked"
    result["summary"] = (
        "Packet contract is present and shape-valid."
        if not issues
        else "Packet contract is incomplete or drifted: " + "; ".join(issues) + "."
    )
    return result


def _run_verifier(path: Path) -> Dict[str, Any]:
    result = {
        "path": str(path),
        "exists": path.is_file(),
        "status": "missing",
        "exit_code": None,
        "summary": "",
    }
    if not path.is_file():
        result["summary"] = "Verifier script is missing."
        return result
    completed = subprocess.run(
        ["python3", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    result["exit_code"] = completed.returncode
    result["summary"] = (completed.stdout or completed.stderr).strip()
    result["status"] = "pass" if completed.returncode == 0 else "fail"
    return result


def _support_risk(summary: Dict[str, Any]) -> Dict[str, Any]:
    open_packets = int(summary.get("open_packet_count") or 0)
    human = int(summary.get("needs_human_response") or 0)
    update_required = int(summary.get("update_required_case_count") or 0)
    closure_waiting = int(summary.get("closure_waiting_on_release_truth") or 0)
    if open_packets == 0 and human == 0 and update_required == 0 and closure_waiting == 0:
        return {
            "state": "low",
            "summary": "No live support-case packet pressure is currently blocking organizer or publication operator work.",
            "counts": {
                "open_packet_count": open_packets,
                "needs_human_response": human,
                "update_required_case_count": update_required,
                "closure_waiting_on_release_truth": closure_waiting,
            },
        }
    risk = "high" if human or update_required else "watch"
    return {
        "state": risk,
        "summary": (
            "Support followthrough still has live packet pressure; organizer publication promotion should stay on hold until the same install-aware support truth clears."
        ),
        "counts": {
            "open_packet_count": open_packets,
            "needs_human_response": human,
            "update_required_case_count": update_required,
            "closure_waiting_on_release_truth": closure_waiting,
        },
    }


def _queue_alignment(queue_item: Dict[str, Any], design_queue_item: Dict[str, Any], work_task: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    if not queue_item:
        issues.append("Fleet queue row is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    expected_fields = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TASK,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "repo": "fleet",
    }
    for field_name, expected in expected_fields.items():
        queue_value = _normalize_text(queue_item.get(field_name)) if queue_item else ""
        design_queue_value = _normalize_text(design_queue_item.get(field_name)) if design_queue_item else ""
        expected_value = _normalize_text(expected)
        if queue_item and queue_value != expected_value:
            issues.append(f"Fleet queue {field_name} drifted.")
        if design_queue_item and design_queue_value != expected_value:
            issues.append(f"Design queue {field_name} drifted.")
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
            issues.append("Registry owner drifted from Fleet.")
        if _normalize_text(work_task.get("title")) != "Add operator-loop checks for organizer health, support risk, and publication readiness.":
            issues.append("Registry work-task title drifted.")
    queue_status = _normalize_text(queue_item.get("status"))
    design_queue_status = _normalize_text(design_queue_item.get("status"))
    registry_status = _normalize_text(work_task.get("status"))
    queue_completion_action = _normalize_text(queue_item.get("completion_action"))
    design_queue_completion_action = _normalize_text(design_queue_item.get("completion_action"))
    registry_completion_action = _normalize_text(work_task.get("completion_action"))
    queue_do_not_reopen_reason = _normalize_text(queue_item.get("do_not_reopen_reason"))
    design_queue_do_not_reopen_reason = _normalize_text(design_queue_item.get("do_not_reopen_reason"))
    registry_do_not_reopen_reason = _normalize_text(work_task.get("do_not_reopen_reason"))
    closed_anywhere = any(status == "complete" for status in (queue_status, design_queue_status, registry_status))
    if closed_anywhere:
        if queue_status != "complete":
            issues.append("Fleet queue status drifted from completed package closure.")
        if design_queue_status != "complete":
            issues.append("Design queue status drifted from completed package closure.")
        if registry_status != "complete":
            issues.append("Registry work-task status drifted from completed package closure.")
        if queue_completion_action != EXPECTED_COMPLETION_ACTION:
            issues.append("Fleet queue completion_action drifted from completed package closure.")
        if design_queue_completion_action != EXPECTED_COMPLETION_ACTION:
            issues.append("Design queue completion_action drifted from completed package closure.")
        if registry_completion_action != EXPECTED_COMPLETION_ACTION:
            issues.append("Registry work-task completion_action drifted from completed package closure.")
        if queue_do_not_reopen_reason != EXPECTED_DO_NOT_REOPEN_REASON:
            issues.append("Fleet queue do_not_reopen_reason drifted from completed package closure.")
        if design_queue_do_not_reopen_reason != EXPECTED_DO_NOT_REOPEN_REASON:
            issues.append("Design queue do_not_reopen_reason drifted from completed package closure.")
        if registry_do_not_reopen_reason != EXPECTED_DO_NOT_REOPEN_REASON:
            issues.append("Registry work-task do_not_reopen_reason drifted from completed package closure.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": queue_status,
        "design_queue_status": design_queue_status,
        "registry_work_task_status": registry_status,
        "closed_anywhere": closed_anywhere,
        "expected_completion_action": EXPECTED_COMPLETION_ACTION if closed_anywhere else "",
        "expected_do_not_reopen_reason": EXPECTED_DO_NOT_REOPEN_REASON if closed_anywhere else "",
        "queue_completion_action": queue_completion_action,
        "design_queue_completion_action": design_queue_completion_action,
        "registry_work_task_completion_action": registry_completion_action,
        "queue_do_not_reopen_reason": queue_do_not_reopen_reason,
        "design_queue_do_not_reopen_reason": design_queue_do_not_reopen_reason,
        "registry_work_task_do_not_reopen_reason": registry_do_not_reopen_reason,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    weekly_governor_packet_path: Path,
    support_packets_path: Path,
    hub_local_release_proof_path: Path,
    hub_organizer_verifier_path: Path,
    hub_creator_publication_verifier_path: Path,
    ea_operator_safe_pack_path: Path,
    ea_organizer_packet_pack_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    weekly_governor = _read_json(weekly_governor_packet_path)
    support_packets = _read_json(support_packets_path)
    hub_proof = _read_json(hub_local_release_proof_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)
    queue_alignment = _queue_alignment(queue_item, design_queue_item, work_task)

    organizer_verifier = _run_verifier(hub_organizer_verifier_path)
    creator_verifier = _run_verifier(hub_creator_publication_verifier_path)

    hub_packages = dict(hub_proof.get("successor_queue_packages_by_id") or {})
    hub_receipts = list(hub_proof.get("proof_receipts") or [])
    artifact_shelf_package = dict(hub_packages.get("next90-m117-hub-artifact-shelf-v2") or {})
    artifact_shelf_receipt = next(
        (receipt for receipt in hub_receipts if isinstance(receipt, dict) and _normalize_text(receipt.get("receipt_id")) == "artifact_shelf:v2"),
        {},
    )
    artifact_shelf_filters_receipt = next(
        (receipt for receipt in hub_receipts if isinstance(receipt, dict) and _normalize_text(receipt.get("receipt_id")) == "artifact_audience_filters"),
        {},
    )
    publication_receipts_present = bool(artifact_shelf_receipt) and bool(artifact_shelf_filters_receipt)

    support_summary = dict(support_packets.get("summary") or {})
    weekly_decision_alignment = dict(weekly_governor.get("decision_alignment") or {})
    public_status_copy = dict(weekly_governor.get("public_status_copy") or {})
    support_risk = _support_risk(support_summary)
    support_followthrough_gates = dict(support_packets.get("followthrough_receipt_gates") or {})
    support_packet_ids = _unique_strings(
        [
            _normalize_text(packet.get("packet_id") or packet.get("id"))
            for packet in support_packets.get("packets") or []
            if isinstance(packet, dict)
        ]
    )
    artifact_receipt_ids = _unique_strings(
        [
            _normalize_text(artifact_shelf_receipt.get("receipt_id")),
            _normalize_text(artifact_shelf_filters_receipt.get("receipt_id")),
        ]
    )
    artifact_receipt_package_ids = _unique_strings(
        [
            _normalize_text(artifact_shelf_package.get("package_id")),
            _normalize_text(artifact_shelf_receipt.get("package_id")),
            _normalize_text(artifact_shelf_filters_receipt.get("package_id")),
        ]
    )

    ea_operator_safe_pack = _pack_contract_status(
        ea_operator_safe_pack_path,
        expected_package_id="next90-m113-executive-assistant-operator-safe-packets",
        expected_milestone_id=113,
        required_surfaces=["gm_prep_packets", "roster_movement_followthrough"],
        contract_prefix="ea.chummer_operator_safe",
        required_sections=["governed_truth_bundle", "proof_guardrails", "packet_families"],
    )
    ea_organizer_pack = _pack_contract_status(
        ea_organizer_packet_pack_path,
        expected_package_id="next90-m118-ea-organizer-followthrough",
        expected_milestone_id=118,
        required_surfaces=["organizer_followthrough:ea", "event_prep_packets"],
        contract_prefix="ea.chummer_organizer",
        required_sections=["source_truth", "proof_guardrails", "packet_families"],
    )
    ea_event_prep_state = "ready" if ea_organizer_pack["state"] == "ready" else "blocked"

    organizer_health = {
        "state": (
            "pass"
            if queue_alignment["state"] == "pass"
            and organizer_verifier["status"] == "pass"
            and creator_verifier["status"] == "pass"
            and publication_receipts_present
            and ea_operator_safe_pack["state"] == "ready"
            and ea_event_prep_state == "ready"
            else "blocked"
        ),
        "queue_alignment": queue_alignment,
        "hub_organizer_ops": organizer_verifier,
        "hub_creator_publication": creator_verifier,
        "artifact_shelf_publication_surface": {
            "state": "pass" if publication_receipts_present else "blocked",
            "package_status": _normalize_text(artifact_shelf_package.get("status")) or "missing",
            "receipt_summary": _normalize_text(artifact_shelf_receipt.get("summary")),
            "filter_receipt_present": bool(artifact_shelf_filters_receipt),
            "summary": (
                "Hub artifact shelf and audience-filter receipts are both present."
                if publication_receipts_present
                else (
                    "Hub artifact shelf receipt is missing."
                    if not artifact_shelf_receipt
                    else "Hub artifact audience-filter receipt is missing."
                )
            ),
        },
        "ea_event_prep_followthrough": {
            "state": ea_event_prep_state,
            "baseline_pack_path": str(ea_operator_safe_pack_path),
            "baseline_pack_present": ea_operator_safe_pack["exists"],
            "baseline_pack_state": ea_operator_safe_pack["state"],
            "baseline_pack_issues": ea_operator_safe_pack["issues"],
            "organizer_pack_path": str(ea_organizer_packet_pack_path),
            "organizer_pack_present": ea_organizer_pack["exists"],
            "organizer_pack_issues": ea_organizer_pack["issues"],
            "summary": (
                "EA organizer event-prep packet contract is present and shape-valid."
                if ea_organizer_pack["state"] == "ready" and ea_operator_safe_pack["state"] == "ready"
                else (
                    ea_operator_safe_pack["summary"]
                    if ea_operator_safe_pack["state"] != "ready"
                    else (
                        "EA still lacks an M118-specific organizer event-prep packet pack, so Fleet must keep the operator packet fail-closed."
                        if not ea_organizer_pack["exists"]
                        else ea_organizer_pack["summary"]
                    )
                )
            ),
        },
    }

    publication_readiness_state = "ready"
    publication_readiness_reasons: List[str] = []
    if creator_verifier["status"] != "pass":
        publication_readiness_state = "blocked"
        publication_readiness_reasons.append("Hub creator publication proof is failing.")
    if not artifact_shelf_receipt:
        publication_readiness_state = "blocked"
        publication_readiness_reasons.append("Hub artifact shelf receipt is missing.")
    if not artifact_shelf_filters_receipt:
        publication_readiness_state = "blocked"
        publication_readiness_reasons.append("Hub artifact audience-filter receipt is missing.")
    if _normalize_text(weekly_decision_alignment.get("status")) != "pass":
        publication_readiness_state = "blocked"
        publication_readiness_reasons.append("Weekly governor decision alignment is failing.")
    if _is_freeze_publication_posture(weekly_decision_alignment, public_status_copy):
        if publication_readiness_state == "ready":
            publication_readiness_state = "watch"
        publication_readiness_reasons.append("Launch expansion is still frozen at the weekly governor layer.")

    publication_readiness = {
        "state": publication_readiness_state,
        "summary": "; ".join(publication_readiness_reasons) or "Publication-facing sibling proofs are present and aligned.",
        "artifact_shelf_receipt_id": _normalize_text(artifact_shelf_receipt.get("receipt_id")),
        "creator_publication_verifier_status": creator_verifier["status"],
        "weekly_governor_action": _normalize_text(weekly_decision_alignment.get("actual_action")),
        "weekly_governor_public_state": _normalize_text(public_status_copy.get("state")),
    }

    next_actions: List[str] = []
    if queue_alignment["state"] != "pass":
        next_actions.append("Repair Fleet/design queue or registry drift before trusting the M118 operator packet.")
    if organizer_verifier["status"] != "pass":
        next_actions.append("Fix the Hub organizer-ops proof lane before promoting organizer-health summaries.")
    if creator_verifier["status"] != "pass":
        next_actions.append("Fix the Hub creator-publication proof lane before promoting publication-readiness summaries.")
    if not artifact_shelf_filters_receipt:
        next_actions.append("Restore the Hub artifact audience-filter receipt before trusting organizer publication-readiness summaries.")
    if ea_operator_safe_pack["state"] != "ready":
        next_actions.append("Repair the EA operator-safe baseline packet contract before trusting organizer event-prep followthrough.")
    if ea_organizer_pack["state"] != "ready":
        next_actions.append("Land the EA M118 organizer event-prep packet contract so Fleet can stop fail-closing the combined operator packet.")
    if support_risk["state"] != "low":
        next_actions.append("Clear install-aware support packet pressure before treating organizer publication work as ready for broad promotion.")
    if not next_actions:
        next_actions.append("Promote the M118 organizer operator packet as a current operator-loop input and keep the sibling proofs fresh.")

    blocked = any(
        (
            organizer_health["state"] != "pass",
            support_risk["state"] == "high",
            publication_readiness["state"] == "blocked",
        )
    )
    status = "blocked" if blocked else "pass"
    status_reason = (
        organizer_health["ea_event_prep_followthrough"]["summary"]
        if organizer_health["ea_event_prep_followthrough"]["state"] == "blocked"
        else "Organizer-health, support-risk, and publication-readiness inputs are aligned."
    )
    source_packet_links = {
        "claim_guard": "fleet_or_ea_packets_must_link_back_to_source_packet_ids",
        "weekly_governor": {
            "contract_name": _normalize_text(weekly_governor.get("contract_name")),
            "as_of": _normalize_text(weekly_governor.get("as_of")),
            "decision_action": _normalize_text(weekly_decision_alignment.get("actual_action")),
        },
        "support_followthrough": {
            "contract_name": _normalize_text(support_packets.get("contract_name")),
            "package_id": _normalize_text(support_followthrough_gates.get("package_id")),
            "packet_ids": support_packet_ids,
        },
        "hub_publication_receipts": {
            "receipt_ids": artifact_receipt_ids,
            "package_ids": artifact_receipt_package_ids,
        },
        "ea_operator_packets": {
            "baseline_pack_path": _display_path(ea_operator_safe_pack_path),
            "organizer_pack_path": _display_path(ea_organizer_packet_pack_path),
        },
    }

    return {
        "generated_at": generated_at or _utc_now(),
        "contract_name": "fleet.next90_m118_organizer_operator_packets",
        "status": status,
        "status_reason": status_reason,
        "package_id": PACKAGE_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "milestone_id": MILESTONE_ID,
        "frontier_id": FRONTIER_ID,
        "work_task_id": WORK_TASK_ID,
        "wave_id": WAVE_ID,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "as_of": _normalize_text(weekly_governor.get("as_of")) or generated_at or _utc_now(),
        "agreement": {
            "queue_scope_matches_package": queue_alignment["state"] == "pass",
            "registry_scope_matches_package": queue_alignment["state"] == "pass",
            "fleet_queue_status": queue_alignment["fleet_queue_status"],
            "design_queue_status": queue_alignment["design_queue_status"],
            "registry_work_task_status": queue_alignment["registry_work_task_status"],
            "closed_anywhere": queue_alignment["closed_anywhere"],
            "queue_completion_action": queue_alignment["queue_completion_action"],
            "design_queue_completion_action": queue_alignment["design_queue_completion_action"],
            "registry_work_task_completion_action": queue_alignment["registry_work_task_completion_action"],
            "queue_do_not_reopen_reason": queue_alignment["queue_do_not_reopen_reason"],
            "design_queue_do_not_reopen_reason": queue_alignment["design_queue_do_not_reopen_reason"],
            "registry_work_task_do_not_reopen_reason": queue_alignment["registry_work_task_do_not_reopen_reason"],
            "expected_completion_action": queue_alignment["expected_completion_action"],
            "expected_do_not_reopen_reason": queue_alignment["expected_do_not_reopen_reason"],
        },
        "organizer_health": organizer_health,
        "support_risk": support_risk,
        "publication_readiness": publication_readiness,
        "source_packet_links": source_packet_links,
        "source_inputs": {
            "weekly_governor_packet": {
                "path": _display_path(weekly_governor_packet_path),
                "generated_at": _normalize_text(weekly_governor.get("generated_at")),
                "status": _normalize_text(weekly_governor.get("status")),
            },
            "support_packets": {
                "path": _display_path(support_packets_path),
                "generated_at": _normalize_text(support_packets.get("generated_at")),
                "successor_package_verification_status": _normalize_text((support_packets.get("successor_package_verification") or {}).get("status")),
            },
            "hub_local_release_proof": {
                "path": _display_path(hub_local_release_proof_path),
                "generated_at": _normalize_text(hub_proof.get("generated_at") or hub_proof.get("generatedAt")),
                "status": _normalize_text(hub_proof.get("status")),
            },
            "ea_operator_safe_pack": {
                "path": _display_path(ea_operator_safe_pack_path),
                "exists": ea_operator_safe_pack["exists"],
                "state": ea_operator_safe_pack["state"],
            },
            "ea_organizer_packet_pack": {
                "path": _display_path(ea_organizer_packet_pack_path),
                "exists": ea_organizer_pack["exists"],
                "state": ea_organizer_pack["state"],
            },
        },
        "next_actions": next_actions,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    organizer = dict(payload.get("organizer_health") or {})
    ea_followthrough = dict(organizer.get("ea_event_prep_followthrough") or {})
    publication = dict(payload.get("publication_readiness") or {})
    support_risk = dict(payload.get("support_risk") or {})
    source_links = dict(payload.get("source_packet_links") or {})
    support_links = dict(source_links.get("support_followthrough") or {})
    hub_links = dict(source_links.get("hub_publication_receipts") or {})
    return "\n".join(
        [
            "# Fleet M118 organizer operator packet",
            "",
            f"- Generated at: `{payload.get('generated_at')}`",
            f"- Status: `{payload.get('status')}`",
            f"- Reason: {payload.get('status_reason')}",
            f"- Queue scope aligned: `{dict(payload.get('agreement') or {}).get('queue_scope_matches_package')}`",
            f"- Registry work-task status: `{dict(payload.get('agreement') or {}).get('registry_work_task_status')}`",
            f"- Hub organizer verifier: `{dict(organizer.get('hub_organizer_ops') or {}).get('status')}`",
            f"- Hub creator publication verifier: `{dict(organizer.get('hub_creator_publication') or {}).get('status')}`",
            f"- Artifact shelf publication surface: `{dict(organizer.get('artifact_shelf_publication_surface') or {}).get('state')}`",
            f"- EA organizer packet contract: `{ea_followthrough.get('state')}`",
            f"- Support risk: `{support_risk.get('state')}`",
            f"- Publication readiness: `{publication.get('state')}`",
            f"- Support followthrough package: `{support_links.get('package_id')}`",
            f"- Hub publication receipts: `{', '.join(hub_links.get('receipt_ids') or []) or 'none'}`",
            "",
            "## Next actions",
            *[f"- {item}" for item in payload.get("next_actions") or []],
            "",
        ]
    ) + "\n"


def main() -> int:
    args = parse_args()
    payload = build_payload(
        registry_path=Path(args.successor_registry),
        queue_path=Path(args.queue_staging),
        design_queue_path=Path(args.design_queue_staging),
        weekly_governor_packet_path=Path(args.weekly_governor_packet),
        support_packets_path=Path(args.support_packets),
        hub_local_release_proof_path=Path(args.hub_local_release_proof),
        hub_organizer_verifier_path=Path(args.hub_organizer_verifier),
        hub_creator_publication_verifier_path=Path(args.hub_creator_publication_verifier),
        ea_operator_safe_pack_path=Path(args.ea_operator_safe_pack),
        ea_organizer_packet_pack_path=Path(args.ea_organizer_packet_pack),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    markdown_path = Path(args.markdown_output)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
