#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

try:
    from scripts.materialize_compile_manifest import (
        repo_root_for_published_path,
        write_compile_manifest,
        write_text_atomic,
    )
except ModuleNotFoundError:
    from materialize_compile_manifest import (
        repo_root_for_published_path,
        write_compile_manifest,
        write_text_atomic,
    )


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
SUCCESSOR_REGISTRY = (
    Path("/docker/chummercomplete/chummer-design/products/chummer")
    / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
)
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
WEEKLY_PULSE = PUBLISHED / "WEEKLY_PRODUCT_PULSE.generated.json"
FLAGSHIP_READINESS = PUBLISHED / "FLAGSHIP_PRODUCT_READINESS.generated.json"
JOURNEY_GATES = PUBLISHED / "JOURNEY_GATES.generated.json"
SUPPORT_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"
STATUS_PLANE = PUBLISHED / "STATUS_PLANE.generated.yaml"
PACKAGE_ID = "next90-m106-fleet-governor-packet"
MILESTONE_ID = 106
OWNED_SURFACES = ("weekly_governor_packet", "measured_rollout_loop")
ALLOWED_PATHS = ("admin", "scripts", "tests", ".codex-studio")
UTC = dt.timezone.utc
WEEKLY_PULSE_MAX_AGE_SECONDS = 8 * 24 * 60 * 60
REQUIRED_LAUNCH_SIGNALS = (
    "journey_gate_state",
    "local_release_proof_status",
    "provider_canary_status",
    "closure_health_state",
)


def iso_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the Fleet weekly governor packet for successor milestone 106."
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--out",
        default=str(PUBLISHED / "WEEKLY_GOVERNOR_PACKET.generated.json"),
        help="output path for WEEKLY_GOVERNOR_PACKET.generated.json",
    )
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--weekly-pulse", default=str(WEEKLY_PULSE))
    parser.add_argument("--flagship-readiness", default=str(FLAGSHIP_READINESS))
    parser.add_argument("--journey-gates", default=str(JOURNEY_GATES))
    parser.add_argument("--support-packets", default=str(SUPPORT_PACKETS))
    parser.add_argument("--status-plane", default=str(STATUS_PLANE))
    return parser.parse_args(argv)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _norm_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _find_milestone(registry: Dict[str, Any]) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and _coerce_int(row.get("id"), -1) == MILESTONE_ID:
            return row
    return {}


def _find_queue_item(queue: Dict[str, Any]) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and str(row.get("package_id") or "").strip() == PACKAGE_ID:
            return row
    return {}


def verify_package(registry: Dict[str, Any], queue: Dict[str, Any]) -> Dict[str, Any]:
    milestone = _find_milestone(registry)
    item = _find_queue_item(queue)
    issues: List[str] = []
    if not milestone:
        issues.append(f"milestone {MILESTONE_ID} is missing from successor registry")
    if not item:
        issues.append(f"queue item {PACKAGE_ID} is missing from staging queue")
    if item:
        if _coerce_int(item.get("milestone_id"), -1) != MILESTONE_ID:
            issues.append("queue item milestone_id does not match milestone 106")
        if str(item.get("repo") or "").strip() != "fleet":
            issues.append("queue item repo is not fleet")
        if _norm_list(item.get("allowed_paths")) != list(ALLOWED_PATHS):
            issues.append("queue item allowed_paths no longer match package authority")
        if _norm_list(item.get("owned_surfaces")) != list(OWNED_SURFACES):
            issues.append("queue item owned_surfaces no longer match package authority")
    if milestone:
        if str(milestone.get("status") or "").strip() != "in_progress":
            issues.append("milestone 106 is not in_progress in successor registry")
        owners = set(_norm_list(milestone.get("owners")))
        if "fleet" not in owners:
            issues.append("milestone 106 no longer names fleet as an owner")
    return {
        "status": "pass" if not issues else "fail",
        "package_id": PACKAGE_ID,
        "milestone_id": MILESTONE_ID,
        "repo": "fleet",
        "owned_surfaces": list(OWNED_SURFACES),
        "allowed_paths": list(ALLOWED_PATHS),
        "registry_milestone_title": str(milestone.get("title") or "").strip(),
        "registry_status": str(milestone.get("status") or "").strip(),
        "registry_dependencies": [
            _coerce_int(dep, -1)
            for dep in (milestone.get("dependencies") or [])
            if _coerce_int(dep, -1) >= 0
        ],
        "queue_title": str(item.get("title") or "").strip(),
        "queue_task": str(item.get("task") or "").strip(),
        "issues": issues,
    }


def _decision_signal_map(decision: Dict[str, Any]) -> Dict[str, str]:
    signals: Dict[str, str] = {}
    for item in decision.get("cited_signals") or []:
        text = str(item or "").strip()
        if not text:
            continue
        key, _, value = text.partition("=")
        if key.strip():
            signals[key.strip()] = value.strip()
    return signals


def _launch_decision(weekly_pulse: Dict[str, Any]) -> Dict[str, Any]:
    for row in weekly_pulse.get("governor_decisions") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("action") or "").strip() in {"freeze_launch", "launch_expand"}:
            return row
    return {}


def verify_weekly_inputs(weekly_pulse: Dict[str, Any], launch_decision: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    generated_at = _parse_iso_utc(weekly_pulse.get("generated_at"))
    if str(weekly_pulse.get("contract_name") or "").strip() != "chummer.weekly_product_pulse":
        issues.append("weekly pulse contract_name is missing or unexpected")
    if _coerce_int(weekly_pulse.get("contract_version"), 0) < 3:
        issues.append("weekly pulse contract_version is stale; expected >=3")
    if not generated_at:
        issues.append("weekly pulse generated_at is missing or invalid")
    else:
        age_seconds = int((dt.datetime.now(UTC) - generated_at).total_seconds())
        if age_seconds > WEEKLY_PULSE_MAX_AGE_SECONDS:
            issues.append(f"weekly pulse is stale ({age_seconds}s old)")
    if not launch_decision:
        issues.append("weekly pulse is missing a launch governance decision")
    else:
        signals = _decision_signal_map(launch_decision)
        missing = [key for key in REQUIRED_LAUNCH_SIGNALS if not signals.get(key)]
        if missing:
            issues.append("weekly pulse launch governance decision is missing cited signal(s): " + ", ".join(missing))
    return {
        "status": "pass" if not issues else "fail",
        "generated_at": str(weekly_pulse.get("generated_at") or "").strip(),
        "max_age_seconds": WEEKLY_PULSE_MAX_AGE_SECONDS,
        "required_launch_signals": list(REQUIRED_LAUNCH_SIGNALS),
        "issues": issues,
    }


def _support_summary(support_packets: Dict[str, Any]) -> Dict[str, Any]:
    summary = dict(support_packets.get("summary") or {})
    return {
        "open_packet_count": _coerce_int(summary.get("open_packet_count"), 0),
        "open_non_external_packet_count": _coerce_int(summary.get("open_non_external_packet_count"), 0),
        "closure_waiting_on_release_truth": _coerce_int(summary.get("closure_waiting_on_release_truth"), 0),
        "update_required_misrouted_case_count": _coerce_int(summary.get("update_required_misrouted_case_count"), 0),
    }


def _flagship_parity_summary(flagship_readiness: Dict[str, Any]) -> Dict[str, Any]:
    planes = dict(flagship_readiness.get("readiness_planes") or {})
    flagship = dict(planes.get("flagship_ready") or {})
    evidence = dict(flagship.get("evidence") or {})
    status_counts = {
        str(key): _coerce_int(value, 0)
        for key, value in dict(evidence.get("status_counts") or {}).items()
    }
    families_below_task = _norm_list(evidence.get("families_below_task_proven"))
    families_below_veteran = _norm_list(evidence.get("families_below_veteran_approved"))
    families_below_gold = _norm_list(evidence.get("families_below_gold_ready"))
    known_family_count = sum(status_counts.values())
    if not evidence or not bool(evidence.get("registry_present")) or known_family_count == 0:
        release_truth_status = "unknown"
    elif families_below_task or families_below_veteran:
        release_truth_status = "blocked"
    elif families_below_gold:
        release_truth_status = "veteran_ready"
    else:
        release_truth_status = "gold_ready"
    return {
        "release_truth_status": release_truth_status,
        "readiness_plane_status": str(flagship.get("status") or "unknown").strip(),
        "registry_path": str(evidence.get("registry_path") or "").strip(),
        "registry_present": bool(evidence.get("registry_present")),
        "status_counts": status_counts,
        "families_below_task_proven": families_below_task,
        "families_below_veteran_approved": families_below_veteran,
        "families_below_gold_ready": families_below_gold,
    }


def build_payload(
    *,
    registry: Dict[str, Any],
    queue: Dict[str, Any],
    weekly_pulse: Dict[str, Any],
    flagship_readiness: Dict[str, Any],
    journey_gates: Dict[str, Any],
    support_packets: Dict[str, Any],
    status_plane: Dict[str, Any],
    source_paths: Dict[str, str],
) -> Dict[str, Any]:
    verification = verify_package(registry, queue)
    launch_decision = _launch_decision(weekly_pulse)
    weekly_input_health = verify_weekly_inputs(weekly_pulse, launch_decision)
    launch_signals = _decision_signal_map(launch_decision)
    supporting = dict(weekly_pulse.get("supporting_signals") or {})
    provider = dict(supporting.get("provider_route_stewardship") or {})
    closure = dict(supporting.get("closure_health") or {})
    adoption = dict(supporting.get("adoption_health") or {})
    journey_summary = dict(journey_gates.get("summary") or {})
    support = _support_summary(support_packets)
    local_release_proof = str(
        launch_signals.get("local_release_proof_status")
        or adoption.get("local_release_proof_status")
        or "unknown"
    ).strip()
    canary_status = str(
        launch_signals.get("provider_canary_status") or provider.get("canary_status") or "unknown"
    ).strip()
    closure_state = str(
        launch_signals.get("closure_health_state") or closure.get("state") or "unknown"
    ).strip()
    journey_state = str(
        launch_signals.get("journey_gate_state")
        or journey_summary.get("overall_state")
        or (weekly_pulse.get("journey_gate_health") or {}).get("state")
        or "unknown"
    ).strip()
    readiness_status = str(flagship_readiness.get("status") or "unknown").strip()
    parity = _flagship_parity_summary(flagship_readiness)
    parity_gold_ready = parity["release_truth_status"] == "gold_ready"
    launch_allowed = (
        verification["status"] == "pass"
        and weekly_input_health["status"] == "pass"
        and readiness_status == "pass"
        and parity_gold_ready
        and journey_state == "ready"
        and local_release_proof == "passed"
        and canary_status == "Canary green on all active lanes"
        and closure_state == "clear"
        and support["open_non_external_packet_count"] == 0
    )
    freeze_active = not launch_allowed
    rollback_watch = (
        support["closure_waiting_on_release_truth"] > 0
        or support["update_required_misrouted_case_count"] > 0
        or str((weekly_pulse.get("release_health") or {}).get("state") or "").strip() not in {
            "green",
            "green_or_explained",
            "ready",
        }
    )
    measured_loop_ready = (
        verification["status"] == "pass"
        and weekly_input_health["status"] == "pass"
        and readiness_status == "pass"
        and parity["release_truth_status"] in {"gold_ready", "veteran_ready"}
        and support["open_non_external_packet_count"] == 0
    )
    return {
        "contract_name": "fleet.weekly_governor_packet",
        "schema_version": 1,
        "generated_at": iso_now(),
        "as_of": str(weekly_pulse.get("as_of") or "").strip(),
        "program_wave": "next_90_day_product_advance",
        "package_verification": verification,
        "weekly_input_health": weekly_input_health,
        "source_paths": source_paths,
        "truth_inputs": {
            "weekly_pulse_contract": str(weekly_pulse.get("contract_name") or "").strip(),
            "weekly_pulse_version": _coerce_int(weekly_pulse.get("contract_version"), 0),
            "flagship_readiness_status": readiness_status,
            "flagship_parity_release_truth": parity,
            "journey_gate_state": journey_state,
            "local_release_proof_status": local_release_proof,
            "provider_canary_status": canary_status,
            "closure_health_state": closure_state,
            "support_summary": support,
            "status_plane_final_claim": str(status_plane.get("whole_product_final_claim_status") or "").strip(),
        },
        "decision_board": {
            "current_launch_action": str(launch_decision.get("action") or "freeze_launch").strip(),
            "current_launch_reason": str(launch_decision.get("reason") or "").strip(),
            "launch_expand": {
                "state": "allowed" if launch_allowed else "blocked",
                "reason": "All measured launch gates are green." if launch_allowed else "Hold expansion until readiness, parity, local release proof, canary, closure, and support gates are all green.",
            },
            "freeze_launch": {
                "state": "active" if freeze_active else "available",
                "reason": str(launch_decision.get("reason") or "Freeze remains the fail-closed default when launch gates are incomplete.").strip(),
            },
            "canary": {
                "state": "ready" if canary_status == "Canary green on all active lanes" else "accumulating",
                "reason": canary_status or "Canary evidence is unavailable.",
                "next_decision": str(provider.get("next_decision") or "").strip(),
            },
            "rollback": {
                "state": "watch" if rollback_watch else "armed",
                "reason": "Rollback stays armed from release/support truth; watch is active when support closure or release health is not clear.",
            },
            "focus_shift": {
                "state": "queued_successor_wave",
                "reason": "Flagship closeout is complete; successor milestone 106 is the scoped Fleet packet slice.",
            },
        },
        "measured_rollout_loop": {
            "loop_status": "ready" if measured_loop_ready else "blocked",
            "cadence": "weekly",
            "required_decision_actions": [
                "launch_expand",
                "freeze_launch",
                "canary",
                "rollback",
                "focus_shift",
            ],
            "evidence_requirements": [
                "successor registry and queue item match package authority",
                "weekly pulse cites journey, local release proof, canary, and closure signals",
                "flagship readiness remains green before any launch expansion",
                "flagship parity remains at veteran_ready or gold_ready before the measured loop can steer launch decisions",
                "support packet counts stay clear for non-external closure work",
            ],
        },
        "risk_clusters": weekly_pulse.get("top_support_or_feedback_clusters") or [],
    }


def materialize(args: argparse.Namespace) -> Path:
    out_path = Path(args.out).resolve()
    source_paths = {
        "successor_registry": str(Path(args.successor_registry).resolve()),
        "queue_staging": str(Path(args.queue_staging).resolve()),
        "weekly_pulse": str(Path(args.weekly_pulse).resolve()),
        "flagship_readiness": str(Path(args.flagship_readiness).resolve()),
        "journey_gates": str(Path(args.journey_gates).resolve()),
        "support_packets": str(Path(args.support_packets).resolve()),
        "status_plane": str(Path(args.status_plane).resolve()),
    }
    payload = build_payload(
        registry=_read_yaml(Path(args.successor_registry).resolve()),
        queue=_read_yaml(Path(args.queue_staging).resolve()),
        weekly_pulse=_read_json(Path(args.weekly_pulse).resolve()),
        flagship_readiness=_read_json(Path(args.flagship_readiness).resolve()),
        journey_gates=_read_json(Path(args.journey_gates).resolve()),
        support_packets=_read_json(Path(args.support_packets).resolve()),
        status_plane=_read_yaml(Path(args.status_plane).resolve()),
        source_paths=source_paths,
    )
    write_text_atomic(out_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    repo_root = repo_root_for_published_path(out_path)
    if repo_root is not None:
        write_compile_manifest(repo_root)
    return out_path


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = materialize(args)
    print(f"wrote weekly governor packet: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
