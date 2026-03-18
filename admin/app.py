import ast
import datetime as dt
import hashlib
import hmac
import html
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response

ADMIN_DIR = pathlib.Path(__file__).resolve().parent
# In containerized runs, Fleet bind-mounts the repo at `/docker`. Prefer that for helper modules.
_MOUNTED_ADMIN_DIR = pathlib.Path(os.environ.get("FLEET_MOUNT_ROOT", "/docker/fleet")) / "admin"
if (_MOUNTED_ADMIN_DIR / "consistency.py").exists() and str(_MOUNTED_ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(_MOUNTED_ADMIN_DIR))
if str(ADMIN_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_DIR))

from consistency import (
    DEFAULT_LANES,
    config_consistency_warnings,
    infer_account_lane,
    normalize_lanes_config,
    normalize_task_queue_item,
)

UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8092"))
APP_TITLE = "Codex Fleet Admin"
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
ACCOUNTS_PATH = pathlib.Path(os.environ.get("FLEET_ACCOUNTS_PATH", "/app/config/accounts.yaml"))
POLICIES_PATH = CONFIG_PATH.with_name("policies.yaml")
ROUTING_PATH = CONFIG_PATH.with_name("routing.yaml")
GROUPS_PATH = CONFIG_PATH.with_name("groups.yaml")
PROJECTS_DIR = CONFIG_PATH.parent / "projects"
PROJECT_INDEX_PATH = PROJECTS_DIR / "_index.yaml"
DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", "/var/lib/codex-fleet/fleet.db"))
CODEX_HOME_ROOT = pathlib.Path(os.environ.get("FLEET_CODEX_HOME_ROOT", "/var/lib/codex-fleet/codex-homes"))
GROUP_ROOT = pathlib.Path(os.environ.get("FLEET_GROUP_ROOT", str(DB_PATH.parent / "groups")))
AUDITOR_URL = os.environ.get("FLEET_AUDITOR_URL", "http://fleet-auditor:8093")
CONTROLLER_URL = os.environ.get("FLEET_CONTROLLER_URL", "http://fleet-controller:8090")
STUDIO_URL = os.environ.get("FLEET_STUDIO_URL", "http://fleet-studio:8091")
AUDIT_REQUEST_PENDING_SECONDS = int(os.environ.get("FLEET_AUDIT_REQUEST_PENDING_SECONDS", "300"))
DOCKER_ROOT = pathlib.Path("/docker")
STUDIO_PUBLISHED_DIR = ".codex-studio/published"
DESIGN_MIRROR_REQUIRED_FILES = [
    ".codex-design/product/VISION.md",
    ".codex-design/product/ARCHITECTURE.md",
    ".codex-design/repo/IMPLEMENTATION_SCOPE.md",
    ".codex-design/review/REVIEW_CONTEXT.md",
]
SOURCE_BACKLOG_OPEN_STATUS = "source_backlog_open"
CONFIGURED_QUEUE_COMPLETE_STATUS = "queue_exhausted"
SCAFFOLD_QUEUE_COMPLETE_STATUS = "scaffold_complete"
COMPLETED_SIGNED_OFF_STATUS = "completed_signed_off"
READY_STATUS = "dispatch_pending"
HEALING_STATUS = "healing"
WAITING_CAPACITY_STATUS = "waiting_capacity"
QUEUE_REFILLING_STATUS = "queue_refilling"
DECISION_REQUIRED_STATUS = "decision_required"
REVIEW_FIX_STATUS = "review_fix"
WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP = "groundwork_review_loop"
GROUNDWORK_PENDING_STATUS = "groundwork_pending"
AWAITING_FIRST_REVIEW_STATUS = "awaiting_first_review"
REVIEW_LIGHT_PENDING_STATUS = "review_light_pending"
JURY_REVIEW_PENDING_STATUS = "jury_review_pending"
JURY_REWORK_REQUIRED_STATUS = "jury_rework_required"
CORE_RESCUE_PENDING_STATUS = "core_rescue_pending"
MANUAL_HOLD_STATUS = "manual_hold"
BLOCKED_CREDIT_BURN_DISABLED_STATUS = "blocked_credit_burn_disabled"
ACCEPTED_AFTER_CORE_STATUS = "accepted_after_core"
ACCEPTED_AFTER_ROUND_STATUSES = {
    "1": "accepted_after_r1",
    "2": "accepted_after_r2",
    "3": "accepted_after_r3",
}
DESIRED_STATE_SCHEMA_VERSION = "2026-03-16.v1"
REVIEW_METADATA_SEPARATOR = " ; "
VALID_LIFECYCLE_STATES = {"planned", "scaffold", "dispatchable", "live", "signoff_only"}
DISPATCH_PARTICIPATION_LIFECYCLES = {"dispatchable", "live"}
COMPILE_MANIFEST_FILENAME = "compile.manifest.json"
REVIEW_HOLD_STATUSES = {
    "awaiting_pr",
    "review_requested",
    "awaiting_first_review",
    "review_light_pending",
    "jury_review_pending",
}
REVIEW_VISIBLE_STATUSES = REVIEW_HOLD_STATUSES | {"review_fix_required", "review_failed", "jury_rework_required", "core_rescue_pending", "manual_hold", "blocked_credit_burn_disabled"}
REVIEW_FAILED_INCIDENT_KIND = "review_failed"
REVIEW_STALLED_INCIDENT_KIND = "review_lane_stalled"
PR_CHECKS_FAILED_INCIDENT_KIND = "pr_checks_failed"
BLOCKED_UNRESOLVED_INCIDENT_KIND = "blocked_unresolved"
QUEUE_OVERLAY_FILENAME = "QUEUE.generated.yaml"
SPARK_MODEL = "gpt-5.3-codex-spark"
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
REVIEW_WAITING_STATUSES = {"queued", "requested"} | REVIEW_HOLD_STATUSES
AUTO_HEAL_CATEGORIES = {"coverage", "review", "capacity", "contracts"}
DEFAULT_AUTO_HEAL_ESCALATION_THRESHOLDS = {
    "coverage": 3,
    "review": 0,
    "capacity": 2,
    "contracts": 1,
}
DEFAULT_AUTO_HEAL_PLAYBOOKS = {
    "coverage": {
        "deterministic_steps": ["detect uncovered scope", "materialize scoped tasks", "publish safe queue overlay"],
        "llm_fallback": True,
        "verify_required": True,
        "max_attempts": 3,
    },
    "review": {
        "deterministic_steps": ["sync PR state", "retrigger stale review", "repair review lane"],
        "llm_fallback": True,
        "verify_required": True,
        "max_attempts": 2,
    },
    "capacity": {
        "deterministic_steps": ["reroute eligible account", "clear cooldown when safe", "shed lower priority load"],
        "llm_fallback": False,
        "verify_required": False,
        "max_attempts": 2,
    },
    "contracts": {
        "deterministic_steps": ["publish bridge shim", "queue remediation slice", "re-audit contract canon"],
        "llm_fallback": True,
        "verify_required": True,
        "max_attempts": 2,
    },
}
DEFAULT_COMPILE_FRESHNESS_HOURS = {
    "planned": 720,
    "scaffold": 336,
    "dispatchable": 168,
    "live": 168,
    "signoff_only": 720,
}
DEFAULT_BRIDGE_FALLBACK_ACCOUNTS = {
    "acct-chatgpt-core": ["acct-core-a", "acct-studio-a"],
    "acct-chatgpt-b": ["acct-ui-a", "acct-shared-b", "acct-hub-a", "acct-ea-a"],
}
EA_STATUS_BASE_URL = os.environ.get("EA_MCP_BASE_URL", "http://host.docker.internal:8090").rstrip("/")
EA_STATUS_API_TOKEN = os.environ.get("EA_MCP_API_TOKEN", "")
EA_STATUS_PRINCIPAL_ID = os.environ.get("EA_MCP_PRINCIPAL_ID", "codex-fleet")
EA_STATUS_CACHE_SECONDS = max(15, int(os.environ.get("FLEET_EA_STATUS_CACHE_SECONDS", "60") or 60))
EA_PROFILE_NAME_BY_LANE = {
    "easy": "easy",
    "repair": "repair",
    "groundwork": "groundwork",
    "review_light": "review_light",
    "core": "core",
    "jury": "audit",
    "survival": "survival",
}
EA_ONEMIN_TIGHT_PERCENT = 20.0
_EA_PROFILE_CACHE: Dict[str, Any] = {"fetched_at": 0.0, "payload": {}}
_EA_STATUS_CACHE: Dict[str, Any] = {"fetched_at": 0.0, "payload": {}, "window": "7d"}
RUNTIME_CACHE_KEY_EA_CODEX_PROFILES = "ea_codex_profiles"
RUNTIME_CACHE_KEY_EA_CODEX_STATUS = "ea_codex_status"
DEFAULT_SINGLETON_GROUP_ROLES = ["auditor", "healer", "project_manager"]
DEFAULT_CAPTAIN_POLICY = {
    "priority": 100,
    "service_floor": 1,
    "shed_order": 100,
    "preemption_policy": "slice_boundary",
    "admission_policy": "normal",
}
OPERATOR_AUTH_REQUIRED = str(os.environ.get("FLEET_OPERATOR_AUTH_REQUIRED", "false") or "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OPERATOR_PASSWORD = str(os.environ.get("FLEET_OPERATOR_PASSWORD", "") or "")
OPERATOR_COOKIE_NAME = str(os.environ.get("FLEET_OPERATOR_COOKIE_NAME", "fleet_operator_session") or "fleet_operator_session").strip() or "fleet_operator_session"
OPERATOR_USER = str(os.environ.get("FLEET_OPERATOR_USER", "operator") or "operator").strip() or "operator"
MISSION_BOARD_CONTRACT_NAME = "fleet.mission_board"
MISSION_BOARD_CONTRACT_VERSION = "2026-03-18"
PUBLIC_STATUS_CONTRACT_NAME = "fleet.public_status"
PUBLIC_STATUS_CONTRACT_VERSION = "2026-03-18"

if OPERATOR_AUTH_REQUIRED and not OPERATOR_PASSWORD:
    raise RuntimeError("FLEET_OPERATOR_PASSWORD is required when FLEET_OPERATOR_AUTH_REQUIRED=true")

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


def operator_auth_enabled() -> bool:
    return OPERATOR_AUTH_REQUIRED and bool(OPERATOR_PASSWORD)


def operator_session_value() -> str:
    return hashlib.sha256(OPERATOR_PASSWORD.encode("utf-8")).hexdigest()


def safe_next_path(value: Optional[str], default: str = "/admin") -> str:
    candidate = str(value or "").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return default
    return candidate


def operator_login_url(request: Request) -> str:
    target = safe_next_path(
        f"{request.url.path}{'?' + request.url.query if request.url.query else ''}",
        "/admin",
    )
    return f"/admin/login?next={urllib.parse.quote(target, safe='')}"


def operator_request_authorized(request: Request) -> bool:
    if not operator_auth_enabled():
        return True
    cookie_value = str(request.cookies.get(OPERATOR_COOKIE_NAME, "") or "")
    if cookie_value and hmac.compare_digest(cookie_value, operator_session_value()):
        return True
    header_value = str(request.headers.get("X-Fleet-Operator-Password", "") or "")
    if header_value and hmac.compare_digest(header_value, OPERATOR_PASSWORD):
        return True
    auth_header = str(request.headers.get("Authorization", "") or "")
    if auth_header.lower().startswith("bearer "):
        bearer = auth_header[7:].strip()
        if bearer and hmac.compare_digest(bearer, OPERATOR_PASSWORD):
            return True
    return False


def operator_auth_exempt_path(path: str) -> bool:
    return path in {"/health", "/admin/login", "/admin/logout"}


def operator_auth_protected_path(path: str) -> bool:
    return path.startswith("/admin") or path.startswith("/api/admin") or path.startswith("/api/cockpit")


@app.middleware("http")
async def operator_auth_middleware(request: Request, call_next):
    path = request.url.path
    if not operator_auth_enabled() or operator_auth_exempt_path(path) or not operator_auth_protected_path(path):
        return await call_next(request)
    if operator_request_authorized(request):
        return await call_next(request)
    login_url = operator_login_url(request)
    if path.startswith("/api/"):
        return JSONResponse({"error": "auth_required", "login": login_url}, status_code=401)
    return RedirectResponse(login_url, status_code=303)


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_yaml(path: pathlib.Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True, width=100000)
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


def normalize_lifecycle_state(value: Any, default: str = "dispatchable") -> str:
    clean = str(value or "").strip().lower() or str(default or "dispatchable").strip().lower()
    return clean if clean in VALID_LIFECYCLE_STATES else str(default or "dispatchable").strip().lower()


def project_dispatch_participates(project: Dict[str, Any]) -> bool:
    return normalize_lifecycle_state(project.get("lifecycle"), "dispatchable") in DISPATCH_PARTICIPATION_LIFECYCLES


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


def load_split_projects() -> List[Dict[str, Any]]:
    if not PROJECTS_DIR.exists() or not PROJECTS_DIR.is_dir():
        return []
    index_data = load_yaml(PROJECT_INDEX_PATH) if PROJECT_INDEX_PATH.exists() else {}
    indexed = [str(item).strip() for item in (index_data.get("projects") or []) if str(item).strip()]
    paths = [PROJECTS_DIR / item for item in indexed] if indexed else sorted(path for path in PROJECTS_DIR.glob("*.yaml") if path.name != PROJECT_INDEX_PATH.name)
    projects: List[Dict[str, Any]] = []
    for path in paths:
        data = load_yaml(path)
        if isinstance(data.get("projects"), list):
            projects.extend(dict(item or {}) for item in data.get("projects") or [] if isinstance(item, dict))
        elif data:
            projects.append(dict(data))
    return projects


def merge_split_config(fleet: Dict[str, Any]) -> Dict[str, Any]:
    policies_data = load_yaml(POLICIES_PATH)
    routing_data = load_yaml(ROUTING_PATH)
    groups_data = load_yaml(GROUPS_PATH)
    split_projects = load_split_projects()
    if policies_data:
        fleet["policies"] = dict(policies_data.get("policies") or policies_data)
    if routing_data:
        fleet["spider"] = dict(routing_data.get("spider") or routing_data)
        lanes = routing_data.get("lanes") or {}
        if isinstance(lanes, dict):
            fleet["lanes"] = dict(lanes)
    if groups_data:
        fleet["project_groups"] = list(groups_data.get("project_groups") or groups_data.get("groups") or [])
    if split_projects:
        fleet["projects"] = split_projects
    return fleet


def normalize_config() -> Dict[str, Any]:
    fleet = load_yaml(CONFIG_PATH)
    fleet = merge_split_config(fleet)
    accounts_cfg = load_yaml(ACCOUNTS_PATH)
    fleet.setdefault("schema_version", DESIRED_STATE_SCHEMA_VERSION)
    fleet.setdefault("policies", {})
    fleet.setdefault("spider", {})
    fleet.setdefault("lanes", {})
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet["lanes"] = normalize_lanes_config(fleet.get("lanes"))
    fleet["accounts"] = accounts_cfg.get("accounts", {}) or {}
    fleet["project_groups"] = normalized_project_groups(fleet["projects"], fleet["project_groups"])
    auto_heal = fleet["policies"].setdefault("auto_heal", {})
    auto_heal.setdefault("categories", {})
    auto_heal.setdefault("escalation_thresholds", {})
    auto_heal["playbooks"] = {
        **DEFAULT_AUTO_HEAL_PLAYBOOKS,
        **(auto_heal.get("playbooks") or {}),
    }
    compile_cfg = fleet["policies"].setdefault("compile", {})
    compile_cfg["freshness_hours"] = {
        **DEFAULT_COMPILE_FRESHNESS_HOURS,
        **(compile_cfg.get("freshness_hours") or {}),
    }
    for project in fleet["projects"]:
        project.setdefault("enabled", True)
        project["lifecycle"] = normalize_lifecycle_state(project.get("lifecycle"), "dispatchable")
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("verify_cmd", "")
        project.setdefault("design_doc", "")
        project.setdefault("accounts", [])
        project.setdefault("account_policy", {})
        project.setdefault("review", {})
        project.setdefault("queue", [])
        project.setdefault("queue_sources", [])
        project.setdefault("runner", {})
        project["queue"] = [
            normalize_task_queue_item(item, lanes=fleet["lanes"])
            for item in project.get("queue") or []
        ]
        project["runner"].setdefault("sandbox", "danger-full-access")
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
        review = project["review"]
        review.setdefault("enabled", True)
        review.setdefault("mode", "github")
        review.setdefault("trigger", "manual_comment")
        review.setdefault("fallback_mode", "local")
        review.setdefault("fallback_conditions", "degraded_or_stalled")
        review.setdefault("required_before_queue_advance", True)
        review.setdefault("focus_template", "for regressions and missing tests")
        review.setdefault("owner", "")
        review.setdefault("repo", "")
        review.setdefault("base_branch", "main")
        review.setdefault("branch_template", f"fleet/{project.get('id', 'project')}")
        review.setdefault("bot_logins", ["codex"])
    project_index = {str(project.get("id") or ""): project for project in fleet["projects"]}
    for group in fleet["project_groups"]:
        group.setdefault("projects", [])
        group["lifecycle"] = normalize_lifecycle_state(group.get("lifecycle"), "live")
        group.setdefault("mode", "independent")
        group.setdefault("contract_sets", [])
        group.setdefault("milestone_source", {})
        group.setdefault("group_roles", [])
        dispatch_members = [
            project_id
            for project_id in (group.get("projects") or [])
            if project_dispatch_participates(project_index.get(str(project_id), {}))
        ]
        default_floor = len(dispatch_members) if str(group.get("mode", "") or "").strip().lower() == "lockstep" and dispatch_members else 1
        group["captain"] = normalized_captain_policy(group.get("captain"), default_service_floor=default_floor)
    return fleet


def project_review_policy(project_cfg: Dict[str, Any]) -> Dict[str, Any]:
    review = dict(project_cfg.get("review") or {})
    review.setdefault("enabled", True)
    review.setdefault("mode", "github")
    review.setdefault("trigger", "manual_comment")
    review.setdefault("fallback_mode", "local")
    review.setdefault("fallback_conditions", "degraded_or_stalled")
    review.setdefault("required_before_queue_advance", True)
    review.setdefault("focus_template", "for regressions and missing tests")
    review.setdefault("owner", "")
    review.setdefault("repo", "")
    review.setdefault("base_branch", "main")
    review.setdefault("branch_template", f"fleet/{project_cfg.get('id', 'project')}")
    review.setdefault("bot_logins", ["codex"])
    return review


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
    project_id: Optional[str],
    stored_status: Optional[str],
    queue_len: int,
    queue_index: int,
    enabled: bool,
    active_run_id: Optional[int],
    source_backlog_open: bool,
    pull_request: Optional[Dict[str, Any]] = None,
) -> str:
    status = str(stored_status or "").strip() or READY_STATUS
    pr = dict(pull_request or {})
    review_status = str(pr.get("review_status") or "").strip().lower()
    review_mode = str(pr.get("review_mode") or "github").strip().lower()
    review_runtime_status: Optional[str] = None
    loop_stage = review_loop_stage(pr)
    if loop_stage in {
        AWAITING_FIRST_REVIEW_STATUS,
        REVIEW_LIGHT_PENDING_STATUS,
        JURY_REVIEW_PENDING_STATUS,
        JURY_REWORK_REQUIRED_STATUS,
        CORE_RESCUE_PENDING_STATUS,
        MANUAL_HOLD_STATUS,
    }:
        review_runtime_status = loop_stage
    elif review_status in {"findings_open", "review_fix_required"}:
        review_runtime_status = "review_fix_required"
    elif review_status == "review_failed":
        review_runtime_status = "review_failed"
    elif review_status == "local_review":
        review_runtime_status = "review_requested" if review_mode == "github" else (loop_stage or "review_requested")
    elif review_status in REVIEW_WAITING_STATUSES:
        review_runtime_status = "review_requested" if review_mode != "github" or int(pr.get("pr_number") or 0) > 0 else "awaiting_pr"
    if not enabled:
        return "paused"
    if status in {"starting", "running", "verifying"} and active_run_id:
        return status
    if int(queue_index) >= int(queue_len):
        if review_runtime_status:
            return review_runtime_status
        if status in REVIEW_VISIBLE_STATUSES:
            return status
        if status == SOURCE_BACKLOG_OPEN_STATUS or source_backlog_open:
            return SOURCE_BACKLOG_OPEN_STATUS
        return "complete"
    if status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS}:
        return READY_STATUS
    return status


def public_runtime_status(runtime_status: Optional[str]) -> str:
    status = str(runtime_status or "").strip() or READY_STATUS
    if status == READY_STATUS:
        return WAITING_CAPACITY_STATUS
    if status == "complete":
        return "complete"
    if status == "awaiting_account":
        return WAITING_CAPACITY_STATUS
    if status in {"review_fix_required", JURY_REWORK_REQUIRED_STATUS, CORE_RESCUE_PENDING_STATUS}:
        return REVIEW_FIX_STATUS
    return status


def queue_complete_public_status(*, lifecycle: Optional[str], group_signed_off: bool) -> str:
    if group_signed_off:
        return COMPLETED_SIGNED_OFF_STATUS
    lifecycle_state = normalize_lifecycle_state(lifecycle, "dispatchable")
    if lifecycle_state in {"planned", "scaffold"}:
        return SCAFFOLD_QUEUE_COMPLETE_STATUS
    return CONFIGURED_QUEUE_COMPLETE_STATUS


def runtime_completion_basis(
    *,
    runtime_status: Optional[str],
    queue_len: int,
    queue_index: int,
    has_queue_sources: bool,
) -> str:
    status = str(runtime_status or "").strip() or READY_STATUS
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
    if status == "awaiting_pr":
        return "local verify passed; waiting to create or update the review record before queue advance"
    if status == "review_requested":
        return "local verify passed; review is requested and queue advance is gated on results"
    if status == AWAITING_FIRST_REVIEW_STATUS:
        return "groundwork passed local verify; waiting for the first review_light pass before queue advance"
    if status == REVIEW_LIGHT_PENDING_STATUS:
        return "rework passed local verify; waiting for the next review_light pass before queue advance"
    if status == JURY_REVIEW_PENDING_STATUS:
        return "cheap review accepted the slice; waiting for jury final signoff before queue advance"
    if status == "review_failed":
        return "review orchestration failed and needs operator attention"
    if status == "review_fix_required":
        return "review returned findings and the slice needs follow-up fixes before queue advance"
    if status == JURY_REWORK_REQUIRED_STATUS:
        return "review findings are still open; the cheap loop is routing the slice back to groundwork"
    if status == CORE_RESCUE_PENDING_STATUS:
        return "cheap review rounds are exhausted or final signoff requested escalation; the slice is waiting for core rescue"
    if status == MANUAL_HOLD_STATUS:
        return "final review requested a manual hold and the slice needs operator attention before queue advance"
    if status == BLOCKED_CREDIT_BURN_DISABLED_STATUS:
        return "cheap review requested core rescue, but zero-credit policy blocked escalation and the slice now needs operator opt-in"
    if status == WAITING_CAPACITY_STATUS:
        return "configured queue has remaining work; waiting for scheduler dispatch, account eligibility, cooldown recovery, or higher-level gate release"
    if status == HEALING_STATUS:
        return "the resolver is actively healing the current blockage or refill condition"
    if status == QUEUE_REFILLING_STATUS:
        return "approved resolver tasks are being published into the next queue overlay"
    if status == DECISION_REQUIRED_STATUS:
        return "resolver-generated follow-up work still needs operator approval before queue advance"
    if status == REVIEW_FIX_STATUS:
        return "review returned findings and the review-fix loop is active"
    if status in {"starting", "running", "verifying"}:
        if queue_len == 0:
            return "configured queue currently resolves to zero active items"
        return f"configured queue has remaining work at {current} / {queue_len}"
    if status == READY_STATUS:
        if queue_len == 0:
            return "configured queue currently resolves to zero active items"
        return f"configured queue has remaining work at {current} / {queue_len} and is waiting for dispatch"
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
    default_weight = positive_int(meta.get("design_milestone_default_weight"), 5)
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
        item["status"] = str(item.get("status") or "open").strip().lower() or "open"
        item["weight"] = milestone_weight(item, default_weight)
        item.setdefault("design_area", "")
        item.setdefault("owner_project", "")
        item.setdefault("exit_tests_total", 0)
        item.setdefault("exit_tests_passed", 0)
        items.append(item)
    return items


def deployment_display_text(*, status: str, summary: str, target_url: str, surface: str = "") -> str:
    if summary:
        return summary
    parts = [part for part in [status, surface, target_url] if str(part).strip()]
    return " | ".join(parts) if parts else "No deployment metadata."


def deployment_promotion_stage(status: str) -> str:
    clean = str(status or "").strip().lower()
    if clean in {"public_stable", "stable"}:
        return "public_stable"
    if clean in {"release_candidate", "rc"}:
        return "release_candidate"
    if clean in {"promoted_preview", "promoted"}:
        return "promoted_preview"
    if clean in {"preview", "live_preview"}:
        return "preview"
    if clean in {"stale_preview", "stale"}:
        return "stale_preview"
    if clean in {"protected_preview", "protected"}:
        return "protected_preview"
    if clean in {"planned"}:
        return "planned"
    return "undeclared"


def normalize_project_deployment(section: Any) -> Dict[str, Any]:
    data = dict(section or {}) if isinstance(section, dict) else {}
    status = str(data.get("status") or "undeclared").strip()
    surface = str(data.get("surface") or "").strip()
    target_url = str(data.get("target_url") or data.get("url") or "").strip()
    summary = str(data.get("summary") or "").strip()
    visibility = str(data.get("visibility") or "").strip()
    promotion_stage = str(data.get("promotion_stage") or deployment_promotion_stage(status)).strip() or "undeclared"
    return {
        "status": status,
        "surface": surface,
        "target_url": target_url,
        "summary": summary,
        "visibility": visibility,
        "promotion_stage": promotion_stage,
        "release_gate": str(data.get("release_gate") or "").strip(),
        "display": deployment_display_text(status=status, summary=summary, target_url=target_url, surface=surface),
    }


def normalize_group_deployment(section: Any) -> Dict[str, Any]:
    data = dict(section or {}) if isinstance(section, dict) else {}
    public_surface = dict(data.get("public_surface") or {}) if isinstance(data.get("public_surface"), dict) else {}
    raw_targets = public_surface.get("targets") or data.get("targets") or []
    targets: List[Dict[str, Any]] = []
    if isinstance(raw_targets, list):
        for item in raw_targets:
            target = dict(item or {}) if isinstance(item, dict) else {}
            targets.append(
                {
                    "name": str(target.get("name") or target.get("id") or "").strip(),
                    "url": str(target.get("url") or "").strip(),
                    "status": str(target.get("status") or "").strip(),
                    "owner_project": str(target.get("owner_project") or "").strip(),
                    "surface": str(target.get("surface") or "").strip(),
                }
            )
    target_url = next((str(target.get("url") or "").strip() for target in targets if str(target.get("url") or "").strip()), "")
    first_surface = next((str(target.get("surface") or "").strip() for target in targets if str(target.get("surface") or "").strip()), "")
    status = str(public_surface.get("status") or data.get("status") or ("public" if target_url else "undeclared")).strip()
    summary = str(public_surface.get("summary") or data.get("summary") or "").strip()
    promotion_stage = str(public_surface.get("promotion_stage") or data.get("promotion_stage") or deployment_promotion_stage(status)).strip() or "undeclared"
    return {
        "status": status,
        "summary": summary,
        "target_url": target_url,
        "targets": targets,
        "promotion_stage": promotion_stage,
        "release_gate": str(public_surface.get("release_gate") or data.get("release_gate") or "").strip(),
        "display": deployment_display_text(status=status, summary=summary, target_url=target_url, surface=first_surface),
    }


def runtime_completion_state(runtime_status: str, lifecycle: str) -> str:
    status = str(runtime_status or "").strip().lower()
    lifecycle_state = normalize_lifecycle_state(lifecycle, "dispatchable")
    if status == "signoff_only" or lifecycle_state == "signoff_only":
        return "signoff_only"
    if status in {"starting", "running", "verifying"}:
        return "in_progress"
    if status in REVIEW_VISIBLE_STATUSES:
        return "review_gate"
    if status in {HEALING_STATUS, QUEUE_REFILLING_STATUS, DECISION_REQUIRED_STATUS, SOURCE_BACKLOG_OPEN_STATUS, "blocked"}:
        return "recovery_pending"
    if status in {CONFIGURED_QUEUE_COMPLETE_STATUS, "complete"}:
        return "runtime_complete"
    if status == SCAFFOLD_QUEUE_COMPLETE_STATUS or lifecycle_state == "scaffold":
        return "scaffold_complete"
    if status == COMPLETED_SIGNED_OFF_STATUS:
        return "signed_off"
    if status == READY_STATUS:
        return "dispatch_ready"
    return status or "unknown"


def project_public_runtime_status(project: Dict[str, Any]) -> str:
    status = str(project.get("status") or project.get("runtime_status") or "").strip().lower()
    if status:
        return status
    return project_runtime_status(project).lower()


def design_completion_state(
    *,
    milestone_coverage_complete: bool,
    design_coverage_complete: bool,
    group_signed_off: bool,
) -> str:
    if group_signed_off and milestone_coverage_complete and design_coverage_complete:
        return "signed_off"
    if milestone_coverage_complete and design_coverage_complete:
        return "covered_pending_signoff"
    if design_coverage_complete:
        return "design_covered_pending_milestones"
    if milestone_coverage_complete:
        return "milestones_mapped_pending_design"
    return "incomplete"


def text_items(values: Any) -> List[str]:
    items: List[str] = []
    for value in values or []:
        if isinstance(value, dict):
            structured = ""
            for key in ("title", "text", "summary", "label", "id"):
                structured = str(value.get(key) or "").strip()
                if structured:
                    break
            if structured:
                items.append(structured)
                continue
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
    status = str(project.get("runtime_status_internal") or project.get("runtime_status") or "").strip() or READY_STATUS
    lifecycle_state = normalize_lifecycle_state(project.get("lifecycle"), "dispatchable")
    if lifecycle_state == "signoff_only":
        if status in {"blocked", "review_failed"} or int(project.get("open_incident_count") or 0) > 0:
            return "high"
        return "nominal"
    if status in {"blocked", "awaiting_account"}:
        return "critical"
    if status in {"awaiting_pr", "review_requested", "review_failed", "review_fix_required"}:
        return "high"
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
    participant_projects = [project for project in group_projects if project_dispatch_participates(project)]
    eligible_union: List[str] = []
    per_project: Dict[str, int] = {}
    account_rows = {row["alias"]: row for row in account_pool_rows(config)}
    total_slots = 0
    for project in participant_projects:
        aliases = eligible_account_aliases(config, project, now)
        per_project[str(project.get("id") or "")] = len(aliases)
        for alias in aliases:
            if alias in eligible_union:
                continue
            eligible_union.append(alias)
            total_slots += max(1, int((account_rows.get(alias, {}).get("max_parallel_runs") or 1)))
    captain = group_captain_policy(group_cfg)
    required_slots = max(1, int(captain.get("service_floor") or 1))
    total_slots = min(total_slots, max(1, int(((config.get("policies") or {}).get("max_parallel_runs") or 1))))
    remaining_slices = sum(max(int(project.get("queue_len") or 0) - int(project.get("queue_index") or 0), 0) for project in participant_projects)
    if not participant_projects:
        return {
            "level": "sufficient",
            "basis": "no dispatch-participating members are currently in this group",
            "eligible_accounts": eligible_union,
            "eligible_account_count": len(eligible_union),
            "eligible_parallel_slots": total_slots,
            "required_slots": 0,
            "remaining_slices": 0,
        }
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
    participant_projects = [project for project in group_projects if project_dispatch_participates(project)]
    project_states = {project_pressure_state(project) for project in participant_projects}
    if "critical" in project_states or not bool(group.get("dispatch_ready", True)):
        return "high"
    if "high" in project_states:
        return "high"
    if "elevated" in project_states or int(group.get("uncovered_scope_count") or 0) > 0:
        return "elevated"
    if "active" in project_states:
        return "active"
    return "nominal"


def runway_finish_outlook(level: str, basis: str) -> str:
    clean = str(level or "").strip().lower()
    if clean == "blocked":
        return "blocked to start"
    if clean == "insufficient":
        return "shortfall against service floor"
    if clean == "tight":
        return "can run now, finish under pressure"
    if clean == "sufficient":
        return "enough to finish at current posture"
    return str(basis or "runway outlook unknown").strip() or "runway outlook unknown"


def audit_task_candidate_counts_for_scope(scope_type: str, scope_ids: List[str]) -> Dict[str, int]:
    if not table_exists("audit_task_candidates") or not scope_ids:
        return {"open": 0, "approved": 0}
    placeholders = ", ".join("?" for _ in scope_ids)
    counts = {"open": 0, "approved": 0}
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT status, finding_key, COUNT(*) AS count
            FROM audit_task_candidates
            WHERE scope_type=? AND scope_id IN ({placeholders}) AND status IN ('open', 'approved')
            GROUP BY status, finding_key
            """,
            (scope_type, *scope_ids),
        ).fetchall()
    for row in rows:
        status = str(row["status"] or "").strip().lower()
        if status == "open" and audit_finding_is_recommended(row["finding_key"]):
            counts["approved"] += int(row["count"] or 0)
            continue
        if status in counts:
            counts[status] += int(row["count"] or 0)
    return counts


def group_ready_project_ids(group_projects: List[Dict[str, Any]]) -> List[str]:
    return [
        str(project.get("id") or "")
        for project in group_projects
        if project_dispatch_participates(project) and project_runtime_status(project) == READY_STATUS
    ]


def group_auditor_task_counts(group_id: str, group_projects: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"open": 0, "approved": 0}
    for project in group_projects:
        counts["open"] += int(project.get("open_audit_task_count") or 0)
        counts["approved"] += int(project.get("approved_audit_task_count") or 0)
    group_counts = audit_task_candidate_counts_for_scope("group", [group_id])
    counts["open"] += int(group_counts["open"])
    counts["approved"] += int(group_counts["approved"])
    return counts


def short_question_detail(text: str, limit: int = 180) -> str:
    detail = " ".join(str(text or "").strip().split())
    if len(detail) <= limit:
        return detail
    return detail[: limit - 3].rstrip() + "..."


def operator_relevant_dispatch_blockers(values: List[Any]) -> List[str]:
    blockers = [str(value or "").strip() for value in values if str(value or "").strip()]
    if not blockers:
        return []
    filtered = [
        blocker
        for blocker in blockers
        if "run already in progress" not in blocker.lower()
        and "cooldown active" not in blocker.lower()
        and not blocker.lower().startswith("incident:")
    ]
    return filtered


def group_open_incidents(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    group_id = str(group.get("id") or "").strip()
    project_ids = [str(project.get("id") or "").strip() for project in group_projects if str(project.get("id") or "").strip()]
    items = incidents(status="open", limit=100, scope_type="group", scope_ids=[group_id]) if group_id else []
    items.extend(incidents(status="open", limit=100, scope_type="project", scope_ids=project_ids))
    items = filter_runtime_relevant_incidents(items, group_projects)
    items.sort(
        key=lambda item: (
            0 if str(item.get("severity") or "") == "critical" else 1 if str(item.get("severity") or "") == "high" else 2,
            str(item.get("updated_at") or ""),
        )
    )
    return items


def group_operator_question(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> str:
    group_id = str(group.get("id") or "").strip() or "group"
    ready_count = int(group.get("ready_project_count") or 0)
    review_waiting = int(group.get("review_waiting_count") or 0)
    review_blocking = int(group.get("review_blocking_count") or 0)
    blockers = list(group.get("contract_blockers") or []) + operator_relevant_dispatch_blockers(group.get("dispatch_blockers") or [])
    status = str(group.get("status") or "").strip().lower()
    auditor_can_solve = bool(group.get("auditor_can_solve"))
    incident_rows = [item for item in (group.get("incidents") or []) if incident_requires_operator_attention(item)]
    if incident_rows:
        top = incident_rows[0]
        return f"{group_id}: {short_question_detail(top.get('title') or top.get('summary') or 'an incident needs operator attention')}. Should I apply the proposed recovery, or override it manually?"
    if review_blocking > 0:
        return f"{group_id}: Codex review reported blocking findings. Should I fix them and re-request review, or accept the risk?"
    if review_waiting > 0:
        return f"{group_id}: review is still pending. Should I wait for GitHub review, or override the review gate?"
    if status == "product_signed_off":
        return f"{group_id}: this group is signed off. Should I keep it closed, or reopen it for more work?"
    if status == "complete":
        return f"{group_id}: this group is complete. Should I keep it closed, or reopen it only if more work is required?"
    if blockers:
        first_blocker = short_question_detail(blockers[0])
        if ready_count > 1 and not auditor_can_solve:
            return f"{group_id}: {ready_count} dispatch-eligible projects are blocked above the repo layer and the auditor has no publishable fix. Should I keep the block in place, or choose the missing contract or package direction? First blocker: {first_blocker}"
        return f"{group_id}: blockers remain open. Should I keep the block in place, or override it manually? First blocker: {first_blocker}"
    if status == "proposed_tasks":
        return f"{group_id}: the auditor has proposed follow-up work. Should I publish the approved tasks now, or keep them pending?"
    if status == "audit_requested":
        return f"{group_id}: the auditor refill loop is already running. Should I wait for it to finish, or override it manually?"
    if status == "audit_required":
        return f"{group_id}: the current queue is exhausted without signoff. Should I run another audit or refill pass, or sign off the group?"
    if ready_count > 0:
        return f"{group_id}: {ready_count} projects are waiting for dispatch. Should I let the group run, or keep it paused?"
    return f"{group_id}: what is the next operator decision for this group?"


def group_notification_payload(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    group_id = str(group.get("id") or "").strip() or "group"
    ready_ids = list(group.get("ready_project_ids") or [])
    ready_count = len(ready_ids)
    auditor_can_solve = bool(group.get("auditor_can_solve"))
    blockers = list(group.get("contract_blockers") or []) + operator_relevant_dispatch_blockers(group.get("dispatch_blockers") or [])
    review_blocking = int(group.get("review_blocking_count") or 0)
    incident_rows = [item for item in (group.get("incidents") or []) if incident_requires_operator_attention(item)]
    needs_notification = bool(incident_rows)
    reason_bits: List[str] = []
    if incident_rows:
        top = incident_rows[0]
        reason_bits.append(short_question_detail(top.get("title") or top.get("summary") or "", limit=140))
        if blockers:
            reason_bits.append(short_question_detail(blockers[0], limit=140))
        if review_blocking > 0:
            reason_bits.append(f"{review_blocking} blocking review finding(s)")
    severity = str((incident_rows[0] if incident_rows else {}).get("severity") or "")
    title = f"{group_id}: {len(incident_rows)} incident(s) need operator attention" if incident_rows else ""
    return {
        "needed": needs_notification,
        "severity": severity,
        "title": title,
        "reason": "; ".join(reason_bits),
        "question": str(group.get("operator_question") or ""),
        "ready_project_count": ready_count,
        "ready_project_ids": ready_ids,
        "incident_count": len(incident_rows),
        "auditor_can_solve": auditor_can_solve,
        "focus_id": f"group-problem-{group_id}",
        "href": f"/admin#group-problem-{group_id}",
        "notification_key": f"{group_id}|{ready_count}|{len(incident_rows)}|{int(auditor_can_solve)}|{'; '.join(reason_bits)}",
    }


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


def project_review_policy_summary(project: Dict[str, Any]) -> str:
    review = project_review_policy(project)
    if not bool(review.get("enabled", True)):
        return "review disabled"
    parts = [
        f"mode={str(review.get('mode') or 'github')}",
        f"trigger={str(review.get('trigger') or 'manual_comment')}",
        "required" if bool(review.get("required_before_queue_advance", True)) else "advisory",
    ]
    owner = str(review.get("owner") or "").strip()
    repo = str(review.get("repo") or "").strip()
    if owner and repo:
        parts.append(f"repo={owner}/{repo}")
    fallback_mode = str(review.get("fallback_mode") or "").strip()
    fallback_conditions = str(review.get("fallback_conditions") or "").strip()
    if fallback_mode:
        suffix = f"fallback={fallback_mode}"
        if fallback_conditions:
            suffix += f" when {fallback_conditions}"
        parts.append(suffix)
    focus = str(review.get("focus_template") or "").strip()
    if focus:
        parts.append(f"focus={focus}")
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


SCOPE_TEXT_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "before",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "so",
    "still",
    "that",
    "the",
    "their",
    "then",
    "this",
    "to",
    "with",
}


def normalize_scope_text(text: Any) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(text or "").strip().lower())
    tokens = [token for token in cleaned.split() if len(token) > 1 and token not in SCOPE_TEXT_STOPWORDS]
    return " ".join(tokens)


def scope_text_materialized(scope_text: str, materialized_texts: List[str]) -> bool:
    normalized_scope = normalize_scope_text(scope_text)
    if not normalized_scope:
        return False
    scope_tokens = set(normalized_scope.split())
    if not scope_tokens:
        return False
    for item in materialized_texts:
        normalized_item = normalize_scope_text(item)
        if not normalized_item:
            continue
        if normalized_scope in normalized_item or normalized_item in normalized_scope:
            return True
        item_tokens = set(normalized_item.split())
        overlap = len(scope_tokens & item_tokens)
        if overlap >= min(4, len(scope_tokens)) and overlap >= max(2, int(len(scope_tokens) * 0.55)):
            return True
    return False


def audit_candidate_materialization_texts(scope_type: str, scope_id: str) -> List[str]:
    if not table_exists("audit_task_candidates"):
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT title, detail
            FROM audit_task_candidates
            WHERE scope_type=? AND scope_id=? AND status IN ('open', 'approved', 'published')
            ORDER BY last_seen_at DESC, task_index ASC
            """,
            (scope_type, scope_id),
        ).fetchall()
    texts: List[str] = []
    for row in rows:
        for value in (row["title"], row["detail"]):
            clean = str(value or "").strip()
            if clean:
                texts.append(clean)
    return texts


def actionable_scope_items(scope_items: List[str], materialized_texts: List[str]) -> List[str]:
    return [item for item in scope_items if not scope_text_materialized(item, materialized_texts)]


def project_actionable_uncovered_scope(
    project_id: str,
    scope_items: List[str],
    queue_items: List[str],
    current_slice: Optional[str],
) -> List[str]:
    materialized_texts = list(queue_items)
    if current_slice:
        materialized_texts.append(str(current_slice))
    materialized_texts.extend(audit_candidate_materialization_texts("project", project_id))
    return actionable_scope_items(scope_items, materialized_texts)


def group_actionable_uncovered_scope(
    group_id: str,
    scope_items: List[str],
    group_projects: List[Dict[str, Any]],
) -> List[str]:
    materialized_texts = audit_candidate_materialization_texts("group", group_id)
    for project in group_projects:
        queue = project.get("queue")
        if isinstance(queue, list):
            materialized_texts.extend(str(item or "").strip() for item in queue if str(item or "").strip())
        current_item = current_queue_item_text(project)
        if current_item:
            materialized_texts.append(current_item)
    actionable = actionable_scope_items(scope_items, materialized_texts)
    if not actionable:
        return []
    dispatch_projects = [project for project in group_projects if project_dispatch_participates(project)]
    followup_projects = dispatch_projects or group_projects
    concrete_followup = any(
        int(project.get("open_audit_task_count") or 0) > 0
        or int(project.get("approved_audit_task_count") or 0) > 0
        or bool(project.get("needs_refill"))
        or int(project.get("uncovered_scope_count") or 0) > 0
        for project in followup_projects
    )
    if not concrete_followup:
        return []
    return actionable


def project_queue_source_health(project_cfg: Dict[str, Any], queue_len: int) -> str:
    if project_cfg.get("queue_sources"):
        if queue_len <= 0:
            return "source-backed queue resolved to zero active items"
        return "source-backed queue resolved to active items"
    if queue_len <= 0:
        return "static queue is empty"
    return "static queue has active items"


def project_has_refill_path(
    *,
    project_cfg: Dict[str, Any],
    runtime_status: str,
    queue_len: int,
    uncovered_scope_count: int,
    open_task_count: int,
    approved_task_count: int,
) -> bool:
    return bool(
        runtime_status == SOURCE_BACKLOG_OPEN_STATUS
        or (bool(project_cfg.get("queue_sources")) and queue_len <= 0)
        or (runtime_status == "complete" and uncovered_scope_count > 0)
        or approved_task_count > 0
        or open_task_count > 0
    )


def project_stop_context(
    *,
    project_cfg: Dict[str, Any],
    runtime_status: str,
    queue_len: int,
    uncovered_scope_count: int,
    modeled_uncovered_scope_count: int = 0,
    open_task_count: int,
    approved_task_count: int,
    group_open_task_count: int = 0,
    group_approved_task_count: int = 0,
    last_error: Optional[str],
    cooldown_until: Optional[str],
    review_eta: Optional[Dict[str, Any]],
    pull_request: Optional[Dict[str, Any]] = None,
    milestone_coverage_complete: bool,
    design_coverage_complete: bool,
    group_signed_off: bool,
) -> Dict[str, Any]:
    stop_reason = ""
    next_action = ""
    unblocker = ""
    now = utc_now()
    lifecycle_state = normalize_lifecycle_state(project_cfg.get("lifecycle"), "dispatchable")
    cooldown = parse_iso(cooldown_until)
    active = runtime_status in {"starting", "running", "verifying"}
    display_uncovered_scope_count = max(int(uncovered_scope_count or 0), int(modeled_uncovered_scope_count or 0))
    refill_path = project_has_refill_path(
        project_cfg=project_cfg,
        runtime_status=runtime_status,
        queue_len=queue_len,
        uncovered_scope_count=uncovered_scope_count,
        open_task_count=open_task_count,
        approved_task_count=approved_task_count,
    )
    pr = dict(pull_request or {})
    review_mode = str((pr.get("review_mode") or (project_cfg.get("review") or {}).get("mode") or "github")).strip().lower()
    review_status = str(pr.get("review_status") or "").strip().lower()
    review_summary = str((review_eta or {}).get("summary") or "").strip().lower()
    effective_local_review = bool(
        review_mode != "github"
        or review_status == "local_review"
        or review_summary.startswith("local review")
    )
    if lifecycle_state == "signoff_only":
        open_task_count = 0
        approved_task_count = 0
        group_open_task_count = 0
        group_approved_task_count = 0
        refill_path = False
    needs_refill = bool(not active and runtime_status not in REVIEW_VISIBLE_STATUSES and not group_signed_off and refill_path)
    if not active:
        if runtime_status == "complete" and lifecycle_state == "signoff_only":
            stop_reason = "this repo is informational only and is not part of the coding queue"
            next_action = "refresh the human guide when canonical design, ownership, or public-surface truth changes"
            unblocker = ""
        elif runtime_status == "paused":
            stop_reason = "desired state disabled the project"
            next_action = "resume the project"
            unblocker = "operator"
        elif runtime_status == "awaiting_pr":
            stop_reason = "local verify passed and the slice is awaiting GitHub PR/review orchestration"
            next_action = "check GitHub repo connectivity or request review again"
            unblocker = "operator"
        elif runtime_status == "review_requested":
            if effective_local_review:
                stop_reason = "the slice is waiting on local review"
                next_action = str((review_eta or {}).get("summary") or "wait for local review or redispatch it if needed")
                unblocker = "local review lane"
            else:
                stop_reason = "the slice is waiting on GitHub Codex review"
                next_action = str((review_eta or {}).get("summary") or "wait for review, sync review state, or re-request review if needed")
                unblocker = "GitHub Codex review lane"
        elif runtime_status == "review_failed":
            if effective_local_review:
                stop_reason = "local review orchestration failed"
                next_action = "let the healer or scheduler restart the local review lane before escalating"
                unblocker = "healer"
            else:
                stop_reason = "GitHub review orchestration failed"
                next_action = "let the healer resync review state or repair the PR lane before escalating"
                unblocker = "healer"
        elif runtime_status == "review_fix_required":
            if effective_local_review:
                stop_reason = "local review returned findings that must be fixed before queue advance"
                next_action = "let the scheduler redispatch the slice to apply the review fixes and then rerun local review"
                unblocker = "scheduler"
            else:
                stop_reason = "GitHub review returned findings that must be fixed before queue advance"
                next_action = "let the scheduler redispatch the slice to apply the review fixes and then re-request review"
                unblocker = "scheduler"
        elif runtime_status == "awaiting_account":
            stop_reason = "no eligible account or model is available for the current slice"
            next_action = "let the scheduler spill over to another eligible account or wait for capacity recovery"
            unblocker = "scheduler"
        elif runtime_status == "blocked":
            stop_reason = "repeated failures blocked execution"
            if approved_task_count > 0 or open_task_count > 0:
                next_action = "healing tasks are ready; the resolver will publish the next narrowed follow-up"
                unblocker = "healer"
            elif group_approved_task_count > 0 or group_open_task_count > 0:
                next_action = "group-level recovery tasks are ready; the resolver will publish the next narrowed follow-up"
                unblocker = "healer"
            else:
                next_action = "the targeted auditor is generating a recovery path before escalation"
                unblocker = "auditor"
        elif runtime_status == HEALING_STATUS:
            stop_reason = "the healer is actively resolving the current blockage or refill condition"
            if approved_task_count > 0:
                next_action = "approved healing tasks are being published automatically"
            elif open_task_count > 0 or group_open_task_count > 0 or group_approved_task_count > 0:
                next_action = "the healer is narrowing follow-up work and will publish the next safe slice automatically"
            else:
                next_action = "wait for the healer to finish resolving the current blockage before dispatch resumes"
            unblocker = "healer"
        elif runtime_status == QUEUE_REFILLING_STATUS:
            stop_reason = "approved refill work is being published into the next queue overlay"
            next_action = "wait for the healer to publish the next queue overlay and resume dispatch"
            unblocker = "healer"
        elif cooldown and cooldown > now:
            stop_reason = "project is cooling down after a recent failure or rate limit"
            next_action = "wait for cooldown expiry or let the scheduler reroute capacity"
            unblocker = "scheduler"
        elif runtime_status == SOURCE_BACKLOG_OPEN_STATUS:
            stop_reason = "the current queue materialization is exhausted, but the backlog source still reports open work"
            if approved_task_count > 0:
                next_action = "approved refill tasks are being published into the next queue overlay"
                unblocker = "healer"
            elif open_task_count > 0:
                next_action = "the healer is reviewing resolver proposals and will publish the safe refill automatically unless policy blocks it"
                unblocker = "healer"
            else:
                next_action = "the auditor is materializing the next scoped queue from backlog evidence"
                unblocker = "auditor"
        elif runtime_status == "complete" and needs_refill:
            if approved_task_count > 0:
                stop_reason = "the current queue is exhausted and approved refill work is being published"
                next_action = "approved refill tasks are being published automatically"
                unblocker = "healer"
            elif open_task_count > 0:
                stop_reason = "the current queue is exhausted and safe refill work is being prepared"
                next_action = "the healer is converting uncovered scope into the next scoped queue automatically"
                unblocker = "healer"
            elif queue_len <= 0 and project_cfg.get("queue_sources"):
                stop_reason = "the current queue is exhausted and the backlog source is being rematerialized"
                next_action = "the auditor is refilling the queue from source-backed backlog evidence and modeled design scope"
                unblocker = "auditor"
            else:
                stop_reason = "the current queue is exhausted while modeled design scope is being materialized"
                next_action = "the auditor is generating the next scoped queue from uncovered scope"
                unblocker = "auditor"
        elif runtime_status == "complete":
            if approved_task_count > 0:
                stop_reason = "the current queue is exhausted and approved refill work is ready to publish"
                next_action = "approved refill tasks are being published automatically"
                unblocker = "healer"
            elif open_task_count > 0:
                stop_reason = "the current queue is exhausted and safe refill work is waiting to publish"
                next_action = "the healer is converting uncovered scope into the next scoped queue automatically"
                unblocker = "healer"
            elif uncovered_scope_count > 0:
                stop_reason = "the current queue is exhausted while uncovered scope remains"
                next_action = "the auditor is generating the next scoped queue from uncovered scope"
                unblocker = "auditor"
            elif display_uncovered_scope_count > 0:
                stop_reason = "the current queue is complete, but modeled design scope still remains outside the runtime queue"
                if queue_len <= 0 and project_cfg.get("queue_sources"):
                    next_action = "the auditor is refilling the queue from source-backed backlog evidence and modeled design scope"
                    unblocker = "auditor"
                else:
                    next_action = "materialize the remaining modeled design scope into runnable backlog before signoff"
                    unblocker = "design backlog materialization"
            elif queue_len <= 0 and project_cfg.get("queue_sources"):
                stop_reason = "the backlog source produced zero active items"
                next_action = "the auditor is refilling the queue from source-backed backlog evidence"
                unblocker = "auditor"
            elif group_signed_off:
                stop_reason = "the current queue is complete and the group is signed off"
                next_action = "no automatic follow-up is pending"
                unblocker = ""
            else:
                stop_reason = "the current queue is complete and the project is waiting for group or product signoff"
                next_action = "wait for the remaining group closure steps; the controller will sign off the group automatically when every member is runtime-complete"
                unblocker = "group signoff workflow"
        elif queue_len <= 0 and project_cfg.get("queue_sources"):
            stop_reason = "the backlog source produced zero active items"
            if approved_task_count > 0:
                next_action = "approved refill tasks are being published automatically"
                unblocker = "healer"
            elif open_task_count > 0:
                next_action = "the healer is reviewing source-backed refill proposals and will publish the safe queue automatically"
                unblocker = "healer"
            else:
                next_action = "the auditor is refilling the queue from source-backed backlog evidence"
                unblocker = "auditor"
        elif runtime_status == READY_STATUS:
            stop_reason = "configured queue has remaining work and is waiting for scheduler dispatch"
            next_action = "let the fleet dispatch the next slice automatically or run it now"
            unblocker = "scheduler"
    closure_owner = str(unblocker or ("worker" if active else "")).strip()
    if active:
        closure_state = "active"
    elif lifecycle_state == "signoff_only":
        closure_state = "closed"
    elif runtime_status in REVIEW_VISIBLE_STATUSES:
        closure_state = "review"
    elif needs_refill or runtime_status in {HEALING_STATUS, QUEUE_REFILLING_STATUS, SOURCE_BACKLOG_OPEN_STATUS, "blocked"}:
        closure_state = "healing"
    elif runtime_status in {CONFIGURED_QUEUE_COMPLETE_STATUS, SCAFFOLD_QUEUE_COMPLETE_STATUS, "complete"} and not group_signed_off:
        closure_state = "awaiting_signoff"
    elif group_signed_off or runtime_status == COMPLETED_SIGNED_OFF_STATUS:
        closure_state = "closed"
    elif runtime_status == READY_STATUS:
        closure_state = "dispatch_ready"
    else:
        closure_state = "open"
    return {
        "stop_reason": stop_reason,
        "queue_source_health": project_queue_source_health(project_cfg, queue_len),
        "backlog_source": project_backlog_source_summary(project_cfg),
        "next_action": next_action,
        "unblocker": unblocker,
        "closure_owner": closure_owner,
        "closure_state": closure_state,
        "needs_refill": needs_refill,
        "refill_ready": bool(approved_task_count > 0),
        "open_audit_task_count": int(open_task_count),
        "approved_audit_task_count": int(approved_task_count),
        "stopped_not_signed_off": bool(stop_reason and not active and not group_signed_off and lifecycle_state != "signoff_only"),
        "requires_operator_attention": bool((stop_reason or last_error) and unblocker == "operator"),
    }


def project_progress_label(project: Dict[str, Any]) -> str:
    queue_len = int(project.get("queue_len") or 0)
    queue_index = int(project.get("queue_index") or 0)
    if queue_len <= 0:
        return "0 / 0"
    if project.get("runtime_status") in {
        "complete",
        CONFIGURED_QUEUE_COMPLETE_STATUS,
        SCAFFOLD_QUEUE_COMPLETE_STATUS,
        COMPLETED_SIGNED_OFF_STATUS,
    }:
        return f"{queue_len} / {queue_len}"
    return f"{min(queue_index + 1, queue_len)} / {queue_len}"


def project_audit_task_counts(project_id: str) -> Dict[str, int]:
    if not table_exists("audit_task_candidates"):
        return {"open": 0, "approved": 0, "published": 0}
    with db() as conn:
        rows = conn.execute(
            """
            SELECT status, finding_key, COUNT(*) AS count
            FROM audit_task_candidates
            WHERE scope_type='project' AND scope_id=?
            GROUP BY status, finding_key
            """,
            (project_id,),
        ).fetchall()
    counts = {"open": 0, "approved": 0, "published": 0}
    for row in rows:
        status = str(row["status"] or "").strip().lower()
        if status == "open" and audit_finding_is_recommended(row["finding_key"]):
            counts["approved"] += int(row["count"] or 0)
            continue
        if status in counts:
            counts[status] += int(row["count"] or 0)
    return counts


def pull_request_rows() -> Dict[str, Dict[str, Any]]:
    if not table_exists("pull_requests"):
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM pull_requests ORDER BY project_id").fetchall()
    return {str(row["project_id"]): dict(row) for row in rows}


def normalized_pull_request_row(project_cfg: Dict[str, Any], pr_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    pr = dict(pr_row or {})
    review = project_review_policy(project_cfg)
    owner = str(review.get("owner") or pr.get("repo_owner") or "").strip()
    repo = str(review.get("repo") or pr.get("repo_name") or "").strip()
    review_mode = str(pr.get("review_mode") or review.get("mode") or "github").strip().lower()
    pr_number = int(pr.get("pr_number") or 0)
    if owner:
        pr["repo_owner"] = owner
    if repo:
        pr["repo_name"] = repo
    if owner and repo:
        repo_url = f"https://github.com/{owner}/{repo}"
        pr["repo_url"] = repo_url
        if review_mode == "github" and pr_number > 0:
            pr["pr_url"] = f"{repo_url}/pull/{pr_number}"
    pr["jury_feedback_history"] = list(json_field(pr.get("jury_feedback_history_json"), []))
    pr["issue_fingerprints"] = list(json_field(pr.get("issue_fingerprints_json"), []))
    pr["blocking_issue_count_by_round"] = list(json_field(pr.get("blocking_issue_count_by_round_json"), []))
    pr["repeat_issue_count_by_round"] = list(json_field(pr.get("repeat_issue_count_by_round_json"), []))
    pr["allowance_burn_by_lane"] = dict(json_field(pr.get("allowance_burn_by_lane_json"), {}))
    pr["last_review_feedback"] = dict(json_field(pr.get("last_review_feedback_json"), {}))
    pr["needs_core_rescue"] = bool(pr.get("needs_core_rescue"))
    pr["pass_without_core"] = bool(pr.get("pass_without_core"))
    return pr


def metadata_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def decode_review_focus(raw_focus: str) -> Tuple[str, Dict[str, str]]:
    focus_parts: List[str] = []
    metadata: Dict[str, str] = {}
    for part in str(raw_focus or "").split(REVIEW_METADATA_SEPARATOR):
        clean = str(part or "").strip()
        if not clean:
            continue
        if "=" in clean:
            key, value = clean.split("=", 1)
            if value.strip():
                metadata[key] = value.strip()
                continue
        focus_parts.append(clean)
    return REVIEW_METADATA_SEPARATOR.join(focus_parts).strip(), metadata


def review_focus_final_reviewer_lane(metadata: Dict[str, Any]) -> str:
    final_lane = str(metadata.get("final_reviewer_lane") or "").strip().lower()
    if final_lane:
        return final_lane
    if metadata_flag(metadata.get("jury_acceptance_required")):
        return "jury"
    return str(metadata.get("reviewer_lane") or metadata.get("required_reviewer_lane") or "core").strip().lower() or "core"


def review_loop_stage(pr_row: Optional[Dict[str, Any]]) -> Optional[str]:
    pr = dict(pr_row or {})
    if str(pr.get("workflow_kind") or "default").strip().lower() != WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
        return None
    review_status = str(pr.get("review_status") or "").strip().lower()
    if review_status in {
        AWAITING_FIRST_REVIEW_STATUS,
        REVIEW_LIGHT_PENDING_STATUS,
        JURY_REVIEW_PENDING_STATUS,
        JURY_REWORK_REQUIRED_STATUS,
        CORE_RESCUE_PENDING_STATUS,
        MANUAL_HOLD_STATUS,
        BLOCKED_CREDIT_BURN_DISABLED_STATUS,
        ACCEPTED_AFTER_CORE_STATUS,
        *ACCEPTED_AFTER_ROUND_STATUSES.values(),
    }:
        return review_status
    review_round = int(pr.get("review_round") or pr.get("local_review_attempts") or 0)
    first_review_complete = bool(pr.get("first_review_complete_at")) or review_round > 0
    _, metadata = decode_review_focus(str(pr.get("review_focus") or ""))
    reviewer_lane = str(metadata.get("reviewer_lane") or "").strip().lower()
    final_reviewer_lane = review_focus_final_reviewer_lane(metadata)
    jury_acceptance_required = metadata_flag(metadata.get("jury_acceptance_required"))
    if review_status == "local_review":
        if reviewer_lane and reviewer_lane == final_reviewer_lane and jury_acceptance_required:
            return JURY_REVIEW_PENDING_STATUS
        return AWAITING_FIRST_REVIEW_STATUS if not first_review_complete else REVIEW_LIGHT_PENDING_STATUS
    if review_status in {"review_fix_required", JURY_REWORK_REQUIRED_STATUS}:
        if bool(pr.get("needs_core_rescue")):
            return CORE_RESCUE_PENDING_STATUS
        return JURY_REWORK_REQUIRED_STATUS
    if review_status == "fallback_clean":
        accepted_on_round = str(pr.get("accepted_on_round") or "").strip().lower()
        if accepted_on_round == "core":
            return ACCEPTED_AFTER_CORE_STATUS
        if accepted_on_round in ACCEPTED_AFTER_ROUND_STATUSES:
            return ACCEPTED_AFTER_ROUND_STATUSES[accepted_on_round]
    return None


def project_workflow_stage(
    task_meta: Dict[str, Any],
    pr_row: Optional[Dict[str, Any]],
    runtime_status: Optional[str],
) -> Optional[str]:
    if str(task_meta.get("workflow_kind") or "default").strip().lower() != WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
        return None
    stage = review_loop_stage(pr_row)
    if stage:
        return stage
    status = str(runtime_status or "").strip().lower()
    if status in {READY_STATUS, "starting", "running", "verifying"}:
        if bool((pr_row or {}).get("needs_core_rescue")):
            return CORE_RESCUE_PENDING_STATUS
        return GROUNDWORK_PENDING_STATUS
    return None


def review_eta_payload(
    pr_row: Optional[Dict[str, Any]],
    *,
    cooldown_until: Optional[str] = None,
    now: Optional[dt.datetime] = None,
    config: Optional[Dict[str, Any]] = None,
    review_active: Optional[bool] = None,
) -> Dict[str, Any]:
    current = now or utc_now()
    pr = pr_row or {}
    review_status = str(pr.get("review_status") or "").strip().lower()
    review_mode = str(pr.get("review_mode") or "github").strip().lower()
    review_requested_at = parse_iso(str(pr.get("review_requested_at") or pr.get("updated_at") or ""))
    policies = ((config or normalize_config()).get("policies") or {})
    reset_at = parse_iso(str(pr.get("review_rate_limit_reset_at") or ""))
    fallback_wait_minutes = max(
        1,
        int(
            (
                policies.get("review_local_fallback_throttled_wait_minutes", 1)
                if reset_at and reset_at > current
                else policies.get("review_local_fallback_project_wait_minutes", 45)
            )
            or 1
        ),
    )
    fallback_at = review_requested_at + dt.timedelta(minutes=fallback_wait_minutes) if review_requested_at else None
    wake_at = parse_iso(str(pr.get("next_retry_at") or cooldown_until or ""))
    if review_status == "local_review":
        started_at = parse_iso(str(pr.get("local_review_last_at") or ""))
        local_review_running = bool(review_active) if review_active is not None else bool(pr.get("active_run_id") or pr.get("local_review_active"))
        if started_at and local_review_running:
            elapsed = human_duration((current - started_at).total_seconds())
            summary = "local review is running"
            if elapsed:
                summary += f" ({elapsed})"
        else:
            queued_at = parse_iso(str(pr.get("review_requested_at") or pr.get("updated_at") or ""))
            elapsed = human_duration((current - queued_at).total_seconds()) if queued_at else ""
            summary = "local review is queued"
            if elapsed:
                summary += f" ({elapsed})"
        return {
            "throttled": False,
            "reset_at": "",
            "reset_in": "",
            "wake_at": iso(wake_at) if wake_at else "",
            "wake_in": human_duration(max(0, int((wake_at - current).total_seconds()))) if wake_at else "",
            "summary": summary,
        }
    if review_status and review_status not in REVIEW_WAITING_STATUSES:
        return {"throttled": False, "reset_at": "", "reset_in": "", "wake_at": "", "wake_in": "", "summary": ""}
    if review_status in REVIEW_WAITING_STATUSES and review_mode != "github":
        summary = "local review is queued"
        if fallback_at:
            if fallback_at > current:
                fallback_seconds = max(0, int((fallback_at - current).total_seconds()))
                return {
                    "throttled": False,
                    "reset_at": "",
                    "reset_in": "",
                    "wake_at": iso(fallback_at),
                    "wake_in": human_duration(fallback_seconds),
                    "summary": f"{summary}; retry eligible at {iso(fallback_at)} ({human_duration(fallback_seconds)})",
                }
            return {
                "throttled": False,
                "reset_at": "",
                "reset_in": "",
                "wake_at": iso(fallback_at),
                "wake_in": "0s",
                "summary": f"{summary}; retry window is open",
            }
        return {
            "throttled": False,
            "reset_at": "",
            "reset_in": "",
            "wake_at": "",
            "wake_in": "",
            "summary": summary,
        }
    if reset_at and reset_at > current:
        reset_seconds = max(0, int((reset_at - current).total_seconds()))
        wake_seconds = max(0, int((wake_at - current).total_seconds())) if wake_at else None
        return {
            "throttled": True,
            "reset_at": iso(reset_at),
            "reset_in": human_duration(reset_seconds),
            "wake_at": iso(wake_at) if wake_at else "",
            "wake_in": human_duration(wake_seconds) if wake_seconds is not None else "",
            "summary": (
                f"GitHub review sync is throttled until {iso(reset_at)}"
                + (f" ({human_duration(reset_seconds)})" if reset_seconds > 0 else "")
                + (f"; spider wake-up check at {iso(wake_at)}" if wake_at else "")
            ),
        }
    if wake_at and wake_at <= current:
        return {
            "throttled": False,
            "reset_at": "",
            "reset_in": "",
            "wake_at": iso(wake_at),
            "wake_in": "0s",
            "summary": f"review sync is due now (scheduled wake-up was {iso(wake_at)})",
        }
    if wake_at:
        wake_seconds = max(0, int((wake_at - current).total_seconds()))
        return {
            "throttled": False,
            "reset_at": "",
            "reset_in": "",
            "wake_at": iso(wake_at),
            "wake_in": human_duration(wake_seconds),
            "summary": f"next review sync attempt at {iso(wake_at)}",
        }
    if review_status in REVIEW_WAITING_STATUSES:
        summary = "awaiting GitHub review; next sync pass within 30s"
        wake_in = ""
        wake_at_text = ""
        if fallback_at:
            if fallback_at > current:
                fallback_seconds = max(0, int((fallback_at - current).total_seconds()))
                wake_at_text = iso(fallback_at)
                wake_in = human_duration(fallback_seconds)
                summary += f"; local fallback eligible at {wake_at_text} ({wake_in})"
            else:
                wake_at_text = iso(fallback_at)
                wake_in = "0s"
                summary += "; local fallback eligibility window is open"
        return {
            "throttled": False,
            "reset_at": "",
            "reset_in": "",
            "wake_at": wake_at_text,
            "wake_in": wake_in,
            "summary": summary,
        }
    return {"throttled": False, "reset_at": "", "reset_in": "", "wake_at": "", "wake_in": "", "summary": ""}


def review_findings_summary() -> Dict[str, Dict[str, int]]:
    if not table_exists("review_findings"):
        return {}
    with db() as conn:
        rows = conn.execute(
            """
            SELECT project_id, COUNT(*) AS count, COALESCE(SUM(CASE WHEN blocking THEN 1 ELSE 0 END), 0) AS blocking_count
            FROM review_findings
            GROUP BY project_id
            """
        ).fetchall()
    return {
        str(row["project_id"]): {
            "count": int(row["count"] or 0),
            "blocking_count": int(row["blocking_count"] or 0),
        }
        for row in rows
    }


def review_findings(limit: int = 100) -> List[Dict[str, Any]]:
    if not table_exists("review_findings"):
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM review_findings
            ORDER BY CASE severity WHEN 'blocking' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                     updated_at DESC,
                     project_id,
                     pr_number
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def incidents(
    *,
    status: str = "open",
    limit: int = 200,
    scope_type: Optional[str] = None,
    scope_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not table_exists("incidents"):
        return []
    clauses = ["status=?"]
    params: List[Any] = [status]
    if scope_type:
        clauses.append("scope_type=?")
        params.append(scope_type)
    if scope_ids:
        clean_ids = [str(item).strip() for item in scope_ids if str(item).strip()]
        if clean_ids:
            placeholders = ", ".join("?" for _ in clean_ids)
            clauses.append(f"scope_id IN ({placeholders})")
            params.extend(clean_ids)
    where = " AND ".join(clauses)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM incidents
            WHERE {where}
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                     updated_at DESC,
                     scope_type,
                     scope_id
            LIMIT ?
            """,
            (*params, int(limit)),
        ).fetchall()
    items = [dict(row) for row in rows]
    for item in items:
        context = json_field(item.get("context_json"), {})
        item["context"] = context if isinstance(context, dict) else {}
    return items


def incident_requires_operator_attention(item: Dict[str, Any]) -> bool:
    context = item.get("context") if isinstance(item.get("context"), dict) else json_field(item.get("context_json"), {})
    incident_kind = str(item.get("incident_kind") or "").strip()
    severity = str(item.get("severity") or "").strip().lower()
    always_visible = {
        BLOCKED_UNRESOLVED_INCIDENT_KIND,
        REVIEW_FAILED_INCIDENT_KIND,
        REVIEW_STALLED_INCIDENT_KIND,
        PR_CHECKS_FAILED_INCIDENT_KIND,
    }
    if severity == "critical" or incident_kind in always_visible:
        return True
    if isinstance(context, dict):
        if "operator_required" in context:
            return bool(context.get("operator_required"))
        if "can_resolve" in context:
            return not bool(context.get("can_resolve"))
    return False


def incident_auto_heal_category(item: Dict[str, Any]) -> Optional[str]:
    incident_kind = str(item.get("incident_kind") or "").strip().lower()
    if incident_kind in {REVIEW_FAILED_INCIDENT_KIND, REVIEW_STALLED_INCIDENT_KIND, PR_CHECKS_FAILED_INCIDENT_KIND}:
        return "review"
    if incident_kind == BLOCKED_UNRESOLVED_INCIDENT_KIND:
        return "capacity"
    return None


def incident_context_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    context = item.get("context") if isinstance(item.get("context"), dict) else json_field(item.get("context_json"), {})
    return context if isinstance(context, dict) else {}


def incident_target_project_id(item: Dict[str, Any]) -> str:
    scope_type = str(item.get("scope_type") or "").strip()
    scope_id = str(item.get("scope_id") or "").strip()
    if scope_type == "project":
        return scope_id
    context = incident_context_payload(item)
    return str(context.get("project_id") or "").strip() if isinstance(context, dict) else ""


def incident_applies_to_projects(item: Dict[str, Any], projects_by_id: Dict[str, Dict[str, Any]]) -> bool:
    incident_kind = str(item.get("incident_kind") or "").strip()
    if incident_kind != BLOCKED_UNRESOLVED_INCIDENT_KIND:
        return True
    project_id = incident_target_project_id(item)
    if not project_id:
        return True
    project = projects_by_id.get(project_id)
    if not project:
        return True
    runtime_status = str(
        project.get("runtime_status_internal")
        or project.get("runtime_status")
        or project.get("status_internal")
        or project.get("status")
        or ""
    ).strip().lower()
    return runtime_status == "blocked"


def filter_runtime_relevant_incidents(rows: List[Dict[str, Any]], projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    projects_by_id = {str(project.get("id") or "").strip(): project for project in projects if str(project.get("id") or "").strip()}
    return [item for item in rows if incident_applies_to_projects(item, projects_by_id)]


def incident_row(incident_id: int) -> sqlite3.Row:
    if not table_exists("incidents"):
        raise HTTPException(404, "incidents table not available")
    with db() as conn:
        row = conn.execute("SELECT * FROM incidents WHERE id=?", (int(incident_id),)).fetchone()
    if not row:
        raise HTTPException(404, "incident not found")
    return row


def update_incident_record(
    incident_id: int,
    *,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    resolved: bool = False,
) -> None:
    if not table_exists("incidents"):
        raise HTTPException(404, "incidents table not available")
    row = incident_row(incident_id)
    next_status = str(status or row["status"] or "open")
    next_severity = str(severity or row["severity"] or "medium")
    next_context = context if context is not None else incident_context_payload(dict(row))
    now_text = iso(utc_now()) or ""
    resolved_at = now_text if resolved else None
    with db() as conn:
        conn.execute(
            """
            UPDATE incidents
            SET status=?, severity=?, context_json=?, updated_at=?, resolved_at=?
            WHERE id=?
            """,
            (next_status, next_severity, json.dumps(next_context or {}, sort_keys=True), now_text, resolved_at, int(incident_id)),
        )


def public_project_status(
    runtime_status: str,
    *,
    lifecycle: Optional[str] = None,
    cooldown_until: Optional[str],
    needs_refill: bool,
    open_task_count: int = 0,
    approved_task_count: int = 0,
    group_signed_off: bool = False,
) -> str:
    status = str(runtime_status or "").strip() or READY_STATUS
    lifecycle_state = normalize_lifecycle_state(lifecycle, "dispatchable")
    if status == READY_STATUS:
        return READY_STATUS
    if status == "awaiting_account":
        return WAITING_CAPACITY_STATUS
    if status == "review_fix_required":
        return REVIEW_FIX_STATUS
    if status == "review_failed":
        return HEALING_STATUS
    if status in {"awaiting_pr", "review_requested"}:
        return status
    if status == "blocked" and (approved_task_count > 0 or open_task_count > 0):
        return HEALING_STATUS
    if status in {"complete", SOURCE_BACKLOG_OPEN_STATUS} and needs_refill:
        if approved_task_count > 0:
            return QUEUE_REFILLING_STATUS
        if open_task_count > 0:
            return HEALING_STATUS
        return HEALING_STATUS
    if status == "complete":
        if lifecycle_state == "signoff_only":
            return "signoff_only"
        return queue_complete_public_status(lifecycle=lifecycle, group_signed_off=group_signed_off)
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
    signed_off_at = parse_iso(meta.get("signed_off_at"))
    reopened_at = parse_iso(meta.get("reopened_at"))
    if reopened_at and (signed_off_at is None or reopened_at >= signed_off_at):
        return False
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


def group_audit_request_pending(meta: Dict[str, Any], *, now: Optional[dt.datetime] = None) -> bool:
    last_audit_requested_at = parse_iso(meta.get("last_audit_requested_at"))
    if last_audit_requested_at is None:
        return False
    last_refill_requested_at = parse_iso(meta.get("last_refill_requested_at"))
    if last_refill_requested_at and last_refill_requested_at > last_audit_requested_at:
        return False
    current_now = now or utc_now()
    return last_audit_requested_at >= current_now - dt.timedelta(seconds=AUDIT_REQUEST_PENDING_SECONDS)


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


DESIGN_PROGRESS_WINDOW_DAYS = 14
DESIGN_ETA_MILESTONE_FLOOR_DAYS = 2.0
DESIGN_ETA_SCOPE_FLOOR_DAYS = 1.5
DESIGN_ETA_COVERAGE_TAX_DAYS = 7.0
DESIGN_ETA_BLOCKED_TAX_DAYS = 3.0
DESIGN_ETA_MATERIALIZATION_MULTIPLIER_CAP = 2.5


def positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def design_scope_default_weight(meta: Dict[str, Any]) -> int:
    return positive_int(meta.get("design_scope_default_weight"), 3)


def milestone_weight(item: Dict[str, Any], default_weight: int = 5) -> int:
    return positive_int(item.get("weight"), default_weight)


def throughput_finished_runs(project_ids: List[str], since: dt.datetime) -> int:
    clean_ids = [str(project_id).strip() for project_id in project_ids if str(project_id).strip()]
    if not clean_ids:
        return 0
    placeholders = ", ".join("?" for _ in clean_ids)
    query = f"""
        SELECT COUNT(*) AS count
        FROM runs
        WHERE project_id IN ({placeholders})
          AND finished_at IS NOT NULL
          AND finished_at >= ?
          AND job_kind IN ('coding', 'healing', 'local_review')
          AND COALESCE(status, '') NOT IN ('failed', 'error', 'cancelled', 'canceled')
    """
    with db() as conn:
        row = conn.execute(query, (*clean_ids, iso(since))).fetchone()
    return int((row["count"] if row else 0) or 0)


def progress_percentages(
    *,
    total_weight: int,
    complete_weight: int,
    inflight_weight: int,
    blocked_weight: int,
    unmaterialized_weight: int,
) -> Dict[str, int]:
    total = max(1, int(total_weight or 0))
    weights = {
        "complete": max(0, int(complete_weight or 0)),
        "inflight": max(0, int(inflight_weight or 0)),
        "blocked": max(0, int(blocked_weight or 0)),
        "unmaterialized": max(0, int(unmaterialized_weight or 0)),
    }
    percents = {key: int(round((value / total) * 100.0)) for key, value in weights.items()}
    diff = 100 - sum(percents.values())
    percents["complete"] = max(0, percents["complete"] + diff)
    return {
        "percent_complete": percents["complete"],
        "percent_inflight": percents["inflight"],
        "percent_blocked": percents["blocked"],
        "percent_unmaterialized": percents["unmaterialized"],
    }


def build_design_eta_payload(
    *,
    meta: Dict[str, Any],
    now: dt.datetime,
    remaining_weight: int,
    project_ids: List[str],
    active_workers: int,
    uncovered_scope_count: int,
    blocked_weight: int,
) -> Dict[str, Any]:
    milestones = remaining_milestone_items(meta)
    remaining_count = len(milestones)
    result: Dict[str, Any] = {
        "estimated_remaining_seconds": None,
        "eta_at": None,
        "eta_human": "unknown",
        "eta_basis": "",
        "eta_unavailable_reason": "",
        "confidence": "low",
        "confidence_reason": "",
        "coverage_status": "registry_missing",
        "progress_basis": "weighted_milestones_plus_scope",
        "bottleneck": "",
        "eta_mode": "unknown",
    }
    if not meta:
        result["eta_basis"] = "no design coverage registry configured"
        result["eta_unavailable_reason"] = "no_design_registry"
        result["confidence_reason"] = "no design registry exists yet"
        return result
    coverage_complete = bool(meta.get("milestone_coverage_complete")) and bool(meta.get("design_coverage_complete"))
    result["coverage_status"] = "complete" if coverage_complete else "coverage_incomplete"
    if remaining_weight <= 0:
        result.update(
            {
                "estimated_remaining_seconds": 0,
                "eta_at": iso(now),
                "eta_human": "0s",
                "eta_basis": "weighted design milestones and uncovered scope are complete",
                "confidence": "high" if bool(meta.get("design_coverage_complete")) and coverage_complete else "low",
                "confidence_reason": (
                    "all tracked design weight is complete"
                    if coverage_complete
                    else "work appears complete, but milestone/design coverage is still incomplete"
                ),
                "bottleneck": "",
                "eta_mode": "exact",
            }
        )
        return result
    since = now - dt.timedelta(days=DESIGN_PROGRESS_WINDOW_DAYS)
    finished_runs = throughput_finished_runs(project_ids, since)
    velocity_per_day = (finished_runs / float(DESIGN_PROGRESS_WINDOW_DAYS)) + (max(0, int(active_workers or 0)) * 0.40)
    if velocity_per_day <= 0:
        result["eta_basis"] = "remaining weighted design scope exists, but no trailing delivery velocity is available yet"
        result["eta_unavailable_reason"] = "design_velocity_missing"
        result["confidence"] = "low"
        result["confidence_reason"] = (
            "coverage is incomplete and no delivery velocity exists yet"
            if uncovered_scope_count > 0 or not coverage_complete
            else "no trailing delivery velocity exists yet"
        )
        result["bottleneck"] = "coverage_materialization" if uncovered_scope_count > 0 else ("blocked_execution" if blocked_weight > 0 else "delivery_velocity")
        return result
    conservative_mode = (not coverage_complete) or uncovered_scope_count > 0 or blocked_weight > 0
    remaining_days = remaining_weight / velocity_per_day
    if conservative_mode:
        materialization_ratio = float(uncovered_scope_count) / float(max(1, remaining_count))
        materialization_multiplier = 1.0 + min(
            DESIGN_ETA_MATERIALIZATION_MULTIPLIER_CAP - 1.0,
            (materialization_ratio * 0.75) + (0.35 if not coverage_complete else 0.0),
        )
        milestone_floor_days = float(remaining_count) * DESIGN_ETA_MILESTONE_FLOOR_DAYS
        scope_floor_days = float(uncovered_scope_count) * DESIGN_ETA_SCOPE_FLOOR_DAYS
        coverage_tax_days = DESIGN_ETA_COVERAGE_TAX_DAYS if not coverage_complete else 0.0
        blocked_tax_days = DESIGN_ETA_BLOCKED_TAX_DAYS if blocked_weight > 0 else 0.0
        remaining_days = max(
            remaining_days * materialization_multiplier,
            milestone_floor_days + scope_floor_days + coverage_tax_days + blocked_tax_days,
        )
    remaining_seconds = max(0, int(round(remaining_days * 86400)))
    eta_at = now + dt.timedelta(seconds=remaining_seconds)
    confidence = "low"
    if coverage_complete and finished_runs >= 8 and uncovered_scope_count <= 2 and blocked_weight == 0:
        confidence = "high"
    elif coverage_complete and (finished_runs >= 4 or active_workers > 0):
        confidence = "medium"
    confidence_reason = "coverage is incomplete, so ETA stays conservative"
    if coverage_complete and confidence == "high":
        confidence_reason = "coverage is complete and recent throughput is strong"
    elif coverage_complete and confidence == "medium":
        confidence_reason = "coverage is complete, but recent throughput is only moderately stable"
    elif blocked_weight > 0:
        confidence_reason = "blocked work remains, so confidence stays low"
    elif uncovered_scope_count > 0:
        confidence_reason = "unmaterialized scope still remains outside the runnable backlog"
    eta_human = human_duration(remaining_seconds) or "0s"
    eta_basis = f"remaining_weight / trailing_{DESIGN_PROGRESS_WINDOW_DAYS}d_velocity"
    eta_mode = "exact"
    if conservative_mode:
        eta_human = f">= {eta_human}"
        eta_basis = (
            f"conservative lower bound from weighted design scope, {remaining_count} open milestone"
            f"{'s' if remaining_count != 1 else ''}, and uncovered-scope materialization"
        )
        eta_mode = "conservative_lower_bound"
    result.update(
        {
            "estimated_remaining_seconds": remaining_seconds,
            "eta_at": iso(eta_at),
            "eta_human": eta_human,
            "eta_basis": eta_basis,
            "eta_unavailable_reason": "",
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "coverage_status": "complete" if coverage_complete else "coverage_incomplete",
            "progress_basis": "weighted_milestones_plus_scope",
            "bottleneck": "coverage_materialization" if uncovered_scope_count > 0 else ("blocked_execution" if blocked_weight > 0 else "delivery_velocity"),
            "eta_mode": eta_mode,
        }
    )
    return result


def design_progress_payload(
    *,
    meta: Dict[str, Any],
    runtime_status: str,
    uncovered_scope_count: int,
    project_ids: List[str],
    active_workers: int,
    now: dt.datetime,
) -> Dict[str, Any]:
    if not meta:
        eta = build_design_eta_payload(
            meta=meta,
            now=now,
            remaining_weight=0,
            project_ids=project_ids,
            active_workers=active_workers,
            uncovered_scope_count=uncovered_scope_count,
            blocked_weight=0,
        )
        return {
            "percent_complete": 0,
            "percent_inflight": 0,
            "percent_blocked": 0,
            "percent_unmaterialized": 100,
            "eta_human": eta.get("eta_human") or "unknown",
            "eta_confidence": eta.get("confidence") or "low",
            "eta_confidence_reason": eta.get("confidence_reason") or "design registry missing",
            "coverage_status": eta.get("coverage_status") or "registry_missing",
            "progress_basis": eta.get("progress_basis") or "weighted_milestones_plus_scope",
            "eta_basis": eta.get("eta_basis") or "",
            "eta_at": eta.get("eta_at"),
            "basis": "weighted_milestones_plus_scope",
            "summary": "design registry missing",
            "main_blocker": "design registry missing",
            "remaining_weight": 0,
            "total_weight": 0,
            "open_milestones": 0,
            "uncovered_scope_count": uncovered_scope_count,
            "active_workers": int(active_workers or 0),
            "bottleneck": "design_registry",
            "eta": eta,
        }
    milestones = remaining_milestone_items(meta)
    default_scope_weight = design_scope_default_weight(meta)
    milestone_open_weight = sum(milestone_weight(item) for item in milestones if str(item.get("status") or "open").strip().lower() not in {"done", "complete", "closed"})
    coverage_complete = bool(meta.get("milestone_coverage_complete")) and bool(meta.get("design_coverage_complete"))
    scope_weight = uncovered_scope_count * default_scope_weight
    if not coverage_complete and milestone_open_weight <= 0 and uncovered_scope_count <= 0:
        uncovered_scope_count = 1
        scope_weight = default_scope_weight
    total_weight = max(
        positive_int(meta.get("design_total_weight"), milestone_open_weight + scope_weight or 1),
        milestone_open_weight + scope_weight,
    )
    blocked_state = runtime_status in {"blocked", "review_failed", "group_blocked"}
    blocked_weight = milestone_open_weight if blocked_state else sum(
        milestone_weight(item)
        for item in milestones
        if str(item.get("status") or "open").strip().lower() == "blocked"
    )
    inflight_weight = max(0, milestone_open_weight - blocked_weight)
    tracked_remaining = inflight_weight + blocked_weight + scope_weight
    complete_weight = max(0, total_weight - tracked_remaining)
    percentages = progress_percentages(
        total_weight=total_weight,
        complete_weight=complete_weight,
        inflight_weight=inflight_weight,
        blocked_weight=blocked_weight,
        unmaterialized_weight=scope_weight,
    )
    eta = build_design_eta_payload(
        meta=meta,
        now=now,
        remaining_weight=tracked_remaining,
        project_ids=project_ids,
        active_workers=active_workers,
        uncovered_scope_count=uncovered_scope_count,
        blocked_weight=blocked_weight,
    )
    remaining_count = len(milestones)
    summary_parts: List[str] = []
    if remaining_count:
        summary_parts.append(f"{remaining_count} milestone{'s' if remaining_count != 1 else ''} open")
    if uncovered_scope_count:
        summary_parts.append("uncovered scope still being materialized")
    elif not coverage_complete:
        summary_parts.append("coverage registry is still incomplete")
    elif blocked_weight:
        summary_parts.append("blocked design work remains")
    elif not remaining_count:
        summary_parts.append("design responsibilities are fully mapped and complete")
    main_blocker = ""
    if uncovered_scope_count:
        main_blocker = "coverage materialization"
    elif not coverage_complete:
        main_blocker = "coverage registry incomplete"
    elif blocked_weight:
        main_blocker = "blocked execution"
    elif milestones:
        first = milestones[0]
        main_blocker = str(first.get("id") or first.get("title") or "").strip()
    return {
        **percentages,
        "eta_human": eta.get("eta_human") or "unknown",
        "eta_confidence": eta.get("confidence") or "low",
        "eta_confidence_reason": eta.get("confidence_reason") or "",
        "coverage_status": eta.get("coverage_status") or ("complete" if coverage_complete else "coverage_incomplete"),
        "progress_basis": eta.get("progress_basis") or "weighted_milestones_plus_scope",
        "eta_basis": eta.get("eta_basis") or "",
        "eta_at": eta.get("eta_at"),
        "basis": "weighted_milestones_plus_scope",
        "summary": "; ".join(summary_parts),
        "main_blocker": main_blocker,
        "remaining_weight": tracked_remaining,
        "total_weight": total_weight,
        "open_milestones": remaining_count,
        "uncovered_scope_count": uncovered_scope_count,
        "active_workers": int(active_workers or 0),
        "bottleneck": eta.get("bottleneck") or main_blocker,
        "eta": eta,
    }


def delivery_progress_units_for_project(project: Dict[str, Any]) -> Tuple[int, int, int, int]:
    queue_len = int(project.get("queue_len") or 0)
    runtime_status = project_runtime_status(project).lower()
    public_status = project_public_runtime_status(project)
    inflight_statuses = {
        "starting",
        "running",
        "verifying",
        "review_requested",
        "review_fix_required",
        "healing",
        "queue_refilling",
        "awaiting_account",
        WAITING_CAPACITY_STATUS,
        READY_STATUS,
    }
    complete_statuses = {
        "complete",
        CONFIGURED_QUEUE_COMPLETE_STATUS,
        SCAFFOLD_QUEUE_COMPLETE_STATUS,
        COMPLETED_SIGNED_OFF_STATUS,
    }
    if queue_len <= 0:
        if public_status in {"blocked", "review_failed"}:
            return (1, 0, 0, 1)
        if bool(project.get("needs_refill")) or public_status in inflight_statuses or runtime_status in inflight_statuses:
            return (1, 0, 1, 0)
        if project_effectively_complete(project) or public_status in complete_statuses:
            return (1, 1, 0, 0)
        return (1, 0, 0, 0)
    queue_index = max(0, min(int(project.get("queue_index") or 0), queue_len))
    complete_units = queue_len if project_effectively_complete(project) else min(queue_index, queue_len)
    tail_not_complete = bool(queue_len > 0 and complete_units >= queue_len and not project_effectively_complete(project))
    if tail_not_complete and runtime_status in {"blocked", "review_failed"}:
        complete_units = max(0, queue_len - 1)
    elif tail_not_complete and (runtime_status in inflight_statuses or public_status in inflight_statuses):
        complete_units = max(0, queue_len - 1)
    blocked_units = 1 if runtime_status in {"blocked", "review_failed"} and complete_units < queue_len else 0
    inflight_units = 1 if (runtime_status in inflight_statuses or public_status in inflight_statuses) and complete_units < queue_len and blocked_units == 0 else 0
    return (max(1, queue_len), complete_units, inflight_units, blocked_units)


def delivery_progress_payload_for_project(project: Dict[str, Any]) -> Dict[str, int]:
    total, complete_units, inflight_units, blocked_units = delivery_progress_units_for_project(project)
    unstarted_units = max(0, total - complete_units - inflight_units - blocked_units)
    percents = progress_percentages(
        total_weight=total,
        complete_weight=complete_units,
        inflight_weight=inflight_units,
        blocked_weight=blocked_units,
        unmaterialized_weight=unstarted_units,
    )
    return {
        "percent_complete": percents["percent_complete"],
        "percent_inflight": percents["percent_inflight"],
        "percent_blocked": percents["percent_blocked"],
        "percent_unstarted": percents["percent_unmaterialized"],
    }


def delivery_progress_payload_for_group(group_projects: List[Dict[str, Any]]) -> Dict[str, int]:
    total_units = 0
    complete_units = 0
    inflight_units = 0
    blocked_units = 0
    for project in group_projects:
        total, complete, inflight, blocked = delivery_progress_units_for_project(project)
        total_units += total
        complete_units += complete
        inflight_units += inflight
        blocked_units += blocked
    unstarted_units = max(0, total_units - complete_units - inflight_units - blocked_units)
    percents = progress_percentages(
        total_weight=max(1, total_units),
        complete_weight=complete_units,
        inflight_weight=inflight_units,
        blocked_weight=blocked_units,
        unmaterialized_weight=unstarted_units,
    )
    return {
        "percent_complete": percents["percent_complete"],
        "percent_inflight": percents["percent_inflight"],
        "percent_blocked": percents["percent_blocked"],
        "percent_unstarted": percents["percent_unmaterialized"],
    }


def project_runtime_status(project: Dict[str, Any]) -> str:
    return str(
        project.get("status_internal")
        or project.get("runtime_status_internal")
        or project.get("status")
        or project.get("runtime_status")
        or ""
    ).strip() or READY_STATUS


def project_effectively_complete(project: Dict[str, Any]) -> bool:
    public_status = str(project.get("runtime_status") or project.get("status") or "").strip().lower()
    internal_status = project_runtime_status(project)
    if bool(project.get("group_signed_off")):
        return True
    if public_status in {
        "complete",
        COMPLETED_SIGNED_OFF_STATUS,
        CONFIGURED_QUEUE_COMPLETE_STATUS,
        SCAFFOLD_QUEUE_COMPLETE_STATUS,
    }:
        return True
    return internal_status == "complete" and not bool(project.get("needs_refill"))


def project_queue_length(project: Dict[str, Any]) -> int:
    queue = project.get("queue")
    if isinstance(queue, list):
        return len(queue)
    return int(project.get("queue_len") or 0)


def project_has_live_worker(project: Dict[str, Any]) -> bool:
    active_run_id = str(project.get("active_run_id") or "").strip()
    if active_run_id not in {"", "0"}:
        return True
    return project_runtime_status(project).lower() in {"starting", "running", "verifying"}


def runtime_status_for_active_run(base_status: str, run_row: Dict[str, Any]) -> str:
    run_status = str(run_row.get("status") or "").strip().lower()
    if run_status not in {"starting", "running", "verifying"}:
        return base_status
    job_kind = str(run_row.get("job_kind") or "coding").strip().lower()
    if job_kind in {"local_review", "github_review"}:
        return "review_requested"
    return run_status


def normalize_slice_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        clean = value.strip()
        if clean[:1] in "{[" and clean[-1:] in "}]":
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(clean)
                except Exception:
                    continue
                normalized = normalize_slice_text(parsed)
                if normalized:
                    return normalized
        return clean
    if isinstance(value, dict):
        parts: List[str] = []
        for key, item in value.items():
            clean_item = normalize_slice_text(item)
            clean_key = str(key or "").strip()
            if not clean_item:
                continue
            parts.append(f"{clean_key}: {clean_item}" if clean_key else clean_item)
        if parts:
            return " | ".join(parts[:3]).strip()
    if isinstance(value, (list, tuple, set)):
        parts = [normalize_slice_text(item) for item in value]
        parts = [item for item in parts if item]
        if parts:
            return " | ".join(parts[:3]).strip()
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True).strip()
    except TypeError:
        return str(value).strip()


def current_queue_item_text(project: Dict[str, Any]) -> str:
    queue = project.get("queue")
    if isinstance(queue, list):
        queue_index = int(project.get("queue_index") or 0)
        if 0 <= queue_index < len(queue):
            return normalize_slice_text(queue[queue_index])
    return normalize_slice_text(project.get("current_queue_item") or project.get("current_slice") or project.get("slice_name") or "")


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
    incident_rows = group.get("incidents")
    if incident_rows is None:
        incident_rows = group_open_incidents(group, group_projects)
    incident_rows = [item for item in (incident_rows or []) if incident_requires_operator_attention(item)]
    if incident_rows:
        top = incident_rows[0]
        blockers.append(
            f"incident: {short_question_detail(top.get('title') or top.get('summary') or 'operator attention required', limit=140)}"
        )
    participant_projects = [project for project in group_projects if project_dispatch_participates(project)]
    contract_blockers = text_items(meta.get("contract_blockers"))
    contract_phase_allowed = bool(contract_blockers) and bool(participant_projects) and all(
        is_contract_remediation_slice(current_queue_item_text(project))
        and (
            int(project.get("queue_index") or 0) < project_queue_length(project)
            or bool(current_queue_item_text(project))
        )
        for project in participant_projects
    )
    if contract_blockers and not contract_phase_allowed:
        blockers.extend(f"contract blocker: {item}" for item in contract_blockers)

    mode = str(group.get("mode", "") or "independent").strip().lower()
    if mode == "lockstep":
        for project in participant_projects:
            project_id = str(project.get("id") or "unknown")
            status = project_runtime_status(project)
            queue_len = project_queue_length(project)
            queue_index = int(project.get("queue_index") or 0)
            cooldown_until = parse_iso(project.get("cooldown_until"))
            pending_slice = current_queue_item_text(project)
            if status in {
                "complete",
                CONFIGURED_QUEUE_COMPLETE_STATUS,
                SCAFFOLD_QUEUE_COMPLETE_STATUS,
                COMPLETED_SIGNED_OFF_STATUS,
            } or bool(project.get("group_signed_off")):
                continue
            if not bool(project.get("enabled", True)):
                blockers.append(f"{project_id}: project disabled")
            elif status in {"starting", "running", "verifying"} and not contract_phase_allowed:
                blockers.append(f"{project_id}: run already in progress")
            elif cooldown_until and cooldown_until > now:
                blockers.append(f"{project_id}: cooldown active")
            elif status == "awaiting_account":
                blockers.append(f"{project_id}: awaiting eligible account")
            elif status in REVIEW_HOLD_STATUSES:
                blockers.append(f"{project_id}: waiting on review lane")
            elif status == "review_failed":
                blockers.append(f"{project_id}: review orchestration failed")
            elif status == "blocked":
                blockers.append(f"{project_id}: blocked after repeated failures")
            elif queue_index >= queue_len and not pending_slice:
                if status == SOURCE_BACKLOG_OPEN_STATUS:
                    blockers.append(f"{project_id}: runtime queue exhausted while source backlog remains open")
                else:
                    blockers.append(f"{project_id}: runtime queue exhausted")

    ready = not blockers
    if ready:
        basis = "group dispatch is allowed"
        if mode == "lockstep":
            basis = "lockstep group is eligible to dispatch all member projects together"
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
    audit_requested = group_audit_request_pending(meta)
    actionable_group_uncovered_scope = group_actionable_uncovered_scope(
        str(group.get("id") or ""),
        text_items(meta.get("uncovered_scope")),
        group_projects,
    )
    operational_projects = [
        project
        for project in group_projects
        if normalize_lifecycle_state(project.get("lifecycle"), "dispatchable") != "signoff_only"
    ]
    dispatch_projects = [project for project in group_projects if project_dispatch_participates(project)]
    completion_projects = dispatch_projects or group_projects
    mode = str(group.get("mode", "") or "independent").strip().lower()
    active_statuses = {"starting", "running", "verifying", "healing", "queue_refilling", "review_fix_required", "review_requested"}
    has_active_worker = any(
        str(project.get("active_run_id") or "").strip() not in {"", "0"}
        and str(project.get("status") or project.get("runtime_status") or project_runtime_status(project)).strip().lower() in active_statuses
        for project in group_projects
    )
    if group_is_signed_off(meta):
        return "product_signed_off"
    dispatch = group_dispatch_state(group, meta, group_projects, utc_now())
    milestone_items = remaining_milestone_items(meta)
    if text_items(meta.get("contract_blockers")):
        return "contract_blocked"
    incident_rows = group.get("incidents")
    if incident_rows is None:
        incident_rows = group_open_incidents(group, group_projects)
    if any(incident_requires_operator_attention(item) for item in (incident_rows or [])):
        return "group_blocked"
    if has_active_worker:
        return "lockstep_active" if mode == "lockstep" else "active"
    if any(int(project.get("approved_audit_task_count") or 0) > 0 or int(project.get("open_audit_task_count") or 0) > 0 for project in operational_projects):
        return "proposed_tasks"
    if any(bool(project.get("needs_refill")) for project in operational_projects):
        return "audit_requested" if audit_requested else "audit_required"
    if actionable_group_uncovered_scope:
        return "audit_requested" if audit_requested else "audit_required"
    if completion_projects and all(project_effectively_complete(project) for project in completion_projects):
        return CONFIGURED_QUEUE_COMPLETE_STATUS
    if milestone_items:
        if mode == "lockstep" and not dispatch.get("dispatch_ready"):
            return "group_blocked"
        return "milestone_backlog_open"
    if not bool(meta.get("milestone_coverage_complete")) or not bool(meta.get("design_coverage_complete")):
        return "audit_requested" if audit_requested else "audit_required"
    return "audit_requested" if audit_requested else "audit_required"


def derive_group_phase(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> str:
    status = str(group.get("status") or "").strip().lower()
    if status == "product_signed_off":
        return "signed_off"
    if status in {"complete", CONFIGURED_QUEUE_COMPLETE_STATUS}:
        return "complete"
    if status in {"contract_blocked", "group_blocked"}:
        return "blocked"
    if status == "proposed_tasks":
        return "proposed_tasks"
    if status == "audit_requested":
        return "audit_requested"
    if status == "audit_required":
        return "audit_required"
    active_statuses = {"running", "starting", "verifying"}
    if any(project_runtime_status(project) in active_statuses for project in group_projects):
        return "running"
    if bool(group.get("dispatch_ready")):
        return WAITING_CAPACITY_STATUS
    return HEALING_STATUS


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
    signoff_only_projects = {
        str(project.get("id") or "").strip()
        for project in (normalize_config().get("projects") or [])
        if normalize_lifecycle_state(project.get("lifecycle"), "dispatchable") == "signoff_only"
    }
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
        if str(item.get("scope_type") or "") == "project" and str(item.get("scope_id") or "") in signoff_only_projects:
            continue
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


def default_bootstrap_verify_script() -> str:
    return textwrap.dedent(
        r"""
        #!/usr/bin/env bash
        set -euo pipefail

        ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
        cd "$ROOT_DIR"

        ran_any=0

        note() {
          printf '==> %s\n' "$1"
        }

        have() {
          command -v "$1" >/dev/null 2>&1
        }

        mark_ran() {
          ran_any=1
        }

        has_package_script() {
          [ -f package.json ] && grep -q "\"$1\"[[:space:]]*:" package.json
        }

        run_node_script() {
          script="$1"
          package_manager="$2"
          case "$package_manager" in
            npm)
              if ! has_package_script "$script"; then
                return
              fi
              if [ "$script" = "test" ]; then
                note "npm test --if-present"
                npm test --if-present
              else
                note "npm run $script --if-present"
                npm run "$script" --if-present
              fi
              mark_ran
              ;;
            pnpm)
              if ! has_package_script "$script"; then
                return
              fi
              if [ "$script" = "test" ]; then
                note "pnpm test"
                pnpm test
              else
                note "pnpm run $script"
                pnpm run "$script"
              fi
              mark_ran
              ;;
            yarn)
              if ! has_package_script "$script"; then
                return
              fi
              if [ "$script" = "test" ]; then
                note "yarn test"
                yarn test
              else
                note "yarn $script"
                yarn "$script"
              fi
              mark_ran
              ;;
          esac
        }

        maybe_python() {
          if ! have python3; then
            return
          fi
          if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f requirements.txt ] || find . -path './.git' -prune -o -name '*.py' -print -quit | grep -q .; then
            note "python3 -m compileall ."
            python3 -m compileall .
            mark_ran
          fi
          if [ -d tests ] || find . -path './.git' -prune -o \( -name 'test_*.py' -o -name '*_test.py' \) -print -quit | grep -q .; then
            if python3 -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)" >/dev/null 2>&1; then
              note "python3 -m pytest"
              python3 -m pytest
              mark_ran
            fi
          fi
        }

        maybe_node() {
          if [ ! -f package.json ]; then
            return
          fi
          if have npm; then
            package_manager="npm"
          elif [ -f pnpm-lock.yaml ] && have pnpm; then
            package_manager="pnpm"
          elif [ -f yarn.lock ] && have yarn; then
            package_manager="yarn"
          else
            return
          fi
          run_node_script lint "$package_manager"
          run_node_script test "$package_manager"
          run_node_script build "$package_manager"
          run_node_script typecheck "$package_manager"
        }

        maybe_dotnet() {
          if ! have dotnet; then
            return
          fi
          solution="$(find . -maxdepth 3 -name '*.sln' -print | sort | head -n 1)"
          project="$(find . -maxdepth 4 -name '*.csproj' -print | sort | head -n 1)"
          test_project="$(find . -maxdepth 5 \( -name '*Tests.csproj' -o -name '*Test.csproj' \) -print | sort | head -n 1)"
          if [ -n "$solution" ]; then
            note "dotnet build $solution"
            dotnet build "$solution"
            mark_ran
            if [ -n "$test_project" ]; then
              note "dotnet test $solution --no-build"
              dotnet test "$solution" --no-build
              mark_ran
            fi
            return
          fi
          if [ -n "$project" ]; then
            note "dotnet build $project"
            dotnet build "$project"
            mark_ran
          fi
          if [ -n "$test_project" ]; then
            note "dotnet test $test_project --no-build"
            dotnet test "$test_project" --no-build
            mark_ran
          fi
        }

        maybe_go() {
          if [ -f go.mod ] && have go; then
            note "go test ./..."
            go test ./...
            mark_ran
          fi
        }

        maybe_rust() {
          if [ -f Cargo.toml ] && have cargo; then
            note "cargo test"
            cargo test
            mark_ran
          fi
        }

        maybe_python
        maybe_node
        maybe_dotnet
        maybe_go
        maybe_rust

        if [ "$ran_any" -eq 0 ]; then
          note "No standard verification commands detected. Customize scripts/ai/verify.sh for this repo."
        fi
        """
    ).lstrip()


def write_bootstrap_verify_script(path: pathlib.Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(default_bootstrap_verify_script(), encoding="utf-8")
    path.chmod(0o755)


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
    write_bootstrap_verify_script(verify_script)


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
        write_bootstrap_verify_script(repo_root / "scripts" / "ai" / "verify.sh")


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
            "sandbox": "danger-full-access",
            "approval_policy": "never",
            "exec_timeout_seconds": 5400,
            "verify_timeout_seconds": 1800,
            "always_continue": True,
            "avoid_permission_escalation": True,
            "config_overrides": [],
        },
        "review": {
            "enabled": True,
            "mode": "github",
            "trigger": "manual_comment",
            "required_before_queue_advance": True,
            "focus_template": "for regressions and missing tests",
            "owner": str(spec.get("github_owner") or "").strip(),
            "repo": str(spec.get("github_repo") or project_id).strip() if str(spec.get("github_owner") or "").strip() else "",
            "base_branch": "main",
            "branch_template": f"fleet/{project_id}",
            "bot_logins": ["codex"],
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
    split_groups = [group for group in (data.get("project_groups") or []) if not bool((group or {}).get("auto_created"))]
    split_projects = [dict(project or {}) for project in (data.get("projects") or [])]
    split_policies = dict(data.get("policies") or {})
    split_routing = dict(data.get("spider") or {})

    save_yaml(POLICIES_PATH, {"policies": split_policies})
    save_yaml(ROUTING_PATH, {"spider": split_routing})
    save_yaml(GROUPS_PATH, {"project_groups": split_groups})

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    project_files: List[str] = []
    for project in split_projects:
        project_id = str(project.get("id") or "").strip()
        if not project_id:
            continue
        file_name = f"{project_id}.yaml"
        project_files.append(file_name)
        save_yaml(PROJECTS_DIR / file_name, project)
    save_yaml(PROJECT_INDEX_PATH, {"projects": project_files})

    for key in ("policies", "spider", "projects", "project_groups"):
        data.pop(key, None)
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


def account_spark_runtime_state(account_row: Dict[str, Any], account_cfg: Dict[str, Any], allowed_models: List[str], now: dt.datetime) -> str:
    base_state = account_runtime_state(account_row, account_cfg, now)
    if base_state != "ready":
        return base_state
    if not account_supports_spark(account_cfg, allowed_models):
        return "disabled"
    spark_backoff_until = parse_iso(account_row.get("spark_backoff_until"))
    if spark_backoff_until and spark_backoff_until > now:
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
        configured = alias in accounts_cfg
        allowed_models = list(account_cfg.get("allowed_models") or json.loads(db_row.get("allowed_models_json") or "[]") or [])
        item = {
            "alias": alias,
            "bridge_name": str(account_cfg.get("bridge_name") or "").strip(),
            "bridge_priority": int(account_cfg.get("bridge_priority") or 0),
            "configured_lane": infer_account_lane(account_cfg, alias=alias),
            "auth_kind": account_cfg.get("auth_kind") or db_row.get("auth_kind") or "api_key",
            "allowed_models": allowed_models,
            "spark_enabled": account_supports_spark(account_cfg, allowed_models),
            "configured": configured,
            "configured_state": str(account_cfg.get("health_state", "ready") or "ready") if configured else "removed",
            "pool_state": account_runtime_state(db_row, account_cfg, now),
            "spark_pool_state": account_spark_runtime_state(db_row, account_cfg, allowed_models, now),
            "daily_budget_usd": account_cfg.get("daily_budget_usd", db_row.get("daily_budget_usd")),
            "monthly_budget_usd": account_cfg.get("monthly_budget_usd", db_row.get("monthly_budget_usd")),
            "max_parallel_runs": int(account_cfg.get("max_parallel_runs", db_row.get("max_parallel_runs") or 1)),
            "project_allowlist": list(account_cfg.get("project_allowlist") or []),
            "daily_usage": {"cost": 0.0},
            "monthly_usage": {"cost": 0.0},
            "active_runs": 0,
            "backoff_until": db_row.get("backoff_until"),
            "spark_backoff_until": db_row.get("spark_backoff_until"),
            "last_used_at": db_row.get("last_used_at"),
            "last_error": db_row.get("last_error"),
            "spark_last_error": db_row.get("spark_last_error"),
            "capability_models": list(json.loads(db_row.get("capability_models_json") or "[]") or []),
            "capability_checked_at": db_row.get("capability_checked_at"),
            "capability_status": db_row.get("capability_status"),
            "success_count": int(db_row.get("success_count") or 0),
            "failure_count": int(db_row.get("failure_count") or 0),
            "last_selected_model": db_row.get("last_selected_model"),
            "last_model_success_at": db_row.get("last_model_success_at"),
            "last_model_failure_at": db_row.get("last_model_failure_at"),
            "auth_status": account_auth_status(account_cfg) if configured else "not_configured",
            "codex_home": str(account_home(alias)),
        }
        item["lane_policy"] = dict((config.get("lanes") or {}).get(item["configured_lane"]) or {})
        if DB_PATH.exists():
            with db() as conn:
                item["active_runs"] = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM runs
                        WHERE account_alias=?
                          AND status IN ('starting', 'running')
                          AND COALESCE(NULLIF(TRIM(job_kind), ''), 'coding') IN ('coding', 'healing', 'local_review')
                        """,
                        (alias,),
                    ).fetchone()[0]
                )
                item["occupied_runs"] = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM runs
                        WHERE account_alias=?
                          AND status IN ('starting', 'running')
                        """,
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


def runtime_cache_row(cache_key: str) -> Optional[Dict[str, Any]]:
    if not table_exists("runtime_caches"):
        return None
    with db() as conn:
        row = conn.execute("SELECT * FROM runtime_caches WHERE cache_key=?", (cache_key,)).fetchone()
    return dict(row) if row else None


def load_runtime_cache(cache_key: str) -> Tuple[Dict[str, Any], Optional[dt.datetime]]:
    row = runtime_cache_row(cache_key)
    if not row:
        return {}, None
    payload = json_field(row.get("payload_json"), {})
    if not isinstance(payload, dict):
        payload = {}
    return payload, parse_iso(str(row.get("fetched_at") or ""))


def provider_slot_state(provider_payload: Dict[str, Any]) -> str:
    explicit = str(provider_payload.get("state") or "").strip().lower()
    if explicit:
        return explicit
    slot_states = [str(item.get("state") or "").strip().lower() for item in provider_payload.get("slots") or [] if str(item.get("state") or "").strip()]
    if any(state == "ready" for state in slot_states):
        return "ready"
    if any(state in {"degraded", "cooldown"} for state in slot_states):
        return "degraded"
    if slot_states:
        return slot_states[0]
    return "unknown"


def ea_codex_profiles(force: bool = False) -> Dict[str, Any]:
    now = time.time()
    cached = _EA_PROFILE_CACHE.get("payload")
    fetched_at = float(_EA_PROFILE_CACHE.get("fetched_at") or 0.0)
    if not force and cached and (now - fetched_at) < EA_STATUS_CACHE_SECONDS:
        return cached if isinstance(cached, dict) else {}
    persisted_payload, persisted_fetched_at = load_runtime_cache(RUNTIME_CACHE_KEY_EA_CODEX_PROFILES)
    if not EA_STATUS_BASE_URL:
        if persisted_payload:
            _EA_PROFILE_CACHE["fetched_at"] = now
            _EA_PROFILE_CACHE["payload"] = persisted_payload
            return persisted_payload
        return {}
    request = urllib.request.Request(
        f"{EA_STATUS_BASE_URL}/v1/codex/profiles",
        headers={
            **({"Authorization": f"Bearer {EA_STATUS_API_TOKEN}"} if EA_STATUS_API_TOKEN else {}),
            "X-EA-Principal-ID": EA_STATUS_PRINCIPAL_ID,
            "User-Agent": "codex-fleet-admin",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        if persisted_payload:
            payload = persisted_payload
            cache_now = now
            if persisted_fetched_at is not None:
                cache_now = max(0.0, persisted_fetched_at.timestamp())
            _EA_PROFILE_CACHE["fetched_at"] = cache_now
            _EA_PROFILE_CACHE["payload"] = payload
            return payload
        payload = {}
    _EA_PROFILE_CACHE["fetched_at"] = now
    _EA_PROFILE_CACHE["payload"] = payload if isinstance(payload, dict) else {}
    return _EA_PROFILE_CACHE["payload"]


def ea_codex_status(force: bool = False, *, window: str = "7d") -> Dict[str, Any]:
    now = time.time()
    cached = _EA_STATUS_CACHE.get("payload")
    fetched_at = float(_EA_STATUS_CACHE.get("fetched_at") or 0.0)
    cached_window = str(_EA_STATUS_CACHE.get("window") or "7d")
    if not force and cached and cached_window == window and (now - fetched_at) < EA_STATUS_CACHE_SECONDS:
        return cached if isinstance(cached, dict) else {}
    persisted_payload, persisted_fetched_at = load_runtime_cache(RUNTIME_CACHE_KEY_EA_CODEX_STATUS)
    if not EA_STATUS_BASE_URL:
        if persisted_payload:
            _EA_STATUS_CACHE["fetched_at"] = now
            _EA_STATUS_CACHE["payload"] = persisted_payload
            _EA_STATUS_CACHE["window"] = window
            return persisted_payload
        return {}
    request = urllib.request.Request(
        f"{EA_STATUS_BASE_URL}/v1/codex/status?window={window}",
        headers={
            **({"Authorization": f"Bearer {EA_STATUS_API_TOKEN}"} if EA_STATUS_API_TOKEN else {}),
            "X-EA-Principal-ID": EA_STATUS_PRINCIPAL_ID,
            "User-Agent": "codex-fleet-admin",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        if persisted_payload:
            payload = persisted_payload
            cache_now = now
            if persisted_fetched_at is not None:
                cache_now = max(0.0, persisted_fetched_at.timestamp())
            _EA_STATUS_CACHE["fetched_at"] = cache_now
            _EA_STATUS_CACHE["payload"] = payload
            _EA_STATUS_CACHE["window"] = window
            return payload
        payload = {}
    _EA_STATUS_CACHE["fetched_at"] = now
    _EA_STATUS_CACHE["payload"] = payload if isinstance(payload, dict) else {}
    _EA_STATUS_CACHE["window"] = window
    return _EA_STATUS_CACHE["payload"]


def ea_lane_capacity_snapshot(lanes: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    payload = ea_codex_profiles()
    profiles = {
        str(item.get("profile") or "").strip(): dict(item)
        for item in payload.get("profiles") or []
        if str(item.get("profile") or "").strip()
    }
    providers = dict(((payload.get("provider_health") or {}).get("providers")) or {})
    snapshots: Dict[str, Dict[str, Any]] = {}
    normalized = normalize_lanes_config(lanes)
    for lane_name in normalized:
        profile_name = EA_PROFILE_NAME_BY_LANE.get(lane_name, lane_name)
        profile = profiles.get(profile_name, {})
        provider_hints = list(profile.get("provider_hint_order") or (normalized.get(lane_name) or {}).get("provider_hint_order") or [])
        provider_rows: List[Dict[str, Any]] = []
        for provider_key in provider_hints:
            provider_payload = dict(providers.get(provider_key) or {})
            provider_rows.append(
                {
                    "provider_key": provider_key,
                    "state": provider_slot_state(provider_payload),
                    "remaining_percent_of_max": provider_payload.get("remaining_percent_of_max"),
                    "estimated_hours_remaining_at_current_pace": provider_payload.get("estimated_hours_remaining_at_current_pace"),
                    "estimated_burn_credits_per_hour": provider_payload.get("estimated_burn_credits_per_hour"),
                    "estimated_remaining_credits_total": provider_payload.get("estimated_remaining_credits_total"),
                    "max_requests_per_hour": provider_payload.get("max_requests_per_hour"),
                    "max_credits_per_hour": provider_payload.get("max_credits_per_hour"),
                    "max_credits_per_day": provider_payload.get("max_credits_per_day"),
                    "detail": str(provider_payload.get("detail") or "").strip(),
                }
            )
        primary_state = provider_rows[0]["state"] if provider_rows else "unknown"
        fallback_ready = any(str(item.get("state") or "") == "ready" for item in provider_rows[1:])
        snapshots[lane_name] = {
            "lane": lane_name,
            "profile": profile_name,
            "model": str(profile.get("model") or "").strip(),
            "provider_hint_order": provider_hints,
            "state": "fallback_ready" if primary_state != "ready" and fallback_ready else primary_state,
            "providers": provider_rows,
            "review_required": bool(profile.get("review_required")),
            "merge_policy": str(profile.get("merge_policy") or "").strip(),
        }
    return snapshots


def lane_snapshot_remaining_percent(snapshot: Dict[str, Any]) -> Optional[float]:
    for provider in snapshot.get("providers") or []:
        value = provider.get("remaining_percent_of_max")
        try:
            if value is None:
                continue
            return float(value)
        except Exception:
            continue
    return None


def lane_primary_provider(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return dict(next(iter(snapshot.get("providers") or []), {}) or {})


def lane_native_allowance_payload(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    provider = lane_primary_provider(snapshot)
    return {
        "provider_key": str(provider.get("provider_key") or "unknown"),
        "state": str(snapshot.get("state") or provider.get("state") or "unknown"),
        "remaining_percent_of_max": lane_snapshot_remaining_percent(snapshot),
        "estimated_hours_remaining_at_current_pace": provider.get("estimated_hours_remaining_at_current_pace"),
        "estimated_burn_credits_per_hour": provider.get("estimated_burn_credits_per_hour"),
        "estimated_remaining_credits_total": provider.get("estimated_remaining_credits_total"),
        "max_requests_per_hour": provider.get("max_requests_per_hour"),
        "max_credits_per_hour": provider.get("max_credits_per_hour"),
        "max_credits_per_day": provider.get("max_credits_per_day"),
    }


def lane_sustainable_runway(snapshot: Dict[str, Any]) -> str:
    provider = lane_primary_provider(snapshot)
    hours = provider.get("estimated_hours_remaining_at_current_pace")
    if hours not in (None, ""):
        try:
            return human_duration(int(float(hours) * 3600))
        except Exception:
            return "unknown"
    remaining = lane_snapshot_remaining_percent(snapshot)
    state = str(snapshot.get("state") or provider.get("state") or "unknown").strip().lower()
    if remaining is None and state in {"ready", "fallback_ready"}:
        return "Forever on trend"
    if remaining is not None:
        return f"{human_percent(remaining)} allowance"
    return "unknown"


def project_next_reviewer_lane(
    current_task_meta: Dict[str, Any],
    pr_row: Optional[Dict[str, Any]],
    runtime_status: Optional[str],
) -> Optional[str]:
    workflow_kind = str(current_task_meta.get("workflow_kind") or "default").strip().lower()
    required_lane = str(current_task_meta.get("required_reviewer_lane") or "").strip().lower()
    final_lane = str(current_task_meta.get("final_reviewer_lane") or required_lane).strip().lower()
    active_lane = str(decode_review_focus(str((pr_row or {}).get("review_focus") or ""))[1].get("reviewer_lane") or "").strip().lower()
    if workflow_kind != WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
        if active_lane:
            return active_lane
        if str(runtime_status or "").strip().lower() in {"review_requested", "review_failed", "review_fix_required"}:
            return required_lane or None
        return None
    stage = project_workflow_stage(current_task_meta, pr_row, runtime_status)
    if stage in {AWAITING_FIRST_REVIEW_STATUS, REVIEW_LIGHT_PENDING_STATUS}:
        return required_lane or "jury"
    if stage in {JURY_REVIEW_PENDING_STATUS, CORE_RESCUE_PENDING_STATUS}:
        return final_lane or "jury"
    if stage in {GROUNDWORK_PENDING_STATUS, JURY_REWORK_REQUIRED_STATUS}:
        if bool((pr_row or {}).get("needs_core_rescue")):
            return final_lane or "jury"
        return required_lane or "jury"
    if active_lane:
        return active_lane
    return None


def project_core_rescue_likely_next(current_task_meta: Dict[str, Any], pr_row: Optional[Dict[str, Any]]) -> bool:
    if str(current_task_meta.get("workflow_kind") or "default").strip().lower() != WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
        return False
    pr = pr_row or {}
    return bool(pr.get("needs_core_rescue"))


def project_allowance_by_lane(
    *,
    selected_lane: str,
    current_task_meta: Dict[str, Any],
    pr_row: Optional[Dict[str, Any]],
    lane_capacities: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    pr = pr_row or {}
    burn_by_lane = dict(pr.get("allowance_burn_by_lane") or {})
    active_lane = str(decode_review_focus(str(pr.get("review_focus") or ""))[1].get("reviewer_lane") or "").strip().lower()
    ordered_lanes: List[str] = []
    for lane_name in [
        str(selected_lane or "").strip().lower(),
        str(current_task_meta.get("required_reviewer_lane") or "").strip().lower(),
        str(current_task_meta.get("final_reviewer_lane") or "").strip().lower(),
        active_lane,
        *[str(item or "").strip().lower() for item in current_task_meta.get("allowed_lanes") or []],
        *[str(item or "").strip().lower() for item in burn_by_lane.keys()],
    ]:
        if lane_name and lane_name not in ordered_lanes:
            ordered_lanes.append(lane_name)
    payload: Dict[str, Dict[str, Any]] = {}
    for lane_name in ordered_lanes:
        snapshot = lane_capacities.get(lane_name) or {}
        native = lane_native_allowance_payload(snapshot)
        burn = dict(burn_by_lane.get(lane_name) or {})
        payload[lane_name] = {
            **native,
            "estimated_cost_usd": float(burn.get("estimated_cost_usd") or 0.0),
            "runs": int(burn.get("runs") or 0),
            "sustainable_runway": lane_sustainable_runway(snapshot),
        }
    return payload


def project_lane_allowance_summary(project: Dict[str, Any]) -> str:
    parts: List[str] = []
    for lane_name, payload in list((project.get("allowance_percent_by_lane") or {}).items())[:4]:
        remaining = payload.get("remaining_percent_of_max")
        remaining_text = human_percent(remaining) if remaining is not None else "n/a"
        parts.append(f"{lane_name} {remaining_text} / {format_usd(float(payload.get('estimated_cost_usd') or 0.0))}")
    return " · ".join(parts) if parts else "n/a"


def decision_meta_summary(meta: Dict[str, Any]) -> str:
    if not meta:
        return ""
    parts: List[str] = []
    if meta.get("lane"):
        lane = str(meta.get("lane") or "")
        submode = str(meta.get("lane_submode") or "")
        parts.append(f"lane={lane}{f'/{submode}' if submode else ''}")
    if meta.get("selected_profile"):
        parts.append(f"profile={meta['selected_profile']}")
    if meta.get("escalation_reason"):
        parts.append(f"why={meta['escalation_reason']}")
    if meta.get("why_not_cheaper"):
        parts.append(f"cheaper={meta['why_not_cheaper']}")
    if meta.get("predicted_changed_files") is not None:
        parts.append(f"files={meta['predicted_changed_files']}")
    if meta.get("feedback_count") is not None:
        parts.append(f"feedback={meta['feedback_count']}")
    if "spark_eligible" in meta:
        parts.append("spark=yes" if meta.get("spark_eligible") else "spark=no")
    if meta.get("requires_contract_authority"):
        parts.append("contract=yes")
    if meta.get("operator_override_required"):
        parts.append("operator=yes")
    lane_capacity = meta.get("lane_capacity") or {}
    if lane_capacity:
        state = str(lane_capacity.get("state") or "").strip()
        if state:
            parts.append(f"capacity={state}")
        remaining = lane_capacity.get("remaining_percent_of_max")
        if remaining is None:
            providers = lane_capacity.get("providers") or []
            for provider in providers:
                if provider.get("remaining_percent_of_max") is not None:
                    remaining = provider.get("remaining_percent_of_max")
                    break
        try:
            if remaining is not None:
                parts.append(f"remain={float(remaining):.1f}%")
        except Exception:
            pass
    if meta.get("required_reviewer_lane"):
        parts.append(f"reviewer={meta['required_reviewer_lane']}")
    if meta.get("final_reviewer_lane"):
        parts.append(f"final={meta['final_reviewer_lane']}")
    signoff_requirements = [str(item).strip() for item in meta.get("signoff_requirements") or [] if str(item).strip()]
    if signoff_requirements:
        parts.append(f"signoff={'+'.join(signoff_requirements[:3])}")
    return ", ".join(parts)


def selection_trace_summary(trace: List[Dict[str, Any]]) -> str:
    selected = next((item for item in trace if item.get("state") == "selected"), None)
    selected_summary = ""
    if isinstance(selected, dict):
        lane = str(selected.get("requested_lane") or selected.get("lane") or "").strip()
        submode = str(selected.get("lane_submode") or "").strip()
        reason = str(selected.get("escalation_reason") or "").strip()
        selected_summary = ", ".join(
            part for part in [f"lane={lane}{f'/{submode}' if submode else ''}" if lane else "", f"why={reason}" if reason else ""] if part
        )
    skipped: List[str] = []
    for item in trace:
        if item.get("state") == "selected":
            continue
        alias = str(item.get("alias") or "?")
        reason = str(item.get("reason") or item.get("state") or "skipped")
        skipped.append(f"{alias}: {reason}")
    if not skipped:
        return selected_summary
    summary = "; ".join(skipped[:2])
    if len(skipped) > 2:
        summary = f"{summary}; +{len(skipped) - 2} more"
    return "; ".join(part for part in [selected_summary, summary] if part)


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


def latest_spider_decision_by_project(limit: int = 400) -> Dict[str, Dict[str, Any]]:
    if not table_exists("spider_decisions"):
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM spider_decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id or project_id in latest:
            continue
        latest[project_id] = hydrate_spider_decision(dict(row))
    return latest


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
        fields.append("spark_backoff_until=NULL")
    if clear_last_error:
        fields.append("last_error=NULL")
        fields.append("spark_last_error=NULL")
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
        phase = str(existing.get("phase") or READY_STATUS).strip().lower() or READY_STATUS
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


def resolve_design_doc_path(repo_root: pathlib.Path, design_doc: str) -> Optional[pathlib.Path]:
    raw = str(design_doc or "").strip()
    if not raw:
        return None
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path
    return repo_root / path


def design_compile_present(repo_root: pathlib.Path, design_doc: str = "") -> bool:
    if all((repo_root / rel).is_file() for rel in DESIGN_MIRROR_REQUIRED_FILES):
        return True
    design_doc_path = resolve_design_doc_path(repo_root, design_doc)
    return bool(design_doc_path and design_doc_path.is_file())


def latest_design_compile_mtime(repo_root: pathlib.Path, design_doc: str = "") -> Optional[float]:
    times = [(repo_root / rel).stat().st_mtime for rel in DESIGN_MIRROR_REQUIRED_FILES if (repo_root / rel).is_file()]
    design_doc_path = resolve_design_doc_path(repo_root, design_doc)
    if design_doc_path and design_doc_path.is_file():
        times.append(design_doc_path.stat().st_mtime)
    if not times:
        return None
    return max(times)


def studio_compile_summary(repo_root: pathlib.Path, design_doc: str = "") -> Dict[str, Any]:
    published_dir = repo_root / STUDIO_PUBLISHED_DIR
    manifest_path = published_dir / COMPILE_MANIFEST_FILENAME
    design_compiled = design_compile_present(repo_root, design_doc)
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                stages = dict(payload.get("stages") or {})
                stages["design_compile"] = bool(stages.get("design_compile")) or design_compiled
                return {
                    "published_at": str(payload.get("published_at") or ""),
                    "stages": stages,
                    "dispatchable_truth_ready": bool(payload.get("dispatchable_truth_ready")),
                    "artifacts": list(payload.get("artifacts") or []),
                    "lifecycle": str(payload.get("lifecycle") or ""),
                }
        except Exception:
            pass
    files = studio_published_files(repo_root)
    if not files and not design_compiled:
        return {"published_at": "", "stages": {}, "dispatchable_truth_ready": False, "artifacts": [], "lifecycle": ""}
    design_files = {"VISION.md", "ROADMAP.md", "ARCHITECTURE.md"}
    policy_files = {"runtime-instructions.generated.md", "QUEUE.generated.yaml", "PROGRAM_MILESTONES.generated.yaml", "CONTRACT_SETS.yaml", "GROUP_BLOCKERS.md"}
    mtimes = [(published_dir / name).stat().st_mtime for name in files if (published_dir / name).exists()]
    mirror_mtime = latest_design_compile_mtime(repo_root, design_doc)
    if mirror_mtime is not None:
        mtimes.append(mirror_mtime)
    latest_mtime = max(mtimes) if mtimes else dt.datetime.now(tz=UTC).timestamp()
    return {
        "published_at": iso(dt.datetime.fromtimestamp(latest_mtime, UTC)),
        "stages": {
            "design_compile": design_compiled or any(name in design_files for name in files),
            "policy_compile": any(name in policy_files for name in files),
            "execution_compile": "QUEUE.generated.yaml" in files,
        },
        "dispatchable_truth_ready": "QUEUE.generated.yaml" in files,
        "artifacts": files,
        "lifecycle": "",
    }


def compile_health(summary: Dict[str, Any], lifecycle: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    lifecycle_state = normalize_lifecycle_state(lifecycle, "dispatchable")
    compile_cfg = (((config or normalize_config()).get("policies") or {}).get("compile") or {})
    freshness_hours_map = dict(DEFAULT_COMPILE_FRESHNESS_HOURS)
    freshness_hours_map.update(compile_cfg.get("freshness_hours") or {})
    freshness_hours = int(freshness_hours_map.get(lifecycle_state) or DEFAULT_COMPILE_FRESHNESS_HOURS.get(lifecycle_state, 168))
    published_at = parse_iso(str(summary.get("published_at") or ""))
    age_hours = None
    if published_at is not None:
        age_hours = max(0, int((utc_now() - published_at).total_seconds() // 3600))
    stages = dict(summary.get("stages") or {})
    needs_design = lifecycle_state in {"scaffold", "dispatchable", "live", "signoff_only"}
    needs_policy = lifecycle_state in {"dispatchable", "live", "signoff_only"}
    needs_execution = lifecycle_state in {"dispatchable", "live"}
    missing: List[str] = []
    if needs_design and not stages.get("design_compile"):
        missing.append("design compile")
    if needs_policy and not stages.get("policy_compile"):
        missing.append("policy compile")
    if needs_execution and not bool(summary.get("dispatchable_truth_ready")):
        missing.append("execution compile")
    if lifecycle_state == "planned":
        return {
            "status": "not_required",
            "tone": "gray",
            "summary": "planned work does not require dispatch artifacts yet",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if missing and not list(summary.get("artifacts") or []):
        return {
            "status": "missing",
            "tone": "red" if lifecycle_state in DISPATCH_PARTICIPATION_LIFECYCLES else "yellow",
            "summary": f"missing {', '.join(missing)}",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if missing:
        return {
            "status": "partial",
            "tone": "yellow",
            "summary": f"missing {', '.join(missing)}",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if age_hours is not None and age_hours > freshness_hours:
        return {
            "status": "stale",
            "tone": "yellow",
            "summary": f"published {age_hours}h ago; freshness target {freshness_hours}h",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    return {
        "status": "ready",
        "tone": "green",
        "summary": "compile artifacts are current enough for this lifecycle",
        "freshness_hours": freshness_hours,
        "age_hours": age_hours,
    }


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


def audit_finding_is_recommended(finding_key: Any) -> bool:
    key = str(finding_key or "").strip().lower()
    return key.endswith("_recommended")


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

    update_project_runtime(project["id"], status=READY_STATUS, clear_cooldown=True)
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
    member_projects = [str(project_id).strip() for project_id in (group_cfg(config, group_id).get("projects") or []) if str(project_id).strip()]

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
    elif len(member_projects) == 1:
        project_id = member_projects[0]
        project = project_cfg(config, project_id)
        overlay_path = merge_queue_overlay_item(project, str(candidate["detail"] or candidate["title"] or "").strip(), mode="append")
        published_targets.append(
            {
                "target_type": "project",
                "target_id": project_id,
                "path": str(overlay_path),
                "file_count": 1,
            }
        )
        update_project_runtime(project_id, status=READY_STATUS, clear_cooldown=True)

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
        member_projects=member_projects,
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


def trigger_auditor_run(*, scope_type: Optional[str] = None, scope_id: Optional[str] = None) -> None:
    url = f"{AUDITOR_URL}/api/auditor/run-now"
    if scope_type and scope_id:
        url = f"{url}?scope_type={urllib.parse.quote(str(scope_type))}&scope_id={urllib.parse.quote(str(scope_id))}"
    request = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30):
            return
    except urllib.error.URLError as exc:
        raise HTTPException(502, f"unable to trigger fleet-auditor: {exc}") from exc


def trigger_controller_post(path: str) -> Dict[str, Any]:
    request = urllib.request.Request(f"{CONTROLLER_URL}{path}", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise HTTPException(exc.code, detail or f"controller request failed: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(502, f"unable to reach fleet-controller: {exc}") from exc
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {"raw": raw}


def trigger_studio_post(path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{STUDIO_URL}{path}", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise HTTPException(exc.code, detail or f"studio request failed: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(502, f"unable to reach fleet-studio: {exc}") from exc
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {"raw": raw}


def set_group_enabled(group_id: str, enabled: bool) -> None:
    config = normalize_config()
    group = group_cfg(config, group_id)
    for project_id in group.get("projects") or []:
        set_project_enabled(str(project_id), enabled)
        if enabled:
            update_project_runtime(str(project_id), status=READY_STATUS, clear_cooldown=True)


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
    active_runs: Dict[str, Dict[str, Any]] = {}
    for run_row in active_run_rows():
        project_id = str(run_row.get("project_id") or "").strip()
        if project_id and project_id not in active_runs:
            active_runs[project_id] = run_row
    pr_rows = pull_request_rows()
    review_summary = review_findings_summary()
    open_incident_rows = incidents(status="open", limit=400)
    now = utc_now()
    usage_start = usage_window_start(config)
    latest_completed_runs = latest_completed_run_by_project(limit=200)
    latest_decisions = latest_spider_decision_by_project()
    lane_capacities = ea_lane_capacity_snapshot(config.get("lanes") or {})
    items: List[Dict[str, Any]] = []
    for project in config.get("projects", []):
        row = dict(project)
        pr_row = normalized_pull_request_row(project, pr_rows.get(project["id"]))
        lifecycle_state = normalize_lifecycle_state(project.get("lifecycle"), "dispatchable")
        runtime_row = runtime.get(project["id"], {})
        project_groups = project_group_defs(config, project["id"])
        row["queue_index"] = int(runtime_row.get("queue_index") or 0)
        queue_items = json.loads(runtime_row.get("queue_json") or "[]") if runtime_row.get("queue_json") else list(project.get("queue") or [])
        has_queue_sources = bool(project.get("queue_sources"))
        runtime_status = effective_runtime_status(
            project_id=project["id"],
            stored_status=runtime_row.get("status"),
            queue_len=len(queue_items),
            queue_index=row["queue_index"],
            enabled=bool(project.get("enabled", True)),
            active_run_id=runtime_row.get("active_run_id"),
            source_backlog_open=has_queue_sources and bool(queue_items),
            pull_request=pr_row,
        )
        active_run = active_runs.get(project["id"]) or {}
        active_run_status = str(active_run.get("status") or "").strip()
        active_run_id = active_run.get("id")
        if active_run_status in {"starting", "running", "verifying"}:
            runtime_status = runtime_status_for_active_run(runtime_status, active_run)
        elif runtime_status not in {"starting", "running", "verifying"}:
            active_run_id = None
        if not active_run_id and runtime_status in {"starting", "running", "verifying"}:
            active_run_id = runtime_row.get("active_run_id")
        row["active_run_id"] = active_run_id
        active_run_alias = str(active_run.get("account_alias") or "").strip() if active_run_id else ""
        row["active_run_account_alias"] = active_run_alias if active_run_alias else None
        active_preview = run_preview_payload(active_run) if active_run_id else {"log_preview": "", "final_preview": ""}
        row["active_run_log_preview"] = active_preview["log_preview"]
        row["active_run_final_preview"] = active_preview["final_preview"]
        if active_run_id and active_run_alias:
            active_run_backend, active_run_identity = run_backend_and_identity(active_run_alias, config.get("accounts") or {})
            active_run_model = str(active_run.get("model") or "").strip()
            row["active_run_account_backend"] = active_run_backend
            row["active_run_account_identity"] = active_run_identity
            row["active_run_model"] = active_run_model
            row["active_run_brain"] = run_brain_label(active_run_alias, active_run_model, active_run_identity)
        else:
            row["active_run_account_backend"] = "not active"
            row["active_run_account_identity"] = ""
            row["active_run_model"] = ""
            row["active_run_brain"] = "not active"
        if row["active_run_account_backend"] == "not active":
            last_run = latest_completed_runs.get(str(project["id"]) or "", {})
            if last_run:
                last_alias = str(last_run.get("account_alias") or "").strip()
                row["last_run_account_alias"] = last_alias if last_alias else None
                last_backend, last_identity = run_backend_and_identity(last_alias, config.get("accounts") or {})
                last_model = str(last_run.get("model") or "").strip()
                row["last_run_account_backend"] = last_backend or "not active"
                row["last_run_account_identity"] = last_identity
                row["last_run_model"] = last_model
                row["last_run_brain"] = run_brain_label(last_alias, last_model, last_identity)
                row["last_run_finished_at"] = last_run.get("finished_at")
                last_preview = run_preview_payload(last_run)
                row["last_run_log_preview"] = last_preview["log_preview"]
                row["last_run_final_preview"] = last_preview["final_preview"]
            else:
                row["last_run_account_alias"] = None
                row["last_run_account_backend"] = "not active"
                row["last_run_account_identity"] = ""
                row["last_run_model"] = ""
                row["last_run_brain"] = "not active"
                row["last_run_finished_at"] = ""
                row["last_run_log_preview"] = ""
                row["last_run_final_preview"] = ""
        else:
            row["last_run_account_alias"] = None
            row["last_run_account_backend"] = ""
            row["last_run_account_identity"] = ""
            row["last_run_model"] = ""
            row["last_run_brain"] = ""
            row["last_run_finished_at"] = ""
            row["last_run_log_preview"] = ""
            row["last_run_final_preview"] = ""
        row["runtime_status_internal"] = runtime_status
        row["stored_status"] = runtime_row.get("status")
        row["group_ids"] = [group["id"] for group in project_groups]
        row["group_audit_task_counts"] = audit_task_candidate_counts_for_scope("group", row["group_ids"])
        if lifecycle_state == "signoff_only":
            row["group_audit_task_counts"] = {"open": 0, "approved": 0, "published": 0}
        row["completion_basis"] = runtime_completion_basis(
            runtime_status=runtime_status,
            queue_len=len(queue_items),
            queue_index=row["queue_index"],
            has_queue_sources=has_queue_sources,
        )
        row["queue_len"] = len(queue_items)
        current_task_item = queue_items[row["queue_index"]] if row["queue_index"] < len(queue_items) else runtime_row.get("current_slice")
        current_task_meta = normalize_task_queue_item(current_task_item, lanes=config.get("lanes"))
        row["current_slice"] = (
            normalize_slice_text(active_run.get("slice_name"))
            or (
                str(current_task_meta.get("title") or "").strip()
            if row["queue_index"] < len(queue_items)
            else normalize_slice_text(runtime_row.get("current_slice")) or None
            )
        )
        row["current_task_meta"] = current_task_meta
        latest_decision = latest_decisions.get(project["id"], {})
        latest_decision_meta = dict(latest_decision.get("decision_meta") or {})
        row["latest_decision_meta"] = latest_decision_meta
        row["decision_meta_summary"] = str(latest_decision.get("decision_meta_summary") or "")
        row["selection_trace_summary"] = str(latest_decision.get("selection_trace_summary") or "")
        row["selected_lane"] = str(latest_decision_meta.get("lane") or "")
        row["selected_lane_submode"] = str(latest_decision_meta.get("lane_submode") or "")
        row["selected_profile"] = str(latest_decision_meta.get("selected_profile") or "")
        row["selected_lane_reason"] = str(latest_decision_meta.get("escalation_reason") or "")
        row["selected_lane_why_not_cheaper"] = str(latest_decision_meta.get("why_not_cheaper") or "")
        row["selected_lane_allowance"] = dict(latest_decision_meta.get("expected_allowance_burn") or {})
        lane_capacity = dict(latest_decision_meta.get("lane_capacity") or {})
        row["selected_lane_capacity"] = lane_capacity
        row["selected_lane_capacity_state"] = str(lane_capacity.get("state") or "")
        remaining = lane_capacity.get("remaining_percent_of_max")
        if remaining is None:
            for provider in lane_capacity.get("providers") or []:
                if provider.get("remaining_percent_of_max") is not None:
                    remaining = provider.get("remaining_percent_of_max")
                    break
        row["selected_lane_capacity_remaining_percent"] = remaining
        row["allowed_lanes"] = list(current_task_meta.get("allowed_lanes") or [])
        row["required_reviewer_lane"] = str(current_task_meta.get("required_reviewer_lane") or "")
        row["task_final_reviewer_lane"] = str(current_task_meta.get("final_reviewer_lane") or "")
        row["task_landing_lane"] = str(current_task_meta.get("landing_lane") or "")
        row["task_difficulty"] = str(current_task_meta.get("difficulty") or "")
        row["task_risk_level"] = str(current_task_meta.get("risk_level") or "")
        row["task_branch_policy"] = str(current_task_meta.get("branch_policy") or "")
        row["task_acceptance_level"] = str(current_task_meta.get("acceptance_level") or "")
        row["task_budget_class"] = str(current_task_meta.get("budget_class") or "")
        row["task_latency_class"] = str(current_task_meta.get("latency_class") or "")
        row["task_design_owner"] = str(current_task_meta.get("design_owner") or "")
        row["task_design_sensitive"] = bool(current_task_meta.get("design_sensitive"))
        row["task_architecture_sensitive"] = bool(current_task_meta.get("architecture_sensitive"))
        row["task_dispatchability_state"] = str(current_task_meta.get("dispatchability_state") or "")
        row["task_workflow_kind"] = str(current_task_meta.get("workflow_kind") or "default")
        row["task_max_review_rounds"] = int(current_task_meta.get("max_review_rounds") or 0)
        row["task_first_review_required"] = bool(current_task_meta.get("first_review_required"))
        row["task_jury_acceptance_required"] = bool(current_task_meta.get("jury_acceptance_required"))
        row["task_allow_credit_burn"] = bool(current_task_meta.get("allow_credit_burn"))
        row["task_allow_paid_fast_lane"] = bool(current_task_meta.get("allow_paid_fast_lane"))
        row["task_allow_core_rescue"] = bool(current_task_meta.get("allow_core_rescue"))
        row["task_core_rescue_after_round"] = int(current_task_meta.get("core_rescue_after_round") or 0)
        row["task_groundwork_required"] = bool(current_task_meta.get("groundwork_required"))
        row["task_jury_required"] = bool(current_task_meta.get("jury_required"))
        row["task_operator_override_required"] = bool(current_task_meta.get("operator_override_required"))
        row["task_protected_runtime"] = bool(current_task_meta.get("protected_runtime"))
        row["task_signoff_requirements"] = list(current_task_meta.get("signoff_requirements") or [])
        row["task_publish_truth_sources"] = list(current_task_meta.get("publish_truth_sources") or [])
        row["last_error"] = runtime_row.get("last_error")
        row["cooldown_until"] = runtime_row.get("cooldown_until")
        row["consecutive_failures"] = runtime_row.get("consecutive_failures", 0)
        row["published_files"] = studio_published_files(pathlib.Path(project["path"]))
        row["compile"] = studio_compile_summary(pathlib.Path(project["path"]), str(project.get("design_doc") or ""))
        row["compile_health"] = compile_health(row["compile"], str(row.get("lifecycle") or ""), config)
        row["dispatch_participant"] = project_dispatch_participates(row)
        project_meta = registry["projects"].get(project["id"], {})
        project_group_meta = effective_group_meta(project_groups[0], registry, group_runtime) if project_groups else {}
        row["group_signed_off"] = group_is_signed_off(project_group_meta)
        row["remaining_milestones"] = remaining_milestone_items(project_meta)
        row["modeled_uncovered_scope"] = text_items(project_meta.get("uncovered_scope"))
        row["modeled_uncovered_scope_count"] = len(row["modeled_uncovered_scope"])
        row["uncovered_scope"] = project_actionable_uncovered_scope(
            project["id"],
            row["modeled_uncovered_scope"],
            queue_items,
            row["current_slice"],
        )
        row["uncovered_scope_count"] = len(row["uncovered_scope"])
        row["milestone_coverage_complete"] = bool(project_meta.get("milestone_coverage_complete"))
        row["design_coverage_complete"] = bool(project_meta.get("design_coverage_complete"))
        row["audit_task_counts"] = project_audit_task_counts(project["id"])
        if lifecycle_state == "signoff_only":
            row["audit_task_counts"] = {"open": 0, "approved": 0, "published": 0}
        row["review"] = project_review_policy(project)
        row["deployment"] = normalize_project_deployment(project.get("deployment"))
        row["pull_request"] = pr_row
        row["review_rounds_used"] = int((pr_row or {}).get("review_round") or (pr_row or {}).get("local_review_attempts") or 0)
        row["first_review_complete"] = bool((pr_row or {}).get("first_review_complete_at")) or row["review_rounds_used"] > 0
        row["active_reviewer_lane"] = str(decode_review_focus(str((pr_row or {}).get("review_focus") or ""))[1].get("reviewer_lane") or "")
        accepted_on_round = str((pr_row or {}).get("accepted_on_round") or "").strip()
        if not accepted_on_round and str((pr_row or {}).get("review_status") or "").strip().lower() == "fallback_clean":
            accepted_on_round = str(row["review_rounds_used"]) if row["review_rounds_used"] > 0 else ""
        row["accepted_on_round"] = accepted_on_round or None
        row["workflow_stage"] = project_workflow_stage(current_task_meta, pr_row, runtime_status)
        row["next_reviewer_lane"] = project_next_reviewer_lane(current_task_meta, pr_row, runtime_status)
        row["core_rescue_likely_next"] = project_core_rescue_likely_next(current_task_meta, pr_row)
        row["allowance_burn_by_lane"] = dict((pr_row or {}).get("allowance_burn_by_lane") or {})
        row["allowance_percent_by_lane"] = project_allowance_by_lane(
            selected_lane=row["selected_lane"],
            current_task_meta=current_task_meta,
            pr_row=pr_row,
            lane_capacities=lane_capacities,
        )
        primary_runway_lane = row["next_reviewer_lane"] or row["selected_lane"] or row["required_reviewer_lane"]
        row["sustainable_runway"] = (
            lane_sustainable_runway(lane_capacities.get(primary_runway_lane) or {})
            if primary_runway_lane
            else "unknown"
        )
        row["review_eta"] = review_eta_payload(
            row["pull_request"],
            cooldown_until=row["cooldown_until"],
            now=now,
            config=config,
            review_active=bool(row.get("active_run_id")),
        )
        row["review_findings"] = review_summary.get(project["id"], {"count": 0, "blocking_count": 0})
        row["incidents"] = []
        row["open_incident_count"] = 0
        row["primary_incident"] = None
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
        design_uncovered_scope_count = max(
            int(row.get("uncovered_scope_count") or 0),
            int(row.get("modeled_uncovered_scope_count") or 0),
        )
        row["design_progress"] = design_progress_payload(
            meta=project_meta,
            runtime_status=runtime_status,
            uncovered_scope_count=design_uncovered_scope_count,
            project_ids=[str(project.get("id") or "")],
            active_workers=1 if project_has_live_worker(row) else 0,
            now=now,
        )
        row["design_eta"] = dict(row["design_progress"].get("eta") or {})
        row.update(
            project_stop_context(
                project_cfg=project,
                runtime_status=runtime_status,
                queue_len=len(queue_items),
                    uncovered_scope_count=row["uncovered_scope_count"],
                    modeled_uncovered_scope_count=row["modeled_uncovered_scope_count"],
                    open_task_count=row["audit_task_counts"]["open"],
                    approved_task_count=row["audit_task_counts"]["approved"],
                    group_open_task_count=int((row.get("group_audit_task_counts") or {}).get("open") or 0),
                    group_approved_task_count=int((row.get("group_audit_task_counts") or {}).get("approved") or 0),
                last_error=row["last_error"],
                cooldown_until=row["cooldown_until"],
                review_eta=row.get("review_eta"),
                pull_request=row.get("pull_request"),
                milestone_coverage_complete=row["milestone_coverage_complete"],
                design_coverage_complete=row["design_coverage_complete"],
                group_signed_off=row["group_signed_off"],
            )
        )
        row["runtime_status"] = public_project_status(
            runtime_status,
            lifecycle=str(row.get("lifecycle") or ""),
            cooldown_until=row["cooldown_until"],
            needs_refill=bool(row.get("needs_refill")),
            open_task_count=int(row["audit_task_counts"]["open"]),
            approved_task_count=int(row["audit_task_counts"]["approved"]),
            group_signed_off=row["group_signed_off"],
        )
        row["status"] = row["runtime_status"]
        row["pressure_state"] = project_pressure_state(row)
        row["allowance_usage"] = recent_usage_for_scope([project["id"]], usage_start)
        row["delivery_progress"] = delivery_progress_payload_for_project(row)
        if (
            not row.get("active_run_id")
            and runtime_status == "complete"
            and not bool(row.get("needs_refill"))
            and int(row["audit_task_counts"]["open"]) <= 0
            and int(row["audit_task_counts"]["approved"]) <= 0
        ):
            row["current_slice"] = None
        row["runtime_completion_state"] = runtime_completion_state(row["runtime_status"], str(row.get("lifecycle") or ""))
        row["design_completion_state"] = design_completion_state(
            milestone_coverage_complete=bool(row.get("milestone_coverage_complete")),
            design_coverage_complete=bool(row.get("design_coverage_complete")),
            group_signed_off=bool(row.get("group_signed_off")),
        )
        row["completion_axes"] = {
            "lifecycle": normalize_lifecycle_state(row.get("lifecycle"), "dispatchable"),
            "runtime": row["runtime_completion_state"],
            "design": row["design_completion_state"],
            "closure": str(row.get("closure_state") or "open"),
        }
        items.append(row)
    open_incident_rows = filter_runtime_relevant_incidents(open_incident_rows, items)
    for row in items:
        row["incidents"] = [
            item
            for item in open_incident_rows
            if str(item.get("scope_type") or "") == "project" and str(item.get("scope_id") or "") == row["id"]
        ]
        row["open_incident_count"] = len(row["incidents"])
        row["primary_incident"] = row["incidents"][0] if row["incidents"] else None
    return items


def summarize_ops(
    projects: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
    account_pools: List[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    open_incident_rows = incidents(status="open", limit=400)
    stopped_not_signed_off = [project for project in projects if project.get("stopped_not_signed_off")]
    blocked_projects = [
        project
        for project in projects
        if project.get("runtime_status_internal") in {"blocked", SOURCE_BACKLOG_OPEN_STATUS, "awaiting_account"}
        or project.get("needs_refill")
    ]
    queue_exhausted_projects = [
        project for project in projects if str(project.get("runtime_status") or "").strip() == CONFIGURED_QUEUE_COMPLETE_STATUS
    ]
    scaffold_complete_projects = [
        project for project in projects if str(project.get("runtime_status") or "").strip() == SCAFFOLD_QUEUE_COMPLETE_STATUS
    ]
    coverage_pressure_projects = [
        project
        for project in projects
        if project.get("needs_refill")
        or project.get("runtime_status_internal") == SOURCE_BACKLOG_OPEN_STATUS
        or project.get("runtime_status") in {HEALING_STATUS, QUEUE_REFILLING_STATUS, DECISION_REQUIRED_STATUS}
    ]
    proposed_task_groups = [group for group in groups if str(group.get("status") or "") == "proposed_tasks"]
    now = utc_now()
    cooling_down = [
        project
        for project in projects
        if project.get("cooldown_until") and (parse_iso(project.get("cooldown_until")) or now) > now
    ]
    accounts_needing_attention = [
        pool
        for pool in account_pools
        if str(pool.get("pool_state") or "") != "ready" or str(pool.get("auth_status") or "") != "ready" or pool.get("last_error")
    ]
    group_blockers = [
        group
        for group in groups
        if group.get("contract_blockers")
        or str(group.get("status") or "") in {"contract_blocked", "group_blocked"}
        or (
            str(group.get("status") or "") not in {"active", "lockstep_active"}
            and bool(operator_relevant_dispatch_blockers(group.get("dispatch_blockers") or []))
        )
    ]
    notifications = [group for group in groups if group.get("notification_needed")]
    audit_required_groups = [group for group in groups if str(group.get("status") or "") in {"audit_required", "audit_requested"}]
    high_pressure_groups = [group for group in groups if str(group.get("pressure_state") or "") in {"critical", "high"}]
    tight_pool_groups = [
        group for group in groups if str((group.get("pool_sufficiency") or {}).get("level") or "") in {"blocked", "insufficient", "tight"}
    ]
    ready_to_run_now = [
        group
        for group in groups
        if bool(group.get("dispatch_ready")) and str(group.get("status") or "") not in {"audit_required", "audit_requested", "product_signed_off"}
    ]
    review_policy_status = {"config": {"policies": normalize_config().get("policies", {})}}
    prs_waiting_for_review = [
        project
        for project in projects
        if str((project.get("pull_request") or {}).get("review_status") or "") in REVIEW_WAITING_STATUSES
    ]
    stalled_review_projects = [project for project in prs_waiting_for_review if review_request_stalled(project, review_policy_status)]
    prs_with_blocking_findings = [
        project
        for project in projects
        if int((project.get("review_findings") or {}).get("blocking_count") or 0) > 0
    ]
    prs_clean_ready = [
        project
        for project in projects
        if str((project.get("pull_request") or {}).get("review_status") or "") == "clean"
    ]
    review_failed_incidents = [item for item in open_incident_rows if str(item.get("incident_kind") or "") == REVIEW_FAILED_INCIDENT_KIND]
    review_stalled_incidents = [item for item in open_incident_rows if str(item.get("incident_kind") or "") == REVIEW_STALLED_INCIDENT_KIND]
    blocked_unresolved_incidents = [item for item in open_incident_rows if str(item.get("incident_kind") or "") == BLOCKED_UNRESOLVED_INCIDENT_KIND]
    runs_needing_attention = [
        run
        for run in runs
        if str(run.get("status") or "").strip().lower() not in {"complete", "starting", "running", "verifying"}
    ]
    return {
        "open_incident_count": len(open_incident_rows),
        "stopped_not_signed_off": stopped_not_signed_off,
        "blocked_projects": blocked_projects,
        "queue_exhausted_projects": queue_exhausted_projects,
        "scaffold_complete_projects": scaffold_complete_projects,
        "coverage_pressure_projects": coverage_pressure_projects,
        "proposed_task_groups": proposed_task_groups,
        "cooling_down": cooling_down,
        "accounts_needing_attention": accounts_needing_attention,
        "group_blockers": group_blockers,
        "notifications": notifications,
        "audit_required_groups": audit_required_groups,
        "high_pressure_groups": high_pressure_groups,
        "tight_pool_groups": tight_pool_groups,
        "ready_to_run_now": ready_to_run_now,
        "prs_waiting_for_review": prs_waiting_for_review,
        "stalled_review_projects": stalled_review_projects,
        "prs_with_blocking_findings": prs_with_blocking_findings,
        "prs_clean_ready": prs_clean_ready,
        "review_failed_incidents": review_failed_incidents,
        "review_stalled_incidents": review_stalled_incidents,
        "blocked_unresolved_incidents": blocked_unresolved_incidents,
        "runs_needing_attention": runs_needing_attention,
        "open_findings": findings,
    }


def human_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return ""
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}s"
    minutes, seconds = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h" if hours else f"{days}d"


def elapsed_seconds(started_at: Optional[str], *, now: Optional[dt.datetime] = None) -> Optional[int]:
    started = parse_iso(started_at)
    if not started:
        return None
    reference = now or utc_now()
    return max(0, int((reference - started).total_seconds()))


def scheduler_posture(
    ops: Dict[str, Any],
    groups: List[Dict[str, Any]],
    account_pools: List[Dict[str, Any]],
) -> str:
    blocked_groups = len(ops.get("group_blockers") or [])
    review_blocking = len(ops.get("prs_with_blocking_findings") or [])
    attention_accounts = len(ops.get("accounts_needing_attention") or [])
    high_pressure = len(ops.get("high_pressure_groups") or [])
    tight_pool = len(ops.get("tight_pool_groups") or [])
    notifications = len(ops.get("notifications") or [])
    if blocked_groups > 0 and (notifications > 0 or review_blocking > 0 or high_pressure > 0):
        return "emergency"
    if blocked_groups > 0 or review_blocking > 0 or attention_accounts > 0:
        return "critical"
    if tight_pool > 0 or len(ops.get("prs_waiting_for_review") or []) > 0 or len(ops.get("audit_required_groups") or []) > 0:
        return "constrained"
    if any(str(group.get("pressure_state") or "") in {"active", "elevated", "high"} for group in groups):
        return "nominal"
    if any(int(pool.get("active_runs") or 0) > 0 for pool in account_pools):
        return "nominal"
    return "nominal"


def next_reset_windows(spider: Dict[str, Any], account_pools: List[Dict[str, Any]], *, now: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
    reference = now or utc_now()
    next_day = (reference + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if reference.month == 12:
        next_month = reference.replace(year=reference.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        next_month = reference.replace(month=reference.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    standard_recovery = min(
        (parse_iso(pool.get("backoff_until")) for pool in account_pools if parse_iso(pool.get("backoff_until"))),
        default=None,
    )
    spark_recovery = min(
        (
            parse_iso(pool.get("spark_backoff_until"))
            for pool in account_pools
            if bool(pool.get("spark_enabled")) and parse_iso(pool.get("spark_backoff_until"))
        ),
        default=None,
    )
    items = [
        {
            "label": "ChatGPT standard recovery",
            "at": iso(standard_recovery) if standard_recovery else None,
            "basis": "earliest observed account backoff expiry" if standard_recovery else "no active ChatGPT backoff observed",
            "human": human_duration(int((standard_recovery - reference).total_seconds())) if standard_recovery else "clear",
        },
        {
            "label": "Spark recovery",
            "at": iso(spark_recovery) if spark_recovery else None,
            "basis": "earliest observed Spark-capable account backoff expiry" if spark_recovery else "no active Spark backoff observed",
            "human": human_duration(int((spark_recovery - reference).total_seconds())) if spark_recovery else "clear",
        },
        {
            "label": "API daily budget reset",
            "at": iso(next_day),
            "basis": "UTC day boundary",
            "human": human_duration(int((next_day - reference).total_seconds())),
        },
        {
            "label": "API monthly budget reset",
            "at": iso(next_month),
            "basis": "UTC month boundary",
            "human": human_duration(int((next_month - reference).total_seconds())),
        },
    ]
    alliance_hours = int(spider.get("token_alliance_window_hours") or 24)
    items.append(
        {
            "label": "Alliance lookback window",
            "at": iso(reference + dt.timedelta(hours=alliance_hours)),
            "basis": f"{alliance_hours}h scheduler usage horizon",
            "human": f"{alliance_hours}h",
        }
    )
    return items


def latest_runs_by_project(limit: int = 200) -> Dict[str, Dict[str, Any]]:
    rows = recent_runs(limit)
    items: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        project_id = str(row.get("project_id") or "").strip()
        if project_id and project_id not in items:
            items[project_id] = row
    return items


def latest_completed_run_by_project(limit: int = 200) -> Dict[str, Dict[str, Any]]:
    rows = recent_runs(limit)
    items: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        project_id = str(row.get("project_id") or "").strip()
        if not project_id:
            continue
        if project_id in items:
            continue
        if str(row.get("finished_at") or "").strip():
            items[project_id] = row
    return items


def active_run_rows(limit: int = 100) -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM runs
            WHERE status IN ('starting', 'running', 'verifying', 'requested', 'awaiting_review')
              AND finished_at IS NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def run_backend_and_identity(account_alias: str, accounts_cfg: Dict[str, Any]) -> tuple[str, str]:
    alias = str(account_alias or "").strip()
    if not alias:
        return "unknown", ""
    account_cfg = (accounts_cfg or {}).get(alias) or {}
    if alias.lower().startswith("acct-ea-"):
        identity = str(
            account_cfg.get("bridge_name")
            or account_cfg.get("bridge_identity")
            or account_cfg.get("account_name")
            or alias
        ).strip()
        return "EA", identity or alias
    backend_name = "Codex user"
    identity = str(
        account_cfg.get("bridge_name")
        or account_cfg.get("bridge_identity")
        or account_cfg.get("account_name")
        or ""
    ).strip()
    if not identity:
        identity = alias
    return backend_name, identity


def run_brain_label(account_alias: str, model: str, identity: str = "") -> str:
    alias = str(account_alias or "").strip().lower()
    configured = str(model or "").strip()
    identity = str(identity or "").strip()
    if alias == "github":
        return "Codex Reviewer"
    if alias.startswith("acct-ea-"):
        if configured:
            return f"EA backend / {configured}"
        return "EA backend"
    if "gpt-5.3-codex-spark" in configured:
        brain = "Codex Spark"
    elif "gpt-5.3-codex" in configured:
        brain = "Codex Engine"
    elif configured:
        brain = configured
    else:
        brain = "Codex model unknown"
    if identity and "codex user" in identity.lower():
        return brain
    if identity:
        return f"{brain} ({identity})"
    return brain


def studio_proposals(limit: int = 50) -> List[Dict[str, Any]]:
    if not table_exists("studio_proposals"):
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM studio_proposals
            WHERE status IS NULL OR status!='published'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        payload = json_field(item.get("payload_json"), {})
        proposal = payload.get("proposal") or {}
        targets = proposal.get("targets") or []
        item["payload"] = payload if isinstance(payload, dict) else {}
        item["proposal"] = proposal if isinstance(proposal, dict) else {}
        item["files"] = list(item["proposal"].get("files") or [])
        item["targets"] = targets if isinstance(targets, list) else []
        item["targets_summary"] = ", ".join(
            f"{target.get('target_type')}:{target.get('target_id')}"
            for target in item["targets"][:4]
            if isinstance(target, dict)
        )
        if not item["targets_summary"] and item.get("target_type") and item.get("target_id"):
            item["targets_summary"] = f"{item.get('target_type')}:{item.get('target_id')}"
        item["review_context"] = str(item["proposal"].get("summary") or item.get("summary") or "").strip()
        items.append(item)
    return items


def build_attention_items(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    projects = status.get("projects") or status["config"].get("projects", [])
    groups = status.get("groups") or status["config"].get("groups", [])
    ops = status.get("ops_summary") or {}
    account_pools = status.get("account_pools") or []
    task_candidates = (status.get("auditor") or {}).get("task_candidates") or []
    proposals = studio_proposals()
    items: List[Dict[str, Any]] = []

    def add_item(
        *,
        item_id: str,
        card_id: Optional[str] = None,
        kind: str,
        severity: str,
        scope_type: str,
        scope_id: str,
        title: str,
        detail: str,
        primary_action: Optional[Dict[str, Any]] = None,
        secondary_action: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        stale_after: Optional[str] = None,
    ) -> None:
        items.append(
            {
                "id": item_id,
                "kind": kind,
                "severity": severity,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "card_id": card_id or f"attention-{item_id.replace(':', '-').replace('/', '-')}",
                "title": title,
                "detail": detail,
                "primary_action": primary_action or {},
                "secondary_action": secondary_action or {},
                "created_at": created_at,
                "stale_after": stale_after,
            }
        )

    for incident in status.get("incidents") or []:
        if not incident_requires_operator_attention(incident):
            continue
        scope_type = str(incident.get("scope_type") or "")
        scope_id = str(incident.get("scope_id") or "")
        incident_kind = str(incident.get("incident_kind") or "")
        title = str(incident.get("title") or f"{scope_type}:{scope_id} incident")
        summary = str(incident.get("summary") or "")
        incident_id = str(incident.get("id") or "")
        card_id = f"incident-card-{incident_id}" if incident_id else f"incident-{scope_type}-{scope_id}"
        primary_action = {
            "label": "Open context",
            "focus_id": f"incident-focus-{incident_id}",
            "method": "focus",
        }
        secondary_action = {
            "label": "Auto-resolve now",
            "href": f"/api/admin/incidents/{incident_id}/auto-resolve",
            "method": "post",
        }
        add_item(
            item_id=f"incident:{incident.get('id')}",
            card_id=card_id,
            kind=incident_kind or "incident",
            severity=str(incident.get("severity") or "high"),
            scope_type=scope_type or "project",
            scope_id=scope_id,
            title=title,
            detail=summary,
            primary_action=primary_action,
            secondary_action=secondary_action,
            created_at=incident.get("created_at"),
            stale_after=incident.get("updated_at"),
        )

    for group in groups:
        group_id = str(group.get("id") or "")
        if group.get("notification_needed"):
            add_item(
                item_id=f"notify:{group_id}",
                card_id=f"group-problem-{group_id}",
                kind="blocked",
                severity="critical" if group.get("contract_blockers") else "high",
                scope_type="group",
                scope_id=group_id,
                title=f"{group_id} needs an operator decision",
                detail=str((group.get("notification") or {}).get("reason") or group.get("operator_question") or ""),
                primary_action={
                    "label": "Open problem",
                    "href": f"/admin#group-problem-{group_id}",
                    "method": "get",
                },
                secondary_action={
                    "label": "Run audit",
                    "href": f"/api/admin/groups/{group_id}/audit-now",
                    "method": "post",
                },
            )

    for project in ops.get("prs_waiting_for_review") or []:
        project_id = str(project.get("id") or "")
        pr = project.get("pull_request") or {}
        stalled = review_request_stalled(project, status)
        add_item(
            item_id=f"review_wait:{project_id}",
            card_id=f"review-wait-{project_id}",
            kind="review",
            severity="critical" if stalled else "high",
            scope_type="project",
            scope_id=project_id,
            title=(f"GitHub review lane is stalled for {project_id}" if stalled else f"GitHub review required before queue advance for {project_id}"),
            detail=(
                str(pr.get("pr_url") or project.get("current_slice") or "review gate pending")
                + ("; @codex review was requested but no Codex review has landed within SLA" if stalled else "")
                + (
                    f"; {(project.get('review_eta') or {}).get('summary')}"
                    if str((project.get("review_eta") or {}).get("summary") or "").strip()
                    else ""
                )
            ),
            primary_action={
                "label": "Retrigger review" if stalled else "Sync review",
                "href": f"/api/admin/projects/{project_id}/review/request" if stalled else f"/api/admin/projects/{project_id}/review/sync",
                "method": "post",
            },
            secondary_action={
                "label": "Open PR",
                "href": str(pr.get("pr_url") or ""),
                "method": "get",
            },
            created_at=pr.get("review_requested_at"),
        )

    for project in ops.get("prs_with_blocking_findings") or []:
        project_id = str(project.get("id") or "")
        counts = project.get("review_findings") or {}
        pr = project.get("pull_request") or {}
        add_item(
            item_id=f"review_blocking:{project_id}",
            card_id=f"review-blocking-{project_id}",
            kind="review",
            severity="critical",
            scope_type="project",
            scope_id=project_id,
            title=f"{project_id} has blocking Codex review findings",
            detail=f"Blocking findings: {int(counts.get('blocking_count') or 0)}",
            primary_action={
                "label": "Sync review",
                "href": f"/api/admin/projects/{project_id}/review/sync",
                "method": "post",
            },
            secondary_action={
                "label": "Open PR",
                "href": str(pr.get("pr_url") or ""),
                "method": "get",
            },
            created_at=pr.get("review_completed_at") or pr.get("review_requested_at"),
        )

    for task in task_candidates:
        status_value = str(task.get("status") or "open")
        task_meta = task.get("task_meta") or {}
        is_bootstrap = bool(task_meta.get("bootstrap_project"))
        if status_value not in {"open", "approved"}:
            continue
        scope_type = str(task.get("scope_type") or "")
        scope_id = str(task.get("scope_id") or "")
        detail = str(task.get("detail") or "")
        title = str(task.get("title") or "")
        if status_value == "approved":
            add_item(
                item_id=f"approved_task:{task.get('id')}",
                card_id=f"approved-task-{task.get('id')}",
                kind="bootstrap" if is_bootstrap else "publish",
                severity="high",
                scope_type=scope_type,
                scope_id=scope_id,
                title=title,
                detail=detail,
                primary_action={
                    "label": "Publish now",
                    "href": f"/api/admin/audit/tasks/{task['id']}/publish",
                    "method": "post",
                },
                secondary_action={
                    "label": "Reject",
                    "href": f"/api/admin/audit/tasks/{task['id']}/reject",
                    "method": "post",
                },
                created_at=task.get("last_seen_at"),
            )
        elif is_bootstrap:
            add_item(
                item_id=f"bootstrap:{task.get('id')}",
                card_id=f"bootstrap-task-{task.get('id')}",
                kind="bootstrap",
                severity="medium",
                scope_type=scope_type,
                scope_id=scope_id,
                title=f"Bootstrap proposal ready: {title}",
                detail=detail,
                primary_action={
                    "label": "Approve",
                    "href": f"/api/admin/audit/tasks/{task['id']}/approve",
                    "method": "post",
                },
                secondary_action={
                    "label": "Reject",
                    "href": f"/api/admin/audit/tasks/{task['id']}/reject",
                    "method": "post",
                },
                created_at=task.get("last_seen_at"),
            )
        else:
            add_item(
                item_id=f"open_task:{task.get('id')}",
                card_id=f"open-task-{task.get('id')}",
                kind="auditor",
                severity="medium",
                scope_type=scope_type,
                scope_id=scope_id,
                title=title,
                detail=detail,
                primary_action={
                    "label": "Approve",
                    "href": f"/api/admin/audit/tasks/{task['id']}/approve",
                    "method": "post",
                },
                secondary_action={
                    "label": "Reject",
                    "href": f"/api/admin/audit/tasks/{task['id']}/reject",
                    "method": "post",
                },
                created_at=task.get("last_seen_at"),
            )

    for project in projects:
        project_id = str(project.get("id") or "")
        runtime_status = str(project.get("runtime_status") or "")
        if runtime_status not in {"audit_required", "audit_requested", "proposed_tasks", HEALING_STATUS, QUEUE_REFILLING_STATUS, DECISION_REQUIRED_STATUS}:
            continue
        primary_action = {
            "label": "Open group",
            "href": f"/admin/groups/{(project.get('group_ids') or [''])[0]}",
            "method": "get",
        }
        if int(project.get("approved_audit_task_count") or 0) > 0:
            primary_action = {
                "label": "Publish approved",
                "href": f"/api/admin/groups/{(project.get('group_ids') or [''])[0]}/refill-approved",
                "method": "post",
                "fields": {"queue_mode": "append"},
            }
        add_item(
            item_id=f"refill:{project_id}",
            card_id=f"refill-{project_id}",
            kind="refill",
            severity="high" if runtime_status in {"proposed_tasks", DECISION_REQUIRED_STATUS} else "medium",
            scope_type="project",
            scope_id=project_id,
            title=f"{project_id} is {runtime_status}",
            detail=str(project.get("next_action") or project.get("stop_reason") or ""),
            primary_action=primary_action,
            secondary_action={
                "label": "Run audit",
                "href": f"/api/admin/groups/{(project.get('group_ids') or [''])[0]}/audit-now",
                "method": "post",
            }
            if project.get("group_ids")
            else {},
        )

    for pool in account_pools:
        if not bool(pool.get("configured")) and not int(pool.get("active_runs") or 0) and not pool.get("backoff_until") and not pool.get("last_error"):
            continue
        if str(pool.get("pool_state") or "") == "ready" and str(pool.get("auth_status") or "") == "ready":
            continue
        alias = str(pool.get("alias") or "")
        add_item(
            item_id=f"account:{alias}",
            card_id=f"account-pressure-{alias}",
            kind="account_pressure",
            severity="high",
            scope_type="fleet",
            scope_id=alias,
            title=f"{alias} needs account attention",
            detail=f"pool={pool.get('pool_state')} auth={pool.get('auth_status')} error={pool.get('last_error') or ''}".strip(),
            primary_action={
                "label": "Validate auth",
                "href": f"/api/admin/accounts/{alias}/validate",
                "method": "post",
            },
            secondary_action={
                "label": "Clear backoff",
                "href": f"/api/admin/accounts/{alias}/clear-backoff",
                "method": "post",
            },
            created_at=pool.get("last_used_at"),
        )

    for proposal in proposals:
        proposal_id = int(proposal.get("id") or 0)
        add_item(
            item_id=f"studio:{proposal_id}",
            card_id=f"studio-proposal-card-{proposal_id}",
            kind="publish",
            severity="medium",
            scope_type=str(proposal.get("target_type") or "project"),
            scope_id=str(proposal.get("target_id") or proposal.get("project_id") or ""),
            title=str(proposal.get("title") or f"Studio proposal #{proposal_id}"),
            detail=str(proposal.get("review_context") or proposal.get("targets_summary") or ""),
            primary_action={
                "label": "Preview",
                "focus_id": f"studio-proposal-{proposal_id}",
                "method": "focus",
            },
            secondary_action={
                "label": "Open studio",
                "href": f"/studio?session={proposal.get('session_id')}",
                "method": "get",
            },
            created_at=proposal.get("created_at"),
        )

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "info": 3}
    incident_kinds = {
        "incident",
        BLOCKED_UNRESOLVED_INCIDENT_KIND,
        REVIEW_FAILED_INCIDENT_KIND,
        REVIEW_STALLED_INCIDENT_KIND,
        PR_CHECKS_FAILED_INCIDENT_KIND,
    }
    items.sort(
        key=lambda item: (
            severity_rank.get(str(item.get("severity") or "info"), 9),
            0 if str(item.get("kind") or "") in incident_kinds else 1,
            -(parse_iso(item.get("created_at")).timestamp() if parse_iso(item.get("created_at")) else 0.0),
            str(item.get("id") or ""),
        )
    )
    return items


def active_worker_phase(project: Dict[str, Any], run: Dict[str, Any]) -> str:
    run_status = str(run.get("status") or "").strip().lower()
    job_kind = str(run.get("job_kind") or "coding").strip().lower()
    project_runtime = str(project.get("runtime_status_internal") or project.get("runtime_status") or "").strip().lower()
    if run_status == "verifying":
        return "verifying"
    if job_kind in {"local_review", "github_review"}:
        return "review_wait"
    if job_kind == "healing" and project_runtime not in {"starting", "running", "verifying"}:
        return "healing"
    return "coding"


def _preview_tail(text: str, *, max_lines: int, max_chars: int) -> str:
    lines = [line.rstrip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    preview = "\n".join(lines[-max_lines:]).strip()
    if len(preview) <= max_chars:
        return preview
    return preview[-max_chars:].lstrip()


def read_run_preview(path_value: Any, *, max_lines: int = 6, max_chars: int = 480) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""
    path = pathlib.Path(raw)
    if not path.exists() or not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return _preview_tail(text, max_lines=max_lines, max_chars=max_chars)


def run_preview_payload(run: Dict[str, Any]) -> Dict[str, str]:
    item = run if isinstance(run, dict) else {}
    return {
        "log_preview": read_run_preview(item.get("log_path"), max_lines=6, max_chars=520),
        "final_preview": read_run_preview(item.get("final_message_path"), max_lines=4, max_chars=360),
    }


def build_worker_cards(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    projects = status.get("projects") or status["config"].get("projects", [])
    projects_by_id = {str(project.get("id") or ""): project for project in projects}
    active_runs: Dict[str, Dict[str, Any]] = {}
    for row in active_run_rows():
        project_id = str(row.get("project_id") or "").strip()
        if project_id and project_id not in active_runs:
            active_runs[project_id] = row
    cards: List[Dict[str, Any]] = []
    now = utc_now()
    for project_id, run in active_runs.items():
        project = projects_by_id.get(project_id) or {"id": project_id}
        run_status = str(run.get("status") or "").strip()
        if run_status not in {"starting", "running", "verifying"}:
            continue
        job_kind = str(run.get("job_kind") or "coding").strip().lower()
        phase = active_worker_phase(project, run)
        elapsed = elapsed_seconds(run.get("started_at"), now=now)
        account_alias = str(run.get("account_alias") or "").strip()
        accounts_cfg = (status.get("config") or {}).get("accounts") or {}
        account_backend, account_identity = run_backend_and_identity(account_alias, accounts_cfg)
        model = str(run.get("model") or "").strip()
        run_brain = run_brain_label(account_alias, model, account_identity)
        actions: List[Dict[str, Any]] = [
            {"label": "Pause", "href": f"/api/admin/projects/{project_id}/pause", "method": "post"},
            {"label": "Retry", "href": f"/api/admin/projects/{project_id}/retry", "method": "post"},
        ]
        preview = run_preview_payload(run)
        cards.append(
            {
                "worker_id": str(run.get("id") or f"project:{project_id}"),
                "project_id": project_id,
                "group_id": (project.get("group_ids") or [""])[0],
                "account_alias": account_alias,
                "account_backend": account_backend,
                "account_identity": account_identity,
                "model": model,
                "brain": run_brain,
                "route_class": str(run.get("spider_tier") or "").strip(),
                "job_kind": job_kind,
                "current_slice": str(project.get("current_slice") or run.get("slice_name") or "").strip(),
                "phase": phase,
                "started_at": run.get("started_at"),
                "elapsed_seconds": elapsed,
                "elapsed_human": human_duration(elapsed),
                "review_state": str((project.get("pull_request") or {}).get("review_status") or "not_requested"),
                "cooldown_until": project.get("cooldown_until"),
                **preview,
                "available_actions": actions,
            }
        )
    phase_rank = {"blocked": 0, "review_failed": 1, "review_fix_required": 2, "review_wait": 3, "healing": 4, "verifying": 5, "coding": 6, "awaiting_account": 7, "cooldown": 8}
    if not cards: cards = ([{"label": ((v.get("label") if isinstance(v, dict) else "") or k), "alias": str(k), "bridge_priority": 999, "token_status": "unknown", "pool_left": "unknown", "pressure_state": "green", "current_summary": "Idle · waiting on next runnable slice.", "current_work_items": [], "active_runs": 0, "occupied_runs": 0, "burn_rate": "$0.000/day", "projected_exhaustion": "unknown", "top_consumers": [], "allowed_models": [], "service_aliases": []} for k, v in (((status.get("config") or {}).get("lanes") or {}) or {}).items()] or cards)
    cards.sort(key=lambda item: (phase_rank.get(str(item.get("phase") or ""), 99), -int(item.get("elapsed_seconds") or 0), str(item.get("project_id") or "")))
    return cards


def build_worker_breakdown(status: Dict[str, Any]) -> Dict[str, int]:
    active_runs = active_run_rows()
    projects = status.get("projects") or status["config"].get("projects", [])
    projects_by_id = {str(project.get("id") or "").strip(): project for project in projects}
    active_coding_project_ids: set[str] = set()
    active_healing_project_ids: set[str] = set()
    active_review_project_ids: set[str] = set()
    active_verifying_project_ids: set[str] = set()
    for row in active_runs:
        project_id = str(row.get("project_id") or "").strip()
        run_status = str(row.get("status") or "").strip().lower()
        if not project_id or run_status not in {"starting", "running", "verifying"}:
            continue
        phase = active_worker_phase(projects_by_id.get(project_id) or {"id": project_id}, dict(row))
        if phase == "coding":
            active_coding_project_ids.add(project_id)
        elif phase == "healing":
            active_healing_project_ids.add(project_id)
        elif phase == "review_wait":
            active_review_project_ids.add(project_id)
        elif phase == "verifying":
            active_verifying_project_ids.add(project_id)
    coding = len(active_coding_project_ids)
    active_review = len(active_review_project_ids)
    verifying = len(active_verifying_project_ids)
    review_waits = 0
    healing = len(active_healing_project_ids)
    healing_pressure = 0
    now = utc_now()
    for project in projects:
        project_id = str(project.get("id") or "").strip()
        if (
            project_id in active_coding_project_ids
            or project_id in active_review_project_ids
            or project_id in active_verifying_project_ids
        ):
            continue
        runtime_status = str(project.get("runtime_status_internal") or project.get("runtime_status") or "").strip()
        cooldown = parse_iso(project.get("cooldown_until"))
        if runtime_status in {"awaiting_pr", "review_requested"}:
            review_waits += 1
        elif runtime_status in {"review_failed", "review_fix_required", "awaiting_account", "blocked"} or (cooldown and cooldown > now):
            healing_pressure += 1
    return {
        "active_workers": coding + active_review + verifying + healing,
        "active_coding_workers": coding,
        "active_review_workers": active_review,
        "active_verify_workers": verifying,
        "queued_review_workers": review_waits,
        "review_wait_workers": review_waits,
        "review_pressure_workers": review_waits + active_review,
        "healing_workers": healing,
        "healing_pressure_workers": healing_pressure,
    }


def build_approval_center(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    projects = status.get("projects") or status["config"].get("projects", [])
    task_candidates = (status.get("auditor") or {}).get("task_candidates") or []
    proposals = studio_proposals()
    items: List[Dict[str, Any]] = []
    for task in task_candidates:
        status_value = str(task.get("status") or "")
        if status_value != "open":
            continue
        items.append(
            {
                "kind": "audit",
                "title": str(task.get("title") or ""),
                "detail": str(task.get("detail") or ""),
                "actions": [
                    {"label": "Approve", "href": f"/api/admin/audit/tasks/{task['id']}/approve", "method": "post"},
                    {"label": "Reject", "href": f"/api/admin/audit/tasks/{task['id']}/reject", "method": "post"},
                ],
                "focus_id": f"audit-task-{task['id']}",
            }
        )
    for proposal in proposals:
        proposal_id = int(proposal.get("id") or 0)
        items.append(
            {
                "kind": "studio",
                "title": str(proposal.get("title") or f"Studio proposal #{proposal_id}"),
                "detail": str(proposal.get("review_context") or proposal.get("targets_summary") or ""),
                "actions": [
                    {"label": "Preview", "focus_id": f"studio-proposal-{proposal_id}", "method": "focus"},
                    {"label": "Publish", "href": f"/api/admin/studio/proposals/{proposal_id}/publish", "method": "post"},
                ],
                "focus_id": f"studio-proposal-{proposal_id}",
            }
        )
    return items[:20]


def account_pressure_state(pool: Dict[str, Any]) -> str:
    if str(pool.get("auth_status") or "") != "ready":
        return "red"
    if str(pool.get("pool_state") or "") in {"disabled", "draining", "cooldown", "exhausted", "auth_stale"}:
        return "red"
    daily_budget = float(pool.get("daily_budget_usd") or 0.0)
    daily_cost = float((pool.get("daily_usage") or {}).get("cost") or 0.0)
    monthly_budget = float(pool.get("monthly_budget_usd") or 0.0)
    monthly_cost = float((pool.get("monthly_usage") or {}).get("cost") or 0.0)
    if (daily_budget and daily_cost >= daily_budget * 0.85) or (monthly_budget and monthly_cost >= monthly_budget * 0.85):
        return "yellow"
    if int(pool.get("active_runs") or 0) >= int(pool.get("max_parallel_runs") or 1):
        return "yellow"
    return "green"


def format_usd(value: float) -> str:
    if value >= 100:
        return f"${value:.0f}"
    if value >= 10:
        return f"${value:.1f}"
    return f"${value:.2f}"


def account_token_status_text(pool: Dict[str, Any], now: Optional[dt.datetime] = None) -> str:
    current_now = now or utc_now()
    auth_status = str(pool.get("auth_status") or "").strip()
    pool_state = str(pool.get("pool_state") or "").strip()
    spark_pool_state = str(pool.get("spark_pool_state") or "").strip()
    backoff = parse_iso(pool.get("spark_backoff_until") or pool.get("backoff_until"))
    parts: List[str] = []
    if auth_status and auth_status != "ready":
        parts.append(auth_status.replace("_", " "))
    if pool_state:
        parts.append(pool_state.replace("_", " "))
    if spark_pool_state and spark_pool_state != pool_state:
        parts.append(f"spark {spark_pool_state.replace('_', ' ')}")
    if backoff and backoff > current_now:
        parts.append(f"cooldown {human_duration(int((backoff - current_now).total_seconds()))}")
    return " · ".join(dict.fromkeys(parts)) if parts else "ready"


def account_pool_left_text(pool: Dict[str, Any]) -> str:
    daily_budget = float(pool.get("daily_budget_usd") or 0.0)
    daily_cost = float((pool.get("daily_usage") or {}).get("cost") or 0.0)
    monthly_budget = float(pool.get("monthly_budget_usd") or 0.0)
    monthly_cost = float((pool.get("monthly_usage") or {}).get("cost") or 0.0)
    max_parallel_runs = max(1, int(pool.get("max_parallel_runs") or 1))
    active_runs = int(pool.get("active_runs") or 0)
    slots_left = max(max_parallel_runs - active_runs, 0)
    parts: List[str] = []
    if daily_budget:
        parts.append(f"{format_usd(max(daily_budget - daily_cost, 0.0))} today")
    if monthly_budget:
        parts.append(f"{format_usd(max(monthly_budget - monthly_cost, 0.0))} month")
    parts.append(f"{slots_left} slot{'s' if slots_left != 1 else ''} left")
    return " · ".join(parts)


def top_consumers_for_account(alias: str, groups_by_project: Dict[str, str], start: dt.datetime) -> List[str]:
    if not DB_PATH.exists():
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT project_id, COALESCE(SUM(estimated_cost_usd), 0.0) AS cost
            FROM runs
            WHERE account_alias=? AND started_at >= ?
            GROUP BY project_id
            ORDER BY cost DESC, project_id
            LIMIT 3
            """,
            (alias, iso(start)),
        ).fetchall()
    labels: List[str] = []
    for row in rows:
        project_id = str(row["project_id"] or "")
        group_id = groups_by_project.get(project_id, "")
        cost = float(row["cost"] or 0.0)
        label = f"{project_id} ${cost:.3f}"
        if group_id:
            label = f"{group_id}/{label}"
        labels.append(label)
    return labels


def build_runway_model(status: Dict[str, Any]) -> Dict[str, Any]:
    groups = status.get("groups") or status["config"].get("groups", [])
    projects = status.get("projects") or status["config"].get("projects", [])
    account_pools = status.get("account_pools") or []
    lane_capacities = ea_lane_capacity_snapshot((status.get("config") or {}).get("lanes") or {})
    occupied_run_counts: Dict[str, int] = {}
    for row in active_run_rows():
        alias = str(row.get("account_alias") or "").strip()
        run_status = str(row.get("status") or "").strip().lower()
        if not alias or run_status not in {"starting", "running", "verifying"}:
            continue
        occupied_run_counts[alias] = occupied_run_counts.get(alias, 0) + 1
    config = normalize_config()
    usage_start = usage_window_start(normalize_config())
    max_parallel = max(1, int(((config.get("policies") or {}).get("max_parallel_runs") or 1)))
    groups_by_project: Dict[str, str] = {}
    for group in groups:
        for project_id in group.get("projects") or []:
            groups_by_project[str(project_id)] = str(group.get("id") or "")
    projects_by_group: Dict[str, List[Dict[str, Any]]] = {}
    for project in projects:
        for group_id in project.get("group_ids") or []:
            projects_by_group.setdefault(str(group_id), []).append(project)
    total_group_cost = sum(float((group.get("allowance_usage") or {}).get("estimated_cost_usd") or 0.0) for group in groups) or 0.0
    group_rows: List[Dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: (-int((item.get("captain") or {}).get("priority") or 0), str(item.get("id") or ""))):
        group_projects = projects_by_group.get(str(group.get("id") or ""), [])
        sufficiency = group.get("pool_sufficiency") or {}
        eligible_slots = int(sufficiency.get("eligible_parallel_slots") or 0)
        required_slots = max(1, int(sufficiency.get("required_slots") or 1))
        estimated_cost = float((group.get("allowance_usage") or {}).get("estimated_cost_usd") or 0.0)
        drain_share_percent = int(round((estimated_cost / total_group_cost) * 100.0)) if total_group_cost > 0 else 0
        group_rows.append(
            {
                "group_id": str(group.get("id") or ""),
                "lifecycle": str(group.get("lifecycle") or ""),
                "priority": int((group.get("captain") or {}).get("priority") or 0),
                "service_floor": int((group.get("captain") or {}).get("service_floor") or 0),
                "admission_policy": str((group.get("captain") or {}).get("admission_policy") or ""),
                "status": str(group.get("status") or ""),
                "bottleneck": "; ".join((group.get("contract_blockers") or [])[:1] + (group.get("dispatch_blockers") or [])[:1]) or str(group.get("dispatch_basis") or ""),
                "runway_risk": str(group.get("pressure_state") or "nominal"),
                "pool_level": str(sufficiency.get("level") or "unknown"),
                "remaining_slices": int(sufficiency.get("remaining_slices") or 0),
                "eligible_parallel_slots": eligible_slots,
                "required_slots": required_slots,
                "slot_share_percent": int(round((eligible_slots / max_parallel) * 100.0)),
                "drain_share_percent": drain_share_percent,
                "estimated_cost_usd": estimated_cost,
                "dispatch_member_count": int(group.get("dispatch_member_count") or 0),
                "scaffold_member_count": int(group.get("scaffold_member_count") or 0),
                "signoff_only_member_count": int(group.get("signoff_only_member_count") or 0),
                "compile_attention_count": sum(
                    1
                    for project in group_projects
                    if str((project.get("compile_health") or {}).get("status") or "") not in {"ready", "not_required"}
                ),
                "deployment": group.get("deployment") or {},
                "deployment_summary": str((group.get("deployment") or {}).get("display") or ""),
                "deployment_url": str((group.get("deployment") or {}).get("target_url") or ""),
                "design_progress": dict(group.get("design_progress") or {}),
                "design_eta": dict(group.get("design_eta") or group.get("program_eta") or {}),
                "delivery_progress": dict(group.get("delivery_progress") or {}),
                "finish_outlook": runway_finish_outlook(
                    str(sufficiency.get("level") or ""),
                    str(sufficiency.get("basis") or ""),
                ),
                "sufficiency_basis": str(sufficiency.get("basis") or ""),
            }
        )
    account_rows: List[Dict[str, Any]] = []
    for pool in account_pools:
        daily_budget = float(pool.get("daily_budget_usd") or 0.0)
        daily_cost = float((pool.get("daily_usage") or {}).get("cost") or 0.0)
        monthly_budget = float(pool.get("monthly_budget_usd") or 0.0)
        monthly_cost = float((pool.get("monthly_usage") or {}).get("cost") or 0.0)
        budget_health = "green"
        if (daily_budget and daily_cost >= daily_budget * 0.85) or (monthly_budget and monthly_cost >= monthly_budget * 0.85):
            budget_health = "yellow"
        if (daily_budget and daily_cost >= daily_budget) or (monthly_budget and monthly_cost >= monthly_budget):
            budget_health = "red"
        projected = "unknown"
        if daily_budget and daily_cost > 0:
            hours_left = max(0.0, (daily_budget - daily_cost) / max(daily_cost / 24.0, 0.0001))
            projected = human_duration(int(hours_left * 3600))
        elif monthly_budget and monthly_cost > 0:
            projected = "month"
        occupied = int(occupied_run_counts.get(str(pool.get("alias") or ""), 0))
        account_rows.append(
            {
                "alias": str(pool.get("alias") or ""),
                "bridge_name": str(pool.get("bridge_name") or ""),
                "bridge_priority": int(pool.get("bridge_priority") or 0),
                "auth_kind": str(pool.get("auth_kind") or ""),
                "standard_pool_state": str(pool.get("pool_state") or ""),
                "spark_pool_state": str(pool.get("spark_pool_state") or ""),
                "api_budget_health": budget_health,
                "active_runs": max(int(pool.get("active_runs") or 0), occupied),
                "recent_backoff": str(pool.get("spark_backoff_until") or pool.get("backoff_until") or ""),
                "burn_rate": f"${daily_cost:.3f}/day",
                "projected_exhaustion": projected,
                "pressure_state": account_pressure_state(pool),
                "top_consumers": top_consumers_for_account(str(pool.get('alias') or ''), groups_by_project, usage_start),
            }
        )
    lane_rows: List[Dict[str, Any]] = []
    for lane_name, snapshot in lane_capacities.items():
        native = lane_native_allowance_payload(snapshot)
        estimated_cost = 0.0
        run_count = 0
        for project in projects:
            lane_payload = dict(((project.get("allowance_percent_by_lane") or {}).get(lane_name)) or {})
            estimated_cost += float(lane_payload.get("estimated_cost_usd") or 0.0)
            run_count += int(lane_payload.get("runs") or 0)
        lane_rows.append(
            {
                "lane": lane_name,
                "state": native.get("state"),
                "provider_key": native.get("provider_key"),
                "remaining_percent_of_max": native.get("remaining_percent_of_max"),
                "estimated_hours_remaining_at_current_pace": native.get("estimated_hours_remaining_at_current_pace"),
                "estimated_remaining_credits_total": native.get("estimated_remaining_credits_total"),
                "estimated_burn_credits_per_hour": native.get("estimated_burn_credits_per_hour"),
                "max_requests_per_hour": native.get("max_requests_per_hour"),
                "max_credits_per_hour": native.get("max_credits_per_hour"),
                "max_credits_per_day": native.get("max_credits_per_day"),
                "estimated_cost_usd": round(estimated_cost, 6),
                "run_count": run_count,
                "sustainable_runway": lane_sustainable_runway(snapshot),
            }
        )
    lane_rows.sort(key=lambda item: str(item.get("lane") or ""))
    return {"groups": group_rows, "accounts": account_rows, "lanes": lane_rows}


def build_operator_cards(
    status: Dict[str, Any],
    *,
    workers: Optional[List[Dict[str, Any]]] = None,
    runway: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    now = utc_now()
    accounts_cfg = ((status.get("config") or {}).get("accounts") or {})
    worker_rows = list(workers or build_worker_cards(status))
    runway_accounts = {
        str(row.get("alias") or "").strip(): row for row in ((runway or {}).get("accounts") or []) if str(row.get("alias") or "").strip()
    }
    account_pools = {
        str(pool.get("alias") or "").strip(): pool for pool in (status.get("account_pools") or []) if str(pool.get("alias") or "").strip()
    }
    workers_by_alias: Dict[str, List[Dict[str, Any]]] = {}
    for worker in worker_rows:
        alias = str(worker.get("account_alias") or "").strip()
        if alias:
            workers_by_alias.setdefault(alias, []).append(worker)
    bridge_services: List[Dict[str, Any]] = []
    seen_bridge_names: set[str] = set()
    for alias, account_cfg in accounts_cfg.items():
        clean_alias = str(alias or "").strip()
        bridge_name = str((account_cfg or {}).get("bridge_name") or "").strip()
        if not clean_alias or not bridge_name or bridge_name in seen_bridge_names:
            continue
        aliases: List[str] = [clean_alias]
        configured_fallbacks = account_cfg.get("bridge_fallback_accounts") or DEFAULT_BRIDGE_FALLBACK_ACCOUNTS.get(clean_alias, [])
        for fallback_alias in configured_fallbacks:
            clean_fallback = str(fallback_alias or "").strip()
            if clean_fallback and clean_fallback in accounts_cfg and clean_fallback not in aliases:
                aliases.append(clean_fallback)
        bridge_services.append(
            {
                "label": bridge_name,
                "bridge_priority": int(account_cfg.get("bridge_priority") or 0),
                "primary_alias": clean_alias,
                "aliases": aliases,
            }
        )
        seen_bridge_names.add(bridge_name)
    bridge_services.sort(key=lambda item: (int(item.get("bridge_priority") or 999), str(item.get("label") or "")))
    cards: List[Dict[str, Any]] = []
    for service in bridge_services:
        bridge_name = str(service.get("label") or "").strip()
        aliases = [str(alias or "").strip() for alias in service.get("aliases") or [] if str(alias or "").strip()]
        phase_order = {
            "coding": 0,
            "local_review": 1,
            "review_wait": 2,
            "verifying": 3,
            "healing": 4,
            "dispatch_pending": 5,
        }
        account_workers = sorted(
            [
                worker
                for alias in aliases
                for worker in workers_by_alias.get(alias, [])
                if str(worker.get("phase") or "").strip()
            ],
            key=lambda worker: (
                phase_order.get(str(worker.get("phase") or "").strip(), 99),
                str(worker.get("project_id") or ""),
            ),
        )
        representative_alias = ""
        if account_workers:
            representative_alias = str(account_workers[0].get("account_alias") or "").strip()
        if not representative_alias:
            representative_alias = next(
                (
                    alias
                    for alias in aliases
                    if str((account_pools.get(alias) or {}).get("pool_state") or "").strip() == "ready"
                ),
                str(service.get("primary_alias") or ""),
            )
        pool = account_pools.get(representative_alias) or account_pools.get(str(service.get("primary_alias") or "")) or {}
        account_runway = runway_accounts.get(representative_alias) or runway_accounts.get(str(service.get("primary_alias") or "")) or {}
        representative_cfg = accounts_cfg.get(representative_alias) or accounts_cfg.get(str(service.get("primary_alias") or "")) or {}
        configured_lane = infer_account_lane(representative_cfg, alias=representative_alias or str(service.get("primary_alias") or ""))
        lane_policy = dict((((status.get("config") or {}).get("lanes") or {}).get(configured_lane)) or {})
        current_work_items: List[Dict[str, Any]] = []
        for worker in account_workers[:3]:
            current_work_items.append(
                {
                    "project_id": str(worker.get("project_id") or "").strip(),
                    "phase": str(worker.get("phase") or "").strip(),
                    "slice": str(worker.get("current_slice") or worker.get("phase") or "").strip(),
                    "elapsed_human": str(worker.get("elapsed_human") or "").strip(),
                }
            )
        ops_summary = dict(status.get("ops_summary") or {})
        current_summary = "Idle · waiting on next runnable slice."
        if current_work_items:
            labels = [
                f"{item['project_id']} ({item['phase'].replace('_', ' ')})"
                if item.get("project_id") and item.get("phase")
                else str(item.get("project_id") or item.get("phase") or "").strip()
                for item in current_work_items
            ]
            labels = [label for label in labels if label]
            if labels:
                current_summary = "Working on " + ", ".join(labels[:2]) + (" +" if len(labels) > 2 else "")
        elif str(pool.get("pool_state") or "").strip() not in {"ready", ""}:
            last_error = str(pool.get("last_error") or "").lower()
            if "usage-limited" in last_error:
                current_summary = "Waiting for quota recheck."
            else:
                current_summary = "Waiting for account recovery."
        elif int(ops_summary.get("review_waiting_projects") or 0) > 0 or int(ops_summary.get("blocked_groups") or 0) > 0:
            current_summary = "Idle · waiting on review or recovery."
        raw_active_runs = sum(int((account_pools.get(alias) or {}).get("active_runs") or 0) for alias in aliases)
        raw_occupied_runs = sum(int((account_pools.get(alias) or {}).get("occupied_runs") or 0) for alias in aliases)
        effective_runs = max(raw_active_runs, len(current_work_items))
        cards.append(
            {
                "label": bridge_name,
                "alias": str(service.get("primary_alias") or ""),
                "bridge_priority": int(service.get("bridge_priority") or 0),
                "configured_lane": configured_lane,
                "lane_label": str(lane_policy.get("label") or configured_lane.title()),
                "lane_authority": str(lane_policy.get("authority") or ""),
                "lane_worker_profile": str(lane_policy.get("worker_profile") or ""),
                "lane_runtime_model": str(lane_policy.get("runtime_model") or ""),
                "provider_hints": list(lane_policy.get("provider_hint_order") or []),
                "token_status": account_token_status_text(pool, now=now),
                "pool_left": account_pool_left_text(pool),
                "pressure_state": str(account_runway.get("pressure_state") or account_pressure_state(pool)),
                "current_summary": current_summary,
                "current_work_items": current_work_items,
                "active_runs": effective_runs,
                "occupied_runs": max(raw_occupied_runs, effective_runs),
                "burn_rate": str(account_runway.get("burn_rate") or "$0.000/day"),
                "projected_exhaustion": str(account_runway.get("projected_exhaustion") or "unknown"),
                "top_consumers": list(account_runway.get("top_consumers") or []),
                "allowed_models": list(pool.get("allowed_models") or []),
                "service_aliases": aliases,
            }
        )
    if not cards:
        cards = (
            [
                {
                    "label": ((v.get("label") if isinstance(v, dict) else "") or k),
                    "alias": str(k),
                    "bridge_priority": 999,
                    "configured_lane": str(k),
                    "lane_label": ((v.get("label") if isinstance(v, dict) else "") or k),
                    "lane_authority": ((v.get("authority") if isinstance(v, dict) else "") or ""),
                    "lane_worker_profile": ((v.get("worker_profile") if isinstance(v, dict) else "") or ""),
                    "lane_runtime_model": ((v.get("runtime_model") if isinstance(v, dict) else "") or ""),
                    "provider_hints": list((v.get("provider_hint_order") if isinstance(v, dict) else []) or []),
                    "token_status": "unknown",
                    "pool_left": "unknown",
                    "pressure_state": "green",
                    "current_summary": "Idle · waiting on next runnable slice.",
                    "current_work_items": [],
                    "active_runs": 0,
                    "occupied_runs": 0,
                    "burn_rate": "$0.000/day",
                    "projected_exhaustion": "unknown",
                    "top_consumers": [],
                    "allowed_models": [],
                    "service_aliases": [],
                }
                for k, v in (((status.get("config") or {}).get("lanes") or {}) or {}).items()
            ]
            or cards
        )
    cards.sort(key=lambda item: (int(item.get("bridge_priority") or 999), str(item.get("label") or "")))
    return cards


def cockpit_simulation(status: Dict[str, Any], group_id: str, action: str) -> Dict[str, Any]:
    clean_group_id = str(group_id or "").strip()
    clean_action = str(action or "").strip().lower()
    if clean_action not in {"protect", "drain", "burst"}:
        raise HTTPException(400, "unknown simulation action")
    groups = status.get("groups") or status["config"].get("groups", [])
    target_group = next((group for group in groups if str(group.get("id") or "") == clean_group_id), None)
    if not target_group:
        raise HTTPException(404, f"unknown group: {clean_group_id}")

    max_parallel = max(1, int(((status.get("config") or {}).get("policies") or {}).get("max_parallel_runs") or 1))
    rows: List[Dict[str, Any]] = []
    for group in groups:
        captain = dict(group.get("captain") or {})
        priority = int(captain.get("priority") or 0)
        service_floor = max(0, int(captain.get("service_floor") or 0))
        admission_policy = str(captain.get("admission_policy") or "normal")
        if str(group.get("id") or "") == clean_group_id:
            if clean_action == "protect":
                priority = max(priority, 500)
                service_floor = max(service_floor, 1)
                admission_policy = "protect"
            elif clean_action == "drain":
                service_floor = 0
                admission_policy = "drain"
            elif clean_action == "burst":
                priority = max(priority, 250)
                admission_policy = "burst"
        rows.append(
            {
                "group_id": str(group.get("id") or ""),
                "priority": priority,
                "service_floor": service_floor,
                "shed_order": int((captain.get("shed_order") or 0)),
                "admission_policy": admission_policy,
                "pressure_state": str(group.get("pressure_state") or ""),
                "remaining_slices": int(((group.get("pool_sufficiency") or {}).get("remaining_slices") or 0)),
                "eligible_parallel_slots": int(((group.get("pool_sufficiency") or {}).get("eligible_parallel_slots") or 0)),
            }
        )

    total_floor = sum(int(item["service_floor"]) for item in rows)
    overflow = max(0, total_floor - max_parallel)
    shed_candidates: List[str] = []
    if overflow > 0:
        for item in sorted(rows, key=lambda row: (row["priority"], row["shed_order"], row["group_id"])):
            if item["group_id"] == clean_group_id and clean_action != "drain":
                continue
            if item["service_floor"] <= 0:
                continue
            shed_candidates.append(str(item["group_id"]))
            overflow -= int(item["service_floor"])
            if overflow <= 0:
                break

    beneficiaries = [
        str(item["group_id"])
        for item in sorted(rows, key=lambda row: (-row["priority"], row["group_id"]))
        if str(item["group_id"]) != clean_group_id and str(item["admission_policy"]) != "drain"
    ][:3]
    if clean_action == "burst":
        target_slots = int((target_group.get("pool_sufficiency") or {}).get("eligible_parallel_slots") or 0)
        burst_gain = 1 if target_slots < max_parallel else 0
        notes = (
            f"{clean_group_id} is promoted to burst priority and can likely claim {burst_gain} additional dispatch slot(s) if accounts recover."
            if burst_gain
            else f"{clean_group_id} is already at the current slot ceiling; burst mostly changes scheduling priority."
        )
    elif clean_action == "protect":
        notes = f"{clean_group_id} is protected at the next slice boundary; lower-priority groups become shed candidates if service floors exceed {max_parallel}."
    else:
        released = max(1, int((target_group.get("captain") or {}).get("service_floor") or 0))
        notes = f"{clean_group_id} is drained and releases up to {released} guaranteed slot(s) for higher-priority groups."

    posture = scheduler_posture(status.get("ops_summary") or {}, groups, status.get("account_pools") or [])
    return {
        "group_id": clean_group_id,
        "action": clean_action,
        "current_posture": posture,
        "max_parallel_runs": max_parallel,
        "projected_total_service_floor": total_floor,
        "shed_candidates": shed_candidates,
        "beneficiary_groups": beneficiaries,
        "projected_priority_order": [str(item["group_id"]) for item in sorted(rows, key=lambda row: (-row["priority"], row["group_id"]))],
        "notes": notes,
    }


def auto_heal_enabled(status: Dict[str, Any]) -> bool:
    policies = ((status.get("config") or {}).get("policies") or {})
    return bool(policies.get("auto_heal_enabled", True))


def scope_auto_heal_policy(config: Dict[str, Any], *, project_id: Optional[str] = None, group_id: Optional[str] = None) -> Dict[str, Any]:
    auto_heal = (((config.get("policies") or {}).get("auto_heal")) or {})
    if project_id:
        return dict((auto_heal.get("projects") or {}).get(str(project_id).strip()) or {})
    if group_id:
        return dict((auto_heal.get("groups") or {}).get(str(group_id).strip()) or {})
    return {}


def scope_auto_heal_categories(
    config: Dict[str, Any],
    *,
    project_id: Optional[str] = None,
    group_id: Optional[str] = None,
) -> Dict[str, bool]:
    base = {
        "coverage": True,
        "review": True,
        "capacity": True,
        "contracts": True,
    }
    scope_policy = scope_auto_heal_policy(config, project_id=project_id, group_id=group_id)
    categories = dict(scope_policy.get("categories") or {})
    for key in list(base):
        if key in categories:
            base[key] = bool(categories.get(key))
    return base


def scope_auto_heal_enabled(
    config: Dict[str, Any],
    *,
    project_id: Optional[str] = None,
    group_id: Optional[str] = None,
) -> bool:
    policies = config.get("policies") or {}
    if not bool(policies.get("auto_heal_enabled", True)):
        return False
    scope_policy = scope_auto_heal_policy(config, project_id=project_id, group_id=group_id)
    if "enabled" in scope_policy:
        return bool(scope_policy.get("enabled"))
    return True


def auto_heal_escalation_thresholds(config: Dict[str, Any]) -> Dict[str, int]:
    auto_heal = (((config.get("policies") or {}).get("auto_heal")) or {})
    raw = dict(auto_heal.get("escalation_thresholds") or {})
    result = dict(DEFAULT_AUTO_HEAL_ESCALATION_THRESHOLDS)
    for category in list(result):
        if category in raw:
            result[category] = max(0, int(raw.get(category) or 0))
    return result


def auto_heal_escalation_threshold(config: Dict[str, Any], category: str) -> int:
    return int(auto_heal_escalation_thresholds(config).get(str(category or "").strip().lower(), 0))


def auto_heal_categories(status: Dict[str, Any]) -> Dict[str, bool]:
    policies = ((status.get("config") or {}).get("policies") or {})
    categories = (((policies.get("auto_heal") or {}).get("categories")) or {})
    result = {
        "coverage": True,
        "review": True,
        "capacity": True,
        "contracts": True,
    }
    for key in list(result):
        if key in categories:
            result[key] = bool(categories.get(key))
    return result


def review_request_stalled(project: Dict[str, Any], status: Dict[str, Any], *, now: Optional[dt.datetime] = None) -> bool:
    pr = project.get("pull_request") or {}
    review_status = str(pr.get("review_status") or "").strip().lower()
    if review_status not in REVIEW_WAITING_STATUSES:
        return False
    if parse_iso(pr.get("review_completed_at")):
        return False
    review_eta = review_eta_payload(
        pr,
        cooldown_until=pr.get("next_retry_at"),
        now=now,
        config=status.get("config") or normalize_config(),
    )
    reset_at = parse_iso(str(review_eta.get("reset_at") or ""))
    if bool(review_eta.get("throttled")) and reset_at and reset_at > (now or utc_now()):
        return False
    requested_at = parse_iso(pr.get("review_requested_at")) or parse_iso(pr.get("updated_at"))
    if not requested_at:
        return False
    policies = ((status.get("config") or {}).get("policies") or {})
    stall_minutes = max(1, int(policies.get("review_stall_sla_minutes", 10) or 10))
    return requested_at <= (now or utc_now()) - dt.timedelta(minutes=stall_minutes)


def build_lamp_items(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    projects = status.get("projects") or status["config"].get("projects", [])
    groups = status.get("groups") or status["config"].get("groups", [])
    findings = (status.get("auditor") or {}).get("findings") or []
    incidents_rows = status.get("incidents") or []
    ops = status.get("ops_summary") or {}
    now = utc_now()
    stalled_reviews = [project for project in projects if review_request_stalled(project, status, now=now)]
    unresolved_design = [
        group
        for group in groups
        if str(group.get("status") or "") == DECISION_REQUIRED_STATUS
        or (group.get("notification_needed") and not group.get("auditor_can_solve"))
    ]
    contract_findings = [
        finding
        for finding in findings
        if any(token in str(finding.get("finding_key") or "").lower() for token in ("contract", "session", "dto", "explain", "package"))
    ]
    coverage_findings = [
        finding
        for finding in findings
        if str(finding.get("finding_key") or "") in {"project.uncovered_scope", "project.queue_exhausted_with_uncovered_scope", "project.milestone_coverage_incomplete"}
    ]
    execution_scope_ids = [
        str(project.get("id") or "")
        for project in projects
        if project_has_live_worker(project)
    ]
    capacity_scope_ids = [
        str(project.get("id") or "")
        for project in projects
        if str(project.get("runtime_status") or "") in {WAITING_CAPACITY_STATUS, "awaiting_account"}
    ]
    review_scope_ids = sorted(
        {
            *[str(project.get("id") or "") for project in ops.get("prs_waiting_for_review") or []],
            *[
                str(project.get("id") or "")
                for project in projects
                if int((project.get("review_findings") or {}).get("blocking_count") or 0) > 0
                or str(project.get("runtime_status") or "").strip() in {"review_requested", REVIEW_FIX_STATUS, "review_failed"}
            ],
        }
    )
    coverage_scope_ids = sorted(
        {
            *[str(project.get("id") or "") for project in ops.get("coverage_pressure_projects") or []],
            *[str(group.get("id") or "") for group in ops.get("audit_required_groups") or []],
        }
    )
    contract_scope_ids = sorted(
        {
            *[str(group.get("id") or "") for group in groups if group.get("contract_blockers")],
            *[str(finding.get("scope_id") or "") for finding in contract_findings],
        }
    )
    design_scope_ids = [str(group.get("id") or "") for group in unresolved_design]
    lamp_specs = [
        {
            "id": "execution",
            "label": "Execution",
            "count": len(execution_scope_ids),
            "state": "red" if any(str(item.get("incident_kind") or "") == BLOCKED_UNRESOLVED_INCIDENT_KIND for item in incidents_rows) else ("yellow" if any(str(project.get("runtime_status") or "") == HEALING_STATUS for project in projects) else "green"),
            "detail": "blocked unresolved incidents, active workers, and healing runs",
            "href": "/admin/details#projects",
            "focus_id": "lamp-execution",
            "summary_lines": execution_scope_ids[:6],
            "auto_action": "retry blocked slices, reroute cooled-down work, and keep active workers flowing",
            "eta_hint": "next scheduler sweep",
        },
        {
            "id": "capacity",
            "label": "Capacity",
            "count": len(ops.get("tight_pool_groups") or []) + len(capacity_scope_ids),
            "state": "red" if any(str((group.get("pool_sufficiency") or {}).get("level") or "") in {"blocked", "insufficient"} for group in groups) else ("yellow" if any(str((group.get("pool_sufficiency") or {}).get("level") or "") == "tight" for group in groups) else "green"),
            "detail": "eligible pool sufficiency, waiting-capacity projects, and account pressure",
            "href": "/admin/details#accounts",
            "focus_id": "lamp-capacity",
            "summary_lines": capacity_scope_ids[:6],
            "auto_action": "shed low-priority demand, burst reserve accounts, and wait out pool cooldowns",
            "eta_hint": "pool reset window or next dispatch pass",
            "category": "capacity",
        },
        {
            "id": "review",
            "label": "Review",
            "count": len(review_scope_ids),
            "state": "red" if stalled_reviews or any(str(item.get("incident_kind") or "") in {REVIEW_STALLED_INCIDENT_KIND, REVIEW_FAILED_INCIDENT_KIND, PR_CHECKS_FAILED_INCIDENT_KIND} for item in incidents_rows) else ("yellow" if (ops.get("prs_waiting_for_review") or []) else "green"),
            "detail": "GitHub review waits, stalled review requests, and failed review sync",
            "href": "/admin/details#reviews",
            "focus_id": "lamp-review",
            "summary_lines": review_scope_ids[:6],
            "auto_action": "sync PR state, retrigger stale review heads, and repair failed review lanes",
            "eta_hint": "review SLA or next sync pass",
            "category": "review",
        },
        {
            "id": "coverage",
            "label": "Coverage",
            "count": len(coverage_findings) + len(ops.get("coverage_pressure_projects") or []) + len(ops.get("audit_required_groups") or []),
            "state": "yellow" if coverage_findings or ops.get("coverage_pressure_projects") or ops.get("audit_required_groups") else "green",
            "detail": "queue refills, uncovered scope, and audit-required groups",
            "href": "/admin/details#audit",
            "focus_id": "lamp-coverage",
            "summary_lines": coverage_scope_ids[:6],
            "auto_action": "materialize uncovered scope into new tasks, publish safe queue overlays, and requeue groups",
            "eta_hint": "next auditor cycle",
            "category": "coverage",
        },
        {
            "id": "contracts",
            "label": "Contracts",
            "count": len(contract_findings) + len([group for group in groups if group.get("contract_blockers")]),
            "state": "red" if any(group.get("contract_blockers") for group in groups) else ("yellow" if contract_findings else "green"),
            "detail": "contract blockers, package-plane drift, session/event canon, and explain DTO seams",
            "href": "/admin/details#groups",
            "focus_id": "lamp-contracts",
            "summary_lines": contract_scope_ids[:6],
            "auto_action": "publish safe bridge shims, keep contract remediation slices moving, and surface only real canon conflicts",
            "eta_hint": "after next audit or remediation slice",
            "category": "contracts",
        },
        {
            "id": "design",
            "label": "Design Decisions",
            "count": len(design_scope_ids),
            "state": "red" if unresolved_design else "green",
            "detail": "only unresolved human design or policy decisions should stay red here",
            "href": "/admin/details#studio",
            "focus_id": "lamp-design",
            "summary_lines": design_scope_ids[:6],
            "auto_action": "auto-choose recommended options whenever the auditor or spider produced one",
            "eta_hint": "immediate when a recommendation exists",
        },
    ]
    return lamp_specs


def first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def human_percent(value: Any) -> str:
    try:
        if value is None:
            return "n/a"
        return f"{float(value):.0f}%"
    except Exception:
        return "n/a"


def baseline_slice_seconds(project: Dict[str, Any]) -> int:
    difficulty = str(project.get("task_difficulty") or "").strip().lower()
    base = {
        "easy": 30 * 60,
        "medium": 75 * 60,
        "hard": 180 * 60,
    }.get(difficulty, 60 * 60)
    risk = str(project.get("task_risk_level") or "").strip().lower()
    if risk == "medium":
        base = int(base * 1.25)
    elif risk == "high":
        base = int(base * 1.6)
    acceptance = str(project.get("task_acceptance_level") or "").strip().lower()
    if acceptance in {"reviewed", "merge_ready"}:
        base += 25 * 60
    elif acceptance == "verified":
        base += 10 * 60
    return max(base, 20 * 60)


def slice_forecast_from_project(project: Dict[str, Any], *, elapsed_seconds: int = 0) -> Dict[str, Any]:
    baseline = baseline_slice_seconds(project)
    remaining = max(baseline - max(0, int(elapsed_seconds or 0)), 10 * 60)
    lane = first_nonempty(project.get("selected_lane"), (project.get("allowed_lanes") or [None])[0], "unknown")
    provider = first_nonempty(project.get("active_run_account_backend"), project.get("last_run_account_backend"), (project.get("selected_lane_capacity") or {}).get("providers", [{}])[0].get("provider_key"))
    brain = first_nonempty(project.get("active_run_brain"), project.get("last_run_brain"), project.get("active_run_model"))
    verify_ahead = str(project.get("runtime_status") or "") not in REVIEW_VISIBLE_STATUSES and bool(project.get("required_reviewer_lane"))
    return {
        "project_id": str(project.get("id") or ""),
        "title": first_nonempty(project.get("current_slice"), project.get("next_action"), "No runnable slice selected"),
        "lane": lane,
        "provider": provider or "unknown",
        "brain": brain or "unknown",
        "reason": first_nonempty(project.get("selected_lane_reason"), project.get("decision_meta_summary"), project.get("next_action"), project.get("stop_reason")),
        "elapsed_seconds": int(max(0, elapsed_seconds or 0)),
        "elapsed_human": human_duration(int(max(0, elapsed_seconds or 0))),
        "remaining_seconds": remaining,
        "remaining_human": human_duration(remaining),
        "total_seconds": baseline,
        "total_human": human_duration(baseline),
        "verify_or_review_ahead": verify_ahead,
        "prerequisites": first_nonempty(project.get("stop_reason"), project.get("next_action"), "none"),
    }


def queue_candidate_confidence(project: Dict[str, Any]) -> str:
    runtime_status = str(project.get("runtime_status") or "").strip().lower()
    capacity_state = str(project.get("selected_lane_capacity_state") or "").strip().lower()
    if runtime_status in {HEALING_STATUS, QUEUE_REFILLING_STATUS, SOURCE_BACKLOG_OPEN_STATUS, DECISION_REQUIRED_STATUS, "blocked", WAITING_CAPACITY_STATUS, "awaiting_account"}:
        return "volatile"
    if runtime_status in REVIEW_VISIBLE_STATUSES or capacity_state in {"degraded", "fallback_ready", "unknown"}:
        return "likely"
    return "stable"


def queue_forecast_payload(status: Dict[str, Any], *, workers: List[Dict[str, Any]]) -> Dict[str, Any]:
    projects = status.get("projects") or []
    active_worker = next((worker for worker in workers if str(worker.get("project_id") or "").strip()), None)
    projects_by_id = {str(project.get("id") or ""): project for project in projects}
    active_project = projects_by_id.get(str((active_worker or {}).get("project_id") or ""))
    queued_projects = [
        project for project in projects
        if str(project.get("id") or "") != str((active_project or {}).get("id") or "")
        and str(project.get("runtime_status") or "") in {READY_STATUS, WAITING_CAPACITY_STATUS, "awaiting_account", "review_requested", "awaiting_pr", HEALING_STATUS, QUEUE_REFILLING_STATUS}
        and first_nonempty(project.get("current_slice"), project.get("next_action"))
    ]
    status_rank = {
        READY_STATUS: 0,
        "review_requested": 1,
        "awaiting_pr": 1,
        WAITING_CAPACITY_STATUS: 2,
        "awaiting_account": 2,
        HEALING_STATUS: 3,
        QUEUE_REFILLING_STATUS: 4,
    }
    queued_projects.sort(key=lambda item: (status_rank.get(str(item.get("runtime_status") or ""), 9), str(item.get("id") or "")))
    if active_project:
        now_card = slice_forecast_from_project(active_project, elapsed_seconds=int((active_worker or {}).get("elapsed_seconds") or 0))
        next_project = queued_projects[0] if queued_projects else None
        then_project = queued_projects[1] if len(queued_projects) > 1 else None
    elif queued_projects:
        now_project = queued_projects[0]
        now_card = slice_forecast_from_project(now_project)
        next_project = queued_projects[1] if len(queued_projects) > 1 else None
        then_project = queued_projects[2] if len(queued_projects) > 2 else None
    else:
        now_card = {
            "project_id": "",
            "title": "Idle",
            "lane": "idle",
            "provider": "none",
            "brain": "none",
            "reason": "No active worker is executing a slice right now.",
            "elapsed_seconds": 0,
            "elapsed_human": "0s",
            "remaining_seconds": 0,
            "remaining_human": "unknown",
            "total_seconds": 0,
            "total_human": "unknown",
            "verify_or_review_ahead": False,
            "prerequisites": "dispatchable work",
        }
        next_project = None
        then_project = None
    next_card = slice_forecast_from_project(next_project) if next_project else {"title": "No next slice materialized", "prerequisites": "queue refill or dispatch", "lane": "unknown", "provider": "unknown", "brain": "unknown", "reason": "The runtime queue has no dispatchable successor yet.", "remaining_human": "unknown", "project_id": "", "verify_or_review_ahead": False}
    then_card = slice_forecast_from_project(then_project) if then_project else {"title": "No then slice visible", "prerequisites": "future refill or approval", "lane": "unknown", "provider": "unknown", "brain": "unknown", "reason": "The next queue boundary is still fluid.", "remaining_human": "unknown", "project_id": "", "verify_or_review_ahead": False}
    next_card["confidence"] = queue_candidate_confidence(next_project or {})
    then_card["confidence"] = queue_candidate_confidence(then_project or {}) if then_project else "volatile"
    return {
        "now": now_card,
        "next": next_card,
        "then": then_card,
    }


def mission_forecast_payload(status: Dict[str, Any], *, queue_forecast: Dict[str, Any], lane_capacities: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    groups = status.get("groups") or []
    incomplete_groups = [group for group in groups if str(group.get("status") or "").strip() not in {"complete", COMPLETED_SIGNED_OFF_STATUS}]
    milestone_group = next(
        (
            group for group in sorted(
                incomplete_groups,
                key=lambda item: (
                    0 if str((item.get("design_progress") or {}).get("summary") or "").strip() else 1,
                    str(item.get("id") or ""),
                ),
            )
        ),
        None,
    )
    vision_group = next(
        (
            group for group in sorted(
                incomplete_groups,
                key=lambda item: str(((item.get("program_eta") or {}).get("eta_human") or "zzzz")),
            )
        ),
        None,
    )
    lane_bits = []
    for lane in ("core", "easy", "jury"):
        snapshot = lane_capacities.get(lane) or {}
        lane_bits.append(f"{lane.title()} {human_percent(lane_snapshot_remaining_percent(snapshot))}")
    stop_time = next(
        (
            provider.get("estimated_hours_remaining_at_current_pace")
            for lane in ("core", "easy", "jury")
            for provider in ((lane_capacities.get(lane) or {}).get("providers") or [])
            if provider.get("estimated_hours_remaining_at_current_pace") is not None
        ),
        None,
    )
    stop_risk = "none"
    if stop_time is not None:
        try:
            if float(stop_time) <= 24:
                stop_risk = f"throttles in {human_duration(int(float(stop_time) * 3600))}"
            else:
                stop_risk = f"{human_duration(int(float(stop_time) * 3600))} runway"
        except Exception:
            stop_risk = "unknown"
    headline = " ".join(
        part for part in [
            f"Working now: {queue_forecast.get('now', {}).get('title') or 'Idle'}." ,
            f"ETA: {queue_forecast.get('now', {}).get('remaining_human') or 'unknown'}.",
            f"Next: {queue_forecast.get('next', {}).get('title') or 'none'}.",
            f"Vision: {((vision_group or {}).get('program_eta') or {}).get('eta_human') or 'unknown'}.",
            f"Capacity: {', '.join(lane_bits)}.",
            f"Stop risk: {stop_risk}.",
        ] if part
    )
    return {
        "headline": headline,
        "current_eta": queue_forecast.get("now", {}).get("remaining_human") or "unknown",
        "next_title": queue_forecast.get("next", {}).get("title") or "none",
        "vision_eta": ((vision_group or {}).get("program_eta") or {}).get("eta_human") or "unknown",
        "milestone_title": first_nonempty((milestone_group or {}).get("name"), (milestone_group or {}).get("id"), "No milestone in focus"),
        "milestone_eta": ((milestone_group or {}).get("program_eta") or {}).get("eta_human") or "unknown",
        "lane_capacity_summary": lane_bits,
        "stop_risk": stop_risk,
    }


def capacity_forecast_payload(status: Dict[str, Any], *, lane_capacities: Dict[str, Dict[str, Any]], runway: Dict[str, Any]) -> Dict[str, Any]:
    lanes: List[Dict[str, Any]] = []
    critical_lane = "core"
    critical_stop = "unknown"
    runway_lanes = {
        str(item.get("lane") or "").strip(): item for item in (runway.get("lanes") or []) if str(item.get("lane") or "").strip()
    }
    lane_order = [str(name).strip() for name in ((status.get("config") or {}).get("lanes") or {}).keys() if str(name).strip()]
    if not lane_order:
        lane_order = [str(name).strip() for name in lane_capacities.keys() if str(name).strip()]
    if not lane_order:
        lane_order = ["easy", "repair", "groundwork", "review_light", "core", "jury", "survival"]
    for lane in lane_order:
        snapshot = lane_capacities.get(lane) or {}
        native = lane_native_allowance_payload(snapshot)
        remaining = native.get("remaining_percent_of_max")
        hours = native.get("estimated_hours_remaining_at_current_pace")
        state = str(snapshot.get("state") or "unknown")
        if lane == critical_lane and hours is not None:
            try:
                critical_stop = human_duration(int(float(hours) * 3600))
            except Exception:
                critical_stop = "unknown"
        runway_lane = runway_lanes.get(lane) or {}
        lanes.append(
            {
                "lane": lane,
                "profile": str(snapshot.get("profile") or lane),
                "model": str(snapshot.get("model") or "unknown"),
                "provider": str(native.get("provider_key") or "unknown"),
                "state": state,
                "remaining_percent": remaining,
                "remaining_text": human_percent(remaining) if remaining is not None else ("quota unknown" if state == "unknown" else state),
                "hours_text": human_duration(int(float(hours) * 3600)) if hours not in (None, "") else "unknown",
                "hot_runway": human_duration(int(float(hours) * 3600)) if hours not in (None, "") else "unknown",
                "sustainable_runway": lane_sustainable_runway(snapshot),
                "native_allowance": native,
                "local_estimated_burn_usd": float(runway_lane.get("estimated_cost_usd") or 0.0),
                "local_run_count": int(runway_lane.get("run_count") or 0),
                "mission_ready": state in {"ready", "fallback_ready"},
            }
        )
    accounts = runway.get("accounts") or []
    pool_outlook = next((str(item.get("projected_exhaustion") or "").strip() for item in accounts if str(item.get("projected_exhaustion") or "").strip() and str(item.get("projected_exhaustion")) != "unknown"), "unknown")
    finite_hours = [item.get("native_allowance", {}).get("estimated_hours_remaining_at_current_pace") for item in lanes]
    finite_hours = [float(value) for value in finite_hours if value not in (None, "")]
    mission_runway = (
        "Forever on trend"
        if lanes and not finite_hours and all(str(item.get("state") or "") in {"ready", "fallback_ready"} for item in lanes)
        else ("unknown" if not finite_hours else human_duration(int(min(finite_hours) * 3600)))
    )
    return {
        "lanes": lanes,
        "critical_path_lane": critical_lane,
        "critical_path_stop": critical_stop,
        "pool_runway": pool_outlook,
        "mission_runway": mission_runway,
    }


def vision_forecast_payload(status: Dict[str, Any], *, queue_forecast: Dict[str, Any]) -> Dict[str, Any]:
    groups = status.get("groups") or []
    if not groups:
        return {
            "milestone_title": "No groups configured",
            "milestone_eta": "unknown",
            "milestone_percent_complete": 0,
            "vision_eta_p50": "unknown",
            "vision_eta_p90": "unknown",
            "summary": "No program groups are configured.",
        }
    ranked = sorted(groups, key=lambda item: (-int(((item.get("delivery_progress") or {}).get("percent_complete") or 0)), str(item.get("id") or "")))
    milestone = ranked[-1]
    design = milestone.get("design_progress") or {}
    eta = milestone.get("program_eta") or {}
    confidence = str(eta.get("confidence") or design.get("eta_confidence") or "low")
    p50 = str(eta.get("eta_human") or "unknown")
    p90 = p50 if confidence == "high" else ("unknown" if p50 == "unknown" else f"{p50}+" if confidence == "medium" else f"{p50}++")
    return {
        "milestone_title": first_nonempty(milestone.get("name"), milestone.get("id"), "unknown"),
        "milestone_eta": p50,
        "milestone_percent_complete": int((milestone.get("delivery_progress") or {}).get("percent_complete") or 0),
        "milestone_percent_blocked": int((milestone.get("delivery_progress") or {}).get("percent_blocked") or 0),
        "milestone_percent_inflight": int((milestone.get("delivery_progress") or {}).get("percent_inflight") or 0),
        "vision_eta_p50": p50,
        "vision_eta_p90": p90,
        "confidence": confidence,
        "summary": first_nonempty(design.get("summary"), milestone.get("bottleneck"), queue_forecast.get("next", {}).get("reason"), "No program forecast summary available."),
    }


def blocker_forecast_payload(status: Dict[str, Any], *, queue_forecast: Dict[str, Any], attention: List[Dict[str, Any]], lamps: List[Dict[str, Any]]) -> Dict[str, Any]:
    now_project = str((queue_forecast.get("now") or {}).get("project_id") or "")
    next_project = str((queue_forecast.get("next") or {}).get("project_id") or "")
    def blocker_for(scope_id: str) -> str:
        if scope_id:
            for item in attention:
                if str(item.get("scope_id") or "") == scope_id:
                    return first_nonempty(item.get("title"), item.get("detail"))
        return ""
    now_blocker = blocker_for(now_project) or first_nonempty((queue_forecast.get("now") or {}).get("prerequisites"), "none")
    next_blocker = blocker_for(next_project) or first_nonempty((queue_forecast.get("next") or {}).get("prerequisites"), "none")
    vision_blocker = first_nonempty(*(item.get("detail") for item in lamps if str(item.get("state") or "") in {"red", "yellow"}), "none")
    return {
        "now": now_blocker,
        "next": next_blocker,
        "vision": vision_blocker,
    }


def truth_freshness_payload(status: Dict[str, Any]) -> Dict[str, Any]:
    projects = status.get("projects") or []
    groups = status.get("groups") or []
    generated_at_text = str(status.get("generated_at") or iso(utc_now()) or "")
    generated_at = parse_iso(generated_at_text)
    age_text = "unknown"
    if generated_at:
        age_seconds = max(0, int((utc_now() - generated_at).total_seconds()))
        age_text = human_duration(age_seconds)
    compile_attention = sum(
        1 for project in projects if str(((project.get("compile_health") or {}).get("status")) or "").strip().lower() not in {"ready", "not_required"}
    )
    config_warning_count = len(status.get("config_warnings") or [])
    dispatch_ready_groups = sum(1 for group in groups if bool(group.get("dispatch_ready")))
    dispatch_total_groups = len(groups)
    state = "fresh"
    if compile_attention > 0 or config_warning_count > 0:
        state = "attention"
    if compile_attention > 2 or config_warning_count > 2:
        state = "stale"
    summary = (
        f"Published {generated_at_text or 'unknown'} ({age_text} ago) · "
        f"compile attention {compile_attention} · config warnings {config_warning_count} · "
        f"dispatchable groups {dispatch_ready_groups}/{dispatch_total_groups}"
    )
    return {
        "state": state,
        "generated_at": generated_at_text,
        "age": age_text,
        "compile_attention_count": compile_attention,
        "config_warning_count": config_warning_count,
        "dispatch_ready_groups": dispatch_ready_groups,
        "dispatch_total_groups": dispatch_total_groups,
        "summary": summary,
    }


def mission_active_project(status: Dict[str, Any], queue_forecast: Dict[str, Any]) -> Dict[str, Any]:
    now_project_id = str((queue_forecast.get("now") or {}).get("project_id") or "").strip()
    if not now_project_id:
        return {}
    return next((project for project in (status.get("projects") or []) if str(project.get("id") or "").strip() == now_project_id), {})


def telemetry_root_for_status(status: Dict[str, Any]) -> pathlib.Path:
    fleet_project = next(
        (project for project in (status.get("projects") or []) if str(project.get("id") or "").strip() == "fleet"),
        {},
    )
    repo_path = pathlib.Path(str(fleet_project.get("path") or DOCKER_ROOT / "fleet"))
    return repo_path / "logs" / "telemetry"


def load_latest_telemetry_payload(status: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    latest_dir = telemetry_root_for_status(status) / "latest"
    payload: Dict[str, Dict[str, Any]] = {}
    for name in ("summary", "review_loop", "worker_utilization"):
        target = latest_dir / f"{name}.json"
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            loaded = {}
        payload[name] = dict(loaded) if isinstance(loaded, dict) else {}
    return payload


def execution_loop_payload(
    status: Dict[str, Any],
    *,
    queue_forecast: Dict[str, Any],
    blocker_forecast: Dict[str, Any],
) -> Dict[str, Any]:
    telemetry = load_latest_telemetry_payload(status)
    telemetry_review_loop = dict(telemetry.get("review_loop") or {})
    telemetry_workers = dict(telemetry.get("worker_utilization") or {})
    telemetry_summary = dict(telemetry.get("summary") or {})
    project = mission_active_project(status, queue_forecast)
    if not project:
        return {
            "workflow_kind": "idle",
            "active": False,
            "title": queue_forecast.get("now", {}).get("title") or "Idle",
            "project_id": "",
            "current_stage": "idle",
            "current_stage_label": "Idle",
            "current_lane": "idle",
            "provider": "none",
            "brain": "none",
            "current_round": 0,
            "max_review_rounds": 0,
            "round_label": "r0 / r0",
            "rounds_remaining": 0,
            "required_reviewer_lane": "",
            "final_reviewer_lane": "",
            "landing_lane": "",
            "next_reviewer_lane": "",
            "allow_credit_burn": False,
            "allow_paid_fast_lane": False,
            "allow_core_rescue": False,
            "core_rescue_likely_next": False,
            "stop_reason": blocker_forecast.get("now") or "none",
            "next_reviewer_summary": "No reviewer is pending.",
            "landing_summary": "No landing lane is active.",
            "timeline": [
                {"id": "groundwork", "label": "Groundwork", "state": "current"},
                {"id": "review", "label": "Jury", "state": "pending"},
                {"id": "rework", "label": "Rework", "state": "pending"},
                {"id": "jury", "label": "Jury", "state": "pending"},
                {"id": "land", "label": "Land", "state": "pending"},
            ],
            "policy_summary": "No active cheap-loop slice is running right now.",
            "telemetry_review_loop": telemetry_review_loop,
            "telemetry_worker_utilization": telemetry_workers,
            "telemetry_summary": telemetry_summary,
        }

    workflow_kind = str(project.get("task_workflow_kind") or "default").strip().lower() or "default"
    stage = str(project.get("workflow_stage") or "").strip().lower() or "groundwork_pending"
    max_rounds = int(project.get("task_max_review_rounds") or 0)
    review_rounds_used = int(project.get("review_rounds_used") or 0)
    current_round = 0
    if max_rounds > 0:
        current_round = min(max_rounds, max(1, review_rounds_used or 1))
    required_lane = str(project.get("required_reviewer_lane") or "").strip().lower()
    final_lane = str(project.get("task_final_reviewer_lane") or required_lane or "").strip().lower()
    landing_lane = str(project.get("task_landing_lane") or final_lane or "").strip().lower()
    required_lane_label = "Jury" if required_lane == "jury" else ("Review Light" if required_lane == "review_light" else required_lane.title() or "Review")
    allow_credit_burn = bool(project.get("task_allow_credit_burn"))
    allow_paid_fast_lane = bool(project.get("task_allow_paid_fast_lane"))
    allow_core_rescue = bool(project.get("task_allow_core_rescue"))
    stage_to_index = {
        GROUNDWORK_PENDING_STATUS: 0,
        AWAITING_FIRST_REVIEW_STATUS: 1,
        REVIEW_LIGHT_PENDING_STATUS: 1,
        JURY_REWORK_REQUIRED_STATUS: 2,
        JURY_REVIEW_PENDING_STATUS: 3,
        CORE_RESCUE_PENDING_STATUS: 3,
        ACCEPTED_AFTER_ROUND_STATUSES["1"]: 4,
        ACCEPTED_AFTER_ROUND_STATUSES["2"]: 4,
        ACCEPTED_AFTER_ROUND_STATUSES["3"]: 4,
        ACCEPTED_AFTER_CORE_STATUS: 4,
    }
    current_index = stage_to_index.get(stage, 0)
    timeline: List[Dict[str, Any]] = []
    for index, (step_id, label) in enumerate(
        [
            ("groundwork", "Groundwork"),
            (required_lane or "review", required_lane_label),
            ("rework", "Rework"),
            ("jury", "Jury"),
            ("land", "Land"),
        ]
    ):
        state = "pending"
        if index < current_index:
            state = "done"
        elif index == current_index:
            state = "current"
        timeline.append({"id": step_id, "label": label, "state": state})
    if stage == JURY_REWORK_REQUIRED_STATUS:
        timeline[2]["state"] = "current"
        timeline[3]["state"] = "pending"
        timeline[4]["state"] = "pending"
    provider = str((queue_forecast.get("now") or {}).get("provider") or project.get("active_run_account_backend") or project.get("last_run_account_backend") or "unknown")
    brain = str((queue_forecast.get("now") or {}).get("brain") or project.get("active_run_brain") or project.get("last_run_brain") or "unknown")
    policy_bits = [
        f"landing via {landing_lane or 'none'}",
        "credit burn disabled" if not allow_credit_burn else "credit burn allowed",
        "paid fast lane disabled" if not allow_paid_fast_lane else "paid fast lane allowed",
        "core rescue explicit-only" if allow_core_rescue else "core rescue disabled",
    ]
    stage_labels = {
        GROUNDWORK_PENDING_STATUS: "Groundwork",
        AWAITING_FIRST_REVIEW_STATUS: required_lane_label,
        REVIEW_LIGHT_PENDING_STATUS: required_lane_label,
        JURY_REWORK_REQUIRED_STATUS: "Rework",
        JURY_REVIEW_PENDING_STATUS: "Jury",
        CORE_RESCUE_PENDING_STATUS: "Jury / Core Rescue",
        ACCEPTED_AFTER_ROUND_STATUSES["1"]: "Landing",
        ACCEPTED_AFTER_ROUND_STATUSES["2"]: "Landing",
        ACCEPTED_AFTER_ROUND_STATUSES["3"]: "Landing",
        ACCEPTED_AFTER_CORE_STATUS: "Landing",
    }
    return {
        "workflow_kind": workflow_kind,
        "active": True,
        "title": project.get("current_slice") or queue_forecast.get("now", {}).get("title") or project.get("id") or "Current slice",
        "project_id": project.get("id") or "",
        "current_stage": stage,
        "current_stage_label": stage_labels.get(stage, stage.replace("_", " ") or "Groundwork"),
        "current_lane": project.get("selected_lane") or queue_forecast.get("now", {}).get("lane") or "unknown",
        "provider": provider,
        "brain": brain,
        "current_round": current_round,
        "max_review_rounds": max_rounds,
        "round_label": (
            f"r{current_round} / r{max_rounds}" if max_rounds > 0 and current_round > 0 else "no review loop"
        ),
        "rounds_remaining": max(0, max_rounds - current_round) if max_rounds > 0 and current_round > 0 else 0,
        "required_reviewer_lane": required_lane,
        "final_reviewer_lane": final_lane,
        "landing_lane": landing_lane,
        "next_reviewer_lane": str(project.get("next_reviewer_lane") or "").strip().lower(),
        "allow_credit_burn": allow_credit_burn,
        "allow_paid_fast_lane": allow_paid_fast_lane,
        "allow_core_rescue": allow_core_rescue,
        "core_rescue_likely_next": bool(project.get("core_rescue_likely_next")),
        "stop_reason": blocker_forecast.get("now") or project.get("stop_reason") or "none",
        "next_reviewer_summary": f"next reviewer {str(project.get('next_reviewer_lane') or '').strip().lower() or 'n/a'}",
        "landing_summary": f"landing via {landing_lane or 'n/a'}",
        "timeline": timeline,
        "policy_summary": " · ".join(bit for bit in policy_bits if bit),
        "telemetry_review_loop": telemetry_review_loop,
        "telemetry_worker_utilization": telemetry_workers,
        "telemetry_summary": telemetry_summary,
    }


def group_cards_payload(status: Dict[str, Any]) -> List[Dict[str, Any]]:
    groups = status.get("groups") or []
    projects = status.get("projects") or []
    projects_by_group: Dict[str, List[Dict[str, Any]]] = {}
    for project in projects:
        for group_id in project.get("group_ids") or []:
            projects_by_group.setdefault(str(group_id), []).append(project)
    cards: List[Dict[str, Any]] = []
    for group in groups:
        group_id = str(group.get("id") or "")
        member_projects = projects_by_group.get(group_id, [])
        active_project = next(
            (
                project for project in member_projects
                if str(project.get("runtime_status") or "").strip().lower() in {"starting", "running", "verifying", READY_STATUS}
                and first_nonempty(project.get("current_slice"), project.get("next_action"))
            ),
            member_projects[0] if member_projects else {},
        )
        cards.append(
            {
                "group_id": group_id,
                "current_objective": first_nonempty(
                    (group.get("design_progress") or {}).get("summary"),
                    group.get("dispatch_basis"),
                    group.get("bottleneck"),
                    "No current objective recorded.",
                ),
                "current_slice": first_nonempty((active_project or {}).get("current_slice"), (active_project or {}).get("next_action"), "Queue not materialized"),
                "next_milestone_eta": ((group.get("milestone_eta") or {}).get("eta_human") or "unknown"),
                "program_eta": ((group.get("program_eta") or {}).get("eta_human") or "unknown"),
                "dispatchability": "dispatchable" if group.get("dispatch_ready") else "blocked",
                "design_truth_freshness": (
                    "compile attention"
                    if int(group.get("compile_attention_count") or 0) > 0
                    else "compiled"
                ),
                "blocker_count": len(group.get("dispatch_blockers") or []) + len(group.get("contract_blockers") or []),
                "review_debt": int(group.get("review_waiting_count") or 0) + int(group.get("review_blocking_count") or 0),
                "status": group.get("status") or "unknown",
                "phase": group.get("phase") or "unknown",
            }
        )
    return cards


def lane_runway_payload(
    status: Dict[str, Any],
    *,
    capacity_forecast: Dict[str, Any],
    execution_loop: Dict[str, Any],
) -> List[Dict[str, Any]]:
    active_project = mission_active_project(status, {"now": {"project_id": execution_loop.get("project_id")}})
    allowed_lanes = {str(item).strip().lower() for item in (active_project.get("allowed_lanes") or []) if str(item).strip()}
    mission_lanes = {
        str(execution_loop.get("current_lane") or "").strip().lower(),
        str(execution_loop.get("required_reviewer_lane") or "").strip().lower(),
        str(execution_loop.get("final_reviewer_lane") or "").strip().lower(),
        str(execution_loop.get("landing_lane") or "").strip().lower(),
        str(execution_loop.get("next_reviewer_lane") or "").strip().lower(),
        *allowed_lanes,
    }
    mission_lanes.discard("")
    payload: List[Dict[str, Any]] = []
    for item in capacity_forecast.get("lanes") or []:
        lane_name = str(item.get("lane") or "").strip().lower()
        policy_enabled = True
        policy_reason = "mission-ready"
        if lane_name == "core" and not bool(execution_loop.get("allow_credit_burn")):
            policy_enabled = False
            policy_reason = "credit burn disabled"
        elif lane_name == "repair" and not bool(execution_loop.get("allow_paid_fast_lane")):
            policy_enabled = False
            policy_reason = "paid fast lane disabled"
        elif lane_name == "survival" and execution_loop.get("workflow_kind") == WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
            policy_enabled = False
            policy_reason = "not on cheap loop"
        payload.append(
            {
                **item,
                "mission_enabled": lane_name in mission_lanes,
                "policy_enabled": policy_enabled,
                "policy_reason": policy_reason,
                "critical_path": lane_name == str(capacity_forecast.get("critical_path_lane") or "").strip().lower(),
            }
        )
    return payload


def mission_blockers_payload(
    status: Dict[str, Any],
    *,
    blocker_forecast: Dict[str, Any],
    attention: List[Dict[str, Any]],
    execution_loop: Dict[str, Any],
) -> Dict[str, Any]:
    items = [
        {
            "scope": "current slice",
            "detail": blocker_forecast.get("now") or "none",
        },
        {
            "scope": "next slice",
            "detail": blocker_forecast.get("next") or "none",
        },
        {
            "scope": "vision horizon",
            "detail": blocker_forecast.get("vision") or "none",
        },
    ]
    priority = [
        {
            "title": str(item.get("title") or item.get("scope_id") or "attention"),
            "detail": str(item.get("detail") or item.get("summary") or "").strip(),
            "scope": str(item.get("scope_id") or item.get("scope_type") or "").strip(),
        }
        for item in attention[:4]
    ]
    stop_detail = blocker_forecast.get("now") or blocker_forecast.get("vision") or "none"
    stop_sentence = (
        f"Work stops because {stop_detail}."
        if stop_detail and stop_detail != "none"
        else "Forever on trend."
    )
    if execution_loop.get("active") and not bool(execution_loop.get("allow_credit_burn")) and bool(execution_loop.get("core_rescue_likely_next")):
        stop_sentence = "Work stops because core rescue is the next escalation but credit burn is disabled."
    return {
        "items": items,
        "priority": priority,
        "stop_sentence": stop_sentence,
    }


def provider_credit_card_payload() -> Dict[str, Any]:
    payload = ea_codex_status(window="7d")
    aggregate = dict(payload.get("onemin_billing_aggregate") or {})
    if not aggregate:
        return {}
    basis_counts = dict(aggregate.get("basis_counts") or {})
    actual_slots = int(basis_counts.get("actual_billing_usage_page") or 0)
    estimated_slots = sum(
        int(value or 0)
        for key, value in basis_counts.items()
        if str(key or "").strip() and str(key or "").strip() != "actual_billing_usage_page"
    )
    if actual_slots > 0 and estimated_slots == 0:
        basis_quality = "actual"
    elif actual_slots > 0:
        basis_quality = "mixed"
    elif basis_counts:
        basis_quality = "estimated"
    else:
        basis_quality = "stale"
    return {
        "provider": "1min",
        "free_credits": aggregate.get("sum_free_credits"),
        "max_credits": aggregate.get("sum_max_credits"),
        "remaining_percent_total": aggregate.get("remaining_percent_total"),
        "next_topup_at": aggregate.get("next_topup_at"),
        "topup_amount": aggregate.get("topup_amount"),
        "hours_until_next_topup": aggregate.get("hours_until_next_topup"),
        "hours_remaining_at_current_pace_no_topup": aggregate.get("hours_remaining_at_current_pace_no_topup"),
        "hours_remaining_including_next_topup_at_current_pace": aggregate.get(
            "hours_remaining_including_next_topup_at_current_pace"
        ),
        "days_remaining_including_next_topup_at_7d_avg": aggregate.get("days_remaining_including_next_topup_at_7d_avg"),
        "depletes_before_next_topup": aggregate.get("depletes_before_next_topup"),
        "basis_quality": basis_quality,
        "basis_summary": aggregate.get("basis_summary") or "unknown",
        "slot_count_with_billing_snapshot": aggregate.get("slot_count_with_billing_snapshot"),
        "slot_count_with_member_reconciliation": aggregate.get("slot_count_with_member_reconciliation"),
        "latest_member_reconciliation_at": aggregate.get("latest_member_reconciliation_at"),
        "last_actual_balance_check_at": ((payload.get("topup_summary") or {}).get("last_actual_balance_check_at")),
    }


def mission_board_payload(
    status: Dict[str, Any],
    *,
    mission_snapshot: Dict[str, Any],
    queue_forecast: Dict[str, Any],
    vision_forecast: Dict[str, Any],
    capacity_forecast: Dict[str, Any],
    blocker_forecast: Dict[str, Any],
    attention: List[Dict[str, Any]],
) -> Dict[str, Any]:
    truth_freshness = truth_freshness_payload(status)
    execution_loop = execution_loop_payload(status, queue_forecast=queue_forecast, blocker_forecast=blocker_forecast)
    lane_runway = lane_runway_payload(status, capacity_forecast=capacity_forecast, execution_loop=execution_loop)
    blockers = mission_blockers_payload(status, blocker_forecast=blocker_forecast, attention=attention, execution_loop=execution_loop)
    provider_credit = provider_credit_card_payload()
    current_slice = {
        "title": execution_loop.get("title") or queue_forecast.get("now", {}).get("title") or "Idle",
        "lane": execution_loop.get("current_lane") or queue_forecast.get("now", {}).get("lane") or "idle",
        "provider": execution_loop.get("provider") or queue_forecast.get("now", {}).get("provider") or "none",
        "brain": execution_loop.get("brain") or queue_forecast.get("now", {}).get("brain") or "none",
        "eta": queue_forecast.get("now", {}).get("remaining_human") or mission_snapshot.get("current_eta") or "unknown",
        "review_ahead": "yes" if (queue_forecast.get("now", {}) or {}).get("verify_or_review_ahead") else "no",
        "stage": execution_loop.get("current_stage_label") or "Idle",
    }
    next_transition = {
        "title": queue_forecast.get("next", {}).get("title") or "No next slice materialized",
        "lane": queue_forecast.get("next", {}).get("lane") or "unknown",
        "confidence": queue_forecast.get("next", {}).get("confidence") or "unknown",
        "prerequisites": queue_forecast.get("next", {}).get("prerequisites") or "none",
        "reason": queue_forecast.get("next", {}).get("reason") or "No queue reason recorded.",
    }
    mission_horizon = {
        "milestone_title": vision_forecast.get("milestone_title") or mission_snapshot.get("milestone_title") or "unknown",
        "milestone_eta": vision_forecast.get("milestone_eta") or mission_snapshot.get("milestone_eta") or "unknown",
        "vision_eta_p50": vision_forecast.get("vision_eta_p50") or mission_snapshot.get("vision_eta") or "unknown",
        "vision_eta_p90": vision_forecast.get("vision_eta_p90") or "unknown",
        "confidence": vision_forecast.get("confidence") or "unknown",
    }
    capacity = {
        "critical_path_lane": capacity_forecast.get("critical_path_lane") or "unknown",
        "critical_path_stop": capacity_forecast.get("critical_path_stop") or "unknown",
        "mission_runway": capacity_forecast.get("mission_runway") or "unknown",
        "pool_runway": capacity_forecast.get("pool_runway") or "unknown",
        "next_reset_windows": next_reset_windows((status.get("config") or {}).get("spider") or {}, status.get("account_pools") or []),
    }
    return {
        "contract_name": MISSION_BOARD_CONTRACT_NAME,
        "contract_version": MISSION_BOARD_CONTRACT_VERSION,
        "surface_vocabulary": ["truth", "slice", "loop", "runway", "blockers", "landing"],
        "headline": mission_snapshot.get("headline") or "",
        "current_slice": current_slice,
        "next_transition": next_transition,
        "mission_horizon": mission_horizon,
        "capacity": capacity,
        "truth_freshness": truth_freshness,
        "execution_loop": execution_loop,
        "group_cards": group_cards_payload(status),
        "lane_runway": lane_runway,
        "provider_credit_card": provider_credit,
        "blockers": blockers,
    }


def deployment_posture_payload(status: Dict[str, Any]) -> Dict[str, Any]:
    targets: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def append_target(
        *,
        scope_type: str,
        scope_id: str,
        target_url: str,
        display: str,
        surface: str,
        status_text: str,
        promotion_stage: str,
        release_gate: str,
    ) -> None:
        clean_scope = str(scope_id or "").strip()
        clean_url = str(target_url or "").strip()
        if not clean_scope or not clean_url:
            return
        key = (scope_type, clean_scope, clean_url)
        if key in seen:
            return
        seen.add(key)
        targets.append(
            {
                "scope_type": scope_type,
                "scope_id": clean_scope,
                "target_url": clean_url,
                "display": str(display or clean_url).strip() or clean_url,
                "surface": str(surface or "").strip(),
                "status": str(status_text or "undeclared").strip(),
                "promotion_stage": str(promotion_stage or "undeclared").strip(),
                "release_gate": str(release_gate or "").strip(),
            }
        )

    for group in status.get("groups") or []:
        deployment = dict(group.get("deployment") or {})
        append_target(
            scope_type="group",
            scope_id=str(group.get("id") or ""),
            target_url=str(deployment.get("target_url") or ""),
            display=str(deployment.get("display") or ""),
            surface=str((deployment.get("targets") or [{}])[0].get("surface") or ""),
            status_text=str(deployment.get("status") or ""),
            promotion_stage=str(deployment.get("promotion_stage") or ""),
            release_gate=str(deployment.get("release_gate") or ""),
        )
        for target in deployment.get("targets") or []:
            append_target(
                scope_type="group",
                scope_id=str(group.get("id") or ""),
                target_url=str((target or {}).get("url") or ""),
                display=str((target or {}).get("name") or (target or {}).get("url") or ""),
                surface=str((target or {}).get("surface") or ""),
                status_text=str((target or {}).get("status") or deployment.get("status") or ""),
                promotion_stage=str(deployment.get("promotion_stage") or ""),
                release_gate=str(deployment.get("release_gate") or ""),
            )
    for project in status.get("projects") or []:
        deployment = dict(project.get("deployment") or {})
        append_target(
            scope_type="project",
            scope_id=str(project.get("id") or ""),
            target_url=str(deployment.get("target_url") or ""),
            display=str(deployment.get("display") or ""),
            surface=str(deployment.get("surface") or ""),
            status_text=str(deployment.get("status") or ""),
            promotion_stage=str(deployment.get("promotion_stage") or ""),
            release_gate=str(deployment.get("release_gate") or ""),
        )

    return {
        "operator_auth_required": operator_auth_enabled(),
        "login_path": "/admin/login" if operator_auth_enabled() else "",
        "dashboard_path": "/dashboard/",
        "command_deck_path": "/admin",
        "explorer_path": "/admin/details",
        "studio_path": "/studio",
        "public_target_count": len(targets),
        "public_targets": targets[:12],
    }


def canonical_public_status_payload(status: Dict[str, Any]) -> Dict[str, Any]:
    cockpit = status.get("cockpit") or {}
    summary = cockpit.get("summary") or {}
    public_projects: List[Dict[str, Any]] = []
    for project in status.get("projects", []):
        public_projects.append(
            {
                "id": project.get("id"),
                "current_slice": project.get("current_slice"),
                "runtime_status": project.get("runtime_status") or project.get("status_internal") or project.get("status"),
                "selected_lane": project.get("selected_lane"),
                "next_reviewer_lane": project.get("next_reviewer_lane"),
                "required_reviewer_lane": project.get("required_reviewer_lane"),
                "task_final_reviewer_lane": project.get("task_final_reviewer_lane"),
                "task_landing_lane": project.get("task_landing_lane"),
                "task_workflow_kind": project.get("task_workflow_kind"),
                "review_rounds_used": project.get("review_rounds_used"),
                "task_max_review_rounds": project.get("task_max_review_rounds"),
                "task_allow_credit_burn": project.get("task_allow_credit_burn"),
                "task_allow_paid_fast_lane": project.get("task_allow_paid_fast_lane"),
                "task_allow_core_rescue": project.get("task_allow_core_rescue"),
                "sustainable_runway": project.get("sustainable_runway"),
                "decision_meta_summary": project.get("decision_meta_summary"),
                "deployment": project.get("deployment") or {},
            }
        )
    public_groups: List[Dict[str, Any]] = []
    for group in status.get("groups", []):
        public_groups.append(
            {
                "id": group.get("id"),
                "phase": group.get("phase"),
                "pressure_state": group.get("pressure_state"),
                "dispatch_basis": group.get("dispatch_basis"),
                "lifecycle": group.get("lifecycle"),
                "projects": group.get("projects"),
                "deployment": group.get("deployment") or {},
            }
        )
    return {
        "contract_name": PUBLIC_STATUS_CONTRACT_NAME,
        "contract_version": PUBLIC_STATUS_CONTRACT_VERSION,
        "generated_at": status.get("generated_at"),
        "summary": {
            "mission_headline": summary.get("mission_headline") or ((cockpit.get("mission_snapshot") or {}).get("headline") or ""),
            "fleet_health": summary.get("fleet_health") or "unknown",
            "scheduler_posture": summary.get("scheduler_posture") or "unknown",
            "blocked_groups": int(summary.get("blocked_groups") or 0),
            "open_incidents": int(summary.get("open_incidents") or 0),
            "review_waiting_projects": int(summary.get("review_waiting_projects") or 0),
            "recommended_action": summary.get("recommended_action") or "",
        },
        "mission_board": cockpit.get("mission_board", {}),
        "mission_snapshot": cockpit.get("mission_snapshot", {}),
        "queue_forecast": cockpit.get("queue_forecast", {}),
        "vision_forecast": cockpit.get("vision_forecast", {}),
        "capacity_forecast": cockpit.get("capacity_forecast", {}),
        "blocker_forecast": cockpit.get("blocker_forecast", {}),
        "deployment_posture": deployment_posture_payload(status),
        "projects": public_projects,
        "groups": public_groups,
    }


def cockpit_payload_from_status(status: Dict[str, Any]) -> Dict[str, Any]:
    projects = status.get("projects") or status["config"].get("projects", [])
    groups = status.get("groups") or status["config"].get("groups", [])
    account_pools = status.get("account_pools") or []
    ops = status.get("ops_summary") or {}
    spider = status["config"].get("spider") or {}
    auditor = status.get("auditor") or {}
    attention = build_attention_items(status)
    workers = build_worker_cards(status)
    runway = build_runway_model(status)
    operators = build_operator_cards(status, workers=workers, runway=runway)
    approvals = build_approval_center(status)
    lamps = build_lamp_items(status)
    lane_capacities = ea_lane_capacity_snapshot((status.get("config") or {}).get("lanes") or {})
    queue_forecast = queue_forecast_payload(status, workers=workers)
    mission_snapshot = mission_forecast_payload(status, queue_forecast=queue_forecast, lane_capacities=lane_capacities)
    vision_forecast = vision_forecast_payload(status, queue_forecast=queue_forecast)
    capacity_forecast = capacity_forecast_payload(status, lane_capacities=lane_capacities, runway=runway)
    blocker_forecast = blocker_forecast_payload(status, queue_forecast=queue_forecast, attention=attention, lamps=lamps)
    mission_board = mission_board_payload(
        status,
        mission_snapshot=mission_snapshot,
        queue_forecast=queue_forecast,
        vision_forecast=vision_forecast,
        capacity_forecast=capacity_forecast,
        blocker_forecast=blocker_forecast,
        attention=attention,
    )
    worker_breakdown = build_worker_breakdown(status)
    posture = scheduler_posture(ops, groups, account_pools)
    summary = {
        "fleet_health": "ok",
        "scheduler_posture": posture,
        "blocked_groups": len(ops.get("group_blockers") or []),
        "open_incidents": int(ops.get("open_incident_count") or len(status.get("incidents") or [])),
        "review_failed_incidents": len(ops.get("review_failed_incidents") or []),
        "review_stalled_incidents": len(ops.get("review_stalled_incidents") or []),
        "blocked_unresolved_incidents": len(ops.get("blocked_unresolved_incidents") or []),
        "review_waiting_projects": len(ops.get("prs_waiting_for_review") or []),
        "queue_exhausted_projects": len(ops.get("queue_exhausted_projects") or []),
        "coverage_pressure_projects": len(ops.get("coverage_pressure_projects") or []),
        "audit_required_groups": len(ops.get("audit_required_groups") or []),
        "approvals_waiting": len(approvals),
        "active_workers": worker_breakdown["active_workers"],
        "active_coding_workers": worker_breakdown["active_coding_workers"],
        "active_review_workers": worker_breakdown.get("active_review_workers", 0),
        "queued_review_workers": worker_breakdown.get("queued_review_workers", worker_breakdown["review_wait_workers"]),
        "review_wait_workers": worker_breakdown["review_wait_workers"],
        "review_pressure_workers": worker_breakdown.get("review_pressure_workers", worker_breakdown["review_wait_workers"]),
        "healing_workers": worker_breakdown["healing_workers"],
        "notifications": len(status.get("notifications") or []),
        "next_reset_windows": next_reset_windows(spider, account_pools),
        "recommended_action": (attention[0]["title"] if attention else (approvals[0]["title"] if approvals else "No urgent action right now")),
        "auditor_last_run": (auditor.get("last_run") or {}).get("finished_at") or (auditor.get("last_run") or {}).get("started_at"),
        "auto_heal_enabled": auto_heal_enabled(status),
        "auto_heal_categories": auto_heal_categories(status),
        "mission_headline": mission_snapshot.get("headline") or "",
    }
    return {
        "summary": summary,
        "mission_board": mission_board,
        "mission_snapshot": mission_snapshot,
        "queue_forecast": queue_forecast,
        "vision_forecast": vision_forecast,
        "capacity_forecast": capacity_forecast,
        "blocker_forecast": blocker_forecast,
        "lane_capacities": lane_capacities,
        "operators": operators,
        "lamps": lamps,
        "attention": attention,
        "workers": workers,
        "worker_breakdown": worker_breakdown,
        "approvals": approvals,
        "runway": runway,
        "generated_at": status.get("generated_at") or iso(utc_now()),
    }


def admin_status_payload() -> Dict[str, Any]:
    config = normalize_config()
    consistency_warnings = config_consistency_warnings(config)
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
        group_row["dispatch_member_count"] = len([project for project in group_projects if project_dispatch_participates(project)])
        group_row["scaffold_member_count"] = len([project for project in group_projects if normalize_lifecycle_state(project.get("lifecycle"), "dispatchable") == "scaffold"])
        group_row["signoff_only_member_count"] = len([project for project in group_projects if normalize_lifecycle_state(project.get("lifecycle"), "dispatchable") == "signoff_only"])
        group_row["compile_attention_count"] = sum(
            1 for project in group_projects if str((project.get("compile_health") or {}).get("status") or "") not in {"ready", "not_required"}
        )
        group_row["captain"] = group_captain_policy(group_cfg)
        group_row["deployment"] = normalize_group_deployment(group_cfg.get("deployment"))
        group_row["signed_off"] = group_is_signed_off(group_meta)
        group_row["signoff_state"] = str(group_meta.get("signoff_state") or ("signed_off" if group_row["signed_off"] else "open"))
        group_row["signed_off_at"] = group_meta.get("signed_off_at")
        group_row["reopened_at"] = group_meta.get("reopened_at")
        group_row["last_audit_requested_at"] = group_meta.get("last_audit_requested_at")
        group_row["last_refill_requested_at"] = group_meta.get("last_refill_requested_at")
        group_row["contract_blockers"] = text_items(group_meta.get("contract_blockers"))
        group_row["remaining_milestones"] = remaining_milestone_items(group_meta)
        group_row["modeled_uncovered_scope"] = text_items(group_meta.get("uncovered_scope"))
        group_row["modeled_uncovered_scope_count"] = len(group_row["modeled_uncovered_scope"])
        group_row["uncovered_scope"] = group_actionable_uncovered_scope(
            str(group_cfg.get("id") or ""),
            group_row["modeled_uncovered_scope"],
            group_projects,
        )
        group_row["uncovered_scope_count"] = len(group_row["uncovered_scope"])
        group_row["milestone_coverage_complete"] = bool(group_meta.get("milestone_coverage_complete"))
        group_row["design_coverage_complete"] = bool(group_meta.get("design_coverage_complete"))
        group_row.update(group_dispatch_state(group_cfg, group_meta, group_projects, now))
        group_row["dispatch_blockers_internal"] = list(group_row.get("dispatch_blockers") or [])
        group_row["dispatch_blockers"] = operator_relevant_dispatch_blockers(group_row.get("dispatch_blockers_internal") or [])
        group_row["status"] = effective_group_status(group_cfg, group_meta, group_projects)
        group_row["phase"] = derive_group_phase(group_row, group_projects)
        group_row["project_statuses"] = [{"id": project["id"], "status": project["runtime_status"]} for project in group_projects]
        group_row["review_waiting_count"] = sum(
            1 for project in group_projects if str((project.get("pull_request") or {}).get("review_status") or "") in REVIEW_WAITING_STATUSES
        )
        group_row["review_blocking_count"] = sum(
            int((project.get("review_findings") or {}).get("blocking_count") or 0) for project in group_projects
        )
        group_row["allowance_usage"] = recent_usage_for_scope([project["id"] for project in group_projects], usage_start)
        group_row["pool_sufficiency"] = group_pool_sufficiency(config, group_cfg, group_projects, now)
        group_row["bottleneck"] = "; ".join((group_row.get("contract_blockers") or [])[:1] + (group_row.get("dispatch_blockers") or [])[:1]) or str(group_row.get("dispatch_basis") or "")
        group_row["remaining_slices"] = int(((group_row.get("pool_sufficiency") or {}).get("remaining_slices") or 0))
        group_row["pressure_state"] = group_pressure_state(group_row, group_projects)
        group_row["ready_project_ids"] = group_ready_project_ids(group_projects)
        group_row["ready_project_count"] = len(group_row["ready_project_ids"])
        group_row["auditor_task_counts"] = group_auditor_task_counts(str(group_row.get("id") or ""), group_projects)
        group_row["auditor_can_solve"] = bool(
            int((group_row["auditor_task_counts"] or {}).get("open") or 0)
            or int((group_row["auditor_task_counts"] or {}).get("approved") or 0)
        )
        group_row["incidents"] = group_open_incidents(group_row, group_projects)
        group_row["open_incident_count"] = len(group_row["incidents"])
        group_row["operator_question"] = group_operator_question(group_row, group_projects)
        group_row["notification"] = group_notification_payload(group_row, group_projects)
        group_row["notification_needed"] = bool((group_row.get("notification") or {}).get("needed"))
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
        active_group_workers = sum(1 for project in group_projects if project_has_live_worker(project))
        design_uncovered_scope_count = max(
            int(group_row.get("uncovered_scope_count") or 0),
            int(group_row.get("modeled_uncovered_scope_count") or 0),
        )
        group_row["design_progress"] = design_progress_payload(
            meta=group_meta,
            runtime_status=str(group_row.get("status") or ""),
            uncovered_scope_count=design_uncovered_scope_count,
            project_ids=[str(project.get("id") or "") for project in group_projects],
            active_workers=active_group_workers,
            now=now,
        )
        group_row["program_eta"] = dict(group_row["design_progress"].get("eta") or {})
        group_row["design_eta"] = dict(group_row["design_progress"].get("eta") or {})
        group_row["delivery_progress"] = delivery_progress_payload_for_group(group_projects)
        if (
            str(group_row.get("status") or "") in {"group_blocked", "contract_blocked"}
            and active_group_workers <= 0
            and int((group_row.get("delivery_progress") or {}).get("percent_blocked") or 0) <= 0
            and int((group_row.get("delivery_progress") or {}).get("percent_inflight") or 0) > 0
        ):
            group_row["delivery_progress"]["percent_blocked"] = int(group_row["delivery_progress"].get("percent_inflight") or 0)
            group_row["delivery_progress"]["percent_inflight"] = 0
        groups.append(group_row)
    notifications = sorted(
        [dict(group.get("notification") or {}, group_id=group.get("id")) for group in groups if group.get("notification_needed")],
        key=lambda item: (
            0 if str(item.get("severity") or "") in {"critical", "high"} else 1,
            -int(item.get("incident_count") or 0),
            -int(item.get("ready_project_count") or 0),
            str(item.get("group_id") or ""),
        ),
    )
    account_pools = account_pool_rows(config)
    findings = audit_findings()
    task_candidates = audit_task_candidates()
    config = normalize_config()
    project_map = {str(project.get("id") or ""): project for project in (config.get("projects") or [])}
    pr_rows = [
        normalized_pull_request_row(project_map.get(str(row.get("project_id") or ""), {}), row)
        for row in pull_request_rows().values()
    ]
    github_review_rows = review_findings()
    recent_run_rows = recent_runs()
    recent_decision_rows = recent_decisions()
    open_incident_rows = filter_runtime_relevant_incidents(incidents(status="open", limit=400), projects)
    payload = {
        "projects": projects,
        "groups": groups,
        "notifications": notifications,
        "incidents": open_incident_rows,
        "config": {
            "schema_version": config.get("schema_version"),
            "policies": config.get("policies", {}),
            "spider": config.get("spider", {}),
            "projects": projects,
            "groups": groups,
            "accounts": config.get("accounts", {}),
            "lanes": config.get("lanes", {}),
        },
        "config_warnings": consistency_warnings,
        "account_pools": account_pools,
        "auditor": {
            "last_run": recent_auditor_run(),
            "findings": findings,
            "task_candidates": task_candidates,
        },
        "pull_requests": pr_rows,
        "review_findings": github_review_rows,
        "studio_publish_events": studio_publish_events(),
        "group_publish_events": group_publish_events(),
        "group_runs": group_runs(),
        "recent_runs": recent_run_rows,
        "recent_decisions": recent_decision_rows,
        "ops_summary": summarize_ops(projects, groups, account_pools, findings, recent_run_rows),
        "generated_at": iso(utc_now()),
    }
    payload["cockpit"] = cockpit_payload_from_status(payload)
    payload["public_status"] = canonical_public_status_payload(payload)
    payload["summary"] = payload["cockpit"].get("summary", {})
    payload["fleet_health"] = payload["summary"].get("fleet_health")
    payload["lamps"] = payload["cockpit"].get("lamps", [])
    payload["attention"] = payload["cockpit"].get("attention", [])
    payload["workers"] = payload["cockpit"].get("workers", [])
    payload["runway"] = payload["cockpit"].get("runway", {})
    return payload


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login(next: Optional[str] = None) -> str:
    target = safe_next_path(next, "/admin")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Fleet Operator Login</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #0b1220;
        color: #e5edf8;
        font: 16px/1.45 system-ui, sans-serif;
      }}
      .card {{
        width: min(26rem, calc(100vw - 2rem));
        padding: 1.5rem;
        border-radius: 16px;
        background: #111a2c;
        border: 1px solid #24324d;
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
      }}
      h1 {{ margin: 0 0 0.5rem; font-size: 1.35rem; }}
      p {{ margin: 0 0 1rem; color: #aab8d1; }}
      label {{ display: block; margin-bottom: 0.4rem; font-weight: 600; }}
      input {{
        width: 100%;
        box-sizing: border-box;
        padding: 0.8rem 0.9rem;
        border-radius: 10px;
        border: 1px solid #314261;
        background: #09111f;
        color: #f3f7ff;
      }}
      button {{
        margin-top: 1rem;
        width: 100%;
        padding: 0.85rem 1rem;
        border: 0;
        border-radius: 10px;
        background: #60a5fa;
        color: #08111f;
        font-weight: 700;
        cursor: pointer;
      }}
      .muted {{ font-size: 0.9rem; color: #94a3b8; }}
    </style>
  </head>
  <body>
    <form class="card" method="post" action="/admin/login">
      <h1>Fleet operator login</h1>
      <p>Authenticate once to use the bridge, admin console, and studio.</p>
      <input type="hidden" name="next" value="{html.escape(target)}" />
      <label for="password">Operator password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required autofocus />
      <button type="submit">Sign in</button>
      <p class="muted">User: {html.escape(OPERATOR_USER)}</p>
    </form>
  </body>
</html>"""


@app.post("/admin/login")
def admin_login_submit(password: str = Form(...), next: str = Form("/admin")) -> Response:
    if operator_auth_enabled() and not hmac.compare_digest(str(password or ""), OPERATOR_PASSWORD):
        raise HTTPException(status_code=401, detail="invalid operator password")
    target = safe_next_path(next, "/admin")
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        key=OPERATOR_COOKIE_NAME,
        value=operator_session_value(),
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/admin/logout")
def admin_logout(next: str = Form("/admin/login")) -> Response:
    target = safe_next_path(next, "/admin/login")
    response = RedirectResponse(target, status_code=303)
    response.delete_cookie(OPERATOR_COOKIE_NAME, path="/")
    return response


def status_surface_payload(status: Dict[str, Any]) -> Dict[str, Any]:
    cockpit = status.get("cockpit") or {}
    public_status = status.get("public_status") or canonical_public_status_payload(status)
    return {
        **status,
        "explorer": cockpit,
        "public_status": public_status,
        "mission_board": public_status.get("mission_board", {}),
        "mission_snapshot": public_status.get("mission_snapshot", {}),
        "queue_forecast": public_status.get("queue_forecast", {}),
        "vision_forecast": public_status.get("vision_forecast", {}),
        "capacity_forecast": public_status.get("capacity_forecast", {}),
        "blocker_forecast": public_status.get("blocker_forecast", {}),
    }


def public_dashboard_status_payload() -> Dict[str, Any]:
    return status_surface_payload(admin_status_payload()).get("public_status", {})


@app.get("/api/admin/status")
def api_admin_status() -> Dict[str, Any]:
    return status_surface_payload(admin_status_payload())


@app.get("/api/public/status")
def api_public_status() -> Dict[str, Any]:
    return public_dashboard_status_payload()


@app.get("/api/cockpit/status")
def api_cockpit_status() -> Dict[str, Any]:
    status = status_surface_payload(admin_status_payload())
    return {
        "generated_at": status.get("generated_at"),
        "public_status": status.get("public_status", {}),
        "cockpit": status.get("cockpit", {}),
        "explorer": status.get("explorer", {}),
        "mission_board": status.get("mission_board", {}),
        "mission_snapshot": status.get("mission_snapshot", {}),
        "queue_forecast": status.get("queue_forecast", {}),
        "vision_forecast": status.get("vision_forecast", {}),
        "capacity_forecast": status.get("capacity_forecast", {}),
        "blocker_forecast": status.get("blocker_forecast", {}),
        "incidents": status.get("incidents", []),
        "ops_summary": status.get("ops_summary", {}),
        "lanes": (((status.get("config") or {}).get("lanes")) or {}),
        "config": {
            "schema_version": (status.get("config") or {}).get("schema_version"),
            "policies": ((status.get("config") or {}).get("policies") or {}),
            "spider": {
                "classification_mode": (((status.get("config") or {}).get("spider") or {}).get("classification_mode") or ""),
            },
        },
        "groups": [
            {
                "id": group.get("id"),
                "status": group.get("status"),
                "lifecycle": group.get("lifecycle"),
                "projects": group.get("projects"),
                "dispatch_member_count": group.get("dispatch_member_count"),
                "scaffold_member_count": group.get("scaffold_member_count"),
                "signoff_only_member_count": group.get("signoff_only_member_count"),
                "compile_attention_count": group.get("compile_attention_count"),
                "design_progress": group.get("design_progress"),
                "design_eta": group.get("design_eta"),
                "delivery_progress": group.get("delivery_progress"),
                "uncovered_scope_count": group.get("uncovered_scope_count"),
                "dispatch_basis": group.get("dispatch_basis"),
                "pressure_state": group.get("pressure_state"),
                "phase": group.get("phase"),
            }
            for group in status.get("groups", [])
        ],
        "projects": [
            {
                "id": project.get("id"),
                "runtime_status": project.get("runtime_status"),
                "lifecycle": project.get("lifecycle"),
                "group_ids": project.get("group_ids"),
                "dispatch_participant": project.get("dispatch_participant"),
                "compile": project.get("compile"),
                "compile_health": project.get("compile_health"),
                "review_eta": project.get("review_eta"),
                "current_slice": project.get("current_slice"),
                "allowed_lanes": project.get("allowed_lanes"),
                "required_reviewer_lane": project.get("required_reviewer_lane"),
                "task_final_reviewer_lane": project.get("task_final_reviewer_lane"),
                "task_landing_lane": project.get("task_landing_lane"),
                "active_reviewer_lane": project.get("active_reviewer_lane"),
                "selected_lane": project.get("selected_lane"),
                "selected_lane_submode": project.get("selected_lane_submode"),
                "selected_lane_reason": project.get("selected_lane_reason"),
                "selected_lane_capacity_state": project.get("selected_lane_capacity_state"),
                "selected_lane_capacity_remaining_percent": project.get("selected_lane_capacity_remaining_percent"),
                "decision_meta_summary": project.get("decision_meta_summary"),
                "selection_trace_summary": project.get("selection_trace_summary"),
                "task_difficulty": project.get("task_difficulty"),
                "task_risk_level": project.get("task_risk_level"),
                "task_branch_policy": project.get("task_branch_policy"),
                "task_acceptance_level": project.get("task_acceptance_level"),
                "task_budget_class": project.get("task_budget_class"),
                "task_latency_class": project.get("task_latency_class"),
                "task_workflow_kind": project.get("task_workflow_kind"),
                "task_max_review_rounds": project.get("task_max_review_rounds"),
                "task_first_review_required": project.get("task_first_review_required"),
                "task_jury_acceptance_required": project.get("task_jury_acceptance_required"),
                "task_allow_credit_burn": project.get("task_allow_credit_burn"),
                "task_allow_paid_fast_lane": project.get("task_allow_paid_fast_lane"),
                "task_allow_core_rescue": project.get("task_allow_core_rescue"),
                "task_core_rescue_after_round": project.get("task_core_rescue_after_round"),
                "workflow_stage": project.get("workflow_stage"),
                "review_rounds_used": project.get("review_rounds_used"),
                "first_review_complete": project.get("first_review_complete"),
                "accepted_on_round": project.get("accepted_on_round"),
                "next_reviewer_lane": project.get("next_reviewer_lane"),
                "core_rescue_likely_next": project.get("core_rescue_likely_next"),
                "allowance_burn_by_lane": project.get("allowance_burn_by_lane"),
                "allowance_percent_by_lane": project.get("allowance_percent_by_lane"),
                "sustainable_runway": project.get("sustainable_runway"),
                "last_review_feedback": ((project.get("pull_request") or {}).get("last_review_feedback") or {}),
                "stop_reason": project.get("stop_reason"),
                "next_action": project.get("next_action"),
                "design_progress": project.get("design_progress"),
                "design_eta": project.get("design_eta"),
                "delivery_progress": project.get("delivery_progress"),
                "uncovered_scope_count": project.get("uncovered_scope_count"),
                "active_run_account_alias": project.get("active_run_account_alias"),
                "active_run_account_backend": project.get("active_run_account_backend"),
                "active_run_account_identity": project.get("active_run_account_identity"),
                "active_run_model": project.get("active_run_model"),
                "active_run_brain": project.get("active_run_brain"),
                "last_run_account_alias": project.get("last_run_account_alias"),
                "last_run_account_backend": project.get("last_run_account_backend"),
                "last_run_account_identity": project.get("last_run_account_identity"),
                "last_run_model": project.get("last_run_model"),
                "last_run_brain": project.get("last_run_brain"),
                "last_run_finished_at": project.get("last_run_finished_at"),
            }
            for project in status.get("projects", [])
        ],
    }


@app.get("/api/cockpit/summary")
def api_cockpit_summary() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("summary", {})


@app.get("/api/cockpit/mission-snapshot")
def api_cockpit_mission_snapshot() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("mission_snapshot", {})


@app.get("/api/cockpit/mission-board")
def api_cockpit_mission_board() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("mission_board", {})


@app.get("/api/cockpit/queue-forecast")
def api_cockpit_queue_forecast() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("queue_forecast", {})


@app.get("/api/cockpit/vision-forecast")
def api_cockpit_vision_forecast() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("vision_forecast", {})


@app.get("/api/cockpit/capacity-forecast")
def api_cockpit_capacity_forecast() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("capacity_forecast", {})


@app.get("/api/cockpit/blocker-forecast")
def api_cockpit_blocker_forecast() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("blocker_forecast", {})


@app.get("/api/cockpit/attention")
def api_cockpit_attention() -> List[Dict[str, Any]]:
    return admin_status_payload().get("cockpit", {}).get("attention", [])


@app.get("/api/cockpit/workers")
def api_cockpit_workers() -> List[Dict[str, Any]]:
    return admin_status_payload().get("cockpit", {}).get("workers", [])


@app.get("/api/cockpit/lamps")
def api_cockpit_lamps() -> List[Dict[str, Any]]:
    return admin_status_payload().get("cockpit", {}).get("lamps", [])


@app.get("/api/cockpit/runway")
def api_cockpit_runway() -> Dict[str, Any]:
    return admin_status_payload().get("cockpit", {}).get("runway", {})


@app.get("/api/cockpit/simulation")
def api_cockpit_simulation(group_id: str, action: str = "protect") -> Dict[str, Any]:
    return cockpit_simulation(admin_status_payload(), group_id, action)


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
            "sandbox": "danger-full-access",
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
    if auth_status == "ready":
        accounts = dict(config.get("accounts", {}) or {})
        if alias in accounts:
            account_row = dict(accounts.get(alias) or {})
            configured_state = str(account_row.get("health_state", "ready") or "ready").strip().lower()
            if configured_state == "auth_stale":
                account_row["health_state"] = "ready"
                accounts[alias] = account_row
                save_accounts_config(accounts)
    update_account_runtime(alias, clear_last_error=(auth_status == "ready"), last_error=None if auth_status == "ready" else auth_status)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/routing/update")
def api_admin_update_routing(
    classification_mode: str = Form("evidence_v1"),
    feedback_file_window: str = Form("2"),
    escalate_to_complex_after_failures: str = Form("2"),
    token_alliance_window_hours: str = Form("24"),
) -> RedirectResponse:
    config = normalize_config()
    spider = dict(config.get("spider", {}) or {})
    spider["classification_mode"] = str(classification_mode or "evidence_v1").strip() or "evidence_v1"
    spider["feedback_file_window"] = max(0, int(parse_optional_int(feedback_file_window, default=2) or 2))
    spider["escalate_to_complex_after_failures"] = max(1, int(parse_optional_int(escalate_to_complex_after_failures, default=2) or 2))
    spider["token_alliance_window_hours"] = max(1, int(parse_optional_int(token_alliance_window_hours, default=24) or 24))
    config["spider"] = spider
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/policies/auto-heal")
def api_admin_update_auto_heal(enabled: str = Form("0")) -> RedirectResponse:
    config = normalize_config()
    policies = dict(config.get("policies", {}) or {})
    policies["auto_heal_enabled"] = str(enabled or "").strip() in {"1", "true", "yes", "on"}
    config["policies"] = policies
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/policies/auto-heal/category/{category}")
def api_admin_update_auto_heal_category(category: str, enabled: str = Form("0")) -> RedirectResponse:
    clean_category = str(category or "").strip().lower()
    if clean_category not in AUTO_HEAL_CATEGORIES:
        raise HTTPException(400, "unknown auto-heal category")
    config = normalize_config()
    policies = dict(config.get("policies", {}) or {})
    auto_heal = dict(policies.get("auto_heal") or {})
    categories = dict(auto_heal.get("categories") or {})
    categories[clean_category] = str(enabled or "").strip() in {"1", "true", "yes", "on"}
    auto_heal["categories"] = categories
    policies["auto_heal"] = auto_heal
    config["policies"] = policies
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/policies/auto-heal/escalation/{category}")
def api_admin_update_auto_heal_escalation_threshold(category: str, attempts: str = Form("0")) -> RedirectResponse:
    clean_category = str(category or "").strip().lower()
    if clean_category not in AUTO_HEAL_CATEGORIES:
        raise HTTPException(400, "unknown auto-heal category")
    config = normalize_config()
    policies = dict(config.get("policies", {}) or {})
    auto_heal = dict(policies.get("auto_heal") or {})
    thresholds = dict(auto_heal.get("escalation_thresholds") or {})
    thresholds[clean_category] = max(0, int(parse_optional_int(attempts, default=0) or 0))
    auto_heal["escalation_thresholds"] = thresholds
    policies["auto_heal"] = auto_heal
    config["policies"] = policies
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/policies/auto-heal/category/{category}/resolve-now")
def api_admin_resolve_auto_heal_category_now(category: str) -> RedirectResponse:
    clean_category = str(category or "").strip().lower()
    if clean_category not in AUTO_HEAL_CATEGORIES:
        raise HTTPException(400, "unknown auto-heal category")
    status = admin_status_payload()
    if clean_category == "review":
        for project in status.get("ops_summary", {}).get("prs_waiting_for_review") or []:
            project_id = str(project.get("id") or "").strip()
            if not project_id:
                continue
            if review_request_stalled(project, status):
                trigger_controller_post(f"/api/projects/{project_id}/review/request")
            else:
                trigger_controller_post(f"/api/projects/{project_id}/review/sync")
        for incident in status.get("incidents") or []:
            if incident_auto_heal_category(incident) != "review":
                continue
            project_id = str(incident.get("scope_id") or "").strip()
            if project_id:
                trigger_controller_post(f"/api/projects/{project_id}/review/sync")
        return RedirectResponse("/admin", status_code=303)

    if clean_category == "coverage":
        for group in status.get("groups") or []:
            group_id = str(group.get("id") or "").strip()
            if not group_id:
                continue
            if int((group.get("auditor_task_counts") or {}).get("approved") or 0) > 0:
                publish_group_approved_tasks(group_id, queue_mode="append")
        trigger_auditor_run()
        return RedirectResponse("/admin", status_code=303)

    if clean_category in {"capacity", "contracts"}:
        trigger_auditor_run()
        return RedirectResponse("/admin", status_code=303)

    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/auto-heal")
def api_admin_update_project_auto_heal(
    project_id: str,
    enabled: str = Form("0"),
    coverage: Optional[str] = Form(None),
    review: Optional[str] = Form(None),
    capacity: Optional[str] = Form(None),
    contracts: Optional[str] = Form(None),
) -> RedirectResponse:
    config = normalize_config()
    if not any(str(project.get("id") or "") == project_id for project in config.get("projects") or []):
        raise HTTPException(404, f"unknown project: {project_id}")
    policies = dict(config.get("policies") or {})
    auto_heal = dict(policies.get("auto_heal") or {})
    projects = dict(auto_heal.get("projects") or {})
    projects[project_id] = {
        "enabled": str(enabled or "").strip() in {"1", "true", "yes", "on"},
        "categories": {
            "coverage": coverage is not None,
            "review": review is not None,
            "capacity": capacity is not None,
            "contracts": contracts is not None,
        },
    }
    auto_heal["projects"] = projects
    policies["auto_heal"] = auto_heal
    config["policies"] = policies
    save_fleet_config(config)
    return RedirectResponse("/admin/details#settings", status_code=303)


@app.post("/api/admin/groups/{group_id}/auto-heal")
def api_admin_update_group_auto_heal(
    group_id: str,
    enabled: str = Form("0"),
    coverage: Optional[str] = Form(None),
    review: Optional[str] = Form(None),
    capacity: Optional[str] = Form(None),
    contracts: Optional[str] = Form(None),
) -> RedirectResponse:
    config = normalize_config()
    if not any(str(group.get("id") or "") == group_id for group in config.get("project_groups") or []):
        raise HTTPException(404, f"unknown group: {group_id}")
    policies = dict(config.get("policies") or {})
    auto_heal = dict(policies.get("auto_heal") or {})
    groups = dict(auto_heal.get("groups") or {})
    groups[group_id] = {
        "enabled": str(enabled or "").strip() in {"1", "true", "yes", "on"},
        "categories": {
            "coverage": coverage is not None,
            "review": review is not None,
            "capacity": capacity is not None,
            "contracts": contracts is not None,
        },
    }
    auto_heal["groups"] = groups
    policies["auto_heal"] = auto_heal
    config["policies"] = policies
    save_fleet_config(config)
    return RedirectResponse("/admin/details#settings", status_code=303)


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
    update_project_runtime(project_id, status=READY_STATUS, clear_cooldown=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/clear-cooldown")
def api_admin_clear_cooldown(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, clear_cooldown=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/retry")
def api_admin_retry_project(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, status=READY_STATUS, clear_cooldown=True, reset_failures=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/run-now")
def api_admin_run_now(project_id: str) -> RedirectResponse:
    update_project_runtime(project_id, status=READY_STATUS, clear_cooldown=True, reset_failures=True)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/review/request")
def api_admin_request_review(project_id: str) -> RedirectResponse:
    trigger_controller_post(f"/api/projects/{project_id}/review/request")
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/projects/{project_id}/review/sync")
def api_admin_sync_review(project_id: str) -> RedirectResponse:
    trigger_controller_post(f"/api/projects/{project_id}/review/sync")
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


@app.post("/api/admin/projects/{project_id}/review-policy")
def api_admin_update_project_review_policy(
    project_id: str,
    enabled: Optional[str] = Form(None),
    mode: str = Form("github"),
    trigger: str = Form("manual_comment"),
    required_before_queue_advance: Optional[str] = Form(None),
    owner: str = Form(""),
    repo: str = Form(""),
    base_branch: str = Form("main"),
    branch_template: str = Form(""),
    focus_template: str = Form("for regressions and missing tests"),
    bot_logins: str = Form("codex"),
) -> RedirectResponse:
    config = normalize_config()
    project = project_cfg(config, project_id)
    branch = str(branch_template or f"fleet/{project_id}").strip() or f"fleet/{project_id}"
    project["review"] = {
        "enabled": enabled is not None,
        "mode": str(mode or "github").strip() or "github",
        "trigger": str(trigger or "manual_comment").strip() or "manual_comment",
        "required_before_queue_advance": required_before_queue_advance is not None,
        "owner": str(owner or "").strip(),
        "repo": str(repo or "").strip(),
        "base_branch": str(base_branch or "main").strip() or "main",
        "branch_template": branch,
        "focus_template": str(focus_template or "for regressions and missing tests").strip() or "for regressions and missing tests",
        "bot_logins": split_items(bot_logins) or ["codex"],
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


@app.post("/api/admin/groups/{group_id}/protect")
def api_admin_protect_group(group_id: str) -> RedirectResponse:
    config = normalize_config()
    group = group_cfg(config, group_id)
    captain = group_captain_policy(group)
    captain["priority"] = max(int(captain.get("priority") or 0), 500)
    captain["service_floor"] = max(int(captain.get("service_floor") or 0), 1)
    captain["admission_policy"] = "protect"
    group["captain"] = normalized_captain_policy(captain, default_service_floor=max(1, len(group.get("projects") or [])))
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/drain")
def api_admin_drain_group(group_id: str) -> RedirectResponse:
    config = normalize_config()
    group = group_cfg(config, group_id)
    captain = group_captain_policy(group)
    captain["admission_policy"] = "drain"
    group["captain"] = normalized_captain_policy(captain, default_service_floor=max(1, len(group.get("projects") or [])))
    save_fleet_config(config)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/groups/{group_id}/burst")
def api_admin_burst_group(group_id: str) -> RedirectResponse:
    config = normalize_config()
    group = group_cfg(config, group_id)
    captain = group_captain_policy(group)
    captain["priority"] = max(int(captain.get("priority") or 0), 250)
    captain["admission_policy"] = "burst"
    group["captain"] = normalized_captain_policy(captain, default_service_floor=max(1, len(group.get("projects") or [])))
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
    trigger_auditor_run(scope_type="group", scope_id=group_id)
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
        phase=WAITING_CAPACITY_STATUS,
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


@app.post("/api/admin/groups/{group_id}/heal-now")
def api_admin_heal_group_now(group_id: str) -> RedirectResponse:
    group = group_cfg(normalize_config(), group_id)
    published = publish_group_approved_tasks(group_id, queue_mode="append")
    upsert_group_runtime(
        group_id,
        signoff_state="open",
        mark_refill_requested=published > 0,
        mark_audit_requested=published <= 0,
    )
    if published <= 0:
        trigger_auditor_run(scope_type="group", scope_id=group_id)
    log_group_run(
        group_id,
        run_kind="heal",
        phase=QUEUE_REFILLING_STATUS if published > 0 else "audit_requested",
        status="requested",
        member_projects=[str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()],
        details={"requested_by": "admin", "published_count": int(published)},
    )
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/incidents/{incident_id}/auto-resolve")
def api_admin_auto_resolve_incident(incident_id: int) -> RedirectResponse:
    incident = dict(incident_row(incident_id))
    scope_type = str(incident.get("scope_type") or "").strip()
    scope_id = str(incident.get("scope_id") or "").strip()
    incident_kind = str(incident.get("incident_kind") or "").strip()
    context = incident_context_payload(incident)
    context["last_admin_action"] = "auto_resolve"
    context["last_admin_action_at"] = iso(utc_now())
    update_incident_record(incident_id, context=context)

    if scope_type == "project":
        if incident_kind == REVIEW_STALLED_INCIDENT_KIND:
            trigger_controller_post(f"/api/projects/{scope_id}/review/request")
        elif incident_kind in {REVIEW_FAILED_INCIDENT_KIND, PR_CHECKS_FAILED_INCIDENT_KIND}:
            trigger_controller_post(f"/api/projects/{scope_id}/review/sync")
            trigger_controller_post(f"/api/projects/{scope_id}/retry")
        elif incident_kind == BLOCKED_UNRESOLVED_INCIDENT_KIND:
            trigger_auditor_run(scope_type="project", scope_id=scope_id)
            trigger_controller_post(f"/api/projects/{scope_id}/retry")
        else:
            trigger_controller_post(f"/api/projects/{scope_id}/retry")
        return RedirectResponse("/admin", status_code=303)

    if scope_type == "group":
        published = publish_group_approved_tasks(scope_id, queue_mode="append")
        upsert_group_runtime(
            scope_id,
            signoff_state="open",
            mark_refill_requested=published > 0,
            mark_audit_requested=published <= 0,
        )
        trigger_auditor_run(scope_type="group", scope_id=scope_id)
        return RedirectResponse("/admin", status_code=303)

    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/incidents/{incident_id}/ack")
def api_admin_ack_incident(incident_id: int) -> RedirectResponse:
    incident = dict(incident_row(incident_id))
    context = incident_context_payload(incident)
    context["acknowledged_by"] = "admin"
    context["acknowledged_at"] = iso(utc_now())
    update_incident_record(incident_id, status="acknowledged", context=context)
    return RedirectResponse("/admin", status_code=303)


@app.post("/api/admin/incidents/{incident_id}/escalate")
def api_admin_escalate_incident(incident_id: int) -> RedirectResponse:
    incident = dict(incident_row(incident_id))
    context = incident_context_payload(incident)
    context["operator_required"] = True
    context["can_resolve"] = False
    context["escalated_by"] = "admin"
    context["escalated_at"] = iso(utc_now())
    update_incident_record(incident_id, severity="critical", context=context)
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


@app.post("/api/admin/studio/proposals/{proposal_id}/publish")
def api_admin_publish_studio_proposal(proposal_id: int, mode: str = Form("")) -> RedirectResponse:
    trigger_studio_post(f"/api/studio/proposals/{proposal_id}/publish", {"mode": mode} if mode else {})
    return RedirectResponse("/admin", status_code=303)


def render_admin_dashboard(*, show_details: bool = False) -> str:
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
    github_review_findings = status.get("review_findings") or []
    publish_events = status.get("studio_publish_events") or []
    group_publish_event_rows = status.get("group_publish_events") or []
    group_run_rows = status.get("group_runs") or []
    runs = status["recent_runs"]
    decisions = status.get("recent_decisions") or []
    ops = status.get("ops_summary") or {}
    cockpit = status.get("cockpit") or cockpit_payload_from_status(status)
    public_status = status.get("public_status") or canonical_public_status_payload(status)
    cockpit_summary = cockpit.get("summary") or {}
    mission_board = public_status.get("mission_board") or cockpit.get("mission_board") or {}
    mission_snapshot = public_status.get("mission_snapshot") or cockpit.get("mission_snapshot") or {}
    queue_forecast = public_status.get("queue_forecast") or cockpit.get("queue_forecast") or {}
    vision_forecast = public_status.get("vision_forecast") or cockpit.get("vision_forecast") or {}
    capacity_forecast = public_status.get("capacity_forecast") or cockpit.get("capacity_forecast") or {}
    blocker_forecast = public_status.get("blocker_forecast") or cockpit.get("blocker_forecast") or {}
    execution_loop = mission_board.get("execution_loop") or {}
    mission_group_cards = mission_board.get("group_cards") or []
    mission_lane_runway = mission_board.get("lane_runway") or []
    mission_provider_credit = mission_board.get("provider_credit_card") or {}
    mission_blockers = mission_board.get("blockers") or {}
    truth_freshness = mission_board.get("truth_freshness") or {}
    lamps = cockpit.get("lamps") or []
    attention_items = cockpit.get("attention") or []
    worker_cards = cockpit.get("workers") or []
    worker_breakdown = cockpit.get("worker_breakdown") or {}
    approval_items = cockpit.get("approvals") or []
    runway = cockpit.get("runway") or {}
    studio_pending = studio_proposals()
    incident_items = status.get("incidents") or []
    red_incident_items = [item for item in incident_items if incident_requires_operator_attention(item)]
    review_failure_incidents = [item for item in red_incident_items if str(item.get("incident_kind") or "") == REVIEW_FAILED_INCIDENT_KIND]
    review_stalled_incidents = [item for item in red_incident_items if str(item.get("incident_kind") or "") == REVIEW_STALLED_INCIDENT_KIND]
    blocked_unresolved_incidents = [item for item in red_incident_items if str(item.get("incident_kind") or "") == BLOCKED_UNRESOLVED_INCIDENT_KIND]
    config_ref = status.get("config") or {}
    default_project_auto_heal_enabled = scope_auto_heal_enabled(config_ref, project_id="core")
    default_project_auto_heal_categories = scope_auto_heal_categories(config_ref, project_id="core")
    default_group_auto_heal_enabled = scope_auto_heal_enabled(config_ref, group_id="chummer-vnext")
    default_group_auto_heal_categories = scope_auto_heal_categories(config_ref, group_id="chummer-vnext")
    escalation_thresholds = auto_heal_escalation_thresholds(config_ref)
    group_lookup = {str(group.get("id") or ""): group for group in groups}
    consistency_warnings = status.get("config_warnings") or []

    def td(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    def title_attr(value: Any) -> str:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return ""
        return f' title="{html.escape(text)}"'

    consistency_warning_html = (
        "".join(
            f'<div class="attention-item"><strong>{td(item.get("title"))}</strong><div class="muted">{td(item.get("summary"))}</div><div class="muted">{td(item.get("detail"))}</div></div>'
            for item in consistency_warnings
        )
        or '<p class="muted">No config or route consistency warnings.</p>'
    )

    def joined_lines(items: List[Any], *, empty: str = "None right now.") -> str:
        clean = [str(item).strip() for item in items if str(item).strip()]
        return "; ".join(clean) if clean else empty

    def render_summary_list(items: List[Any], render_item) -> str:
        if not items:
            return '<p class="muted">None right now.</p>'
        rendered = "".join(f"<li>{render_item(item)}</li>" for item in items[:5])
        if len(items) > 5:
            rendered += f"<li class=\"muted\">+{len(items) - 5} more</li>"
        return f"<ul>{rendered}</ul>"

    def render_action(action: Dict[str, Any], *, css_class: str = "") -> str:
        if not action:
            return ""
        label = td(action.get("label") or "Action")
        href = str(action.get("href") or "").strip()
        method = str(action.get("method") or "get").strip().lower()
        focus_id = str(action.get("focus_id") or "").strip()
        classes = f"action-btn {css_class}".strip()
        title = title_attr(action.get("title"))
        fields = action.get("fields") or {}
        if focus_id:
            return f'<button type="button" class="{classes}" onclick="openFocus(\'{html.escape(focus_id)}\')"{title}>{label}</button>'
        if method == "post" and href:
            hidden = "".join(
                f'<input type="hidden" name="{html.escape(str(name))}" value="{html.escape(str(value))}" />'
                for name, value in fields.items()
            )
            return f'<form method="post" action="{html.escape(href)}">{hidden}<button class="{classes}" type="submit"{title}>{label}</button></form>'
        if href:
            return f'<a class="{classes}" href="{html.escape(href)}"{title}>{label}</a>'
        return ""

    def chip(value: str, *, tone: str = "") -> str:
        clean = str(value or "").strip() or "unknown"
        tone_class = f" tone-{tone}" if tone else ""
        return f'<span class="chip{tone_class}">{td(clean)}</span>'

    def severity_tone(value: str) -> str:
        clean = str(value or "").strip().lower()
        if clean in {"critical", "high", "blocked", "red", "emergency"}:
            return "danger"
        if clean in {"medium", "elevated", "yellow", "constrained"}:
            return "warn"
        if clean in {"clean", "green", "nominal", "active"}:
            return "good"
        if clean in {WAITING_CAPACITY_STATUS, "waiting", "queued", "pending"}:
            return "warn"
        return "muted"

    def progress_bar_html(progress: Dict[str, Any], *, delivery: bool = False) -> str:
        complete = max(0, int(progress.get("percent_complete") or 0))
        inflight = max(0, int(progress.get("percent_inflight") or 0))
        blocked = max(0, int(progress.get("percent_blocked") or 0))
        gray_key = "percent_unstarted" if delivery else "percent_unmaterialized"
        gray = max(0, int(progress.get(gray_key) or 0))
        return (
            '<div class="progress-bar">'
            f'<span class="progress-segment progress-complete" style="width:{complete}%"></span>'
            f'<span class="progress-segment progress-inflight" style="width:{inflight}%"></span>'
            f'<span class="progress-segment progress-blocked" style="width:{blocked}%"></span>'
            f'<span class="progress-segment progress-unmaterialized" style="width:{gray}%"></span>'
            "</div>"
        )

    def progress_summary_html(progress: Dict[str, Any], *, delivery: bool = False) -> str:
        gray_key = "percent_unstarted" if delivery else "percent_unmaterialized"
        gray_label = "unstarted" if delivery else "unmaterialized"
        return (
            f"{td(progress.get('percent_complete'))}% done · "
            f"{td(progress.get('percent_inflight'))}% inflight · "
            f"{td(progress.get('percent_blocked'))}% blocked · "
            f"{td(progress.get(gray_key))}% {gray_label}"
        )

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
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/review/request"><button type="submit">Request Review</button></form>'
        )
        actions.append(
            f'<form method="post" action="/api/admin/projects/{project["id"]}/review/sync"><button type="submit">Sync Review</button></form>'
        )
        progress_label = project_progress_label(project)
        review_row = project.get("pull_request") or {}
        review_counts = project.get("review_findings") or {}
        design_progress = project.get("design_progress") or {}
        review_link = (
            f'<a href="{html.escape(str(review_row.get("pr_url")))}">PR #{td(review_row.get("pr_number"))}</a>'
            if review_row.get("pr_url")
            else ""
        )
        project_rows.append(
            f"""
            <tr id="project-row-{td(project.get('id'))}">
              <td><div>{td(project.get('id'))}</div><div class="muted">{td(project.get('path'))}</div></td>
              <td><div>{td(project.get('runtime_status'))}</div><div class="muted">{td(project.get('completion_basis'))}</div><div class="muted">lifecycle: {td(project.get('lifecycle'))} / compile: {td((project.get('compile_health') or {}).get('status'))}</div><div class="muted">{td((project.get('compile_health') or {}).get('summary'))}</div><div class="muted">pressure: {td(project.get('pressure_state'))}</div><div class="muted">review: {td(review_row.get('review_status') or 'not_requested')} / blocking {td(review_counts.get('blocking_count'))}</div><div class="muted">deploy: {td((project.get('deployment') or {}).get('display'))}</div></td>
              <td><div>{td(project.get('stop_reason'))}</div><div class="muted">{td(project.get('next_action'))}</div><div class="muted">{td(project.get('unblocker'))}</div><div class="muted">audit tasks: approved {td(project.get('approved_audit_task_count'))} / open {td(project.get('open_audit_task_count'))}</div></td>
              <td><div>{td(project.get('queue_source_health'))}</div><div class="muted">{td(project.get('backlog_source'))}</div></td>
              <td>{progress_label}</td>
              <td><div>{td(project.get('current_slice'))}</div><div class="muted">lane: {td(project.get('selected_lane') or 'unknown')} / {td(project.get('selected_lane_submode') or 'n/a')}</div><div class="muted">review: {td(project.get('required_reviewer_lane') or 'n/a')} -> {td(project.get('task_final_reviewer_lane') or project.get('required_reviewer_lane') or 'n/a')}</div><div class="muted">loop: round {td(project.get('review_rounds_used'))} / {td(project.get('task_max_review_rounds') or '0')} · next reviewer {td(project.get('next_reviewer_lane') or 'n/a')}</div><div class="muted">active review: {td(project.get('active_reviewer_lane') or 'n/a')} · core rescue next: {td('likely' if project.get('core_rescue_likely_next') else 'no')}</div><div class="muted">{td(project.get('decision_meta_summary') or '')}</div></td>
              <td><div>{review_link or td(project_review_policy_summary(project))}</div><div class="muted">{td(project_review_policy_summary(project))}</div><div class="muted">requested {td(review_row.get('review_requested_at') or '')}</div><div class="muted">{td((project.get('review_eta') or {}).get('summary') or '')}</div></td>
              <td><div>{td((project.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((project.get('milestone_eta') or {}).get('eta_basis'))}</div><div class="muted">design {td((project.get('design_eta') or {}).get('eta_human') or 'unknown')} · {td((project.get('design_eta') or {}).get('confidence') or (design_progress.get('eta_confidence') or 'low'))}</div><div class="muted">{td((project.get('design_eta') or {}).get('coverage_status') or '')}</div><div class="muted">{td((project.get('design_eta') or {}).get('confidence_reason') or '')}</div></td>
              <td>{td(project.get('uncovered_scope_count'))}</td>
              <td><div class="muted">{progress_summary_html(design_progress)}</div>{progress_bar_html(design_progress)}<div class="muted">{td(design_progress.get('summary') or '')}</div><div class="muted">blocker: {td(design_progress.get('main_blocker') or '')}</div><div class="muted">coverage: {td((project.get('design_eta') or {}).get('coverage_status') or '')}</div><div class="muted">{td((project.get('design_eta') or {}).get('confidence_reason') or '')}</div></td>
              <td><div>{td(', '.join(project.get('accounts') or []))}</div><div class="muted">{td(project_account_policy_summary(project))}</div><div class="muted">{td(runner_policy_summary(project))}</div><div class="muted">capacity: {td(project.get('selected_lane_capacity_state') or 'unknown')} / {td(project.get('selected_lane_capacity_remaining_percent') if project.get('selected_lane_capacity_remaining_percent') is not None else 'n/a')}%</div><div class="muted">lane allowance: {td(project_lane_allowance_summary(project))}</div><div class="muted">runway: {td(project.get('sustainable_runway') or 'unknown')} · next reviewer {td(project.get('next_reviewer_lane') or 'n/a')}</div><div class="muted">active brain: {td(project.get('active_run_brain') or 'n/a')} / last brain: {td(project.get('last_run_brain') or 'n/a')}</div><div class="muted">allowance: ${float((project.get('allowance_usage') or {}).get('estimated_cost_usd') or 0.0):.4f} / {(project.get('allowance_usage') or {}).get('run_count') or 0} runs</div></td>
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
        design_progress = group.get("design_progress") or {}
        group_rows.append(
            f"""
            <tr id="group-row-{td(group.get('id'))}">
              <td><a href="/admin/groups/{html.escape(str(group.get('id') or ''))}">{td(group.get('id'))}</a></td>
              <td><div>{td(group.get('status'))}</div><div class="muted">phase: {td(group.get('phase'))}</div><div class="muted">lifecycle: {td(group.get('lifecycle'))} / {td(group.get('mode'))}</div><div class="muted">pressure: {td(group.get('pressure_state'))}</div><div class="muted">{td('signed off' if group.get('signed_off') else 'not signed off')}</div><div class="muted">{td(group.get('signed_off_at') or group.get('reopened_at') or '')}</div><div class="muted">dispatch {td(group.get('dispatch_member_count'))} / scaffold {td(group.get('scaffold_member_count'))} / signoff-only {td(group.get('signoff_only_member_count'))} / compile attention {td(group.get('compile_attention_count'))}</div><div class="muted">dispatch-eligible projects: {td(group.get('ready_project_count'))} / incidents: {td(group.get('open_incident_count'))} / auditor solve: {td('yes' if group.get('auditor_can_solve') else 'no')}</div><div class="muted">public surface: {td((group.get('deployment') or {}).get('display'))}</div></td>
              <td><div>{td('dispatchable' if group.get('dispatch_ready') else 'blocked')}</div><div class="muted">{td(group.get('dispatch_basis'))}</div></td>
              <td>{td(', '.join(group.get('projects') or []))}</td>
              <td><div>{td(', '.join(group.get('contract_sets') or []))}</div><div class="muted">{td('; '.join(group.get('contract_blockers') or []))}</div><div class="muted">{td(group_captain_policy_summary(group))}</div><div class="muted">review waiting {td(group.get('review_waiting_count'))} / blocking {td(group.get('review_blocking_count'))}</div><div class="muted">question: {td(group.get('operator_question'))}</div><div class="muted">notify: {td('yes' if group.get('notification_needed') else 'no')}</div></td>
              <td><div>{td(len(group.get('dispatch_blockers') or []))}</div><div class="muted">{td('; '.join(group.get('dispatch_blockers') or []))}</div></td>
              <td>{td(group.get('uncovered_scope_count'))}</td>
              <td><div>{td((group.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td><div>{td((group.get('program_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('program_eta') or {}).get('eta_basis'))}</div><div class="muted">confidence {td((group.get('program_eta') or {}).get('confidence') or (design_progress.get('eta_confidence') or 'low'))}</div><div class="muted">coverage {td((group.get('design_eta') or {}).get('coverage_status') or '')}</div><div class="muted">{td((group.get('design_eta') or {}).get('confidence_reason') or '')}</div><div class="muted">pool: {td((group.get('pool_sufficiency') or {}).get('level'))} / slots {td((group.get('pool_sufficiency') or {}).get('eligible_parallel_slots'))}</div><div class="muted">allowance: ${float((group.get('allowance_usage') or {}).get('estimated_cost_usd') or 0.0):.4f}</div></td>
              <td><div class="muted">{progress_summary_html(design_progress)}</div>{progress_bar_html(design_progress)}<div class="muted">{td(design_progress.get('summary') or '')}</div><div class="muted">coverage: {td((group.get('design_eta') or {}).get('coverage_status') or '')}</div><div class="muted">{td((group.get('design_eta') or {}).get('confidence_reason') or '')}</div></td>
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
                parts.append("dispatchable" if details.get("dispatch_ready") else "dispatch-blocked")
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

    review_rows: List[str] = []
    for project in projects:
        pr = project.get("pull_request") or {}
        if not pr and not bool((project.get("review") or {}).get("enabled", True)):
            continue
        actions = [
            f'<form method="post" action="/api/admin/projects/{project["id"]}/review/request"><button type="submit">Request Review</button></form>',
            f'<form method="post" action="/api/admin/projects/{project["id"]}/review/sync"><button type="submit">Sync Review</button></form>',
        ]
        pr_link = (
            f'<a href="{html.escape(str(pr.get("pr_url")))}">PR #{td(pr.get("pr_number"))}</a>'
            if pr.get("pr_url")
            else ""
        )
        review_rows.append(
            f"""
            <tr id="review-row-{td(project.get('id'))}">
              <td>{td(project.get('id'))}</td>
              <td>{td((project.get('review') or {}).get('mode'))}</td>
              <td>{td((project.get('review') or {}).get('trigger'))}</td>
              <td>{td((project.get('review') or {}).get('owner'))}/{td((project.get('review') or {}).get('repo'))}</td>
              <td>{pr_link}</td>
              <td>{td(pr.get('review_status') or 'not_requested')}</td>
              <td>{td((project.get('review_findings') or {}).get('blocking_count'))} / {td((project.get('review_findings') or {}).get('count'))}</td>
              <td>{td(pr.get('review_requested_at'))}</td>
              <td>{td((project.get('review_eta') or {}).get('summary') or '')}</td>
              <td>{td(pr.get('review_completed_at'))}</td>
              <td><div class="actions">{''.join(actions)}</div></td>
            </tr>
            """
        )

    github_review_rows: List[str] = []
    for finding in github_review_findings[:50]:
        body = str(finding.get("body") or "").strip()
        github_review_rows.append(
            f"""
            <tr>
              <td>{td(finding.get('project_id'))}</td>
              <td>{td(finding.get('pr_number'))}</td>
              <td>{td(finding.get('severity'))}</td>
              <td>{td(finding.get('path'))}:{td(finding.get('line'))}</td>
              <td>{td(body[:240] + ('...' if len(body) > 240 else ''))}</td>
              <td>{td(finding.get('updated_at'))}</td>
            </tr>
            """
        )

    studio_proposal_rows: List[str] = []
    focus_blocks: List[str] = []
    for proposal in studio_pending[:30]:
        proposal_id = int(proposal.get("id") or 0)
        payload = proposal.get("payload") or {}
        proposal_payload = proposal.get("proposal") or {}
        files = list(proposal_payload.get("files") or [])
        targets = list(proposal.get("targets") or [])
        studio_proposal_rows.append(
            f"""
            <tr>
              <td>{td(proposal.get('id'))}</td>
              <td>{td(proposal.get('status') or 'pending')}</td>
              <td>{td(proposal.get('role'))}</td>
              <td>{td(proposal.get('target_type'))}:{td(proposal.get('target_id'))}</td>
              <td><div>{td(proposal.get('title'))}</div><div class="muted">{td(proposal.get('summary'))}</div></td>
              <td>{td(proposal.get('targets_summary') or '<single target>')}</td>
              <td><div class="actions">{render_action({'label': 'Preview', 'focus_id': f'studio-proposal-{proposal_id}', 'method': 'focus'})}{render_action({'label': 'Publish', 'href': f'/api/admin/studio/proposals/{proposal_id}/publish', 'method': 'post'})}</div></td>
            </tr>
            """
        )
        target_lines = "".join(
            f"<li>{td(target.get('target_type'))}:{td(target.get('target_id'))}</li>"
            for target in targets
            if isinstance(target, dict)
        ) or "<li>&lt;single target proposal&gt;</li>"
        file_lines = "".join(
            f"<li>{td(file_item.get('path'))}</li>"
            for file_item in files
            if isinstance(file_item, dict)
        ) or "<li>No direct file artifacts listed</li>"
        focus_blocks.append(
            f"""
            <div id="studio-proposal-{proposal_id}" class="focus-template">
              <h3>{td(proposal.get('title') or f'Studio proposal #{proposal_id}')}</h3>
              <p class="muted">{td(proposal.get('summary') or '')}</p>
              <p><strong>Scope:</strong> {td(proposal.get('target_type'))}:{td(proposal.get('target_id'))}</p>
              <p><strong>Role:</strong> {td(proposal.get('role'))}</p>
              <p><strong>Targets:</strong></p>
              <ul>{target_lines}</ul>
              <p><strong>Files:</strong></p>
              <ul>{file_lines}</ul>
              <p><strong>Feedback note:</strong></p>
              <pre>{html.escape(str(proposal_payload.get('feedback_note') or ''))}</pre>
              <div class="actions">
                {render_action({'label': 'Publish now', 'href': f'/api/admin/studio/proposals/{proposal_id}/publish', 'method': 'post'})}
                {render_action({'label': 'Open Studio', 'href': f"/studio?session={proposal.get('session_id')}", 'method': 'get'})}
              </div>
            </div>
            """
        )

    for task in task_candidates[:40]:
        focus_blocks.append(
            f"""
            <div id="audit-task-{task['id']}" class="focus-template">
              <h3>{td(task.get('title'))}</h3>
              <p class="muted">{td(task.get('finding_key'))}</p>
              <p><strong>Scope:</strong> {td(task.get('scope_type'))}:{td(task.get('scope_id'))}</p>
              <pre>{html.escape(str(task.get('detail') or ''))}</pre>
              <div class="actions">
                {render_action({'label': 'Approve', 'href': f"/api/admin/audit/tasks/{task['id']}/approve", 'method': 'post'}) if str(task.get('status') or '') == 'open' else ''}
                {render_action({'label': 'Publish', 'href': f"/api/admin/audit/tasks/{task['id']}/publish", 'method': 'post'}) if str(task.get('status') or '') == 'approved' else ''}
                {render_action({'label': 'Reject', 'href': f"/api/admin/audit/tasks/{task['id']}/reject", 'method': 'post'})}
              </div>
            </div>
            """
        )

    mission_strip_html = "".join(
        [
            f"""
            <div class="mission-card">
              <div class="mission-label">Fleet health</div>
              <div class="mission-value">{chip(cockpit_summary.get('fleet_health') or 'ok', tone=severity_tone(cockpit_summary.get('fleet_health') or 'ok'))}</div>
            </div>
            """,
            f"""
            <div class="mission-card">
              <div class="mission-label">Scheduler posture</div>
              <div class="mission-value">{chip(cockpit_summary.get('scheduler_posture') or 'nominal', tone=severity_tone(cockpit_summary.get('scheduler_posture') or 'nominal'))}</div>
            </div>
            """,
            f"""
            <div class="mission-card">
              <div class="mission-label">Blocked groups</div>
              <div class="mission-value">{td(cockpit_summary.get('blocked_groups') or 0)}</div>
            </div>
            """,
            f"""
            <div class="mission-card">
              <div class="mission-label">Open incidents</div>
              <div class="mission-value">{td(cockpit_summary.get('open_incidents') or 0)}</div>
            </div>
            """,
            f"""
            <div class="mission-card">
              <div class="mission-label">Review waits</div>
              <div class="mission-value">{td(cockpit_summary.get('review_waiting_projects') or 0)}</div>
            </div>
            """,
            f"""
            <div class="mission-card">
              <div class="mission-label">Audit / refill</div>
              <div class="mission-value">{td(cockpit_summary.get('audit_required_groups') or 0)} groups / {td(cockpit_summary.get('coverage_pressure_projects') or 0)} projects</div>
            </div>
            """,
            f"""
            <div class="mission-card mission-card-wide">
              <div class="mission-label">Reset windows</div>
              <div class="mission-reset-list">
                {''.join(f"<div><strong>{td(item.get('label'))}</strong><span>{td(item.get('human'))}</span><small>{td(item.get('basis'))}</small></div>" for item in (cockpit_summary.get('next_reset_windows') or [])[:4])}
              </div>
            </div>
            """,
        ]
    )

    lamp_strip_html = "".join(
        (
            f"""
            <button type="button" class="lamp-card lamp-{severity_tone(item.get('state') or '')}" onclick="openFocus('{html.escape(str(item.get('focus_id') or ''))}')" {title_attr(joined_lines([item.get('detail'), joined_lines(item.get('summary_lines') or [], empty='No affected scopes.'), str(item.get('auto_action') or '')]))}>
              <div class="lamp-label">{td(item.get('label'))}</div>
              <div class="lamp-value">{td(item.get('count') or 0)}</div>
              <div class="lamp-detail">{td(item.get('detail') or '')}</div>
            </button>
            """
            if item.get("focus_id")
            else f"""
            <a class="lamp-card lamp-{severity_tone(item.get('state') or '')}" href="{html.escape(str(item.get('href') or '/admin/details'))}" {title_attr(joined_lines([item.get('detail'), joined_lines(item.get('summary_lines') or [], empty='No affected scopes.'), str(item.get('auto_action') or '')]))}>
              <div class="lamp-label">{td(item.get('label'))}</div>
              <div class="lamp-value">{td(item.get('count') or 0)}</div>
              <div class="lamp-detail">{td(item.get('detail') or '')}</div>
            </a>
            """
        )
        for item in lamps[:6]
    )

    attention_html = "".join(
        f"""
        <article id="{td(item.get('card_id'))}" class="attention-item severity-{severity_tone(item.get('severity') or '')}">
          <div class="attention-head">
            <div class="attention-chips">
              {chip(item.get('severity') or 'info', tone=severity_tone(item.get('severity') or 'info'))}
              {chip(item.get('kind') or 'attention')}
              {chip(f"{item.get('scope_type')}:{item.get('scope_id')}")}
            </div>
            <div class="attention-actions">
              {render_action(item.get('primary_action') or {}, css_class='primary')}
              {render_action(item.get('secondary_action') or {}, css_class='secondary')}
            </div>
          </div>
          <h3>{td(item.get('title'))}</h3>
          <p>{td(item.get('detail'))}</p>
        </article>
        """
        for item in attention_items[:6]
    ) or '<div class="empty-state">No urgent approvals or stalls right now.</div>'

    incident_html = "".join(
        f"""
        <article id="incident-card-{td(item.get('id'))}" class="attention-item severity-{severity_tone(item.get('severity') or '')}" {title_attr(joined_lines([item.get('summary'), json.dumps(incident_context_payload(item), sort_keys=True)]))}>
          <div class="attention-head">
            <div class="attention-chips">
              {chip(item.get('severity') or 'high', tone=severity_tone(item.get('severity') or 'high'))}
              {chip(item.get('incident_kind') or 'incident')}
              {chip(f"{item.get('scope_type')}:{item.get('scope_id')}")}
            </div>
            <div class="attention-actions">
              {render_action({'label': 'Open context', 'focus_id': f"incident-focus-{item['id']}", 'method': 'focus'})}
              {render_action({'label': 'Auto-resolve now', 'href': f"/api/admin/incidents/{item['id']}/auto-resolve", 'method': 'post'})}
              {render_action({'label': 'Ack', 'href': f"/api/admin/incidents/{item['id']}/ack", 'method': 'post'})}
            </div>
          </div>
          <h3>{td(item.get('title'))}</h3>
          <p>{td(item.get('summary'))}</p>
        </article>
        """
        for item in red_incident_items[:5]
    ) or '<div class="empty-state">No open incidents right now.</div>'

    review_failure_incidents_html = "".join(
        f"<li>{td(item.get('scope_id'))}: {td(item.get('title'))}</li>"
        for item in review_failure_incidents[:6]
    ) or "<li>None</li>"

    review_stalled_incidents_html = "".join(
        f"<li>{td(item.get('scope_id'))}: {td(item.get('title'))}</li>"
        for item in review_stalled_incidents[:6]
    ) or "<li>None</li>"

    blocked_unresolved_incidents_html = "".join(
        f"<li>{td(item.get('scope_id'))}: {td(item.get('title'))}</li>"
        for item in blocked_unresolved_incidents[:6]
    ) or "<li>None</li>"

    worker_cards_html = "".join(
        f"""
        <article id="worker-card-{td(worker.get('project_id'))}" class="worker-card">
          <div class="worker-top">
            <div>
              <h3>{td(worker.get('project_id'))}</h3>
              <div class="muted">{td(worker.get('group_id'))}</div>
            </div>
            {chip(worker.get('phase') or WAITING_CAPACITY_STATUS, tone=severity_tone(worker.get('phase') or WAITING_CAPACITY_STATUS))}
          </div>
          <p class="worker-slice">{td(worker.get('current_slice'))}</p>
          <div class="worker-meta">
            <span>{td(worker.get('account_alias') or 'unassigned')}</span>
            <span>{td(worker.get('account_backend') or '')}</span>
            <span>{td(worker.get('account_identity') or '')}</span>
            <span>{td(worker.get('brain') or '')}</span>
            <span>{td(worker.get('model') or '')}</span>
            <span>{td(worker.get('route_class') or '')}</span>
            <span>{td(worker.get('elapsed_human') or '')}</span>
          </div>
          <div class="worker-meta muted">
            <span>review {td(worker.get('review_state'))}</span>
            <span>{td(worker.get('started_at') or '')}</span>
            <span>{td(worker.get('cooldown_until') or '')}</span>
          </div>
          <div class="worker-preview-grid">
            <div class="worker-preview-panel">
              <div class="worker-preview-label">Log Tail</div>
              <pre>{td(worker.get('log_preview') or 'No live log preview yet.')}</pre>
            </div>
            <div class="worker-preview-panel">
              <div class="worker-preview-label">Latest Final</div>
              <pre>{td(worker.get('final_preview') or 'No final message written yet.')}</pre>
            </div>
          </div>
          <div class="actions">
            {''.join(render_action(action) for action in (worker.get('available_actions') or [])[:4])}
            {f'<a class="action-btn" href="/api/logs/{worker.get("worker_id")}">Raw logs</a>' if str(worker.get("worker_id")).isdigit() else ''}
            {f'<a class="action-btn" href="/api/final/{worker.get("worker_id")}">Raw final</a>' if str(worker.get("worker_id")).isdigit() else ''}
          </div>
        </article>
        """
        for worker in worker_cards[:6]
    ) or '<div class="empty-state">No active workers right now.</div>'

    group_cards_html = "".join(
        f"""
        <article id="group-card-{td(item.get('group_id'))}" class="worker-card" {title_attr(joined_lines([item.get('bottleneck'), f"status {item.get('status')}", f"pool {item.get('pool_level')}", f"remaining {item.get('remaining_slices')} slices"]))}>
          <div class="worker-top">
            <div>
              <h3><button type="button" class="card-link" onclick="openFocus('group-focus-{html.escape(str(item.get('group_id') or ''))}')">{td(item.get('group_id'))}</button></h3>
              <div class="muted">priority {td(item.get('priority'))} · floor {td(item.get('service_floor'))} · {td(item.get('admission_policy'))}</div>
            </div>
            {chip(item.get('runway_risk') or item.get('status') or '', tone=severity_tone(item.get('runway_risk') or item.get('status') or ''))}
          </div>
          <p class="worker-slice">{td(item.get('bottleneck') or 'No current bottleneck')}</p>
          <div class="worker-meta muted">
            <span>{td(item.get('finish_outlook') or '')}</span>
            <span>{td(item.get('slot_share_percent'))}% pool</span>
            <span>{td(item.get('drain_share_percent'))}% recent drain</span>
          </div>
          <div class="worker-meta muted">
            <span>{td(item.get('deployment_summary') or 'No public surface metadata')}</span>
            <span>{td(item.get('deployment_url') or '')}</span>
          </div>
          <div class="worker-meta muted">
            <span>status {td(item.get('status'))}</span>
            <span>pool {td(item.get('pool_level'))}</span>
            <span>{td(item.get('eligible_parallel_slots'))} slots</span>
            <span>{td(item.get('remaining_slices'))} slices</span>
          </div>
          <div class="progress-stack">
            <div><strong>Design completeness:</strong> {td((item.get('design_progress') or {}).get('percent_complete'))}% · ETA {td((item.get('design_eta') or {}).get('eta_human') or 'unknown')} · {td((item.get('design_eta') or {}).get('confidence') or ((item.get('design_progress') or {}).get('eta_confidence') or 'low'))}</div>
            {progress_bar_html(item.get('design_progress') or {})}
            <div class="muted">{td((item.get('design_progress') or {}).get('summary') or '')}</div>
          </div>
          <div class="actions">
            {render_action({'label': 'Protect', 'href': f"/api/admin/groups/{item['group_id']}/protect", 'method': 'post'})}
            {render_action({'label': 'Drain', 'href': f"/api/admin/groups/{item['group_id']}/drain", 'method': 'post'})}
            {render_action({'label': 'Burst', 'href': f"/api/admin/groups/{item['group_id']}/burst", 'method': 'post'})}
            {render_action({'label': 'Heal now', 'href': f"/api/admin/groups/{item['group_id']}/heal-now", 'method': 'post'})}
            {render_action({'label': 'Pause', 'href': f"/api/admin/groups/{item['group_id']}/pause", 'method': 'post'})}
          </div>
        </article>
        """
        for item in (runway.get("groups") or [])[:4]
    ) or '<div class="empty-state">No groups configured.</div>'

    group_priority_rows_html = "".join(
        f"""
        <tr>
          <td><a href="/admin/groups/{html.escape(str(item.get('group_id') or ''))}">{td(item.get('group_id'))}</a></td>
          <td>{td(item.get('priority'))}</td>
          <td>{td(item.get('service_floor'))}</td>
          <td>{td(item.get('admission_policy'))}</td>
          <td>{chip(item.get('status') or '', tone=severity_tone(item.get('status') or ''))}</td>
          <td>{td(item.get('bottleneck'))}</td>
          <td>{chip(item.get('runway_risk') or '', tone=severity_tone(item.get('runway_risk') or ''))}</td>
          <td>
            <div class="actions">
              {render_action({'label': 'Protect', 'href': f"/api/admin/groups/{item['group_id']}/protect", 'method': 'post'})}
              {render_action({'label': 'Drain', 'href': f"/api/admin/groups/{item['group_id']}/drain", 'method': 'post'})}
              {render_action({'label': 'Burst', 'href': f"/api/admin/groups/{item['group_id']}/burst", 'method': 'post'})}
              {render_action({'label': 'Heal now', 'href': f"/api/admin/groups/{item['group_id']}/heal-now", 'method': 'post'})}
              {render_action({'label': 'Pause', 'href': f"/api/admin/groups/{item['group_id']}/pause", 'method': 'post'})}
              {render_action({'label': 'Refill', 'href': f"/api/admin/groups/{item['group_id']}/refill-approved", 'method': 'post', 'fields': {'queue_mode': 'append'}})}
            </div>
          </td>
        </tr>
        """
        for item in (runway.get("groups") or [])[:12]
    ) or '<tr><td colspan="8">No groups configured.</td></tr>'

    for item in lamps[:6]:
        category = str(item.get("category") or "").strip().lower()
        category_controls = ""
        if category in AUTO_HEAL_CATEGORIES:
            enabled = bool((cockpit_summary.get("auto_heal_categories") or {}).get(category))
            category_controls = f"""
              <div class="actions">
                {render_action({'label': 'Auto-resolve now', 'href': f"/api/admin/policies/auto-heal/category/{category}/resolve-now", 'method': 'post'}, css_class='primary')}
                {render_action({'label': 'Always auto-resolve this category', 'href': f"/api/admin/policies/auto-heal/category/{category}", 'method': 'post', 'fields': {'enabled': '1'}}, css_class='secondary')}
              </div>
              <form method="post" action="/api/admin/policies/auto-heal/escalation/{category}">
                <label for="escalation-{category}">Escalate after failed healer attempts</label>
                <input id="escalation-{category}" name="attempts" type="number" min="0" value="{td(escalation_thresholds.get(category) or 0)}" />
                <p class="muted">Current auto-heal state: {td('enabled' if enabled else 'disabled')}</p>
                <p><button type="submit">Save threshold</button></p>
              </form>
            """
        scope_lines = "".join(f"<li>{td(scope_id)}</li>" for scope_id in (item.get("summary_lines") or [])[:8]) or "<li>No affected scopes right now.</li>"
        focus_blocks.append(
            f"""
            <div id="{td(item.get('focus_id'))}" class="focus-template">
              <h3>{td(item.get('label'))}</h3>
              <p class="muted">{td(item.get('detail'))}</p>
              <p><strong>Affected scopes:</strong></p>
              <ul>{scope_lines}</ul>
              <p><strong>Resolver plan:</strong> {td(item.get('auto_action') or 'No automatic resolver plan recorded.')}</p>
              <p><strong>ETA to heal:</strong> {td(item.get('eta_hint') or 'next control-loop pass')}</p>
              <div class="actions">
                {render_action({'label': 'Open raw details', 'href': item.get('href') or '/admin/details', 'method': 'get'})}
              </div>
              {category_controls}
            </div>
            """
        )

    for item in red_incident_items[:12]:
        incident_id = int(item.get("id") or 0)
        category = incident_auto_heal_category(item)
        category_controls = ""
        if category in AUTO_HEAL_CATEGORIES:
            category_controls = f"""
              <div class="actions">
                {render_action({'label': 'Always auto-resolve this class', 'href': f"/api/admin/policies/auto-heal/category/{category}", 'method': 'post', 'fields': {'enabled': '1'}}, css_class='secondary')}
              </div>
              <form method="post" action="/api/admin/policies/auto-heal/escalation/{category}">
                <label for="incident-escalation-{incident_id}">Escalate after failed healer attempts</label>
                <input id="incident-escalation-{incident_id}" name="attempts" type="number" min="0" value="{td(escalation_thresholds.get(category) or 0)}" />
                <p><button type="submit">Save threshold</button></p>
              </form>
            """
        context_json = html.escape(json.dumps(incident_context_payload(item), indent=2, sort_keys=True))
        focus_blocks.append(
            f"""
            <div id="incident-focus-{incident_id}" class="focus-template">
              <h3>{td(item.get('title'))}</h3>
              <p class="muted">{td(item.get('incident_kind'))} · {td(item.get('scope_type'))}:{td(item.get('scope_id'))}</p>
              <p><strong>Summary:</strong> {td(item.get('summary') or '')}</p>
              <p><strong>Active resolver plan:</strong> {td('healer-owned' if incident_context_payload(item).get('can_resolve') else 'operator-owned escalation')}</p>
              <div class="actions">
                {render_action({'label': 'Auto-resolve now', 'href': f"/api/admin/incidents/{incident_id}/auto-resolve", 'method': 'post'}, css_class='primary')}
                {render_action({'label': 'Ack', 'href': f"/api/admin/incidents/{incident_id}/ack", 'method': 'post'})}
                {render_action({'label': 'Escalate', 'href': f"/api/admin/incidents/{incident_id}/escalate", 'method': 'post'}, css_class='secondary')}
              </div>
              {category_controls}
              <p><strong>Evidence / context:</strong></p>
              <pre>{context_json}</pre>
            </div>
            """
        )

    for item in (runway.get("groups") or [])[:6]:
        group_id = str(item.get("group_id") or "").strip()
        group_row = group_lookup.get(group_id, {})
        incident_lines = "".join(
            f"<li>{td(incident.get('title') or incident.get('summary') or 'open incident')}</li>"
            for incident in (group_row.get("incidents") or [])[:6]
            if incident_requires_operator_attention(incident)
        ) or "<li>No red incidents right now.</li>"
        focus_blocks.append(
            f"""
            <div id="group-focus-{td(group_id)}" class="focus-template">
              <h3>{td(group_id)}</h3>
              <p class="muted">priority {td(item.get('priority'))} · floor {td(item.get('service_floor'))} · {td(item.get('admission_policy'))}</p>
              <p><strong>Bottleneck:</strong> {td(item.get('bottleneck') or 'No current bottleneck')}</p>
              <p><strong>Runway risk:</strong> {td(item.get('runway_risk') or item.get('status') or 'unknown')}</p>
              <p><strong>Finish outlook:</strong> {td(item.get('finish_outlook') or item.get('sufficiency_basis') or 'unknown')}</p>
              <p><strong>Pool share:</strong> {td(item.get('slot_share_percent'))}% of fleet slots · <strong>Recent drain:</strong> {td(item.get('drain_share_percent'))}%</p>
              <p><strong>Delivery:</strong> {progress_summary_html((group_row or {}).get('delivery_progress') or {}, delivery=True)}</p>
              {progress_bar_html((group_row or {}).get('delivery_progress') or {}, delivery=True)}
              <p><strong>Design:</strong> {progress_summary_html((group_row or {}).get('design_progress') or {})}</p>
              {progress_bar_html((group_row or {}).get('design_progress') or {})}
              <p class="muted">ETA {(group_row.get('design_eta') or {}).get('eta_human') or 'unknown'} · confidence {(group_row.get('design_eta') or {}).get('confidence') or ((group_row.get('design_progress') or {}).get('eta_confidence') or 'low')} · blocker {td((group_row.get('design_progress') or {}).get('main_blocker') or '')}</p>
              <p><strong>Current phase:</strong> {td((group_row or {}).get('phase') or '')}</p>
              <p><strong>Open red incidents:</strong></p>
              <ul>{incident_lines}</ul>
              <div class="actions">
                {render_action({'label': 'Protect', 'href': f"/api/admin/groups/{group_id}/protect", 'method': 'post'})}
                {render_action({'label': 'Drain', 'href': f"/api/admin/groups/{group_id}/drain", 'method': 'post'})}
                {render_action({'label': 'Burst', 'href': f"/api/admin/groups/{group_id}/burst", 'method': 'post'})}
                {render_action({'label': 'Heal now', 'href': f"/api/admin/groups/{group_id}/heal-now", 'method': 'post'}, css_class='primary')}
                {render_action({'label': 'Pause', 'href': f"/api/admin/groups/{group_id}/pause", 'method': 'post'})}
              </div>
              <div class="actions">
                {render_action({'label': 'Open group page', 'href': f"/admin/groups/{group_id}", 'method': 'get'})}
              </div>
            </div>
            """
        )

    pressured_accounts = [
        item for item in (runway.get("accounts") or [])
        if str(item.get("pressure_state") or "") in {"red", "yellow"}
    ] or list(runway.get("accounts") or [])[:4]
    account_pressure_cards_html = "".join(
        f"""
        <article class="approval-item">
          <div class="approval-head">
            {chip(item.get('alias') or '')}
            {chip(item.get('pressure_state') or '', tone=severity_tone(item.get('pressure_state') or ''))}
          </div>
          <p>{td(item.get('auth_kind'))} · standard {td(item.get('standard_pool_state'))} · spark {td(item.get('spark_pool_state'))}</p>
          <p class="muted">{td(item.get('burn_rate'))} · projected {td(item.get('projected_exhaustion'))} · {td('; '.join(item.get('top_consumers') or []))}</p>
          <div class="actions">
            {render_action({'label': 'Drain', 'href': f"/api/admin/accounts/{item['alias']}/state", 'method': 'post', 'fields': {'state': 'draining'}})}
            {render_action({'label': 'Disable', 'href': f"/api/admin/accounts/{item['alias']}/state", 'method': 'post', 'fields': {'state': 'disabled'}})}
            {render_action({'label': 'Resume', 'href': f"/api/admin/accounts/{item['alias']}/state", 'method': 'post', 'fields': {'state': 'ready'}})}
            {render_action({'label': 'Validate auth', 'href': f"/api/admin/accounts/{item['alias']}/validate", 'method': 'post'})}
          </div>
        </article>
        """
        for item in pressured_accounts[:6]
    ) or '<div class="empty-state">No account pressure right now.</div>'

    account_runway_rows_html = "".join(
        f"""
        <tr>
          <td>{td(item.get('alias'))}</td>
          <td>{td(item.get('auth_kind'))}</td>
          <td>{chip(item.get('standard_pool_state') or '', tone=severity_tone(item.get('pressure_state') or ''))}</td>
          <td>{chip(item.get('spark_pool_state') or '', tone=severity_tone(item.get('pressure_state') or ''))}</td>
          <td>{chip(item.get('api_budget_health') or '', tone=severity_tone(item.get('api_budget_health') or ''))}</td>
          <td>{td(item.get('active_runs'))}</td>
          <td>{td(item.get('burn_rate'))}</td>
          <td>{td(item.get('projected_exhaustion'))}</td>
          <td>{td('; '.join(item.get('top_consumers') or []))}</td>
          <td>
            <div class="actions">
              {render_action({'label': 'Drain', 'href': f"/api/admin/accounts/{item['alias']}/state", 'method': 'post', 'fields': {'state': 'draining'}})}
              {render_action({'label': 'Disable', 'href': f"/api/admin/accounts/{item['alias']}/state", 'method': 'post', 'fields': {'state': 'disabled'}})}
              {render_action({'label': 'Resume', 'href': f"/api/admin/accounts/{item['alias']}/state", 'method': 'post', 'fields': {'state': 'ready'}})}
              {render_action({'label': 'Validate auth', 'href': f"/api/admin/accounts/{item['alias']}/validate", 'method': 'post'})}
            </div>
          </td>
        </tr>
        """
        for item in (runway.get("accounts") or [])[:12]
    ) or '<tr><td colspan="10">No account pools yet.</td></tr>'

    approval_html = "".join(
        f"""
        <article class="approval-item">
          <div class="approval-head">
            {chip(item.get('kind') or 'approval')}
            <strong>{td(item.get('title'))}</strong>
          </div>
          <p>{td(item.get('detail'))}</p>
          <div class="actions">{''.join(render_action(action) for action in (item.get('actions') or []))}</div>
        </article>
        """
        for item in approval_items[:12]
    ) or '<div class="empty-state">No review, publish, or refill approvals are waiting.</div>'

    def forecast_tone(value: str) -> str:
        clean = str(value or "").strip().lower()
        if clean in {"stable", "ready", "green", "none"}:
            return "good"
        if clean in {"likely", "fallback_ready", "yellow", "warn"}:
            return "warn"
        if clean in {"volatile", "red", "blocked", "degraded"}:
            return "danger"
        return "muted"

    forecast_lane_rows_html = "".join(
        f"""
        <div class="forecast-capacity-row">
          <div>
            <strong>{td(str(item.get('lane') or '').title())}</strong>
            <div class="muted">{td(item.get('provider'))} · {td(item.get('model'))}</div>
          </div>
          <div style="text-align:right;">
            {chip(item.get('remaining_text') or 'unknown', tone=forecast_tone(item.get('state') or ''))}
            <div class="muted">native {td((item.get('native_allowance') or {}).get('estimated_remaining_credits_total') if (item.get('native_allowance') or {}).get('estimated_remaining_credits_total') is not None else 'n/a')} credits · burn ${float(item.get('local_estimated_burn_usd') or 0.0):.4f}</div>
            <div class="muted">runway {td(item.get('sustainable_runway') or item.get('hot_runway') or 'unknown')} · state {td(item.get('state') or 'unknown')}</div>
          </div>
        </div>
        """
        for item in (capacity_forecast.get("lanes") or [])
    ) or '<div class="empty-state">No lane-capacity telemetry is available.</div>'
    blocker_rows_html = "".join(
        f"""
        <div class="forecast-blocker-row">
          <strong>{td(label)}</strong>
          <span>{td(value)}</span>
        </div>
        """
        for label, value in [
            ("Current slice", blocker_forecast.get("now") or "none"),
            ("Next slice", blocker_forecast.get("next") or "none"),
            ("Vision", blocker_forecast.get("vision") or "none"),
        ]
    )
    command_loop_timeline_html = "".join(
        f"""
        <div class="forecast-card">
          <div class="forecast-kicker">{td(item.get('label') or item.get('id') or 'step')}</div>
          <div class="forecast-title">{chip(item.get('state') or 'pending', tone=forecast_tone(item.get('state') or ''))}</div>
        </div>
        """
        for item in (execution_loop.get("timeline") or [])
    ) or '<div class="empty-state">No cheap-loop timeline is active right now.</div>'
    command_group_cards_html = "".join(
        f"""
        <article class="forecast-card">
          <div class="forecast-kicker">{td(item.get('group_id') or 'group')} · {td(item.get('dispatchability') or 'unknown')}</div>
          <div class="forecast-title">{td(item.get('current_objective') or 'No current objective recorded.')}</div>
          <div class="forecast-meta">
            <div><strong>Current slice:</strong> {td(item.get('current_slice') or 'Queue not materialized')}</div>
            <div><strong>Milestone ETA:</strong> {td(item.get('next_milestone_eta') or 'unknown')} · <strong>Program ETA:</strong> {td(item.get('program_eta') or 'unknown')}</div>
            <div><strong>Design truth:</strong> {td(item.get('design_truth_freshness') or 'unknown')} · <strong>Review debt:</strong> {td(item.get('review_debt') or 0)}</div>
            <div><strong>Blockers:</strong> {td(item.get('blocker_count') or 0)} · <strong>Status:</strong> {td(item.get('status') or 'unknown')} / {td(item.get('phase') or 'unknown')}</div>
          </div>
        </article>
        """
        for item in mission_group_cards[:6]
    ) or '<div class="empty-state">No mission groups are available yet.</div>'
    command_lane_rows_html = "".join(
        f"""
        <div class="forecast-capacity-row">
          <div>
            <strong>{td(str(item.get('lane') or '').title())}</strong>
            <div class="muted">{td(item.get('provider') or 'unknown')} · {td(item.get('model') or 'unknown')}</div>
            <div class="muted">mission {'yes' if item.get('mission_enabled') else 'no'} · policy {'yes' if item.get('policy_enabled') else 'no'}</div>
          </div>
          <div style="text-align:right;">
            {chip(item.get('remaining_text') or 'unknown', tone=forecast_tone(item.get('state') or ''))}
            <div class="muted">{td(item.get('sustainable_runway') or 'unknown')} · {td('critical path' if item.get('critical_path') else (item.get('policy_reason') or 'mission-ready'))}</div>
          </div>
        </div>
        """
        for item in mission_lane_runway
    ) or '<div class="empty-state">No lane-runway telemetry is available.</div>'
    command_provider_credit_html = (
        f"""
        <div class="forecast-card">
          <div class="forecast-kicker">{td(mission_provider_credit.get('provider') or '1min')} billing truth</div>
          <div class="forecast-title">{td(human_percent(mission_provider_credit.get('remaining_percent_total')) if mission_provider_credit.get('remaining_percent_total') is not None else 'unknown')}</div>
          <div class="forecast-meta">
            <div><strong>Free:</strong> {td(human_int(mission_provider_credit.get('free_credits')) if mission_provider_credit.get('free_credits') is not None else 'unknown')} / {td(human_int(mission_provider_credit.get('max_credits')) if mission_provider_credit.get('max_credits') is not None else 'unknown')}</div>
            <div><strong>Next top-up:</strong> {td(mission_provider_credit.get('next_topup_at') or 'unknown')} · <strong>Amount:</strong> {td(human_int(mission_provider_credit.get('topup_amount')) if mission_provider_credit.get('topup_amount') is not None else 'unknown')}</div>
            <div><strong>Runway:</strong> no top-up {td(mission_provider_credit.get('hours_remaining_at_current_pace_no_topup') or 'unknown')}h · incl. top-up {td(mission_provider_credit.get('hours_remaining_including_next_topup_at_current_pace') or 'unknown')}h</div>
            <div><strong>7d avg:</strong> {td(mission_provider_credit.get('days_remaining_including_next_topup_at_7d_avg') or 'unknown')}d · <strong>Depletes first:</strong> {td('yes' if mission_provider_credit.get('depletes_before_next_topup') else 'no')}</div>
            <div><strong>Basis:</strong> {td(mission_provider_credit.get('basis_quality') or 'unknown')} · <span class="muted">{td(mission_provider_credit.get('basis_summary') or 'unknown')}</span></div>
            <div><strong>Coverage:</strong> {td(mission_provider_credit.get('slot_count_with_billing_snapshot') or 0)} billing slots · {td(mission_provider_credit.get('slot_count_with_member_reconciliation') or 0)} member snapshots</div>
          </div>
        </div>
        """
        if mission_provider_credit
        else '<div class="empty-state">No billing-backed credit telemetry is available.</div>'
    )
    command_blocker_rows_html = "".join(
        f"""
        <div class="forecast-blocker-row">
          <strong>{td(item.get('scope') or 'blocker')}</strong>
          <span>{td(item.get('detail') or 'none')}</span>
        </div>
        """
        for item in (mission_blockers.get("items") or [])
    ) or blocker_rows_html
    command_priority_blockers_html = "".join(
        f"""
        <article class="forecast-card">
          <div class="forecast-kicker">{td(item.get('scope') or 'attention')}</div>
          <div class="forecast-title">{td(item.get('title') or 'attention')}</div>
          <div class="forecast-meta">
            <div>{td(item.get('detail') or 'No detail recorded.')}</div>
          </div>
        </article>
        """
        for item in (mission_blockers.get("priority") or [])[:4]
    ) or '<div class="empty-state">No priority blockers right now.</div>'
    truth_freshness_html = (
        f"<strong>{td(truth_freshness.get('summary') or 'No truth-freshness summary available.')}</strong>"
        f"<div class=\"muted\">state {td(truth_freshness.get('state') or 'unknown')} · published {td(truth_freshness.get('generated_at') or 'unknown')}</div>"
    )
    explorer_snapshot_cards_html = "".join(
        [
            f"""
            <article class="mission-card">
              <div class="mission-label">Current Slice</div>
              <div class="mission-value">{td((mission_board.get('current_slice') or {}).get('title') or 'Idle')}</div>
              <div class="muted">stage {td(execution_loop.get('current_stage_label') or 'Idle')} · round {td(execution_loop.get('round_label') or 'r0 / r0')}</div>
              <div class="muted">{td(execution_loop.get('next_reviewer_summary') or 'No reviewer is pending.')} · {td(execution_loop.get('landing_summary') or 'No landing lane is active.')}</div>
            </article>
            """,
            f"""
            <article class="mission-card">
              <div class="mission-label">Stop Condition</div>
              <div class="mission-value">{td((mission_blockers.get('stop_sentence') or 'Forever on trend.'))}</div>
              <div class="muted">truth freshness {td(truth_freshness.get('state') or 'unknown')} · generated {td(truth_freshness.get('generated_at') or 'unknown')}</div>
            </article>
            """,
            f"""
            <article class="mission-card">
              <div class="mission-label">Raw Ops Snapshot</div>
              <div class="mission-value">{td(int(worker_breakdown.get('active_coding_workers') or 0))} coding · {td(int(worker_breakdown.get('active_review_workers') or 0))} review</div>
              <div class="muted">{td(len(attention_items))} attention · {td(len(approval_items))} approvals · {td(len(incident_items))} incidents</div>
              <div class="muted">contract {td(mission_board.get('contract_name') or 'fleet.mission_board')} · v{td(mission_board.get('contract_version') or 'unknown')}</div>
            </article>
            """,
            f"""
            <article class="mission-card">
              <div class="mission-label">Explorer Focus</div>
              <div class="mission-value">Projects, Groups, Reviews, Accounts, Routing, History</div>
              <div class="muted">Use the tabs below for raw queue/runtime truth, routing history, audit, and settings.</div>
            </article>
            """,
        ]
    )

    bridge_active_slice_html = "".join(
        f"""
        <article class="mini-card">
          <div class="mini-head">
            <strong>{td(worker.get('project_id'))}</strong>
            {chip(worker.get('phase') or WAITING_CAPACITY_STATUS, tone=severity_tone(worker.get('phase') or WAITING_CAPACITY_STATUS))}
          </div>
          <div class="mini-body">{td(worker.get('current_slice') or 'No active slice')}</div>
          <div class="mini-meta">
            {td(worker.get('account_alias') or 'unassigned')} · {td(worker.get('account_backend') or 'n/a')} · {td(worker.get('brain') or worker.get('model') or '')} · {td(worker.get('elapsed_human') or '')}
          </div>
        </article>
        """
        for worker in [item for item in worker_cards if str(item.get('phase') or '') in {'coding', 'verifying'}][:6]
    ) or '<div class="empty-state">No active coding slices right now.</div>'

    bridge_review_gate_html = "".join(
        f"""
        <article class="mini-card">
          <div class="mini-head">
            <strong>{td(item.get('title') or item.get('kind') or 'review item')}</strong>
            {chip(item.get('kind') or 'review', tone=severity_tone(item.get('severity') or item.get('kind') or 'warn'))}
          </div>
          <div class="mini-body">{td(item.get('detail') or '')}</div>
          <div class="actions mini-actions">{''.join(render_action(action) for action in (item.get('actions') or [])[:2])}</div>
        </article>
        """
        for item in approval_items[:4]
    ) or '<div class="empty-state">No review or approval waits.</div>'

    healer_activity_items: List[Dict[str, Any]] = []
    for group in groups:
        status_value = str(group.get("status") or "").strip().lower()
        if status_value in {"audit_requested", "audit_required", "proposed_tasks"}:
            healer_activity_items.append(
                {
                    "label": f"group:{group.get('id')}",
                    "status": status_value,
                    "detail": group.get("dispatch_basis") or group.get("operator_question") or "group healer activity",
                    "action": {"label": "Open group", "href": f"/admin/groups/{group['id']}", "method": "get"},
                }
            )
    for project in projects:
        runtime_status = str(project.get("runtime_status") or "").strip().lower()
        if runtime_status in {HEALING_STATUS, QUEUE_REFILLING_STATUS, REVIEW_FIX_STATUS}:
            healer_activity_items.append(
                {
                    "label": f"project:{project.get('id')}",
                    "status": runtime_status,
                    "detail": project.get("next_action") or project.get("stop_reason") or "project healer activity",
                    "action": {"label": "Open Explorer", "href": "/admin/details#projects", "method": "get"},
                }
            )
    bridge_healer_html = "".join(
        f"""
        <article class="mini-card">
          <div class="mini-head">
            <strong>{td(item.get('label'))}</strong>
            {chip(item.get('status') or 'healing', tone=severity_tone(item.get('status') or 'healing'))}
          </div>
          <div class="mini-body">{td(item.get('detail') or '')}</div>
          <div class="actions mini-actions">{render_action(item.get('action') or {})}</div>
        </article>
        """
        for item in healer_activity_items[:5]
    ) or '<div class="empty-state">No healer-owned activity right now.</div>'
    healer_status_label = str(auditor_run.get("status") or "").strip() or ("active" if healer_activity_items else "quiet")

    settings_grid_html = f"""
    <div class="settings-grid">
      <div class="panel">
        <h3>Routing Policy</h3>
        <form method="post" action="/api/admin/routing/update">
          <label for="classification_mode">Classification Mode</label>
          <input id="classification_mode" name="classification_mode" type="text" value="{td(spider.get('classification_mode') or 'evidence_v1')}" />
          <label for="feedback_file_window">Feedback Window</label>
          <input id="feedback_file_window" name="feedback_file_window" type="text" value="{td(spider.get('feedback_file_window') or 2)}" />
          <label for="escalate_to_complex_after_failures">Escalate After Failures</label>
          <input id="escalate_to_complex_after_failures" name="escalate_to_complex_after_failures" type="text" value="{td(spider.get('escalate_to_complex_after_failures') or 2)}" />
          <label for="token_alliance_window_hours">Token Alliance Window Hours</label>
          <input id="token_alliance_window_hours" name="token_alliance_window_hours" type="text" value="{td(spider.get('token_alliance_window_hours') or 24)}" />
          <p><button type="submit">Save routing</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Add or Update Account</h3>
        <form method="post" action="/api/admin/accounts/upsert">
          <label for="alias">Alias</label>
          <input id="alias" name="alias" type="text" placeholder="acct-ui-a" required />
          <label for="auth_kind">Auth Kind</label>
          <input id="auth_kind" name="auth_kind" type="text" value="chatgpt_auth_json" />
          <label for="allowed_models">Allowed Models</label>
          <textarea id="allowed_models" name="allowed_models" placeholder="gpt-5.3-codex-spark&#10;gpt-5.3-codex&#10;gpt-5-mini"></textarea>
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
          <p><button type="submit">Save account</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Project Account Policy</h3>
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
          <p><button type="submit">Save project policy</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Project Review Policy</h3>
        <form method="post" action="/api/admin/projects/core/review-policy" onsubmit="this.action='/api/admin/projects/' + encodeURIComponent(this.project_id.value || 'core') + '/review-policy'">
          <label for="review_policy_project_id">Project ID</label>
          <input id="review_policy_project_id" name="project_id" type="text" value="core" />
          <label><input name="enabled" type="checkbox" value="1" checked /> Review Enabled</label>
          <label><input name="required_before_queue_advance" type="checkbox" value="1" checked /> Require Review Before Queue Advance</label>
          <label for="review_mode">Mode</label>
          <input id="review_mode" name="mode" type="text" value="github" />
          <label for="review_trigger">Trigger</label>
          <input id="review_trigger" name="trigger" type="text" value="manual_comment" />
          <label for="review_owner">GitHub Owner</label>
          <input id="review_owner" name="owner" type="text" placeholder="ArchonMegalon" />
          <label for="review_repo">GitHub Repo</label>
          <input id="review_repo" name="repo" type="text" placeholder="chummer6-core" />
          <label for="review_base_branch">Base Branch</label>
          <input id="review_base_branch" name="base_branch" type="text" value="main" />
          <label for="review_branch_template">Branch Template</label>
          <input id="review_branch_template" name="branch_template" type="text" value="fleet/core" />
          <label for="review_focus_template">Review Focus</label>
          <input id="review_focus_template" name="focus_template" type="text" value="for regressions and missing tests" />
          <label for="review_bot_logins">Bot Logins</label>
          <textarea id="review_bot_logins" name="bot_logins" placeholder="codex"></textarea>
          <p><button type="submit">Save review policy</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Project Auto-Heal Policy</h3>
        <form method="post" action="/api/admin/projects/core/auto-heal" onsubmit="this.action='/api/admin/projects/' + encodeURIComponent(this.project_id.value || 'core') + '/auto-heal'">
          <label for="auto_heal_project_id">Project ID</label>
          <input id="auto_heal_project_id" name="project_id" type="text" value="core" />
          <label><input name="enabled" type="checkbox" value="1" {'checked' if default_project_auto_heal_enabled else ''} /> Enable Auto-Heal Override</label>
          <label><input name="coverage" type="checkbox" value="1" {'checked' if default_project_auto_heal_categories.get('coverage') else ''} /> Coverage</label>
          <label><input name="review" type="checkbox" value="1" {'checked' if default_project_auto_heal_categories.get('review') else ''} /> Review</label>
          <label><input name="capacity" type="checkbox" value="1" {'checked' if default_project_auto_heal_categories.get('capacity') else ''} /> Capacity</label>
          <label><input name="contracts" type="checkbox" value="1" {'checked' if default_project_auto_heal_categories.get('contracts') else ''} /> Contracts</label>
          <p><button type="submit">Save project auto-heal</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Group Captain Policy</h3>
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
          <p><button type="submit">Save captain policy</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Group Auto-Heal Policy</h3>
        <form method="post" action="/api/admin/groups/chummer-vnext/auto-heal" onsubmit="this.action='/api/admin/groups/' + encodeURIComponent(this.group_id.value || 'chummer-vnext') + '/auto-heal'">
          <label for="auto_heal_group_id">Group ID</label>
          <input id="auto_heal_group_id" name="group_id" type="text" value="chummer-vnext" />
          <label><input name="enabled" type="checkbox" value="1" {'checked' if default_group_auto_heal_enabled else ''} /> Enable Auto-Heal Override</label>
          <label><input name="coverage" type="checkbox" value="1" {'checked' if default_group_auto_heal_categories.get('coverage') else ''} /> Coverage</label>
          <label><input name="review" type="checkbox" value="1" {'checked' if default_group_auto_heal_categories.get('review') else ''} /> Review</label>
          <label><input name="capacity" type="checkbox" value="1" {'checked' if default_group_auto_heal_categories.get('capacity') else ''} /> Capacity</label>
          <label><input name="contracts" type="checkbox" value="1" {'checked' if default_group_auto_heal_categories.get('contracts') else ''} /> Contracts</label>
          <p><button type="submit">Save group auto-heal</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Routing Class Policy</h3>
        <form method="post" action="/api/admin/routing/classes/micro_edit" onsubmit="this.action='/api/admin/routing/classes/' + encodeURIComponent(this.route_class.value || 'micro_edit')">
          <label for="route_class">Route Class</label>
          <input id="route_class" name="route_class" type="text" value="micro_edit" />
          <label for="route_models">Models</label>
          <textarea id="route_models" name="models" placeholder="gpt-5.3-codex-spark&#10;gpt-5.3-codex&#10;gpt-5-mini"></textarea>
          <label for="route_reasoning_effort">Reasoning Effort</label>
          <input id="route_reasoning_effort" name="reasoning_effort" type="text" value="low" />
          <label for="route_estimated_output_tokens">Estimated Output Tokens</label>
          <input id="route_estimated_output_tokens" name="estimated_output_tokens" type="text" value="1024" />
          <p><button type="submit">Save route class</button></p>
        </form>
      </div>

      <div class="panel">
        <h3>Bootstrap Project</h3>
        <form method="post" action="/api/admin/projects/bootstrap">
          <label for="project_id">Project ID</label>
          <input id="project_id" name="project_id" type="text" placeholder="ui-kit" required />
          <label for="repo_path">Repo Path</label>
          <input id="repo_path" name="repo_path" type="text" placeholder="/docker/chummercomplete/chummer-ui-kit" required />
          <label for="group_id">Group ID</label>
          <input id="group_id" name="group_id" type="text" placeholder="chummer-vnext" />
          <label for="design_doc">Design Doc</label>
          <input id="design_doc" name="design_doc" type="text" placeholder="/docker/chummercomplete/chummer-design/products/chummer/projects/ui-kit.md" />
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
          <input id="github_repo" name="github_repo" type="text" placeholder="chummer6-ui-kit" />
          <label for="github_visibility">GitHub Visibility</label>
          <input id="github_visibility" name="github_visibility" type="text" value="private" />
          <label><input name="create_repo_dir" type="checkbox" value="1" checked /> Create repo directory if missing</label>
          <label><input name="bootstrap_files" type="checkbox" value="1" checked /> Bootstrap repo-local AI files</label>
          <label><input name="init_local_git" type="checkbox" value="1" checked /> Initialize local git repo</label>
          <label><input name="create_github_repo" type="checkbox" value="1" /> Create GitHub repo with <code>gh</code></label>
          <p><button type="submit">Bootstrap project</button></p>
        </form>
      </div>
    </div>
    """

    if not show_details:
        return f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>{APP_TITLE}</title>
            <style>
              :root {{
                --bg: #efe5d4;
                --panel: #fffaf3;
                --line: #ccb99a;
                --text: #1d1711;
                --muted: #6a5844;
                --accent: #0d5c63;
                --danger: #8a3626;
                --warn: #946115;
                --good: #2f6b44;
                --shadow: 0 18px 44px rgba(31, 26, 20, 0.10);
              }}
              * {{ box-sizing: border-box; }}
              body {{
                margin: 0;
                font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
                background: var(--bg);
                color: var(--text);
              }}
              .page {{ width: min(1480px, calc(100vw - 28px)); margin: 0 auto 36px; padding: 20px 0 0; }}
              .hero, .panel {{
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 24px;
                padding: 20px;
                box-shadow: var(--shadow);
              }}
              .hero {{
                background:
                  radial-gradient(circle at top right, rgba(13,92,99,0.12), transparent 32%),
                  linear-gradient(145deg, #fff8ef 0%, #fffaf3 52%, #f4ecde 100%);
              }}
              .hero-top, .panel-head {{
                display: flex;
                justify-content: space-between;
                gap: 16px;
                align-items: flex-start;
                flex-wrap: wrap;
              }}
              .hero-kicker {{ font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }}
              .hero h1, .panel h2 {{ margin: 0; }}
              .muted {{ color: var(--muted); }}
              .hero-links, .actions {{ display: flex; flex-wrap: wrap; gap: 10px; }}
              .hero-link, .action-btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 10px 14px;
                border-radius: 999px;
                border: 1px solid var(--line);
                background: #f7f0e3;
                color: var(--text);
                text-decoration: none;
                font-weight: 600;
              }}
              .forecast-strip {{
                margin-top: 18px;
                padding: 18px 20px;
                border-radius: 22px;
                background: linear-gradient(135deg, #0d5c63, #1e7a74);
                color: #f7fbf8;
              }}
              .forecast-strip strong {{
                display: inline-block;
                margin-right: 8px;
                font-size: 13px;
                letter-spacing: 0.06em;
                text-transform: uppercase;
              }}
              .forecast-grid {{
                display: grid;
                grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
                gap: 18px;
                margin-top: 18px;
              }}
              .forecast-main, .forecast-side {{ display: grid; gap: 18px; }}
              .timeline-grid {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 12px;
              }}
              .forecast-card {{
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 16px;
                background: #fffdf9;
              }}
              .forecast-kicker {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }}
              .forecast-title {{ margin: 8px 0 10px; font-size: 24px; line-height: 1.15; }}
              .forecast-meta {{ display: grid; gap: 8px; color: var(--muted); font-size: 14px; }}
              .forecast-capacity-row, .forecast-blocker-row {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: flex-start;
                padding: 10px 0;
                border-top: 1px solid var(--line);
              }}
              .forecast-capacity-row:first-child, .forecast-blocker-row:first-child {{ border-top: none; padding-top: 0; }}
              .details-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 10px;
                margin-top: 12px;
              }}
              .detail-link {{
                display: block;
                padding: 14px;
                border-radius: 14px;
                border: 1px solid var(--line);
                background: #f7f0e3;
                text-decoration: none;
                color: var(--text);
              }}
              .detail-link strong {{ display: block; margin-bottom: 4px; }}
              code {{ background: #f7f0e3; padding: 2px 4px; border-radius: 6px; }}
              .chip {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 10px;
                border-radius: 999px;
                border: 1px solid var(--line);
                background: #f7f0e3;
                font-size: 12px;
                font-weight: 700;
              }}
              .tone-danger {{ background: #f3d4cf; color: var(--danger); }}
              .tone-warn {{ background: #f4e7c4; color: var(--warn); }}
              .tone-good {{ background: #d8eadc; color: var(--good); }}
              .tone-muted {{ background: #e7dfd1; color: var(--muted); }}
              .empty-state {{
                border: 1px dashed var(--line);
                border-radius: 16px;
                padding: 16px;
                color: var(--muted);
                background: rgba(255,255,255,0.55);
              }}
              @media (max-width: 1080px) {{
                .forecast-grid, .timeline-grid {{ grid-template-columns: 1fr; }}
              }}
            </style>
          </head>
          <body>
            <!-- Fleet Raw Details -->
            <div class="page">
              <section class="hero">
                <div class="hero-top">
                  <div>
                    <div class="hero-kicker">Command Deck</div>
                    <h1>{APP_TITLE}</h1>
                    <p><strong>Desired state:</strong> <code>{td(str(CONFIG_PATH))}</code> · <strong>Runtime state:</strong> <code>{td(str(DB_PATH))}</code></p>
                    <p class="muted">Forecast-first operator truth. Slice horizon, queue horizon, vision horizon, and capacity stop conditions live here; inventory and raw controls stay in <code>/admin/details</code>.</p>
                  </div>
                  <div class="hero-links">
                    <a class="hero-link" href="/">Fleet Dashboard</a>
                    <a class="hero-link" href="/studio">Studio</a>
                    <a class="hero-link" href="/admin/details">Open Explorer</a>
                    <a class="hero-link" href="/api/admin/status">Status API</a>
                  </div>
                </div>
                <div class="forecast-strip"><strong>Mission Forecast</strong>{td(mission_snapshot.get('headline') or cockpit_summary.get('mission_headline') or 'No forecast is available right now.')}</div>
              </section>

              <section class="forecast-grid">
                <div class="forecast-main">
                  <section class="panel">
                    <div class="panel-head">
                      <div>
                        <h2>Active Loop</h2>
                        <p class="muted">Current slice, next transition, and the cheap review loop that will decide whether jury can land.</p>
                      </div>
                    </div>
                    <div class="timeline-grid">
                      <article class="forecast-card">
                        <div class="forecast-kicker">Current Slice</div>
                        <div class="forecast-title">{td((mission_board.get('current_slice') or {}).get('title') or 'Idle')}</div>
                        <div class="forecast-meta">
                          <div><strong>Stage:</strong> {td(execution_loop.get('current_stage_label') or 'Idle')} · <strong>Round:</strong> {td(execution_loop.get('round_label') or 'r0 / r0')}</div>
                          <div><strong>Lane:</strong> {td((mission_board.get('current_slice') or {}).get('lane') or 'unknown')} · <strong>Provider:</strong> {td((mission_board.get('current_slice') or {}).get('provider') or 'unknown')} · <strong>Brain:</strong> {td((mission_board.get('current_slice') or {}).get('brain') or 'unknown')}</div>
                          <div><strong>ETA:</strong> {td((mission_board.get('current_slice') or {}).get('eta') or 'unknown')} · <strong>Review ahead:</strong> {td((mission_board.get('current_slice') or {}).get('review_ahead') or 'no')} · <strong>Rounds left:</strong> {td(execution_loop.get('rounds_remaining') or 0)}</div>
                          <div><strong>Next reviewer:</strong> {td(execution_loop.get('next_reviewer_lane') or 'n/a')} · <strong>Landing lane:</strong> {td(execution_loop.get('landing_lane') or 'n/a')}</div>
                          <div><strong>Policy:</strong> {td(execution_loop.get('policy_summary') or 'No cheap-loop policy recorded.')}</div>
                          <div><strong>Accepted r1/r2/r3:</strong> {td(((execution_loop.get('telemetry_review_loop') or {}).get('accepted_on_round_counts') or {}).get('1') or 0)} / {td(((execution_loop.get('telemetry_review_loop') or {}).get('accepted_on_round_counts') or {}).get('2') or 0)} / {td(((execution_loop.get('telemetry_review_loop') or {}).get('accepted_on_round_counts') or {}).get('3') or 0)} · <strong>Shadow assist:</strong> {td(int(float(((execution_loop.get('telemetry_review_loop') or {}).get('shadow_assist_rate') or 0.0) * 100)))}%</div>
                          <div><strong>Busy primary/shadow/jury:</strong> {td((execution_loop.get('telemetry_worker_utilization') or {}).get('groundwork_primary_busy_percent') or 0)}% / {td((execution_loop.get('telemetry_worker_utilization') or {}).get('groundwork_shadow_busy_percent') or 0)}% / {td((execution_loop.get('telemetry_worker_utilization') or {}).get('jury_busy_percent') or 0)}%</div>
                        </div>
                      </article>
                      <article class="forecast-card">
                        <div class="forecast-kicker">Next Transition</div>
                        <div class="forecast-title">{td((mission_board.get('next_transition') or {}).get('title') or 'No next slice materialized')}</div>
                        <div class="forecast-meta">
                          <div><strong>Lane:</strong> {td((mission_board.get('next_transition') or {}).get('lane') or 'unknown')} · <strong>Confidence:</strong> {chip((mission_board.get('next_transition') or {}).get('confidence') or 'unknown', tone=forecast_tone((mission_board.get('next_transition') or {}).get('confidence') or ''))}</div>
                          <div><strong>Prerequisites:</strong> {td((mission_board.get('next_transition') or {}).get('prerequisites') or 'none')}</div>
                          <div><strong>Reason:</strong> {td((mission_board.get('next_transition') or {}).get('reason') or 'No queue reason recorded.')}</div>
                          <div><strong>Next reviewer:</strong> {td(execution_loop.get('next_reviewer_lane') or 'n/a')} · <strong>Landing lane:</strong> {td(execution_loop.get('landing_lane') or 'n/a')}</div>
                        </div>
                      </article>
                      {command_loop_timeline_html}
                    </div>
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <div>
                        <h2>Mission Groups</h2>
                        <p class="muted">Group-first mission view: objective, current slice, dispatchability, blocker count, and review debt.</p>
                      </div>
                      {chip(f"{len(mission_group_cards)} groups", tone='muted')}
                    </div>
                    <div class="timeline-grid">{command_group_cards_html}</div>
                  </section>
                </div>

                <div class="forecast-side">
                  <section class="panel">
                    <div class="panel-head">
                      <div>
                        <h2>Lane Runway</h2>
                        <p class="muted">Foreground lane, provider, allowance, sustainable runway, and whether policy currently allows the lane to matter.</p>
                      </div>
                    </div>
                    {command_lane_rows_html}
                    <div class="forecast-capacity-row">
                      <div><strong>Mission runway</strong><div class="muted">Critical path lane: {td((mission_board.get('capacity') or {}).get('critical_path_lane') or capacity_forecast.get('critical_path_lane') or 'unknown')}</div></div>
                      <div>{td((mission_board.get('capacity') or {}).get('mission_runway') or capacity_forecast.get('mission_runway') or 'unknown')}</div>
                    </div>
                    <div class="forecast-capacity-row">
                      <div><strong>Pool runway</strong><div class="muted">Next reset windows</div></div>
                      <div>{td((mission_board.get('capacity') or {}).get('pool_runway') or capacity_forecast.get('pool_runway') or 'unknown')}</div>
                    </div>
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <div>
                        <h2>Billing Truth</h2>
                        <p class="muted">1min billing-backed runway, next top-up, and reconciliation coverage from EA status.</p>
                      </div>
                    </div>
                    {command_provider_credit_html}
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <div>
                        <h2>Blockers</h2>
                        <p class="muted">Only the blockers that stop the current slice, the next transition, or the mission horizon belong on the home screen.</p>
                      </div>
                    </div>
                    {command_blocker_rows_html}
                    <div class="forecast-card" style="margin-top:12px;">
                      <div class="forecast-kicker">Stop Condition</div>
                      <div class="forecast-meta">
                        <div><strong>{td((mission_blockers.get('stop_sentence') or 'Forever on trend.'))}</strong></div>
                      </div>
                    </div>
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <div>
                        <h2>Mission Horizon</h2>
                        <p class="muted">Milestone ETA, vision ETA, and truth freshness stay above raw subsystem inventory.</p>
                      </div>
                    </div>
                    <div class="timeline-grid">
                      <article class="forecast-card">
                        <div class="forecast-kicker">Milestone</div>
                        <div class="forecast-title">{td((mission_board.get('mission_horizon') or {}).get('milestone_title') or vision_forecast.get('milestone_title') or 'unknown')}</div>
                        <div class="forecast-meta">
                          <div><strong>ETA:</strong> {td((mission_board.get('mission_horizon') or {}).get('milestone_eta') or vision_forecast.get('milestone_eta') or 'unknown')}</div>
                          <div><strong>Confidence:</strong> {td((mission_board.get('mission_horizon') or {}).get('confidence') or vision_forecast.get('confidence') or 'unknown')}</div>
                        </div>
                      </article>
                      <article class="forecast-card">
                        <div class="forecast-kicker">Vision</div>
                        <div class="forecast-title">p50 {td((mission_board.get('mission_horizon') or {}).get('vision_eta_p50') or vision_forecast.get('vision_eta_p50') or 'unknown')}</div>
                        <div class="forecast-meta">
                          <div><strong>p90:</strong> {td((mission_board.get('mission_horizon') or {}).get('vision_eta_p90') or vision_forecast.get('vision_eta_p90') or 'unknown')}</div>
                          <div><strong>Freshness:</strong> {td(truth_freshness.get('state') or 'unknown')}</div>
                        </div>
                      </article>
                      <article class="forecast-card">
                        <div class="forecast-kicker">Truth Freshness</div>
                        <div class="forecast-meta">{truth_freshness_html}</div>
                      </article>
                    </div>
                  </section>

                  <section class="panel">
                    <div class="panel-head">
                      <div>
                        <h2>Drilldowns</h2>
                        <p class="muted">Raw controls, routing, accounts, audits, and history move to the explorer.</p>
                      </div>
                    </div>
                    <div class="details-grid">
                      <a class="detail-link" href="/admin/details#projects"><strong>Projects</strong><span class="muted">Queue status, current slice, milestone ETA, uncovered scope, accounts.</span></a>
                      <a class="detail-link" href="/admin/details#groups"><strong>Groups</strong><span class="muted">Dispatch blockers, contract sets, signoff truth, program ETA.</span></a>
                      <a class="detail-link" href="/admin/details#reviews"><strong>Reviews</strong><span class="muted">GitHub/local review status and blocking findings.</span></a>
                      <a class="detail-link" href="/admin/details#audit"><strong>Audit</strong><span class="muted">Open findings and publishable candidate tasks.</span></a>
                      <a class="detail-link" href="/admin/details#accounts"><strong>Accounts</strong><span class="muted">Pool state, budgets, auth, parallelism, and backoff.</span></a>
                      <a class="detail-link" href="/admin/details#routing"><strong>Routing</strong><span class="muted">Route classes, price table, and recent routing decisions.</span></a>
                    </div>
                  </section>
                </div>
              </section>

              <section class="panel">
                <div class="panel-head">
                  <div>
                    <h2>Secondary Signals</h2>
                    <p class="muted">Priority attention items stay visible, but lamps and subsystem trivia no longer drive the layout.</p>
                  </div>
                  {chip(f"{len(attention_items)} attention / {len(red_incident_items)} incidents")}
                </div>
                <div class="timeline-grid">
                  <div class="forecast-card">{consistency_warning_html}</div>
                  <div class="forecast-card">{command_priority_blockers_html}</div>
                  <div class="forecast-card">{incident_html}</div>
                </div>
              </section>
            </div>
          </body>
        </html>
        """

    if show_details:
        return f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>{APP_TITLE}</title>
            <style>
              :root {{
                --bg: #f4f1ea;
                --panel: #fffdfa;
                --line: #d3c8b6;
                --line-strong: #a6967d;
                --text: #1f1a14;
                --muted: #645848;
                --accent: #215e63;
                --danger: #8f2f1f;
                --warn: #946115;
                --good: #2d6a3f;
                --shadow: 0 12px 30px rgba(31, 26, 20, 0.08);
              }}
              * {{ box-sizing: border-box; }}
              body {{
                margin: 0;
                font-family: ui-sans-serif, system-ui, sans-serif;
                background: var(--bg);
                color: var(--text);
              }}
              a {{ color: inherit; }}
              code {{ background: #f1ece1; padding: 2px 6px; border-radius: 8px; }}
              .page {{ width: min(1500px, calc(100vw - 28px)); margin: 16px auto 28px; }}
              .hero, .panel {{
                background: var(--panel);
                border: 1px solid var(--line);
                border-radius: 22px;
                box-shadow: var(--shadow);
                padding: 20px;
                margin-bottom: 16px;
              }}
              .hero-top, .panel-head, .worker-top, .attention-head, .approval-head {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: flex-start;
              }}
              .hero-links, .actions {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
              }}
              .hero-link, .action-btn {{
                border: 1px solid var(--line-strong);
                border-radius: 999px;
                padding: 9px 12px;
                text-decoration: none;
                background: #f8f4ec;
                color: var(--text);
                font-weight: 700;
              }}
              .action-btn.primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
              .muted {{ color: var(--muted); }}
              .mission-strip, .lamp-strip {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
                gap: 10px;
                margin-top: 14px;
              }}
              .mission-card, .lamp-card {{
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 14px;
                background: #fffaf3;
                text-decoration: none;
                color: inherit;
                text-align: left;
                width: 100%;
                cursor: pointer;
              }}
              .lamp-card {{
                appearance: none;
                font: inherit;
              }}
              .mission-card-wide {{ grid-column: span 2; }}
              .mission-label, .lamp-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
              .mission-value, .lamp-value {{ font-size: 24px; font-weight: 800; margin-top: 6px; }}
              .lamp-detail {{ margin-top: 8px; font-size: 13px; color: var(--muted); }}
              .lamp-danger {{ border-color: #d29b94; background: #fff1ef; }}
              .lamp-warn {{ border-color: #d4bb86; background: #fff8e9; }}
              .lamp-good {{ border-color: #9ec6a7; background: #f1fbf3; }}
              .chip {{
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 4px 9px;
                background: #eee6d7;
                font-size: 12px;
                font-weight: 800;
              }}
              .tone-danger {{ background: #f3d4cf; color: var(--danger); }}
              .tone-warn {{ background: #f4e7c4; color: var(--warn); }}
              .tone-good {{ background: #d8eadc; color: var(--good); }}
              .tone-muted {{ background: #e7dfd1; color: var(--muted); }}
              .cockpit-grid {{
                display: grid;
                grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
                gap: 16px;
                align-items: start;
              }}
              .stack {{ display: grid; gap: 16px; }}
              .attention-list, .approval-list, .worker-grid {{
                display: grid;
                gap: 10px;
              }}
              .worker-grid {{ grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
              .attention-item, .approval-item, .worker-card {{
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 14px;
                background: #fffaf3;
              }}
              .severity-danger {{ border-color: #d29b94; background: #fff1ef; }}
              .severity-warn {{ border-color: #d4bb86; background: #fff8e9; }}
              .worker-slice {{ margin: 10px 0; font-weight: 700; }}
              .worker-meta {{ display: flex; gap: 12px; flex-wrap: wrap; font-size: 13px; }}
              .progress-stack {{ display: grid; gap: 6px; margin-top: 10px; }}
              .progress-bar {{
                display: flex;
                height: 10px;
                border-radius: 999px;
                overflow: hidden;
                background: #e9e1d4;
                border: 1px solid var(--line);
              }}
              .progress-segment {{ display: block; height: 100%; }}
              .progress-complete {{ background: #5a8f65; }}
              .progress-inflight {{ background: #4d7ea8; }}
              .progress-blocked {{ background: #b55a4c; }}
              .progress-unmaterialized {{ background: #bdb3a6; }}
              .empty-state {{ border: 1px dashed var(--line); border-radius: 18px; padding: 18px; color: var(--muted); }}
              .card-link {{
                border: none;
                background: none;
                padding: 0;
                color: inherit;
                font: inherit;
                font-weight: 700;
                cursor: pointer;
                text-decoration: underline;
                text-underline-offset: 0.12em;
              }}
              .details-launch {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
              }}
              .drawer-stack {{
                display: grid;
                gap: 12px;
              }}
              .drawer-panel {{
                border: 1px solid var(--line);
                border-radius: 16px;
                background: #fffaf3;
                padding: 0;
                overflow: hidden;
              }}
              .drawer-panel summary {{
                list-style: none;
                cursor: pointer;
                padding: 14px 16px;
                font-weight: 700;
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
              }}
              .drawer-panel summary::-webkit-details-marker {{ display: none; }}
              .drawer-body {{ padding: 0 16px 16px; }}
              .bridge-grid {{
                display: grid;
                grid-template-columns: 1fr;
                gap: 16px;
                align-items: start;
              }}
              .bridge-main, .bridge-side {{
                display: grid;
                gap: 16px;
              }}
              .bridge-row {{
                display: grid;
                grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.9fr);
                gap: 16px;
                align-items: start;
              }}
              .bridge-strip {{
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 16px;
              }}
              .mini-grid {{
                display: grid;
                gap: 10px;
                grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
              }}
              .mini-card {{
                border: 1px solid var(--line);
                border-radius: 16px;
                padding: 12px;
                background: #fffaf3;
              }}
              .mini-head {{
                display: flex;
                justify-content: space-between;
                gap: 10px;
                align-items: flex-start;
              }}
              .mini-body {{
                margin-top: 8px;
                font-weight: 700;
                line-height: 1.35;
              }}
              .mini-meta {{
                margin-top: 6px;
                color: var(--muted);
                font-size: 13px;
              }}
              .mini-actions {{
                margin-top: 10px;
              }}
              .incident-rail {{
                display: grid;
                gap: 10px;
              }}
              .incident-rail .attention-item {{
                padding: 12px;
              }}
              form {{ margin: 0; }}
              @media (max-width: 1180px) {{
                .bridge-grid, .bridge-row, .bridge-strip {{ grid-template-columns: 1fr; }}
              }}
            </style>
          </head>
          <body>
            <div class="page">
              <section class="hero">
                <div class="hero-top">
                  <div>
                    <div class="muted" style="text-transform:uppercase; letter-spacing:0.08em; font-size:12px;">Fleet Explorer</div>
                    <h1 style="margin:6px 0 8px;">{APP_TITLE}</h1>
                    <p><strong>Desired state:</strong> <code>{td(str(CONFIG_PATH))}</code> · <strong>Runtime state:</strong> <code>{td(str(DB_PATH))}</code></p>
                    <p class="muted"><strong>Best next action:</strong> {td(cockpit_summary.get('recommended_action') or 'No urgent action right now')}</p>
                  </div>
                  <div class="hero-links">
                    <a class="hero-link" href="/">Fleet Dashboard</a>
                    <a class="hero-link" href="/studio">Studio</a>
                    <a class="hero-link" href="/admin/details">Open Explorer</a>
                  </div>
                </div>
              </section>

              <section class="bridge-grid">
                <div class="bridge-main">
                  <div class="bridge-row">
                    <div class="panel">
                      <div class="panel-head">
                        <div>
                          <h2 style="margin:0;">Group Mission Cards</h2>
                          <p class="muted">Top mission groups only: current bottleneck, runway risk, and captain levers.</p>
                        </div>
                        {chip(f"{len(runway.get('groups') or [])} groups", tone='muted')}
                      </div>
                      <div class="worker-grid">{group_cards_html}</div>
                    </div>

                    <div class="panel">
                      <div class="panel-head">
                        <div>
                          <h2 style="margin:0;">Incident Rail</h2>
                          <p class="muted">Red incidents only. Yellow healing stays in the lower healer lane.</p>
                        </div>
                        {chip(f"{len(red_incident_items)} red", tone='danger' if red_incident_items else 'good')}
                      </div>
                      <div class="incident-rail">{incident_html}</div>
                      <div class="worker-meta muted" style="margin-top:12px;">
                        <span>{td(len(review_failure_incidents))} review failed</span>
                        <span>{td(len(review_stalled_incidents))} review stalled</span>
                        <span>{td(len(blocked_unresolved_incidents))} blocked unresolved</span>
                      </div>
                    </div>
                  </div>

                  <div class="bridge-row">
                    <div class="panel">
                      <div class="panel-head">
                        <div>
                          <h2 style="margin:0;">Pool Runway</h2>
                          <p class="muted">Only the most pressured pools and the levers that change fleet posture quickly.</p>
                        </div>
                        {chip(f"{len(runway.get('accounts') or [])} pools", tone='warn' if (runway.get('accounts') or []) else 'muted')}
                      </div>
                      <div class="approval-list">{account_pressure_cards_html}</div>
                    </div>

                    <div class="panel">
                      <div class="panel-head">
                        <div>
                          <h2 style="margin:0;">Auto-Heal and Lamps</h2>
                          <p class="muted">Stable control signals plus direct category policy toggles from the bridge.</p>
                        </div>
                        {chip('auto' if cockpit_summary.get('auto_heal_enabled') else 'paused', tone='good' if cockpit_summary.get('auto_heal_enabled') else 'warn')}
                      </div>
                      <div class="lamp-strip">{lamp_strip_html}</div>
                      <div class="chip-row" style="margin-top:12px;">
                        {"".join(
                            f'<form method="post" action="/api/admin/policies/auto-heal/category/{td(category)}" style="display:inline-flex; margin:0;">'
                            f'<input type="hidden" name="enabled" value="{td("0" if ((cockpit_summary.get("auto_heal_categories") or {}).get(category)) else "1")}" />'
                            f'<button class="chip {"ok" if ((cockpit_summary.get("auto_heal_categories") or {}).get(category)) else "muted"}" type="submit">{td(category)}: {td("auto" if ((cockpit_summary.get("auto_heal_categories") or {}).get(category)) else "manual")}</button>'
                            f'</form>'
                            for category in ("coverage", "review", "capacity", "contracts")
                        )}
                      </div>
                    </div>
                  </div>

                  <div class="bridge-strip">
                    <div class="panel">
                      <div class="panel-head">
                        <div>
                          <h2 style="margin:0;">Active Slices</h2>
                          <p class="muted">Only coding work in flight.</p>
                        </div>
                        {chip(f"{int(worker_breakdown.get('active_coding_workers') or 0)} active", tone='good' if int(worker_breakdown.get('active_coding_workers') or 0) else 'muted')}
                      </div>
                      <div class="mini-grid">{bridge_active_slice_html}</div>
                    </div>

                    <div class="panel">
                      <div class="panel-head">
                        <div>
                          <h2 style="margin:0;">Review Gate</h2>
                          <p class="muted">Compact PR, publish, and refill waits.</p>
                        </div>
                        {chip(f"{len(approval_items)} waiting", tone='warn' if approval_items else 'muted')}
                      </div>
                      <div class="mini-grid">{bridge_review_gate_html}</div>
                    </div>

                    <div class="panel">
                      <div class="panel-head">
                        <div>
                          <h2 style="margin:0;">Healer Activity</h2>
                          <p class="muted">Only routine closure loops and refill work.</p>
                        </div>
                        {chip(healer_status_label, tone=severity_tone(healer_status_label))}
                      </div>
                      <div class="mini-grid">{bridge_healer_html}</div>
                    </div>
                  </div>
                </div>

              </section>
            </div>
          </body>
        </html>
        """

    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{APP_TITLE}</title>
        <style>
          :root {{
            --bg: #f4f1ea;
            --panel: #fffdfa;
            --panel-strong: #f7f2e7;
            --line: #d3c8b6;
            --line-strong: #a6967d;
            --text: #1f1a14;
            --muted: #645848;
            --accent: #215e63;
            --danger: #8f2f1f;
            --warn: #946115;
            --good: #2d6a3f;
            --shadow: 0 12px 30px rgba(31, 26, 20, 0.08);
          }}
          * {{ box-sizing: border-box; }}
          body {{
            font-family: "IBM Plex Sans", "Trebuchet MS", sans-serif;
            margin: 0;
            color: var(--text);
            background:
              radial-gradient(circle at top left, rgba(33, 94, 99, 0.10), transparent 30%),
              radial-gradient(circle at top right, rgba(148, 97, 21, 0.08), transparent 32%),
              linear-gradient(180deg, #faf7f1 0%, var(--bg) 100%);
          }}
          a {{ color: var(--accent); }}
          code {{ background: #efe7d8; padding: 2px 5px; border-radius: 6px; }}
          pre {{
            white-space: pre-wrap;
            background: #f6f1e6;
            border: 1px solid var(--line);
            padding: 12px;
            border-radius: 10px;
            overflow-x: auto;
          }}
          h1, h2, h3 {{ font-family: "Space Grotesk", "Trebuchet MS", sans-serif; margin-top: 0; }}
          p {{ line-height: 1.45; }}
          .muted {{ color: var(--muted); }}
          .page {{
            width: min(1600px, calc(100vw - 32px));
            margin: 0 auto;
            padding: 24px 0 40px;
          }}
          .hero {{
            border: 1px solid var(--line);
            background: linear-gradient(135deg, rgba(33, 94, 99, 0.08), rgba(255, 253, 250, 0.92));
            box-shadow: var(--shadow);
            border-radius: 22px;
            padding: 24px;
            margin-bottom: 20px;
          }}
          .hero-top {{
            display: flex;
            justify-content: space-between;
            gap: 18px;
            align-items: flex-start;
            flex-wrap: wrap;
          }}
          .hero-links {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
          }}
          .hero-link {{
            text-decoration: none;
            border: 1px solid var(--line-strong);
            background: rgba(255,255,255,0.72);
            padding: 9px 12px;
            border-radius: 999px;
            font-weight: 600;
          }}
          .hero-kicker {{
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 12px;
            color: var(--muted);
            margin-bottom: 8px;
          }}
          .mission-strip {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 12px;
            margin-top: 18px;
          }}
          .mission-card {{
            background: rgba(255,255,255,0.82);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 14px;
          }}
          .mission-card-wide {{
            grid-column: span 2;
          }}
          .mission-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin-bottom: 8px;
          }}
          .mission-value {{
            font-size: 20px;
            font-weight: 700;
          }}
          .mission-reset-list {{
            display: grid;
            gap: 8px;
          }}
          .mission-reset-list div {{
            display: grid;
            gap: 2px;
          }}
          .mission-reset-list span {{ font-weight: 700; }}
          .mission-reset-list small {{ color: var(--muted); }}
          .cockpit-grid {{
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
            gap: 20px;
            align-items: start;
          }}
          .cockpit-main, .cockpit-side {{
            display: grid;
            gap: 20px;
          }}
          .panel {{
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 18px;
            box-shadow: var(--shadow);
          }}
          .panel-accent {{
            background: linear-gradient(180deg, rgba(33, 94, 99, 0.05), rgba(255, 253, 250, 0.98));
          }}
          .panel-head {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
            margin-bottom: 12px;
          }}
          .panel-head p {{ margin: 0; }}
          .attention-list, .worker-grid, .approval-list {{ display: grid; gap: 12px; }}
          .attention-item, .worker-card, .approval-item {{
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 14px;
            background: #fff;
          }}
          .focused-card {{
            outline: 3px solid rgba(33, 94, 99, 0.35);
            box-shadow: 0 0 0 6px rgba(33, 94, 99, 0.10);
          }}
          .attention-item.severity-danger {{ border-color: #c7a39a; background: #fff8f6; }}
          .attention-item.severity-warn {{ border-color: #d4c08c; background: #fffbee; }}
          .attention-head, .worker-top, .approval-head {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-start;
            flex-wrap: wrap;
          }}
          .attention-chips, .worker-meta {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
          }}
          .worker-slice {{
            margin: 10px 0;
            font-weight: 600;
          }}
          .worker-preview-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
            margin-top: 12px;
          }}
          .worker-preview-panel {{
            border: 1px solid var(--line);
            border-radius: 12px;
            background: #f7f2ea;
            padding: 10px;
          }}
          .worker-preview-label {{
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 6px;
          }}
          .worker-preview-panel pre {{
            margin: 0;
            white-space: pre-wrap;
            word-break: break-word;
            font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace;
            color: var(--text);
          }}
          .progress-stack {{
            display: grid;
            gap: 6px;
            margin-top: 10px;
          }}
          .progress-bar {{
            display: flex;
            height: 10px;
            border-radius: 999px;
            overflow: hidden;
            background: #ece5d9;
            border: 1px solid var(--line);
          }}
          .progress-segment {{ display: block; height: 100%; }}
          .progress-complete {{ background: #5a8f65; }}
          .progress-inflight {{ background: #4d7ea8; }}
          .progress-blocked {{ background: #b55a4c; }}
          .progress-unmaterialized {{ background: #bdb3a6; }}
          .chip {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 9px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid var(--line);
            background: #f2ece0;
          }}
          .tone-danger {{ color: var(--danger); border-color: #d7b2aa; background: #fff3f1; }}
          .tone-warn {{ color: var(--warn); border-color: #d8c79a; background: #fff9e7; }}
          .tone-good {{ color: var(--good); border-color: #aac8b0; background: #f2fbf4; }}
          .tone-muted {{ color: var(--muted); }}
          .actions {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 10px;
          }}
          .actions form {{ margin: 0; }}
          .action-btn, .actions button {{
            appearance: none;
            border: 1px solid var(--line-strong);
            background: #fff;
            color: var(--text);
            border-radius: 999px;
            padding: 8px 12px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
          }}
          .action-btn.primary {{
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
          }}
          .action-btn.secondary {{
            background: #f7f2e7;
          }}
          .empty-state {{
            padding: 20px;
            border: 1px dashed var(--line-strong);
            border-radius: 16px;
            color: var(--muted);
            text-align: center;
            background: rgba(255,255,255,0.55);
          }}
          table {{
            border-collapse: collapse;
            width: 100%;
            margin: 0;
          }}
          th, td {{
            border: 1px solid var(--line);
            padding: 10px;
            text-align: left;
            vertical-align: top;
          }}
          th {{
            background: #f7f2e7;
          }}
          .detail-tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 22px 0 14px;
          }}
          .tab-button {{
            border: 1px solid var(--line-strong);
            background: #f8f4ec;
            padding: 10px 14px;
            border-radius: 999px;
            font-weight: 700;
            cursor: pointer;
          }}
          .tab-button.active {{
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
          }}
          .detail-pane {{
            display: none;
          }}
          .detail-pane.active {{
            display: block;
          }}
          .detail-pane .panel {{
            margin-bottom: 20px;
          }}
          .settings-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 18px;
          }}
          input[type=text], textarea {{
            width: 100%;
            box-sizing: border-box;
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 10px 12px;
            background: #fffdfa;
            color: var(--text);
          }}
          textarea {{ min-height: 120px; }}
          label {{ display: block; margin: 12px 0 4px; font-weight: 700; }}
          .focus-template {{ display: none; }}
          dialog {{
            width: min(480px, calc(100vw - 24px));
            border: 1px solid var(--line-strong);
            border-radius: 18px;
            padding: 0;
            box-shadow: 0 30px 80px rgba(0,0,0,0.24);
            margin: 12px 12px 12px auto;
            max-height: calc(100vh - 24px);
            height: calc(100vh - 24px);
          }}
          dialog::backdrop {{ background: rgba(31, 26, 20, 0.45); }}
          .dialog-body {{
            padding: 22px;
            height: 100%;
            overflow: auto;
            position: relative;
          }}
          .dialog-close {{
            position: absolute;
            right: 14px;
            top: 14px;
          }}
          @media (max-width: 1080px) {{
            .cockpit-grid {{ grid-template-columns: 1fr; }}
            .mission-card-wide {{ grid-column: span 1; }}
          }}
          @media (max-width: 700px) {{
            .page {{ width: min(100vw - 20px, 100%); }}
            .hero, .panel {{ border-radius: 16px; }}
          }}
        </style>
      </head>
      <body>
        <div class="page">
          <section class="hero" id="cockpit">
                <div class="hero-top">
                  <div>
                    <div class="hero-kicker">Fleet Explorer</div>
                    <h1>{APP_TITLE}</h1>
                    <p><strong>Desired state:</strong> <code>{td(str(CONFIG_PATH))}</code> · <strong>Runtime state:</strong> <code>{td(str(DB_PATH))}</code></p>
                    <p class="muted">Raw queue/runtime truth, routing history, accounts, audit, and settings stay explicit here. The command deck lives at <code>/admin</code>.</p>
                    <p class="muted"><strong>Best next action:</strong> {td(cockpit_summary.get('recommended_action') or 'No urgent action right now')}</p>
                  </div>
                  <div class="hero-links">
                    <a class="hero-link" href="/admin">Command Deck</a>
                    <a class="hero-link" href="/">Fleet Dashboard</a>
                    <a class="hero-link" href="/studio">Studio</a>
                    <a class="hero-link" href="/api/admin/status">Status API</a>
                  </div>
                </div>
            <div class="mission-strip">
              {mission_strip_html}
            </div>
          </section>

          <section class="panel panel-accent" id="overview">
            <div class="panel-head">
              <div>
                <h2>Explorer Snapshot</h2>
                <p class="muted">Explorer is for raw queue/runtime truth, routing history, accounts, audit, and settings. It is not a second home dashboard.</p>
              </div>
              {chip(f"{len(projects)} projects · {len(groups)} groups", tone='muted')}
            </div>
            <div class="mission-strip">
              {explorer_snapshot_cards_html}
            </div>
          </section>

          <div class="detail-tabs">
            <a class="tab-button" href="#overview">Overview</a>
            <button class="tab-button active" type="button" data-tab="projects">Projects</button>
            <button class="tab-button" type="button" data-tab="groups">Groups</button>
            <button class="tab-button" type="button" data-tab="reviews">Reviews</button>
            <button class="tab-button" type="button" data-tab="audit">Audit</button>
            <button class="tab-button" type="button" data-tab="milestones">Milestones</button>
            <button class="tab-button" type="button" data-tab="accounts">Accounts</button>
            <button class="tab-button" type="button" data-tab="routing">Routing</button>
            <button class="tab-button" type="button" data-tab="history">History</button>
            <button class="tab-button" type="button" data-tab="studio">Studio</button>
            <button class="tab-button" type="button" data-tab="settings">Settings</button>
          </div>

          <section class="detail-pane active" id="projects" data-tab-pane="projects">
            <div class="panel">
              <div class="panel-head"><div><h2>Projects</h2><p class="muted">Raw queue/runtime inventory with truthful stop reasons and local levers.</p></div></div>
              <table>
                <thead>
                  <tr><th>Project</th><th>Queue Status</th><th>Why Stopped</th><th>Queue Source</th><th>Progress</th><th>Current Slice</th><th>Review</th><th>Milestone ETA</th><th>Uncovered Scope</th><th>Design</th><th>Accounts</th><th>Cooldown</th><th>Last Error</th><th>Actions</th></tr>
                </thead>
                <tbody>{''.join(project_rows) or '<tr><td colspan="13">No projects configured.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="groups" data-tab-pane="groups">
            <div class="panel">
              <div class="panel-head"><div><h2>Groups</h2><p class="muted">Group status, blockers, uncovered scope, and signoff truth.</p></div></div>
              <table>
                <thead>
                  <tr><th>ID</th><th>Status / Phase</th><th>Dispatch</th><th>Projects</th><th>Contract Sets / Blockers</th><th>Dispatch Blockers</th><th>Uncovered Scope</th><th>Milestone ETA</th><th>Program ETA</th><th>Design</th><th>Actions</th></tr>
                </thead>
                <tbody>{''.join(group_rows) or '<tr><td colspan="10">No project groups configured.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="reviews" data-tab-pane="reviews">
            <div class="panel">
              <div class="panel-head"><div><h2>Review Lane</h2><p class="muted">GitHub Codex review status, gating, and review findings.</p></div></div>
              <table>
                <thead>
                  <tr><th>Project</th><th>Mode</th><th>Trigger</th><th>Repository</th><th>PR</th><th>Review Status</th><th>Blocking / Total Findings</th><th>Requested</th><th>ETA</th><th>Completed</th><th>Actions</th></tr>
                </thead>
                <tbody>{''.join(review_rows) or '<tr><td colspan="11">No review-enabled projects configured.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>GitHub Review Findings</h2>
              <table>
                <thead><tr><th>Project</th><th>PR</th><th>Severity</th><th>Path</th><th>Comment</th><th>Updated</th></tr></thead>
                <tbody>{''.join(github_review_rows) or '<tr><td colspan="6">No ingested GitHub review findings.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="audit" data-tab-pane="audit">
            <div class="panel">
              <div class="panel-head"><div><h2>Audit Findings</h2><p class="muted">Open findings across fleet, groups, and projects.</p></div></div>
              <table>
                <thead><tr><th>Scope Type</th><th>Scope ID</th><th>Severity</th><th>Finding</th><th>Summary</th><th>Candidate Tasks</th><th>Last Seen</th></tr></thead>
                <tbody>{''.join(finding_rows) or '<tr><td colspan="7">No open audit findings.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Audit Task Candidates</h2>
              <table>
                <thead><tr><th>ID</th><th>Status</th><th>Scope Type</th><th>Scope ID</th><th>Finding Key</th><th>Title</th><th>Detail</th><th>Last Seen</th><th>Actions</th></tr></thead>
                <tbody>{''.join(candidate_rows) or '<tr><td colspan="9">No open or approved audit task candidates.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="milestones" data-tab-pane="milestones">
            <div class="panel">
              <h2>Group Milestone Board</h2>
              <table>
                <thead><tr><th>Group</th><th>Phase</th><th>Status</th><th>Remaining Milestones</th><th>Milestones</th><th>Uncovered Scope</th><th>Scope Preview</th></tr></thead>
                <tbody>{''.join(group_milestone_rows) or '<tr><td colspan="7">No groups configured.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Project Milestone Board</h2>
              <table>
                <thead><tr><th>Project</th><th>Queue Status</th><th>Remaining Milestones</th><th>Milestones</th><th>Uncovered Scope</th><th>Scope Preview</th></tr></thead>
                <tbody>{''.join(project_milestone_rows) or '<tr><td colspan="6">No projects configured.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="accounts" data-tab-pane="accounts">
            <div class="panel">
              <h2>Accounts</h2>
              <table>
                <thead><tr><th>Alias</th><th>Auth</th><th>Configured State</th><th>Spark</th><th>Allowed Models</th><th>Day Budget</th><th>Month Budget</th><th>Parallel</th><th>Project Allowlist</th><th>Auth Status</th><th>Actions</th></tr></thead>
                <tbody>{''.join(account_rows) or '<tr><td colspan="11">No accounts configured.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Account Pools</h2>
              <table>
                <thead><tr><th>Alias</th><th>Pool State</th><th>Active</th><th>Day Cost</th><th>Month Cost</th><th>Backoff</th><th>Last Used</th><th>CODEX_HOME</th><th>Last Error</th></tr></thead>
                <tbody>{''.join(pool_rows) or '<tr><td colspan="9">No live account pools yet.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="routing" data-tab-pane="routing">
            <div class="panel">
              <h2>Routing Classes</h2>
              <table>
                <thead><tr><th>Route Class</th><th>Models</th><th>Reasoning</th><th>Estimated Output Tokens</th></tr></thead>
                <tbody>{''.join(tier_rows) or '<tr><td colspan="4">No tier preferences configured.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Price Table</h2>
              <table>
                <thead><tr><th>Model</th><th>Input</th><th>Cached Input</th><th>Output</th></tr></thead>
                <tbody>{''.join(price_rows) or '<tr><td colspan="4">No pricing configured.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Routing Decisions</h2>
              <table>
                <thead><tr><th>ID</th><th>Project</th><th>Slice</th><th>Route Class</th><th>Model</th><th>Account</th><th>Reason</th><th>Created</th></tr></thead>
                <tbody>{''.join(decision_rows) or '<tr><td colspan="8">No routing decisions yet.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="history" data-tab-pane="history">
            <div class="panel">
              <h2>Group Publish Events</h2>
              <table>
                <thead><tr><th>ID</th><th>Group</th><th>Source</th><th>Scope</th><th>Published Targets</th><th>Created</th></tr></thead>
                <tbody>{''.join(group_publish_rows) or '<tr><td colspan="6">No group publish events yet.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Group Runs</h2>
              <table>
                <thead><tr><th>ID</th><th>Group</th><th>Kind</th><th>Phase</th><th>Status</th><th>Members</th><th>Details</th><th>Started</th></tr></thead>
                <tbody>{''.join(group_run_history_rows) or '<tr><td colspan="8">No group runs yet.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Recent Runs</h2>
              <table>
                <thead><tr><th>ID</th><th>Project</th><th>Status</th><th>Slice</th><th>Model</th><th>Started</th><th>Finished</th><th>Log</th><th>Final</th></tr></thead>
                <tbody>{''.join(run_rows) or '<tr><td colspan="9">No runs yet.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="studio" data-tab-pane="studio">
            <div class="panel">
              <div class="panel-head"><div><h2>Studio Integration</h2><p class="muted">Pending proposal previews and publish controls without leaving `/admin`.</p></div></div>
              <table>
                <thead><tr><th>ID</th><th>Status</th><th>Role</th><th>Scope</th><th>Proposal</th><th>Targets</th><th>Actions</th></tr></thead>
                <tbody>{''.join(studio_proposal_rows) or '<tr><td colspan="7">No unpublished Studio proposals.</td></tr>'}</tbody>
              </table>
            </div>
            <div class="panel">
              <h2>Studio Publish Events</h2>
              <table>
                <thead><tr><th>ID</th><th>Source Target</th><th>Mode</th><th>Published Targets</th><th>Created</th></tr></thead>
                <tbody>{''.join(publish_event_rows) or '<tr><td colspan="5">No studio publish events yet.</td></tr>'}</tbody>
              </table>
            </div>
          </section>

          <section class="detail-pane" id="settings" data-tab-pane="settings">
            <div class="panel">
              <div class="panel-head"><div><h2>Settings</h2><p class="muted">Keep the raw control-plane forms, but move them behind the Explorer.</p></div></div>
              {settings_grid_html}
            </div>
          </section>

          <div class="focus-template-bank">
            {''.join(focus_blocks)}
          </div>
        </div>

        <dialog id="focus-dialog">
          <div class="dialog-body">
            <button class="action-btn dialog-close" type="button" onclick="closeFocus()">Close</button>
            <div id="focus-body"></div>
          </div>
        </dialog>

        <script>
          function setActiveTab(tab, updateHash) {{
            document.querySelectorAll('[data-tab-pane]').forEach(function(el) {{
              el.classList.toggle('active', el.getAttribute('data-tab-pane') === tab);
            }});
            document.querySelectorAll('.tab-button[data-tab]').forEach(function(el) {{
              el.classList.toggle('active', el.getAttribute('data-tab') === tab);
            }});
            if (tab && updateHash !== false) {{
              history.replaceState(null, '', '#' + tab);
            }}
          }}
          document.querySelectorAll('.tab-button[data-tab]').forEach(function(button) {{
            button.addEventListener('click', function() {{
              setActiveTab(button.getAttribute('data-tab'));
            }});
          }});
          function openFocus(id) {{
            var source = document.getElementById(id);
            var dialog = document.getElementById('focus-dialog');
            var body = document.getElementById('focus-body');
            if (!source || !dialog || !body) {{
              return;
            }}
            body.innerHTML = source.innerHTML;
            if (typeof dialog.showModal === 'function') {{
              dialog.showModal();
            }} else {{
              dialog.setAttribute('open', 'open');
            }}
          }}
          function closeFocus() {{
            var dialog = document.getElementById('focus-dialog');
            if (!dialog) {{
              return;
            }}
            if (typeof dialog.close === 'function') {{
              dialog.close();
            }} else {{
              dialog.removeAttribute('open');
            }}
          }}
          function focusCard(id) {{
            if (!id) {{
              return;
            }}
            var target = document.getElementById(id);
            if (!target) {{
              return;
            }}
            target.classList.add('focused-card');
            target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            window.setTimeout(function() {{
              target.classList.remove('focused-card');
            }}, 2200);
          }}
          (function() {{
            var hash = (window.location.hash || '').replace('#', '');
            if (hash && document.querySelector('[data-tab-pane=\"' + hash + '\"]')) {{
              setActiveTab(hash);
              return;
            }}
            setActiveTab('projects', false);
            focusCard(hash);
          }})();
          window.addEventListener('hashchange', function() {{
            var hash = (window.location.hash || '').replace('#', '');
            if (hash && document.querySelector('[data-tab-pane=\"' + hash + '\"]')) {{
              setActiveTab(hash);
              return;
            }}
            focusCard(hash);
          }});
        </script>
      </body>
    </html>
    """


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
def admin_dashboard() -> str:
    return render_admin_dashboard(show_details=False)


@app.get("/admin/details", response_class=HTMLResponse)
def admin_details() -> str:
    return render_admin_dashboard(show_details=True)


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
    review_findings = [item for item in (status.get("review_findings") or []) if str(item.get("project_id") or "") in member_ids]
    publish_events = [item for item in (status.get("group_publish_events") or []) if item.get("group_id") == group_id]
    run_rows = [item for item in (status.get("group_runs") or []) if item.get("group_id") == group_id]
    current_milestone = next(iter(group.get("remaining_milestones") or []), {})

    def local_progress_bar(progress: Dict[str, Any], *, delivery: bool = False) -> str:
        gray_key = "percent_unstarted" if delivery else "percent_unmaterialized"
        complete = max(0, int(progress.get("percent_complete") or 0))
        inflight = max(0, int(progress.get("percent_inflight") or 0))
        blocked = max(0, int(progress.get("percent_blocked") or 0))
        gray = max(0, int(progress.get(gray_key) or 0))
        return (
            '<div class="progress-bar">'
            f'<span class="progress-segment progress-complete" style="width:{complete}%"></span>'
            f'<span class="progress-segment progress-inflight" style="width:{inflight}%"></span>'
            f'<span class="progress-segment progress-blocked" style="width:{blocked}%"></span>'
            f'<span class="progress-segment progress-unmaterialized" style="width:{gray}%"></span>'
            "</div>"
        )

    def local_progress_summary(progress: Dict[str, Any], *, delivery: bool = False) -> str:
        gray_key = "percent_unstarted" if delivery else "percent_unmaterialized"
        gray_label = "unstarted" if delivery else "unmaterialized"
        return (
            f"{html.escape(str(progress.get('percent_complete') or 0))}% done · "
            f"{html.escape(str(progress.get('percent_inflight') or 0))}% inflight · "
            f"{html.escape(str(progress.get('percent_blocked') or 0))}% blocked · "
            f"{html.escape(str(progress.get(gray_key) or 0))}% {gray_label}"
        )

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
          <td>{html.escape(str((project.get('pull_request') or {}).get('review_status') or 'not_requested'))}</td>
          <td>{int(project.get('approved_audit_task_count') or 0)} / {int(project.get('open_audit_task_count') or 0)}</td>
          <td><div>{html.escape(str((project.get('design_progress') or {}).get('percent_complete') or 0))}%</div><div class="muted">{html.escape(str((project.get('design_progress') or {}).get('summary') or ''))}</div><div class="progress-stack">{local_progress_bar(project.get('design_progress') or {})}</div></td>
          <td><div>{html.escape(str((project.get('design_eta') or {}).get('eta_human') or 'unknown'))}</div><div class="muted">confidence: {html.escape(str((project.get('design_eta') or {}).get('confidence') or ((project.get('design_progress') or {}).get('eta_confidence') or 'low')))}</div><div class="muted">coverage: {html.escape(str((project.get('design_eta') or {}).get('coverage_status') or ''))}</div><div class="muted">reason: {html.escape(str((project.get('design_eta') or {}).get('confidence_reason') or ''))}</div><div class="muted">blocker: {html.escape(str((project.get('design_progress') or {}).get('main_blocker') or 'none'))}</div><div class="muted">{html.escape(str((project.get('design_eta') or {}).get('eta_basis') or ''))}</div></td>
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
    review_rows = "".join(
        f"""
        <tr>
          <td>{html.escape(str(item.get('project_id') or ''))}</td>
          <td>{html.escape(str(item.get('pr_number') or ''))}</td>
          <td>{html.escape(str(item.get('severity') or ''))}</td>
          <td>{html.escape(str(item.get('path') or ''))}:{html.escape(str(item.get('line') or ''))}</td>
          <td>{html.escape(str(item.get('body') or ''))}</td>
          <td>{html.escape(str(item.get('updated_at') or ''))}</td>
        </tr>
        """
        for item in review_findings[:40]
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
            <p class="muted">dispatch-eligible projects: {html.escape(str(group.get('ready_project_count') or 0))} / incidents: {html.escape(str(group.get('open_incident_count') or 0))} / auditor solve: {html.escape('yes' if group.get('auditor_can_solve') else 'no')}</p>
            <p><strong>Operator question:</strong> {html.escape(str(group.get('operator_question') or ''))}</p>
            <p><strong>Notification:</strong> {html.escape('yes' if group.get('notification_needed') else 'no')}</p>
            <p class="muted">{html.escape(str((group.get('notification') or {}).get('reason') or ''))}</p>
          </div>
          <div class="panel">
            <h2>Milestone</h2>
            <p><strong>{current_milestone_label}</strong></p>
            <p class="muted">remaining milestones: {len(group.get('remaining_milestones') or [])}</p>
            <p class="muted">program ETA: {html.escape(str((group.get('program_eta') or {}).get('eta_human') or 'unknown'))}</p>
            <p class="muted">design completeness: {html.escape(str((group.get('design_progress') or {}).get('percent_complete') or 0))}% · confidence {html.escape(str((group.get('program_eta') or {}).get('confidence') or ((group.get('design_progress') or {}).get('eta_confidence') or 'low')))}</p>
            <div class="progress-stack">{local_progress_bar(group.get('delivery_progress') or {}, delivery=True)}{local_progress_bar(group.get('design_progress') or {})}</div>
            <p class="muted">delivery: {local_progress_summary(group.get('delivery_progress') or {}, delivery=True)}</p>
            <p class="muted">design: {local_progress_summary(group.get('design_progress') or {})}</p>
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
            <tr><th>Project</th><th>Status</th><th>Current Slice</th><th>Review</th><th>Approved / Open Tasks</th><th>Design Status</th><th>Design ETA / Risk</th><th>Stop Reason</th><th>Next Action</th></tr>
          </thead>
          <tbody>
            {member_rows or '<tr><td colspan="9">No member projects.</td></tr>'}
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
        <h2>GitHub Review Findings</h2>
        <table>
          <thead>
            <tr><th>Project</th><th>PR</th><th>Severity</th><th>Path</th><th>Comment</th><th>Updated</th></tr>
          </thead>
          <tbody>
            {review_rows or '<tr><td colspan="6">No GitHub review findings for this group.</td></tr>'}
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
