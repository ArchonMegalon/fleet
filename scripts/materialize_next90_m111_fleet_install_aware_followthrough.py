#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = ROOT / ".codex-design" / "product"

PACKAGE_ID = "next90-m111-fleet-install-aware-followthrough"
FRONTIER_ID = 5200108449
MILESTONE_ID = 111
WORK_TASK_ID = "111.4"
WAVE_ID = "W9"
REGISTRY_PATH = Path("/docker/chummercomplete/chummer-design/products/chummer/NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml")
QUEUE_PATH = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
SUPPORT_PACKETS_PATH = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
WEEKLY_GOVERNOR_PACKET_PATH = PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"
WEEKLY_PRODUCT_PULSE_PATH = PRODUCT_MIRROR / "WEEKLY_PRODUCT_PULSE.generated.json"
PROGRESS_REPORT_PATH = PRODUCT_MIRROR / "PROGRESS_REPORT.generated.json"
DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M111_FLEET_INSTALL_AWARE_FOLLOWTHROUGH.generated.json"
UTC = dt.timezone.utc

EXPECTED_ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]
EXPECTED_OWNED_SURFACES = ["install_aware_followthrough", "product_governor:artifact_promotion"]
EXPECTED_COMPLETION_ACTION = "verify_closed_package_only"
EXPECTED_DO_NOT_REOPEN_REASON = (
    "M111 Fleet install-aware followthrough is complete; future shards must verify the "
    "install-aware gate receipt, standalone verifier, registry row, queue row, and design queue row "
    "instead of reopening the followthrough-mail and public-proof promotion package."
)
REQUIRED_PUBLICATION_REFS = (
    ("support_packets", SUPPORT_PACKETS_PATH, "install-aware followthrough receipt source"),
    ("weekly_governor_packet", WEEKLY_GOVERNOR_PACKET_PATH, "promotion and kill-switch ledger"),
    ("weekly_product_pulse", WEEKLY_PRODUCT_PULSE_PATH, "public promotion decision source"),
    ("progress_report", PROGRESS_REPORT_PATH, "public proof shelf snapshot"),
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize the Fleet M111 install-aware followthrough gate from published support, "
            "governor, and public-proof artifacts."
        )
    )
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS_PATH))
    parser.add_argument("--weekly-governor-packet", default=str(WEEKLY_GOVERNOR_PACKET_PATH))
    parser.add_argument("--weekly-product-pulse", default=str(WEEKLY_PRODUCT_PULSE_PATH))
    parser.add_argument("--progress-report", default=str(PROGRESS_REPORT_PATH))
    parser.add_argument("--successor-registry", default=str(REGISTRY_PATH))
    parser.add_argument("--queue-staging", default=str(QUEUE_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def _utc_now_iso() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _find_queue_item(queue_payload: Dict[str, Any]) -> Dict[str, Any]:
    for row in queue_payload.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("package_id")) == PACKAGE_ID:
            return row
    return {}


def _find_registry_milestone(registry_payload: Dict[str, Any]) -> Dict[str, Any]:
    for row in registry_payload.get("milestones") or []:
        if isinstance(row, dict) and row.get("id") == MILESTONE_ID:
            return row
    return {}


def _find_registry_work_task(milestone: Dict[str, Any]) -> Dict[str, Any]:
    for row in milestone.get("work_tasks") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == WORK_TASK_ID:
            return row
    return {}


def _weekly_launch_decision(weekly_pulse: Dict[str, Any]) -> Dict[str, str]:
    rows = weekly_pulse.get("governor_decisions") or []
    if not isinstance(rows, list):
        return {"action": "", "reason": ""}
    for row in rows:
        if not isinstance(row, dict):
            continue
        action = _normalize_text(row.get("action"))
        if action in {"launch_expand", "freeze_launch"}:
            return {
                "action": action,
                "reason": _normalize_text(row.get("reason")),
            }
    return {"action": "", "reason": ""}


def _expected_public_status_state(governor_action: str, rollback_state: str) -> str:
    if governor_action == "launch_expand":
        return "launch_expand_allowed"
    if rollback_state == "armed":
        return "freeze_with_rollback_watch"
    return "freeze_launch"


def _publication_ref(name: str, role: str, path: Path) -> Dict[str, Any]:
    exists = path.exists()
    payload = _read_json(path) if exists else {}
    return {
        "name": name,
        "role": role,
        "path": str(path),
        "exists": exists,
        "sha256": _sha256_file(path) if exists else "",
        "generated_at": _normalize_text(payload.get("generated_at")),
        "as_of": _normalize_text(payload.get("as_of")),
    }


def _all_equal(values: Iterable[str]) -> bool:
    items = [value for value in values if value]
    return len(set(items)) <= 1


def _gate_state(passed: bool) -> str:
    return "pass" if passed else "hold"


def _gate_reason(*, passed: bool, reasons: List[str], positive: str) -> str:
    if passed:
        return positive
    return "; ".join(reason for reason in reasons if reason) or "install-aware promotion evidence is incomplete"


def build_payload(
    *,
    support_packets_path: Path,
    weekly_governor_packet_path: Path,
    weekly_product_pulse_path: Path,
    progress_report_path: Path,
    registry_path: Path,
    queue_path: Path,
    generated_at: str | None = None,
) -> Dict[str, Any]:
    support_packets = _read_json(support_packets_path)
    weekly_governor_packet = _read_json(weekly_governor_packet_path)
    weekly_product_pulse = _read_json(weekly_product_pulse_path)
    progress_report = _read_json(progress_report_path)
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)

    queue_item = _find_queue_item(queue)
    milestone = _find_registry_milestone(registry)
    work_task = _find_registry_work_task(milestone)

    support_summary = dict(support_packets.get("summary") or {})
    support_verification = dict(support_packets.get("successor_package_verification") or {})
    followthrough_gates = dict(support_packets.get("followthrough_receipt_gates") or {})
    decision_alignment = dict(weekly_governor_packet.get("decision_alignment") or {})
    decision_board = dict(weekly_governor_packet.get("decision_board") or {})
    public_status_copy = dict(weekly_governor_packet.get("public_status_copy") or {})
    pulse_decision = _weekly_launch_decision(weekly_product_pulse)

    reporter_missing = int(support_summary.get("reporter_followthrough_blocked_missing_install_receipts_count") or 0)
    reporter_mismatch = int(support_summary.get("reporter_followthrough_blocked_receipt_mismatch_count") or 0)
    receipt_gate_missing = int(followthrough_gates.get("blocked_missing_install_receipts_count") or 0)
    receipt_gate_mismatch = int(followthrough_gates.get("blocked_receipt_mismatch_count") or 0)
    closure_waiting = int(support_summary.get("closure_waiting_on_release_truth") or 0)
    support_verification_status = _normalize_text(support_verification.get("status"))

    governor_action = _normalize_text(decision_alignment.get("actual_action"))
    expected_action = _normalize_text(decision_alignment.get("expected_action"))
    rollback_state = _normalize_text(((decision_board.get("rollback") or {}).get("state")))
    freeze_launch_state = _normalize_text(((decision_board.get("freeze_launch") or {}).get("state")))
    launch_expand_state = _normalize_text(((decision_board.get("launch_expand") or {}).get("state")))
    expected_public_status = _expected_public_status_state(governor_action, rollback_state)

    publication_refs = [
        _publication_ref(name, role, path)
        for name, path, role in (
            ("support_packets", support_packets_path, "install-aware followthrough receipt source"),
            ("weekly_governor_packet", weekly_governor_packet_path, "promotion and kill-switch ledger"),
            ("weekly_product_pulse", weekly_product_pulse_path, "public promotion decision source"),
            ("progress_report", progress_report_path, "public proof shelf snapshot"),
        )
    ]
    publication_ref_as_of_values = [str(ref.get("as_of") or "").strip() for ref in publication_refs if ref["name"] != "support_packets"]
    publication_refs_present = all(bool(ref.get("exists")) and bool(ref.get("sha256")) for ref in publication_refs)
    publication_ref_as_of_aligned = _all_equal(publication_ref_as_of_values)
    receipt_blockers_clear = (
        reporter_missing == 0
        and reporter_mismatch == 0
        and receipt_gate_missing == 0
        and receipt_gate_mismatch == 0
    )
    closure_clear = closure_waiting == 0
    weekly_launch_action_aligned = bool(
        governor_action
        and pulse_decision["action"]
        and governor_action == pulse_decision["action"]
        and governor_action == expected_action
        and _normalize_text(decision_alignment.get("status")) == "pass"
    )
    governor_public_status_aligned = _normalize_text(public_status_copy.get("state")) == expected_public_status
    support_successor_verification_pass = support_verification_status == "pass"

    mail_gate_pass = receipt_blockers_clear and closure_clear and support_successor_verification_pass
    public_proof_gate_pass = (
        mail_gate_pass
        and weekly_launch_action_aligned
        and governor_public_status_aligned
        and governor_action == "launch_expand"
        and publication_refs_present
        and publication_ref_as_of_aligned
    )

    mail_hold_reasons: List[str] = []
    if not receipt_blockers_clear:
        mail_hold_reasons.append(
            "install-aware receipt blockers remain "
            f"(reporter_missing={reporter_missing}, reporter_mismatch={reporter_mismatch}, "
            f"receipt_gate_missing={receipt_gate_missing}, receipt_gate_mismatch={receipt_gate_mismatch})"
        )
    if not closure_clear:
        mail_hold_reasons.append(f"support closure still waits on release truth ({closure_waiting})")
    if not support_successor_verification_pass:
        mail_hold_reasons.append(
            f"support successor package verification is {_normalize_text(support_verification.get('status')) or 'missing'}"
        )

    public_hold_reasons = list(mail_hold_reasons)
    if not weekly_launch_action_aligned:
        public_hold_reasons.append(
            "weekly pulse and governor launch actions do not agree on public promotion posture"
        )
    if not governor_public_status_aligned:
        public_hold_reasons.append(
            "public status copy state does not match the measured governor decision"
        )
    if governor_action and governor_action != "launch_expand":
        public_hold_reasons.append(f"governor action is {governor_action} instead of launch_expand")
    if not publication_refs_present:
        missing = ", ".join(ref["name"] for ref in publication_refs if not ref["exists"] or not ref["sha256"])
        public_hold_reasons.append(f"publication refs are missing or unreadable: {missing}")
    if not publication_ref_as_of_aligned:
        public_hold_reasons.append(
            "publication refs do not share one public as_of date across pulse, governor, and progress report"
        )

    return {
        "contract_name": "fleet.install_aware_followthrough_gate",
        "schema_version": 1,
        "generated_at": generated_at or _utc_now_iso(),
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave_id": WAVE_ID,
        "registry_milestone_title": _normalize_text(milestone.get("title")),
        "registry_status": _normalize_text(milestone.get("status")),
        "registry_exit_criteria": _normalize_list(milestone.get("exit_criteria")),
        "registry_dependencies": list(milestone.get("dependencies") or []),
        "registry_work_task_title": _normalize_text(work_task.get("title")),
        "registry_work_task_status": _normalize_text(work_task.get("status")),
        "registry_work_task_completion_action": _normalize_text(work_task.get("completion_action")),
        "registry_work_task_do_not_reopen_reason": _normalize_text(work_task.get("do_not_reopen_reason")),
        "queue_title": _normalize_text(queue_item.get("title")),
        "queue_task": _normalize_text(queue_item.get("task")),
        "queue_repo": _normalize_text(queue_item.get("repo")),
        "queue_wave": _normalize_text(queue_item.get("wave")),
        "queue_status": _normalize_text(queue_item.get("status")),
        "queue_completion_action": _normalize_text(queue_item.get("completion_action")),
        "queue_do_not_reopen_reason": _normalize_text(queue_item.get("do_not_reopen_reason")),
        "queue_allowed_paths": _normalize_list(queue_item.get("allowed_paths")),
        "queue_owned_surfaces": _normalize_list(queue_item.get("owned_surfaces")),
        "source_paths": {
            "support_packets": str(support_packets_path),
            "weekly_governor_packet": str(weekly_governor_packet_path),
            "weekly_product_pulse": str(weekly_product_pulse_path),
            "progress_report": str(progress_report_path),
            "successor_registry": str(registry_path),
            "queue_staging": str(queue_path),
        },
        "support_receipt_truth": {
            "support_packets_generated_at": _normalize_text(support_packets.get("generated_at")),
            "successor_package_verification_status": support_verification_status,
            "reporter_followthrough_blocked_missing_install_receipts_count": reporter_missing,
            "reporter_followthrough_blocked_receipt_mismatch_count": reporter_mismatch,
            "followthrough_receipt_gates_blocked_missing_install_receipts_count": receipt_gate_missing,
            "followthrough_receipt_gates_blocked_receipt_mismatch_count": receipt_gate_mismatch,
            "closure_waiting_on_release_truth": closure_waiting,
            "followthrough_ready_count": int(followthrough_gates.get("ready_count") or 0),
        },
        "launch_truth": {
            "weekly_product_pulse_generated_at": _normalize_text(weekly_product_pulse.get("generated_at")),
            "weekly_product_pulse_as_of": _normalize_text(weekly_product_pulse.get("as_of")),
            "weekly_product_pulse_action": pulse_decision["action"],
            "weekly_product_pulse_reason": pulse_decision["reason"],
            "weekly_governor_packet_generated_at": _normalize_text(weekly_governor_packet.get("generated_at")),
            "weekly_governor_packet_as_of": _normalize_text(weekly_governor_packet.get("as_of")),
            "governor_expected_action": expected_action,
            "governor_actual_action": governor_action,
            "governor_alignment_status": _normalize_text(decision_alignment.get("status")),
            "freeze_launch_state": freeze_launch_state,
            "launch_expand_state": launch_expand_state,
            "rollback_state": rollback_state,
            "public_status_state": _normalize_text(public_status_copy.get("state")),
            "public_status_headline": _normalize_text(public_status_copy.get("headline")),
            "public_status_body": _normalize_text(public_status_copy.get("body")),
            "expected_public_status_state": expected_public_status,
        },
        "publication_refs": publication_refs,
        "agreement": {
            "queue_scope_matches_package": (
                _normalize_text(queue_item.get("repo")) == "fleet"
                and _normalize_text(queue_item.get("wave")) == WAVE_ID
                and _normalize_list(queue_item.get("allowed_paths")) == EXPECTED_ALLOWED_PATHS
                and _normalize_list(queue_item.get("owned_surfaces")) == EXPECTED_OWNED_SURFACES
            ),
            "registry_scope_matches_package": (
                _normalize_text(work_task.get("id")) == WORK_TASK_ID
                and _normalize_text(work_task.get("owner")) == "fleet"
            ),
            "queue_closure_matches_package": (
                _normalize_text(queue_item.get("status")) == "complete"
                and _normalize_text(queue_item.get("completion_action")) == EXPECTED_COMPLETION_ACTION
                and _normalize_text(queue_item.get("do_not_reopen_reason")) == EXPECTED_DO_NOT_REOPEN_REASON
            ),
            "registry_closure_matches_package": (
                _normalize_text(work_task.get("status")) == "complete"
                and _normalize_text(work_task.get("completion_action")) == EXPECTED_COMPLETION_ACTION
                and _normalize_text(work_task.get("do_not_reopen_reason")) == EXPECTED_DO_NOT_REOPEN_REASON
            ),
            "receipt_blockers_clear": receipt_blockers_clear,
            "closure_clear": closure_clear,
            "support_successor_verification_pass": support_successor_verification_pass,
            "weekly_launch_action_aligned": weekly_launch_action_aligned,
            "governor_public_status_aligned": governor_public_status_aligned,
            "publication_refs_present": publication_refs_present,
            "publication_ref_as_of_aligned": publication_ref_as_of_aligned,
            "publication_refs_agree": (
                publication_refs_present and publication_ref_as_of_aligned and weekly_launch_action_aligned
            ),
        },
        "kill_switch_posture": {
            "freeze_launch_state": freeze_launch_state,
            "rollback_state": rollback_state,
            "launch_expand_state": launch_expand_state,
            "expected_public_status_state": expected_public_status,
            "allows_public_promotion": public_proof_gate_pass,
        },
        "gates": {
            "followthrough_mail": {
                "state": _gate_state(mail_gate_pass),
                "reason": _gate_reason(
                    passed=mail_gate_pass,
                    reasons=mail_hold_reasons,
                    positive=(
                        "Install-aware followthrough mail is clear: support receipt blockers are zero, "
                        "support closure is current, and the source support packet remains verifier-backed."
                    ),
                ),
            },
            "public_proof_promotion": {
                "state": _gate_state(public_proof_gate_pass),
                "reason": _gate_reason(
                    passed=public_proof_gate_pass,
                    reasons=public_hold_reasons,
                    positive=(
                        "Public proof promotion is clear: install-aware receipt gates are green, weekly launch truth agrees, "
                        "and the promoted publication refs share one public snapshot."
                    ),
                ),
            },
        },
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output).resolve()
    payload = build_payload(
        support_packets_path=Path(args.support_packets).resolve(),
        weekly_governor_packet_path=Path(args.weekly_governor_packet).resolve(),
        weekly_product_pulse_path=Path(args.weekly_product_pulse).resolve(),
        progress_report_path=Path(args.progress_report).resolve(),
        registry_path=Path(args.successor_registry).resolve(),
        queue_path=Path(args.queue_staging).resolve(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote install-aware followthrough gate: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
