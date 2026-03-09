import datetime as dt
import html
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8092"))
APP_TITLE = "Codex Fleet Admin"
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
ACCOUNTS_PATH = pathlib.Path(os.environ.get("FLEET_ACCOUNTS_PATH", "/app/config/accounts.yaml"))
DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", "/var/lib/codex-fleet/fleet.db"))
CODEX_HOME_ROOT = pathlib.Path(os.environ.get("FLEET_CODEX_HOME_ROOT", "/var/lib/codex-fleet/codex-homes"))
GROUP_ROOT = pathlib.Path(os.environ.get("FLEET_GROUP_ROOT", str(DB_PATH.parent / "groups")))
AUDITOR_URL = os.environ.get("FLEET_AUDITOR_URL", "http://fleet-auditor:8093")
DOCKER_ROOT = pathlib.Path("/docker")
STUDIO_PUBLISHED_DIR = ".codex-studio/published"
SOURCE_BACKLOG_OPEN_STATUS = "source_backlog_open"
CONFIGURED_QUEUE_COMPLETE_STATUS = "queue_exhausted"
QUEUE_OVERLAY_FILENAME = "QUEUE.generated.yaml"
SPARK_MODEL = "gpt-5.3-codex-spark"
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
DEFAULT_SINGLETON_GROUP_ROLES = ["auditor", "project_manager"]
DEFAULT_CAPTAIN_POLICY = {
    "priority": 100,
    "service_floor": 1,
    "shed_order": 100,
    "preemption_policy": "slice_boundary",
    "admission_policy": "normal",
}

app = FastAPI(title=APP_TITLE)


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(ts: Optional[dt.datetime]) -> Optional[str]:
    return ts.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z") if ts else None


def parse_iso(value: Optional[str]) -> Optional[dt.datetime]:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(value).astimezone(UTC)
    except ValueError:
        return None


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_yaml(path: pathlib.Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    tmp_path.replace(path)


def normalized_captain_policy(raw_policy: Any, *, default_service_floor: int = 1) -> Dict[str, Any]:
    policy = dict(DEFAULT_CAPTAIN_POLICY)
    if isinstance(raw_policy, dict):
        policy.update(raw_policy)
    policy["priority"] = int(policy.get("priority") or DEFAULT_CAPTAIN_POLICY["priority"])
    policy["service_floor"] = max(0, int(policy.get("service_floor") or default_service_floor))
    policy["shed_order"] = max(0, int(policy.get("shed_order") or DEFAULT_CAPTAIN_POLICY["shed_order"]))
    policy["preemption_policy"] = str(policy.get("preemption_policy") or DEFAULT_CAPTAIN_POLICY["preemption_policy"]).strip() or DEFAULT_CAPTAIN_POLICY["preemption_policy"]
    policy["admission_policy"] = str(policy.get("admission_policy") or DEFAULT_CAPTAIN_POLICY["admission_policy"]).strip() or DEFAULT_CAPTAIN_POLICY["admission_policy"]
    return policy


def normalized_project_groups(projects: List[Dict[str, Any]], groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    known_projects = {str(project.get("id", "")).strip() for project in projects if str(project.get("id", "")).strip()}
    assigned: set[str] = set()
    normalized: List[Dict[str, Any]] = []
    used_ids: set[str] = set()

    for raw_group in groups or []:
        group = dict(raw_group or {})
        group_id = str(group.get("id", "")).strip()
        if not group_id or group_id in used_ids:
            continue
        cleaned_projects: List[str] = []
        for raw_project_id in group.get("projects") or []:
            project_id = str(raw_project_id).strip()
            if not project_id or project_id not in known_projects or project_id in assigned:
                continue
            cleaned_projects.append(project_id)
            assigned.add(project_id)
        group["projects"] = cleaned_projects
        default_floor = len(cleaned_projects) if str(group.get("mode", "") or "").strip().lower() == "lockstep" and cleaned_projects else 1
        group["captain"] = normalized_captain_policy(group.get("captain"), default_service_floor=default_floor)
        used_ids.add(group_id)
        normalized.append(group)

    for project in projects:
        project_id = str(project.get("id", "")).strip()
        if not project_id or project_id in assigned:
            continue
        group_id = f"solo-{project_id}"
        suffix = 2
        while group_id in used_ids:
            group_id = f"solo-{project_id}-{suffix}"
            suffix += 1
        normalized.append(
            {
                "id": group_id,
                "projects": [project_id],
                "mode": "singleton",
                "contract_sets": [],
                "milestone_source": {},
                "group_roles": list(DEFAULT_SINGLETON_GROUP_ROLES),
                "captain": normalized_captain_policy({}, default_service_floor=1),
                "auto_created": True,
            }
        )
        used_ids.add(group_id)
        assigned.add(project_id)
    return normalized


def normalize_config() -> Dict[str, Any]:
    fleet = load_yaml(CONFIG_PATH)
    accounts_cfg = load_yaml(ACCOUNTS_PATH)
    fleet.setdefault("policies", {})
    fleet.setdefault("spider", {})
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet["accounts"] = accounts_cfg.get("accounts", {}) or {}
    fleet["project_groups"] = normalized_project_groups(fleet["projects"], fleet["project_groups"])
    for group in fleet["project_groups"]:
        group.setdefault("projects", [])
        group.setdefault("mode", "independent")
        group.setdefault("contract_sets", [])
        group.setdefault("milestone_source", {})
        group.setdefault("group_roles", [])
        default_floor = len(group.get("projects") or []) if str(group.get("mode", "") or "").strip().lower() == "lockstep" and (group.get("projects") or []) else 1
        group["captain"] = normalized_captain_policy(group.get("captain"), default_service_floor=default_floor)
    for project in fleet["projects"]:
        project.setdefault("enabled", True)
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("verify_cmd", "")
        project.setdefault("design_doc", "")
        project.setdefault("accounts", [])
        project.setdefault("account_policy", {})
        project.setdefault("queue", [])
        project.setdefault("queue_sources", [])
        project.setdefault("runner", {})
        project["runner"].setdefault("sandbox", "workspace-write")
        project["runner"].setdefault("approval_policy", "never")
        project["runner"].setdefault("exec_timeout_seconds", 5400)
        project["runner"].setdefault("verify_timeout_seconds", 1800)
        project["runner"].setdefault("config_overrides", [])
        project["runner"].setdefault("always_continue", True)
        project["runner"].setdefault("avoid_permission_escalation", True)
        policy = project["account_policy"]
        policy.setdefault("preferred_accounts", list(project.get("accounts") or []))
        policy.setdefault("burst_accounts", [])
        policy.setdefault("reserve_accounts", [])
        policy.setdefault("allow_chatgpt_accounts", True)
        policy.setdefault("allow_api_accounts", True)
        policy.setdefault("spark_enabled", True)
    return fleet


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(name: str) -> bool:
    if not DB_PATH.exists():
        return False
    with db() as conn:
        row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


def group_runtime_rows() -> Dict[str, Dict[str, Any]]:
    if not table_exists("group_runtime"):
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM group_runtime ORDER BY group_id").fetchall()
    return {str(row["group_id"]): dict(row) for row in rows}


def project_cfg(config: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    for project in config.get("projects", []):
        if project.get("id") == project_id:
            return project
    raise KeyError(project_id)


def group_cfg(config: Dict[str, Any], group_id: str) -> Dict[str, Any]:
    for group in config.get("project_groups") or []:
        if group.get("id") == group_id:
            return group
    raise KeyError(group_id)


def project_runtime_rows() -> Dict[str, Dict[str, Any]]:
    if not DB_PATH.exists():
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    return {row["id"]: dict(row) for row in rows}


def effective_runtime_status(
    *,
    stored_status: Optional[str],
    queue_len: int,
    queue_index: int,
    enabled: bool,
    active_run_id: Optional[int],
    source_backlog_open: bool,
) -> str:
    status = str(stored_status or "").strip() or "idle"
    if not enabled:
        return "paused"
    if int(queue_index) >= int(queue_len):
        if status in {"starting", "running", "verifying"} and active_run_id:
            return status
        if source_backlog_open:
            return SOURCE_BACKLOG_OPEN_STATUS
        return "complete"
    if status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS}:
        return "idle"
    return status


def public_runtime_status(runtime_status: Optional[str]) -> str:
    status = str(runtime_status or "").strip() or "idle"
    if status == "idle":
        return "idle"
    if status == "complete":
        return CONFIGURED_QUEUE_COMPLETE_STATUS
    return status


def runtime_completion_basis(
    *,
    runtime_status: Optional[str],
    queue_len: int,
    queue_index: int,
    has_queue_sources: bool,
) -> str:
    status = str(runtime_status or "").strip() or "idle"
    current = min(max(int(queue_index), 0) + 1, queue_len) if queue_len else 0

    if status == "complete":
        if has_queue_sources and queue_len == 0:
            return "queue source resolved to zero active items; roadmap/design coverage is not signed off"
        if has_queue_sources:
            return "queue source-backed runtime queue is exhausted; roadmap/design coverage is not signed off"
        if queue_len == 0:
            return "configured queue is empty; roadmap/design coverage is not signed off"
        return "configured runtime queue is exhausted; roadmap/design coverage is not signed off"
    if status == SOURCE_BACKLOG_OPEN_STATUS:
        return "repo-native backlog still has open items; runtime queue cursor exhausted an earlier materialization"
    if status in {"starting", "running", "verifying", "idle"}:
        if queue_len == 0:
            return "configured queue currently resolves to zero active items"
        return f"configured queue has remaining work at {current} / {queue_len}"
    if status == "awaiting_account":
        return "configured queue has remaining work; waiting for an eligible account"
    if status == "blocked":
        return "configured queue has remaining work; execution is blocked after repeated failures"
    if status == "paused":
        return "project disabled in desired state"
    return f"runtime state derived from configured queue status: {status}"


def resolve_config_file(source_path: str) -> Optional[pathlib.Path]:
    raw = str(source_path or "").strip()
    if not raw:
        return None
    path = pathlib.Path(raw)
    return path if path.is_absolute() else CONFIG_PATH.parent / path


def normalize_named_mapping(section: Any) -> Dict[str, Dict[str, Any]]:
    items: Dict[str, Dict[str, Any]] = {}
    if isinstance(section, dict):
        for key, value in section.items():
            item = dict(value) if isinstance(value, dict) else {}
            item.setdefault("id", str(key))
            items[str(key)] = item
        return items
    if isinstance(section, list):
        for value in section:
            if not isinstance(value, dict):
                continue
            key = str(value.get("id", "")).strip()
            if not key:
                continue
            items[key] = dict(value)
    return items


def remaining_milestone_items(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for idx, value in enumerate(meta.get("remaining_milestones") or [], start=1):
        if isinstance(value, dict):
            item = dict(value)
            item.setdefault("id", f"M{idx}")
            item.setdefault("title", item["id"])
        else:
            title = str(value).strip()
            if not title:
                continue
            item = {"id": f"M{idx}", "title": title, "status": "open"}
        items.append(item)
    return items


def text_items(values: Any) -> List[str]:
    items: List[str] = []
    for value in values or []:
        if isinstance(value, dict):
            for key, item_value in value.items():
                left = str(key).strip()
                right = str(item_value).strip()
                text = f"{left}: {right}" if left and right else left or right
                if text:
                    items.append(text)
            continue
        text = str(value).strip()
        if text:
            items.append(text)
    return items


def project_group_defs(config: Dict[str, Any], project_id: str) -> List[Dict[str, Any]]:
    return [group for group in config.get("project_groups") or [] if project_id in (group.get("projects") or [])]


def group_captain_policy(group_cfg: Dict[str, Any]) -> Dict[str, Any]:
    default_floor = len(group_cfg.get("projects") or []) if str(group_cfg.get("mode", "") or "").strip().lower() == "lockstep" and (group_cfg.get("projects") or []) else 1
    return normalized_captain_policy(group_cfg.get("captain"), default_service_floor=default_floor)


def usage_window_start(config: Dict[str, Any]) -> dt.datetime:
    hours = int((config.get("spider", {}) or {}).get("token_alliance_window_hours", 24))
    return utc_now() - dt.timedelta(hours=hours)


def recent_usage_for_scope(project_ids: List[str], start: dt.datetime) -> Dict[str, Any]:
    clean_ids = [str(project_id).strip() for project_id in project_ids if str(project_id).strip()]
    if not clean_ids:
        return {"run_count": 0, "estimated_cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
    placeholders = ", ".join("?" for _ in clean_ids)
    query = f"""
        SELECT
          COUNT(*) AS run_count,
          COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd,
          COALESCE(SUM(input_tokens), 0) AS input_tokens,
          COALESCE(SUM(output_tokens), 0) AS output_tokens
        FROM runs
        WHERE project_id IN ({placeholders}) AND started_at >= ?
    """
    with db() as conn:
        row = conn.execute(query, (*clean_ids, iso(start))).fetchone()
    return {
        "run_count": int(row["run_count"] or 0) if row else 0,
        "estimated_cost_usd": float(row["estimated_cost_usd"] or 0.0) if row else 0.0,
        "input_tokens": int(row["input_tokens"] or 0) if row else 0,
        "output_tokens": int(row["output_tokens"] or 0) if row else 0,
    }


def project_pressure_state(project: Dict[str, Any]) -> str:
    status = str(project.get("runtime_status_internal") or project.get("runtime_status") or "").strip() or "idle"
    if status in {"blocked", "awaiting_account"}:
        return "critical"
    if parse_iso(project.get("cooldown_until")):
        return "high"
    if int(project.get("consecutive_failures") or 0) > 0 or str(project.get("last_error") or "").strip():
        return "high"
    if bool(project.get("needs_refill")) or int(project.get("approved_audit_task_count") or 0) > 0 or int(project.get("open_audit_task_count") or 0) > 0:
        return "elevated"
    if int(project.get("uncovered_scope_count") or 0) > 0:
        return "elevated"
    if status in {"starting", "running", "verifying"}:
        return "active"
    return "nominal"


def eligible_account_aliases(config: Dict[str, Any], project: Dict[str, Any], now: dt.datetime) -> List[str]:
    policy = dict(project.get("account_policy") or {})
    aliases: List[str] = []
    for alias in (
        list(policy.get("preferred_accounts") or [])
        + list(policy.get("burst_accounts") or [])
        + list(policy.get("reserve_accounts") or [])
        + list(project.get("accounts") or [])
    ):
        clean = str(alias or "").strip()
        if clean and clean not in aliases:
            aliases.append(clean)
    accounts_cfg = config.get("accounts", {}) or {}
    eligible: List[str] = []
    if not aliases:
        return eligible
    rows = {row["alias"]: row for row in account_pool_rows(config)}
    for alias in aliases:
        account_cfg = dict(accounts_cfg.get(alias, {}) or {})
        row = rows.get(alias, {})
        auth_kind = str(account_cfg.get("auth_kind") or row.get("auth_kind") or "api_key")
        if auth_kind in CHATGPT_AUTH_KINDS and not bool(policy.get("allow_chatgpt_accounts", True)):
            continue
        if auth_kind == "api_key" and not bool(policy.get("allow_api_accounts", True)):
            continue
        if account_runtime_state(row, account_cfg, now) != "ready":
            continue
        eligible.append(alias)
    return eligible


def group_pool_sufficiency(config: Dict[str, Any], group_cfg: Dict[str, Any], group_projects: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    eligible_union: List[str] = []
    per_project: Dict[str, int] = {}
    account_rows = {row["alias"]: row for row in account_pool_rows(config)}
    total_slots = 0
    for project in group_projects:
        aliases = eligible_account_aliases(config, project, now)
        per_project[str(project.get("id") or "")] = len(aliases)
        for alias in aliases:
            if alias in eligible_union:
                continue
            eligible_union.append(alias)
            total_slots += max(1, int((account_rows.get(alias, {}).get("max_parallel_runs") or 1)))
    captain = group_captain_policy(group_cfg)
    required_slots = max(1, int(captain.get("service_floor") or 1))
    remaining_slices = sum(max(int(project.get("queue_len") or 0) - int(project.get("queue_index") or 0), 0) for project in group_projects)
    if any(count <= 0 for count in per_project.values()):
        level = "blocked"
        basis = "at least one member project has no eligible account pool"
    elif total_slots < required_slots:
        level = "insufficient"
        basis = "eligible account pool cannot satisfy the configured service floor"
    elif remaining_slices > max(total_slots, 1) * 6:
        level = "tight"
        basis = "remaining queue load is materially larger than the currently eligible pool"
    else:
        level = "sufficient"
        basis = "eligible account pool can satisfy the current service floor"
    return {
        "level": level,
        "basis": basis,
        "eligible_accounts": eligible_union,
        "eligible_account_count": len(eligible_union),
        "eligible_parallel_slots": total_slots,
        "required_slots": required_slots,
        "remaining_slices": remaining_slices,
    }


def group_pressure_state(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> str:
    if group.get("signed_off"):
        return "signed_off"
    if group.get("contract_blockers") or str(group.get("status") or "") == "contract_blocked":
        return "critical"
    project_states = {project_pressure_state(project) for project in group_projects}
    if "critical" in project_states or not bool(group.get("dispatch_ready", True)):
        return "high"
    if "high" in project_states:
        return "high"
    if "elevated" in project_states or int(group.get("uncovered_scope_count") or 0) > 0:
        return "elevated"
    if "active" in project_states:
        return "active"
    return "nominal"


def project_account_policy_summary(project: Dict[str, Any]) -> str:
    policy = dict(project.get("account_policy") or {})
    parts: List[str] = []
    preferred = ", ".join(str(item).strip() for item in (policy.get("preferred_accounts") or []) if str(item).strip())
    burst = ", ".join(str(item).strip() for item in (policy.get("burst_accounts") or []) if str(item).strip())
    reserve = ", ".join(str(item).strip() for item in (policy.get("reserve_accounts") or []) if str(item).strip())
    if preferred:
        parts.append(f"preferred={preferred}")
    if burst:
        parts.append(f"burst={burst}")
    if reserve:
        parts.append(f"reserve={reserve}")
    flags = []
    if not bool(policy.get("allow_chatgpt_accounts", True)):
        flags.append("chatgpt-auth disallowed")
    if not bool(policy.get("allow_api_accounts", True)):
        flags.append("api-key disallowed")
    if not bool(policy.get("spark_enabled", True)):
        flags.append("spark disabled")
    if flags:
        parts.append(", ".join(flags))
    return "; ".join(parts)


def group_captain_policy_summary(group: Dict[str, Any]) -> str:
    captain = group_captain_policy(group)
    return (
        f"priority={captain.get('priority')} ; "
        f"floor={captain.get('service_floor')} ; "
        f"shed={captain.get('shed_order')} ; "
        f"admission={captain.get('admission_policy')} ; "
        f"preemption={captain.get('preemption_policy')}"
    )


def runner_policy_summary(project: Dict[str, Any]) -> str:
    runner = dict(project.get("runner") or {})
    flags: List[str] = []
    if bool(runner.get("always_continue", True)):
        flags.append("always continue")
    if bool(runner.get("avoid_permission_escalation", True)):
        flags.append("avoid escalation")
    return ", ".join(flags)


def project_backlog_source_summary(project_cfg: Dict[str, Any]) -> str:
    sources: List[str] = []
    if project_cfg.get("queue"):
        sources.append("fleet.yaml queue")
    for source_cfg in project_cfg.get("queue_sources") or []:
        kind = str(source_cfg.get("kind") or "source").strip()
        path = str(source_cfg.get("path") or "").strip()
        sources.append(f"{kind}:{path}" if path else kind)
    overlay_path = pathlib.Path(project_cfg["path"]) / STUDIO_PUBLISHED_DIR / QUEUE_OVERLAY_FILENAME
    if overlay_path.exists():
        sources.append(".codex-studio/published/QUEUE.generated.yaml")
    return ", ".join(sources) or "no backlog source configured"


def project_queue_source_health(project_cfg: Dict[str, Any], queue_len: int) -> str:
    if project_cfg.get("queue_sources"):
        if queue_len <= 0:
            return "source-backed queue resolved to zero active items"
        return "source-backed queue resolved to active items"
    if queue_len <= 0:
        return "static queue is empty"
    return "static queue has active items"


def project_stop_context(
    *,
    project_cfg: Dict[str, Any],
    runtime_status: str,
    queue_len: int,
    uncovered_scope_count: int,
    open_task_count: int,
    approved_task_count: int,
    last_error: Optional[str],
    cooldown_until: Optional[str],
    milestone_coverage_complete: bool,
    design_coverage_complete: bool,
    group_signed_off: bool,
) -> Dict[str, Any]:
    stop_reason = ""
    next_action = ""
    unblocker = ""
    active = runtime_status in {"starting", "running", "verifying"}
    if not active:
        if runtime_status == "paused":
            stop_reason = "desired state disabled the project"
            next_action = "resume the project"
            unblocker = "operator"
        elif runtime_status == "awaiting_account":
            stop_reason = "no eligible account or model is available for the current slice"
            next_action = "resume, validate, or reroute accounts for this project"
            unblocker = "operator"
        elif runtime_status == "blocked":
            stop_reason = "repeated failures blocked execution"
            next_action = "inspect the last run, split the slice if needed, and retry"
            unblocker = "operator"
        elif cooldown_until:
            stop_reason = "project is cooling down after a recent failure or rate limit"
            next_action = "wait for cooldown expiry or clear the cooldown manually"
            unblocker = "operator"
        elif runtime_status == SOURCE_BACKLOG_OPEN_STATUS:
            stop_reason = "the current queue materialization is exhausted, but the backlog source still reports open work"
            if approved_task_count > 0:
                next_action = "publish approved auditor tasks or use group refill"
                unblocker = "operator"
            elif open_task_count > 0:
                next_action = "review auditor task proposals and approve or publish the next scoped queue"
                unblocker = "operator"
            else:
                next_action = "regenerate or publish the next scoped queue from backlog evidence"
                unblocker = "auditor or project manager"
        elif runtime_status == "complete" and uncovered_scope_count > 0:
            stop_reason = "the current queue is exhausted while uncovered scope remains"
            if approved_task_count > 0:
                next_action = "publish approved auditor tasks or use group refill"
                unblocker = "operator"
            elif open_task_count > 0:
                next_action = "review auditor task proposals and approve or publish the next scoped queue"
                unblocker = "operator"
            else:
                next_action = "generate the next scoped queue from design and backlog gaps"
                unblocker = "auditor and project manager"
        elif runtime_status == "complete":
            stop_reason = "the current queue is exhausted"
            next_action = "sign off the product or publish the next scoped queue"
            unblocker = "operator"
        elif queue_len <= 0 and project_cfg.get("queue_sources"):
            stop_reason = "the backlog source produced zero active items"
            if approved_task_count > 0:
                next_action = "publish approved auditor tasks or use group refill"
                unblocker = "operator"
            elif open_task_count > 0:
                next_action = "review auditor task proposals and approve or publish the next scoped queue"
                unblocker = "operator"
            else:
                next_action = "audit the backlog source and generate the next scoped queue"
                unblocker = "auditor and project manager"
    exhausted_or_empty = runtime_status in {CONFIGURED_QUEUE_COMPLETE_STATUS, SOURCE_BACKLOG_OPEN_STATUS, "complete"} or (
        queue_len <= 0 and bool(project_cfg.get("queue_sources"))
    )
    needs_refill = bool(not active and exhausted_or_empty and not group_signed_off)
    return {
        "stop_reason": stop_reason,
        "queue_source_health": project_queue_source_health(project_cfg, queue_len),
        "backlog_source": project_backlog_source_summary(project_cfg),
        "next_action": next_action,
        "unblocker": unblocker,
        "needs_refill": needs_refill,
        "refill_ready": bool(approved_task_count > 0),
        "open_audit_task_count": int(open_task_count),
        "approved_audit_task_count": int(approved_task_count),
        "stopped_not_signed_off": bool(stop_reason and not active and not group_signed_off),
        "requires_operator_attention": bool(stop_reason or last_error),
    }


def project_progress_label(project: Dict[str, Any]) -> str:
    queue_len = int(project.get("queue_len") or 0)
    queue_index = int(project.get("queue_index") or 0)
    if queue_len <= 0:
        return "0 / 0"
    if project.get("runtime_status") == CONFIGURED_QUEUE_COMPLETE_STATUS:
        return f"{queue_len} / {queue_len}"
    return f"{min(queue_index + 1, queue_len)} / {queue_len}"


def project_audit_task_counts(project_id: str) -> Dict[str, int]:
    if not table_exists("audit_task_candidates"):
        return {"open": 0, "approved": 0, "published": 0}
    with db() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM audit_task_candidates
            WHERE scope_type='project' AND scope_id=?
            GROUP BY status
            """,
            (project_id,),
        ).fetchall()
    counts = {"open": 0, "approved": 0, "published": 0}
    for row in rows:
        status = str(row["status"] or "").strip().lower()
        if status in counts:
            counts[status] = int(row["count"] or 0)
    return counts


def public_project_status(
    runtime_status: str,
    *,
    cooldown_until: Optional[str],
    needs_refill: bool,
    open_task_count: int = 0,
    approved_task_count: int = 0,
) -> str:
    status = str(runtime_status or "").strip() or "idle"
    cooldown = parse_iso(cooldown_until)
    if status == "idle" and cooldown and cooldown > utc_now():
        return "cooldown"
    if status in {"complete", SOURCE_BACKLOG_OPEN_STATUS} and needs_refill:
        if approved_task_count > 0 or open_task_count > 0:
            return "proposed_tasks"
        return "audit_required"
    return public_runtime_status(status)


def group_registry_meta(group_cfg: Dict[str, Any], registry: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
    meta = dict((registry.get("groups") or {}).get(str(group_cfg.get("id") or ""), {}) or {})
    if meta:
        return meta
    if not bool(group_cfg.get("auto_created")):
        return {}
    project_ids = [str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()]
    if len(project_ids) != 1:
        return {}
    project_meta = dict((registry.get("projects") or {}).get(project_ids[0], {}) or {})
    if not project_meta:
        return {}
    project_meta.setdefault("contract_blockers", [])
    project_meta.setdefault("signed_off", bool(project_meta.get("product_signed_off") or project_meta.get("signed_off")))
    return project_meta


def group_is_signed_off(meta: Dict[str, Any]) -> bool:
    signoff_state = str(meta.get("signoff_state") or meta.get("status") or "").strip().lower()
    return bool(
        meta.get("signed_off")
        or meta.get("product_signed_off")
        or signoff_state in {"signed_off", "product_signed_off", "complete"}
    )


def effective_group_meta(
    group_cfg: Dict[str, Any],
    registry: Dict[str, Dict[str, Dict[str, Any]]],
    runtime_rows: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    meta = group_registry_meta(group_cfg, registry)
    runtime = dict(runtime_rows.get(str(group_cfg.get("id") or ""), {}) or {})
    if runtime:
        meta = dict(meta)
        signoff_state = str(runtime.get("signoff_state") or "").strip().lower()
        if signoff_state:
            meta["signoff_state"] = signoff_state
            meta["signed_off"] = signoff_state == "signed_off"
        for key in ("signed_off_at", "reopened_at", "last_audit_requested_at", "last_refill_requested_at", "phase", "last_phase_at"):
            if runtime.get(key):
                meta[key] = runtime.get(key)
    return meta


def load_program_registry(config: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    registry: Dict[str, Dict[str, Dict[str, Any]]] = {"groups": {}, "projects": {}}
    loaded: set[pathlib.Path] = set()
    for group in config.get("project_groups") or []:
        source = group.get("milestone_source") or {}
        kind = str(source.get("kind", "") or "").strip().lower()
        if kind not in {"group_milestones", "yaml"}:
            continue
        path = resolve_config_file(str(source.get("path", "")))
        if not path or path in loaded or not path.exists() or not path.is_file():
            continue
        data = load_yaml(path)
        registry["groups"].update(normalize_named_mapping(data.get("groups")))
        registry["projects"].update(normalize_named_mapping(data.get("projects")))
        loaded.add(path)
    return registry


def estimate_registry_eta(meta: Dict[str, Any], now: dt.datetime, *, coverage_key: str, missing_basis: str, incomplete_basis: str, zero_basis: str, missing_reason: str, incomplete_reason: str) -> Dict[str, Any]:
    remaining_count = len(remaining_milestone_items(meta))
    result: Dict[str, Any] = {
        "remaining_milestones": remaining_count,
        "estimated_remaining_seconds": None,
        "eta_at": None,
        "eta_human": "unknown",
        "eta_basis": "",
        "eta_unavailable_reason": "",
    }
    if not meta:
        result["eta_basis"] = missing_basis
        result["eta_unavailable_reason"] = missing_reason
        return result
    if not bool(meta.get(coverage_key)):
        result["eta_basis"] = incomplete_basis
        result["eta_unavailable_reason"] = incomplete_reason
        return result
    if remaining_count == 0:
        result.update(
            {
                "estimated_remaining_seconds": 0,
                "eta_at": iso(now),
                "eta_human": "0s",
                "eta_basis": zero_basis,
            }
        )
        return result
    result["eta_basis"] = "defined milestones exist, but no milestone task-to-ETA model is configured"
    result["eta_unavailable_reason"] = "milestone_eta_model_missing"
    return result


def project_runtime_status(project: Dict[str, Any]) -> str:
    return str(
        project.get("status_internal")
        or project.get("runtime_status_internal")
        or project.get("status")
        or project.get("runtime_status")
        or ""
    ).strip() or "idle"


def project_queue_length(project: Dict[str, Any]) -> int:
    queue = project.get("queue")
    if isinstance(queue, list):
        return len(queue)
    return int(project.get("queue_len") or 0)


def current_queue_item_text(project: Dict[str, Any]) -> str:
    queue = project.get("queue")
    if isinstance(queue, list):
        queue_index = int(project.get("queue_index") or 0)
        if 0 <= queue_index < len(queue):
            return str(queue[queue_index] or "").strip()
    return str(project.get("current_queue_item") or project.get("slice_name") or "").strip()


def is_contract_remediation_slice(text: str) -> bool:
    lower = str(text or "").strip().lower()
    if not lower:
        return False
    keywords = [
        "contract",
        "dto",
        "canonical",
        "compatibility",
        "extract",
        "extraction",
        "split",
        "repo split",
        "session_events_vnext",
        "runtime_dtos_vnext",
        "event envelope",
        "shared contract",
        "package consumption",
        "package-only",
        "engine contracts",
        "play contracts",
        "ui kit",
        "ui-kit",
        "token canon",
        "registry contracts",
        "hub registry",
        "hub-registry",
        "media factory",
        "media-factory",
        "play transport",
        "engine mutation",
        "milestone mapping",
        "executable queue work",
        "ownership",
        "session shell ownership",
        "artifact metadata",
        "publication workflow",
        "asset lifecycle",
        "renderer",
        "render-only",
        "job surfaces",
        "storage",
        "explain",
        "ai platform",
    ]
    return any(keyword in lower for keyword in keywords)


def group_dispatch_state(group: Dict[str, Any], meta: Dict[str, Any], group_projects: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    blockers: List[str] = []
    if group_is_signed_off(meta):
        blockers.append("group signed off")
    contract_blockers = text_items(meta.get("contract_blockers"))
    contract_phase_allowed = bool(contract_blockers) and bool(group_projects) and all(
        is_contract_remediation_slice(current_queue_item_text(project))
        and int(project.get("queue_index") or 0) < project_queue_length(project)
        for project in group_projects
    )
    if contract_blockers and not contract_phase_allowed:
        blockers.extend(f"contract blocker: {item}" for item in contract_blockers)

    mode = str(group.get("mode", "") or "independent").strip().lower()
    if mode == "lockstep":
        for project in group_projects:
            project_id = str(project.get("id") or "unknown")
            status = project_runtime_status(project)
            queue_len = project_queue_length(project)
            queue_index = int(project.get("queue_index") or 0)
            cooldown_until = parse_iso(project.get("cooldown_until"))
            if not bool(project.get("enabled", True)):
                blockers.append(f"{project_id}: project disabled")
            elif status in {"starting", "running", "verifying"} and not contract_phase_allowed:
                blockers.append(f"{project_id}: run already in progress")
            elif cooldown_until and cooldown_until > now:
                blockers.append(f"{project_id}: cooldown active")
            elif status == "awaiting_account":
                blockers.append(f"{project_id}: awaiting eligible account")
            elif status == "blocked":
                blockers.append(f"{project_id}: blocked after repeated failures")
            elif queue_index >= queue_len:
                if status == SOURCE_BACKLOG_OPEN_STATUS:
                    blockers.append(f"{project_id}: runtime queue exhausted while source backlog remains open")
                else:
                    blockers.append(f"{project_id}: runtime queue exhausted")

    ready = not blockers
    if ready:
        basis = "group dispatch is allowed"
        if mode == "lockstep":
            basis = "lockstep group is ready to dispatch all member projects together"
        if contract_phase_allowed:
            basis = "lockstep contract-remediation and extraction slices are allowed to run while contract blockers remain open"
    else:
        basis = "group dispatch blocked by current runtime and contract state"
        if mode == "lockstep":
            basis = "lockstep dispatch blocked until all member projects and group blockers are ready"
    return {
        "dispatch_ready": ready,
        "dispatch_blockers": blockers,
        "dispatch_basis": basis,
        "contract_phase_allowed": contract_phase_allowed,
    }


def effective_group_status(group: Dict[str, Any], meta: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> str:
    if group_is_signed_off(meta):
        return "product_signed_off"
    dispatch = group_dispatch_state(group, meta, group_projects, utc_now())
    if text_items(meta.get("contract_blockers")):
        return "contract_blocked"
    if any(int(project.get("approved_audit_task_count") or 0) > 0 or int(project.get("open_audit_task_count") or 0) > 0 for project in group_projects):
        return "proposed_tasks"
    if any(bool(project.get("needs_refill")) for project in group_projects):
        return "audit_required"
    if text_items(meta.get("uncovered_scope")) or not bool(meta.get("milestone_coverage_complete")):
        return "audit_required"
    if remaining_milestone_items(meta):
        if str(group.get("mode", "") or "").strip().lower() == "lockstep" and not dispatch.get("dispatch_ready"):
            active_statuses = {"running", "starting", "verifying"}
            if any(project_runtime_status(project) in active_statuses for project in group_projects):
                return "lockstep_active"
            return "group_blocked"
        return "milestone_backlog_open"
    active_statuses = {"running", "starting", "verifying", "idle", "awaiting_account", "blocked", "cooldown"}
    if any(project_runtime_status(project) in active_statuses for project in group_projects):
        return "lockstep_active"
    return "audit_required"


def derive_group_phase(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> str:
    status = str(group.get("status") or "").strip().lower()
    if status == "product_signed_off":
        return "signed_off"
    if status in {"contract_blocked", "group_blocked"}:
        return "blocked"
    if status == "proposed_tasks":
        return "proposed_tasks"
    if status == "audit_required":
        return "audit_required"
    active_statuses = {"running", "starting", "verifying"}
    if any(project_runtime_status(project) in active_statuses for project in group_projects):
        return "running"
    if bool(group.get("dispatch_ready")):
        return "ready"
    return "idle"


def recent_runs(limit: int = 20) -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    with db() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def recent_auditor_run() -> Optional[Dict[str, Any]]:
    if not table_exists("auditor_runs"):
        return None
    with db() as conn:
        row = conn.execute("SELECT * FROM auditor_runs ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def audit_findings(limit: int = 100) -> List[Dict[str, Any]]:
    if not table_exists("audit_findings"):
        return []
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_findings WHERE status='open' ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, last_seen_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["evidence"] = json.loads(item.pop("evidence_json", "[]") or "[]")
        item["candidate_tasks"] = json.loads(item.pop("candidate_tasks_json", "[]") or "[]")
        items.append(item)
    return items


def audit_task_candidates(limit: int = 100) -> List[Dict[str, Any]]:
    if not table_exists("audit_task_candidates"):
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM audit_task_candidates
            WHERE status IN ('open', 'approved')
            ORDER BY CASE status WHEN 'approved' THEN 0 ELSE 1 END, last_seen_at DESC, scope_type, scope_id, task_index
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["task_meta"] = json_field(item.pop("task_meta_json", "{}"), {})
        items.append(item)
    return items


def studio_publish_events(limit: int = 50) -> List[Dict[str, Any]]:
    if not table_exists("studio_publish_events"):
        return []
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM studio_publish_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        targets = json_field(item.get("published_targets_json"), [])
        item["published_targets"] = targets if isinstance(targets, list) else []
        target_labels = [
            f"{target.get('target_type')}:{target.get('target_id')} ({target.get('file_count')})"
            for target in item["published_targets"]
        ]
        item["published_targets_summary"] = ", ".join(target_labels[:3])
        if len(target_labels) > 3:
            item["published_targets_summary"] = f"{item['published_targets_summary']}, +{len(target_labels) - 3} more"
        items.append(item)
    return items


def group_publish_events(limit: int = 50) -> List[Dict[str, Any]]:
    if not table_exists("group_publish_events"):
        return []
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM group_publish_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        targets = json_field(item.get("published_targets_json"), [])
        item["published_targets"] = targets if isinstance(targets, list) else []
        labels = [f"{target.get('target_type')}:{target.get('target_id')}" for target in item["published_targets"]]
        item["published_targets_summary"] = ", ".join(labels[:3])
        if len(labels) > 3:
            item["published_targets_summary"] = f"{item['published_targets_summary']}, +{len(labels) - 3} more"
        items.append(item)
    return items


def log_group_run(
    group_id: str,
    *,
    run_kind: str,
    phase: str,
    status: str,
    member_projects: List[str],
    details: Optional[Dict[str, Any]] = None,
) -> None:
    if not table_exists("group_runs"):
        return
    now_text = iso(utc_now())
    with db() as conn:
        conn.execute(
            """
            INSERT INTO group_runs(group_id, run_kind, phase, status, member_projects_json, details_json, started_at, finished_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group_id,
                run_kind,
                phase,
                status,
                json.dumps(member_projects, indent=2),
                json.dumps(details or {}, indent=2),
                now_text,
                now_text,
            ),
        )


def group_runs(limit: int = 50) -> List[Dict[str, Any]]:
    if not table_exists("group_runs"):
        return []
    with db() as conn:
        rows = conn.execute("SELECT * FROM group_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        members = json_field(item.get("member_projects_json"), [])
        details = json_field(item.get("details_json"), {})
        item["member_projects"] = members if isinstance(members, list) else []
        item["details"] = details if isinstance(details, dict) else {}
        item["member_projects_summary"] = ", ".join(str(member) for member in item["member_projects"][:4])
        if len(item["member_projects"]) > 4:
            item["member_projects_summary"] = f"{item['member_projects_summary']}, +{len(item['member_projects']) - 4} more"
        items.append(item)
    return items


def split_items(raw: Any) -> List[str]:
    if isinstance(raw, (list, tuple)):
        values: List[str] = []
        for item in raw:
            value = str(item or "").strip()
            if value:
                values.append(value)
        return values
    values: List[str] = []
    for line in str(raw or "").replace(",", "\n").splitlines():
        value = line.strip()
        if value:
            values.append(value)
    return values


def validate_repo_path(repo_path: str) -> pathlib.Path:
    path = pathlib.Path(repo_path).expanduser()
    if not path.is_absolute():
        raise HTTPException(400, "repo path must be absolute")
    try:
        path.relative_to(DOCKER_ROOT)
    except ValueError as exc:
        raise HTTPException(400, "repo path must live under /docker") from exc
    if not path.exists() or not path.is_dir():
        raise HTTPException(400, "repo path is not visible inside the fleet containers")
    return path


def validate_or_create_repo_path(repo_path: str, *, create_if_missing: bool = False) -> pathlib.Path:
    path = pathlib.Path(repo_path).expanduser()
    if not path.is_absolute():
        raise HTTPException(400, "repo path must be absolute")
    try:
        path.relative_to(DOCKER_ROOT)
    except ValueError as exc:
        raise HTTPException(400, "repo path must live under /docker") from exc
    if path.exists():
        if not path.is_dir():
            raise HTTPException(400, "repo path exists but is not a directory")
        return path
    if not create_if_missing:
        raise HTTPException(400, "repo path is not visible inside the fleet containers")
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_optional_repo_file(repo_root: pathlib.Path, raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    path = pathlib.Path(value)
    if path.is_absolute():
        return str(path)
    return str(repo_root / path)


def bootstrap_repo_ai_files(repo_root: pathlib.Path, feedback_dir: str, state_file: str) -> None:
    feedback_path = repo_root / feedback_dir
    feedback_path.mkdir(parents=True, exist_ok=True)
    applied_log = feedback_path / ".applied.log"
    applied_log.touch(exist_ok=True)

    studio_published = repo_root / STUDIO_PUBLISHED_DIR
    studio_published.mkdir(parents=True, exist_ok=True)

    scripts_ai = repo_root / "scripts/ai"
    scripts_ai.mkdir(parents=True, exist_ok=True)

    agent_memory = repo_root / ".agent-memory.md"
    if not agent_memory.exists():
        agent_memory.write_text(
            "# Repo-local agent memory\n\n- Keep repo-specific workflow notes here.\n",
            encoding="utf-8",
        )

    state_path = repo_root / state_file
    if not state_path.exists():
        state_path.write_text("{}\n", encoding="utf-8")

    verify_script = scripts_ai / "verify.sh"
    if not verify_script.exists():
        verify_script.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n# TODO: replace with repo verification commands.\n",
            encoding="utf-8",
        )
        verify_script.chmod(0o755)


def write_if_missing(path: pathlib.Path, content: str, *, executable: bool = False) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def bootstrap_new_project_repo(
    repo_root: pathlib.Path,
    *,
    project_id: str,
    feedback_dir: str,
    state_file: str,
    design_doc: str,
    verify_cmd: str,
) -> None:
    write_if_missing(
        repo_root / "README.md",
        f"# {project_id}\n\nBootstrapped by Codex Fleet.\n",
    )
    write_if_missing(
        repo_root / "AGENTS.md",
        "# Repo Instructions\n\n- Keep changes scoped to the queue item.\n- Verify before finishing.\n",
    )
    write_if_missing(
        repo_root / "WORKLIST.md",
        "# Worklist\n\n- [queued] Bootstrap repo structure and package boundaries\n",
    )
    bootstrap_repo_ai_files(repo_root, feedback_dir, state_file)
    if design_doc:
        design_path = resolve_optional_repo_file(repo_root, design_doc)
        design_file = pathlib.Path(design_path)
        write_if_missing(
            design_file,
            f"# {project_id} design\n\n- Mission: define the repo boundary and package plane.\n",
        )
    if verify_cmd.strip() == "bash scripts/ai/verify.sh":
        write_if_missing(
            repo_root / "scripts" / "ai" / "verify.sh",
            "#!/usr/bin/env bash\nset -euo pipefail\n# TODO: replace with repo verification commands.\n",
            executable=True,
        )


def maybe_init_git_repo(repo_root: pathlib.Path) -> None:
    if (repo_root / ".git").exists():
        return
    try:
        subprocess.run(["git", "init", "-q", str(repo_root)], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(repo_root), "branch", "-M", "main"], check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise HTTPException(500, "git is not available in the admin runtime") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, exc.stderr.strip() or "git init failed") from exc


def maybe_create_github_repo(repo_root: pathlib.Path, *, owner: str, repo_name: str, visibility: str) -> None:
    if not owner or not repo_name:
        raise HTTPException(400, "github owner and repo name are required for repo creation")
    gh_bin = shutil.which("gh")
    if not gh_bin:
        raise HTTPException(500, "gh CLI is not available in the admin runtime")
    try:
        subprocess.run(
            [
                gh_bin,
                "repo",
                "create",
                f"{owner}/{repo_name}",
                "--source",
                str(repo_root),
                "--remote",
                "origin",
                "--push",
                "--" + (visibility or "private"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        if "already exists" in stderr.lower():
            return
        raise HTTPException(500, stderr or "gh repo create failed") from exc


def register_project_entry(config: Dict[str, Any], project: Dict[str, Any], *, group_id: str = "") -> None:
    if any(existing.get("id") == project.get("id") for existing in config.get("projects", [])):
        raise HTTPException(400, f"project id already exists: {project.get('id')}")
    config.setdefault("projects", []).append(project)
    clean_group_id = str(group_id or "").strip()
    if not clean_group_id:
        return
    for group in config.get("project_groups") or []:
        if str(group.get("id") or "") != clean_group_id:
            continue
        members = [str(item).strip() for item in (group.get("projects") or []) if str(item).strip()]
        if project["id"] not in members:
            members.append(project["id"])
        group["projects"] = members
        return
    config.setdefault("project_groups", []).append(
        {
            "id": clean_group_id,
            "projects": [project["id"]],
            "mode": "independent",
            "contract_sets": [],
            "milestone_source": {},
            "group_roles": list(DEFAULT_SINGLETON_GROUP_ROLES),
            "captain": normalized_captain_policy({}, default_service_floor=1),
        }
    )


def bootstrap_project_from_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    project_id = str(spec.get("project_id") or "").strip()
    if not project_id:
        raise HTTPException(400, "bootstrap project_id is required")
    repo_root = validate_or_create_repo_path(str(spec.get("repo_path") or ""), create_if_missing=bool(spec.get("create_repo_dir")))
    feedback_dir = str(spec.get("feedback_dir") or "feedback").strip() or "feedback"
    state_file = str(spec.get("state_file") or ".agent-state.json").strip() or ".agent-state.json"
    design_doc = str(spec.get("design_doc") or "").strip()
    verify_cmd = str(spec.get("verify_cmd") or "").strip()
    if bool(spec.get("bootstrap_files", True)):
        bootstrap_new_project_repo(
            repo_root,
            project_id=project_id,
            feedback_dir=feedback_dir,
            state_file=state_file,
            design_doc=design_doc,
            verify_cmd=verify_cmd,
        )
    if bool(spec.get("init_local_git")):
        maybe_init_git_repo(repo_root)
    if bool(spec.get("create_github_repo")):
        maybe_create_github_repo(
            repo_root,
            owner=str(spec.get("github_owner") or "").strip(),
            repo_name=str(spec.get("github_repo") or project_id).strip(),
            visibility=str(spec.get("github_visibility") or "private").strip() or "private",
        )

    project = {
        "id": project_id,
        "path": str(repo_root),
        "design_doc": resolve_optional_repo_file(repo_root, design_doc),
        "verify_cmd": verify_cmd,
        "feedback_dir": feedback_dir,
        "state_file": state_file,
        "enabled": True,
        "accounts": split_items(spec.get("account_aliases") or ""),
        "account_policy": {
            "preferred_accounts": split_items(spec.get("preferred_accounts") or ""),
            "burst_accounts": split_items(spec.get("burst_accounts") or ""),
            "reserve_accounts": split_items(spec.get("reserve_accounts") or ""),
            "allow_chatgpt_accounts": bool(spec.get("allow_chatgpt_accounts", True)),
            "allow_api_accounts": bool(spec.get("allow_api_accounts", True)),
            "spark_enabled": bool(spec.get("spark_enabled", True)),
        },
        "runner": {
            "sandbox": "workspace-write",
            "approval_policy": "never",
            "exec_timeout_seconds": 5400,
            "verify_timeout_seconds": 1800,
            "always_continue": True,
            "avoid_permission_escalation": True,
            "config_overrides": [],
        },
        "queue": split_items(spec.get("queue_items") or ""),
    }
    config = normalize_config()
    register_project_entry(config, project, group_id=str(spec.get("group_id") or "").strip())
    save_fleet_config(config)
    return {
        "project_id": project_id,
        "path": str(repo_root),
        "group_id": str(spec.get("group_id") or "").strip(),
        "created_github_repo": bool(spec.get("create_github_repo")),
    }


def save_fleet_config(config: Dict[str, Any]) -> None:
    data = dict(config)
    data.pop("accounts", None)
    data["project_groups"] = [group for group in (data.get("project_groups") or []) if not bool((group or {}).get("auto_created"))]
    save_yaml(CONFIG_PATH, data)


def save_accounts_config(accounts: Dict[str, Any]) -> None:
    save_yaml(ACCOUNTS_PATH, {"accounts": accounts})


def account_home(alias: str) -> pathlib.Path:
    return CODEX_HOME_ROOT / alias


def read_api_key_from_file(api_key_file: pathlib.Path) -> str:
    if not api_key_file.exists():
        raise RuntimeError(f"missing api_key_file: {api_key_file}")
    api_key = api_key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        raise RuntimeError(f"empty api_key_file: {api_key_file}")
    return api_key


def read_api_key(account_cfg: Dict[str, Any]) -> str:
    api_key_env = str(account_cfg.get("api_key_env", "") or "").strip()
    if api_key_env:
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"missing environment variable for api_key_env: {api_key_env}")
        return api_key
    api_key_file = pathlib.Path(str(account_cfg.get("api_key_file", "") or "").strip())
    return read_api_key_from_file(api_key_file)


def has_api_key(account_cfg: Dict[str, Any]) -> bool:
    try:
        return bool(read_api_key(account_cfg))
    except Exception:
        return False


def account_runtime_state(account_row: Dict[str, Any], account_cfg: Dict[str, Any], now: dt.datetime) -> str:
    configured = str(account_cfg.get("health_state", "ready") or "ready").strip().lower()
    if configured in {"disabled", "draining", "exhausted", "auth_stale"}:
        return configured
    backoff_until = parse_iso(account_row.get("backoff_until"))
    if backoff_until and backoff_until > now:
        return "cooldown"
    return "ready"


def account_supports_spark(account_cfg: Dict[str, Any], allowed_models: List[str]) -> bool:
    auth_kind = str(account_cfg.get("auth_kind", "api_key") or "api_key")
    if auth_kind not in CHATGPT_AUTH_KINDS:
        return False
    if not bool(account_cfg.get("spark_enabled", SPARK_MODEL in allowed_models)):
        return False
    return (not allowed_models) or (SPARK_MODEL in allowed_models)


def account_auth_status(account_cfg: Dict[str, Any]) -> str:
    auth_kind = str(account_cfg.get("auth_kind", "api_key") or "api_key")
    if auth_kind == "api_key":
        try:
            read_api_key(account_cfg)
            return "ready"
        except Exception as exc:
            return str(exc)
    if auth_kind in CHATGPT_AUTH_KINDS:
        auth_json_file = pathlib.Path(str(account_cfg.get("auth_json_file", "") or "").strip())
        if not auth_json_file.exists():
            return f"missing auth_json_file: {auth_json_file}"
        return "ready"
    return f"unsupported auth_kind: {auth_kind}"


def account_pool_rows(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    accounts_cfg = config.get("accounts", {}) or {}
    rows: Dict[str, Dict[str, Any]] = {}
    if DB_PATH.exists():
        with db() as conn:
            db_rows = conn.execute("SELECT * FROM accounts ORDER BY alias").fetchall()
        for row in db_rows:
            rows[row["alias"]] = dict(row)
    now = utc_now()
    items: List[Dict[str, Any]] = []
    for alias in sorted(set(rows) | set(accounts_cfg)):
        db_row = rows.get(alias, {})
        account_cfg = dict(accounts_cfg.get(alias, {}) or {})
        allowed_models = list(account_cfg.get("allowed_models") or json.loads(db_row.get("allowed_models_json") or "[]") or [])
        item = {
            "alias": alias,
            "auth_kind": account_cfg.get("auth_kind") or db_row.get("auth_kind") or "api_key",
            "allowed_models": allowed_models,
            "spark_enabled": account_supports_spark(account_cfg, allowed_models),
            "configured_state": str(account_cfg.get("health_state", "ready") or "ready"),
            "pool_state": account_runtime_state(db_row, account_cfg, now),
            "daily_budget_usd": account_cfg.get("daily_budget_usd", db_row.get("daily_budget_usd")),
            "monthly_budget_usd": account_cfg.get("monthly_budget_usd", db_row.get("monthly_budget_usd")),
            "max_parallel_runs": int(account_cfg.get("max_parallel_runs", db_row.get("max_parallel_runs") or 1)),
            "project_allowlist": list(account_cfg.get("project_allowlist") or []),
            "daily_usage": {"cost": 0.0},
            "monthly_usage": {"cost": 0.0},
            "active_runs": 0,
            "backoff_until": db_row.get("backoff_until"),
            "last_used_at": db_row.get("last_used_at"),
            "last_error": db_row.get("last_error"),
            "auth_status": account_auth_status(account_cfg),
            "codex_home": str(account_home(alias)),
        }
        if DB_PATH.exists():
            with db() as conn:
                item["active_runs"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM runs WHERE account_alias=? AND status IN ('starting', 'running', 'verifying')",
                        (alias,),
                    ).fetchone()[0]
                )
            day_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            with db() as conn:
                day_row = conn.execute(
                    "SELECT COALESCE(SUM(estimated_cost_usd), 0.0) AS cost FROM runs WHERE account_alias=? AND started_at >= ?",
                    (alias, iso(day_start)),
                ).fetchone()
                month_row = conn.execute(
                    "SELECT COALESCE(SUM(estimated_cost_usd), 0.0) AS cost FROM runs WHERE account_alias=? AND started_at >= ?",
                    (alias, iso(month_start)),
                ).fetchone()
            item["daily_usage"] = {"cost": float((day_row["cost"] if day_row else 0.0) or 0.0)}
            item["monthly_usage"] = {"cost": float((month_row["cost"] if month_row else 0.0) or 0.0)}
        items.append(item)
    return items


def recent_decisions(limit: int = 50) -> List[Dict[str, Any]]:
    if not table_exists("spider_decisions"):
        return []
    with db() as conn:
        rows = conn.execute("SELECT * FROM spider_decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [hydrate_spider_decision(dict(row)) for row in rows]


def json_field(raw: Optional[str], default: Any) -> Any:
    if raw in (None, ""):
        return default
    try:
        value = json.loads(raw)
    except Exception:
        return default
    if isinstance(default, dict) and not isinstance(value, dict):
        return {}
    if isinstance(default, list) and not isinstance(value, list):
        return []
    return value


def decision_meta_summary(meta: Dict[str, Any]) -> str:
    if not meta:
        return ""
    parts: List[str] = []
    if meta.get("predicted_changed_files") is not None:
        parts.append(f"files={meta['predicted_changed_files']}")
    if meta.get("feedback_count") is not None:
        parts.append(f"feedback={meta['feedback_count']}")
    if "spark_eligible" in meta:
        parts.append("spark=yes" if meta.get("spark_eligible") else "spark=no")
    if meta.get("requires_contract_authority"):
        parts.append("contract=yes")
    return ", ".join(parts)


def selection_trace_summary(trace: List[Dict[str, Any]]) -> str:
    skipped: List[str] = []
    for item in trace:
        if item.get("state") == "selected":
            continue
        alias = str(item.get("alias") or "?")
        reason = str(item.get("reason") or item.get("state") or "skipped")
        skipped.append(f"{alias}: {reason}")
    if not skipped:
        return ""
    summary = "; ".join(skipped[:2])
    if len(skipped) > 2:
        summary = f"{summary}; +{len(skipped) - 2} more"
    return summary


def hydrate_spider_decision(row: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(row)
    meta = json_field(item.get("decision_meta_json"), {})
    trace = json_field(item.get("selection_trace_json"), [])
    item["decision_meta"] = meta if isinstance(meta, dict) else {}
    item["selection_trace"] = trace if isinstance(trace, list) else []
    item["decision_meta_summary"] = decision_meta_summary(item["decision_meta"])
    item["selection_trace_summary"] = selection_trace_summary(item["selection_trace"])
    item["skipped_alias_count"] = len([entry for entry in item["selection_trace"] if entry.get("state") != "selected"])
    return item


def parse_optional_float(raw: str) -> Optional[float]:
    value = str(raw or "").strip()
    if not value:
        return None
    return float(value)


def parse_optional_int(raw: str, *, default: Optional[int] = None) -> Optional[int]:
    value = str(raw or "").strip()
    if not value:
        return default
    return int(value)


def update_account_runtime(
    alias: str,
    *,
    clear_backoff: bool = False,
    last_error: Optional[str] = None,
    clear_last_error: bool = False,
) -> None:
    if not DB_PATH.exists():
        return
    fields: List[str] = []
    values: List[Any] = []
    if clear_backoff:
        fields.append("backoff_until=NULL")
    if clear_last_error:
        fields.append("last_error=NULL")
    elif last_error is not None:
        fields.append("last_error=?")
        values.append(last_error)
    if not fields:
        return
    fields.append("updated_at=?")
    values.append(iso(utc_now()))
    values.append(alias)
    with db() as conn:
        conn.execute(f"UPDATE accounts SET {', '.join(fields)} WHERE alias=?", values)


def set_project_enabled(project_id: str, enabled: bool) -> None:
    config = normalize_config()
    project = project_cfg(config, project_id)
    project["enabled"] = bool(enabled)
    save_fleet_config(config)


def update_project_runtime(project_id: str, *, status: Optional[str] = None, clear_cooldown: bool = False, reset_failures: bool = False) -> None:
    if not DB_PATH.exists():
        return
    fields: List[str] = []
    values: List[Any] = []
    if status is not None:
        fields.append("status=?")
        values.append(status)
    if clear_cooldown:
        fields.append("cooldown_until=NULL")
    if reset_failures:
        fields.extend(["consecutive_failures=0", "last_error=NULL"])
    if not fields:
        return
    fields.append("updated_at=?")
    values.append(iso(utc_now()))
    values.append(project_id)
    with db() as conn:
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id=?", values)


def upsert_group_runtime(
    group_id: str,
    *,
    signoff_state: Optional[str] = None,
    mark_audit_requested: bool = False,
    mark_refill_requested: bool = False,
) -> None:
    if not table_exists("group_runtime"):
        return
    now_text = iso(utc_now())
    with db() as conn:
        row = conn.execute("SELECT * FROM group_runtime WHERE group_id=?", (group_id,)).fetchone()
        existing = dict(row) if row else {}
        next_signoff = str(signoff_state or existing.get("signoff_state") or "open").strip().lower() or "open"
        signed_off_at = existing.get("signed_off_at")
        reopened_at = existing.get("reopened_at")
        phase = str(existing.get("phase") or "idle").strip().lower() or "idle"
        last_phase_at = existing.get("last_phase_at")
        if signoff_state is not None:
            if next_signoff == "signed_off":
                signed_off_at = now_text
            else:
                reopened_at = now_text
        last_audit_requested_at = now_text if mark_audit_requested else existing.get("last_audit_requested_at")
        last_refill_requested_at = now_text if mark_refill_requested else existing.get("last_refill_requested_at")
        conn.execute(
            """
            INSERT INTO group_runtime(group_id, signoff_state, signed_off_at, reopened_at, last_audit_requested_at, last_refill_requested_at, phase, last_phase_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                signoff_state=excluded.signoff_state,
                signed_off_at=excluded.signed_off_at,
                reopened_at=excluded.reopened_at,
                last_audit_requested_at=excluded.last_audit_requested_at,
                last_refill_requested_at=excluded.last_refill_requested_at,
                phase=excluded.phase,
                last_phase_at=excluded.last_phase_at,
                updated_at=excluded.updated_at
            """,
            (
                group_id,
                next_signoff,
                signed_off_at,
                reopened_at,
                last_audit_requested_at,
                last_refill_requested_at,
                phase,
                last_phase_at,
                now_text,
            ),
        )


def studio_published_files(repo_root: pathlib.Path) -> List[str]:
    published_dir = repo_root / STUDIO_PUBLISHED_DIR
    if not published_dir.exists() or not published_dir.is_dir():
        return []
    return sorted(child.name for child in published_dir.iterdir() if child.is_file())


def feedback_filename(prefix: str) -> str:
    safe = "".join(ch for ch in prefix.lower() if ch.isalnum() or ch in {"-", "_"}).strip("-_") or "audit"
    return utc_now().strftime(f"%Y-%m-%d-%H%M%S-{safe}.md")


def fleet_repo_root() -> pathlib.Path:
    return CONFIG_PATH.parent.parent


def group_target_root(group_id: str) -> pathlib.Path:
    GROUP_ROOT.mkdir(parents=True, exist_ok=True)
    return GROUP_ROOT / str(group_id).strip()


def group_feedback_root(group_id: str) -> pathlib.Path:
    return group_target_root(group_id) / "feedback"


def group_published_root(group_id: str) -> pathlib.Path:
    return group_target_root(group_id) / STUDIO_PUBLISHED_DIR


def audit_task_candidate_row(candidate_id: int) -> sqlite3.Row:
    if not table_exists("audit_task_candidates"):
        raise HTTPException(404, "audit task candidates table not available")
    with db() as conn:
        row = conn.execute("SELECT * FROM audit_task_candidates WHERE id=?", (candidate_id,)).fetchone()
    if not row:
        raise HTTPException(404, "audit task candidate not found")
    return row


def audit_task_candidate_meta(candidate: Any) -> Dict[str, Any]:
    if isinstance(candidate, sqlite3.Row):
        raw = candidate["task_meta_json"] if "task_meta_json" in candidate.keys() else "{}"
    elif isinstance(candidate, dict):
        raw = candidate.get("task_meta_json", "{}")
    else:
        raw = "{}"
    value = json_field(raw, {})
    return value if isinstance(value, dict) else {}


def audit_finding_row(scope_type: str, scope_id: str, finding_key: str) -> Optional[sqlite3.Row]:
    if not table_exists("audit_findings"):
        return None
    with db() as conn:
        return conn.execute(
            "SELECT * FROM audit_findings WHERE scope_type=? AND scope_id=? AND finding_key=?",
            (scope_type, scope_id, finding_key),
        ).fetchone()


def set_audit_candidate_status(candidate_id: int, status: str, *, resolved: bool) -> None:
    if not table_exists("audit_task_candidates"):
        raise HTTPException(404, "audit task candidates table not available")
    now = iso(utc_now())
    with db() as conn:
        conn.execute(
            "UPDATE audit_task_candidates SET status=?, last_seen_at=?, resolved_at=? WHERE id=?",
            (status, now, now if resolved else None, candidate_id),
        )


def queue_overlay_path(project: Dict[str, Any]) -> pathlib.Path:
    return pathlib.Path(project["path"]) / STUDIO_PUBLISHED_DIR / QUEUE_OVERLAY_FILENAME


def merge_queue_overlay_item(project: Dict[str, Any], item_text: str, *, mode: str = "append") -> pathlib.Path:
    path = queue_overlay_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_yaml(path)
    if isinstance(data, list):
        items = [str(item).strip() for item in data if str(item).strip()]
        existing_mode = "append"
    elif isinstance(data, dict):
        existing_mode = str(data.get("mode", "append") or "append").strip().lower() or "append"
        raw_items = data.get("items")
        if raw_items is None:
            raw_items = data.get("queue")
        items = [str(item).strip() for item in (raw_items or []) if str(item).strip()]
    else:
        existing_mode = "append"
        items = []
    text = str(item_text).strip()
    queue_mode = str(mode or existing_mode or "append").strip().lower() or "append"
    if text:
        items = [item for item in items if item != text]
        if queue_mode == "replace":
            items = [text]
        elif queue_mode == "prepend":
            items = [text] + items
        else:
            items.append(text)
    save_yaml(path, {"mode": queue_mode, "items": items})
    return path


def log_group_publish_event(
    group_id: str,
    *,
    source: str,
    source_scope_type: str,
    source_scope_id: str,
    finding_key: Optional[str],
    candidate_id: Optional[int],
    published_targets: List[Dict[str, Any]],
) -> None:
    if not table_exists("group_publish_events"):
        return
    with db() as conn:
        conn.execute(
            """
            INSERT INTO group_publish_events(group_id, source, source_scope_type, source_scope_id, finding_key, candidate_id, published_targets_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group_id,
                source,
                source_scope_type,
                source_scope_id,
                finding_key,
                candidate_id,
                json.dumps(published_targets, indent=2),
                iso(utc_now()),
            ),
        )


def render_group_blockers_markdown(
    group_id: str,
    candidate: sqlite3.Row,
    finding: Optional[sqlite3.Row],
    config: Dict[str, Any],
) -> str:
    group = group_cfg(config, group_id)
    lines = ["# Group Blockers", "", f"Generated: {utc_now().date().isoformat()}", ""]
    members = [str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()]
    if members:
        lines.append(f"Members: {', '.join(members)}")
        lines.append("")
    lines.extend(
        [
            f"## Auditor Candidate #{candidate['id']}",
            "",
            f"- Finding Key: {candidate['finding_key']}",
            f"- Title: {candidate['title']}",
            f"- Detail: {candidate['detail']}",
        ]
    )
    if finding:
        lines.extend(
            [
                f"- Severity: {finding['severity']}",
                f"- Summary: {finding['summary']}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_group_contract_sets_yaml(group_id: str, candidate: sqlite3.Row, config: Dict[str, Any]) -> str:
    group = group_cfg(config, group_id)
    payload = {
        "group_id": group_id,
        "contract_sets": list(group.get("contract_sets") or []),
        "published_from_auditor": [
            {
                "candidate_id": int(candidate["id"]),
                "finding_key": str(candidate["finding_key"] or ""),
                "title": str(candidate["title"] or ""),
                "detail": str(candidate["detail"] or ""),
                "published_at": iso(utc_now()),
            }
        ],
    }
    return yaml.safe_dump(payload, sort_keys=False)


def render_group_program_milestones_yaml(group_id: str, candidate: sqlite3.Row, finding: Optional[sqlite3.Row], config: Dict[str, Any]) -> str:
    registry = load_program_registry(config)
    group_meta = dict((registry.get("groups") or {}).get(group_id, {}) or {})
    payload = {
        "groups": {
            group_id: {
                "milestone_coverage_complete": bool(group_meta.get("milestone_coverage_complete")),
                "design_coverage_complete": bool(group_meta.get("design_coverage_complete")),
                "uncovered_scope": text_items(group_meta.get("uncovered_scope")),
                "remaining_milestones": remaining_milestone_items(group_meta),
                "auditor_publication": {
                    "candidate_id": int(candidate["id"]),
                    "finding_key": str(candidate["finding_key"] or ""),
                    "title": str(candidate["title"] or ""),
                    "detail": str(candidate["detail"] or ""),
                    "severity": str(finding["severity"] if finding else ""),
                    "published_at": iso(utc_now()),
                },
            }
        }
    }
    return yaml.safe_dump(payload, sort_keys=False)


def publish_project_audit_candidate(candidate_id: int, *, queue_mode: str = "append", source: str = "manual") -> Dict[str, Any]:
    candidate = audit_task_candidate_row(candidate_id)
    if candidate["scope_type"] != "project":
        raise HTTPException(400, "only project-scoped audit task candidates can be published directly")
    config = normalize_config()
    try:
        project = project_cfg(config, candidate["scope_id"])
    except KeyError as exc:
        raise HTTPException(404, f"unknown project target: {candidate['scope_id']}") from exc

    finding = audit_finding_row(candidate["scope_type"], candidate["scope_id"], candidate["finding_key"])
    overlay_path = merge_queue_overlay_item(project, str(candidate["detail"] or candidate["title"] or "").strip(), mode=queue_mode)

    feedback_dir = pathlib.Path(project["path"]) / project.get("feedback_dir", "feedback")
    feedback_dir.mkdir(parents=True, exist_ok=True)
    note_name = feedback_filename(f"audit-task-{candidate_id}")
    note_path = feedback_dir / note_name
    note_lines = [
        "# Auditor Publication",
        "",
        f"Date: {utc_now().date().isoformat()}",
        f"Candidate ID: {candidate_id}",
        f"Scope: {candidate['scope_type']}:{candidate['scope_id']}",
        f"Finding Key: {candidate['finding_key']}",
        "",
        f"## Task",
        f"- Title: {candidate['title']}",
        f"- Detail: {candidate['detail']}",
        "",
    ]
    if finding:
        note_lines.extend(
            [
                "## Finding",
                f"- Severity: {finding['severity']}",
                f"- Title: {finding['title']}",
                f"- Summary: {finding['summary']}",
                "",
            ]
        )
    note_lines.extend(
        [
            "## Publication",
            f"- Queue overlay: {overlay_path}",
            f"- Queue mode: {queue_mode}",
            f"- Feedback note: {note_path}",
            "",
            "This task was published from the fleet auditor board.",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    update_project_runtime(project["id"], status="idle", clear_cooldown=True)
    project_groups = project_group_defs(config, project["id"])
    if project_groups:
        group_id = str(project_groups[0].get("id") or "")
        upsert_group_runtime(group_id, signoff_state="open", mark_refill_requested=True)
        log_group_publish_event(
            group_id,
            source=source,
            source_scope_type="project",
            source_scope_id=project["id"],
            finding_key=str(candidate["finding_key"] or ""),
            candidate_id=int(candidate_id),
            published_targets=[
                {
                    "target_type": "project",
                    "target_id": project["id"],
                    "queue_overlay": str(overlay_path),
                    "feedback_note": str(note_path),
                }
            ],
        )
        log_group_run(
            group_id,
            run_kind="publish",
            phase="proposed_tasks",
            status="published",
            member_projects=[str(project["id"])],
            details={
                "source_scope_type": "project",
                "source_scope_id": str(project["id"]),
                "candidate_id": int(candidate_id),
                "finding_key": str(candidate["finding_key"] or ""),
                "queue_mode": queue_mode,
            },
        )
    set_audit_candidate_status(candidate_id, "published", resolved=True)
    return {
        "candidate_id": candidate_id,
        "project_id": project["id"],
        "queue_overlay": str(overlay_path),
        "feedback_note": str(note_path),
    }


def publish_group_audit_candidate(candidate_id: int, *, source: str = "manual") -> Dict[str, Any]:
    candidate = audit_task_candidate_row(candidate_id)
    if candidate["scope_type"] != "group":
        raise HTTPException(400, "only group-scoped audit task candidates can be published as group artifacts")
    config = normalize_config()
    group_id = str(candidate["scope_id"] or "").strip()
    group_cfg(config, group_id)
    finding = audit_finding_row(candidate["scope_type"], candidate["scope_id"], candidate["finding_key"])
    task_meta = audit_task_candidate_meta(candidate)

    published_root = group_published_root(group_id)
    feedback_root = group_feedback_root(group_id)
    published_root.mkdir(parents=True, exist_ok=True)
    feedback_root.mkdir(parents=True, exist_ok=True)

    blockers_path = published_root / "GROUP_BLOCKERS.md"
    blockers_path.write_text(render_group_blockers_markdown(group_id, candidate, finding, config), encoding="utf-8")

    published_targets: List[Dict[str, Any]] = [
        {"target_type": "group", "target_id": group_id, "path": str(blockers_path), "file_count": 1}
    ]

    detail_lower = f"{candidate['finding_key']} {candidate['title']} {candidate['detail']}".lower()
    if "contract" in detail_lower or "session" in detail_lower or "dto" in detail_lower or "explain" in detail_lower:
        contract_path = published_root / "CONTRACT_SETS.yaml"
        contract_path.write_text(render_group_contract_sets_yaml(group_id, candidate, config), encoding="utf-8")
        published_targets.append({"target_type": "group", "target_id": group_id, "path": str(contract_path), "file_count": 1})
    if "milestone" in detail_lower or "scope" in detail_lower or "coverage" in detail_lower:
        milestone_path = published_root / "PROGRAM_MILESTONES.generated.yaml"
        milestone_path.write_text(render_group_program_milestones_yaml(group_id, candidate, finding, config), encoding="utf-8")
        published_targets.append({"target_type": "group", "target_id": group_id, "path": str(milestone_path), "file_count": 1})

    bootstrap_result: Dict[str, Any] = {}
    bootstrap_spec = dict(task_meta.get("bootstrap_project") or {})
    if bootstrap_spec:
        bootstrap_spec.setdefault("group_id", group_id)
        bootstrap_result = bootstrap_project_from_spec(bootstrap_spec)
        published_targets.append(
            {
                "target_type": "project",
                "target_id": bootstrap_result["project_id"],
                "path": bootstrap_result["path"],
                "file_count": 1,
            }
        )

    note_path = feedback_root / feedback_filename(f"group-audit-task-{candidate_id}")
    note_lines = [
        "# Group Auditor Publication",
        "",
        f"Date: {utc_now().date().isoformat()}",
        f"Candidate ID: {candidate_id}",
        f"Group: {group_id}",
        f"Finding Key: {candidate['finding_key']}",
        f"Source: {source}",
        "",
        "## Task",
        f"- Title: {candidate['title']}",
        f"- Detail: {candidate['detail']}",
    ]
    if finding:
        note_lines.extend(
            [
                "",
                "## Finding",
                f"- Severity: {finding['severity']}",
                f"- Title: {finding['title']}",
                f"- Summary: {finding['summary']}",
            ]
        )
    if bootstrap_result:
        note_lines.extend(
            [
                "",
                "## Bootstrap Result",
                f"- Project ID: {bootstrap_result['project_id']}",
                f"- Repo Path: {bootstrap_result['path']}",
                f"- Group ID: {bootstrap_result['group_id'] or group_id}",
            ]
        )
    note_lines.extend(
        [
            "",
            "## Published Targets",
            *[f"- {item['path']}" for item in published_targets],
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")
    published_targets.append({"target_type": "group", "target_id": group_id, "path": str(note_path), "file_count": 1})

    upsert_group_runtime(group_id, signoff_state="open", mark_refill_requested=True)
    log_group_publish_event(
        group_id,
        source=source,
        source_scope_type="group",
        source_scope_id=group_id,
        finding_key=str(candidate["finding_key"] or ""),
        candidate_id=int(candidate_id),
        published_targets=published_targets,
    )
    log_group_run(
        group_id,
        run_kind="publish",
        phase="proposed_tasks",
        status="published",
        member_projects=[str(project_id).strip() for project_id in (group_cfg(config, group_id).get("projects") or []) if str(project_id).strip()],
        details={
            "source_scope_type": "group",
            "source_scope_id": group_id,
            "candidate_id": int(candidate_id),
            "finding_key": str(candidate["finding_key"] or ""),
        },
    )
    set_audit_candidate_status(candidate_id, "published", resolved=True)
    return {
        "candidate_id": candidate_id,
        "group_id": group_id,
        "published_targets": published_targets,
    }


def publish_fleet_audit_candidate(candidate_id: int, *, source: str = "manual") -> Dict[str, Any]:
    candidate = audit_task_candidate_row(candidate_id)
    if candidate["scope_type"] != "fleet":
        raise HTTPException(400, "only fleet-scoped audit task candidates can bootstrap new projects")
    task_meta = audit_task_candidate_meta(candidate)
    bootstrap_spec = dict(task_meta.get("bootstrap_project") or {})
    if not bootstrap_spec:
        raise HTTPException(400, "fleet candidate is missing bootstrap_project metadata")
    result = bootstrap_project_from_spec(bootstrap_spec)

    note_path = fleet_repo_root() / "feedback" / feedback_filename(f"fleet-audit-task-{candidate_id}")
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        "\n".join(
            [
                "# Fleet Auditor Publication",
                "",
                f"Date: {utc_now().date().isoformat()}",
                f"Candidate ID: {candidate_id}",
                f"Scope: {candidate['scope_type']}:{candidate['scope_id']}",
                f"Finding Key: {candidate['finding_key']}",
                f"Source: {source}",
                "",
                "## Task",
                f"- Title: {candidate['title']}",
                f"- Detail: {candidate['detail']}",
                "",
                "## Bootstrap Result",
                f"- Project ID: {result['project_id']}",
                f"- Repo Path: {result['path']}",
                f"- Group ID: {result['group_id'] or 'singleton'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    group_id = str(result.get("group_id") or "").strip()
    if group_id:
        upsert_group_runtime(group_id, signoff_state="open", mark_refill_requested=True)
        log_group_publish_event(
            group_id,
            source=source,
            source_scope_type="fleet",
            source_scope_id="fleet",
            finding_key=str(candidate["finding_key"] or ""),
            candidate_id=int(candidate_id),
            published_targets=[
                {"target_type": "project", "target_id": result["project_id"], "path": result["path"], "file_count": 1},
                {"target_type": "fleet", "target_id": "fleet", "path": str(note_path), "file_count": 1},
            ],
        )
        log_group_run(
            group_id,
            run_kind="publish",
            phase="proposed_tasks",
            status="published",
            member_projects=[result["project_id"]],
            details={
                "source_scope_type": "fleet",
                "source_scope_id": "fleet",
                "candidate_id": int(candidate_id),
                "finding_key": str(candidate["finding_key"] or ""),
                "bootstrap_project": result["project_id"],
            },
        )
    set_audit_candidate_status(candidate_id, "published", resolved=True)
    return {"candidate_id": candidate_id, "bootstrap_result": result, "feedback_note": str(note_path)}


def trigger_auditor_run() -> None:
    request = urllib.request.Request(f"{AUDITOR_URL}/api/auditor/run-now", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30):
            return
    except urllib.error.URLError as exc:
        raise HTTPException(502, f"unable to trigger fleet-auditor: {exc}") from exc


def set_group_enabled(group_id: str, enabled: bool) -> None:
    config = normalize_config()
    group = group_cfg(config, group_id)
    for project_id in group.get("projects") or []:
        set_project_enabled(str(project_id), enabled)
        if enabled:
            update_project_runtime(str(project_id), status="idle", clear_cooldown=True)


def publish_group_approved_tasks(group_id: str, *, queue_mode: str = "append") -> int:
    config = normalize_config()
    group = group_cfg(config, group_id)
    project_ids = [str(project_id) for project_id in (group.get("projects") or []) if str(project_id).strip()]
    if not table_exists("audit_task_candidates"):
        return 0
    with db() as conn:
        rows: List[sqlite3.Row] = []
        if project_ids:
            placeholders = ",".join("?" for _ in project_ids)
            rows.extend(
                conn.execute(
                    f"""
                    SELECT id, scope_type
                    FROM audit_task_candidates
                    WHERE scope_type='project'
                      AND scope_id IN ({placeholders})
                      AND status='approved'
                    ORDER BY scope_id, last_seen_at ASC, task_index ASC
                    """,
                    tuple(project_ids),
                ).fetchall()
            )
        rows.extend(
            conn.execute(
                """
                SELECT id, scope_type
                FROM audit_task_candidates
                WHERE scope_type='group'
                  AND scope_id=?
                  AND status='approved'
                ORDER BY last_seen_at ASC, task_index ASC
                """,
                (group_id,),
            ).fetchall()
        )
    published = 0
    for row in rows:
        if row["scope_type"] == "group":
            publish_group_audit_candidate(int(row["id"]), source="group_refill")
        else:
            publish_project_audit_candidate(int(row["id"]), queue_mode=queue_mode, source="group_refill")
        published += 1
    return published


def merged_projects() -> List[Dict[str, Any]]:
    config = normalize_config()
    registry = load_program_registry(config)
    runtime = project_runtime_rows()
    group_runtime = group_runtime_rows()
    now = utc_now()
    usage_start = usage_window_start(config)
    items: List[Dict[str, Any]] = []
    for project in config.get("projects", []):
        row = dict(project)
        runtime_row = runtime.get(project["id"], {})
        project_groups = project_group_defs(config, project["id"])
        row["queue_index"] = int(runtime_row.get("queue_index") or 0)
        queue_items = json.loads(runtime_row.get("queue_json") or "[]") if runtime_row.get("queue_json") else list(project.get("queue") or [])
        has_queue_sources = bool(project.get("queue_sources"))
        runtime_status = effective_runtime_status(
            stored_status=runtime_row.get("status"),
            queue_len=len(queue_items),
            queue_index=row["queue_index"],
            enabled=bool(project.get("enabled", True)),
            active_run_id=runtime_row.get("active_run_id"),
            source_backlog_open=has_queue_sources and bool(queue_items),
        )
        row["runtime_status_internal"] = runtime_status
        row["group_ids"] = [group["id"] for group in project_groups]
        row["completion_basis"] = runtime_completion_basis(
            runtime_status=runtime_status,
            queue_len=len(queue_items),
            queue_index=row["queue_index"],
            has_queue_sources=has_queue_sources,
        )
        row["queue_len"] = len(queue_items)
        row["current_slice"] = queue_items[row["queue_index"]] if row["queue_index"] < len(queue_items) else None
        row["last_error"] = runtime_row.get("last_error")
        row["cooldown_until"] = runtime_row.get("cooldown_until")
        row["consecutive_failures"] = runtime_row.get("consecutive_failures", 0)
        row["published_files"] = studio_published_files(pathlib.Path(project["path"]))
        project_meta = registry["projects"].get(project["id"], {})
        project_group_meta = effective_group_meta(project_groups[0], registry, group_runtime) if project_groups else {}
        row["group_signed_off"] = group_is_signed_off(project_group_meta)
        row["remaining_milestones"] = remaining_milestone_items(project_meta)
        row["uncovered_scope"] = text_items(project_meta.get("uncovered_scope"))
        row["uncovered_scope_count"] = len(row["uncovered_scope"])
        row["milestone_coverage_complete"] = bool(project_meta.get("milestone_coverage_complete"))
        row["design_coverage_complete"] = bool(project_meta.get("design_coverage_complete"))
        row["audit_task_counts"] = project_audit_task_counts(project["id"])
        row["milestone_eta"] = estimate_registry_eta(
            project_meta,
            now,
            coverage_key="milestone_coverage_complete",
            missing_basis="no milestone registry configured for this project",
            incomplete_basis="milestone coverage incomplete",
            zero_basis="all defined milestones complete",
            missing_reason="no_milestone_registry",
            incomplete_reason="milestone_coverage_incomplete",
        )
        row["design_eta"] = estimate_registry_eta(
            project_meta,
            now,
            coverage_key="design_coverage_complete",
            missing_basis="no design coverage registry configured for this project",
            incomplete_basis="design coverage incomplete",
            zero_basis="design responsibilities fully mapped and current milestone set is complete",
            missing_reason="no_design_registry",
            incomplete_reason="design_coverage_incomplete",
        )
        row.update(
            project_stop_context(
                project_cfg=project,
                runtime_status=runtime_status,
                queue_len=len(queue_items),
                uncovered_scope_count=row["uncovered_scope_count"],
                open_task_count=row["audit_task_counts"]["open"],
                approved_task_count=row["audit_task_counts"]["approved"],
                last_error=row["last_error"],
                cooldown_until=row["cooldown_until"],
                milestone_coverage_complete=row["milestone_coverage_complete"],
                design_coverage_complete=row["design_coverage_complete"],
                group_signed_off=row["group_signed_off"],
            )
        )
        row["pressure_state"] = project_pressure_state(row)
        row["allowance_usage"] = recent_usage_for_scope([project["id"]], usage_start)
        row["runtime_status"] = public_project_status(
            runtime_status,
            cooldown_until=row["cooldown_until"],
            needs_refill=bool(row.get("needs_refill")),
            open_task_count=int(row["audit_task_counts"]["open"]),
            approved_task_count=int(row["audit_task_counts"]["approved"]),
        )
        items.append(row)
    return items


def summarize_ops(
    projects: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
    account_pools: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stopped_not_signed_off = [project for project in projects if project.get("stopped_not_signed_off")]
    blocked_projects = [
        project
        for project in projects
        if project.get("runtime_status_internal") in {"blocked", SOURCE_BACKLOG_OPEN_STATUS, "awaiting_account"}
        or project.get("needs_refill")
    ]
    queue_exhausted_projects = [
        project
        for project in projects
        if project.get("runtime_status_internal") in {"complete", SOURCE_BACKLOG_OPEN_STATUS}
        or project.get("runtime_status") in {"audit_required", "proposed_tasks"}
    ]
    proposed_task_groups = [group for group in groups if str(group.get("status") or "") == "proposed_tasks"]
    cooling_down = [project for project in projects if project.get("cooldown_until")]
    accounts_needing_attention = [
        pool
        for pool in account_pools
        if str(pool.get("pool_state") or "") != "ready" or str(pool.get("auth_status") or "") != "ready" or pool.get("last_error")
    ]
    group_blockers = [
        group for group in groups if group.get("contract_blockers") or group.get("dispatch_blockers") or not group.get("dispatch_ready", True)
    ]
    audit_required_groups = [group for group in groups if str(group.get("status") or "") == "audit_required"]
    high_pressure_groups = [group for group in groups if str(group.get("pressure_state") or "") in {"critical", "high"}]
    tight_pool_groups = [
        group for group in groups if str((group.get("pool_sufficiency") or {}).get("level") or "") in {"blocked", "insufficient", "tight"}
    ]
    ready_to_run_now = [
        group
        for group in groups
        if bool(group.get("dispatch_ready")) and str(group.get("status") or "") not in {"audit_required", "product_signed_off"}
    ]
    runs_needing_attention = [
        run
        for run in runs
        if str(run.get("status") or "").strip().lower() not in {"complete", "starting", "running", "verifying"}
    ]
    return {
        "stopped_not_signed_off": stopped_not_signed_off,
        "blocked_projects": blocked_projects,
        "queue_exhausted_projects": queue_exhausted_projects,
        "proposed_task_groups": proposed_task_groups,
        "cooling_down": cooling_down,
        "accounts_needing_attention": accounts_needing_attention,
        "group_blockers": group_blockers,
        "audit_required_groups": audit_required_groups,
        "high_pressure_groups": high_pressure_groups,
        "tight_pool_groups": tight_pool_groups,
        "ready_to_run_now": ready_to_run_now,
        "runs_needing_attention": runs_needing_attention,
        "open_findings": findings,
    }


def admin_status_payload() -> Dict[str, Any]:
    config = normalize_config()
    projects = merged_projects()
    registry = load_program_registry(config)
    group_runtime = group_runtime_rows()
    project_map = {project["id"]: project for project in projects}
    now = utc_now()
    usage_start = usage_window_start(config)
    groups: List[Dict[str, Any]] = []
    for group_cfg in config.get("project_groups") or []:
        group_meta = effective_group_meta(group_cfg, registry, group_runtime)
        group_projects = [project_map[project_id] for project_id in group_cfg.get("projects") or [] if project_id in project_map]
        group_row = dict(group_cfg)
        group_row["captain"] = group_captain_policy(group_cfg)
        group_row["signed_off"] = group_is_signed_off(group_meta)
        group_row["signoff_state"] = str(group_meta.get("signoff_state") or ("signed_off" if group_row["signed_off"] else "open"))
        group_row["signed_off_at"] = group_meta.get("signed_off_at")
        group_row["reopened_at"] = group_meta.get("reopened_at")
        group_row["last_audit_requested_at"] = group_meta.get("last_audit_requested_at")
        group_row["last_refill_requested_at"] = group_meta.get("last_refill_requested_at")
        group_row["contract_blockers"] = text_items(group_meta.get("contract_blockers"))
        group_row["remaining_milestones"] = remaining_milestone_items(group_meta)
        group_row["uncovered_scope"] = text_items(group_meta.get("uncovered_scope"))
        group_row["uncovered_scope_count"] = len(group_row["uncovered_scope"])
        group_row["milestone_coverage_complete"] = bool(group_meta.get("milestone_coverage_complete"))
        group_row["design_coverage_complete"] = bool(group_meta.get("design_coverage_complete"))
        group_row.update(group_dispatch_state(group_cfg, group_meta, group_projects, now))
        group_row["status"] = effective_group_status(group_cfg, group_meta, group_projects)
        group_row["phase"] = derive_group_phase(group_row, group_projects)
        group_row["project_statuses"] = [{"id": project["id"], "status": project["runtime_status"]} for project in group_projects]
        group_row["allowance_usage"] = recent_usage_for_scope([project["id"] for project in group_projects], usage_start)
        group_row["pool_sufficiency"] = group_pool_sufficiency(config, group_cfg, group_projects, now)
        group_row["pressure_state"] = group_pressure_state(group_row, group_projects)
        group_row["milestone_eta"] = estimate_registry_eta(
            group_meta,
            now,
            coverage_key="milestone_coverage_complete",
            missing_basis="no group milestone registry configured",
            incomplete_basis="group milestone coverage incomplete",
            zero_basis="all defined group milestones complete",
            missing_reason="no_group_milestone_registry",
            incomplete_reason="group_milestone_coverage_incomplete",
        )
        group_row["program_eta"] = estimate_registry_eta(
            group_meta,
            now,
            coverage_key="design_coverage_complete",
            missing_basis="no program registry configured for this group",
            incomplete_basis="program milestone coverage incomplete",
            zero_basis="program responsibilities are fully mapped and the current group milestone set is complete",
            missing_reason="no_program_registry",
            incomplete_reason="program_coverage_incomplete",
        )
        groups.append(group_row)
    account_pools = account_pool_rows(config)
    findings = audit_findings()
    task_candidates = audit_task_candidates()
    recent_run_rows = recent_runs()
    recent_decision_rows = recent_decisions()
    return {
        "projects": projects,
        "groups": groups,
        "config": {
            "policies": config.get("policies", {}),
            "spider": config.get("spider", {}),
            "projects": projects,
            "groups": groups,
            "accounts": config.get("accounts", {}),
        },
        "account_pools": account_pools,
        "auditor": {
            "last_run": recent_auditor_run(),
            "findings": findings,
            "task_candidates": task_candidates,
        },
        "studio_publish_events": studio_publish_events(),
        "group_publish_events": group_publish_events(),
        "group_runs": group_runs(),
        "recent_runs": recent_run_rows,
        "recent_decisions": recent_decision_rows,
        "ops_summary": summarize_ops(projects, groups, account_pools, findings, recent_run_rows),
        "generated_at": iso(utc_now()),
    }


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/api/admin/status")
def api_admin_status() -> Dict[str, Any]:
    return admin_status_payload()


@app.post("/api/admin/projects/add")
def api_admin_add_project(
    project_id: str = Form(...),
    repo_path: str = Form(...),
    design_doc: str = Form(""),
    verify_cmd: str = Form(""),
    feedback_dir: str = Form("feedback"),
    state_file: str = Form(".agent-state.json"),
    account_aliases: str = Form(""),
    queue_items: str = Form(""),
    bootstrap_files: Optional[str] = Form(None),
) -> RedirectResponse:
    config = normalize_config()
    if any(project.get("id") == project_id for project in config.get("projects", [])):
        raise HTTPException(400, f"project id already exists: {project_id}")

    repo_root = validate_repo_path(repo_path)
    accounts = split_items(account_aliases)
    queue = split_items(queue_items)
    project = {
        "id": project_id.strip(),
        "path": str(repo_root),
        "design_doc": resolve_optional_repo_file(repo_root, design_doc),
        "verify_cmd": verify_cmd.strip(),
        "feedback_dir": feedback_dir.strip() or "feedback",
        "state_file": state_file.strip() or ".agent-state.json",
        "enabled": True,
        "accounts": accounts,
        "runner": {
            "sandbox": "workspace-write",
            "approval_policy": "never",
            "exec_timeout_seconds": 5400,
            "verify_timeout_seconds": 1800,
            "always_continue": True,
            "avoid_permission_escalation": True,
            "config_overrides": [],
        },
        "queue": queue,
    }
    if bootstrap_files:
        bootstrap_repo_ai_files(repo_root, project["feedback_dir"], project["state_file"])

    config.setdefault("projects", []).append(project)
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/bootstrap")
def api_admin_bootstrap_project(
    project_id: str = Form(...),
    repo_path: str = Form(...),
    group_id: str = Form(""),
    design_doc: str = Form(""),
    verify_cmd: str = Form(""),
    feedback_dir: str = Form("feedback"),
    state_file: str = Form(".agent-state.json"),
    account_aliases: str = Form(""),
    preferred_accounts: str = Form(""),
    burst_accounts: str = Form(""),
    reserve_accounts: str = Form(""),
    queue_items: str = Form(""),
    create_repo_dir: Optional[str] = Form(None),
    bootstrap_files: Optional[str] = Form(None),
    init_local_git: Optional[str] = Form(None),
    create_github_repo: Optional[str] = Form(None),
    github_owner: str = Form(""),
    github_repo: str = Form(""),
    github_visibility: str = Form("private"),
) -> RedirectResponse:
    bootstrap_project_from_spec(
        {
            "project_id": project_id,
            "repo_path": repo_path,
            "group_id": group_id,
            "design_doc": design_doc,
            "verify_cmd": verify_cmd,
            "feedback_dir": feedback_dir,
            "state_file": state_file,
            "account_aliases": account_aliases,
            "preferred_accounts": preferred_accounts,
            "burst_accounts": burst_accounts,
            "reserve_accounts": reserve_accounts,
            "queue_items": queue_items,
            "create_repo_dir": create_repo_dir is not None,
            "bootstrap_files": bootstrap_files is not None,
            "init_local_git": init_local_git is not None,
            "create_github_repo": create_github_repo is not None,
            "github_owner": github_owner,
            "github_repo": github_repo,
            "github_visibility": github_visibility,
        }
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/accounts/upsert")
def api_admin_upsert_account(
    alias: str = Form(...),
    auth_kind: str = Form(...),
    allowed_models: str = Form(""),
    api_key_env: str = Form(""),
    api_key_file: str = Form(""),
    auth_json_file: str = Form(""),
    daily_budget_usd: str = Form(""),
    monthly_budget_usd: str = Form(""),
    max_parallel_runs: str = Form("1"),
    health_state: str = Form("ready"),
    project_allowlist: str = Form(""),
    spark_enabled: Optional[str] = Form(None),
) -> RedirectResponse:
    config = normalize_config()
    accounts = dict(config.get("accounts", {}) or {})
    clean_alias = str(alias or "").strip()
    if not clean_alias:
        raise HTTPException(400, "account alias is required")
    account = {
        "auth_kind": str(auth_kind or "api_key").strip() or "api_key",
        "allowed_models": split_items(allowed_models),
        "daily_budget_usd": parse_optional_float(daily_budget_usd),
        "monthly_budget_usd": parse_optional_float(monthly_budget_usd),
        "max_parallel_runs": max(1, int(parse_optional_int(max_parallel_runs, default=1) or 1)),
        "health_state": str(health_state or "ready").strip() or "ready",
        "project_allowlist": split_items(project_allowlist),
        "spark_enabled": spark_enabled is not None,
    }
    if str(api_key_env or "").strip():
        account["api_key_env"] = str(api_key_env).strip()
    if str(api_key_file or "").strip():
        account["api_key_file"] = str(api_key_file).strip()
    if str(auth_json_file or "").strip():
        account["auth_json_file"] = str(auth_json_file).strip()
    accounts[clean_alias] = account
    save_accounts_config(accounts)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/accounts/{alias}/state")
def api_admin_set_account_state(alias: str, state: str = Form(...)) -> RedirectResponse:
    config = normalize_config()
    accounts = dict(config.get("accounts", {}) or {})
    if alias not in accounts:
        raise HTTPException(404, f"unknown account alias: {alias}")
    accounts[alias]["health_state"] = str(state or "ready").strip() or "ready"
    save_accounts_config(accounts)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/accounts/{alias}/clear-backoff")
def api_admin_clear_account_backoff(alias: str) -> RedirectResponse:
    update_account_runtime(alias, clear_backoff=True, clear_last_error=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/accounts/{alias}/validate")
def api_admin_validate_account(alias: str) -> RedirectResponse:
    config = normalize_config()
    account = (config.get("accounts", {}) or {}).get(alias)
    if not account:
        raise HTTPException(404, f"unknown account alias: {alias}")
    auth_status = account_auth_status(account)
    update_account_runtime(alias, clear_last_error=(auth_status == "ready"), last_error=None if auth_status == "ready" else auth_status)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/routing/update")
def api_admin_update_routing(
    classification_mode: str = Form("heuristic_v2"),
    feedback_file_window: str = Form("2"),
    escalate_to_complex_after_failures: str = Form("2"),
    token_alliance_window_hours: str = Form("24"),
) -> RedirectResponse:
    config = normalize_config()
    spider = dict(config.get("spider", {}) or {})
    spider["classification_mode"] = str(classification_mode or "heuristic_v2").strip() or "heuristic_v2"
    spider["feedback_file_window"] = max(0, int(parse_optional_int(feedback_file_window, default=2) or 2))
    spider["escalate_to_complex_after_failures"] = max(1, int(parse_optional_int(escalate_to_complex_after_failures, default=2) or 2))
    spider["token_alliance_window_hours"] = max(1, int(parse_optional_int(token_alliance_window_hours, default=24) or 24))
    config["spider"] = spider
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/routing/classes/{route_class}")
def api_admin_update_routing_class(
    route_class: str,
    models: str = Form(""),
    reasoning_effort: str = Form("low"),
    estimated_output_tokens: str = Form("1024"),
) -> RedirectResponse:
    clean_route_class = str(route_class or "").strip()
    if not clean_route_class:
        raise HTTPException(400, "route class is required")
    config = normalize_config()
    spider = dict(config.get("spider", {}) or {})
    tier_preferences = dict(spider.get("tier_preferences", {}) or {})
    tier_preferences[clean_route_class] = {
        "models": split_items(models),
        "reasoning_effort": str(reasoning_effort or "low").strip() or "low",
        "estimated_output_tokens": max(1, int(parse_optional_int(estimated_output_tokens, default=1024) or 1024)),
    }
    spider["tier_preferences"] = tier_preferences
    config["spider"] = spider
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/pause")
def api_admin_pause_project(project_id: str) -> RedirectResponse:
    set_project_enabled(project_id, False)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/resume")
def api_admin_resume_project(project_id: str) -> RedirectResponse:
    set_project_enabled(project_id, True)
    update_project_runtime(project_id, status="idle", clear_cooldown=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/clear-cooldown")
def api_admin_clear_cooldown(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, clear_cooldown=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/retry")
def api_admin_retry_project(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, status="idle", clear_cooldown=True, reset_failures=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/run-now")
def api_admin_run_now(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, status="idle", clear_cooldown=True, reset_failures=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/account-policy")
def api_admin_update_project_account_policy(
    project_id: str,
    preferred_accounts: str = Form(""),
    burst_accounts: str = Form(""),
    reserve_accounts: str = Form(""),
    allow_chatgpt_accounts: Optional[str] = Form(None),
    allow_api_accounts: Optional[str] = Form(None),
    spark_enabled: Optional[str] = Form(None),
) -> RedirectResponse:
    config = normalize_config()
    project = project_cfg(config, project_id)
    project["account_policy"] = {
        "preferred_accounts": split_items(preferred_accounts),
        "burst_accounts": split_items(burst_accounts),
        "reserve_accounts": split_items(reserve_accounts),
        "allow_chatgpt_accounts": allow_chatgpt_accounts is not None,
        "allow_api_accounts": allow_api_accounts is not None,
        "spark_enabled": spark_enabled is not None,
    }
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/captain")
def api_admin_update_group_captain(
    group_id: str,
    priority: str = Form("100"),
    service_floor: str = Form("1"),
    shed_order: str = Form("100"),
    preemption_policy: str = Form("slice_boundary"),
    admission_policy: str = Form("normal"),
) -> RedirectResponse:
    config = normalize_config()
    group = group_cfg(config, group_id)
    group["captain"] = normalized_captain_policy(
        {
            "priority": parse_optional_int(priority, default=100) or 100,
            "service_floor": parse_optional_int(service_floor, default=1) or 1,
            "shed_order": parse_optional_int(shed_order, default=100) or 100,
            "preemption_policy": str(preemption_policy or "slice_boundary").strip() or "slice_boundary",
            "admission_policy": str(admission_policy or "normal").strip() or "normal",
        },
        default_service_floor=max(1, len(group.get("projects") or [])) if str(group.get("mode", "") or "").strip().lower() == "lockstep" and (group.get("projects") or []) else 1,
    )
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/auditor/run-now")
def api_admin_run_auditor_now() -> RedirectResponse:
    trigger_auditor_run()
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/audit-now")
def api_admin_run_group_auditor_now(group_id: str) -> RedirectResponse:
    group = group_cfg(normalize_config(), group_id)
    upsert_group_runtime(group_id, mark_audit_requested=True)
    log_group_run(
        group_id,
        run_kind="audit",
        phase="audit_required",
        status="requested",
        member_projects=[str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()],
        details={"requested_by": "admin"},
    )
    trigger_auditor_run()
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/pause")
def api_admin_pause_group(group_id: str) -> RedirectResponse:
    group = group_cfg(normalize_config(), group_id)
    set_group_enabled(group_id, False)
    log_group_run(
        group_id,
        run_kind="pause",
        phase="blocked",
        status="requested",
        member_projects=[str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()],
        details={"requested_by": "admin"},
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/resume")
def api_admin_resume_group(group_id: str) -> RedirectResponse:
    group = group_cfg(normalize_config(), group_id)
    set_group_enabled(group_id, True)
    upsert_group_runtime(group_id, signoff_state="open")
    log_group_run(
        group_id,
        run_kind="resume",
        phase="ready",
        status="requested",
        member_projects=[str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()],
        details={"requested_by": "admin"},
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/signoff")
def api_admin_signoff_group(group_id: str) -> RedirectResponse:
    group = group_cfg(normalize_config(), group_id)
    upsert_group_runtime(group_id, signoff_state="signed_off")
    log_group_run(
        group_id,
        run_kind="signoff",
        phase="signed_off",
        status="requested",
        member_projects=[str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()],
        details={"requested_by": "admin"},
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/reopen")
def api_admin_reopen_group(group_id: str) -> RedirectResponse:
    group = group_cfg(normalize_config(), group_id)
    upsert_group_runtime(group_id, signoff_state="open")
    log_group_run(
        group_id,
        run_kind="reopen",
        phase="audit_required",
        status="requested",
        member_projects=[str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()],
        details={"requested_by": "admin"},
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/refill-approved")
def api_admin_refill_group_approved(group_id: str, queue_mode: str = Form("append")) -> RedirectResponse:
    group = group_cfg(normalize_config(), group_id)
    published = publish_group_approved_tasks(group_id, queue_mode=queue_mode)
    upsert_group_runtime(group_id, signoff_state="open", mark_refill_requested=True)
    log_group_run(
        group_id,
        run_kind="refill",
        phase="proposed_tasks",
        status="requested",
        member_projects=[str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()],
        details={"requested_by": "admin", "queue_mode": queue_mode, "published_count": int(published)},
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/audit/tasks/{candidate_id}/approve")
def api_admin_approve_audit_task(candidate_id: int) -> RedirectResponse:
    audit_task_candidate_row(candidate_id)
    set_audit_candidate_status(candidate_id, "approved", resolved=False)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/audit/tasks/{candidate_id}/reject")
def api_admin_reject_audit_task(candidate_id: int) -> RedirectResponse:
    audit_task_candidate_row(candidate_id)
    set_audit_candidate_status(candidate_id, "rejected", resolved=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/audit/tasks/{candidate_id}/publish")
def api_admin_publish_audit_task(candidate_id: int) -> RedirectResponse:
    candidate = audit_task_candidate_row(candidate_id)
    if candidate["scope_type"] == "fleet":
        publish_fleet_audit_candidate(candidate_id)
    elif candidate["scope_type"] == "group":
        publish_group_audit_candidate(candidate_id)
    else:
        publish_project_audit_candidate(candidate_id)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/audit/tasks/{candidate_id}/publish-mode")
def api_admin_publish_audit_task_mode(candidate_id: int, queue_mode: str = Form("append")) -> RedirectResponse:
    candidate = audit_task_candidate_row(candidate_id)
    if candidate["scope_type"] == "fleet":
        publish_fleet_audit_candidate(candidate_id)
    elif candidate["scope_type"] == "group":
        publish_group_audit_candidate(candidate_id)
    else:
        publish_project_audit_candidate(candidate_id, queue_mode=queue_mode)
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
def admin_dashboard() -> str:
    status = admin_status_payload()
    projects = status["config"]["projects"]
    groups = status.get("groups") or status["config"].get("groups", [])
    accounts = status["config"]["accounts"]
    account_pools = status.get("account_pools") or []
    account_pool_map = {row["alias"]: row for row in account_pools}
    spider = status["config"]["spider"] or {}
    auditor = status.get("auditor") or {}
    auditor_run = auditor.get("last_run") or {}
    findings = auditor.get("findings") or []
    task_candidates = auditor.get("task_candidates") or []
    publish_events = status.get("studio_publish_events") or []
    group_publish_event_rows = status.get("group_publish_events") or []
    group_run_rows = status.get("group_runs") or []
    runs = status["recent_runs"]
    decisions = status.get("recent_decisions") or []
    ops = status.get("ops_summary") or {}

    def td(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    def render_summary_list(items: List[Any], render_item) -> str:
        if not items:
            return '<p class="muted">None right now.</p>'
        rendered = "".join(f"<li>{render_item(item)}</li>" for item in items[:5])
        if len(items) > 5:
            rendered += f"<li class=\"muted\">+{len(items) - 5} more</li>"
        return f"<ul>{rendered}</ul>"

    project_rows: List[str] = []
    for project in projects:
        actions: List[str] = []
        if project.get("enabled", True):
            actions.append(
                f'<form method="post" action="/api/admin/projects/{project["id"]}/pause"><button type="submit">Pause</button></form>'
            )
        else:
            actions.append(
                f'<form method="post" action="/api/admin/projects/{project["id"]}/resume"><button type="submit">Resume</button></form>'
            )
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/run-now"><button type="submit">Run Now</button></form>'
        )
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/retry"><button type="submit">Retry</button></form>'
        )
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/clear-cooldown"><button type="submit">Clear Cooldown</button></form>'
        )
        progress_label = project_progress_label(project)
        project_rows.append(
            f"""
            <tr>
              <td><div>{td(project.get('id'))}</div><div class="muted">{td(project.get('path'))}</div></td>
              <td><div>{td(project.get('runtime_status'))}</div><div class="muted">{td(project.get('completion_basis'))}</div><div class="muted">pressure: {td(project.get('pressure_state'))}</div></td>
              <td><div>{td(project.get('stop_reason'))}</div><div class="muted">{td(project.get('next_action'))}</div><div class="muted">{td(project.get('unblocker'))}</div><div class="muted">audit tasks: approved {td(project.get('approved_audit_task_count'))} / open {td(project.get('open_audit_task_count'))}</div></td>
              <td><div>{td(project.get('queue_source_health'))}</div><div class="muted">{td(project.get('backlog_source'))}</div></td>
              <td>{progress_label}</td>
              <td>{td(project.get('current_slice'))}</td>
              <td><div>{td((project.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((project.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td>{td(project.get('uncovered_scope_count'))}</td>
              <td><div>{td(', '.join(project.get('accounts') or []))}</div><div class="muted">{td(project_account_policy_summary(project))}</div><div class="muted">{td(runner_policy_summary(project))}</div><div class="muted">allowance: ${float((project.get('allowance_usage') or {}).get('estimated_cost_usd') or 0.0):.4f} / {(project.get('allowance_usage') or {}).get('run_count') or 0} runs</div></td>
              <td>{td(project.get('cooldown_until'))}</td>
              <td>{td(project.get('last_error'))}</td>
              <td><div class="actions">{''.join(actions)}</div></td>
            </tr>
            """
        )

    group_rows: List[str] = []
    for group in groups:
        actions = [
            f'<form method="post" action="/api/admin/groups/{group["id"]}/pause"><button type="submit">Pause Group</button></form>',
            f'<form method="post" action="/api/admin/groups/{group["id"]}/resume"><button type="submit">Resume Group</button></form>',
            f'<form method="post" action="/api/admin/groups/{group["id"]}/audit-now"><button type="submit">Run Group Audit</button></form>',
            f'<form method="post" action="/api/admin/groups/{group["id"]}/refill-approved"><input type="hidden" name="queue_mode" value="append" /><button type="submit">Refill Approved Tasks</button></form>',
        ]
        if group.get("signed_off"):
            actions.append(f'<form method="post" action="/api/admin/groups/{group["id"]}/reopen"><button type="submit">Reopen Group</button></form>')
        else:
            actions.append(f'<form method="post" action="/api/admin/groups/{group["id"]}/signoff"><button type="submit">Sign Off Group</button></form>')
        group_rows.append(
            f"""
            <tr>
              <td><a href="/admin/groups/{html.escape(str(group.get('id') or ''))}">{td(group.get('id'))}</a></td>
              <td><div>{td(group.get('status'))}</div><div class="muted">phase: {td(group.get('phase'))}</div><div class="muted">{td(group.get('mode'))}</div><div class="muted">pressure: {td(group.get('pressure_state'))}</div><div class="muted">{td('signed off' if group.get('signed_off') else 'not signed off')}</div><div class="muted">{td(group.get('signed_off_at') or group.get('reopened_at') or '')}</div></td>
              <td><div>{td('ready' if group.get('dispatch_ready') else 'blocked')}</div><div class="muted">{td(group.get('dispatch_basis'))}</div></td>
              <td>{td(', '.join(group.get('projects') or []))}</td>
              <td><div>{td(', '.join(group.get('contract_sets') or []))}</div><div class="muted">{td('; '.join(group.get('contract_blockers') or []))}</div><div class="muted">{td(group_captain_policy_summary(group))}</div></td>
              <td><div>{td(len(group.get('dispatch_blockers') or []))}</div><div class="muted">{td('; '.join(group.get('dispatch_blockers') or []))}</div></td>
              <td>{td(group.get('uncovered_scope_count'))}</td>
              <td><div>{td((group.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td><div>{td((group.get('program_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('program_eta') or {}).get('eta_basis'))}</div><div class="muted">pool: {td((group.get('pool_sufficiency') or {}).get('level'))} / slots {td((group.get('pool_sufficiency') or {}).get('eligible_parallel_slots'))}</div><div class="muted">allowance: ${float((group.get('allowance_usage') or {}).get('estimated_cost_usd') or 0.0):.4f}</div></td>
              <td><div class="actions">{''.join(actions)}</div></td>
            </tr>
            """
        )

    account_rows: List[str] = []
    for alias, account in sorted(accounts.items()):
        allowed_models = account.get("allowed_models") or []
        spark_enabled = bool(account.get("spark_enabled", SPARK_MODEL in allowed_models))
        pool = account_pool_map.get(alias, {})
        actions = [
            f'<form method="post" action="/api/admin/accounts/{alias}/validate"><button type="submit">Validate</button></form>',
            f'<form method="post" action="/api/admin/accounts/{alias}/state"><input type="hidden" name="state" value="ready" /><button type="submit">Resume</button></form>',
            f'<form method="post" action="/api/admin/accounts/{alias}/state"><input type="hidden" name="state" value="draining" /><button type="submit">Drain</button></form>',
            f'<form method="post" action="/api/admin/accounts/{alias}/state"><input type="hidden" name="state" value="disabled" /><button type="submit">Disable</button></form>',
            f'<form method="post" action="/api/admin/accounts/{alias}/clear-backoff"><button type="submit">Clear Backoff</button></form>',
        ]
        account_rows.append(
            f"""
            <tr>
              <td>{td(alias)}</td>
              <td>{td(account.get('auth_kind'))}</td>
              <td>{td(account.get('health_state') or 'ready')}</td>
              <td>{td('yes' if spark_enabled else 'no')}</td>
              <td>{td(', '.join(allowed_models))}</td>
              <td>{td(account.get('daily_budget_usd'))}</td>
              <td>{td(account.get('monthly_budget_usd'))}</td>
              <td>{td(account.get('max_parallel_runs'))}</td>
              <td>{td(', '.join(account.get('project_allowlist') or []))}</td>
              <td><div>{td(pool.get('auth_status') or '')}</div><div class="muted">{td(pool.get('pool_state') or '')}</div></td>
              <td><div class="actions">{''.join(actions)}</div></td>
            </tr>
            """
        )

    pool_rows: List[str] = []
    for pool in account_pools:
        daily = pool.get("daily_usage") or {}
        monthly = pool.get("monthly_usage") or {}
        pool_rows.append(
            f"""
            <tr>
              <td>{td(pool.get('alias'))}</td>
              <td>{td(pool.get('pool_state'))}</td>
              <td>{td(pool.get('active_runs'))} / {td(pool.get('max_parallel_runs'))}</td>
              <td>${float(daily.get('cost') or 0.0):.4f}</td>
              <td>${float(monthly.get('cost') or 0.0):.4f}</td>
              <td>{td(pool.get('backoff_until'))}</td>
              <td>{td(pool.get('last_used_at'))}</td>
              <td>{td(pool.get('codex_home'))}</td>
              <td>{td(pool.get('last_error'))}</td>
            </tr>
            """
        )

    tier_rows: List[str] = []
    for tier, details in (spider.get("tier_preferences") or {}).items():
        tier_rows.append(
            f"""
            <tr>
              <td>{td(tier)}</td>
              <td>{td(', '.join(details.get('models') or []))}</td>
              <td>{td(details.get('reasoning_effort'))}</td>
              <td>{td(details.get('estimated_output_tokens'))}</td>
            </tr>
            """
        )

    price_rows: List[str] = []
    for model, pricing in (spider.get("price_table") or {}).items():
        price_rows.append(
            f"""
            <tr>
              <td>{td(model)}</td>
              <td>{td(pricing.get('input'))}</td>
              <td>{td(pricing.get('cached_input'))}</td>
              <td>{td(pricing.get('output'))}</td>
            </tr>
            """
        )

    run_rows: List[str] = []
    for run in runs[:20]:
        run_rows.append(
            f"""
            <tr>
              <td>{td(run.get('id'))}</td>
              <td>{td(run.get('project_id'))}</td>
              <td>{td(run.get('status'))}</td>
              <td>{td(run.get('slice_name'))}</td>
              <td>{td(run.get('model'))}</td>
              <td>{td(run.get('started_at'))}</td>
              <td>{td(run.get('finished_at'))}</td>
              <td><a href="/api/logs/{run['id']}">log</a></td>
              <td><a href="/api/final/{run['id']}">final</a></td>
            </tr>
            """
        )

    decision_rows: List[str] = []
    for decision in decisions[:30]:
        detail_bits = [bit for bit in [decision.get("decision_meta_summary"), decision.get("selection_trace_summary")] if bit]
        decision_rows.append(
            f"""
            <tr>
              <td>{td(decision.get('id'))}</td>
              <td>{td(decision.get('project_id'))}</td>
              <td>{td(decision.get('slice_name'))}</td>
              <td>{td(decision.get('spider_tier'))}</td>
              <td>{td(decision.get('selected_model'))}</td>
              <td>{td(decision.get('account_alias'))}</td>
              <td><div>{td(decision.get('reason'))}</div><div class="muted">{td(' | '.join(detail_bits))}</div></td>
              <td>{td(decision.get('created_at'))}</td>
            </tr>
            """
        )

    finding_rows: List[str] = []
    for finding in findings[:50]:
        finding_rows.append(
            f"""
            <tr>
              <td>{td(finding.get('scope_type'))}</td>
              <td>{td(finding.get('scope_id'))}</td>
              <td>{td(finding.get('severity'))}</td>
              <td><div>{td(finding.get('title'))}</div><div class="muted">{td(finding.get('finding_key'))}</div></td>
              <td>{td(finding.get('summary'))}</td>
              <td>{td(len(finding.get('candidate_tasks') or []))}</td>
              <td>{td(finding.get('last_seen_at'))}</td>
            </tr>
            """
        )

    candidate_rows: List[str] = []
    for task in task_candidates[:50]:
        status_value = str(task.get("status") or "open")
        actions: List[str] = []
        if status_value == "open":
            actions.extend(
                [
                    f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/approve"><button type="submit">Approve</button></form>',
                    f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/reject"><button type="submit">Reject</button></form>',
                ]
            )
        if status_value == "approved":
            actions.append(
                f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/publish"><button type="submit">Publish</button></form>'
            )
            if task.get("scope_type") == "project":
                actions.append(
                    f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/publish-mode"><input type="hidden" name="queue_mode" value="replace" /><button type="submit">Publish Replace</button></form>'
                )
            actions.append(
                f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/reject"><button type="submit">Reject</button></form>'
            )
        candidate_rows.append(
            f"""
            <tr>
              <td>{td(task.get('id'))}</td>
              <td>{td(task.get('status'))}</td>
              <td>{td(task.get('scope_type'))}</td>
              <td>{td(task.get('scope_id'))}</td>
              <td>{td(task.get('finding_key'))}</td>
              <td>{td(task.get('title'))}</td>
              <td><div>{td(task.get('detail'))}</div><div class="muted">{td('bootstrap project' if (task.get('task_meta') or {}).get('bootstrap_project') else '')}</div></td>
              <td>{td(task.get('last_seen_at'))}</td>
              <td><div class="actions">{''.join(actions)}</div></td>
            </tr>
            """
        )

    publish_event_rows: List[str] = []
    for event in publish_events[:30]:
        publish_event_rows.append(
            f"""
            <tr>
              <td>{td(event.get('id'))}</td>
              <td>{td(event.get('source_target_type'))}:{td(event.get('source_target_id'))}</td>
              <td>{td(event.get('mode'))}</td>
              <td>{td(event.get('published_targets_summary'))}</td>
              <td>{td(event.get('created_at'))}</td>
            </tr>
            """
        )

    group_publish_rows: List[str] = []
    for event in group_publish_event_rows[:30]:
        group_publish_rows.append(
            f"""
            <tr>
              <td>{td(event.get('id'))}</td>
              <td>{td(event.get('group_id'))}</td>
              <td>{td(event.get('source'))}</td>
              <td>{td(event.get('source_scope_type'))}:{td(event.get('source_scope_id'))}</td>
              <td>{td(event.get('published_targets_summary'))}</td>
              <td>{td(event.get('created_at'))}</td>
            </tr>
            """
        )

    group_run_history_rows: List[str] = []
    for event in group_run_rows[:30]:
        detail_summary = ""
        details = event.get("details") or {}
        if details:
            parts = []
            if details.get("previous_phase"):
                parts.append(f"from {details.get('previous_phase')}")
            if details.get("group_status"):
                parts.append(f"status={details.get('group_status')}")
            if "dispatch_ready" in details:
                parts.append("dispatch-ready" if details.get("dispatch_ready") else "dispatch-blocked")
            detail_summary = "; ".join(parts)
        group_run_history_rows.append(
            f"""
            <tr>
              <td>{td(event.get('id'))}</td>
              <td>{td(event.get('group_id'))}</td>
              <td>{td(event.get('run_kind'))}</td>
              <td>{td(event.get('phase'))}</td>
              <td>{td(event.get('status'))}</td>
              <td>{td(event.get('member_projects_summary'))}</td>
              <td>{td(detail_summary)}</td>
              <td>{td(event.get('started_at'))}</td>
            </tr>
            """
        )

    group_milestone_rows: List[str] = []
    for group in groups:
        remaining_titles = [str(item.get("id") or item.get("title") or "").strip() for item in (group.get("remaining_milestones") or [])]
        uncovered = list(group.get("uncovered_scope") or [])
        group_milestone_rows.append(
            f"""
            <tr>
              <td>{td(group.get('id'))}</td>
              <td>{td(group.get('phase'))}</td>
              <td>{td(group.get('status'))}</td>
              <td>{td(len(group.get('remaining_milestones') or []))}</td>
              <td>{td(', '.join(remaining_titles[:4]))}</td>
              <td>{td(len(uncovered))}</td>
              <td>{td('; '.join(str(item) for item in uncovered[:3]))}</td>
            </tr>
            """
        )

    project_milestone_rows: List[str] = []
    for project in projects:
        remaining_titles = [str(item.get("id") or item.get("title") or "").strip() for item in (project.get("remaining_milestones") or [])]
        uncovered = list(project.get("uncovered_scope") or [])
        project_milestone_rows.append(
            f"""
            <tr>
              <td>{td(project.get('id'))}</td>
              <td>{td(project.get('runtime_status'))}</td>
              <td>{td(len(project.get('remaining_milestones') or []))}</td>
              <td>{td(', '.join(remaining_titles[:4]))}</td>
              <td>{td(len(uncovered))}</td>
              <td>{td('; '.join(str(item) for item in uncovered[:3]))}</td>
            </tr>
            """
        )

    ops_cards = [
        (
            "Stopped but not signed off",
            len(ops.get("stopped_not_signed_off") or []),
            render_summary_list(
                ops.get("stopped_not_signed_off") or [],
                lambda project: f"{td(project.get('id'))}: {td(project.get('stop_reason'))}",
            ),
        ),
        (
            "Blocked or awaiting refill",
            len(ops.get("blocked_projects") or []),
            render_summary_list(
                ops.get("blocked_projects") or [],
                lambda project: f"{td(project.get('id'))}: {td(project.get('runtime_status'))} | {td(project.get('next_action'))}",
            ),
        ),
        (
            "Queues exhausted",
            len(ops.get("queue_exhausted_projects") or []),
            render_summary_list(
                ops.get("queue_exhausted_projects") or [],
                lambda project: f"{td(project.get('id'))}: {td(project.get('runtime_status'))} | refill ready={td('yes' if project.get('refill_ready') else 'no')}",
            ),
        ),
        (
            "Proposed tasks",
            len(ops.get("proposed_task_groups") or []),
            render_summary_list(
                ops.get("proposed_task_groups") or [],
                lambda group: f'<a href="/admin/groups/{html.escape(str(group.get("id") or ""))}">{td(group.get("id"))}</a>: {td(group.get("status"))}',
            ),
        ),
        (
            "Cooling down",
            len(ops.get("cooling_down") or []),
            render_summary_list(
                ops.get("cooling_down") or [],
                lambda project: f"{td(project.get('id'))}: until {td(project.get('cooldown_until'))}",
            ),
        ),
        (
            "Audit-required groups",
            len(ops.get("audit_required_groups") or []),
            render_summary_list(
                ops.get("audit_required_groups") or [],
                lambda group: f'<a href="/admin/groups/{html.escape(str(group.get("id") or ""))}">{td(group.get("id"))}</a>: uncovered={td(group.get("uncovered_scope_count"))} | status={td(group.get("status"))}',
            ),
        ),
        (
            "High-pressure groups",
            len(ops.get("high_pressure_groups") or []),
            render_summary_list(
                ops.get("high_pressure_groups") or [],
                lambda group: f'<a href="/admin/groups/{html.escape(str(group.get("id") or ""))}">{td(group.get("id"))}</a>: pressure={td(group.get("pressure_state"))}',
            ),
        ),
        (
            "Tight pool groups",
            len(ops.get("tight_pool_groups") or []),
            render_summary_list(
                ops.get("tight_pool_groups") or [],
                lambda group: f'<a href="/admin/groups/{html.escape(str(group.get("id") or ""))}">{td(group.get("id"))}</a>: pool={td((group.get("pool_sufficiency") or {}).get("level"))}',
            ),
        ),
        (
            "Accounts needing attention",
            len(ops.get("accounts_needing_attention") or []),
            render_summary_list(
                ops.get("accounts_needing_attention") or [],
                lambda pool: f"{td(pool.get('alias'))}: {td(pool.get('pool_state'))} | {td(pool.get('auth_status'))}",
            ),
        ),
        (
            "Group blockers",
            len(ops.get("group_blockers") or []),
            render_summary_list(
                ops.get("group_blockers") or [],
                lambda group: f'<a href="/admin/groups/{html.escape(str(group.get("id") or ""))}">{td(group.get("id"))}</a>: {td(group.get("dispatch_basis"))}',
            ),
        ),
        (
            "Ready to run now",
            len(ops.get("ready_to_run_now") or []),
            render_summary_list(
                ops.get("ready_to_run_now") or [],
                lambda group: f'<a href="/admin/groups/{html.escape(str(group.get("id") or ""))}">{td(group.get("id"))}</a>: {td(group.get("status"))}',
            ),
        ),
        (
            "Runs needing attention",
            len(ops.get("runs_needing_attention") or []),
            render_summary_list(
                ops.get("runs_needing_attention") or [],
                lambda run: f"run {td(run.get('id'))} / {td(run.get('project_id'))}: {td(run.get('status'))}",
            ),
        ),
    ]
    ops_card_html = "".join(
        f"""
        <div class="panel">
          <h2>{td(title)}</h2>
          <p><strong>{count}</strong></p>
          {content}
        </div>
        """
        for title, count, content in ops_cards
    )

    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta http-equiv="refresh" content="15" />
        <title>{APP_TITLE}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
          th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
          th {{ background: #f4f4f4; }}
          code {{ background: #f4f4f4; padding: 2px 4px; }}
          .muted {{ color: #555; }}
          .actions form {{ display: inline-block; margin: 0 6px 6px 0; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; }}
          .panel {{ border: 1px solid #ccc; padding: 16px; }}
          .panel h2 {{ margin-top: 0; }}
          input[type=text], textarea {{ width: 100%; box-sizing: border-box; }}
          textarea {{ min-height: 120px; }}
          label {{ display: block; margin: 12px 0 4px; font-weight: 600; }}
          ul {{ margin: 8px 0 0 18px; padding: 0; }}
        </style>
      </head>
      <body>
        <h1>{APP_TITLE}</h1>
        <p><a href="/">Open Fleet Dashboard</a> · <a href="/studio">Open Studio</a></p>
        <p><strong>Desired state:</strong> YAML in <code>{td(str(CONFIG_PATH))}</code>. <strong>Runtime state:</strong> SQLite in <code>{td(str(DB_PATH))}</code>.</p>
        <p class="muted">Config changes are picked up automatically by the controller on the next scheduler loop. Pause/Resume edits desired state; Retry/Clear Cooldown/Run Now edit runtime state.</p>
        <p class="muted">Statuses here are queue-runtime states, not product signoff. A project marked <code>audit_required</code> has exhausted its current queue and is waiting for audit/refill or signoff at the group layer.</p>
        <p class="muted">Milestone and program ETA remain <code>unknown</code> until coverage is explicitly modeled in the registry.</p>

        <div class="grid">
          {ops_card_html}
        </div>

        <div class="grid">
          <div class="panel">
            <h2>Auditor</h2>
            <p><strong>Last run:</strong> {td(auditor_run.get('finished_at') or auditor_run.get('started_at'))}</p>
            <p><strong>Status:</strong> {td(auditor_run.get('status') or 'not_started')}</p>
            <p><strong>Open findings:</strong> {td(len(findings))}</p>
            <p><strong>Open task candidates:</strong> {td(len(task_candidates))}</p>
            <form method="post" action="/api/admin/auditor/run-now"><button type="submit">Run Auditor Now</button></form>
          </div>

          <div class="panel">
            <h2>Routing Policy</h2>
            <p><strong>Scheduler interval:</strong> {td(status['config']['policies'].get('scheduler_interval_seconds'))}s</p>
            <p><strong>Max parallel runs:</strong> {td(status['config']['policies'].get('max_parallel_runs'))}</p>
            <p><strong>Token alliance window:</strong> {td(spider.get('token_alliance_window_hours'))}h</p>
            <p><strong>Classification mode:</strong> {td(spider.get('classification_mode') or 'heuristic')}</p>
            <p><strong>Escalate after failures:</strong> {td(spider.get('escalate_to_complex_after_failures'))}</p>
            <p><strong>Injected feedback window:</strong> {td(spider.get('feedback_file_window'))}</p>
            <form method="post" action="/api/admin/routing/update">
              <label for="classification_mode">Classification Mode</label>
              <input id="classification_mode" name="classification_mode" type="text" value="{td(spider.get('classification_mode') or 'heuristic_v2')}" />

              <label for="feedback_file_window">Feedback Window</label>
              <input id="feedback_file_window" name="feedback_file_window" type="text" value="{td(spider.get('feedback_file_window') or 2)}" />

              <label for="escalate_to_complex_after_failures">Escalate After Failures</label>
              <input id="escalate_to_complex_after_failures" name="escalate_to_complex_after_failures" type="text" value="{td(spider.get('escalate_to_complex_after_failures') or 2)}" />

              <label for="token_alliance_window_hours">Token Alliance Window Hours</label>
              <input id="token_alliance_window_hours" name="token_alliance_window_hours" type="text" value="{td(spider.get('token_alliance_window_hours') or 24)}" />

              <p><button type="submit">Update Routing</button></p>
            </form>
          </div>

          <div class="panel">
            <h2>Add Or Update Account</h2>
            <form method="post" action="/api/admin/accounts/upsert">
              <label for="alias">Alias</label>
              <input id="alias" name="alias" type="text" placeholder="acct-ui-a" required />

              <label for="auth_kind">Auth Kind</label>
              <input id="auth_kind" name="auth_kind" type="text" value="chatgpt_auth_json" />

              <label for="allowed_models">Allowed Models</label>
              <textarea id="allowed_models" name="allowed_models" placeholder="gpt-5.3-codex-spark&#10;gpt-5-mini&#10;gpt-5.4"></textarea>

              <label for="auth_json_file">Auth JSON File</label>
              <input id="auth_json_file" name="auth_json_file" type="text" placeholder="/run/secrets/chatgpt.auth.json" />

              <label for="api_key_env">API Key Env</label>
              <input id="api_key_env" name="api_key_env" type="text" placeholder="OPENAI_API_KEY" />

              <label for="api_key_file">API Key File</label>
              <input id="api_key_file" name="api_key_file" type="text" placeholder="/run/secrets/openai.api_key" />

              <label for="daily_budget_usd">Daily Budget</label>
              <input id="daily_budget_usd" name="daily_budget_usd" type="text" placeholder="25" />

              <label for="monthly_budget_usd">Monthly Budget</label>
              <input id="monthly_budget_usd" name="monthly_budget_usd" type="text" placeholder="250" />

              <label for="max_parallel_runs">Max Parallel Runs</label>
              <input id="max_parallel_runs" name="max_parallel_runs" type="text" value="1" />

              <label for="health_state">Configured State</label>
              <input id="health_state" name="health_state" type="text" value="ready" />

              <label for="project_allowlist">Project Allowlist</label>
              <textarea id="project_allowlist" name="project_allowlist" placeholder="core&#10;ui"></textarea>

              <label><input name="spark_enabled" type="checkbox" value="1" checked /> Spark Enabled</label>
              <p><button type="submit">Save Account</button></p>
            </form>
          </div>

          <div class="panel">
            <h2>Project Account Policy</h2>
            <p class="muted">Use one configured project ID. The form posts directly to that project's policy route.</p>
            <form method="post" action="/api/admin/projects/core/account-policy" onsubmit="this.action='/api/admin/projects/' + encodeURIComponent(this.project_id.value || 'core') + '/account-policy'">
              <label for="policy_project_id">Project ID</label>
              <input id="policy_project_id" name="project_id" type="text" value="core" />

              <label for="preferred_accounts">Preferred Accounts</label>
              <textarea id="preferred_accounts" name="preferred_accounts" placeholder="acct-ui-a&#10;acct-chatgpt-core"></textarea>

              <label for="burst_accounts">Burst Accounts</label>
              <textarea id="burst_accounts" name="burst_accounts" placeholder="acct-shared-b"></textarea>

              <label for="reserve_accounts">Reserve Accounts</label>
              <textarea id="reserve_accounts" name="reserve_accounts" placeholder="acct-studio-a"></textarea>

              <label><input name="allow_chatgpt_accounts" type="checkbox" value="1" checked /> Allow ChatGPT Accounts</label>
              <label><input name="allow_api_accounts" type="checkbox" value="1" checked /> Allow API Accounts</label>
              <label><input name="spark_enabled" type="checkbox" value="1" checked /> Spark Enabled</label>
              <p><button type="submit">Save Project Policy</button></p>
            </form>
          </div>

          <div class="panel">
            <h2>Group Captain Policy</h2>
            <p class="muted">Priority, service floor, and shed order control dispatch preference at slice boundaries.</p>
            <form method="post" action="/api/admin/groups/chummer-vnext/captain" onsubmit="this.action='/api/admin/groups/' + encodeURIComponent(this.group_id.value || 'chummer-vnext') + '/captain'">
              <label for="captain_group_id">Group ID</label>
              <input id="captain_group_id" name="group_id" type="text" value="chummer-vnext" />

              <label for="captain_priority">Priority</label>
              <input id="captain_priority" name="priority" type="text" value="200" />

              <label for="captain_service_floor">Service Floor</label>
              <input id="captain_service_floor" name="service_floor" type="text" value="1" />

              <label for="captain_shed_order">Shed Order</label>
              <input id="captain_shed_order" name="shed_order" type="text" value="100" />

              <label for="captain_preemption_policy">Preemption Policy</label>
              <input id="captain_preemption_policy" name="preemption_policy" type="text" value="slice_boundary" />

              <label for="captain_admission_policy">Admission Policy</label>
              <input id="captain_admission_policy" name="admission_policy" type="text" value="normal" />

              <p><button type="submit">Save Group Captain Policy</button></p>
            </form>
          </div>

          <div class="panel">
            <h2>Routing Class Policy</h2>
            <p class="muted">Edit one route class at a time. Model order is preference order.</p>
            <form method="post" action="/api/admin/routing/classes/micro_edit" onsubmit="this.action='/api/admin/routing/classes/' + encodeURIComponent(this.route_class.value || 'micro_edit')">
              <label for="route_class">Route Class</label>
              <input id="route_class" name="route_class" type="text" value="micro_edit" />

              <label for="route_models">Models</label>
              <textarea id="route_models" name="models" placeholder="gpt-5.3-codex-spark&#10;gpt-5-mini&#10;gpt-5.4"></textarea>

              <label for="route_reasoning_effort">Reasoning Effort</label>
              <input id="route_reasoning_effort" name="reasoning_effort" type="text" value="low" />

              <label for="route_estimated_output_tokens">Estimated Output Tokens</label>
              <input id="route_estimated_output_tokens" name="estimated_output_tokens" type="text" value="1024" />

              <p><button type="submit">Save Route Class</button></p>
            </form>
          </div>

          <div class="panel">
            <h2>Bootstrap Project</h2>
            <p class="muted">This is the repo-bootstrap path used for first-class new-project creation from admin or auditor proposals.</p>
            <form method="post" action="/api/admin/projects/bootstrap">
              <label for="project_id">Project ID</label>
              <input id="project_id" name="project_id" type="text" placeholder="ui-kit" required />

              <label for="repo_path">Repo Path</label>
              <input id="repo_path" name="repo_path" type="text" placeholder="/docker/chummercomplete/chummer-ui-kit" required />

              <label for="group_id">Group ID</label>
              <input id="group_id" name="group_id" type="text" placeholder="chummer-vnext" />

              <label for="design_doc">Design Doc</label>
              <input id="design_doc" name="design_doc" type="text" placeholder="docs/design.md or docs/chummer-ui-kit.design.v1.md" />

              <label for="verify_cmd">Verify Command</label>
              <input id="verify_cmd" name="verify_cmd" type="text" placeholder="bash scripts/ai/verify.sh" />

              <label for="account_aliases">Account Aliases</label>
              <textarea id="account_aliases" name="account_aliases" placeholder="acct-photos-a&#10;acct-studio-a&#10;acct-shared-b"></textarea>

              <label for="preferred_bootstrap_accounts">Preferred Accounts</label>
              <textarea id="preferred_bootstrap_accounts" name="preferred_accounts" placeholder="acct-ui-a&#10;acct-shared-b"></textarea>

              <label for="burst_bootstrap_accounts">Burst Accounts</label>
              <textarea id="burst_bootstrap_accounts" name="burst_accounts" placeholder="acct-shared-b"></textarea>

              <label for="reserve_bootstrap_accounts">Reserve Accounts</label>
              <textarea id="reserve_bootstrap_accounts" name="reserve_accounts" placeholder="acct-studio-a"></textarea>

              <label for="queue_items">Initial Queue</label>
              <textarea id="queue_items" name="queue_items" placeholder="Inspect repository state and bootstrap repo-local AI files&#10;Compile recovery&#10;Contract hardening"></textarea>

              <label for="feedback_dir">Feedback Dir</label>
              <input id="feedback_dir" name="feedback_dir" type="text" value="feedback" />

              <label for="state_file">State File</label>
              <input id="state_file" name="state_file" type="text" value=".agent-state.json" />

              <label for="github_owner">GitHub Owner</label>
              <input id="github_owner" name="github_owner" type="text" placeholder="ArchonMegalon" />

              <label for="github_repo">GitHub Repo</label>
              <input id="github_repo" name="github_repo" type="text" placeholder="chummer-ui-kit" />

              <label for="github_visibility">GitHub Visibility</label>
              <input id="github_visibility" name="github_visibility" type="text" value="private" />

              <label><input name="create_repo_dir" type="checkbox" value="1" checked /> Create repo directory if missing</label>
              <label><input name="bootstrap_files" type="checkbox" value="1" checked /> Bootstrap repo-local AI files</label>
              <label><input name="init_local_git" type="checkbox" value="1" checked /> Initialize local git repo</label>
              <label><input name="create_github_repo" type="checkbox" value="1" /> Create GitHub repo with <code>gh</code></label>
              <p><button type="submit">Bootstrap Project</button></p>
            </form>
          </div>
        </div>

        <h2>Projects</h2>
        <table>
          <thead>
            <tr>
              <th>Project</th><th>Queue Status</th><th>Why Stopped</th><th>Queue Source</th><th>Progress</th><th>Current Slice</th><th>Milestone ETA</th><th>Uncovered Scope</th><th>Accounts</th><th>Cooldown</th><th>Last Error</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {''.join(project_rows) or '<tr><td colspan="12">No projects configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Groups</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Status / Phase</th><th>Dispatch</th><th>Projects</th><th>Contract Sets / Blockers</th><th>Dispatch Blockers</th><th>Uncovered Scope</th><th>Milestone ETA</th><th>Program ETA</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {''.join(group_rows) or '<tr><td colspan="10">No project groups configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Accounts</h2>
        <table>
          <thead>
            <tr>
              <th>Alias</th><th>Auth</th><th>Configured State</th><th>Spark</th><th>Allowed Models</th><th>Day Budget</th><th>Month Budget</th><th>Parallel</th><th>Project Allowlist</th><th>Auth Status</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {''.join(account_rows) or '<tr><td colspan="11">No accounts configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Account Pools</h2>
        <table>
          <thead>
            <tr>
              <th>Alias</th><th>Pool State</th><th>Active</th><th>Day Cost</th><th>Month Cost</th><th>Backoff</th><th>Last Used</th><th>CODEX_HOME</th><th>Last Error</th>
            </tr>
          </thead>
          <tbody>
            {''.join(pool_rows) or '<tr><td colspan="9">No live account pools yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Routing Classes</h2>
        <table>
          <thead>
            <tr>
              <th>Route Class</th><th>Models</th><th>Reasoning</th><th>Estimated Output Tokens</th>
            </tr>
          </thead>
          <tbody>
            {''.join(tier_rows) or '<tr><td colspan="4">No tier preferences configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Price Table</h2>
        <table>
          <thead>
            <tr>
              <th>Model</th><th>Input</th><th>Cached Input</th><th>Output</th>
            </tr>
          </thead>
          <tbody>
            {''.join(price_rows) or '<tr><td colspan="4">No pricing configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Audit Findings</h2>
        <table>
          <thead>
            <tr>
              <th>Scope Type</th><th>Scope ID</th><th>Severity</th><th>Finding</th><th>Summary</th><th>Candidate Tasks</th><th>Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {''.join(finding_rows) or '<tr><td colspan="7">No open audit findings.</td></tr>'}
          </tbody>
        </table>

        <h2>Audit Task Candidates</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Status</th><th>Scope Type</th><th>Scope ID</th><th>Finding Key</th><th>Title</th><th>Detail</th><th>Last Seen</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {''.join(candidate_rows) or '<tr><td colspan="9">No open or approved audit task candidates.</td></tr>'}
          </tbody>
        </table>

        <h2>Group Publish Events</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Group</th><th>Source</th><th>Scope</th><th>Published Targets</th><th>Created</th>
            </tr>
          </thead>
          <tbody>
            {''.join(group_publish_rows) or '<tr><td colspan="6">No group publish events yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Group Runs</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Group</th><th>Kind</th><th>Phase</th><th>Status</th><th>Members</th><th>Details</th><th>Started</th>
            </tr>
          </thead>
          <tbody>
            {''.join(group_run_history_rows) or '<tr><td colspan="8">No group runs yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Group Milestone Board</h2>
        <table>
          <thead>
            <tr>
              <th>Group</th><th>Phase</th><th>Status</th><th>Remaining Milestones</th><th>Milestones</th><th>Uncovered Scope</th><th>Scope Preview</th>
            </tr>
          </thead>
          <tbody>
            {''.join(group_milestone_rows) or '<tr><td colspan="7">No groups configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Project Milestone Board</h2>
        <table>
          <thead>
            <tr>
              <th>Project</th><th>Queue Status</th><th>Remaining Milestones</th><th>Milestones</th><th>Uncovered Scope</th><th>Scope Preview</th>
            </tr>
          </thead>
          <tbody>
            {''.join(project_milestone_rows) or '<tr><td colspan="6">No projects configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Studio Publish Events</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Source Target</th><th>Mode</th><th>Published Targets</th><th>Created</th>
            </tr>
          </thead>
          <tbody>
            {''.join(publish_event_rows) or '<tr><td colspan="5">No studio publish events yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Routing Decisions</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Project</th><th>Slice</th><th>Route Class</th><th>Model</th><th>Account</th><th>Reason</th><th>Created</th>
            </tr>
          </thead>
          <tbody>
            {''.join(decision_rows) or '<tr><td colspan="8">No routing decisions yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Recent Runs</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Project</th><th>Status</th><th>Slice</th><th>Model</th><th>Started</th><th>Finished</th><th>Log</th><th>Final</th>
            </tr>
          </thead>
          <tbody>
            {''.join(run_rows) or '<tr><td colspan="9">No runs yet.</td></tr>'}
          </tbody>
        </table>
      </body>
    </html>
    """


@app.get("/admin/groups/{group_id}", response_class=HTMLResponse)
def admin_group_detail(group_id: str) -> str:
    status = admin_status_payload()
    projects = status.get("projects") or status["config"]["projects"]
    groups = status.get("groups") or status["config"].get("groups", [])
    group = next((item for item in groups if str(item.get("id")) == group_id), None)
    if not group:
        raise HTTPException(404, "unknown group")
    member_ids = {str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()}
    member_projects = [project for project in projects if str(project.get("id")) in member_ids]
    findings = [
        item
        for item in (status.get("auditor", {}) or {}).get("findings", [])
        if (item.get("scope_type") == "group" and item.get("scope_id") == group_id)
        or (item.get("scope_type") == "project" and str(item.get("scope_id")) in member_ids)
    ]
    tasks = [
        item
        for item in (status.get("auditor", {}) or {}).get("task_candidates", [])
        if (item.get("scope_type") == "group" and item.get("scope_id") == group_id)
        or (item.get("scope_type") == "project" and str(item.get("scope_id")) in member_ids)
    ]
    publish_events = [item for item in (status.get("group_publish_events") or []) if item.get("group_id") == group_id]
    run_rows = [item for item in (status.get("group_runs") or []) if item.get("group_id") == group_id]
    current_milestone = next(iter(group.get("remaining_milestones") or []), {})
    finding_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(str(item.get('scope_type') or ''))}:{html.escape(str(item.get('scope_id') or ''))}</td>
          <td>{html.escape(str(item.get('severity') or ''))}</td>
          <td><div>{html.escape(str(item.get('title') or ''))}</div><div class="muted">{html.escape(str(item.get('finding_key') or ''))}</div></td>
          <td>{html.escape(str(item.get('summary') or ''))}</td>
          <td>{html.escape(str(item.get('last_seen_at') or ''))}</td>
        </tr>
        """
        for item in findings[:40]
    )
    task_rows = []
    for task in tasks[:40]:
        actions: List[str] = []
        if str(task.get("status") or "open") == "open":
            actions.append(f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/approve"><button type="submit">Approve</button></form>')
            actions.append(f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/reject"><button type="submit">Reject</button></form>')
        elif str(task.get("status") or "") == "approved":
            actions.append(f'<form method="post" action="/api/admin/audit/tasks/{task["id"]}/publish"><button type="submit">Publish</button></form>')
        task_rows.append(
            f"""
            <tr>
              <td>{html.escape(str(task.get('status') or ''))}</td>
              <td>{html.escape(str(task.get('scope_type') or ''))}:{html.escape(str(task.get('scope_id') or ''))}</td>
              <td>{html.escape(str(task.get('title') or ''))}</td>
              <td>{html.escape(str(task.get('detail') or ''))}</td>
              <td><div class="actions">{''.join(actions)}</div></td>
            </tr>
            """
        )
    member_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(str(project.get('id') or ''))}</td>
          <td>{html.escape(str(project.get('runtime_status') or ''))}</td>
          <td>{html.escape(str(project.get('current_slice') or ''))}</td>
          <td>{int(project.get('approved_audit_task_count') or 0)} / {int(project.get('open_audit_task_count') or 0)}</td>
          <td>{html.escape(str(project.get('stop_reason') or ''))}</td>
          <td>{html.escape(str(project.get('next_action') or ''))}</td>
        </tr>
        """
        for project in member_projects
    )
    run_history_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(str(item.get('id') or ''))}</td>
          <td>{html.escape(str(item.get('run_kind') or ''))}</td>
          <td>{html.escape(str(item.get('phase') or ''))}</td>
          <td>{html.escape(str(item.get('status') or ''))}</td>
          <td>{html.escape(str(item.get('member_projects_summary') or ''))}</td>
          <td>{html.escape(str(item.get('started_at') or ''))}</td>
        </tr>
        """
        for item in run_rows[:40]
    )
    publish_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(str(item.get('id') or ''))}</td>
          <td>{html.escape(str(item.get('source') or ''))}</td>
          <td>{html.escape(str(item.get('source_scope_type') or ''))}:{html.escape(str(item.get('source_scope_id') or ''))}</td>
          <td>{html.escape(str(item.get('published_targets_summary') or ''))}</td>
          <td>{html.escape(str(item.get('created_at') or ''))}</td>
        </tr>
        """
        for item in publish_events[:40]
    )
    uncovered_scope = "".join(f"<li>{html.escape(str(item))}</li>" for item in (group.get("uncovered_scope") or []))
    blockers = "".join(f"<li>{html.escape(str(item))}</li>" for item in (group.get("dispatch_blockers") or []))
    contract_blockers = "".join(f"<li>{html.escape(str(item))}</li>" for item in (group.get("contract_blockers") or []))
    current_milestone_label = (
        f"{html.escape(str(current_milestone.get('id') or ''))}: {html.escape(str(current_milestone.get('title') or ''))}"
        if current_milestone
        else "none"
    )
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta http-equiv="refresh" content="15" />
        <title>{APP_TITLE} - {html.escape(group_id)}</title>
        <style>
          body {{ font-family: Arial, sans-serif; margin: 24px; }}
          table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
          th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
          th {{ background: #f4f4f4; }}
          code {{ background: #f4f4f4; padding: 2px 4px; }}
          .muted {{ color: #555; }}
          .actions form {{ display: inline-block; margin: 0 6px 6px 0; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; }}
          .panel {{ border: 1px solid #ccc; padding: 16px; }}
          .panel h2 {{ margin-top: 0; }}
          ul {{ margin: 8px 0 0 18px; padding: 0; }}
        </style>
      </head>
      <body>
        <p><a href="/admin">Back to Admin</a> · <a href="/studio">Open Studio</a></p>
        <h1>Group: {html.escape(group_id)}</h1>
        <div class="grid">
          <div class="panel">
            <h2>Status</h2>
            <p><strong>{html.escape(str(group.get('status') or ''))}</strong></p>
            <p class="muted">phase: {html.escape(str(group.get('phase') or ''))}</p>
            <p class="muted">pressure: {html.escape(str(group.get('pressure_state') or ''))}</p>
            <p class="muted">{html.escape(str(group.get('dispatch_basis') or ''))}</p>
            <p class="muted">{html.escape('signed off' if group.get('signed_off') else 'not signed off')}</p>
          </div>
          <div class="panel">
            <h2>Milestone</h2>
            <p><strong>{current_milestone_label}</strong></p>
            <p class="muted">remaining milestones: {len(group.get('remaining_milestones') or [])}</p>
            <p class="muted">program ETA: {html.escape(str((group.get('program_eta') or {}).get('eta_human') or 'unknown'))}</p>
            <p class="muted">pool: {html.escape(str((group.get('pool_sufficiency') or {}).get('level') or 'unknown'))} / slots {html.escape(str((group.get('pool_sufficiency') or {}).get('eligible_parallel_slots') or 0))}</p>
          </div>
          <div class="panel">
            <h2>Operator Levers</h2>
            <div class="actions">
              <form method="post" action="/api/admin/groups/{html.escape(group_id)}/audit-now"><button type="submit">Run Group Audit</button></form>
              <form method="post" action="/api/admin/groups/{html.escape(group_id)}/refill-approved"><input type="hidden" name="queue_mode" value="append" /><button type="submit">Refill Approved Tasks</button></form>
              <form method="post" action="/api/admin/groups/{html.escape(group_id)}/pause"><button type="submit">Pause Group</button></form>
              <form method="post" action="/api/admin/groups/{html.escape(group_id)}/resume"><button type="submit">Resume Group</button></form>
              {'<form method="post" action="/api/admin/groups/' + html.escape(group_id) + '/reopen"><button type="submit">Reopen Group</button></form>' if group.get('signed_off') else '<form method="post" action="/api/admin/groups/' + html.escape(group_id) + '/signoff"><button type="submit">Sign Off Group</button></form>'}
            </div>
            <p class="muted">{html.escape(group_captain_policy_summary(group))}</p>
          </div>
        </div>
        <div class="grid">
          <div class="panel">
            <h2>Contract Blockers</h2>
            <ul>{contract_blockers or '<li>None</li>'}</ul>
          </div>
          <div class="panel">
            <h2>Dispatch Blockers</h2>
            <ul>{blockers or '<li>None</li>'}</ul>
          </div>
          <div class="panel">
            <h2>Uncovered Scope</h2>
            <ul>{uncovered_scope or '<li>None</li>'}</ul>
          </div>
        </div>
        <h2>Member Projects</h2>
        <table>
          <thead>
            <tr><th>Project</th><th>Status</th><th>Current Slice</th><th>Approved / Open Tasks</th><th>Stop Reason</th><th>Next Action</th></tr>
          </thead>
          <tbody>
            {member_rows or '<tr><td colspan="6">No member projects.</td></tr>'}
          </tbody>
        </table>
        <h2>Latest Audit Findings</h2>
        <table>
          <thead>
            <tr><th>Scope</th><th>Severity</th><th>Finding</th><th>Summary</th><th>Last Seen</th></tr>
          </thead>
          <tbody>
            {finding_rows or '<tr><td colspan="5">No open findings.</td></tr>'}
          </tbody>
        </table>
        <h2>Proposed Tasks</h2>
        <table>
          <thead>
            <tr><th>Status</th><th>Scope</th><th>Title</th><th>Detail</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {''.join(task_rows) or '<tr><td colspan="5">No proposed tasks.</td></tr>'}
          </tbody>
        </table>
        <h2>Group Publish Events</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Source</th><th>Scope</th><th>Targets</th><th>Created</th></tr>
          </thead>
          <tbody>
            {publish_rows or '<tr><td colspan="5">No publish events yet.</td></tr>'}
          </tbody>
        </table>
        <h2>Group Run History</h2>
        <table>
          <thead>
            <tr><th>ID</th><th>Kind</th><th>Phase</th><th>Status</th><th>Members</th><th>Started</th></tr>
          </thead>
          <tbody>
            {run_history_rows or '<tr><td colspan="6">No group run history yet.</td></tr>'}
          </tbody>
        </table>
      </body>
    </html>
    """
