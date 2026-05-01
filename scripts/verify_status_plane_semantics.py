#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from glob import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path("/docker/fleet")
PROJECT_CONFIG_DIR = ROOT / "config" / "projects"
GROUP_CONFIG_PATH = ROOT / "config" / "groups.yaml"
DEFAULT_STATUS_PLANE_PATH = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
FLAGSHIP_READINESS_PATH = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
DEPLOY_SCRIPT_PATH = ROOT / "scripts" / "deploy.sh"
DEFAULT_STATUS_JSON_SNAPSHOT_PATH = ROOT / "state" / "status-plane.verify.json"
VOLATILE_TOP_LEVEL_KEYS = {"generated_at", "source_public_status_generated_at"}
UTC = dt.timezone.utc
REBUILDER_STATE_DIR = Path(os.environ.get("FLEET_REBUILDER_STATE_DIR", str(ROOT / "state" / "rebuilder")))
REBUILDER_AUTOHEAL_STATE_DIR = REBUILDER_STATE_DIR / "autoheal"
RUNTIME_HEALING_EVENTS_PATH = REBUILDER_AUTOHEAL_STATE_DIR / "events.jsonl"
REBUILDER_EXTERNAL_PROOF_AUTOINGEST_STATE_DIR = REBUILDER_STATE_DIR / "external-proof-autoingest"
EXTERNAL_PROOF_AUTOINGEST_STATUS_PATH = REBUILDER_EXTERNAL_PROOF_AUTOINGEST_STATE_DIR / "status.json"
STAGE_ORDER = (
    "pre_repo_local_complete",
    "repo_local_complete",
    "package_canonical",
    "boundary_pure",
    "publicly_promoted",
)
STAGE_RANK = {name: index for index, name in enumerate(STAGE_ORDER)}


class StatusPlaneDriftError(RuntimeError):
    pass


def _flagship_claim_status() -> Dict[str, Any]:
    if not FLAGSHIP_READINESS_PATH.is_file():
        return {}
    try:
        payload = json.loads(FLAGSHIP_READINESS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    flagship_readiness_audit = dict(payload.get("flagship_readiness_audit") or {})
    coverage = dict(payload.get("coverage") or {})
    warning_keys = [
        str(item).strip()
        for item in (payload.get("warning_keys") or [])
        if str(item).strip()
    ]
    if not warning_keys:
        warning_keys = [
            str(item).strip()
            for item in (flagship_readiness_audit.get("warning_coverage_keys") or [])
            if str(item).strip()
        ]
    if not warning_keys and coverage:
        warning_keys = sorted(
            key for key, value in coverage.items() if str(key).strip() and str(value).strip().lower() == "warning"
        )
    if not warning_keys:
        readiness_planes = dict(payload.get("readiness_planes") or {})
        warning_keys = sorted(
            key
            for key, value in readiness_planes.items()
            if str(key).strip()
            and isinstance(value, dict)
            and str(value.get("status") or "").strip().lower() in {"warning", "missing"}
        )
    quality_policy = dict(payload.get("quality_policy") or {})
    return {
        "status": str(payload.get("status") or "").strip().lower() or "unknown",
        "warning_keys": warning_keys,
        "bar": str(quality_policy.get("bar") or "").strip() or "unknown",
        "whole_project_frontier_required": bool(quality_policy.get("whole_project_frontier_required")),
        "feedback_autofix_loop_required": bool(quality_policy.get("feedback_autofix_loop_required")),
        "accept_lowered_standards": bool(quality_policy.get("accept_lowered_standards")),
    }


def _load_project_config_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not PROJECT_CONFIG_DIR.is_dir():
        return rows
    for path in sorted(PROJECT_CONFIG_DIR.glob("*.yaml")):
        if path.name == "_index.yaml":
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            continue
        if payload.get("enabled") is False:
            continue
        project_id = str(payload.get("id") or "").strip()
        if not project_id:
            continue
        project_root = Path(str(payload.get("path") or "").strip())
        lifecycle = str(payload.get("lifecycle") or "dispatchable").strip() or "dispatchable"
        design_doc = str(payload.get("design_doc") or "").strip()
        deployment = dict(payload.get("deployment") or {})
        fallback_stage = (
            _infer_fallback_readiness_stage(
                project_id,
                project_root,
                lifecycle=lifecycle,
                design_doc=design_doc,
                deployment=deployment,
            )
            if project_root
            else "pre_repo_local_complete"
        )
        terminal_stage = "publicly_promoted"
        rows.append(
            {
                "id": project_id,
                "lifecycle": lifecycle,
                "runtime_status": "dispatch_pending",
                "readiness": {
                    "stage": fallback_stage,
                    "terminal_stage": terminal_stage,
                    "final_claim_allowed": fallback_stage == terminal_stage,
                    "warning_count": 0,
                },
                "deployment": {
                    "status": str(deployment.get("status") or ""),
                    "promotion_stage": str(deployment.get("promotion_stage") or ""),
                    "access_posture": str(deployment.get("access_posture") or deployment.get("visibility") or ""),
                },
            }
        )
    return rows


def _load_group_config_rows() -> List[Dict[str, Any]]:
    if not GROUP_CONFIG_PATH.is_file():
        return []
    payload = yaml.safe_load(GROUP_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return []
    rows: List[Dict[str, Any]] = []
    for item in sorted(payload.get("project_groups") or [], key=lambda row: str(dict(row or {}).get("id") or "")):
        row = dict(item or {})
        group_id = str(row.get("id") or "").strip()
        if not group_id:
            continue
        deployment = dict(row.get("deployment") or {})
        public_surface = dict(deployment.get("public_surface") or {})
        status = str(public_surface.get("status") or "").strip()
        promotion_stage = str(public_surface.get("promotion_stage") or "").strip()
        access_posture = str(public_surface.get("access_posture") or "").strip() or status
        values = {
            status.lower(),
            promotion_stage.lower(),
            access_posture.lower(),
        }
        publicly_promoted = any(
            value in {"public", "public_preview", "promoted_preview", "publicly_promoted"} for value in values if value
        )
        rows.append(
            {
                "id": group_id,
                "lifecycle": str(row.get("lifecycle") or "").strip(),
                "phase": str(row.get("phase") or "active").strip() or "active",
                "deployment": {
                    "status": status,
                    "promotion_stage": promotion_stage,
                    "access_posture": access_posture,
                },
                "deployment_readiness": {
                    "publicly_promoted": publicly_promoted,
                    "blocking_owner_projects": [],
                },
            }
        )
    return rows


def _load_json_file(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _fleet_boundary_proof_passed(published_dir: Path) -> bool:
    compile_manifest = _load_json_file(published_dir / "compile.manifest.json")
    if not compile_manifest:
        return False
    if not bool(compile_manifest.get("dispatchable_truth_ready")):
        return False
    stages = dict(compile_manifest.get("stages") or {})
    required_stages = (
        "design_compile",
        "policy_compile",
        "execution_compile",
        "package_compile",
        "capacity_compile",
    )
    if any(stages.get(stage) is not True for stage in required_stages):
        return False
    artifact_inventory = {str(item or "").strip() for item in (compile_manifest.get("artifacts") or [])}
    required_artifacts = {
        "STATUS_PLANE.generated.yaml",
        "PROGRESS_REPORT.generated.json",
        "PROGRESS_HISTORY.generated.json",
        "SUPPORT_CASE_PACKETS.generated.json",
        "JOURNEY_GATES.generated.json",
    }
    if not required_artifacts.issubset(artifact_inventory):
        return False
    support_packets = _load_json_file(published_dir / "SUPPORT_CASE_PACKETS.generated.json")
    if str(support_packets.get("contract_name") or "").strip() != "fleet.support_case_packets":
        return False
    if str(support_packets.get("schema_version") or "").strip() != "1":
        return False
    if not str(support_packets.get("generated_at") or "").strip():
        return False
    return isinstance(support_packets.get("summary") or {}, dict)


def _infer_fallback_readiness_stage(
    project_id: str,
    project_root: Path,
    *,
    lifecycle: str = "dispatchable",
    design_doc: str = "",
    deployment: Dict[str, Any] | None = None,
) -> str:
    published_dir = project_root / ".codex-studio" / "published"
    if not published_dir.is_dir():
        return "pre_repo_local_complete"

    def _proof_passed(payload: Dict[str, Any]) -> bool:
        return str(payload.get("status") or "").strip().lower() in {"pass", "passed", "ready"}

    deployment_row = dict(deployment or {})

    def _is_public_deployment(row: Dict[str, Any]) -> bool:
        values = {
            str(row.get("status") or "").strip().lower(),
            str(row.get("access_posture") or row.get("visibility") or "").strip().lower(),
            str(row.get("promotion_stage") or "").strip().lower(),
        }
        return any(
            value in {"public", "public_preview", "promoted_preview", "publicly_promoted"}
            for value in values
            if value
        )

    if project_id == "hub-registry":
        release_channel = _load_json_file(published_dir / "RELEASE_CHANNEL.generated.json")
        if release_channel:
            release_status = str(release_channel.get("status") or "").strip().lower()
            release_proof_status = str(((release_channel.get("releaseProof") or {}).get("status") or "")).strip().lower()
            if release_status in {"published", "publishable"} and release_proof_status in {"pass", "passed"}:
                return "boundary_pure"
    elif project_id == "core":
        import_parity = _load_json_file(published_dir / "IMPORT_PARITY_CERTIFICATION.generated.json")
        if _proof_passed(import_parity):
            return "boundary_pure"
    elif project_id == "media-factory":
        media_local_release_proof = _load_json_file(published_dir / "MEDIA_LOCAL_RELEASE_PROOF.generated.json")
        artifact_publication_certification = _load_json_file(published_dir / "ARTIFACT_PUBLICATION_CERTIFICATION.generated.json")
        if _proof_passed(media_local_release_proof) and _proof_passed(artifact_publication_certification):
            return "boundary_pure"
    elif project_id == "ui-kit":
        ui_kit_local_release_proof = _load_json_file(published_dir / "UI_KIT_LOCAL_RELEASE_PROOF.generated.json")
        if _proof_passed(ui_kit_local_release_proof):
            return "boundary_pure"
    elif project_id == "hub":
        hub_local_release_proof = _load_json_file(published_dir / "HUB_LOCAL_RELEASE_PROOF.generated.json")
        hub_campaign_os_proof = _load_json_file(published_dir / "HUB_CAMPAIGN_OS_LOCAL_PROOF.generated.json")
        if _is_public_deployment(deployment_row) and _proof_passed(hub_local_release_proof) and _proof_passed(hub_campaign_os_proof):
            return "publicly_promoted"
    elif project_id == "mobile":
        mobile_local_release_proof = _load_json_file(published_dir / "MOBILE_LOCAL_RELEASE_PROOF.generated.json")
        if _is_public_deployment(deployment_row) and _proof_passed(mobile_local_release_proof):
            return "publicly_promoted"
    elif project_id == "ui":
        ui_flagship_release_gate = _load_json_file(published_dir / "UI_FLAGSHIP_RELEASE_GATE.generated.json")
        ui_local_release_proof = _load_json_file(published_dir / "UI_LOCAL_RELEASE_PROOF.generated.json")
        if _is_public_deployment(deployment_row) and _proof_passed(ui_flagship_release_gate) and _proof_passed(ui_local_release_proof):
            return "publicly_promoted"
    elif project_id == "fleet":
        if _fleet_boundary_proof_passed(published_dir):
            return "boundary_pure"
    try:
        from admin import readiness as readiness_module
    except Exception:
        readiness_module = None
        root_path = str(ROOT)
        if root_path not in sys.path:
            sys.path.insert(0, root_path)
        try:
            from admin import readiness as readiness_module
        except Exception:
            readiness_module = None

    if readiness_module is not None:
        compile_summary = readiness_module.studio_compile_summary(project_root, design_doc)
        compile_health = readiness_module.compile_health(compile_summary, lifecycle)
        if str(compile_health.get("status") or "").strip().lower() in {"ready", "not_required"}:
            return "package_canonical"

    generated_artifacts = list(glob(str(published_dir / "*.generated.*")))
    if generated_artifacts:
        return "repo_local_complete"
    return "pre_repo_local_complete"


def _recompute_readiness_counts(projects: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {key: 0 for key in STAGE_ORDER}
    for project in projects:
        readiness = dict(project.get("readiness") or {})
        stage = str(readiness.get("stage") or "pre_repo_local_complete").strip() or "pre_repo_local_complete"
        if stage not in counts:
            stage = "pre_repo_local_complete"
        counts[stage] += 1
    return counts


def _ensure_project_inventory(admin_status: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(admin_status or {})
    projects = list(normalized.get("projects") or [])
    groups = list(normalized.get("groups") or [])
    fallback_projects = _load_project_config_rows()
    fallback_groups = _load_group_config_rows()
    fallback_by_id = {
        str(item.get("id") or "").strip(): dict(item.get("readiness") or {})
        for item in fallback_projects
        if str(item.get("id") or "").strip()
    }
    inventory_changed = False

    if projects:
        upgraded_projects: List[Dict[str, Any]] = []
        stage_upgraded = False
        for row in projects:
            project_row = dict(row or {})
            project_id = str(project_row.get("id") or "").strip()
            readiness = dict(project_row.get("readiness") or {})
            fallback_readiness = dict(fallback_by_id.get(project_id) or {})
            current_stage = str(readiness.get("stage") or "pre_repo_local_complete").strip() or "pre_repo_local_complete"
            fallback_stage = str(fallback_readiness.get("stage") or "").strip()
            fallback_terminal_stage = str(fallback_readiness.get("terminal_stage") or "").strip()
            fallback_final_claim_allowed = bool(fallback_readiness.get("final_claim_allowed"))
            readiness_changed = False
            if fallback_stage and STAGE_RANK.get(fallback_stage, -1) > STAGE_RANK.get(current_stage, -1):
                readiness["stage"] = fallback_stage
                readiness_changed = True
            if fallback_terminal_stage and not str(readiness.get("terminal_stage") or "").strip():
                readiness["terminal_stage"] = fallback_terminal_stage
                readiness_changed = True
            if fallback_final_claim_allowed and not bool(readiness.get("final_claim_allowed")):
                readiness["final_claim_allowed"] = True
                readiness_changed = True
            if readiness_changed:
                project_row["readiness"] = readiness
                stage_upgraded = True
            upgraded_projects.append(project_row)
        if stage_upgraded:
            normalized["projects"] = upgraded_projects
            inventory_changed = True
    elif fallback_projects:
        normalized["projects"] = fallback_projects
        inventory_changed = True

    if not groups and fallback_groups:
        normalized["groups"] = fallback_groups
        inventory_changed = True

    public_status = dict(normalized.get("public_status") or {})
    readiness_summary = dict(public_status.get("readiness_summary") or {})
    readiness_summary["counts"] = _recompute_readiness_counts(list(normalized.get("projects") or []))
    final_claim_ready_project_ids = sorted(
        str(project.get("id") or "").strip()
        for project in (normalized.get("projects") or [])
        if str(project.get("id") or "").strip()
        and bool(dict(project.get("readiness") or {}).get("final_claim_allowed"))
    )
    readiness_summary["final_claim_ready"] = len(final_claim_ready_project_ids)
    readiness_summary["final_claim_ready_project_ids"] = final_claim_ready_project_ids
    flagship_claim = _flagship_claim_status()
    readiness_summary["whole_product_final_claim_status"] = str(flagship_claim.get("status") or "unknown")
    readiness_summary["whole_product_final_claim_bar"] = str(flagship_claim.get("bar") or "unknown")
    readiness_summary["whole_product_final_claim_whole_project_frontier_required"] = bool(
        flagship_claim.get("whole_project_frontier_required")
    )
    readiness_summary["whole_product_final_claim_feedback_autofix_loop_required"] = bool(
        flagship_claim.get("feedback_autofix_loop_required")
    )
    readiness_summary["whole_product_final_claim_accept_lowered_standards"] = bool(
        flagship_claim.get("accept_lowered_standards")
    )
    readiness_summary["whole_product_final_claim_ready"] = int(
        str(flagship_claim.get("status") or "").strip().lower() in {"pass", "passed", "ready"}
        and str(flagship_claim.get("bar") or "").strip().lower() == "top_flagship_grade"
        and bool(flagship_claim.get("whole_project_frontier_required"))
        and bool(flagship_claim.get("feedback_autofix_loop_required"))
        and not bool(flagship_claim.get("accept_lowered_standards"))
    )
    readiness_summary["whole_product_final_claim_warning_keys"] = [
        str(item).strip()
        for item in (flagship_claim.get("warning_keys") or [])
        if str(item).strip()
    ]
    readiness_summary["warning_count"] = len(readiness_summary["whole_product_final_claim_warning_keys"])
    public_status["readiness_summary"] = readiness_summary
    normalized["public_status"] = public_status
    return normalized


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


def _normalize_external_proof_autoingest(payload: Any) -> Dict[str, Any]:
    normalized = dict(payload or {})
    normalized.pop("generated_at", None)
    if str(normalized.get("current_state") or "").strip() == "cooldown":
        normalized["last_detail"] = "cooldown_active"
        summary = dict(normalized.get("summary") or {})
        summary["alert_reason"] = "cooldown_active"
        normalized["summary"] = summary
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


def _external_proof_autoingest_from_state() -> Dict[str, Any]:
    payload = _load_json_mapping(EXTERNAL_PROOF_AUTOINGEST_STATUS_PATH)
    if not payload:
        return {}
    current_state = str(payload.get("current_state") or "unknown").strip() or "unknown"
    last_detail = str(payload.get("last_detail") or "").strip()
    alert_state = "tracking"
    alert_reason = "Waiting for a returned host proof bundle."
    recommended_action = "Return the Windows host proof bundle to the published external-proof commands directory."
    if current_state in {"failed", "blocked", "waiting_for_commands_dir"}:
        alert_state = "action_needed"
        alert_reason = last_detail or "External proof auto-ingest is blocked."
        recommended_action = "Fix the rebuilder proof watcher or rerun finalize-external-host-proof.sh manually."
    elif current_state == "ingested":
        alert_state = "healthy"
        alert_reason = "The latest returned host proof bundle has already been ingested."
        recommended_action = "No action required until a newer host proof bundle arrives."
    elif current_state == "ingesting":
        alert_reason = "A returned host proof bundle is being finalized now."
        recommended_action = "Wait for the rebuilder finalize flow to finish."
    elif current_state == "cooldown":
        alert_reason = last_detail or "External proof auto-ingest is cooling down before retry."
        recommended_action = "Wait for the retry window or inspect the last failure detail."
    return {
        "generated_at": str(payload.get("generated_at") or "").strip(),
        "enabled": str(os.environ.get("FLEET_EXTERNAL_PROOF_AUTOINGEST_ENABLED", "true") or "").strip().lower() in {"1", "true", "yes", "on"},
        "current_state": current_state,
        "commands_dir": str(payload.get("commands_dir") or "").strip(),
        "observed_bundle_count": max(0, int(payload.get("observed_bundle_count") or 0)),
        "last_attempt_at": str(payload.get("last_attempt_at") or "").strip(),
        "last_success_at": str(payload.get("last_success_at") or "").strip(),
        "last_result": str(payload.get("last_result") or "").strip(),
        "last_detail": last_detail,
        "summary": {
            "alert_state": alert_state,
            "alert_reason": alert_reason,
            "recommended_action": recommended_action,
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


def _resolve_external_proof_autoingest(snapshot_external_proof_autoingest: Any) -> Dict[str, Any]:
    snapshot = dict(snapshot_external_proof_autoingest or {})
    local = _external_proof_autoingest_from_state()
    if not local:
        return snapshot
    snapshot_generated = _parse_iso(snapshot.get("generated_at"))
    local_generated = _parse_iso(local.get("generated_at"))
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

    readiness_summary = dict(public_status.get("readiness_summary") or {})
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
        "readiness_summary": readiness_summary,
        "final_claim_ready": int(readiness_summary.get("final_claim_ready") or 0),
        "final_claim_ready_project_ids": list(readiness_summary.get("final_claim_ready_project_ids") or []),
        "whole_product_final_claim_status": readiness_summary.get("whole_product_final_claim_status"),
        "whole_product_final_claim_bar": readiness_summary.get("whole_product_final_claim_bar"),
        "whole_product_final_claim_whole_project_frontier_required": bool(
            readiness_summary.get("whole_product_final_claim_whole_project_frontier_required")
        ),
        "whole_product_final_claim_feedback_autofix_loop_required": bool(
            readiness_summary.get("whole_product_final_claim_feedback_autofix_loop_required")
        ),
        "whole_product_final_claim_accept_lowered_standards": bool(
            readiness_summary.get("whole_product_final_claim_accept_lowered_standards")
        ),
        "whole_product_final_claim_ready": int(readiness_summary.get("whole_product_final_claim_ready") or 0),
        "whole_product_final_claim_warning_keys": list(
            readiness_summary.get("whole_product_final_claim_warning_keys") or []
        ),
        "dispatch_policy": dict(public_status.get("dispatch_policy") or {}),
        "support_summary": dict(public_status.get("support_summary") or {}),
        "publish_readiness": dict(public_status.get("publish_readiness") or {}),
        "runtime_healing": _normalize_runtime_healing(_resolve_runtime_healing(public_status.get("runtime_healing") or {})),
        "external_proof_autoingest": _normalize_external_proof_autoingest(
            _resolve_external_proof_autoingest(public_status.get("external_proof_autoingest") or {})
        ),
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
        actual_value = actual[key]
        if key == "runtime_healing":
            actual_value = _normalize_runtime_healing(actual_value)
        elif key == "external_proof_autoingest":
            actual_value = _normalize_external_proof_autoingest(actual_value)
        if expected[key] != actual_value:
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
    admin_status = _ensure_project_inventory(admin_status)
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
