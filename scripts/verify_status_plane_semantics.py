#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path("/docker/fleet")
DEFAULT_STATUS_PLANE_PATH = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEPLOY_SCRIPT_PATH = ROOT / "scripts" / "deploy.sh"
DEFAULT_STATUS_JSON_SNAPSHOT_PATH = ROOT / "state" / "status-plane.verify.json"
VOLATILE_TOP_LEVEL_KEYS = {"generated_at", "source_public_status_generated_at"}
UTC = dt.timezone.utc
REBUILDER_STATE_DIR = Path(os.environ.get("FLEET_REBUILDER_STATE_DIR", str(ROOT / "state" / "rebuilder")))
REBUILDER_AUTOHEAL_STATE_DIR = REBUILDER_STATE_DIR / "autoheal"
RUNTIME_HEALING_EVENTS_PATH = REBUILDER_AUTOHEAL_STATE_DIR / "events.jsonl"


class StatusPlaneDriftError(RuntimeError):
    pass


def _normalize_stage(stage: Any) -> str:
    return str(stage or "pre_repo_local_complete").strip()


def _normalize_runtime_status(status: Any) -> str:
    normalized = str(status or "").strip()
    if normalized in {
        "dispatch_pending",
        "waiting_capacity",
        "awaiting_account",
        "cooldown",
        "queue_refilling",
        "review_fix",
        "awaiting_pr",
        "review_requested",
        "awaiting_first_review",
        "review_light_pending",
        "jury_review_pending",
        "jury_rework_required",
        "core_rescue_pending",
        "manual_hold",
        "blocked_credit_burn_disabled",
        "local_review",
    }:
        return "dispatch_pending"
    return normalized


def _normalize_runtime_healing(payload: Any) -> Dict[str, Any]:
    normalized = dict(payload or {})
    normalized.pop("generated_at", None)
    return normalized


def _parse_iso(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_json_mapping(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _load_jsonl_rows(path: Path, *, limit: int = 24) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    for line in reversed(lines):
        clean = str(line or "").strip()
        if not clean:
            continue
        try:
            payload = json.loads(clean)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(dict(payload))
        if len(rows) >= limit:
            break
    return rows


def _runtime_healing_from_autoheal_state() -> Dict[str, Any]:
    if not REBUILDER_AUTOHEAL_STATE_DIR.is_dir():
        return {}

    service_rows: List[Dict[str, Any]] = []
    for path in sorted(REBUILDER_AUTOHEAL_STATE_DIR.glob("*.status.json")):
        payload = _load_json_mapping(path)
        if not payload:
            continue
        service = str(payload.get("service") or path.name.replace(".status.json", "")).strip()
        if not service:
            continue
        current_state = str(payload.get("current_state") or "unknown").strip() or "unknown"
        service_rows.append(
            {
                "service": service,
                "current_state": current_state,
                "observed_status": str(payload.get("observed_status") or "").strip(),
                "consecutive_failures": int(payload.get("consecutive_failures") or 0),
                "cooldown_active": bool(payload.get("cooldown_active")),
                "cooldown_remaining_seconds": max(0, int(payload.get("cooldown_remaining_seconds") or 0)),
                "last_result": str(payload.get("last_result") or "").strip(),
                "last_detail": str(payload.get("last_detail") or "").strip(),
                "last_restart_at": str(payload.get("last_restart_at") or "").strip(),
                "generated_at": str(payload.get("generated_at") or "").strip(),
                "escalation_threshold": max(1, int(payload.get("escalation_threshold") or 1)),
                "restart_window_count": max(0, int(payload.get("restart_window_count") or 0)),
                "total_restarts": max(0, int(payload.get("total_restarts") or 0)),
            }
        )

    recent_events = _load_jsonl_rows(RUNTIME_HEALING_EVENTS_PATH, limit=24)
    for event in recent_events:
        event["service"] = str(event.get("service") or "").strip()
        event["event"] = str(event.get("event") or "").strip()
        event["status"] = str(event.get("status") or "").strip()
        event["detail"] = str(event.get("detail") or "").strip()
        event["at"] = str(event.get("at") or "").strip()
        event["consecutive_failures"] = int(event.get("consecutive_failures") or 0)
        event["cooldown_remaining_seconds"] = max(0, int(event.get("cooldown_remaining_seconds") or 0))

    escalated_services = [
        row
        for row in service_rows
        if str(row.get("current_state") or "") in {"escalation_required", "restart_failed"}
    ]
    degraded_services = [
        row
        for row in service_rows
        if str(row.get("current_state") or "") in {"cooldown", "restarting", "observed_unhealthy", "escalation_required", "restart_failed"}
        or bool(row.get("cooldown_active"))
    ]
    cooldown_services = [row for row in service_rows if bool(row.get("cooldown_active"))]
    last_event = recent_events[0] if recent_events else {}
    last_recovery = next(
        (event for event in recent_events if str(event.get("event") or "") == "restart_recovered"),
        {},
    )

    alert_state = "healthy"
    alert_reason = "No runtime healing drift is currently recorded."
    recommended_action = "Keep the bounded auto-heal loop enabled and review the weekly healer history."
    if escalated_services:
        service_labels = ", ".join(str(item.get("service") or "") for item in escalated_services[:3])
        alert_state = "action_needed"
        alert_reason = f"Runtime self-healing escalated for {service_labels or 'one or more services'}."
        recommended_action = "Open Housekeeping, inspect the escalated service, and freeze new change pressure until the root cause is understood."
    elif degraded_services:
        service_labels = ", ".join(str(item.get("service") or "") for item in degraded_services[:3])
        alert_state = "degraded"
        alert_reason = f"Runtime healing is actively compensating for {service_labels or 'recent service drift'}."
        recommended_action = "Verify the unhealthy service, fail streak, and cooldown posture before assuming the stack is steady."

    candidates: List[dt.datetime] = []
    for row in service_rows:
        parsed = _parse_iso(row.get("generated_at"))
        if parsed is not None:
            candidates.append(parsed)
    for event in recent_events:
        parsed = _parse_iso(event.get("at"))
        if parsed is not None:
            candidates.append(parsed)
    generated_at = max(candidates).replace(microsecond=0).isoformat().replace("+00:00", "Z") if candidates else ""

    return {
        "generated_at": generated_at,
        "enabled": True,
        "event_log_present": RUNTIME_HEALING_EVENTS_PATH.is_file(),
        "services": service_rows,
        "recent_events": recent_events,
        "summary": {
            "service_count": len(service_rows),
            "degraded_service_count": len(degraded_services),
            "cooldown_active_count": len(cooldown_services),
            "escalated_service_count": len(escalated_services),
            "recent_restart_count": 0,
            "alert_state": alert_state,
            "alert_reason": alert_reason,
            "recommended_action": recommended_action,
            "last_event_at": str(last_event.get("at") or "").strip(),
            "last_event_service": str(last_event.get("service") or "").strip(),
            "last_event_kind": str(last_event.get("event") or "").strip(),
            "last_event_detail": str(last_event.get("detail") or "").strip(),
            "last_recovered_service": str(last_recovery.get("service") or "").strip(),
            "last_recovered_at": str(last_recovery.get("at") or "").strip(),
        },
    }


def _resolve_runtime_healing(snapshot_runtime_healing: Any) -> Dict[str, Any]:
    snapshot = dict(snapshot_runtime_healing or {})
    local = _runtime_healing_from_autoheal_state()
    if not local:
        return snapshot

    snapshot_alert = str((snapshot.get("summary") or {}).get("alert_state") or "").strip().lower()
    local_alert = str((local.get("summary") or {}).get("alert_state") or "").strip().lower()
    snapshot_generated = _parse_iso(snapshot.get("generated_at"))
    local_generated = _parse_iso(local.get("generated_at"))

    if snapshot_alert != "action_needed":
        return snapshot
    if local_alert != "healthy":
        return snapshot
    if snapshot_generated is not None and local_generated is not None and local_generated <= snapshot_generated:
        return snapshot
    return local


def build_expected_status_plane(admin_status: Dict[str, Any]) -> Dict[str, Any]:
    public_status = dict(admin_status.get("public_status") or {})
    projects = list(admin_status.get("projects") or [])
    groups = list(admin_status.get("groups") or [])

    project_rows: List[Dict[str, Any]] = []
    for project in sorted(projects, key=lambda item: str(item.get("id") or "")):
        readiness = dict(project.get("readiness") or {})
        deployment = dict(project.get("deployment") or {})
        project_rows.append(
            {
                "id": str(project.get("id") or ""),
                "lifecycle": str(project.get("lifecycle") or ""),
                "runtime_status": _normalize_runtime_status(project.get("runtime_status")),
                "readiness_stage": _normalize_stage(readiness.get("stage")),
                "readiness_terminal_stage": str(readiness.get("terminal_stage") or ""),
                "readiness_final_claim_allowed": bool(readiness.get("final_claim_allowed")),
                "readiness_warning_count": int(readiness.get("warning_count") or 0),
                "deployment_status": str(deployment.get("status") or ""),
                "deployment_promotion_stage": str(deployment.get("promotion_stage") or ""),
                "deployment_access_posture": str(deployment.get("access_posture") or deployment.get("visibility") or ""),
            }
        )

    group_rows: List[Dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: str(item.get("id") or "")):
        deployment = dict(group.get("deployment") or {})
        deployment_readiness = dict(group.get("deployment_readiness") or {})
        blocking_owner_projects = sorted({str(item).strip() for item in (deployment_readiness.get("blocking_owner_projects") or []) if str(item).strip()})
        group_rows.append(
            {
                "id": str(group.get("id") or ""),
                "lifecycle": str(group.get("lifecycle") or ""),
                "phase": str(group.get("phase") or ""),
                "deployment_status": str(deployment.get("status") or ""),
                "deployment_promotion_stage": str(deployment.get("promotion_stage") or ""),
                "deployment_access_posture": str(deployment.get("access_posture") or deployment.get("visibility") or ""),
                "publicly_promoted": bool(deployment_readiness.get("publicly_promoted")),
                "blocking_owner_projects": blocking_owner_projects,
            }
        )

    return {
        "contract_name": "fleet.status_plane",
        "schema_version": 1,
        "generated_at": str(admin_status.get("generated_at") or ""),
        "source_public_status_generated_at": str(public_status.get("generated_at") or ""),
        "mission_snapshot": dict(public_status.get("mission_snapshot") or {}),
        "queue_forecast": dict(public_status.get("queue_forecast") or {}),
        "capacity_forecast": dict(public_status.get("capacity_forecast") or {}),
        "blocker_forecast": dict(public_status.get("blocker_forecast") or {}),
        "deployment_posture": dict(public_status.get("deployment_posture") or {}),
        "readiness_summary": dict(public_status.get("readiness_summary") or {}),
        "dispatch_policy": dict(public_status.get("dispatch_policy") or {}),
        "support_summary": dict(public_status.get("support_summary") or {}),
        "publish_readiness": dict(public_status.get("publish_readiness") or {}),
        "runtime_healing": _normalize_runtime_healing(_resolve_runtime_healing(public_status.get("runtime_healing") or {})),
        "projects": project_rows,
        "groups": group_rows,
    }


def compare_status_plane(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    expected_keys = set(expected.keys())
    actual_keys = set(actual.keys())
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        if missing:
            errors.append(f"missing top-level keys: {', '.join(missing)}")
        if extra:
            errors.append(f"unexpected top-level keys: {', '.join(extra)}")

    for key in sorted(expected_keys & actual_keys):
        if key in VOLATILE_TOP_LEVEL_KEYS:
            continue
        if expected[key] != actual[key]:
            errors.append(f"mismatch at {key}")
    return errors


def load_status_plane(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise StatusPlaneDriftError(f"status-plane artifact is missing: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise StatusPlaneDriftError(f"status-plane artifact is not a mapping: {path}")
    return payload


def load_admin_status(status_json_path: Path | None, *, use_default_snapshot: bool = True) -> Dict[str, Any]:
    snapshot_path = status_json_path
    if use_default_snapshot and snapshot_path is None and DEFAULT_STATUS_JSON_SNAPSHOT_PATH.is_file():
        snapshot_path = DEFAULT_STATUS_JSON_SNAPSHOT_PATH

    if snapshot_path is not None:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise StatusPlaneDriftError("status-json payload must be an object")
        return payload

    if not DEPLOY_SCRIPT_PATH.is_file():
        raise StatusPlaneDriftError(f"cannot find deploy helper script at {DEPLOY_SCRIPT_PATH}")

    result = subprocess.run(
        ["bash", str(DEPLOY_SCRIPT_PATH), "admin-status"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise StatusPlaneDriftError(f"failed to load live admin status via deploy.sh admin-status: {stderr or 'unknown error'}")

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise StatusPlaneDriftError(f"admin-status output is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StatusPlaneDriftError("admin-status payload must be an object")
    return payload


def run_verification(status_plane_path: Path, status_json_path: Path | None) -> None:
    actual = load_status_plane(status_plane_path)
    admin_status = load_admin_status(status_json_path, use_default_snapshot=True)
    expected = build_expected_status_plane(admin_status)
    errors = compare_status_plane(expected, actual)
    if errors:
        bullets = "\n".join(f"- {item}" for item in errors)
        raise StatusPlaneDriftError(
            "STATUS_PLANE.generated.yaml drifted from live readiness/deployment semantics:\n"
            f"{bullets}"
        )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify STATUS_PLANE.generated.yaml against Fleet live readiness/deployment semantics.")
    parser.add_argument(
        "--status-plane",
        default=str(DEFAULT_STATUS_PLANE_PATH),
        help="path to STATUS_PLANE.generated.yaml",
    )
    parser.add_argument(
        "--status-json",
        default=None,
        help="optional path to an admin status JSON payload (used for tests/offline verification)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    status_plane_path = Path(args.status_plane).resolve()
    status_json_path = Path(args.status_json).resolve() if args.status_json else None
    try:
        run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)
    except StatusPlaneDriftError as exc:
        print(f"status-plane verification failed: {exc}", file=sys.stderr)
        return 1
    print("status-plane verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
