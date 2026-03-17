import ast
import asyncio
import contextlib
import datetime as dt
import hashlib
import heapq
import hmac
import html
import json
import os
import pathlib
import re
import shlex
import sqlite3
import subprocess
import sys
import textwrap
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

CONTROLLER_DIR = pathlib.Path(__file__).resolve().parent
_MOUNTED_ADMIN_HELPERS_DIR = pathlib.Path(os.environ.get("FLEET_MOUNT_ROOT", "/docker/fleet")) / "admin"
ADMIN_HELPERS_DIR = (
    _MOUNTED_ADMIN_HELPERS_DIR
    if (_MOUNTED_ADMIN_HELPERS_DIR / "consistency.py").exists()
    else (CONTROLLER_DIR.parent / "admin")
)
if str(ADMIN_HELPERS_DIR) not in sys.path:
    sys.path.insert(0, str(ADMIN_HELPERS_DIR))

from consistency import (
    DEFAULT_LANES,
    infer_account_lane,
    normalize_lanes_config,
    normalize_task_queue_item,
    raise_for_config_consistency,
)

UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8090"))
APP_TITLE = "Codex Fleet Spider"
STUDIO_DIRNAME = ".codex-studio"
STUDIO_PUBLISHED_DIRNAME = f"{STUDIO_DIRNAME}/published"
STUDIO_PUBLISHED_FILES = [
    "VISION.md",
    "ROADMAP.md",
    "ARCHITECTURE.md",
    "runtime-instructions.generated.md",
]
DESIGN_MIRROR_PRODUCT_FILES = [
    ".codex-design/product/README.md",
    ".codex-design/product/VISION.md",
    ".codex-design/product/ARCHITECTURE.md",
    ".codex-design/product/PROGRAM_MILESTONES.yaml",
    ".codex-design/product/CONTRACT_SETS.yaml",
    ".codex-design/product/GROUP_BLOCKERS.md",
    ".codex-design/product/OWNERSHIP_MATRIX.md",
]
DESIGN_MIRROR_REPO_FILES = [
    ".codex-design/repo/IMPLEMENTATION_SCOPE.md",
    ".codex-design/review/REVIEW_CONTEXT.md",
]
DESIGN_MIRROR_NOTE_START = "<!-- fleet-design-mirror:start -->"
DESIGN_MIRROR_NOTE_END = "<!-- fleet-design-mirror:end -->"

DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", "/var/lib/codex-fleet/fleet.db"))
LOG_DIR = pathlib.Path(os.environ.get("FLEET_LOG_DIR", "/var/lib/codex-fleet/logs"))
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
ACCOUNTS_PATH = pathlib.Path(os.environ.get("FLEET_ACCOUNTS_PATH", "/app/config/accounts.yaml"))
POLICIES_PATH = CONFIG_PATH.with_name("policies.yaml")
ROUTING_PATH = CONFIG_PATH.with_name("routing.yaml")
GROUPS_PATH = CONFIG_PATH.with_name("groups.yaml")
PROJECTS_DIR = CONFIG_PATH.parent / "projects"
PROJECT_INDEX_PATH = PROJECTS_DIR / "_index.yaml"
CODEX_HOME_ROOT = pathlib.Path(os.environ.get("FLEET_CODEX_HOME_ROOT", "/var/lib/codex-fleet/codex-homes"))
GROUP_ROOT = pathlib.Path(os.environ.get("FLEET_GROUP_ROOT", str(DB_PATH.parent / "groups")))
GH_HOSTS_PATH = pathlib.Path(os.environ.get("FLEET_GH_HOSTS_PATH", "/run/gh/hosts.yml"))
GITHUB_API_BASE = os.environ.get("FLEET_GITHUB_API_BASE", "https://api.github.com").rstrip("/")
GITHUB_WEBHOOK_SECRET = os.environ.get("FLEET_GITHUB_WEBHOOK_SECRET", "")
AUDITOR_URL = os.environ.get("FLEET_AUDITOR_URL", "http://fleet-auditor:8093")
ADMIN_URL = os.environ.get("FLEET_ADMIN_URL", "http://fleet-admin:8092")
AUDIT_REQUEST_PENDING_SECONDS = int(os.environ.get("FLEET_AUDIT_REQUEST_PENDING_SECONDS", "300"))
AUDIT_REQUEST_DEBOUNCE_SECONDS = int(os.environ.get("FLEET_AUDIT_REQUEST_DEBOUNCE_SECONDS", "60"))

DEFAULT_PRICE_TABLE = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5.3-codex": {"input": 1.75, "cached_input": 0.175, "output": 14.00},
    "gpt-5.3-codex-spark": {"input": 0.0, "cached_input": 0.0, "output": 0.0},
}

CHATGPT_STANDARD_MODEL = "gpt-5.3-codex"
SPARK_MODEL = "gpt-5.3-codex-spark"
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
CHATGPT_SUPPORTED_MODELS = {
    CHATGPT_STANDARD_MODEL,
    SPARK_MODEL,
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-5.4",
}
GITHUB_REVIEW_MODEL = "github-codex-review"
READY_STATUS = "dispatch_pending"
HEALING_STATUS = "healing"
WAITING_CAPACITY_STATUS = "waiting_capacity"
QUEUE_REFILLING_STATUS = "queue_refilling"
DECISION_REQUIRED_STATUS = "decision_required"
REVIEW_FIX_STATUS = "review_fix"
REVIEW_HOLD_STATUSES = {
    "awaiting_pr",
    "review_requested",
    "awaiting_first_review",
    "review_light_pending",
    "jury_review_pending",
}
REVIEW_WAITING_STATUSES = {"queued", "requested"} | REVIEW_HOLD_STATUSES
REVIEW_VISIBLE_STATUSES = REVIEW_HOLD_STATUSES | {
    "review_failed",
    "review_fix_required",
    "jury_rework_required",
    "core_rescue_pending",
    "manual_hold",
}
REVIEW_FALLBACK_CLEAN_STATUS = "fallback_clean"
LOCAL_REVIEW_PENDING_STATUS = "local_review"
WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP = "groundwork_review_loop"
GROUNDWORK_PENDING_STATUS = "groundwork_pending"
AWAITING_FIRST_REVIEW_STATUS = "awaiting_first_review"
REVIEW_LIGHT_PENDING_STATUS = "review_light_pending"
JURY_REVIEW_PENDING_STATUS = "jury_review_pending"
JURY_REWORK_REQUIRED_STATUS = "jury_rework_required"
CORE_RESCUE_PENDING_STATUS = "core_rescue_pending"
MANUAL_HOLD_STATUS = "manual_hold"
ACCEPTED_AFTER_CORE_STATUS = "accepted_after_core"
ACCEPTED_AFTER_ROUND_STATUSES = {
    "1": "accepted_after_r1",
    "2": "accepted_after_r2",
    "3": "accepted_after_r3",
}
REVIEW_FAILED_INCIDENT_KIND = "review_failed"
REVIEW_STALLED_INCIDENT_KIND = "review_lane_stalled"
PR_CHECKS_FAILED_INCIDENT_KIND = "pr_checks_failed"
BLOCKED_UNRESOLVED_INCIDENT_KIND = "blocked_unresolved"
DESIRED_STATE_SCHEMA_VERSION = "2026-03-16.v1"
VALID_LIFECYCLE_STATES = {"planned", "scaffold", "dispatchable", "live", "signoff_only"}
DISPATCH_PARTICIPATION_LIFECYCLES = {"dispatchable", "live"}
DEFAULT_COMPILE_FRESHNESS_HOURS = {
    "planned": 720,
    "scaffold": 336,
    "dispatchable": 168,
    "live": 168,
    "signoff_only": 720,
}
REVIEW_FAILURE_INCIDENT_THRESHOLD = 3
DEFAULT_CAPTAIN_POLICY = {
    "priority": 100,
    "service_floor": 1,
    "shed_order": 100,
    "preemption_policy": "slice_boundary",
    "admission_policy": "normal",
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
    "core": "core",
    "jury": "audit",
    "survival": "survival",
}
EA_ONEMIN_TIGHT_PERCENT = 20.0
REVIEW_METADATA_SEPARATOR = " ; "
_EA_PROFILE_CACHE: Dict[str, Any] = {"fetched_at": 0.0, "payload": {}}

DEFAULT_SPIDER = {
    "escalate_to_complex_after_failures": 2,
    "classification_mode": "evidence_v1",
    "feedback_file_window": 2,
    "tier_preferences": {
        "inspect": {
            "lane_preferences": ["easy"],
            "models": ["gpt-5-nano", "gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "none",
            "estimated_output_tokens": 384,
        },
        "draft": {
            "lane_preferences": ["easy", "groundwork", "repair"],
            "models": ["gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "low",
            "estimated_output_tokens": 768,
        },
        "groundwork": {
            "lane_preferences": ["groundwork", "easy", "repair", "core"],
            "models": ["gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "medium",
            "estimated_output_tokens": 1536,
        },
        "micro_edit": {
            "lane_preferences": ["easy", "repair", "core"],
            "models": [SPARK_MODEL, "gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "none",
            "estimated_output_tokens": 768,
        },
        "bounded_fix": {
            "lane_preferences": ["repair", "easy", "core"],
            "models": [SPARK_MODEL, "gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "low",
            "estimated_output_tokens": 1536,
        },
        "multi_file_impl": {
            "lane_preferences": ["repair", "core"],
            "models": ["gpt-5.4", "gpt-5.3-codex"],
            "reasoning_effort": "low",
            "estimated_output_tokens": 2048,
        },
        "cross_repo_contract": {
            "lane_preferences": ["core"],
            "models": ["gpt-5.4", "gpt-5.3-codex"],
            "reasoning_effort": "medium",
            "estimated_output_tokens": 4096,
        },
    },
    "inspect_keywords": [
        "inspect repository state",
        "inspect repo",
        "triage",
        "summarize",
        "inventory",
        "list",
        "audit",
        "status",
        "catalog",
        "docs",
        "readme",
        "explain what is here",
    ],
    "draft_keywords": [
        "draft",
        "decompose",
        "split feedback",
        "proposal",
        "queue overlay",
        "queue.generated",
        "plan",
        "milestone registry",
        "write note",
    ],
    "groundwork_keywords": [
        "architecture",
        "tradeoff",
        "trade-off",
        "deep dive",
        "research",
        "backlog shaping",
        "design review",
        "design",
        "strategy",
        "second pass",
        "groundwork",
        "approach",
        "direction",
        "reconcile",
    ],
    "micro_edit_keywords": [
        "rename",
        "copy tweak",
        "docs cleanup",
        "import cleanup",
        "typo",
        "single-file",
        "single file",
        "minor",
        "small ui tweak",
        "label",
    ],
    "bounded_fix_keywords": [
        "fix",
        "patch",
        "repair",
        "normalize",
        "align",
        "wire",
        "retry",
        "verify",
        "smoke",
        "guardrail",
    ],
    "multi_file_impl_keywords": [
        "implement",
        "add service",
        "add route",
        "add worker",
        "add role",
        "build",
        "refactor",
        "scheduler",
        "service",
        "dashboard",
        "admin",
        "studio",
        "workflow",
        "worker",
        "audit board",
        "delivery",
        "session shell",
        "gm board",
        "spider feed",
        "asset review",
        "publication",
    ],
    "cross_repo_contract_keywords": [
        "contract",
        "compatibility",
        "dto",
        "schema",
        "session event",
        "session_events_vnext",
        "runtime_dtos_vnext",
        "producer/consumer",
        "lockstep",
        "relay envelope",
        "provenance",
        "contract reset",
    ],
    "token_alliance_window_hours": 24,
}

DEFAULT_SINGLETON_GROUP_ROLES = ["auditor", "healer", "project_manager"]

ACTIVE_QUEUE_STATUSES = {
    "queued",
    "queue",
    "pending",
    "todo",
    "blocked",
    "in progress",
    "in_progress",
    "active",
}

MILESTONE_TERMINAL_STATUSES = {"released"}
SOURCE_BACKLOG_OPEN_STATUS = "source_backlog_open"
CONFIGURED_QUEUE_COMPLETE_STATUS = "queue_exhausted"
SCAFFOLD_QUEUE_COMPLETE_STATUS = "scaffold_complete"
COMPLETED_SIGNED_OFF_STATUS = "completed_signed_off"

SYSTEM_PROMPT_TEMPLATE = """
System re-entry.

Read from disk before coding:
{instructions}

Then inspect the current repository state before changing anything.
Do not repeat already completed work.
Use scripts/ai/set-status.sh as you work when available.
Use scripts/ai/verify.sh before declaring completion when available.
{worker_posture_block}

Current slice:
{slice_name}

Spider routing notes:
- selected route class: {tier}
- selected model: {model}
- reasoning effort: {reasoning_effort}
- why: {reason}

{feedback_block}
""".strip()

CODEX_PROMPT_DIRECTIVES = ("/fast",)


def apply_codex_prompt_directives(prompt: str) -> str:
    body = str(prompt or "").lstrip()
    if not body:
        return "\n".join(CODEX_PROMPT_DIRECTIVES)
    for directive in CODEX_PROMPT_DIRECTIVES:
        if body.startswith(f"{directive}\n") or body == directive:
            return body
    return "\n".join(CODEX_PROMPT_DIRECTIVES) + "\n\n" + body


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


def wall_seconds(started_at: Optional[str], finished_at: Optional[str]) -> Optional[float]:
    started = parse_iso(started_at)
    finished = parse_iso(finished_at)
    if not started or not finished:
        return None
    seconds = (finished - started).total_seconds()
    if seconds <= 0:
        return None
    return seconds


def median_seconds(values: List[float]) -> Optional[float]:
    ordered = sorted(value for value in values if value > 0)
    if not ordered:
        return None
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def human_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return ""
    total = max(0, int(round(seconds)))
    if total == 0:
        return "0s"
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts and secs:
        parts.append(f"{secs}s")
    return " ".join(parts[:2])


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


def truncate_title(text: str, max_len: int = 72) -> str:
    clean = " ".join(str(text or "").strip().split())
    if len(clean) <= max_len:
        return clean or "fleet slice"
    return clean[: max_len - 1].rstrip() + "…"


def ensure_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CODEX_HOME_ROOT.mkdir(parents=True, exist_ok=True)
    GROUP_ROOT.mkdir(parents=True, exist_ok=True)


def db() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def table_exists(name: str) -> bool:
    if not DB_PATH.exists():
        return False
    with db() as conn:
        row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                alias TEXT PRIMARY KEY,
                auth_kind TEXT NOT NULL DEFAULT 'api_key',
                api_key_file TEXT,
                api_key_env TEXT,
                auth_json_file TEXT,
                allowed_models_json TEXT NOT NULL DEFAULT '[]',
                daily_budget_usd REAL,
                monthly_budget_usd REAL,
                max_parallel_runs INTEGER NOT NULL DEFAULT 1,
                health_state TEXT NOT NULL DEFAULT 'ready',
                backoff_until TEXT,
                spark_backoff_until TEXT,
                last_used_at TEXT,
                last_error TEXT,
                spark_last_error TEXT,
                capability_models_json TEXT NOT NULL DEFAULT '[]',
                capability_checked_at TEXT,
                capability_status TEXT,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                last_selected_model TEXT,
                last_model_success_at TEXT,
                last_model_failure_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                design_doc TEXT,
                verify_cmd TEXT,
                feedback_dir TEXT,
                state_file TEXT,
                queue_json TEXT NOT NULL,
                queue_index INTEGER NOT NULL DEFAULT 0,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'dispatch_pending',
                current_slice TEXT,
                active_run_id INTEGER,
                cooldown_until TEXT,
                last_run_at TEXT,
                last_error TEXT,
                spider_tier TEXT,
                spider_model TEXT,
                spider_reason TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                account_alias TEXT NOT NULL,
                job_kind TEXT NOT NULL DEFAULT 'coding',
                slice_name TEXT NOT NULL,
                status TEXT NOT NULL,
                model TEXT NOT NULL,
                reasoning_effort TEXT,
                spider_tier TEXT,
                decision_reason TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                exit_code INTEGER,
                verify_exit_code INTEGER,
                input_tokens INTEGER,
                cached_input_tokens INTEGER,
                output_tokens INTEGER,
                estimated_cost_usd REAL,
                log_path TEXT,
                final_message_path TEXT,
                prompt_path TEXT,
                error_class TEXT,
                error_message TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS feedback_history (
                project_id TEXT NOT NULL,
                rel_path TEXT NOT NULL,
                run_id INTEGER,
                applied_at TEXT NOT NULL,
                PRIMARY KEY(project_id, rel_path),
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(run_id) REFERENCES runs(id)
            );

            CREATE TABLE IF NOT EXISTS spider_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                slice_name TEXT NOT NULL,
                account_alias TEXT,
                selected_model TEXT,
                spider_tier TEXT NOT NULL,
                reason TEXT NOT NULL,
                estimated_prompt_chars INTEGER,
                decision_meta_json TEXT NOT NULL DEFAULT '{}',
                selection_trace_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS auditor_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                finding_count INTEGER NOT NULL DEFAULT 0,
                candidate_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                finding_key TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                source TEXT NOT NULL DEFAULT 'fleet-auditor',
                evidence_json TEXT NOT NULL DEFAULT '[]',
                candidate_tasks_json TEXT NOT NULL DEFAULT '[]',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                resolved_at TEXT,
                UNIQUE(scope_type, scope_id, finding_key)
            );

            CREATE TABLE IF NOT EXISTS audit_task_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                finding_key TEXT NOT NULL,
                task_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL,
                task_meta_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'open',
                source TEXT NOT NULL DEFAULT 'fleet-auditor',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                resolved_at TEXT,
                UNIQUE(scope_type, scope_id, finding_key, task_index)
            );

            CREATE TABLE IF NOT EXISTS group_runtime (
                group_id TEXT PRIMARY KEY,
                signoff_state TEXT NOT NULL DEFAULT 'open',
                signed_off_at TEXT,
                reopened_at TEXT,
                last_audit_requested_at TEXT,
                last_refill_requested_at TEXT,
                phase TEXT NOT NULL DEFAULT 'dispatch_pending',
                last_phase_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS group_publish_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                source TEXT NOT NULL,
                source_scope_type TEXT NOT NULL,
                source_scope_id TEXT NOT NULL,
                finding_key TEXT,
                candidate_id INTEGER,
                published_targets_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS group_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                run_kind TEXT NOT NULL,
                phase TEXT NOT NULL,
                status TEXT NOT NULL,
                member_projects_json TEXT NOT NULL DEFAULT '[]',
                details_json TEXT NOT NULL DEFAULT '{}',
                started_at TEXT NOT NULL,
                finished_at TEXT
            );

            CREATE TABLE IF NOT EXISTS pull_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL UNIQUE,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                base_branch TEXT NOT NULL,
                pr_number INTEGER,
                pr_url TEXT,
                pr_title TEXT,
                pr_body TEXT,
                pr_state TEXT NOT NULL DEFAULT 'draft',
                draft INTEGER NOT NULL DEFAULT 1,
                head_sha TEXT,
                review_mode TEXT NOT NULL DEFAULT 'github',
                review_trigger TEXT NOT NULL DEFAULT 'manual_comment',
                review_focus TEXT,
                review_status TEXT NOT NULL DEFAULT 'queued',
                review_requested_at TEXT,
                review_completed_at TEXT,
                review_findings_count INTEGER NOT NULL DEFAULT 0,
                review_blocking_findings_count INTEGER NOT NULL DEFAULT 0,
                last_review_comment_id TEXT,
                last_review_head_sha TEXT,
                last_synced_at TEXT,
                review_sync_failures INTEGER NOT NULL DEFAULT 0,
                review_retrigger_count INTEGER NOT NULL DEFAULT 0,
                review_wakeup_miss_count INTEGER NOT NULL DEFAULT 0,
                local_review_attempts INTEGER NOT NULL DEFAULT 0,
                local_review_last_at TEXT,
                workflow_kind TEXT NOT NULL DEFAULT 'default',
                review_round INTEGER NOT NULL DEFAULT 0,
                max_review_rounds INTEGER NOT NULL DEFAULT 0,
                first_review_complete_at TEXT,
                accepted_on_round TEXT,
                needs_core_rescue INTEGER NOT NULL DEFAULT 0,
                core_rescue_reason TEXT,
                jury_feedback_history_json TEXT NOT NULL DEFAULT '[]',
                issue_fingerprints_json TEXT NOT NULL DEFAULT '[]',
                blocking_issue_count_by_round_json TEXT NOT NULL DEFAULT '[]',
                repeat_issue_count_by_round_json TEXT NOT NULL DEFAULT '[]',
                groundwork_time_ms INTEGER NOT NULL DEFAULT 0,
                jury_time_ms INTEGER NOT NULL DEFAULT 0,
                core_time_ms INTEGER NOT NULL DEFAULT 0,
                allowance_burn_by_lane_json TEXT NOT NULL DEFAULT '{}',
                pass_without_core INTEGER NOT NULL DEFAULT 0,
                last_retrigger_at TEXT,
                next_retry_at TEXT,
                review_rate_limit_reset_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS review_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                external_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                author_login TEXT,
                review_state TEXT,
                path TEXT,
                line INTEGER,
                body TEXT NOT NULL,
                html_url TEXT,
                severity TEXT NOT NULL DEFAULT 'medium',
                blocking INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, pr_number, external_id),
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                incident_kind TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT
            );
            """
        )
        migrate_db(conn)


def migrate_db(conn: sqlite3.Connection) -> None:
    account_cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "api_key_env" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN api_key_env TEXT")
    if "health_state" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN health_state TEXT NOT NULL DEFAULT 'ready'")
    if "spark_backoff_until" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN spark_backoff_until TEXT")
    if "spark_last_error" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN spark_last_error TEXT")
    if "capability_models_json" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN capability_models_json TEXT NOT NULL DEFAULT '[]'")
    if "capability_checked_at" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN capability_checked_at TEXT")
    if "capability_status" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN capability_status TEXT")
    if "success_count" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN success_count INTEGER NOT NULL DEFAULT 0")
    if "failure_count" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN failure_count INTEGER NOT NULL DEFAULT 0")
    if "last_selected_model" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN last_selected_model TEXT")
    if "last_model_success_at" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN last_model_success_at TEXT")
    if "last_model_failure_at" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN last_model_failure_at TEXT")

    run_cols = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "job_kind" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN job_kind TEXT NOT NULL DEFAULT 'coding'")

    spider_cols = {row["name"] for row in conn.execute("PRAGMA table_info(spider_decisions)").fetchall()}
    if "decision_meta_json" not in spider_cols:
        conn.execute("ALTER TABLE spider_decisions ADD COLUMN decision_meta_json TEXT NOT NULL DEFAULT '{}'")
    if "selection_trace_json" not in spider_cols:
        conn.execute("ALTER TABLE spider_decisions ADD COLUMN selection_trace_json TEXT NOT NULL DEFAULT '[]'")

    group_runtime_cols = {row["name"] for row in conn.execute("PRAGMA table_info(group_runtime)").fetchall()}
    if "phase" not in group_runtime_cols:
        conn.execute("ALTER TABLE group_runtime ADD COLUMN phase TEXT NOT NULL DEFAULT 'dispatch_pending'")
    if "last_phase_at" not in group_runtime_cols:
        conn.execute("ALTER TABLE group_runtime ADD COLUMN last_phase_at TEXT")
    audit_task_cols = {row["name"] for row in conn.execute("PRAGMA table_info(audit_task_candidates)").fetchall()}
    if "task_meta_json" not in audit_task_cols:
        conn.execute("ALTER TABLE audit_task_candidates ADD COLUMN task_meta_json TEXT NOT NULL DEFAULT '{}'")
    pull_request_cols = {row["name"] for row in conn.execute("PRAGMA table_info(pull_requests)").fetchall()}
    if "last_review_head_sha" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN last_review_head_sha TEXT")
    if "last_synced_at" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN last_synced_at TEXT")
    if "review_sync_failures" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN review_sync_failures INTEGER NOT NULL DEFAULT 0")
    if "review_retrigger_count" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN review_retrigger_count INTEGER NOT NULL DEFAULT 0")
    if "review_wakeup_miss_count" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN review_wakeup_miss_count INTEGER NOT NULL DEFAULT 0")
    if "local_review_attempts" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN local_review_attempts INTEGER NOT NULL DEFAULT 0")
    if "local_review_last_at" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN local_review_last_at TEXT")
    if "workflow_kind" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN workflow_kind TEXT NOT NULL DEFAULT 'default'")
    if "review_round" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN review_round INTEGER NOT NULL DEFAULT 0")
    if "max_review_rounds" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN max_review_rounds INTEGER NOT NULL DEFAULT 0")
    if "first_review_complete_at" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN first_review_complete_at TEXT")
    if "accepted_on_round" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN accepted_on_round TEXT")
    if "needs_core_rescue" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN needs_core_rescue INTEGER NOT NULL DEFAULT 0")
    if "core_rescue_reason" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN core_rescue_reason TEXT")
    if "jury_feedback_history_json" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN jury_feedback_history_json TEXT NOT NULL DEFAULT '[]'")
    if "issue_fingerprints_json" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN issue_fingerprints_json TEXT NOT NULL DEFAULT '[]'")
    if "blocking_issue_count_by_round_json" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN blocking_issue_count_by_round_json TEXT NOT NULL DEFAULT '[]'")
    if "repeat_issue_count_by_round_json" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN repeat_issue_count_by_round_json TEXT NOT NULL DEFAULT '[]'")
    if "groundwork_time_ms" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN groundwork_time_ms INTEGER NOT NULL DEFAULT 0")
    if "jury_time_ms" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN jury_time_ms INTEGER NOT NULL DEFAULT 0")
    if "core_time_ms" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN core_time_ms INTEGER NOT NULL DEFAULT 0")
    if "allowance_burn_by_lane_json" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN allowance_burn_by_lane_json TEXT NOT NULL DEFAULT '{}'")
    if "pass_without_core" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN pass_without_core INTEGER NOT NULL DEFAULT 0")
    if "last_retrigger_at" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN last_retrigger_at TEXT")
    if "next_retry_at" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN next_retry_at TEXT")
    if "review_rate_limit_reset_at" not in pull_request_cols:
        conn.execute("ALTER TABLE pull_requests ADD COLUMN review_rate_limit_reset_at TEXT")
    incident_cols = {row["name"] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()}
    if incident_cols and "context_json" not in incident_cols:
        conn.execute("ALTER TABLE incidents ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}'")
    conn.execute("UPDATE projects SET status=? WHERE status='ready'", (READY_STATUS,))


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


def run_duration_ms(started_at: Optional[str], finished_at: Optional[str]) -> int:
    started = parse_iso(str(started_at or ""))
    finished = parse_iso(str(finished_at or ""))
    if not started or not finished:
        return 0
    return max(0, int((finished - started).total_seconds() * 1000))


def _round_metric_list(raw: Any) -> List[int]:
    values = json_field(raw if isinstance(raw, str) else json.dumps(raw), []) if not isinstance(raw, list) else raw
    result: List[int] = []
    for item in values:
        try:
            result.append(int(item))
        except Exception:
            result.append(0)
    return result


def _set_round_metric(raw: Any, round_number: int, value: int) -> str:
    values = _round_metric_list(raw)
    while len(values) < round_number:
        values.append(0)
    values[max(0, round_number - 1)] = int(value)
    return json.dumps(values, sort_keys=True)


def _merge_issue_fingerprints(raw: Any, issue_ids: Sequence[str]) -> str:
    current = [str(item).strip() for item in (json_field(raw if isinstance(raw, str) else json.dumps(raw), []) if not isinstance(raw, list) else raw) if str(item).strip()]
    for issue_id in issue_ids:
        clean = str(issue_id).strip()
        if clean and clean not in current:
            current.append(clean)
    return json.dumps(current, sort_keys=True)


def _merge_allowance_burn(raw: Any, lane_name: str, estimated_cost_usd: Optional[float]) -> str:
    payload = json_field(raw if isinstance(raw, str) else json.dumps(raw), {}) if not isinstance(raw, dict) else dict(raw)
    lane = str(lane_name or "").strip().lower()
    if not lane:
        return json.dumps(payload, sort_keys=True)
    row = dict(payload.get(lane) or {})
    row["runs"] = int(row.get("runs") or 0) + 1
    if estimated_cost_usd is not None:
        row["estimated_cost_usd"] = round(float(row.get("estimated_cost_usd") or 0.0) + float(estimated_cost_usd), 6)
    payload[lane] = row
    return json.dumps(payload, sort_keys=True)


def changed_paths_since_snapshot(repo_path: str, baseline_snapshot: Optional[Dict[str, str]]) -> List[str]:
    current_snapshot = git_dirty_snapshot(repo_path)
    if baseline_snapshot is None:
        return sorted(current_snapshot)
    return sorted(path for path, fingerprint in current_snapshot.items() if baseline_snapshot.get(path) != fingerprint)


def review_packet_payload(
    *,
    project_id: str,
    slice_name: str,
    decision: Dict[str, Any],
    changed_paths: Sequence[str],
    verify_rc: Optional[int],
    run_id: int,
) -> Dict[str, Any]:
    return {
        "slice_id": f"{project_id}:{review_slice_key(slice_name)}:{run_id}",
        "title": slice_name,
        "selected_lane": str(decision.get("lane") or ""),
        "required_reviewer_lane": str(decision.get("required_reviewer_lane") or ""),
        "final_reviewer_lane": str(((decision.get("task_meta") or {}).get("final_reviewer_lane") or "")),
        "acceptance_level": str(((decision.get("task_meta") or {}).get("acceptance_level") or "")),
        "review_round": int(((decision.get("task_meta") or {}).get("review_round") or 0)),
        "changed_files": list(changed_paths),
        "verify_exit_code": verify_rc,
    }


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
    if not EA_STATUS_BASE_URL:
        return {}
    request = urllib.request.Request(
        f"{EA_STATUS_BASE_URL}/v1/codex/profiles",
        headers={
            **({"Authorization": f"Bearer {EA_STATUS_API_TOKEN}"} if EA_STATUS_API_TOKEN else {}),
            "X-EA-Principal-ID": EA_STATUS_PRINCIPAL_ID,
            "User-Agent": "codex-fleet-controller",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        payload = {}
    _EA_PROFILE_CACHE["fetched_at"] = now
    _EA_PROFILE_CACHE["payload"] = payload if isinstance(payload, dict) else {}
    return _EA_PROFILE_CACHE["payload"]


def ea_lane_capacity_snapshot(lanes: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    payload = ea_codex_profiles()
    profiles = {
        str(item.get("profile") or "").strip(): dict(item)
        for item in payload.get("profiles") or []
        if str(item.get("profile") or "").strip()
    }
    providers = dict(((payload.get("provider_health") or {}).get("providers")) or {})
    snapshots: Dict[str, Dict[str, Any]] = {}
    for lane_name in normalize_lanes_config(lanes):
        profile_name = EA_PROFILE_NAME_BY_LANE.get(lane_name, lane_name)
        profile = profiles.get(profile_name, {})
        provider_hints = list(profile.get("provider_hint_order") or ((normalize_lanes_config(lanes).get(lane_name) or {}).get("provider_hint_order") or []))
        provider_rows: List[Dict[str, Any]] = []
        for provider_key in provider_hints:
            provider_payload = dict(providers.get(provider_key) or {})
            provider_rows.append(
                {
                    "provider_key": provider_key,
                    "state": provider_slot_state(provider_payload),
                    "remaining_percent_of_max": provider_payload.get("remaining_percent_of_max"),
                    "estimated_hours_remaining_at_current_pace": provider_payload.get("estimated_hours_remaining_at_current_pace"),
                    "detail": str(provider_payload.get("detail") or "").strip(),
                }
            )
        primary_state = provider_rows[0]["state"] if provider_rows else "unknown"
        fallback_ready = any(str(item.get("state") or "") == "ready" for item in provider_rows[1:])
        lane_state = "fallback_ready" if primary_state != "ready" and fallback_ready else primary_state
        snapshots[lane_name] = {
            "lane": lane_name,
            "profile": profile_name,
            "model": str(profile.get("model") or "").strip(),
            "provider_hint_order": provider_hints,
            "state": lane_state,
            "providers": provider_rows,
            "review_required": bool(profile.get("review_required")),
            "merge_policy": str(profile.get("merge_policy") or "").strip(),
        }
    return snapshots


def lane_snapshot_remaining_percent(snapshot: Dict[str, Any]) -> Optional[float]:
    providers = snapshot.get("providers") or []
    for provider in providers:
        value = provider.get("remaining_percent_of_max")
        try:
            if value is None:
                continue
            return float(value)
        except Exception:
            continue
    return None


def lane_capacity_available(snapshot: Dict[str, Any]) -> bool:
    state = str(snapshot.get("state") or "").strip().lower()
    return state in {"ready", "fallback_ready"}


def lane_capacity_tight(snapshot: Dict[str, Any]) -> bool:
    remaining = lane_snapshot_remaining_percent(snapshot)
    if remaining is None:
        return False
    return remaining <= EA_ONEMIN_TIGHT_PERCENT


def reviewer_runtime_model_for_lane(lanes: Dict[str, Any], reviewer_lane: str) -> str:
    lane_cfg = normalize_lanes_config(lanes).get(str(reviewer_lane or "").strip().lower()) or {}
    return str(lane_cfg.get("runtime_model") or "").strip()


def ordered_lane_preferences(tier_prefs: Dict[str, Any], allowed_lanes: List[str]) -> List[str]:
    configured = [str(item).strip().lower() for item in tier_prefs.get("lane_preferences") or [] if str(item).strip()]
    ordered = [lane for lane in configured if lane in allowed_lanes]
    ordered.extend(lane for lane in allowed_lanes if lane not in ordered)
    return ordered or list(allowed_lanes)


def lane_allowance_burn_snapshot(lane_name: str, lanes: Dict[str, Any], lane_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    lane_cfg = normalize_lanes_config(lanes).get(str(lane_name or "").strip().lower()) or {}
    provider = next(iter(lane_snapshot.get("providers") or []), {})
    return {
        "lane": str(lane_name or "").strip().lower(),
        "profile": EA_PROFILE_NAME_BY_LANE.get(str(lane_name or "").strip().lower(), str(lane_name or "").strip().lower()),
        "budget_bias": str(lane_cfg.get("budget_bias") or "standard").strip().lower(),
        "capacity_state": str(lane_snapshot.get("state") or "").strip().lower(),
        "provider": str(provider.get("provider_key") or "").strip(),
        "remaining_percent_of_max": provider.get("remaining_percent_of_max"),
        "estimated_hours_remaining_at_current_pace": provider.get("estimated_hours_remaining_at_current_pace"),
    }


def why_not_cheaper_lane(
    selected_lane: str,
    *,
    allowed_lanes: List[str],
    tier: str,
    escalation_reason: str,
    requires_contract_authority: bool,
    task_meta: Dict[str, Any],
    lane_snapshots: Dict[str, Any],
) -> str:
    lane = str(selected_lane or "").strip().lower()
    if lane == "easy":
        return "easy is already the cheapest eligible lane"
    if lane == "repair":
        if "easy" not in allowed_lanes:
            return "easy is not allowed by task policy"
        if not lane_capacity_available(lane_snapshots.get("easy") or {}):
            return "easy lane capacity is unavailable"
        return "repair is the cheapest implementation lane for bounded code changes"
    if lane == "groundwork":
        if bool(task_meta.get("groundwork_required")):
            return "groundwork is explicitly required by task policy"
        if tier == "groundwork":
            return "groundwork fits slow analysis better than cheaper coding lanes"
        if "easy" not in allowed_lanes and "repair" not in allowed_lanes:
            return "easy and repair are disallowed by task policy"
        if not any(lane_capacity_available(lane_snapshots.get(name) or {}) for name in ("easy", "repair") if name in allowed_lanes):
            return "easy and repair capacity are unavailable"
        return "groundwork is the cheapest eligible analysis lane"
    if lane == "core":
        if bool(task_meta.get("protected_runtime")):
            return "protected_runtime forces core authority"
        if requires_contract_authority:
            return "protected or merge-ready work requires core authority"
        if str(task_meta.get("risk_level") or "").strip().lower() in {"medium", "high"}:
            return "risk policy rejected cheaper lanes"
        if tier in {"multi_file_impl", "cross_repo_contract"}:
            return "scope is too broad for cheap implementation lanes"
        if "easy" not in allowed_lanes and "repair" not in allowed_lanes:
            return "easy and repair are not allowed by task policy"
        if not any(lane_capacity_available(lane_snapshots.get(name) or {}) for name in ("easy", "repair") if name in allowed_lanes):
            return "easy and repair capacity are unavailable"
        return "core is the only eligible lane with merge authority"
    if lane == "jury":
        return "jury is reserved for explicit audit or contradiction resolution"
    if lane == "survival":
        if escalation_reason == "capacity_exhausted_survival_fallback":
            return "primary lanes were unavailable, so survival is the emergency fallback"
        return "survival is only used when cheaper primary lanes cannot carry the slice"
    return "lane selected by current route policy"


def decision_requires_serial_review(project_cfg: Dict[str, Any], decision: Dict[str, Any]) -> bool:
    review = project_review_policy(project_cfg)
    lane = str(decision.get("lane") or "").strip().lower()
    reviewer_lane = str(decision.get("required_reviewer_lane") or "").strip().lower()
    task_meta = dict(decision.get("task_meta") or {})
    acceptance_level = str((task_meta.get("acceptance_level")) or "").strip().lower()
    signoff_requirements = [str(item).strip() for item in task_meta.get("signoff_requirements") or [] if str(item).strip()]
    forced_review = lane in {"easy", "repair", "groundwork", "survival"} or bool(signoff_requirements)
    if forced_review:
        return True
    if not (bool(review.get("enabled", True)) and bool(review.get("required_before_queue_advance", True))):
        return False
    return (
        reviewer_lane and reviewer_lane != lane
    ) or acceptance_level in {"reviewed", "merge_ready"}


def encode_review_focus(
    base_focus: str,
    *,
    reviewer_lane: str,
    reviewer_model: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    parts = [str(base_focus or "").strip()]
    if reviewer_lane:
        parts.append(f"reviewer_lane={reviewer_lane}")
    if reviewer_model:
        parts.append(f"reviewer_model={reviewer_model}")
    for key, value in (metadata or {}).items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if clean_key and clean_value:
            parts.append(f"{clean_key}={clean_value}")
    return REVIEW_METADATA_SEPARATOR.join(part for part in parts if part)


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


def review_slice_key(slice_name: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", str(slice_name or "").strip().lower()).strip("-") or "slice"


def metadata_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def task_final_reviewer_lane(task_meta: Dict[str, Any]) -> str:
    final_lane = str(task_meta.get("final_reviewer_lane") or "").strip().lower()
    if final_lane:
        return final_lane
    if metadata_flag(task_meta.get("jury_acceptance_required")):
        return "jury"
    return str(task_meta.get("required_reviewer_lane") or "core").strip().lower() or "core"


def review_focus_final_reviewer_lane(metadata: Dict[str, Any]) -> str:
    final_lane = str(metadata.get("final_reviewer_lane") or "").strip().lower()
    if final_lane:
        return final_lane
    if metadata_flag(metadata.get("jury_acceptance_required")):
        return "jury"
    return str(metadata.get("reviewer_lane") or metadata.get("required_reviewer_lane") or "core").strip().lower() or "core"


def review_round_for_dispatch(task_meta: Dict[str, Any], *, execution_lane: str) -> int:
    workflow_kind = str(task_meta.get("workflow_kind") or "default").strip().lower()
    current_round = int(task_meta.get("review_round") or 0)
    if workflow_kind != WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
        return max(1, current_round or 1)
    if str(execution_lane or "").strip().lower() == "core":
        return max(1, current_round or int(task_meta.get("core_rescue_after_round") or 1) or 1)
    return max(1, current_round + 1)


def reviewer_lane_for_dispatch(task_meta: Dict[str, Any], *, execution_lane: str) -> str:
    reviewer_lane = str(task_meta.get("required_reviewer_lane") or "core").strip().lower() or "core"
    if str(task_meta.get("workflow_kind") or "default").strip().lower() != WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
        return reviewer_lane
    if str(execution_lane or "").strip().lower() == "core":
        return task_final_reviewer_lane(task_meta)
    return reviewer_lane


def review_focus_metadata(task_meta: Dict[str, Any], *, slice_name: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {"slice_key": review_slice_key(slice_name)}
    for key in (
        "workflow_kind",
        "review_round",
        "max_review_rounds",
        "first_review_required",
        "jury_acceptance_required",
        "core_rescue_after_round",
        "final_reviewer_lane",
    ):
        value = task_meta.get(key)
        if value in (None, "", False):
            continue
        metadata[key] = str(value).strip().lower() if isinstance(value, bool) else str(value).strip()
    return metadata


def accepted_loop_review_status(review_round: int, *, core_used: bool) -> str:
    if core_used:
        return ACCEPTED_AFTER_CORE_STATUS
    round_key = str(max(1, min(int(review_round or 1), 3)))
    return ACCEPTED_AFTER_ROUND_STATUSES.get(round_key, ACCEPTED_AFTER_ROUND_STATUSES["3"])


def review_workflow_kind(pr_row: Optional[Dict[str, Any]] = None) -> str:
    pr = pr_row or {}
    workflow_kind = str(pr.get("workflow_kind") or "").strip().lower()
    if workflow_kind:
        return workflow_kind
    _, metadata = decode_review_focus(str(pr.get("review_focus") or ""))
    return str(metadata.get("workflow_kind") or "default").strip().lower() or "default"


def review_loop_stage(pr_row: Optional[Dict[str, Any]]) -> Optional[str]:
    pr = pr_row or {}
    if review_workflow_kind(pr) != WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP:
        return None
    review_status = str(pr.get("review_status") or "").strip().lower()
    if review_status in {
        AWAITING_FIRST_REVIEW_STATUS,
        REVIEW_LIGHT_PENDING_STATUS,
        JURY_REVIEW_PENDING_STATUS,
        JURY_REWORK_REQUIRED_STATUS,
        CORE_RESCUE_PENDING_STATUS,
        MANUAL_HOLD_STATUS,
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
    if review_status == LOCAL_REVIEW_PENDING_STATUS:
        if reviewer_lane and reviewer_lane == final_reviewer_lane and jury_acceptance_required:
            return JURY_REVIEW_PENDING_STATUS
        return AWAITING_FIRST_REVIEW_STATUS if not first_review_complete else REVIEW_LIGHT_PENDING_STATUS
    if review_status in {"review_fix_required", JURY_REWORK_REQUIRED_STATUS}:
        if bool(pr.get("needs_core_rescue")):
            return CORE_RESCUE_PENDING_STATUS
        return JURY_REWORK_REQUIRED_STATUS
    if review_status == REVIEW_FALLBACK_CLEAN_STATUS:
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


def choose_review_account_alias(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    *,
    reviewer_lane: str,
) -> Optional[str]:
    ordered_aliases = ordered_project_aliases(project_cfg)
    accounts_cfg = config.get("accounts") or {}
    now = utc_now()
    for alias in ordered_aliases:
        account_cfg = accounts_cfg.get(alias) or {}
        if infer_account_lane(account_cfg, alias=alias) != reviewer_lane:
            continue
        with db() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE alias=?", (alias,)).fetchone()
        if not row:
            continue
        if account_runtime_state(row, account_cfg, now) != "ready":
            continue
        return alias
    return None


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
        remaining = lane_snapshot_remaining_percent(lane_capacity) if isinstance(lane_capacity, dict) else None
        if remaining is not None:
            parts.append(f"remain={remaining:.1f}%")
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


def fleet_repo_root() -> pathlib.Path:
    return CONFIG_PATH.parent.parent


def group_target_root(group_id: str) -> pathlib.Path:
    return GROUP_ROOT / str(group_id).strip()


def group_feedback_root(group_id: str) -> pathlib.Path:
    return group_target_root(group_id) / "feedback"


def group_published_root(group_id: str) -> pathlib.Path:
    return group_target_root(group_id) / STUDIO_PUBLISHED_DIRNAME


def project_repo_slug(project_cfg: Dict[str, Any]) -> str:
    review = project_cfg.get("review") or {}
    repo_name = str(review.get("repo") or "").strip()
    if repo_name:
        return repo_name
    return pathlib.Path(str(project_cfg.get("path") or "")).name


def design_project_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    return next((project for project in config.get("projects") or [] if str(project.get("id") or "").strip() == "design"), {})


def write_bytes_if_changed(path: pathlib.Path, payload: bytes) -> bool:
    try:
        if path.exists() and path.read_bytes() == payload:
            return False
    except Exception:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return True


def ensure_design_mirror_agents_note(repo_root: pathlib.Path) -> None:
    path = repo_root / "AGENTS.md"
    managed_block = "\n\n" + "\n".join(
        [
            DESIGN_MIRROR_NOTE_START,
            "## Fleet Design Mirror",
            "- Load `.codex-design/product/README.md`, `.codex-design/repo/IMPLEMENTATION_SCOPE.md`, and `.codex-design/review/REVIEW_CONTEXT.md` when present.",
            "- Treat `.codex-design/` as the approved local mirror of the cross-repo Chummer design front door.",
            DESIGN_MIRROR_NOTE_END,
        ]
    )
    existing = path.read_text(encoding="utf-8") if path.exists() else "# AGENTS\n"
    pattern = rf"\n?{re.escape(DESIGN_MIRROR_NOTE_START)}.*?{re.escape(DESIGN_MIRROR_NOTE_END)}"
    without_block = re.sub(pattern, "", existing, flags=re.S)
    updated = without_block.rstrip("\n") + managed_block + "\n"
    if updated != existing:
        path.write_text(updated, encoding="utf-8")


def sync_design_repo_mirrors(
    config: Dict[str, Any],
    *,
    skip_dirty_repos: bool = False,
    skip_project_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    design_cfg = design_project_cfg(config)
    design_root = pathlib.Path(str(design_cfg.get("path") or "")).resolve()
    manifest_path = design_root / "products" / "chummer" / "sync" / "sync-manifest.yaml"
    if not design_root.exists() or not manifest_path.exists():
        return []
    manifest = load_yaml(manifest_path)
    mirrors = manifest.get("mirrors") or []
    if not isinstance(mirrors, list):
        return []
    repo_lookup = {
        project_repo_slug(project): project
        for project in config.get("projects") or []
        if str(project.get("path") or "").strip()
    }
    def mirror_product_target_rel(product_target: str, source_rel: str, duplicate_basenames: Set[str]) -> pathlib.Path:
        source_path = pathlib.Path(str(source_rel))
        if source_path.name in duplicate_basenames:
            parts = list(source_path.parts)
            if len(parts) >= 2 and parts[0] == "products" and parts[1] == "chummer":
                relative_source = pathlib.Path(*parts[2:])
            else:
                relative_source = source_path
        else:
            relative_source = pathlib.Path(source_path.name)
        return pathlib.Path(product_target) / relative_source

    results: List[Dict[str, Any]] = []
    for mirror in mirrors:
        if not isinstance(mirror, dict):
            continue
        project_cfg = repo_lookup.get(str(mirror.get("repo") or "").strip())
        if not project_cfg:
            continue
        project_id = str(project_cfg.get("id") or "").strip()
        if skip_project_ids and project_id in skip_project_ids:
            continue
        repo_root = pathlib.Path(str(project_cfg.get("path") or "")).resolve()
        if not repo_root.exists():
            continue
        if skip_dirty_repos and (repo_root / ".git").exists():
            try:
                if git_has_changes(str(repo_root)):
                    continue
            except Exception:
                continue
        copied: List[str] = []
        product_target = str(mirror.get("product_target") or mirror.get("target") or ".codex-design/product").strip()
        product_sources = [str(source_rel) for source_rel in mirror.get("product_sources") or mirror.get("sources") or []]
        duplicate_basenames = {
            name
            for name, count in Counter(pathlib.Path(source_rel).name for source_rel in product_sources).items()
            if count > 1
        }
        for source_rel in product_sources:
            source_path = (design_root / str(source_rel)).resolve()
            if not source_path.is_file():
                continue
            target_path = repo_root / mirror_product_target_rel(product_target, source_rel, duplicate_basenames)
            if write_bytes_if_changed(target_path, source_path.read_bytes()):
                copied.append(target_path.relative_to(repo_root).as_posix())
        repo_source = str(mirror.get("repo_source") or "").strip()
        if repo_source:
            source_path = (design_root / repo_source).resolve()
            if source_path.is_file():
                target_rel = str(mirror.get("repo_target") or ".codex-design/repo/IMPLEMENTATION_SCOPE.md").strip()
                target_path = repo_root / target_rel
                if write_bytes_if_changed(target_path, source_path.read_bytes()):
                    copied.append(target_path.relative_to(repo_root).as_posix())
        review_source = str(mirror.get("review_source") or "").strip()
        if review_source:
            source_path = (design_root / review_source).resolve()
            if source_path.is_file():
                target_rel = str(mirror.get("review_target") or ".codex-design/review/REVIEW_CONTEXT.md").strip()
                target_path = repo_root / target_rel
                if write_bytes_if_changed(target_path, source_path.read_bytes()):
                    copied.append(target_path.relative_to(repo_root).as_posix())
        ensure_design_mirror_agents_note(repo_root)
        results.append(
            {
                "project_id": project_id,
                "repo": str(mirror.get("repo") or ""),
                "copied_paths": copied,
            }
        )
    return results


def sync_design_repo_mirrors_if_safe(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    interval_seconds = max(60, get_int_policy(config, "design_mirror_sync_interval_seconds", 300))
    now = utc_now()
    if state.last_design_mirror_sync_at and state.last_design_mirror_sync_at >= now - dt.timedelta(seconds=interval_seconds):
        return []
    results = sync_design_repo_mirrors(config, skip_dirty_repos=True, skip_project_ids=set(state.tasks))
    state.last_design_mirror_sync_at = now
    return results


def project_design_mirror_instruction_items(project_cfg: Dict[str, Any]) -> List[str]:
    repo = pathlib.Path(project_cfg["path"])
    items: List[str] = []
    for rel in DESIGN_MIRROR_PRODUCT_FILES + DESIGN_MIRROR_REPO_FILES:
        if (repo / rel).exists():
            items.append(rel)
    return items


def feedback_filename(prefix: str) -> str:
    safe = "".join(ch for ch in prefix.lower() if ch.isalnum() or ch in {"-", "_"}).strip("-_") or "audit"
    return utc_now().strftime(f"%Y-%m-%d-%H%M%S-{safe}.md")


def queue_overlay_path(project_cfg: Dict[str, Any]) -> pathlib.Path:
    return studio_published_root(project_cfg) / "QUEUE.generated.yaml"


def merge_queue_overlay_item(project_cfg: Dict[str, Any], item_text: str, *, mode: str = "append") -> pathlib.Path:
    path = queue_overlay_path(project_cfg)
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


def queue_overlay_items(project_cfg: Dict[str, Any]) -> List[Any]:
    path = queue_overlay_path(project_cfg)
    if not path.exists() or not path.is_file():
        return []
    data = load_yaml(path)
    if isinstance(data, list):
        return [item for item in data if (isinstance(item, (str, int, float)) and str(item).strip()) or isinstance(item, (dict, list))]
    if isinstance(data, dict):
        raw_items = data.get("items")
        if raw_items is None:
            raw_items = data.get("queue")
        return [item for item in (raw_items or []) if (isinstance(item, (str, int, float)) and str(item).strip()) or isinstance(item, (dict, list))]
    return []


def audit_candidate_queue_text(candidate_row: sqlite3.Row) -> str:
    return str(candidate_row["detail"] or candidate_row["title"] or "").strip()


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
        return
    now_text = iso(utc_now())
    with db() as conn:
        conn.execute(
            "UPDATE audit_task_candidates SET status=?, last_seen_at=?, resolved_at=? WHERE id=?",
            (status, now_text, now_text if resolved else None, candidate_id),
        )


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


def audit_task_candidate_is_recommended(candidate: Any) -> bool:
    meta = audit_task_candidate_meta(candidate)
    if bool(meta.get("recommended_option")) or bool(meta.get("auto_choose_recommended")):
        return True
    if isinstance(candidate, sqlite3.Row):
        finding_key = candidate["finding_key"] if "finding_key" in candidate.keys() else ""
    elif isinstance(candidate, dict):
        finding_key = candidate.get("finding_key", "")
    else:
        finding_key = ""
    return audit_finding_is_recommended(finding_key)


def audit_task_candidate_category(candidate: Any) -> str:
    meta = audit_task_candidate_meta(candidate)
    explicit = str(meta.get("category") or meta.get("auto_heal_category") or "").strip().lower()
    if explicit in {"coverage", "review", "capacity", "contracts"}:
        return explicit

    if isinstance(candidate, sqlite3.Row):
        finding_key = str(candidate["finding_key"] if "finding_key" in candidate.keys() else "")
        title = str(candidate["title"] if "title" in candidate.keys() else "")
        detail = str(candidate["detail"] if "detail" in candidate.keys() else "")
    elif isinstance(candidate, dict):
        finding_key = str(candidate.get("finding_key") or "")
        title = str(candidate.get("title") or "")
        detail = str(candidate.get("detail") or "")
    else:
        finding_key = ""
        title = ""
        detail = ""

    haystack = " ".join([finding_key, title, detail]).lower()
    if any(marker in haystack for marker in ["review", "pull request", "pr checks", "github review"]):
        return "review"
    if any(marker in haystack for marker in ["capacity", "account", "budget", "runway", "pool", "cooldown", "rate limit"]):
        return "capacity"
    if any(marker in haystack for marker in ["contract", "dto", "schema", "canon", "session event", "envelope", "explain"]):
        return "contracts"
    return "coverage"


def publish_audit_candidate_via_admin(candidate_id: int) -> bool:
    request = urllib.request.Request(f"{ADMIN_URL}/api/admin/audit/tasks/{int(candidate_id)}/publish", method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return int(getattr(response, "status", 200) or 200) < 400
    except urllib.error.HTTPError as exc:
        return int(getattr(exc, "code", 500) or 500) in {200, 201, 202, 204, 303}
    except urllib.error.URLError:
        return False


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


def render_group_blockers_markdown(
    group_id: str,
    candidate: sqlite3.Row,
    finding: Optional[sqlite3.Row],
    config: Dict[str, Any],
) -> str:
    group = next((item for item in config.get("project_groups") or [] if str(item.get("id")) == group_id), {})
    lines = ["# Group Blockers", "", f"Generated: {utc_now().date().isoformat()}", ""]
    project_ids = [str(project_id).strip() for project_id in (group.get("projects") or []) if str(project_id).strip()]
    if project_ids:
        lines.append(f"Members: {', '.join(project_ids)}")
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
    blockers = text_items((load_program_registry(config).get("groups") or {}).get(group_id, {}).get("contract_blockers"))
    if blockers:
        lines.extend(["", "## Current Contract Blockers", ""])
        lines.extend(f"- {item}" for item in blockers)
    return "\n".join(lines) + "\n"


def render_group_contract_sets_yaml(group_id: str, candidate: sqlite3.Row, config: Dict[str, Any]) -> str:
    group = next((item for item in config.get("project_groups") or [] if str(item.get("id")) == group_id), {})
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


def publish_project_audit_candidate_runtime(
    config: Dict[str, Any],
    candidate_row: sqlite3.Row,
    *,
    queue_mode: str = "append",
    source: str = "auto",
) -> bool:
    if str(candidate_row["scope_type"] or "") != "project":
        return False
    try:
        project_cfg = get_project_cfg(config, str(candidate_row["scope_id"]))
    except KeyError:
        return False

    project_id = str(project_cfg["id"])
    finding = audit_finding_row(str(candidate_row["scope_type"]), str(candidate_row["scope_id"]), str(candidate_row["finding_key"]))
    overlay_path = merge_queue_overlay_item(project_cfg, str(candidate_row["detail"] or candidate_row["title"] or "").strip(), mode=queue_mode)

    feedback_dir = pathlib.Path(project_cfg["path"]) / project_cfg.get("feedback_dir", "feedback")
    feedback_dir.mkdir(parents=True, exist_ok=True)
    note_path = feedback_dir / feedback_filename(f"audit-task-{candidate_row['id']}")
    note_lines = [
        "# Auditor Publication",
        "",
        f"Date: {utc_now().date().isoformat()}",
        f"Candidate ID: {candidate_row['id']}",
        f"Scope: {candidate_row['scope_type']}:{candidate_row['scope_id']}",
        f"Finding Key: {candidate_row['finding_key']}",
        f"Source: {source}",
        "",
        "## Task",
        f"- Title: {candidate_row['title']}",
        f"- Detail: {candidate_row['detail']}",
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
            "",
            "This task was published from the fleet auditor flow.",
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")

    with db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if row:
        update_project_status(
            project_id,
            status=READY_STATUS,
            current_slice=row["current_slice"],
            active_run_id=None,
            cooldown_until=None,
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=None,
            consecutive_failures=0,
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )

    project_groups = project_group_defs(config, project_id)
    if project_groups:
        group_id = str(project_groups[0].get("id") or "")
        upsert_group_runtime(group_id, signoff_state="open", mark_refill_requested=True)
        log_group_publish_event(
            group_id,
            source=source,
            source_scope_type="project",
            source_scope_id=project_id,
            finding_key=str(candidate_row["finding_key"] or ""),
            candidate_id=int(candidate_row["id"]),
            published_targets=[
                {
                    "target_type": "project",
                    "target_id": project_id,
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
            member_projects=[project_id],
            details={
                "source_scope_type": "project",
                "source_scope_id": project_id,
                "candidate_id": int(candidate_row["id"]),
                "finding_key": str(candidate_row["finding_key"] or ""),
                "queue_mode": queue_mode,
            },
        )
    set_audit_candidate_status(int(candidate_row["id"]), "published", resolved=True)
    return True


def publish_group_audit_candidate_runtime(
    config: Dict[str, Any],
    candidate_row: sqlite3.Row,
    *,
    source: str = "auto",
) -> bool:
    if str(candidate_row["scope_type"] or "") != "group":
        return False
    group_id = str(candidate_row["scope_id"] or "").strip()
    group_ids = {str(group.get("id")) for group in config.get("project_groups") or []}
    if not group_id or group_id not in group_ids:
        return False
    finding = audit_finding_row("group", group_id, str(candidate_row["finding_key"]))
    published_root = group_published_root(group_id)
    feedback_root = group_feedback_root(group_id)
    published_root.mkdir(parents=True, exist_ok=True)
    feedback_root.mkdir(parents=True, exist_ok=True)

    files_written: List[Dict[str, Any]] = []
    group_cfg = next((item for item in config.get("project_groups") or [] if str(item.get("id") or "") == group_id), {})
    member_projects = [str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()]
    blockers_path = published_root / "GROUP_BLOCKERS.md"
    blockers_path.write_text(render_group_blockers_markdown(group_id, candidate_row, finding, config), encoding="utf-8")
    files_written.append({"target_type": "group", "target_id": group_id, "path": str(blockers_path), "file_count": 1})

    finding_key = str(candidate_row["finding_key"] or "")
    detail_lower = f"{finding_key} {candidate_row['title']} {candidate_row['detail']}".lower()
    if "contract" in detail_lower or "session" in detail_lower or "dto" in detail_lower or "explain" in detail_lower:
        contract_path = published_root / "CONTRACT_SETS.yaml"
        contract_path.write_text(render_group_contract_sets_yaml(group_id, candidate_row, config), encoding="utf-8")
        files_written.append({"target_type": "group", "target_id": group_id, "path": str(contract_path), "file_count": 1})
    if "milestone" in detail_lower or "scope" in detail_lower or "coverage" in detail_lower:
        milestone_path = published_root / "PROGRAM_MILESTONES.generated.yaml"
        milestone_path.write_text(render_group_program_milestones_yaml(group_id, candidate_row, finding, config), encoding="utf-8")
        files_written.append({"target_type": "group", "target_id": group_id, "path": str(milestone_path), "file_count": 1})

    if len(member_projects) == 1:
        project_id = member_projects[0]
        try:
            project_cfg = get_project_cfg(config, project_id)
        except KeyError:
            project_cfg = None
        if project_cfg:
            overlay_path = merge_queue_overlay_item(project_cfg, str(candidate_row["detail"] or candidate_row["title"] or "").strip(), mode="append")
            files_written.append({"target_type": "project", "target_id": project_id, "path": str(overlay_path), "file_count": 1})
            with db() as conn:
                row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if row and not row["active_run_id"]:
                update_project_status(
                    project_id,
                    status=READY_STATUS,
                    current_slice=row["current_slice"],
                    active_run_id=None,
                    cooldown_until=None,
                    last_run_at=parse_iso(row["last_run_at"]),
                    last_error=None,
                    consecutive_failures=0,
                    spider_tier=row["spider_tier"],
                    spider_model=row["spider_model"],
                    spider_reason=row["spider_reason"],
                )

    note_path = feedback_root / feedback_filename(f"group-audit-task-{candidate_row['id']}")
    note_lines = [
        "# Group Auditor Publication",
        "",
        f"Date: {utc_now().date().isoformat()}",
        f"Candidate ID: {candidate_row['id']}",
        f"Group: {group_id}",
        f"Finding Key: {candidate_row['finding_key']}",
        f"Source: {source}",
        "",
        "## Task",
        f"- Title: {candidate_row['title']}",
        f"- Detail: {candidate_row['detail']}",
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
    note_lines.extend(
        [
            "",
            "## Published Targets",
            *[f"- {item['path']}" for item in files_written],
        ]
    )
    note_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")
    files_written.append({"target_type": "group", "target_id": group_id, "path": str(note_path), "file_count": 1})

    upsert_group_runtime(group_id, signoff_state="open", mark_refill_requested=True)
    log_group_publish_event(
        group_id,
        source=source,
        source_scope_type="group",
        source_scope_id=group_id,
        finding_key=str(candidate_row["finding_key"] or ""),
        candidate_id=int(candidate_row["id"]),
        published_targets=files_written,
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
            "candidate_id": int(candidate_row["id"]),
            "finding_key": str(candidate_row["finding_key"] or ""),
        },
    )
    set_audit_candidate_status(int(candidate_row["id"]), "published", resolved=True)
    return True


def auto_publish_approved_audit_candidates(config: Dict[str, Any]) -> int:
    if not table_exists("audit_task_candidates"):
        return 0
    with db() as conn:
        project_rows = {row["id"]: row for row in conn.execute("SELECT * FROM projects ORDER BY id").fetchall()}
        candidate_rows = conn.execute(
            """
            SELECT *
            FROM audit_task_candidates
            WHERE status IN ('open', 'approved', 'published')
            ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
                     CASE scope_type WHEN 'group' THEN 0 ELSE 1 END,
                     scope_id,
                     last_seen_at ASC,
                     task_index ASC
            """
        ).fetchall()
    if not candidate_rows:
        return 0

    published = 0
    registry = load_program_registry(config)
    runtime_rows = group_runtime_rows()
    for candidate in candidate_rows:
        recommended = audit_task_candidate_is_recommended(candidate)
        scope_type = str(candidate["scope_type"] or "").strip()
        scope_id = str(candidate["scope_id"] or "").strip()
        candidate_status = str(candidate["status"] or "").strip().lower()
        category = audit_task_candidate_category(candidate)
        category_auto_heal = auto_heal_category_enabled(
            config,
            category,
            project_id=scope_id if scope_type == "project" else None,
            group_id=scope_id if scope_type == "group" else None,
        )
        if not recommended and not category_auto_heal:
            continue
        if candidate_status == "open" and not recommended:
            continue
        if scope_type == "group":
            if candidate_status == "published":
                continue
            group_cfg = next((item for item in config.get("project_groups") or [] if str(item.get("id")) == scope_id), None)
            if not group_cfg:
                continue
            group_meta = effective_group_meta(group_cfg, registry, runtime_rows)
            if group_is_signed_off(group_meta):
                continue
            project_ids = [str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()]
            if any(project_id in state.tasks for project_id in project_ids) and not (recommended and len(project_ids) > 1):
                continue
            if recommended:
                if publish_audit_candidate_via_admin(int(candidate["id"])):
                    published += 1
                continue
            if audit_task_candidate_meta(candidate).get("bootstrap_project"):
                continue
            if publish_group_audit_candidate_runtime(config, candidate, source="auto"):
                published += 1
            continue

        if scope_type != "project":
            continue
        row = project_rows.get(scope_id)
        if not row or scope_id in state.tasks:
            continue
        queue = json.loads(row["queue_json"] or "[]")
        queue_exhausted = int(row["queue_index"] or 0) >= len(queue)
        try:
            project_cfg = get_project_cfg(config, scope_id)
        except KeyError:
            continue
        overlay_items = queue_overlay_items(project_cfg)
        candidate_text = audit_candidate_queue_text(candidate)
        overlay_has_candidate = candidate_text in overlay_items if candidate_text else False
        project_groups = project_group_defs(config, scope_id)
        if project_groups:
            group_cfg = project_groups[0]
            group_meta = effective_group_meta(group_cfg, registry, runtime_rows)
            if group_is_signed_off(group_meta):
                continue
            member_ids = [str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()]
            if any(member_id in state.tasks for member_id in member_ids):
                continue
        if recommended:
            if publish_audit_candidate_via_admin(int(candidate["id"])):
                published += 1
            continue
        if audit_task_candidate_meta(candidate).get("bootstrap_project"):
            continue
        project_status = str(row["status"] or "").strip()
        can_rehydrate_published_candidate = (
            candidate_status == "published"
            and queue_exhausted
            and not overlay_has_candidate
            and project_status in {"complete", SOURCE_BACKLOG_OPEN_STATUS, HEALING_STATUS, QUEUE_REFILLING_STATUS}
        )
        if candidate_status == "published" and not can_rehydrate_published_candidate:
            continue
        queue_mode = "prepend" if candidate_status == "published" else "append"
        if publish_project_audit_candidate_runtime(config, candidate, queue_mode=queue_mode, source="auto"):
            published += 1
    return published


def reconcile_abandoned_runs() -> None:
    with db() as conn:
        now = iso(utc_now())
        conn.execute(
            "UPDATE runs SET status='abandoned', finished_at=COALESCE(finished_at, ?) WHERE status IN ('starting', 'running', 'verifying')",
            (now,),
        )
        conn.execute(
            "UPDATE projects SET status=?, active_run_id=NULL, updated_at=? WHERE status IN ('starting', 'running', 'verifying')",
            (READY_STATUS, now),
        )


def latest_worker_activity_at(project_cfg: Dict[str, Any], project_row: sqlite3.Row, run_row: Optional[sqlite3.Row]) -> Optional[dt.datetime]:
    timestamps: List[dt.datetime] = []
    state_payload = read_state_file(project_cfg["path"], project_cfg.get("state_file") or ".agent-state.json")
    if isinstance(state_payload, dict):
        heartbeat_at = parse_iso(str(state_payload.get("updated_at_utc") or "").strip())
        if heartbeat_at:
            timestamps.append(heartbeat_at)
    if "last_run_at" in project_row.keys():
        last_run_at = parse_iso(project_row["last_run_at"])
        if last_run_at:
            timestamps.append(last_run_at)
    if run_row:
        if "run_started_at" in run_row.keys():
            started_at = parse_iso(run_row["run_started_at"])
        elif "started_at" in run_row.keys():
            started_at = parse_iso(run_row["started_at"])
        else:
            started_at = None
        if started_at:
            timestamps.append(started_at)
        log_path_text = ""
        if "run_log_path" in run_row.keys():
            log_path_text = str(run_row["run_log_path"] or "").strip()
        elif "log_path" in run_row.keys():
            log_path_text = str(run_row["log_path"] or "").strip()
        if log_path_text:
            log_path = pathlib.Path(log_path_text)
            if log_path.exists():
                timestamps.append(dt.datetime.fromtimestamp(log_path.stat().st_mtime, tz=UTC))
    return max(timestamps) if timestamps else None


def reconcile_stale_worker_sessions(config: Dict[str, Any]) -> int:
    stale_seconds = max(300, int(get_policy(config, "stale_heartbeat_seconds", 1800)))
    max_failures = int(get_policy(config, "max_consecutive_failures", 3))
    cooldown_seconds = int(get_policy(config, "restart_cooldown_seconds", 120))
    now = utc_now()
    recovered = 0
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.*,
                   r.started_at AS run_started_at,
                   r.log_path AS run_log_path,
                   r.status AS run_status
            FROM projects p
            LEFT JOIN runs r ON r.id = p.active_run_id
            WHERE p.status IN ('starting', 'running', 'verifying')
            ORDER BY p.id
            """
        ).fetchall()
    for row in rows:
        project_id = str(row["id"] or "").strip()
        if not project_id:
            continue
        try:
            project_cfg = get_project_cfg(config, project_id)
        except KeyError:
            continue
        activity_at = latest_worker_activity_at(project_cfg, row, row)
        if not activity_at or activity_at > now - dt.timedelta(seconds=stale_seconds):
            continue
        stale_age_seconds = int(max(0, (now - activity_at).total_seconds()))
        reason = f"worker session went stale after {stale_age_seconds}s without heartbeat or log activity"
        failures = int(row["consecutive_failures"] or 0) + 1
        next_status = "blocked" if failures >= max_failures else READY_STATUS
        cooldown_until = now + dt.timedelta(seconds=cooldown_seconds)
        task = state.tasks.get(project_id)
        if task and not task.done():
            task.cancel()
        with db() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status='failed',
                    finished_at=COALESCE(finished_at, ?),
                    error_class='stale_heartbeat',
                    error_message=COALESCE(error_message, ?)
                WHERE id=?
                  AND status IN ('starting', 'running', 'verifying')
                """,
                (iso(now), reason, row["active_run_id"]),
            )
        update_project_status(
            project_id,
            status=next_status,
            current_slice=row["current_slice"],
            active_run_id=None,
            cooldown_until=cooldown_until,
            last_run_at=now,
            last_error=reason,
            consecutive_failures=failures,
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
        recovered += 1
    return recovered


def reconcile_finished_run_links() -> int:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.*,
                   r.status AS run_status
            FROM projects p
            LEFT JOIN runs r ON r.id = p.active_run_id
            WHERE p.active_run_id IS NOT NULL
            ORDER BY p.id
            """
        ).fetchall()
    reconciled = 0
    for row in rows:
        run_status = str(row["run_status"] or "").strip().lower()
        if run_status in {"starting", "running", "verifying"}:
            continue
        project_id = str(row["id"] or "").strip()
        if not project_id:
            continue
        status = str(row["status"] or "").strip() or READY_STATUS
        if status in {"starting", "running", "verifying"}:
            status = READY_STATUS
        update_project_status(
            project_id,
            status=status,
            current_slice=row["current_slice"],
            active_run_id=None,
            cooldown_until=parse_iso(row["cooldown_until"]),
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=row["last_error"],
            consecutive_failures=row["consecutive_failures"],
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
        reconciled += 1
    return reconciled


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError:
        # Generated queue/design overlays are recoverable runtime artifacts. Treat parse failures
        # as empty state so the scheduler can heal them on the next publish instead of crashing.
        if path.name in {"QUEUE.generated.yaml", "PROGRAM_MILESTONES.generated.yaml", "CONTRACT_SETS.yaml"} and (
            STUDIO_DIRNAME in path.parts or "groups" in path.parts
        ):
            return {}
        raise


def save_yaml(path: pathlib.Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True, width=100000)
    tmp_path.replace(path)


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


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


def project_dispatch_priority(project: Dict[str, Any]) -> int:
    return int(project.get("dispatch_priority") or 100)


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
    fleet.setdefault("lanes", {})
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet["spider"] = deep_merge(DEFAULT_SPIDER, fleet.get("spider") or {})
    fleet["lanes"] = normalize_lanes_config(fleet.get("lanes"))
    price_table = deep_merge(DEFAULT_PRICE_TABLE, (fleet["spider"].get("price_table") or {}))
    fleet["spider"]["price_table"] = price_table
    fleet["accounts"] = accounts_cfg.get("accounts", {}) or {}

    fleet["project_groups"] = normalized_project_groups(fleet["projects"], fleet["project_groups"])
    auto_heal = fleet["policies"].setdefault("auto_heal", {})
    auto_heal.setdefault("categories", {})
    auto_heal.setdefault("escalation_thresholds", {})
    compile_cfg = fleet["policies"].setdefault("compile", {})
    compile_cfg["freshness_hours"] = {
        **DEFAULT_COMPILE_FRESHNESS_HOURS,
        **(compile_cfg.get("freshness_hours") or {}),
    }

    for project in fleet["projects"]:
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("verify_cmd", "")
        project.setdefault("design_doc", "")
        project.setdefault("enabled", True)
        project["lifecycle"] = normalize_lifecycle_state(project.get("lifecycle"), "dispatchable")
        project.setdefault("accounts", [])
        project.setdefault("account_policy", {})
        project.setdefault("queue_sources", [])
        project["dispatch_priority"] = project_dispatch_priority(project)
        project["queue"] = [
            normalize_task_queue_item(item, lanes=fleet["lanes"])
            for item in resolve_project_queue(project)
        ]
        project["runner"] = project.get("runner") or {}
        project["spider"] = deep_merge(fleet["spider"], project.get("spider") or {})
        project["review"] = dict(project.get("review") or {})
        policy = project["account_policy"]
        project["runner"].setdefault("always_continue", True)
        project["runner"].setdefault("avoid_permission_escalation", True)
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
        review.setdefault("base_branch", "")
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
    raise_for_config_consistency(fleet)
    return fleet


def get_policy(config: Dict[str, Any], key: str, default: Any) -> Any:
    return (config.get("policies") or {}).get(key, default)


def get_int_policy(config: Dict[str, Any], key: str, default: int) -> int:
    value = get_policy(config, key, default)
    if value is None:
        return int(default)
    if isinstance(value, str) and not value.strip():
        return int(default)
    return int(value)


def auto_heal_category_enabled(
    config: Dict[str, Any],
    category: str,
    *,
    project_id: Optional[str] = None,
    group_id: Optional[str] = None,
    default: bool = True,
) -> bool:
    policies = config.get("policies") or {}
    if not bool(policies.get("auto_heal_enabled", True)):
        return False
    auto_heal = policies.get("auto_heal") or {}
    category_key = str(category or "").strip().lower()

    project_overrides = auto_heal.get("projects") or {}
    if project_id:
        project_policy = project_overrides.get(str(project_id).strip()) or {}
        if isinstance(project_policy, dict):
            categories = project_policy.get("categories") or {}
            if category_key in categories:
                return bool(categories.get(category_key))
            if "enabled" in project_policy:
                return bool(project_policy.get("enabled"))
        elif project_policy is not None:
            return bool(project_policy)

    group_overrides = auto_heal.get("groups") or {}
    if group_id:
        group_policy = group_overrides.get(str(group_id).strip()) or {}
        if isinstance(group_policy, dict):
            categories = group_policy.get("categories") or {}
            if category_key in categories:
                return bool(categories.get(category_key))
            if "enabled" in group_policy:
                return bool(group_policy.get("enabled"))
        elif group_policy is not None:
            return bool(group_policy)

    categories = auto_heal.get("categories") or {}
    if category_key in categories:
        return bool(categories.get(category_key))
    return default


def normalize_allowed_models_for_account(auth_kind: str, allowed_models: Any) -> List[str]:
    normalized: List[str] = []
    for item in allowed_models or []:
        model = str(item or "").strip()
        if model and model not in normalized:
            normalized.append(model)
    if auth_kind in CHATGPT_AUTH_KINDS:
        normalized = [model for model in normalized if model in CHATGPT_SUPPORTED_MODELS]
    return normalized


def sync_config_to_db(config: Dict[str, Any]) -> None:
    now = iso(utc_now())
    with db() as conn:
        for alias, account in (config.get("accounts") or {}).items():
            auth_kind = account.get("auth_kind", "api_key")
            allowed_models = normalize_allowed_models_for_account(auth_kind, account.get("allowed_models", []))
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, api_key_file, api_key_env, auth_json_file, allowed_models_json, daily_budget_usd, monthly_budget_usd, max_parallel_runs, health_state, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(alias) DO UPDATE SET
                    auth_kind=excluded.auth_kind,
                    api_key_file=excluded.api_key_file,
                    api_key_env=excluded.api_key_env,
                    auth_json_file=excluded.auth_json_file,
                    allowed_models_json=excluded.allowed_models_json,
                    daily_budget_usd=excluded.daily_budget_usd,
                    monthly_budget_usd=excluded.monthly_budget_usd,
                    max_parallel_runs=excluded.max_parallel_runs,
                    health_state=excluded.health_state,
                    updated_at=excluded.updated_at
                """,
                (
                    alias,
                    auth_kind,
                    account.get("api_key_file", ""),
                    account.get("api_key_env", ""),
                    account.get("auth_json_file", ""),
                    json.dumps(allowed_models),
                    account.get("daily_budget_usd"),
                    account.get("monthly_budget_usd"),
                    int(account.get("max_parallel_runs", 1)),
                    str(account.get("health_state", "ready") or "ready"),
                    now,
                ),
            )

        for project in config.get("projects", []):
            row = conn.execute("SELECT * FROM projects WHERE id=?", (project["id"],)).fetchone()
            existing_index = row["queue_index"] if row else 0
            existing_queue = json.loads(row["queue_json"]) if row and row["queue_json"] else []
            new_queue = project.get("queue", [])
            queue_index = remap_queue_index(existing_queue, existing_index, new_queue)
            conn.execute(
                """
                INSERT INTO projects(id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path=excluded.path,
                    design_doc=excluded.design_doc,
                    verify_cmd=excluded.verify_cmd,
                    feedback_dir=excluded.feedback_dir,
                    state_file=excluded.state_file,
                    queue_json=excluded.queue_json,
                    queue_index=?,
                    updated_at=excluded.updated_at
                """,
                (
                    project["id"],
                    project["path"],
                    project.get("design_doc", ""),
                    project.get("verify_cmd", ""),
                    project.get("feedback_dir", "feedback"),
                    project.get("state_file", ".agent-state.json"),
                    json.dumps(new_queue),
                    queue_index,
                    now,
                    queue_index,
                ),
            )
            if row:
                next_status = effective_project_status(
                    project_id=project["id"],
                    stored_status=row["status"],
                    queue=new_queue,
                    queue_index=queue_index,
                    enabled=bool(project.get("enabled", True)),
                    active_run_id=row["active_run_id"],
                    source_backlog_open=bool(project.get("queue_sources")) and bool(new_queue),
                )
                next_slice = normalize_slice_text(new_queue[queue_index]) if queue_index < len(new_queue) else None
                if next_status != row["status"] or next_slice != row["current_slice"]:
                    conn.execute(
                        """
                        UPDATE projects
                        SET status=?,
                            current_slice=?,
                            active_run_id=CASE WHEN ? IN (?, 'complete', 'paused', 'source_backlog_open') THEN NULL ELSE active_run_id END,
                            updated_at=?
                        WHERE id=?
                        """,
                        (next_status, next_slice, next_status, READY_STATUS, now, project["id"]),
                    )


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
    review.setdefault("base_branch", "")
    review.setdefault("branch_template", f"fleet/{project_cfg.get('id', 'project')}")
    review.setdefault("bot_logins", ["codex"])
    return review


def github_token() -> Optional[str]:
    if not GH_HOSTS_PATH.exists():
        return None
    data = load_yaml(GH_HOSTS_PATH)
    host_entry = data.get("github.com") if isinstance(data, dict) else None
    if not isinstance(host_entry, dict):
        return None
    token = str(host_entry.get("oauth_token") or "").strip()
    return token or None


def run_capture(
    cmd: List[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_seconds: Optional[int] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def parse_github_remote(remote_url: str) -> Tuple[Optional[str], Optional[str]]:
    raw = str(remote_url or "").strip()
    if not raw:
        return None, None
    ssh_match = re.match(r"git@github\\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\\.git)?$", raw)
    if ssh_match:
        return ssh_match.group("owner"), ssh_match.group("repo")
    https_match = re.match(r"https://github\\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\\.git)?/?$", raw)
    if https_match:
        return https_match.group("owner"), https_match.group("repo")
    return None, None


def repo_origin(project_cfg: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    repo_path = str(project_cfg["path"])
    result = run_capture(["git", "remote", "get-url", "origin"], cwd=repo_path, timeout_seconds=30)
    if result.returncode != 0:
        return None, None, None
    remote_url = (result.stdout or "").strip()
    owner, repo = parse_github_remote(remote_url)
    return remote_url or None, owner, repo


def github_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "codex-fleet",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_public_headers() -> Dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": "codex-fleet",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def verify_github_webhook_signature(body: bytes, signature_header: str) -> bool:
    secret = str(GITHUB_WEBHOOK_SECRET or "").strip()
    if not secret:
        return True
    header = str(signature_header or "").strip()
    if not header.startswith("sha256="):
        return False
    provided = header.split("=", 1)[1].strip().lower()
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest().lower()
    return hmac.compare_digest(provided, digest)


def webhook_project_ids(payload: Dict[str, Any]) -> List[str]:
    repository = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    owner = ""
    repo = ""
    if isinstance(repository, dict):
        owner_info = repository.get("owner")
        owner = str((owner_info or {}).get("login") or owner_info or "").strip()
        repo = str(repository.get("name") or "").strip()
    pull_request = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
    pr_number = int(pull_request.get("number") or payload.get("number") or 0)
    head_sha = str(
        ((payload.get("check_run") or {}).get("head_sha"))
        or ((payload.get("check_suite") or {}).get("head_sha"))
        or ((pull_request.get("head") or {}).get("sha"))
        or ""
    ).strip()
    if not table_exists("pull_requests"):
        return []
    clauses: List[str] = []
    params: List[Any] = []
    if owner and repo:
        clauses.append("repo_owner=? AND repo_name=?")
        params.extend([owner, repo])
    if pr_number > 0:
        clauses.append("pr_number=?")
        params.append(pr_number)
    if head_sha:
        clauses.append("(head_sha=? OR last_review_head_sha=?)")
        params.extend([head_sha, head_sha])
    if not clauses:
        return []
    query = "SELECT project_id FROM pull_requests WHERE " + " AND ".join(clauses)
    with db() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return sorted({str(row["project_id"] or "").strip() for row in rows if str(row["project_id"] or "").strip()})


def github_api_json(
    token: str,
    method: str,
    path: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{GITHUB_API_BASE}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    method_name = method.upper()
    data = None
    headers = github_headers(token)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method_name)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        reset_at = None
        reset_header = exc.headers.get("X-RateLimit-Reset") if exc.headers else None
        if reset_header:
            with contextlib.suppress(Exception):
                reset_at = dt.datetime.fromtimestamp(int(str(reset_header).strip()), UTC)
        remaining_header = str(exc.headers.get("X-RateLimit-Remaining") or "").strip() if exc.headers else ""
        lower_detail = detail.lower()
        rate_limited = exc.code in {403, 429} and (
            "rate limit" in lower_detail or "secondary rate limit" in lower_detail or remaining_header == "0"
        )
        if method_name == "GET" and "rate limit exceeded" in detail.lower():
            fallback = urllib.request.Request(url, headers=github_public_headers(), method=method_name)
            try:
                with urllib.request.urlopen(fallback, timeout=60) as response:
                    raw = response.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError:
                pass
        if rate_limited:
            raise GitHubRateLimitError(
                f"github api {method_name} {path} throttled: {exc.code} {detail}",
                reset_at=reset_at,
            ) from exc
        raise RuntimeError(f"github api {method_name} {path} failed: {exc.code} {detail}") from exc
    return json.loads(raw) if raw.strip() else {}


def github_graphql_json(token: str, query: str, variables: Optional[Dict[str, Any]] = None) -> Any:
    return github_api_json(token, "POST", "/graphql", payload={"query": query, "variables": variables or {}})


def project_github_repo(project_cfg: Dict[str, Any], token: Optional[str]) -> Dict[str, Any]:
    review = project_review_policy(project_cfg)
    owner = str(review.get("owner") or "").strip()
    repo = str(review.get("repo") or "").strip()
    remote_url = None
    if not owner or not repo:
        remote_url, remote_owner, remote_repo = repo_origin(project_cfg)
        owner = owner or (remote_owner or "")
        repo = repo or (remote_repo or "")
    if not owner or not repo:
        raise RuntimeError(f"unable to resolve GitHub owner/repo for project {project_cfg['id']}")
    base_branch = str(review.get("base_branch") or "").strip()
    repo_url = f"https://github.com/{owner}/{repo}"
    if not base_branch and token:
        repo_info = github_api_json(token, "GET", f"/repos/{owner}/{repo}")
        base_branch = str(repo_info.get("default_branch") or "").strip()
        repo_url = str(repo_info.get("html_url") or repo_url).strip() or repo_url
    if not base_branch:
        base_branch = "main"
    return {"owner": owner, "repo": repo, "base_branch": base_branch, "repo_url": repo_url, "remote_url": remote_url}


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
    pr["needs_core_rescue"] = bool(pr.get("needs_core_rescue"))
    pr["pass_without_core"] = bool(pr.get("pass_without_core"))
    return pr


def review_hold_status_for_project(
    project_id: str,
    *,
    project_cfg: Optional[Dict[str, Any]] = None,
    pr_row: Optional[Dict[str, Any]] = None,
) -> str:
    pr = pr_row or pull_request_row(project_id) or {}
    loop_stage = review_loop_stage(pr)
    cfg = project_cfg
    if cfg is None:
        try:
            cfg = get_project_cfg(normalize_config(), project_id)
        except Exception:
            cfg = {}
    review_mode = str(project_review_policy(cfg or {}).get("mode") or "github").strip().lower()
    if review_mode != "github":
        if loop_stage in {AWAITING_FIRST_REVIEW_STATUS, REVIEW_LIGHT_PENDING_STATUS, JURY_REVIEW_PENDING_STATUS, MANUAL_HOLD_STATUS}:
            return loop_stage
        return "review_requested"
    return "review_requested" if int(pr.get("pr_number") or 0) > 0 else "awaiting_pr"


def upsert_local_review_request(
    project_cfg: Dict[str, Any],
    *,
    slice_name: str,
    requested_at: Optional[dt.datetime] = None,
    review_focus: Optional[str] = None,
    workflow_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _upsert_local_review_request_impl(
        project_cfg,
        slice_name=slice_name,
        requested_at=requested_at,
        review_focus=review_focus,
        workflow_state=workflow_state,
    )


def _upsert_local_review_request_impl(
    project_cfg: Dict[str, Any],
    *,
    slice_name: str,
    requested_at: Optional[dt.datetime],
    review_focus: Optional[str],
    workflow_state: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    project_id = str(project_cfg["id"] or "").strip()
    if not project_id:
        return {}
    review = project_review_policy(project_cfg)
    owner = str(review.get("owner") or "").strip()
    repo = str(review.get("repo") or "").strip()
    base_branch = str(review.get("base_branch") or "main").strip() or "main"
    trigger = str(review.get("trigger") or "local").strip() or "local"
    focus = str(review_focus or review_focus_text(project_cfg, slice_name)).strip()
    now = iso(requested_at or utc_now())
    focus_metadata = decode_review_focus(focus)[1]
    focus_slice_key = str(focus_metadata.get("slice_key") or review_slice_key(slice_name)).strip()
    workflow = dict(workflow_state or {})
    workflow_kind = str(workflow.get("workflow_kind") or focus_metadata.get("workflow_kind") or "default").strip().lower() or "default"
    review_round = int(workflow.get("review_round") or focus_metadata.get("review_round") or 0)
    max_review_rounds = int(workflow.get("max_review_rounds") or focus_metadata.get("max_review_rounds") or 0)
    groundwork_time_ms = int(workflow.get("groundwork_time_ms") or 0)
    core_time_ms = int(workflow.get("core_time_ms") or 0)
    allowance_burn_json = json.dumps(dict(workflow.get("allowance_burn_by_lane") or {}), sort_keys=True)
    with db() as conn:
        conn.execute(
            """
            INSERT INTO pull_requests(
                project_id, repo_owner, repo_name, branch_name, base_branch, pr_number, pr_url, pr_title, pr_body, pr_state, draft,
                head_sha, review_mode, review_trigger, review_focus, review_status, review_requested_at, review_completed_at,
                review_findings_count, review_blocking_findings_count, last_synced_at, review_sync_failures, next_retry_at,
                workflow_kind, review_round, max_review_rounds, first_review_complete_at, accepted_on_round, needs_core_rescue,
                core_rescue_reason, jury_feedback_history_json, issue_fingerprints_json, blocking_issue_count_by_round_json,
                repeat_issue_count_by_round_json, groundwork_time_ms, jury_time_ms, core_time_ms, allowance_burn_by_lane_json, pass_without_core,
                created_at, updated_at
            )
            VALUES(?, ?, ?, '', ?, 0, '', ?, ?, 'local', 0, '', 'local', ?, ?, ?, ?, NULL, 0, 0, NULL, 0, NULL, ?, ?, ?, NULL, NULL, 0, '', '[]', '[]', '[]', '[]', ?, 0, ?, ?, 0, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                repo_owner=excluded.repo_owner,
                repo_name=excluded.repo_name,
                branch_name='',
                base_branch=excluded.base_branch,
                pr_number=0,
                pr_url='',
                pr_title=excluded.pr_title,
                pr_body=excluded.pr_body,
                pr_state='local',
                draft=0,
                head_sha='',
                review_mode='local',
                review_trigger=excluded.review_trigger,
                review_focus=excluded.review_focus,
                review_status=excluded.review_status,
                review_requested_at=excluded.review_requested_at,
                review_completed_at=NULL,
                review_findings_count=0,
                review_blocking_findings_count=0,
                last_synced_at=NULL,
                review_sync_failures=0,
                review_retrigger_count=0,
                review_wakeup_miss_count=0,
                local_review_attempts=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.local_review_attempts
                    ELSE 0
                END,
                local_review_last_at=NULL,
                workflow_kind=excluded.workflow_kind,
                review_round=excluded.review_round,
                max_review_rounds=excluded.max_review_rounds,
                first_review_complete_at=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.first_review_complete_at
                    ELSE NULL
                END,
                accepted_on_round=NULL,
                needs_core_rescue=0,
                core_rescue_reason='',
                jury_feedback_history_json=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.jury_feedback_history_json
                    ELSE '[]'
                END,
                issue_fingerprints_json=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.issue_fingerprints_json
                    ELSE '[]'
                END,
                blocking_issue_count_by_round_json=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.blocking_issue_count_by_round_json
                    ELSE '[]'
                END,
                repeat_issue_count_by_round_json=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.repeat_issue_count_by_round_json
                    ELSE '[]'
                END,
                groundwork_time_ms=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.groundwork_time_ms + ?
                    ELSE ?
                END,
                jury_time_ms=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.jury_time_ms
                    ELSE 0
                END,
                core_time_ms=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.core_time_ms + ?
                    ELSE ?
                END,
                allowance_burn_by_lane_json=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.allowance_burn_by_lane_json
                    ELSE excluded.allowance_burn_by_lane_json
                END,
                pass_without_core=CASE
                    WHEN instr(COALESCE(pull_requests.review_focus, ''), 'slice_key=' || ?) > 0
                    THEN pull_requests.pass_without_core
                    ELSE 0
                END,
                next_retry_at=NULL,
                review_rate_limit_reset_at=NULL,
                updated_at=excluded.updated_at
            """,
            (
                project_id,
                owner,
                repo,
                base_branch,
                f"Local review for {slice_name}",
                f"Automated local review queued for `{project_id}` slice `{slice_name}`.",
                trigger,
                focus,
                LOCAL_REVIEW_PENDING_STATUS,
                now,
                workflow_kind,
                review_round,
                max_review_rounds,
                groundwork_time_ms,
                core_time_ms,
                allowance_burn_json,
                now,
                now,
                focus_slice_key,
                focus_slice_key,
                focus_slice_key,
                focus_slice_key,
                focus_slice_key,
                focus_slice_key,
                focus_slice_key,
                groundwork_time_ms,
                groundwork_time_ms,
                focus_slice_key,
                focus_slice_key,
                core_time_ms,
                core_time_ms,
                focus_slice_key,
                focus_slice_key,
                now,
            ),
        )
    return pull_request_row(project_id) or {}


def persist_pending_review_request(
    project_cfg: Dict[str, Any],
    *,
    repo_meta: Dict[str, Any],
    branch_name: str,
    head_sha: str,
    slice_name: str,
    requested_at: Optional[dt.datetime] = None,
) -> None:
    project_id = str(project_cfg["id"] or "").strip()
    if not project_id:
        return
    existing = pull_request_row(project_id) or {}
    owner = str(existing.get("repo_owner") or repo_meta.get("owner") or "").strip()
    repo = str(existing.get("repo_name") or repo_meta.get("repo") or "").strip()
    base_branch = str(existing.get("base_branch") or repo_meta.get("base_branch") or "main").strip() or "main"
    if not owner or not repo:
        return
    now = iso(requested_at or utc_now())
    pr_number = int(existing.get("pr_number") or 0)
    review_status = "review_requested" if pr_number > 0 else "awaiting_pr"
    with db() as conn:
        conn.execute(
            """
            INSERT INTO pull_requests(
                project_id, repo_owner, repo_name, branch_name, base_branch, pr_number, pr_url, pr_title, pr_body, pr_state, draft,
                head_sha, review_mode, review_trigger, review_focus, review_status, review_requested_at, review_completed_at,
                review_findings_count, review_blocking_findings_count, last_synced_at, review_sync_failures, next_retry_at, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'github', ?, ?, ?, ?, NULL, 0, 0, NULL, 0, NULL, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                repo_owner=excluded.repo_owner,
                repo_name=excluded.repo_name,
                branch_name=excluded.branch_name,
                base_branch=excluded.base_branch,
                head_sha=excluded.head_sha,
                review_trigger=excluded.review_trigger,
                review_focus=excluded.review_focus,
                review_status=excluded.review_status,
                review_requested_at=excluded.review_requested_at,
                review_completed_at=NULL,
                review_findings_count=0,
                review_blocking_findings_count=0,
                last_synced_at=NULL,
                review_sync_failures=0,
                review_wakeup_miss_count=0,
                local_review_attempts=0,
                local_review_last_at=NULL,
                next_retry_at=NULL,
                updated_at=excluded.updated_at
            """,
            (
                project_id,
                owner,
                repo,
                branch_name,
                base_branch,
                pr_number if pr_number > 0 else None,
                str(existing.get("pr_url") or ""),
                str(existing.get("pr_title") or ""),
                str(existing.get("pr_body") or ""),
                str(existing.get("pr_state") or "open"),
                1 if bool(existing.get("draft", True)) else 0,
                str(head_sha or existing.get("head_sha") or "").strip(),
                str(project_review_policy(project_cfg).get("trigger") or "manual_comment"),
                review_focus_text(project_cfg, slice_name),
                review_status,
                now,
                now,
                now,
            ),
        )


def persisted_review_runtime_status(project_id: str) -> Optional[str]:
    pr = pull_request_row(project_id) or {}
    loop_stage = review_loop_stage(pr)
    if loop_stage in {
        AWAITING_FIRST_REVIEW_STATUS,
        REVIEW_LIGHT_PENDING_STATUS,
        JURY_REVIEW_PENDING_STATUS,
        JURY_REWORK_REQUIRED_STATUS,
        CORE_RESCUE_PENDING_STATUS,
        MANUAL_HOLD_STATUS,
    }:
        return loop_stage
    review_status = str(pr.get("review_status") or "").strip().lower()
    review_mode = str(pr.get("review_mode") or "github").strip().lower()
    if review_status in {"findings_open", "review_fix_required"}:
        return "review_fix_required"
    if review_status == "review_failed":
        return "review_failed"
    if review_status == LOCAL_REVIEW_PENDING_STATUS:
        return review_hold_status_for_project(project_id, pr_row=pr)
    if review_status in REVIEW_WAITING_STATUSES:
        if review_mode != "github":
            return "review_requested"
        return "review_requested" if int(pr.get("pr_number") or 0) > 0 else "awaiting_pr"
    return None


def review_hold_requested_at(pr_row: Optional[Dict[str, Any]] = None, project_row: Optional[sqlite3.Row] = None) -> Optional[dt.datetime]:
    if pr_row:
        requested = parse_iso(str(pr_row.get("review_requested_at") or ""))
        if requested:
            return requested
        requested = parse_iso(str(pr_row.get("updated_at") or ""))
        if requested:
            return requested
    if project_row is not None:
        requested = parse_iso(project_row["updated_at"]) if "updated_at" in project_row.keys() else None
        if requested:
            return requested
        requested = parse_iso(project_row["last_run_at"]) if "last_run_at" in project_row.keys() else None
        if requested:
            return requested
    return None


def review_stall_fallback_mode(config: Dict[str, Any]) -> str:
    return str(get_policy(config, "review_stall_fallback", "hold") or "hold").strip().lower()


def safe_git_branch_name(text: str) -> str:
    branch = re.sub(r"[^a-zA-Z0-9._/-]+", "-", str(text or "").strip()).strip("-/.")
    return branch or "fleet/project"


def review_branch_name(project_cfg: Dict[str, Any]) -> str:
    review = project_review_policy(project_cfg)
    template = str(review.get("branch_template") or f"fleet/{project_cfg.get('id', 'project')}").strip()
    return safe_git_branch_name(template.replace("{project_id}", str(project_cfg.get("id") or "project")))


def review_focus_text(project_cfg: Dict[str, Any], slice_name: str) -> str:
    review = project_review_policy(project_cfg)
    focus = str(review.get("focus_template") or "").strip()
    if focus:
        return focus
    lower = str(slice_name or "").lower()
    if "contract" in lower or "dto" in lower or "compatibility" in lower:
        return "for contract drift and compatibility regressions"
    if "offline" in lower or "sync" in lower or "stale" in lower:
        return "for offline sync and stale-state hazards"
    return "for regressions and missing tests"


def authenticated_push_url(owner: str, repo: str, token: str) -> str:
    encoded = urllib.parse.quote(token, safe="")
    return f"https://x-access-token:{encoded}@github.com/{owner}/{repo}.git"


def git_head_sha(repo_path: str) -> str:
    result = run_capture(["git", "rev-parse", "HEAD"], cwd=repo_path, timeout_seconds=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git rev-parse HEAD failed")
    return (result.stdout or "").strip()


def git_has_changes(repo_path: str) -> bool:
    result = run_capture(["git", "status", "--porcelain"], cwd=repo_path, timeout_seconds=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return bool((result.stdout or "").strip())


def worktree_entry_fingerprint(repo_path: str, rel_path: str) -> str:
    path = pathlib.Path(repo_path) / rel_path
    if not path.exists():
        return "<deleted>"
    if path.is_symlink():
        return f"symlink:{os.readlink(path)}"
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    stat = path.stat()
    return f"mode:{stat.st_mode}"


def git_dirty_paths(repo_path: str) -> List[str]:
    tracked = run_capture(["git", "diff", "--name-only", "-z", "HEAD", "--"], cwd=repo_path, timeout_seconds=30)
    if tracked.returncode != 0:
        raise RuntimeError(tracked.stderr.strip() or "git diff failed")
    untracked = run_capture(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo_path, timeout_seconds=30)
    if untracked.returncode != 0:
        raise RuntimeError(untracked.stderr.strip() or "git ls-files failed")
    seen: set[str] = set()
    paths: List[str] = []
    for payload in ((tracked.stdout or ""), (untracked.stdout or "")):
        for item in payload.split("\x00"):
            path = item.strip()
            if not path or path in seen:
                continue
            seen.add(path)
            paths.append(path)
    return sorted(paths)


def git_dirty_snapshot(repo_path: str) -> Dict[str, str]:
    return {path: worktree_entry_fingerprint(repo_path, path) for path in git_dirty_paths(repo_path)}


def stage_paths_for_review_commit(repo_path: str, baseline_snapshot: Optional[Dict[str, str]] = None) -> List[str]:
    current_snapshot = git_dirty_snapshot(repo_path)
    if baseline_snapshot is None:
        candidate_paths = sorted(current_snapshot)
    else:
        candidate_paths = sorted(
            path
            for path, fingerprint in current_snapshot.items()
            if baseline_snapshot.get(path) != fingerprint
        )
    if not candidate_paths:
        return []
    add = run_capture(["git", "add", "-A", "--", *candidate_paths], cwd=repo_path, timeout_seconds=60)
    if add.returncode != 0:
        raise RuntimeError(add.stderr.strip() or "git add failed")
    return candidate_paths


def commit_and_push_review_branch(
    project_cfg: Dict[str, Any],
    repo_meta: Dict[str, Any],
    slice_name: str,
    token: str,
    *,
    baseline_snapshot: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    repo_path = str(project_cfg["path"])
    branch = review_branch_name(project_cfg)
    checkout = run_capture(["git", "checkout", "-B", branch], cwd=repo_path, timeout_seconds=60)
    if checkout.returncode != 0:
        raise RuntimeError(checkout.stderr.strip() or "git checkout review branch failed")
    if not git_has_changes(repo_path):
        return {"branch": branch, "head_sha": git_head_sha(repo_path), "changed": False}
    staged_paths = stage_paths_for_review_commit(repo_path, baseline_snapshot=baseline_snapshot)
    if not staged_paths:
        return {"branch": branch, "head_sha": git_head_sha(repo_path), "changed": False}
    commit_message = f"fleet({project_cfg['id']}): {truncate_title(slice_name, 72)}"
    commit = run_capture(
        ["git", "-c", "user.name=Codex Fleet", "-c", "user.email=fleet@local", "commit", "--only", "-m", commit_message, "--", *staged_paths],
        cwd=repo_path,
        timeout_seconds=120,
    )
    combined_output = (commit.stdout or "") + "\n" + (commit.stderr or "")
    if commit.returncode != 0 and "nothing to commit" not in combined_output.lower():
        raise RuntimeError(commit.stderr.strip() or commit.stdout.strip() or "git commit failed")
    head_sha = git_head_sha(repo_path)
    push = run_capture(
        ["git", "push", "-u", authenticated_push_url(repo_meta["owner"], repo_meta["repo"], token), f"HEAD:refs/heads/{branch}"],
        cwd=repo_path,
        timeout_seconds=180,
    )
    if push.returncode != 0:
        raise RuntimeError(push.stderr.strip() or push.stdout.strip() or "git push failed")
    return {"branch": branch, "head_sha": head_sha, "changed": True}


def pull_request_row(project_id: str) -> Optional[Dict[str, Any]]:
    if not table_exists("pull_requests"):
        return None
    with db() as conn:
        row = conn.execute("SELECT * FROM pull_requests WHERE project_id=?", (project_id,)).fetchone()
    return dict(row) if row else None


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
    if review_status == LOCAL_REVIEW_PENDING_STATUS:
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


def review_waiting_rows() -> List[Dict[str, Any]]:
    if not table_exists("pull_requests"):
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM pull_requests
            WHERE review_mode='github'
              AND review_status IN ('queued','requested','awaiting_pr','review_requested')
            ORDER BY review_requested_at ASC, updated_at ASC, project_id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def local_review_waiting_rows() -> List[Dict[str, Any]]:
    if not table_exists("pull_requests"):
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM pull_requests
            WHERE review_mode='local'
              AND review_status IN ('queued','requested','review_requested','local_review')
            ORDER BY review_requested_at ASC, updated_at ASC, project_id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def orphaned_local_review_rows() -> List[Dict[str, Any]]:
    if not table_exists("pull_requests") or not table_exists("projects"):
        return []
    with db() as conn:
        rows = conn.execute(
            """
            SELECT pr.*, p.status AS project_status, p.active_run_id AS project_active_run_id
            FROM pull_requests pr
            JOIN projects p ON p.id = pr.project_id
            WHERE pr.review_status='local_review'
            ORDER BY pr.updated_at ASC, pr.project_id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def review_lane_snapshot(config: Dict[str, Any], *, now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    current = now or utc_now()
    rows = review_waiting_rows()
    oldest_wait_minutes = 0.0
    throttled_count = 0
    for row in rows:
        requested_at = review_hold_requested_at(pr_row=row)
        if requested_at:
            oldest_wait_minutes = max(oldest_wait_minutes, (current - requested_at).total_seconds() / 60.0)
        eta = review_eta_payload(row, cooldown_until=row.get("next_retry_at"), now=current, config=config)
        reset_at = parse_iso(str(eta.get("reset_at") or ""))
        if bool(eta.get("throttled")) and reset_at and reset_at > current:
            throttled_count += 1
    waiting_threshold = max(1, int(get_policy(config, "review_local_fallback_waiting_projects_threshold", 3) or 3))
    oldest_threshold = max(1, int(get_policy(config, "review_local_fallback_oldest_wait_minutes", 45) or 45))
    degraded_reasons: List[str] = []
    if throttled_count > 0:
        degraded_reasons.append("github_throttled")
    if len(rows) >= waiting_threshold:
        degraded_reasons.append("waiting_queue_depth")
    if oldest_wait_minutes >= float(oldest_threshold):
        degraded_reasons.append("oldest_wait_exceeded")
    return {
        "waiting_count": len(rows),
        "throttled_count": throttled_count,
        "oldest_wait_minutes": oldest_wait_minutes,
        "degraded": bool(degraded_reasons),
        "reasons": degraded_reasons,
    }


def active_local_review_run(project_id: str) -> bool:
    if project_id in state.tasks:
        with db() as conn:
            row = conn.execute("SELECT active_run_id FROM projects WHERE id=?", (project_id,)).fetchone()
            if row and row["active_run_id"]:
                run = conn.execute("SELECT job_kind, status, finished_at FROM runs WHERE id=?", (row["active_run_id"],)).fetchone()
                if run and str(run["job_kind"] or "").strip() == "local_review" and not parse_iso(run["finished_at"]):
                    return True
    with db() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM runs
            WHERE project_id=?
              AND job_kind='local_review'
              AND status IN ('starting', 'running')
              AND finished_at IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    return bool(row)


def record_review_wakeup_result(project_id: str, *, still_waiting: bool) -> None:
    if not table_exists("pull_requests"):
        return
    with db() as conn:
        if still_waiting:
            conn.execute(
                """
                UPDATE pull_requests
                SET review_wakeup_miss_count = review_wakeup_miss_count + 1,
                    updated_at=?
                WHERE project_id=?
                """,
                (iso(utc_now()), project_id),
            )
        else:
            conn.execute(
                """
                UPDATE pull_requests
                SET review_wakeup_miss_count = 0,
                    updated_at=?
                WHERE project_id=?
                """,
                (iso(utc_now()), project_id),
            )
            return


def should_launch_local_review_fallback(
    config: Dict[str, Any],
    project_id: str,
    pr_row: Dict[str, Any],
    *,
    now: Optional[dt.datetime] = None,
) -> Optional[str]:
    if not bool(get_policy(config, "review_local_fallback_enabled", True)):
        return None
    if str(pr_row.get("review_status") or "").strip().lower() not in REVIEW_WAITING_STATUSES:
        return None
    if active_local_review_run(project_id):
        return None
    requested_at = review_hold_requested_at(pr_row=pr_row)
    if not requested_at:
        return None
    current = now or utc_now()
    wait_minutes = (current - requested_at).total_seconds() / 60.0
    lane = review_lane_snapshot(config, now=current)
    wait_threshold = max(1, int(get_policy(config, "review_local_fallback_project_wait_minutes", 60) or 60))
    throttled_wait = max(1, int(get_policy(config, "review_local_fallback_throttled_wait_minutes", 1) or 1))
    wakeup_threshold = max(1, int(get_policy(config, "review_local_fallback_wakeup_failures", 2) or 2))
    max_attempts = max(1, int(get_policy(config, "review_local_fallback_max_attempts_per_head", 1) or 1))
    wake_misses = int(pr_row.get("review_wakeup_miss_count") or 0)
    attempts = int(pr_row.get("local_review_attempts") or 0)
    if attempts >= max_attempts:
        return None
    if wake_misses >= wakeup_threshold:
        return f"GitHub review wake-up checks produced no review signal {wake_misses} times"
    if lane.get("throttled_count", 0) > 0 and wait_minutes >= float(throttled_wait):
        return (
            f"GitHub review lane is throttled with {int(lane.get('throttled_count') or 0)} blocked projects "
            f"and this project has waited {human_duration(wait_minutes * 60)}"
        )
    if lane.get("degraded") and lane.get("waiting_count", 0) >= max(1, int(get_policy(config, "review_local_fallback_waiting_projects_threshold", 3) or 3)) and wait_minutes >= float(wait_threshold):
        return (
            f"GitHub review lane is degraded with {int(lane.get('waiting_count') or 0)} waiting projects "
            f"and this project has waited {human_duration(wait_minutes * 60)}"
        )
    return None


def normalize_local_review_findings(findings: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(findings):
        if not isinstance(item, dict):
            continue
        body = str(item.get("body") or item.get("summary") or item.get("message") or "").strip()
        if not body:
            continue
        severity = str(item.get("severity") or "medium").strip().lower()
        if severity not in {"low", "medium", "high"}:
            severity = "medium"
        line_value = item.get("line")
        try:
            line = int(line_value) if line_value not in (None, "", 0) else None
        except Exception:
            line = None
        blocking = bool(item.get("blocking"))
        if severity == "high" and "blocking" not in item:
            blocking = True
        normalized.append(
            {
                "external_id": f"local-review:{idx}",
                "source_kind": "local_review",
                "author_login": "fleet-local-review",
                "review_state": "LOCAL_FALLBACK",
                "path": str(item.get("path") or "").strip(),
                "line": line,
                "body": body,
                "html_url": "",
                "severity": severity,
                "blocking": blocking,
            }
        )
    return normalized


def normalize_local_review_issue_packets(issues: List[Any], *, blocking_default: bool) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(issues):
        if not isinstance(item, dict):
            continue
        issue_id = str(item.get("issue_id") or f"jury-issue:{idx}").strip()
        category = str(item.get("category") or "review").strip()
        severity = str(item.get("severity") or ("high" if blocking_default else "medium")).strip().lower()
        if severity not in {"low", "medium", "high", "blocking"}:
            severity = "high" if blocking_default else "medium"
        blocking = blocking_default or severity in {"high", "blocking"} or bool(item.get("blocking"))
        file_hints = [str(value).strip() for value in item.get("file_hints") or [] if str(value).strip()]
        path = file_hints[0] if file_hints else str(item.get("path") or "").strip()
        evidence = [str(value).strip() for value in item.get("evidence") or [] if str(value).strip()]
        fix_expectation = str(item.get("fix_expectation") or "").strip()
        body_parts = [f"[{category}] {issue_id}"]
        if evidence:
            body_parts.append("; ".join(evidence))
        if fix_expectation:
            body_parts.append(f"Expected fix: {fix_expectation}")
        normalized.append(
            {
                "external_id": issue_id,
                "source_kind": "local_review",
                "author_login": "fleet-local-review",
                "review_state": "LOCAL_FALLBACK",
                "path": path,
                "line": None,
                "body": "\n".join(body_parts),
                "html_url": "",
                "severity": "high" if severity == "blocking" else severity,
                "blocking": blocking,
            }
        )
    return normalized


def parse_local_review_result(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw).strip()
        raw = re.sub(r"\n?```$", "", raw).strip()
    candidates = [raw]
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if match:
        candidates.append(match.group(0))
    payload: Optional[Dict[str, Any]] = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            loaded = json.loads(candidate)
        except Exception:
            continue
        if isinstance(loaded, dict):
            payload = loaded
            break
    if payload is None:
        raise RuntimeError("local review fallback did not return parseable JSON")
    verdict = str(payload.get("verdict") or "").strip().lower()
    blocking_issues = normalize_local_review_issue_packets(list(payload.get("blocking_issues") or []), blocking_default=True)
    non_blocking_issues = normalize_local_review_issue_packets(list(payload.get("non_blocking_issues") or []), blocking_default=False)
    findings = [*blocking_issues, *non_blocking_issues, *normalize_local_review_findings(list(payload.get("findings") or []))]
    if verdict in {"clean", "accepted", "accept"}:
        verdict = "accept"
    elif verdict in {"fix_required", "rework", "retry"}:
        verdict = "rework"
    elif verdict not in {"accept", "rework", "core_rescue_required", "manual_hold"}:
        verdict = "rework" if findings else "accept"
    summary = str(payload.get("summary") or "").strip()
    return {
        "verdict": verdict,
        "summary": summary,
        "findings": findings,
        "blocking_issues": blocking_issues,
        "non_blocking_issues": non_blocking_issues,
        "review_round": int(payload.get("review_round") or 0),
        "confidence": payload.get("confidence"),
        "repeat_issue_ids": [str(item).strip() for item in payload.get("repeat_issue_ids") or [] if str(item).strip()],
        "core_rescue_recommended": bool(payload.get("core_rescue_recommended")),
    }


def build_local_review_prompt(
    project_cfg: Dict[str, Any],
    *,
    slice_name: str,
    base_branch: str,
    review_focus: str,
    reason: str,
    review_round: int = 1,
    max_review_rounds: int = 0,
    review_packet: Optional[Dict[str, Any]] = None,
) -> str:
    instructions = [f"- {item}" for item in prompt_instruction_items(project_cfg)]
    round_line = f"Review round: {review_round}" + (f" of {max_review_rounds}\n" if max_review_rounds > 0 else "\n")
    packet_block = "Compact review packet:\n" + json.dumps(review_packet or {}, indent=2, sort_keys=True) + "\n\n" if review_packet else ""
    prompt = (
        "System re-entry.\n\n"
        "Read from disk before reviewing:\n"
        f"{chr(10).join(instructions)}\n\n"
        "This is a local fallback code review.\n"
        "Do not edit files. Do not run formatters. Do not write to the repository.\n"
        f"Review the current branch against `{base_branch}`.\n"
        f"Current slice: {slice_name}\n"
        f"{round_line}"
        f"Review focus: {review_focus or 'for regressions and missing tests'}\n"
        f"Why local fallback is running: {reason}\n\n"
        f"{packet_block}"
        "Inspect only for actionable problems such as regressions, missing tests, contract drift, boundary violations, or state-safety issues.\n"
        "Return JSON only with this shape:\n"
        "{\n"
        '  "review_round": 1,\n'
        '  "verdict": "accept" | "rework" | "core_rescue_required" | "manual_hold",\n'
        '  "confidence": 0.0,\n'
        '  "summary": "short summary",\n'
        '  "blocking_issues": [\n'
        "    {\n"
        '      "issue_id": "stable-id",\n'
        '      "category": "correctness|tests|contracts|state|review",\n'
        '      "severity": "blocking|high|medium|low",\n'
        '      "file_hints": ["relative/path"],\n'
        '      "evidence": ["actionable evidence"],\n'
        '      "fix_expectation": "short fix request"\n'
        "    }\n"
        "  ],\n"
        '  "non_blocking_issues": [],\n'
        '  "repeat_issue_ids": [],\n'
        '  "core_rescue_recommended": false\n'
        "}\n"
        "If there are no actionable findings, return verdict accept and empty issue lists.\n"
    )
    return apply_codex_prompt_directives(prompt)


def ensure_review_pull_request_record(
    project_cfg: Dict[str, Any],
    repo_meta: Dict[str, Any],
    slice_name: str,
    token: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    branch_info = commit_and_push_review_branch(project_cfg, repo_meta, slice_name, token)
    ensure_pull_request(
        project_cfg,
        repo_meta,
        str(branch_info["branch"]),
        str(branch_info["head_sha"]),
        slice_name,
        token,
    )
    pr_row = pull_request_row(project_cfg["id"])
    if not pr_row:
        raise RuntimeError("unable to create pull request record")
    return branch_info, pr_row


def ensure_pull_request(
    project_cfg: Dict[str, Any],
    repo_meta: Dict[str, Any],
    branch_name: str,
    head_sha: str,
    slice_name: str,
    token: str,
) -> Dict[str, Any]:
    owner = repo_meta["owner"]
    repo = repo_meta["repo"]
    base_branch = repo_meta["base_branch"]
    title = f"[fleet] {project_cfg['id']}: {truncate_title(slice_name, 96)}"
    body = (
        f"Automated fleet review PR for `{project_cfg['id']}`.\n\n"
        f"- Current slice: {slice_name}\n"
        f"- Review lane: GitHub Codex review\n"
        f"- Base branch: `{base_branch}`\n"
    )
    existing_items = github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls", query={"state": "open", "head": f"{owner}:{branch_name}"})
    pr: Dict[str, Any]
    if isinstance(existing_items, list) and existing_items:
        pr_number = int(existing_items[0]["number"])
        pr = github_api_json(token, "PATCH", f"/repos/{owner}/{repo}/pulls/{pr_number}", payload={"title": title, "body": body, "base": base_branch})
    else:
        pr = github_api_json(token, "POST", f"/repos/{owner}/{repo}/pulls", payload={"title": title, "body": body, "head": branch_name, "base": base_branch, "draft": True})

    now = iso(utc_now())
    with db() as conn:
        conn.execute(
            """
            INSERT INTO pull_requests(
                project_id, repo_owner, repo_name, branch_name, base_branch, pr_number, pr_url, pr_title, pr_body, pr_state, draft,
                head_sha, review_mode, review_trigger, review_focus, review_status, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'github', ?, ?, 'queued', ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                repo_owner=excluded.repo_owner,
                repo_name=excluded.repo_name,
                branch_name=excluded.branch_name,
                base_branch=excluded.base_branch,
                pr_number=excluded.pr_number,
                pr_url=excluded.pr_url,
                pr_title=excluded.pr_title,
                pr_body=excluded.pr_body,
                pr_state=excluded.pr_state,
                draft=excluded.draft,
                head_sha=excluded.head_sha,
                updated_at=excluded.updated_at
            """,
            (
                project_cfg["id"],
                owner,
                repo,
                branch_name,
                base_branch,
                int(pr["number"]),
                str(pr.get("html_url") or ""),
                title,
                body,
                str(pr.get("state") or "open"),
                1 if bool(pr.get("draft", True)) else 0,
                head_sha,
                str(project_review_policy(project_cfg).get("trigger") or "manual_comment"),
                review_focus_text(project_cfg, slice_name),
                now,
                now,
            ),
        )
    return {"number": int(pr["number"]), "url": str(pr.get("html_url") or ""), "title": title, "body": body}


def request_github_review(
    project_cfg: Dict[str, Any],
    pr_row: sqlite3.Row,
    token: str,
    head_sha: str,
    *,
    is_retrigger: bool = False,
) -> int:
    owner = str(pr_row["repo_owner"])
    repo = str(pr_row["repo_name"])
    pr_number = int(pr_row["pr_number"])
    pr = ensure_pull_request_ready_for_review(pr_row, token)
    live_head_sha = str(((pr.get("head") or {}).get("sha")) or head_sha or pr_row["head_sha"] or "")
    focus = str(pr_row["review_focus"] or "").strip()
    body = "@codex review" + (f" {focus}" if focus else "")
    response = github_api_json(token, "POST", f"/repos/{owner}/{repo}/issues/{pr_number}/comments", payload={"body": body})
    now = iso(utc_now())
    previous_head_sha = str(pr_row["last_review_head_sha"] or "")
    previous_retrigger_count = int(pr_row["review_retrigger_count"] or 0)
    review_retrigger_count = previous_retrigger_count + 1 if is_retrigger and previous_head_sha == live_head_sha else 0
    last_retrigger_at = now if is_retrigger else None
    with db() as conn:
        conn.execute(
            """
            UPDATE pull_requests
            SET review_status=?,
                pr_url=?,
                pr_state=?,
                draft=?,
                head_sha=?,
                review_requested_at=?,
                review_completed_at=NULL,
                review_findings_count=0,
                review_blocking_findings_count=0,
                last_review_comment_id=?,
                last_review_head_sha=?,
                last_synced_at=?,
                review_sync_failures=0,
                review_retrigger_count=?,
                review_wakeup_miss_count=0,
                local_review_attempts=0,
                local_review_last_at=NULL,
                last_retrigger_at=?,
                next_retry_at=NULL,
                review_rate_limit_reset_at=NULL,
                updated_at=?
            WHERE project_id=?
            """,
            (
                review_hold_status_for_project(project_cfg["id"]),
                str(pr.get("html_url") or pr_row["pr_url"] or ""),
                str(pr.get("state") or pr_row["pr_state"] or "open"),
                1 if bool(pr.get("draft", False)) else 0,
                live_head_sha,
                now,
                str(response.get("id") or ""),
                live_head_sha,
                now,
                review_retrigger_count,
                last_retrigger_at,
                now,
                project_cfg["id"],
            ),
        )
    return int(response.get("id") or 0)


def ensure_pull_request_ready_for_review(
    pr_row: sqlite3.Row | Dict[str, Any],
    token: str,
    *,
    pr: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    owner = str(pr_row["repo_owner"])
    repo = str(pr_row["repo_name"])
    pr_number = int(pr_row["pr_number"])
    live_pr = pr or github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
    if bool(live_pr.get("draft")):
        response = github_graphql_json(
            token,
            """
            mutation($id: ID!) {
              markPullRequestReadyForReview(input: {pullRequestId: $id}) {
                pullRequest {
                  id
                  isDraft
                  url
                  state
                  headRefOid
                }
              }
            }
            """,
            {"id": str(live_pr.get("node_id") or "")},
        )
        updated_pr = ((((response.get("data") or {}).get("markPullRequestReadyForReview") or {}).get("pullRequest")) or {})
        head = dict(live_pr.get("head") or {})
        if str(updated_pr.get("headRefOid") or "").strip():
            head["sha"] = str(updated_pr.get("headRefOid") or "").strip()
        live_pr = {
            **live_pr,
            "draft": bool(updated_pr.get("isDraft", False)),
            "html_url": str(updated_pr.get("url") or live_pr.get("html_url") or ""),
            "state": str(updated_pr.get("state") or live_pr.get("state") or "open"),
            "head": head,
        }
    now = iso(utc_now())
    with db() as conn:
        conn.execute(
            """
            UPDATE pull_requests
            SET pr_url=?,
                pr_state=?,
                draft=?,
                head_sha=?,
                updated_at=?
            WHERE project_id=?
            """,
            (
                str(live_pr.get("html_url") or pr_row["pr_url"] or ""),
                str(live_pr.get("state") or pr_row["pr_state"] or "open"),
                1 if bool(live_pr.get("draft", False)) else 0,
                str(((live_pr.get("head") or {}).get("sha")) or pr_row["head_sha"] or ""),
                now,
                str(pr_row["project_id"]),
            ),
        )
    return live_pr


def upsert_github_review_run(
    project_id: str,
    *,
    slice_name: str,
    pr_number: int,
    pr_url: str,
    review_status: str,
    review_focus: str,
) -> int:
    now = iso(utc_now())
    with db() as conn:
        row = conn.execute(
            "SELECT id FROM runs WHERE project_id=? AND job_kind='github_review' AND slice_name=? AND status IN ('queued','requested','received') ORDER BY id DESC LIMIT 1",
            (project_id, slice_name),
        ).fetchone()
        if row:
            run_id = int(row["id"])
            conn.execute(
                "UPDATE runs SET status=?, decision_reason=?, finished_at=CASE WHEN ? IN ('clean', ?, 'findings_open','failed') THEN ? ELSE finished_at END WHERE id=?",
                (review_status, f"pr #{pr_number} {pr_url} ; focus={review_focus}", review_status, REVIEW_FALLBACK_CLEAN_STATUS, now, run_id),
            )
            return run_id
        cur = conn.execute(
            """
            INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, decision_reason, started_at)
            VALUES (?, 'github', 'github_review', ?, ?, ?, ?, ?)
            """,
            (project_id, slice_name, review_status, GITHUB_REVIEW_MODEL, f"pr #{pr_number} {pr_url} ; focus={review_focus}", now),
        )
        return int(cur.lastrowid)


def complete_stalled_review_fallback(
    config: Dict[str, Any],
    project_id: str,
    pr_row: Dict[str, Any],
) -> bool:
    if review_stall_fallback_mode(config) not in {"complete", "complete_slice", "auto_advance"}:
        return False
    if current_pr_check_incident(project_id, head_sha=str(pr_row.get("head_sha") or "")):
        return False
    project_cfg = get_project_cfg(config, project_id)
    with db() as conn:
        project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project_row:
        return False
    if str(project_row["status"] or "").strip().lower() == "review_fix_required":
        return False
    slice_name = current_slice(project_row) or str(project_row["current_slice"] or "").strip() or f"Review {project_id}"
    now = utc_now()
    with db() as conn:
        conn.execute(
            """
            UPDATE pull_requests
            SET review_status=?,
                review_completed_at=?,
                review_findings_count=0,
                review_blocking_findings_count=0,
                next_retry_at=NULL,
                last_synced_at=?,
                updated_at=?
            WHERE project_id=?
            """,
            (REVIEW_FALLBACK_CLEAN_STATUS, iso(now), iso(now), iso(now), project_id),
        )
    upsert_github_review_run(
        project_id,
        slice_name=slice_name,
        pr_number=int(pr_row.get("pr_number") or 0),
        pr_url=str(pr_row.get("pr_url") or ""),
        review_status=REVIEW_FALLBACK_CLEAN_STATUS,
        review_focus=f"{str(pr_row.get('review_focus') or '')} ; fallback=review_sync_stalled".strip(),
    )
    complete_project_slice_after_review(project_cfg, now)
    return True


def looks_like_codex_login(login: str, bot_logins: List[str]) -> bool:
    lower = str(login or "").strip().lower()
    if not lower:
        return False
    wanted = {str(item or "").strip().lower() for item in bot_logins if str(item or "").strip()}
    if lower in wanted:
        return True
    return "codex" in lower


def review_comment_is_request(body: str) -> bool:
    return str(body or "").strip().lower().startswith("@codex review")


def review_finding_severity(body: str) -> Tuple[str, bool]:
    lower = str(body or "").lower()
    blocking = any(
        marker in lower
        for marker in [
            "p0",
            "p1",
            "blocking",
            "must fix",
            "regression",
            "missing test",
            "contract drift",
            "compatibility",
            "duplicate source of truth",
        ]
    )
    if blocking:
        return "high", True
    if any(marker in lower for marker in ["p2", "risk", "should", "warning"]):
        return "medium", False
    return "medium", False


def github_failed_check_runs(token: str, owner: str, repo: str, head_sha: str) -> List[Dict[str, Any]]:
    if not head_sha:
        return []
    response = github_api_json(
        token,
        "GET",
        f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
        query={"per_page": 100},
    )
    runs = response.get("check_runs") if isinstance(response, dict) else []
    failed_conclusions = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
    failed: List[Dict[str, Any]] = []
    for item in runs if isinstance(runs, list) else []:
        status = str(item.get("status") or "").strip().lower()
        conclusion = str(item.get("conclusion") or "").strip().lower()
        if status != "completed" or conclusion not in failed_conclusions:
            continue
        failed.append(
            {
                "id": item.get("id"),
                "name": str(item.get("name") or "").strip(),
                "status": status,
                "conclusion": conclusion,
                "html_url": str(item.get("html_url") or "").strip(),
                "started_at": item.get("started_at"),
                "completed_at": item.get("completed_at"),
                "app": str(((item.get("app") or {}).get("name")) or "").strip(),
            }
        )
    return failed


def sync_pr_check_incident(project_id: str, *, pr_url: str, head_sha: str, failed_checks: List[Dict[str, Any]]) -> None:
    if failed_checks:
        config = normalize_config()
        names = [str(item.get("name") or "").strip() for item in failed_checks[:3] if str(item.get("name") or "").strip()]
        summary = "GitHub pull request checks failed for the current review head."
        if names:
            summary += f" Failing checks: {', '.join(names)}."
        open_or_update_incident(
            scope_type="project",
            scope_id=project_id,
            incident_kind=PR_CHECKS_FAILED_INCIDENT_KIND,
            severity="critical",
            title=f"{project_id} PR checks failed",
            summary=summary,
            context={
                "project_id": project_id,
                "pr_url": pr_url,
                "head_sha": head_sha,
                "failed_checks": failed_checks,
                "can_resolve": auto_heal_category_enabled(config, "review", project_id=project_id),
                "operator_required": False,
            },
        )
        return
    resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[PR_CHECKS_FAILED_INCIDENT_KIND])


def promote_review_fix_candidate(
    config: Dict[str, Any],
    project_id: str,
    row: sqlite3.Row,
    runtime_status: str,
    queue: List[str],
    queue_index: int,
) -> Tuple[str, bool]:
    normalized_status = str(runtime_status or "").strip().lower()
    if normalized_status != "review_fix_required":
        return runtime_status, False
    review_incident = current_pr_check_incident(project_id, head_sha=str((pull_request_row(project_id) or {}).get("head_sha") or ""))
    if not review_incident or not auto_heal_category_enabled(config, "review", project_id=project_id):
        return runtime_status, False
    promoted_status = "review_fix_required"
    current_slice = normalize_slice_text(queue[queue_index]) if queue_index < len(queue) else None
    update_project_status(
        project_id,
        status=promoted_status,
        current_slice=current_slice,
        active_run_id=None,
        cooldown_until=None,
        last_run_at=parse_iso(row["last_run_at"]),
        last_error=row["last_error"],
        consecutive_failures=row["consecutive_failures"],
        spider_tier=row["spider_tier"],
        spider_model=row["spider_model"],
        spider_reason=row["spider_reason"],
    )
    if table_exists("pull_requests"):
        with db() as conn:
            conn.execute(
                """
                UPDATE pull_requests
                SET review_status='review_fix_required',
                    review_completed_at=COALESCE(review_completed_at, ?),
                    next_retry_at=NULL,
                    updated_at=?
                WHERE project_id=?
                """,
                (iso(utc_now()), iso(utc_now()), project_id),
            )
    return promoted_status, True


def sync_review_findings(project_id: str, pr_number: int, findings: List[Dict[str, Any]]) -> None:
    now = iso(utc_now())
    current_ids = {str(item["external_id"]) for item in findings if str(item.get("external_id") or "").strip()}
    with db() as conn:
        for item in findings:
            conn.execute(
                """
                INSERT INTO review_findings(project_id, pr_number, external_id, source_kind, author_login, review_state, path, line, body, html_url, severity, blocking, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, pr_number, external_id) DO UPDATE SET
                    source_kind=excluded.source_kind,
                    author_login=excluded.author_login,
                    review_state=excluded.review_state,
                    path=excluded.path,
                    line=excluded.line,
                    body=excluded.body,
                    html_url=excluded.html_url,
                    severity=excluded.severity,
                    blocking=excluded.blocking,
                    updated_at=excluded.updated_at
                """,
                (
                    project_id,
                    pr_number,
                    str(item["external_id"]),
                    str(item.get("source_kind") or "comment"),
                    str(item.get("author_login") or ""),
                    str(item.get("review_state") or ""),
                    str(item.get("path") or ""),
                    int(item.get("line") or 0) if item.get("line") is not None else None,
                    str(item.get("body") or ""),
                    str(item.get("html_url") or ""),
                    str(item.get("severity") or "medium"),
                    1 if bool(item.get("blocking")) else 0,
                    now,
                    now,
                ),
            )
        if current_ids:
            placeholders = ", ".join("?" for _ in current_ids)
            conn.execute(
                f"DELETE FROM review_findings WHERE project_id=? AND pr_number=? AND external_id NOT IN ({placeholders})",
                (project_id, pr_number, *sorted(current_ids)),
            )
        else:
            conn.execute("DELETE FROM review_findings WHERE project_id=? AND pr_number=?", (project_id, pr_number))


def publish_review_feedback(project_cfg: Dict[str, Any], pr_url: str, findings: List[Dict[str, Any]]) -> Optional[pathlib.Path]:
    if not findings:
        return None
    feedback_dir = pathlib.Path(project_cfg["path"]) / str(project_cfg.get("feedback_dir") or "feedback")
    feedback_dir.mkdir(parents=True, exist_ok=True)
    path = feedback_dir / f"{utc_now().strftime('%Y-%m-%d')}-github-review-pr.md"
    lines = ["# GitHub Codex Review", "", f"PR: {pr_url}", "", "Findings:"]
    for item in findings:
        body = str(item.get("body") or "").strip()
        location = []
        if item.get("path"):
            location.append(str(item["path"]))
        if item.get("line"):
            location.append(f"line {item['line']}")
        prefix = f"- [{str(item.get('severity') or 'medium')}]"
        if location:
            prefix += f" {' : '.join(location)}"
        lines.append(f"{prefix} {body}")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def publish_pr_check_feedback(project_cfg: Dict[str, Any], pr_url: str, failed_checks: List[Dict[str, Any]]) -> Optional[pathlib.Path]:
    if not failed_checks:
        return None
    feedback_dir = pathlib.Path(project_cfg["path"]) / str(project_cfg.get("feedback_dir") or "feedback")
    feedback_dir.mkdir(parents=True, exist_ok=True)
    path = feedback_dir / f"{utc_now().strftime('%Y-%m-%d')}-github-checks-pr.md"
    lines = ["# GitHub PR Check Failures", "", f"PR: {pr_url}", "", "Failing checks:"]
    for item in failed_checks:
        label = str(item.get("name") or "").strip() or "unnamed-check"
        conclusion = str(item.get("conclusion") or "").strip() or "failure"
        url = str(item.get("html_url") or "").strip()
        lines.append(f"- {label} ({conclusion})" + (f" - {url}" if url else ""))
    lines.extend(["", "Repair the failing checks before advancing the queue."])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def complete_project_slice_after_review(project_cfg: Dict[str, Any], finished_at: dt.datetime) -> None:
    project_id = project_cfg["id"]
    increment_queue(project_id)
    with db() as conn:
        row = conn.execute("SELECT queue_json, queue_index FROM projects WHERE id=?", (project_id,)).fetchone()
    queue = json.loads(row["queue_json"] or "[]")
    idx = int(row["queue_index"])
    next_status = "complete" if idx >= len(queue) else READY_STATUS
    next_slice = normalize_slice_text(queue[idx]) if idx < len(queue) else None
    update_project_status(
        project_id,
        status=next_status,
        current_slice=next_slice,
        active_run_id=None,
        cooldown_until=utc_now() + dt.timedelta(seconds=1),
        last_run_at=finished_at,
        last_error=None,
    )


def project_runtime_update_snapshot(project_id: str) -> Dict[str, Any]:
    with db() as conn:
        row = conn.execute(
            """
            SELECT status, current_slice, active_run_id, cooldown_until, last_run_at, last_error,
                   consecutive_failures, spider_tier, spider_model, spider_reason
            FROM projects
            WHERE id=?
            """,
            (project_id,),
        ).fetchone()
        if not row:
            return {}
        active_run = None
        if row["active_run_id"]:
            active_run = conn.execute(
                "SELECT status, finished_at FROM runs WHERE id=?",
                (row["active_run_id"],),
            ).fetchone()
    snapshot = dict(row)
    runtime_status = str(snapshot.get("status") or "").strip()
    if snapshot.get("active_run_id"):
        snapshot["has_active_runtime"] = bool(
            active_run
            and str(active_run["status"] or "").strip() in {"starting", "running", "verifying"}
            and not parse_iso(active_run["finished_at"])
        )
    else:
        snapshot["has_active_runtime"] = runtime_status in {"starting", "running", "verifying"}
    return snapshot


def sync_github_review_state(config: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    project_cfg = get_project_cfg(config, project_id)
    pr_row = pull_request_row(project_id)
    if not pr_row:
        raise RuntimeError(f"no pull request record for {project_id}")
    token = github_token()
    if not token:
        raise RuntimeError("GitHub auth token is unavailable inside fleet")
    owner = str(pr_row["repo_owner"])
    repo = str(pr_row["repo_name"])
    pr_number = int(pr_row["pr_number"])
    requested_at = review_hold_requested_at(pr_row=pr_row) or utc_now()
    bot_logins = list(project_review_policy(project_cfg).get("bot_logins") or ["codex"])

    pr = github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
    review_trigger = str(pr_row.get("review_trigger") or "").strip().lower()
    review_status = str(pr_row.get("review_status") or "").strip().lower()
    if review_trigger == "manual_comment" and review_status in REVIEW_WAITING_STATUSES and bool(pr.get("draft")):
        pr = ensure_pull_request_ready_for_review(pr_row, token, pr=pr)
        refreshed_pr_row = pull_request_row(project_id)
        if refreshed_pr_row:
            pr_row = refreshed_pr_row
        head_sha = str(((pr.get("head") or {}).get("sha")) or pr_row["head_sha"] or "")
        request_github_review(project_cfg, pr_row, token, head_sha, is_retrigger=True)
        refreshed_pr_row = pull_request_row(project_id)
        if refreshed_pr_row:
            pr_row = refreshed_pr_row
            requested_at = review_hold_requested_at(pr_row=pr_row) or utc_now()
    head_sha = str(pr.get("head", {}).get("sha") or pr_row["head_sha"] or "")
    pr_url = str(pr.get("html_url") or pr_row["pr_url"] or "")
    reviews = github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")
    review_comments = github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/comments")
    issue_comments = github_api_json(token, "GET", f"/repos/{owner}/{repo}/issues/{pr_number}/comments")
    failed_checks = github_failed_check_runs(token, owner, repo, head_sha)

    codex_reviews = [
        item for item in (reviews if isinstance(reviews, list) else [])
        if looks_like_codex_login(((item.get("user") or {}).get("login") or ""), bot_logins)
        and (parse_iso(item.get("submitted_at")) or utc_now()) >= requested_at
    ]
    codex_review_comments = [
        item for item in (review_comments if isinstance(review_comments, list) else [])
        if looks_like_codex_login(((item.get("user") or {}).get("login") or ""), bot_logins)
        and (parse_iso(item.get("created_at")) or utc_now()) >= requested_at
    ]
    codex_issue_comments = [
        item for item in (issue_comments if isinstance(issue_comments, list) else [])
        if looks_like_codex_login(((item.get("user") or {}).get("login") or ""), bot_logins)
        and not review_comment_is_request(item.get("body") or "")
        and (parse_iso(item.get("created_at")) or utc_now()) >= requested_at
    ]

    findings: List[Dict[str, Any]] = []
    for item in codex_review_comments:
        severity, blocking = review_finding_severity(str(item.get("body") or ""))
        findings.append(
            {
                "external_id": f"review-comment:{item.get('id')}",
                "source_kind": "pull_request_comment",
                "author_login": ((item.get("user") or {}).get("login") or ""),
                "review_state": "",
                "path": item.get("path"),
                "line": item.get("line") or item.get("original_line"),
                "body": str(item.get("body") or ""),
                "html_url": item.get("html_url"),
                "severity": severity,
                "blocking": blocking,
            }
        )
    for item in codex_issue_comments:
        severity, blocking = review_finding_severity(str(item.get("body") or ""))
        findings.append(
            {
                "external_id": f"issue-comment:{item.get('id')}",
                "source_kind": "issue_comment",
                "author_login": ((item.get("user") or {}).get("login") or ""),
                "review_state": "",
                "path": "",
                "line": None,
                "body": str(item.get("body") or ""),
                "html_url": item.get("html_url"),
                "severity": severity,
                "blocking": blocking,
            }
        )
    for item in codex_reviews:
        state = str(item.get("state") or "").strip().upper()
        body = str(item.get("body") or "").strip()
        if state == "APPROVED" and not body:
            continue
        severity, blocking = review_finding_severity(body)
        blocking = blocking or state == "CHANGES_REQUESTED"
        if body:
            findings.append(
                {
                    "external_id": f"review:{item.get('id')}",
                    "source_kind": "review",
                    "author_login": ((item.get("user") or {}).get("login") or ""),
                    "review_state": state,
                    "path": "",
                    "line": None,
                    "body": body,
                    "html_url": item.get("html_url"),
                    "severity": "high" if blocking else severity,
                    "blocking": blocking,
                }
            )

    waiting_status = review_hold_status_for_project(project_id)
    review_artifacts_present = bool(codex_reviews or codex_review_comments or codex_issue_comments)
    blocking_count = sum(1 for item in findings if bool(item.get("blocking")))
    sync_review_findings(project_id, pr_number, findings)
    sync_pr_check_incident(project_id, pr_url=pr_url, head_sha=head_sha, failed_checks=failed_checks)
    now = iso(utc_now())
    persisted_review_status = (
        "findings_open"
        if findings
        else ("review_fix_required" if failed_checks else ("clean" if review_artifacts_present else waiting_status))
    )
    with db() as conn:
        conn.execute(
            """
            UPDATE pull_requests
            SET pr_url=?, pr_state=?, draft=?, head_sha=?, review_status=?, review_completed_at=?, review_findings_count=?, review_blocking_findings_count=?, last_synced_at=?, review_sync_failures=0, review_wakeup_miss_count=0, next_retry_at=NULL, review_rate_limit_reset_at=NULL, updated_at=?
            WHERE project_id=?
            """,
            (
                pr_url,
                str(pr.get("state") or "open"),
                1 if bool(pr.get("draft", True)) else 0,
                head_sha,
                persisted_review_status,
                now if (review_artifacts_present or failed_checks) else None,
                len(findings),
                blocking_count,
                now,
                now,
                project_id,
            ),
        )
    project_row = project_runtime_update_snapshot(project_id)

    if findings:
        upsert_github_review_run(
            project_id,
            slice_name=str((pr_row["pr_title"] or project_cfg.get("id") or "").strip()),
            pr_number=pr_number,
            pr_url=pr_url,
            review_status="findings_open",
            review_focus=str(pr_row["review_focus"] or ""),
        )
        publish_review_feedback(project_cfg, pr_url, findings)
        project_row = project_runtime_update_snapshot(project_id)
        if not bool(project_row.get("has_active_runtime")):
            update_project_status(
                project_id,
                status="review_fix_required",
                current_slice=review_slice_name(project_id, fallback=str((project_row.get("current_slice") if project_row else "") or "")),
                active_run_id=None,
                cooldown_until=utc_now() + dt.timedelta(seconds=1),
                last_run_at=utc_now(),
                last_error="github review findings published for follow-up",
                spider_tier=project_row.get("spider_tier") if project_row else None,
                spider_model=project_row.get("spider_model") if project_row else None,
                spider_reason=project_row.get("spider_reason") if project_row else None,
            )
    elif failed_checks:
        upsert_github_review_run(
            project_id,
            slice_name=str((pr_row["pr_title"] or project_cfg.get("id") or "").strip()),
            pr_number=pr_number,
            pr_url=pr_url,
            review_status="failed",
            review_focus=str(pr_row["review_focus"] or ""),
        )
        publish_pr_check_feedback(project_cfg, pr_url, failed_checks)
        project_row = project_runtime_update_snapshot(project_id)
        if not bool(project_row.get("has_active_runtime")):
            update_project_status(
                project_id,
                status="review_fix_required",
                current_slice=review_slice_name(project_id, fallback=str((project_row.get("current_slice") if project_row else "") or "")),
                active_run_id=None,
                cooldown_until=utc_now() + dt.timedelta(seconds=1),
                last_run_at=utc_now(),
                last_error="github pull request checks failed for the current review head",
                spider_tier=project_row.get("spider_tier") if project_row else None,
                spider_model=project_row.get("spider_model") if project_row else None,
                spider_reason=project_row.get("spider_reason") if project_row else None,
            )
        return {
            "pr_number": pr_number,
            "pr_url": pr_url,
            "review_status": "review_fix_required",
            "review_findings_count": len(findings),
            "review_blocking_findings_count": blocking_count,
        }
    elif review_artifacts_present:
        upsert_github_review_run(
            project_id,
            slice_name=str((pr_row["pr_title"] or project_cfg.get("id") or "").strip()),
            pr_number=pr_number,
            pr_url=pr_url,
            review_status="clean",
            review_focus=str(pr_row["review_focus"] or ""),
        )
        project_row = project_runtime_update_snapshot(project_id)
        if not bool(project_row.get("has_active_runtime")):
            complete_project_slice_after_review(project_cfg, utc_now())
    else:
        project_row = project_runtime_update_snapshot(project_id)
        if not bool(project_row.get("has_active_runtime")):
            update_project_status(
                project_id,
                status=waiting_status,
                current_slice=review_slice_name(project_id, fallback=str((project_row.get("current_slice") if project_row else "") or "")),
                active_run_id=None,
                cooldown_until=None,
                last_run_at=utc_now(),
                last_error=None,
                spider_tier=project_row.get("spider_tier") if project_row else None,
                spider_model=project_row.get("spider_model") if project_row else None,
                spider_reason=project_row.get("spider_reason") if project_row else None,
            )

    return {
        "pr_number": pr_number,
        "pr_url": pr_url,
        "review_status": persisted_review_status,
        "review_findings_count": len(findings),
        "review_blocking_findings_count": blocking_count,
    }


def sync_pending_github_reviews(config: Dict[str, Any]) -> None:
    if not table_exists("pull_requests"):
        return
    now = utc_now()
    poll_cutoff = now - dt.timedelta(seconds=max(30, int(get_policy(config, "review_poll_interval_seconds", 180) or 180)))
    with db() as conn:
        rows = conn.execute(
            """
            SELECT project_id, review_status, review_sync_failures, next_retry_at
            FROM pull_requests
            WHERE review_mode='github'
              AND (
                (
                  review_status IN ('queued','requested','awaiting_pr','review_requested')
                  AND (next_retry_at IS NULL OR next_retry_at <= ?)
                  AND (last_synced_at IS NULL OR last_synced_at <= ?)
                )
                OR (review_status='failed' AND (next_retry_at IS NULL OR next_retry_at <= ?))
              )
            ORDER BY updated_at ASC, project_id ASC
            """
        , (iso(now), iso(poll_cutoff), iso(now))).fetchall()
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id or project_id in state.tasks:
            continue
        scheduled_retry = bool(row["next_retry_at"])
        try:
            sync_github_review_state(config, project_id)
            if scheduled_retry:
                refreshed = pull_request_row(project_id) or {}
                still_waiting = str(refreshed.get("review_status") or "").strip().lower() in REVIEW_WAITING_STATUSES
                record_review_wakeup_result(project_id, still_waiting=still_waiting)
        except Exception as exc:
            failures = int(row["review_sync_failures"] or 0) + 1
            reset_at = exc.reset_at if isinstance(exc, GitHubRateLimitError) else None
            if reset_at is not None:
                apply_global_review_rate_limit(reset_at, error_text=str(exc))
                continue
            backoff_base = int(get_policy(config, "rate_limit_backoff_base", 60))
            backoff_seconds = backoff_base * min(16, 2 ** max(0, failures - 1))
            retry_at = utc_now() + dt.timedelta(seconds=backoff_seconds)
            transient = is_transient_review_failure(str(exc))
            if transient:
                pr_row = pull_request_row(project_id)
                max_retriggers = max(0, get_int_policy(config, "max_review_retriggers_per_head", 3))
                if (
                    pr_row
                    and review_stall_fallback_mode(config) in {"complete", "complete_slice", "auto_advance"}
                    and review_request_stalled(project_id)
                    and max_retriggers <= 0
                ):
                    complete_stalled_review_fallback(config, project_id, pr_row)
                    continue
            review_status = review_hold_status_for_project(project_id) if transient else "review_failed"
            with db() as conn:
                conn.execute(
                    """
                    UPDATE pull_requests
                    SET review_status=?,
                        review_sync_failures=?,
                        next_retry_at=?,
                        review_rate_limit_reset_at=NULL,
                        last_synced_at=?,
                        updated_at=?
                    WHERE project_id=?
                    """,
                    (review_status, failures, iso(retry_at), iso(utc_now()), iso(utc_now()), project_id),
                )
            update_project_status(
                project_id,
                status=review_status,
                current_slice=None,
                active_run_id=None,
                cooldown_until=retry_at,
                last_run_at=utc_now(),
                last_error=str(exc),
            )


def apply_global_review_rate_limit(reset_at: dt.datetime, *, error_text: str = "") -> None:
    wake_at = max(reset_at, utc_now()) + dt.timedelta(minutes=5)
    message = f"GitHub review sync throttled until {iso(reset_at)}; spider wake-up check at {iso(wake_at)}"
    with db() as conn:
        rows = conn.execute(
            """
            SELECT pr.project_id, p.current_slice
            FROM pull_requests pr
            LEFT JOIN projects p ON p.id = pr.project_id
            WHERE review_mode='github'
              AND review_status IN ('queued','requested','awaiting_pr','review_requested')
            """
        ).fetchall()
        conn.execute(
            """
            UPDATE pull_requests
            SET review_rate_limit_reset_at=?,
                next_retry_at=?,
                updated_at=?
            WHERE review_mode='github'
              AND review_status IN ('queued','requested','awaiting_pr','review_requested')
            """,
            (iso(reset_at), iso(wake_at), iso(utc_now())),
        )
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id:
            continue
        slice_name = str(row["current_slice"] or "").strip() or review_slice_name(project_id)
        update_project_status(
            project_id,
            status=review_hold_status_for_project(project_id),
            current_slice=slice_name,
            active_run_id=None,
            cooldown_until=wake_at,
            last_run_at=utc_now(),
            last_error=message if error_text else message,
        )


def defer_review_sync_due_to_rate_limit(project_id: str, exc: "GitHubRateLimitError") -> Dict[str, Any]:
    reset_at = exc.reset_at or (utc_now() + dt.timedelta(minutes=5))
    apply_global_review_rate_limit(reset_at, error_text=str(exc))
    pr_row = pull_request_row(project_id) or {}
    config = normalize_config()
    project_cfg = get_project_cfg(config, project_id)
    with db() as conn:
        project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    slice_name = ""
    if project_row:
        slice_name = current_slice(project_row) or ""
    return {
        "project_id": project_id,
        "review_status": review_hold_status_for_project(project_id),
        "pr_number": int(pr_row.get("pr_number") or 0),
        "pr_url": str(pr_row.get("pr_url") or ""),
        "slice_name": slice_name or review_slice_name(project_id) or f"Review {project_id}",
        "review_mode": str(project_review_policy(project_cfg).get("mode") or "github"),
        "deferred": True,
        "healing": True,
        "reason": str(exc),
        "retry_at": str(pr_row.get("next_retry_at") or ""),
        "review_eta": review_eta_payload(pr_row, cooldown_until=pr_row.get("next_retry_at")),
    }


def launch_local_review_fallback(
    config: Dict[str, Any],
    project_id: str,
    pr_row: Dict[str, Any],
    *,
    reason: str,
) -> bool:
    existing_task = state.tasks.get(project_id)
    if existing_task is not None:
        done = False
        try:
            done = bool(existing_task.done())
        except Exception:
            done = False
        if done:
            state.tasks.pop(project_id, None)
        else:
            return False
    with db() as conn:
        project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project_row:
        return False
    project_cfg = get_project_cfg(config, project_id)
    coroutine = execute_local_review_fallback(
        config,
        project_cfg,
        project_row,
        pr_row,
        reason=reason,
    )
    loop = state.controller_loop
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None
    if running_loop is not None and running_loop is loop:
        task = asyncio.create_task(coroutine)
    elif loop and loop.is_running():
        task = asyncio.run_coroutine_threadsafe(coroutine, loop)
    else:
        coroutine.close()
        return False
    state.tasks[project_id] = task
    return True


def pending_pull_request_request_stalled(config: Dict[str, Any], project_row: sqlite3.Row, *, now: Optional[dt.datetime] = None) -> bool:
    if pull_request_row(str(project_row["id"] or "").strip()):
        return False
    status = str(project_row["status"] or "").strip().lower()
    if status != "awaiting_pr":
        return False
    requested_at = review_hold_requested_at(project_row=project_row)
    if not requested_at:
        return False
    current = now or utc_now()
    stall_minutes = int(get_policy(config, "review_stall_sla_minutes", 10))
    return requested_at <= current - dt.timedelta(minutes=max(1, stall_minutes))


def heal_pending_pull_request_reviews(config: Dict[str, Any]) -> None:
    if not table_exists("projects"):
        return
    now = utc_now()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM projects
            WHERE status='awaiting_pr'
            ORDER BY updated_at ASC, id ASC
            """
        ).fetchall()
    for row in rows:
        project_id = str(row["id"] or "").strip()
        if not project_id or project_id in state.tasks or not pending_pull_request_request_stalled(config, row, now=now):
            continue
        project_cfg = get_project_cfg(config, project_id)
        review = project_review_policy(project_cfg)
        if not bool(review.get("enabled", True)) or str(review.get("mode") or "github").strip().lower() != "github":
            continue
        try:
            request_project_github_review_now(project_id)
        except HTTPException as exc:
            message = str(exc.detail)
            if is_transient_review_failure(message):
                continue
            update_project_status(
                project_id,
                status="review_failed",
                current_slice=current_slice(row),
                active_run_id=None,
                cooldown_until=None,
                last_run_at=utc_now(),
                last_error=message,
                consecutive_failures=row["consecutive_failures"],
                spider_tier=row["spider_tier"],
                spider_model=row["spider_model"],
                spider_reason=row["spider_reason"],
            )
        except Exception as exc:
            message = str(exc)
            if is_transient_review_failure(message):
                continue
            update_project_status(
                project_id,
                status="review_failed",
                current_slice=current_slice(row),
                active_run_id=None,
                cooldown_until=None,
                last_run_at=utc_now(),
                last_error=message,
                consecutive_failures=row["consecutive_failures"],
                spider_tier=row["spider_tier"],
                spider_model=row["spider_model"],
                spider_reason=row["spider_reason"],
            )


def heal_stalled_github_reviews(config: Dict[str, Any]) -> None:
    if not auto_heal_category_enabled(config, "review") or not table_exists("pull_requests"):
        return
    now = utc_now()
    with db() as conn:
        rows = conn.execute(
            """
            SELECT project_id, head_sha, last_review_head_sha, review_retrigger_count
            FROM pull_requests
            WHERE review_mode='github'
              AND review_status IN ('queued','requested','review_requested')
            ORDER BY updated_at ASC, project_id ASC
            """
        ).fetchall()
    max_retriggers = max(0, get_int_policy(config, "max_review_retriggers_per_head", 3))
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id:
            continue
        pr_row = pull_request_row(project_id)
        if not pr_row:
            continue
        local_review_reason = should_launch_local_review_fallback(config, project_id, pr_row, now=now)
        if local_review_reason and launch_local_review_fallback(config, project_id, pr_row, reason=local_review_reason):
            continue
        if not review_request_stalled(project_id, now=now):
            continue
        if str(pr_row.get("review_trigger") or "").strip().lower() != "manual_comment":
            continue
        if max_retriggers <= 0:
            complete_stalled_review_fallback(config, project_id, pr_row)
            continue
        token = github_token()
        if not token:
            continue
        current_head_sha = str(row["head_sha"] or pr_row.get("head_sha") or "")
        last_review_head_sha = str(row["last_review_head_sha"] or pr_row.get("last_review_head_sha") or "")
        retrigger_count = int(row["review_retrigger_count"] or pr_row.get("review_retrigger_count") or 0)
        if current_head_sha and current_head_sha == last_review_head_sha and retrigger_count >= max_retriggers:
            complete_stalled_review_fallback(config, project_id, pr_row)
            continue
        try:
            request_github_review(
                get_project_cfg(config, project_id),
                pr_row,
                token,
                str(pr_row.get("head_sha") or ""),
                is_retrigger=True,
            )
        except Exception:
            if max_retriggers <= 0:
                complete_stalled_review_fallback(config, project_id, pr_row)
                continue
            if current_head_sha and current_head_sha == last_review_head_sha and (retrigger_count + 1) >= max_retriggers:
                complete_stalled_review_fallback(config, project_id, pr_row)
            continue


def heal_orphaned_local_reviews(config: Dict[str, Any]) -> int:
    healed = 0
    for pr_row in orphaned_local_review_rows():
        project_id = str(pr_row.get("project_id") or "").strip()
        if not project_id:
            continue
        task = state.tasks.get(project_id)
        if task is not None:
            done = False
            try:
                done = bool(task.done())
            except Exception:
                done = False
            if not done:
                continue
            state.tasks.pop(project_id, None)
        if active_local_review_run(project_id):
            continue
        project_status = str(pr_row.get("project_status") or "").strip().lower()
        if project_status in {"starting", "running", "verifying"} or pr_row.get("project_active_run_id"):
            continue
        project_cfg = get_project_cfg(config, project_id)
        review_mode = str(project_review_policy(project_cfg).get("mode") or "github").strip().lower()
        if review_mode == "local":
            try:
                result = request_project_local_review_now(project_id)
            except HTTPException:
                continue
            if bool(result.get("launched")):
                healed += 1
            continue
        if launch_local_review_fallback(config, project_id, pr_row, reason="resume pending local review fallback after interrupted controller task"):
            healed += 1
    return healed


def pull_request_rows() -> Dict[str, Dict[str, Any]]:
    if not table_exists("pull_requests"):
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM pull_requests ORDER BY project_id").fetchall()
    return {str(row["project_id"]): dict(row) for row in rows}


def review_findings_summary() -> Dict[str, Dict[str, int]]:
    if not table_exists("review_findings"):
        return {}
    with db() as conn:
        rows = conn.execute(
            """
            SELECT project_id, COUNT(*) AS finding_count, COALESCE(SUM(blocking), 0) AS blocking_count
            FROM review_findings
            GROUP BY project_id
            """
        ).fetchall()
    return {
        str(row["project_id"]): {
            "count": int(row["finding_count"] or 0),
            "blocking_count": int(row["blocking_count"] or 0),
        }
        for row in rows
    }


def incident_rows(
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


def open_or_update_incident(
    *,
    scope_type: str,
    scope_id: str,
    incident_kind: str,
    severity: str,
    title: str,
    summary: str,
    context: Optional[Dict[str, Any]] = None,
) -> int:
    now = iso(utc_now()) or ""
    context_json = json.dumps(context or {}, sort_keys=True)
    with db() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM incidents
            WHERE scope_type=? AND scope_id=? AND incident_kind=? AND status='open'
            ORDER BY id DESC
            LIMIT 1
            """,
            (scope_type, scope_id, incident_kind),
        ).fetchone()
        if row:
            incident_id = int(row["id"])
            conn.execute(
                """
                UPDATE incidents
                SET severity=?, title=?, summary=?, context_json=?, updated_at=?, resolved_at=NULL
                WHERE id=?
                """,
                (severity, title, summary, context_json, now, incident_id),
            )
            return incident_id
        cur = conn.execute(
            """
            INSERT INTO incidents(scope_type, scope_id, incident_kind, severity, title, summary, context_json, status, created_at, updated_at, resolved_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, NULL)
            """,
            (scope_type, scope_id, incident_kind, severity, title, summary, context_json, now, now),
        )
        return int(cur.lastrowid)


def resolve_incidents(*, scope_type: str, scope_id: str, incident_kinds: List[str]) -> None:
    if not incident_kinds or not table_exists("incidents"):
        return
    placeholders = ", ".join("?" for _ in incident_kinds)
    now = iso(utc_now()) or ""
    with db() as conn:
        conn.execute(
            f"""
            UPDATE incidents
            SET status='resolved', updated_at=?, resolved_at=?
            WHERE scope_type=? AND scope_id=? AND status='open' AND incident_kind IN ({placeholders})
            """,
            (now, now, scope_type, scope_id, *incident_kinds),
        )


def latest_open_incident(
    scope_type: str,
    scope_id: str,
    *,
    incident_kinds: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    rows = incident_rows(status="open", limit=50, scope_type=scope_type, scope_ids=[scope_id])
    if incident_kinds:
        wanted = {str(item).strip() for item in incident_kinds if str(item).strip()}
        rows = [item for item in rows if str(item.get("incident_kind") or "").strip() in wanted]
    return rows[0] if rows else None


def current_pr_check_incident(project_id: str, *, head_sha: str = "") -> Optional[Dict[str, Any]]:
    incident = latest_open_incident("project", project_id, incident_kinds=[PR_CHECKS_FAILED_INCIDENT_KIND])
    if not incident:
        return None
    wanted_head = str(head_sha or "").strip()
    if not wanted_head:
        pr_row = pull_request_row(project_id) or {}
        review_mode = str(pr_row.get("review_mode") or "").strip().lower()
        pr_number = int(pr_row.get("pr_number") or 0)
        if review_mode != "github" or pr_number <= 0:
            resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[PR_CHECKS_FAILED_INCIDENT_KIND])
            return None
    incident_head = str(((incident.get("context") or {}).get("head_sha")) or "").strip()
    if wanted_head and incident_head and incident_head != wanted_head:
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[PR_CHECKS_FAILED_INCIDENT_KIND])
        return None
    return incident


def trigger_auditor_run_now(*, scope_type: Optional[str] = None, scope_id: Optional[str] = None) -> Dict[str, Any]:
    url = f"{AUDITOR_URL}/api/auditor/run-now"
    query: Dict[str, str] = {}
    if scope_type and scope_id:
        query["scope_type"] = str(scope_type)
        query["scope_id"] = str(scope_id)
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except Exception as exc:
        return {
            "requested": False,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "can_resolve": False,
            "error": str(exc),
        }
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        payload = {}
    payload.setdefault("requested", True)
    payload.setdefault("scope_type", scope_type)
    payload.setdefault("scope_id", scope_id)
    return payload


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


def current_slice(project_row: sqlite3.Row) -> Optional[str]:
    queue = json.loads(project_row["queue_json"] or "[]")
    idx = project_row["queue_index"]
    if 0 <= idx < len(queue):
        return normalize_slice_text(queue[idx]) or None
    fallback = normalize_slice_text(project_row["current_slice"])
    if fallback:
        return fallback
    return None


def review_slice_name(project_id: str, fallback: Optional[str] = None) -> Optional[str]:
    candidate = normalize_slice_text(fallback)
    if candidate:
        return candidate
    with db() as conn:
        row = conn.execute("SELECT current_slice FROM projects WHERE id=?", (project_id,)).fetchone()
        current = normalize_slice_text((row["current_slice"] if row else "") or "")
        if current:
            return current
        row = conn.execute(
            """
            SELECT slice_name
            FROM runs
            WHERE project_id=? AND job_kind='coding' AND slice_name IS NOT NULL AND TRIM(slice_name) != ''
            ORDER BY id DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    return normalize_slice_text((row["slice_name"] if row else "") or "") or None


def remap_queue_index(existing_queue: List[str], existing_index: int, new_queue: List[str]) -> int:
    if not new_queue:
        return 0
    existing_index = max(0, min(int(existing_index), len(existing_queue)))
    if existing_queue == new_queue:
        return min(existing_index, len(new_queue))

    current_item = existing_queue[existing_index] if existing_index < len(existing_queue) else None
    if current_item and current_item in new_queue:
        return new_queue.index(current_item)

    completed_items = existing_queue[:existing_index]
    matched = 0
    while matched < len(completed_items) and matched < len(new_queue):
        if new_queue[matched] != completed_items[matched]:
            break
        matched += 1
    return min(matched, len(new_queue))


def effective_project_status(
    *,
    project_id: Optional[str],
    stored_status: Optional[str],
    queue: List[str],
    queue_index: int,
    enabled: bool,
    active_run_id: Optional[int],
    source_backlog_open: bool,
) -> str:
    status = str(stored_status or "").strip() or READY_STATUS
    review_runtime_status = persisted_review_runtime_status(str(project_id or "")) if project_id else None
    if not enabled:
        return "paused"
    if review_runtime_status in {"review_fix_required", "review_failed", JURY_REWORK_REQUIRED_STATUS, CORE_RESCUE_PENDING_STATUS, MANUAL_HOLD_STATUS}:
        return review_runtime_status
    if int(queue_index) >= len(queue):
        if review_runtime_status:
            return review_runtime_status
        if status in REVIEW_VISIBLE_STATUSES:
            return status
        if status in {"starting", "running", "verifying"} and active_run_id:
            return status
        if status == SOURCE_BACKLOG_OPEN_STATUS or source_backlog_open:
            return SOURCE_BACKLOG_OPEN_STATUS
        return "complete"
    if status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS}:
        return READY_STATUS
    return status


def public_project_status(
    runtime_status: Optional[str],
    *,
    lifecycle: Optional[str] = None,
    cooldown_until: Optional[str] = None,
    needs_refill: bool = False,
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
        if group_signed_off:
            return COMPLETED_SIGNED_OFF_STATUS
        if lifecycle_state == "signoff_only":
            return "signoff_only"
        if lifecycle_state in {"planned", "scaffold"}:
            return SCAFFOLD_QUEUE_COMPLETE_STATUS
        return CONFIGURED_QUEUE_COMPLETE_STATUS
    return status


def project_completion_basis(
    *,
    runtime_status: Optional[str],
    queue: List[str],
    queue_index: int,
    has_queue_sources: bool,
) -> str:
    status = str(runtime_status or "").strip() or READY_STATUS
    queue_len = len(queue)
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


def project_backlog_source_summary(project_cfg: Dict[str, Any]) -> str:
    sources: List[str] = []
    if project_cfg.get("queue"):
        sources.append("fleet.yaml queue")
    for source_cfg in project_cfg.get("queue_sources") or []:
        kind = str(source_cfg.get("kind") or "source").strip()
        path = str(source_cfg.get("path") or "").strip()
        sources.append(f"{kind}:{path}" if path else kind)
    overlay_path = studio_published_root(project_cfg) / "QUEUE.generated.yaml"
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
            WHERE scope_type=? AND scope_id=?
              AND (
                status IN ('open', 'approved')
                OR (status='published' AND resolved_at IS NULL)
              )
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
    queue: List[str],
    current_queue_item: Optional[str],
) -> List[str]:
    materialized_texts = list(queue)
    if current_queue_item:
        materialized_texts.append(str(current_queue_item))
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
        or review_status == LOCAL_REVIEW_PENDING_STATUS
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
            stop_reason = "local verify passed and the slice is waiting for PR creation or update"
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


def audit_task_counts(project_id: str) -> Dict[str, int]:
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


def group_runtime_rows() -> Dict[str, Dict[str, Any]]:
    if not table_exists("group_runtime"):
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM group_runtime ORDER BY group_id").fetchall()
    return {str(row["group_id"]): dict(row) for row in rows}


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


def group_audit_request_pending(meta: Dict[str, Any], *, now: Optional[dt.datetime] = None) -> bool:
    last_audit_requested_at = parse_iso(meta.get("last_audit_requested_at"))
    if last_audit_requested_at is None:
        return False
    last_refill_requested_at = parse_iso(meta.get("last_refill_requested_at"))
    if last_refill_requested_at and last_refill_requested_at > last_audit_requested_at:
        return False
    current_now = now or utc_now()
    return last_audit_requested_at >= current_now - dt.timedelta(seconds=AUDIT_REQUEST_PENDING_SECONDS)


def group_audit_request_due(meta: Dict[str, Any], *, now: Optional[dt.datetime] = None) -> bool:
    current_now = now or utc_now()
    last_audit_requested_at = parse_iso(meta.get("last_audit_requested_at"))
    last_refill_requested_at = parse_iso(meta.get("last_refill_requested_at"))
    if last_refill_requested_at and (last_audit_requested_at is None or last_refill_requested_at >= last_audit_requested_at):
        return True
    if last_audit_requested_at is None:
        return True
    return last_audit_requested_at <= current_now - dt.timedelta(seconds=AUDIT_REQUEST_DEBOUNCE_SECONDS)


def group_publish_events(limit: int = 50) -> List[Dict[str, Any]]:
    if not table_exists("group_publish_events"):
        return []
    with db() as conn:
        rows = conn.execute("SELECT * FROM group_publish_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        targets = json_field(item.get("published_targets_json"), [])
        item["published_targets"] = targets if isinstance(targets, list) else []
        target_labels = []
        for target in item["published_targets"]:
            target_labels.append(f"{target.get('target_type')}:{target.get('target_id')}")
        item["published_targets_summary"] = ", ".join(target_labels[:3])
        if len(target_labels) > 3:
            item["published_targets_summary"] = f"{item['published_targets_summary']}, +{len(target_labels) - 3} more"
        items.append(item)
    return items


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


def sync_group_runtime_phase(config: Dict[str, Any]) -> None:
    if not table_exists("group_runtime"):
        return
    registry = load_program_registry(config)
    runtime_rows = group_runtime_rows()
    with db() as conn:
        raw_project_rows = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY id").fetchall()}
    now = utc_now()

    for group_cfg in config.get("project_groups") or []:
        group_id = str(group_cfg.get("id") or "").strip()
        if not group_id:
            continue
        group_meta = effective_group_meta(group_cfg, registry, runtime_rows)
        group_projects: List[Dict[str, Any]] = []
        for project_id in group_cfg.get("projects") or []:
            row = raw_project_rows.get(str(project_id))
            if not row:
                continue
            project_cfg = get_project_cfg(config, str(project_id))
            lifecycle_state = normalize_lifecycle_state(project_cfg.get("lifecycle"), "dispatchable")
            queue = json.loads(row.get("queue_json") or "[]")
            runtime_status = effective_project_status(
                project_id=str(project_id),
                stored_status=row.get("status"),
                queue=queue,
                queue_index=int(row.get("queue_index") or 0),
                enabled=bool(project_cfg.get("enabled", True)),
                active_run_id=row.get("active_run_id"),
                source_backlog_open=bool(project_cfg.get("queue_sources")) and bool(queue),
            )
            counts = audit_task_counts(str(project_id))
            group_counts = audit_task_candidate_counts_for_scope("group", [group_id])
            if lifecycle_state == "signoff_only":
                counts = {"open": 0, "approved": 0, "published": 0}
                group_counts = {"open": 0, "approved": 0, "published": 0}
            stop_ctx = project_stop_context(
                project_cfg=project_cfg,
                runtime_status=runtime_status,
                queue_len=len(queue),
                uncovered_scope_count=0,
                open_task_count=int(counts["open"]),
                approved_task_count=int(counts["approved"]),
                group_open_task_count=int(group_counts["open"]),
                group_approved_task_count=int(group_counts["approved"]),
                last_error=row.get("last_error"),
                cooldown_until=row.get("cooldown_until"),
                review_eta=None,
                milestone_coverage_complete=False,
                design_coverage_complete=False,
                group_signed_off=group_is_signed_off(group_meta),
            )
            project_public_status = public_project_status(
                runtime_status,
                lifecycle=lifecycle_state,
                cooldown_until=row.get("cooldown_until"),
                needs_refill=bool(stop_ctx.get("needs_refill")),
                open_task_count=int(counts["open"]),
                approved_task_count=int(counts["approved"]),
                group_signed_off=group_is_signed_off(group_meta),
            )
            group_projects.append(
                {
                    "id": str(project_id),
                    "lifecycle": lifecycle_state,
                    "queue": queue,
                    "queue_index": int(row.get("queue_index") or 0),
                    "enabled": bool(project_cfg.get("enabled", True)),
                    "cooldown_until": row.get("cooldown_until"),
                    "status": project_public_status,
                    "status_internal": runtime_status,
                    "runtime_status": project_public_status,
                    "needs_refill": bool(stop_ctx.get("needs_refill")),
                    "open_audit_task_count": int(counts["open"]),
                    "approved_audit_task_count": int(counts["approved"]),
                    "current_queue_item": queue[int(row.get("queue_index") or 0)] if int(row.get("queue_index") or 0) < len(queue) else None,
                }
            )
        group_view = dict(group_cfg)
        group_view.update(group_dispatch_state(group_cfg, group_meta, group_projects, now))
        group_view["status"] = effective_group_status(group_cfg, group_meta, group_projects)
        next_phase = derive_group_phase(group_view, group_projects)
        with db() as conn:
            current_runtime_row = conn.execute("SELECT * FROM group_runtime WHERE group_id=?", (group_id,)).fetchone()
            current_runtime = dict(current_runtime_row) if current_runtime_row else dict(runtime_rows.get(group_id, {}) or {})
            previous_signoff = str(current_runtime.get("signoff_state") or "open").strip().lower() or "open"
            next_signoff = previous_signoff
            signed_off_at = current_runtime.get("signed_off_at")
            reopened_at = current_runtime.get("reopened_at")
            auto_signoff = (
                bool(get_policy(config, "auto_signoff_completed_groups", True))
                and str(group_view.get("status") or "").strip().lower() in {"complete", CONFIGURED_QUEUE_COMPLETE_STATUS}
                and previous_signoff != "signed_off"
            )
            if auto_signoff:
                next_signoff = "signed_off"
                signed_off_at = signed_off_at or iso(now)
                group_view["status"] = "product_signed_off"
                next_phase = "signed_off"
            previous_phase = str(current_runtime.get("phase") or "").strip().lower() or READY_STATUS
            phase_timestamp = current_runtime.get("last_phase_at") if previous_phase == next_phase else iso(now)
            conn.execute(
                """
                INSERT INTO group_runtime(group_id, signoff_state, signed_off_at, reopened_at, last_audit_requested_at, last_refill_requested_at, phase, last_phase_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    signoff_state=excluded.signoff_state,
                    signed_off_at=excluded.signed_off_at,
                    reopened_at=excluded.reopened_at,
                    phase=excluded.phase,
                    last_phase_at=excluded.last_phase_at,
                    updated_at=excluded.updated_at
                """,
                (
                    group_id,
                    next_signoff,
                    signed_off_at,
                    reopened_at,
                    current_runtime.get("last_audit_requested_at"),
                    current_runtime.get("last_refill_requested_at"),
                    next_phase,
                    phase_timestamp,
                    iso(now),
                ),
            )
        if auto_signoff:
            log_group_run(
                group_id,
                run_kind="signoff",
                phase="signed_off",
                status="requested",
                member_projects=[str(project.get("id") or "") for project in group_projects],
                details={"requested_by": "controller", "mode": "auto"},
            )
        if previous_phase != next_phase:
            log_group_run(
                group_id,
                run_kind="phase",
                phase=next_phase,
                status="observed",
                member_projects=[str(project.get("id") or "") for project in group_projects],
                details={
                    "previous_phase": previous_phase,
                    "group_status": group_view.get("status"),
                    "dispatch_ready": bool(group_view.get("dispatch_ready")),
                },
            )


def request_due_group_audits(config: Dict[str, Any]) -> int:
    if not bool(get_policy(config, "auto_heal_enabled", True)):
        return 0
    registry = load_program_registry(config)
    runtime_rows = group_runtime_rows()
    with db() as conn:
        raw_project_rows = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY id").fetchall()}
    now = utc_now()
    requested = 0
    for group_cfg in config.get("project_groups") or []:
        group_id = str(group_cfg.get("id") or "").strip()
        if not group_id or not auto_heal_category_enabled(config, "coverage", group_id=group_id):
            continue
        group_meta = effective_group_meta(group_cfg, registry, runtime_rows)
        if group_is_signed_off(group_meta):
            continue
        group_projects: List[Dict[str, Any]] = []
        for project_id in group_cfg.get("projects") or []:
            row = raw_project_rows.get(str(project_id))
            if not row:
                continue
            project_cfg = get_project_cfg(config, str(project_id))
            lifecycle_state = normalize_lifecycle_state(project_cfg.get("lifecycle"), "dispatchable")
            queue = json.loads(row.get("queue_json") or "[]")
            runtime_status = effective_project_status(
                project_id=str(project_id),
                stored_status=row.get("status"),
                queue=queue,
                queue_index=int(row.get("queue_index") or 0),
                enabled=bool(project_cfg.get("enabled", True)),
                active_run_id=row.get("active_run_id"),
                source_backlog_open=bool(project_cfg.get("queue_sources")) and bool(queue),
            )
            counts = audit_task_counts(str(project_id))
            group_counts = audit_task_candidate_counts_for_scope("group", [group_id])
            if lifecycle_state == "signoff_only":
                counts = {"open": 0, "approved": 0, "published": 0}
                group_counts = {"open": 0, "approved": 0, "published": 0}
            stop_ctx = project_stop_context(
                project_cfg=project_cfg,
                runtime_status=runtime_status,
                queue_len=len(queue),
                uncovered_scope_count=0,
                open_task_count=int(counts["open"]),
                approved_task_count=int(counts["approved"]),
                group_open_task_count=int(group_counts["open"]),
                group_approved_task_count=int(group_counts["approved"]),
                last_error=row.get("last_error"),
                cooldown_until=row.get("cooldown_until"),
                review_eta=None,
                milestone_coverage_complete=False,
                design_coverage_complete=False,
                group_signed_off=group_is_signed_off(group_meta),
            )
            group_projects.append(
                {
                    "id": str(project_id),
                    "lifecycle": lifecycle_state,
                    "status": public_project_status(
                        runtime_status,
                        lifecycle=lifecycle_state,
                        cooldown_until=row.get("cooldown_until"),
                        needs_refill=bool(stop_ctx.get("needs_refill")),
                        open_task_count=int(counts["open"]),
                        approved_task_count=int(counts["approved"]),
                        group_signed_off=group_is_signed_off(group_meta),
                    ),
                    "status_internal": runtime_status,
                    "needs_refill": bool(stop_ctx.get("needs_refill")),
                    "open_audit_task_count": int(counts["open"]),
                    "approved_audit_task_count": int(counts["approved"]),
                }
            )
        if effective_group_status(group_cfg, group_meta, group_projects) not in {"audit_required", "milestone_backlog_open"}:
            continue
        if not group_audit_request_due(group_meta, now=now):
            continue
        member_projects = [str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()]
        upsert_group_runtime(group_id, signoff_state="open", mark_audit_requested=True)
        log_group_run(
            group_id,
            run_kind="audit",
            phase="audit_requested",
            status="requested",
            member_projects=member_projects,
            details={"requested_by": "controller"},
        )
        result = trigger_auditor_run_now(scope_type="group", scope_id=group_id)
        if bool(result.get("requested")):
            requested += 1
    return requested


def maintain_active_worker_floor(
    config: Dict[str, Any],
    candidates: Dict[str, "DispatchCandidate"],
    *,
    running_count: int,
) -> int:
    target = max(0, int(get_policy(config, "min_active_codex_workers", 0) or 0))
    max_parallel = max(1, int(get_policy(config, "max_parallel_runs", 3) or 3))
    desired = min(target, max_parallel)
    if desired <= 0 or running_count >= desired:
        return 0

    launched = 0
    floor_candidates = sorted(
        [
            candidate
            for project_id, candidate in candidates.items()
            if (
                candidate.dispatchable
                and candidate.slice_name
                and (project_id not in state.tasks or state.tasks[project_id].done())
            )
        ],
        key=gate_clearing_priority,
    )
    for candidate in floor_candidates:
        if running_count + launched >= desired:
            break
        planned = plan_candidate_launch(config, candidate)
        if not planned:
            continue
        task = asyncio.create_task(
            execute_project_slice(
                config,
                planned.candidate.project_cfg,
                planned.candidate.row,
                planned.candidate.slice_name or "",
                planned.decision,
                planned.account_alias,
                planned.selected_model,
                planned.selection_note,
                planned.selection_trace,
            )
        )
        state.tasks[planned.project_id] = task
        launched += 1

    for pr_row in review_waiting_rows():
        if running_count + launched >= desired:
            break
        project_id = str(pr_row.get("project_id") or "").strip()
        if (
            not project_id
            or (project_id in state.tasks and not state.tasks[project_id].done())
            or active_local_review_run(project_id)
        ):
            continue
        reason = f"maintain active worker floor of {desired} codex runs while no coding slice is dispatchable"
        if launch_local_review_fallback(config, project_id, pr_row, reason=reason):
            launched += 1

    if running_count + launched >= desired:
        return launched

    for pr_row in local_review_waiting_rows():
        if running_count + launched >= desired:
            break
        project_id = str(pr_row.get("project_id") or "").strip()
        if (
            not project_id
            or (project_id in state.tasks and not state.tasks[project_id].done())
            or active_local_review_run(project_id)
        ):
            continue
        try:
            result = request_project_local_review_now(project_id)
        except HTTPException:
            continue
        if bool(result.get("launched")):
            launched += 1

    request_due_group_audits(config)
    return launched


def codex_active_project_ids(project_rows: Sequence[sqlite3.Row]) -> set[str]:
    active_statuses = {"starting", "running"}
    run_ids = [int(row["active_run_id"]) for row in project_rows if row["active_run_id"]]
    runs_by_id: Dict[int, sqlite3.Row] = {}
    if run_ids:
        placeholders = ",".join("?" for _ in run_ids)
        with db() as conn:
            for run in conn.execute(
                f"SELECT id, job_kind, status FROM runs WHERE id IN ({placeholders})",
                tuple(run_ids),
            ).fetchall():
                runs_by_id[int(run["id"])] = run

    active: set[str] = set()
    for row in project_rows:
        project_id = str(row["id"] or "").strip()
        if not project_id:
            continue
        run = runs_by_id.get(int(row["active_run_id"] or 0)) if row["active_run_id"] else None
        run_status = str((run["status"] if run else row["status"]) or "").strip().lower()
        run_kind = str((run["job_kind"] if run else "coding") or "coding").strip().lower() or "coding"
        if run_status in active_statuses and run_kind in {"coding", "healing", "local_review"}:
            active.add(project_id)
    return active


def prepare_dispatch_candidate(config: Dict[str, Any], project_cfg: Dict[str, Any], row: sqlite3.Row, now: dt.datetime) -> "DispatchCandidate":
    project_id = row["id"]
    queue = json.loads(row["queue_json"] or "[]")
    queue_index = int(row["queue_index"] or 0)
    slice_item = queue[queue_index] if 0 <= queue_index < len(queue) else None
    task_meta = normalize_task_queue_item(slice_item, lanes=config.get("lanes"))
    enabled = bool(project_cfg.get("enabled", True))
    has_queue_sources = bool(project_cfg.get("queue_sources"))
    review_runtime_status = persisted_review_runtime_status(project_id)

    if not enabled:
        update_project_status(
            project_id,
            status="paused",
            current_slice=current_slice(row),
            active_run_id=None,
            cooldown_until=None,
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=row["last_error"],
            consecutive_failures=row["consecutive_failures"],
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
        return DispatchCandidate(
            row=row,
            project_cfg=project_cfg,
            queue=queue,
            queue_index=queue_index,
            slice_item=None,
            slice_name=current_slice(row),
            task_meta=task_meta,
            runtime_status="paused",
            cooldown_until=None,
            dispatchable=False,
        )

    if queue_index >= len(queue):
        review_slice = review_slice_name(project_id, fallback=str(row["current_slice"] or ""))
        if review_runtime_status:
            cooldown_until = parse_iso(row["cooldown_until"])
            if str(row["status"] or "").strip().lower() != review_runtime_status or review_slice != str(row["current_slice"] or "").strip():
                update_project_status(
                    project_id,
                    status=review_runtime_status,
                    current_slice=review_slice,
                    active_run_id=None,
                    cooldown_until=cooldown_until,
                    last_run_at=parse_iso(row["last_run_at"]),
                    last_error=row["last_error"],
                    consecutive_failures=row["consecutive_failures"],
                    spider_tier=row["spider_tier"],
                    spider_model=row["spider_model"],
                    spider_reason=row["spider_reason"],
                )
            if review_runtime_status in REVIEW_HOLD_STATUSES | {MANUAL_HOLD_STATUS, "review_failed"}:
                return DispatchCandidate(
                    row=row,
                    project_cfg=project_cfg,
                    queue=queue,
                    queue_index=queue_index,
                    slice_item=None,
                    slice_name=review_slice,
                    task_meta=task_meta,
                    runtime_status=review_runtime_status,
                    cooldown_until=cooldown_until,
                    dispatchable=False,
                )
            if review_runtime_status in {"review_fix_required", JURY_REWORK_REQUIRED_STATUS, CORE_RESCUE_PENDING_STATUS}:
                dispatchable = cooldown_until is None or cooldown_until <= now
                return DispatchCandidate(
                    row=row,
                    project_cfg=project_cfg,
                    queue=queue,
                    queue_index=queue_index,
                    slice_item=None,
                    slice_name=review_slice,
                    task_meta=task_meta,
                    runtime_status=review_runtime_status,
                    cooldown_until=cooldown_until,
                    dispatchable=dispatchable,
                )
        exhausted_status = SOURCE_BACKLOG_OPEN_STATUS if has_queue_sources and bool(queue) else "complete"
        update_project_status(
            project_id,
            status=exhausted_status,
            current_slice=None,
            active_run_id=None,
            cooldown_until=None,
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=row["last_error"],
            consecutive_failures=0,
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
        return DispatchCandidate(
            row=row,
            project_cfg=project_cfg,
            queue=queue,
            queue_index=queue_index,
            slice_item=None,
            slice_name=None,
            task_meta=task_meta,
            runtime_status=exhausted_status,
            cooldown_until=None,
            dispatchable=False,
        )

    runtime_status = str(row["status"] or "").strip() or READY_STATUS
    active_run_id = row["active_run_id"]
    is_active_runtime = bool(active_run_id) or runtime_status in {"starting", "running", "verifying"}
    dispatchability_state = str(task_meta.get("dispatchability_state") or "dispatchable").strip().lower() or "dispatchable"
    if not is_active_runtime and dispatchability_state != "dispatchable":
        status_reason = (
            "current slice is design-only and must stay in compile/policy review before dispatch"
            if dispatchability_state == "design_only"
            else "current slice is explicitly blocked and cannot dispatch"
        )
        update_project_status(
            project_id,
            status="blocked",
            current_slice=normalize_slice_text(queue[queue_index]),
            active_run_id=None,
            cooldown_until=None,
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=status_reason,
            consecutive_failures=row["consecutive_failures"],
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
        return DispatchCandidate(
            row=row,
            project_cfg=project_cfg,
            queue=queue,
            queue_index=queue_index,
            slice_item=slice_item,
            slice_name=normalize_slice_text(queue[queue_index]),
            task_meta=task_meta,
            runtime_status="blocked",
            cooldown_until=None,
            dispatchable=False,
        )
    if not is_active_runtime and review_runtime_status in {"review_fix_required", "review_failed", JURY_REWORK_REQUIRED_STATUS, CORE_RESCUE_PENDING_STATUS, MANUAL_HOLD_STATUS} and runtime_status != review_runtime_status:
        runtime_status = review_runtime_status
        update_project_status(
            project_id,
            status=runtime_status,
            current_slice=normalize_slice_text(queue[queue_index]),
            active_run_id=None,
            cooldown_until=parse_iso(row["cooldown_until"]),
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=row["last_error"],
            consecutive_failures=row["consecutive_failures"],
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
    if runtime_status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS}:
        runtime_status = READY_STATUS
        update_project_status(
            project_id,
            status=runtime_status,
            current_slice=normalize_slice_text(queue[queue_index]),
            active_run_id=None,
            cooldown_until=parse_iso(row["cooldown_until"]),
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=row["last_error"],
            consecutive_failures=row["consecutive_failures"],
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
    if runtime_status == "blocked" and is_transient_review_failure(str(row["last_error"] or "")):
        runtime_status = "review_failed"
        update_project_status(
            project_id,
            status=runtime_status,
            current_slice=normalize_slice_text(queue[queue_index]),
            active_run_id=None,
            cooldown_until=parse_iso(row["cooldown_until"]),
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=row["last_error"],
            consecutive_failures=row["consecutive_failures"],
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )
    if runtime_status == "review_failed" and is_transient_review_failure(str(row["last_error"] or "")):
        if review_runtime_status in REVIEW_HOLD_STATUSES | {MANUAL_HOLD_STATUS}:
            runtime_status = review_runtime_status
            update_project_status(
                project_id,
                status=runtime_status,
                current_slice=normalize_slice_text(queue[queue_index]),
                active_run_id=None,
                cooldown_until=parse_iso(row["cooldown_until"]),
                last_run_at=parse_iso(row["last_run_at"]),
                last_error=row["last_error"],
                consecutive_failures=row["consecutive_failures"],
                spider_tier=row["spider_tier"],
                spider_model=row["spider_model"],
                spider_reason=row["spider_reason"],
            )
    if runtime_status == "review_failed" and is_retryable_push_rejection(str(row["last_error"] or "")):
        cooldown_until = parse_iso(row["cooldown_until"])
        if cooldown_until is None or cooldown_until <= utc_now():
            runtime_status = READY_STATUS
            update_project_status(
                project_id,
                status=runtime_status,
                current_slice=normalize_slice_text(queue[queue_index]),
                active_run_id=None,
                cooldown_until=None,
                last_run_at=parse_iso(row["last_run_at"]),
                last_error="retrying after transient push rejection",
                consecutive_failures=0,
                spider_tier=row["spider_tier"],
                spider_model=row["spider_model"],
                spider_reason=row["spider_reason"],
            )

    runtime_status, promoted_review_fix = promote_review_fix_candidate(
        config,
        project_id,
        row,
        runtime_status,
        queue,
        queue_index,
    )

    if runtime_status == "review_failed":
        review_incident = current_pr_check_incident(project_id, head_sha=str((pull_request_row(project_id) or {}).get("head_sha") or ""))
        if review_incident and auto_heal_category_enabled(config, "review", project_id=project_id):
            runtime_status = "review_fix_required"
            promoted_review_fix = True
            update_project_status(
                project_id,
                status=runtime_status,
                current_slice=normalize_slice_text(queue[queue_index]),
                active_run_id=None,
                cooldown_until=None,
                last_run_at=parse_iso(row["last_run_at"]),
                last_error=row["last_error"],
                consecutive_failures=row["consecutive_failures"],
                spider_tier=row["spider_tier"],
                spider_model=row["spider_model"],
                spider_reason=row["spider_reason"],
            )
        else:
            return DispatchCandidate(
                row=row,
                project_cfg=project_cfg,
                queue=queue,
                queue_index=queue_index,
                slice_item=slice_item,
                slice_name=normalize_slice_text(queue[queue_index]),
                task_meta=task_meta,
                runtime_status=runtime_status,
                cooldown_until=parse_iso(row["cooldown_until"]),
                dispatchable=False,
            )

    if runtime_status in REVIEW_HOLD_STATUSES | {MANUAL_HOLD_STATUS}:
        return DispatchCandidate(
            row=row,
            project_cfg=project_cfg,
            queue=queue,
            queue_index=queue_index,
            slice_item=slice_item,
            slice_name=normalize_slice_text(queue[queue_index]),
            task_meta=task_meta,
            runtime_status=runtime_status,
            cooldown_until=parse_iso(row["cooldown_until"]),
            dispatchable=False,
        )

    cooldown_until = parse_iso(row["cooldown_until"])
    if runtime_status in {"review_fix_required", JURY_REWORK_REQUIRED_STATUS, CORE_RESCUE_PENDING_STATUS} or promoted_review_fix:
        cooldown_until = None
    dispatchable = cooldown_until is None or cooldown_until <= now
    return DispatchCandidate(
        row=row,
        project_cfg=project_cfg,
        queue=queue,
        queue_index=queue_index,
        slice_item=slice_item,
        slice_name=normalize_slice_text(queue[queue_index]),
        task_meta=task_meta,
        runtime_status=runtime_status,
        cooldown_until=cooldown_until,
        dispatchable=dispatchable,
    )


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
    status = project_runtime_status(project)
    lifecycle_state = normalize_lifecycle_state(project.get("lifecycle"), "dispatchable")
    if lifecycle_state == "signoff_only":
        if status in {"blocked", "review_failed"} or int(project.get("open_incident_count") or 0) > 0:
            return "high"
        return "nominal"
    if status in {"review_requested", "awaiting_pr", "review_failed", "review_fix_required"}:
        return "high"
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


def eligible_account_aliases(config: Dict[str, Any], project_cfg: Dict[str, Any], now: dt.datetime) -> List[str]:
    policy = project_account_policy(project_cfg)
    aliases = ordered_project_aliases(project_cfg)
    accounts_cfg = config.get("accounts") or {}
    eligible: List[str] = []
    with db() as conn:
        for alias in aliases:
            row = conn.execute("SELECT * FROM accounts WHERE alias=?", (alias,)).fetchone()
            if not row:
                continue
            account_cfg = accounts_cfg.get(alias) or {}
            auth_kind = str(row["auth_kind"] or account_cfg.get("auth_kind") or "api_key")
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
    member_ids = [str(project.get("id") or "").strip() for project in participant_projects if str(project.get("id") or "").strip()]
    eligible_union: List[str] = []
    per_project: Dict[str, int] = {}
    total_slots = 0
    with db() as conn:
        for project_id in member_ids:
            try:
                project_cfg = get_project_cfg(config, project_id)
            except KeyError:
                continue
            aliases = eligible_account_aliases(config, project_cfg, now)
            per_project[project_id] = len(aliases)
            for alias in aliases:
                if alias in eligible_union:
                    continue
                eligible_union.append(alias)
                row = conn.execute("SELECT max_parallel_runs FROM accounts WHERE alias=?", (alias,)).fetchone()
                total_slots += max(1, int((row["max_parallel_runs"] if row else 1) or 1))
    captain = group_captain_policy(group_cfg)
    required_slots = max(1, int(captain.get("service_floor") or 1))
    total_slots = min(total_slots, max(1, int(get_policy(config, "max_parallel_runs", 1))))
    remaining_slices = sum(max(project_queue_length(project) - int(project.get("queue_index") or 0), 0) for project in participant_projects)
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


def incident_target_project_id(item: Dict[str, Any]) -> str:
    scope_type = str(item.get("scope_type") or "").strip()
    scope_id = str(item.get("scope_id") or "").strip()
    if scope_type == "project":
        return scope_id
    context = item.get("context") if isinstance(item.get("context"), dict) else json_field(item.get("context_json"), {})
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


def group_open_incidents(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    group_id = str(group.get("id") or "").strip()
    project_ids = [str(project.get("id") or "").strip() for project in group_projects if str(project.get("id") or "").strip()]
    incidents = incident_rows(status="open", limit=100, scope_type="group", scope_ids=[group_id]) if group_id else []
    incidents.extend(incident_rows(status="open", limit=100, scope_type="project", scope_ids=project_ids))
    incidents = filter_runtime_relevant_incidents(incidents, group_projects)
    incidents.sort(
        key=lambda item: (
            0 if str(item.get("severity") or "") == "critical" else 1 if str(item.get("severity") or "") == "high" else 2,
            str(item.get("updated_at") or ""),
        )
    )
    return incidents


def group_operator_question(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> str:
    group_id = str(group.get("id") or "").strip() or "group"
    ready_count = int(group.get("ready_project_count") or 0)
    review_waiting = int(group.get("review_waiting_count") or 0)
    review_blocking = int(group.get("review_blocking_count") or 0)
    blockers = list(group.get("contract_blockers") or []) + operator_relevant_dispatch_blockers(group.get("dispatch_blockers") or [])
    status = str(group.get("status") or "").strip().lower()
    auditor_can_solve = bool(group.get("auditor_can_solve"))
    incidents = [item for item in (group.get("incidents") or []) if incident_requires_operator_attention(item)]
    if incidents:
        top = incidents[0]
        return f"{group_id}: {short_question_detail(top.get('title') or top.get('summary') or 'an incident needs operator attention')}. Should I apply the proposed recovery, or override it manually?"
    if review_blocking > 0:
        return f"{group_id}: Codex review reported blocking findings. Should I fix them and re-request review, or accept the risk?"
    if review_waiting > 0:
        return f"{group_id}: review is still pending. Should I wait for GitHub review, or override the review gate?"
    if status == "product_signed_off":
        return f"{group_id}: this group is signed off. Should I keep it closed, or reopen it for more work?"
    if status in {"complete", CONFIGURED_QUEUE_COMPLETE_STATUS}:
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
    incidents = [item for item in (group.get("incidents") or []) if incident_requires_operator_attention(item)]
    needs_notification = bool(incidents)
    reason_bits: List[str] = []
    if incidents:
        top = incidents[0]
        reason_bits.append(short_question_detail(top.get("title") or top.get("summary") or "", limit=140))
        if blockers:
            reason_bits.append(short_question_detail(blockers[0], limit=140))
        if review_blocking > 0:
            reason_bits.append(f"{review_blocking} blocking review finding(s)")
    severity = str((incidents[0] if incidents else {}).get("severity") or "")
    title = f"{group_id}: {len(incidents)} incident(s) need operator attention" if incidents else ""
    return {
        "needed": needs_notification,
        "severity": severity,
        "title": title,
        "reason": "; ".join(reason_bits),
        "question": str(group.get("operator_question") or ""),
        "ready_project_count": ready_count,
        "ready_project_ids": ready_ids,
        "incident_count": len(incidents),
        "auditor_can_solve": auditor_can_solve,
        "focus_id": f"group-problem-{group_id}",
        "href": f"/admin#group-problem-{group_id}",
        "notification_key": f"{group_id}|{ready_count}|{len(incidents)}|{int(auditor_can_solve)}|{'; '.join(reason_bits)}",
    }


def captain_dispatch_key(
    *,
    group_cfg: Dict[str, Any],
    running_by_group: Dict[str, int],
    pressure_high: bool,
) -> Tuple[int, int, int, int, str]:
    captain = group_captain_policy(group_cfg)
    group_id = str(group_cfg.get("id") or "")
    running = int(running_by_group.get(group_id) or 0)
    service_floor = int(captain.get("service_floor") or 0)
    under_floor = 1 if running < service_floor else 0
    admission_policy = str(captain.get("admission_policy") or "normal")
    best_effort_penalty = 1 if pressure_high and admission_policy == "best_effort" and not under_floor else 0
    return (
        best_effort_penalty,
        -under_floor,
        -int(captain.get("priority") or 0),
        int(captain.get("shed_order") or 0),
        group_id,
    )


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


def queue_eta_payload(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "remaining_slices": int(summary.get("remaining_slices") or 0),
        "estimated_remaining_seconds": summary.get("estimated_remaining_seconds"),
        "eta_at": summary.get("eta_at"),
        "eta_human": summary.get("eta_human") or "",
        "eta_basis": summary.get("eta_basis") or "",
        "eta_unavailable_reason": summary.get("eta_unavailable_reason") or "",
    }


def estimate_project_milestone_eta(project: Dict[str, Any], meta: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    remaining_items = remaining_milestone_items(meta)
    remaining_count = len(remaining_items)
    result: Dict[str, Any] = {
        "remaining_milestones": remaining_count,
        "estimated_remaining_seconds": None,
        "eta_at": None,
        "eta_human": "unknown",
        "eta_basis": "",
        "eta_unavailable_reason": "",
    }
    if not meta:
        result["eta_basis"] = "no milestone registry configured for this project"
        result["eta_unavailable_reason"] = "no_milestone_registry"
        return result
    if not bool(meta.get("milestone_coverage_complete")):
        result["eta_basis"] = "milestone coverage incomplete"
        result["eta_unavailable_reason"] = "milestone_coverage_incomplete"
        return result
    if remaining_count == 0:
        result.update(
            {
                "estimated_remaining_seconds": 0,
                "eta_at": iso(now),
                "eta_human": "0s",
                "eta_basis": "all defined milestones complete",
            }
        )
        return result
    mode = str(meta.get("eta_mode", "") or "").strip().lower()
    if mode == "queue_proxy":
        queue_eta = project.get("queue_eta") or {}
        result.update(
            {
                "estimated_remaining_seconds": queue_eta.get("estimated_remaining_seconds"),
                "eta_at": queue_eta.get("eta_at"),
                "eta_human": queue_eta.get("eta_human") or "unknown",
                "eta_basis": f"milestone ETA proxied from configured queue; {queue_eta.get('eta_basis') or ''}".strip("; "),
                "eta_unavailable_reason": queue_eta.get("eta_unavailable_reason") or "",
            }
        )
        return result
    result["eta_basis"] = "defined milestones exist, but no milestone task-to-ETA model is configured"
    result["eta_unavailable_reason"] = "milestone_eta_model_missing"
    return result


def estimate_project_design_eta(meta: Dict[str, Any], milestone_eta: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "estimated_remaining_seconds": None,
        "eta_at": None,
        "eta_human": "unknown",
        "eta_basis": "",
        "eta_unavailable_reason": "",
    }
    if not meta:
        result["eta_basis"] = "no design coverage registry configured for this project"
        result["eta_unavailable_reason"] = "no_design_registry"
        return result
    if not bool(meta.get("design_coverage_complete")):
        result["eta_basis"] = "design coverage incomplete"
        result["eta_unavailable_reason"] = "design_coverage_incomplete"
        return result
    if int(milestone_eta.get("remaining_milestones") or 0) == 0:
        result.update(
            {
                "estimated_remaining_seconds": 0,
                "eta_at": iso(now),
                "eta_human": "0s",
                "eta_basis": "design responsibilities fully mapped and current milestone set is complete",
            }
        )
        return result
    result["eta_basis"] = "design coverage is complete, but no design-level ETA model is configured"
    result["eta_unavailable_reason"] = "design_eta_model_missing"
    return result


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


def active_run_row(run_id: Any) -> Dict[str, Any]:
    try:
        clean_id = int(run_id or 0)
    except Exception:
        clean_id = 0
    if clean_id <= 0:
        return {}
    with db() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, status, job_kind, slice_name, account_alias, model
            FROM runs
            WHERE id=? AND finished_at IS NULL
            """,
            (clean_id,),
        ).fetchone()
    return dict(row) if row else {}


def run_backend_and_identity(account_alias: str, accounts_cfg: Dict[str, Any]) -> Tuple[str, str]:
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
        "ownership matrix",
        "session shell ownership",
        "design repo",
        "front door",
        "mirror",
        "sync workflow",
        "review-guidance",
        "review guidance",
        "milestone truth",
        "group blockers",
        "adr",
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
            elif status == MANUAL_HOLD_STATUS:
                blockers.append(f"{project_id}: operator hold after jury review")
            elif status in {"review_fix_required", JURY_REWORK_REQUIRED_STATUS}:
                blockers.append(f"{project_id}: rework loop still has follow-up fixes")
            elif status == CORE_RESCUE_PENDING_STATUS:
                blockers.append(f"{project_id}: waiting for core rescue before queue advance")
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


def estimate_group_milestone_eta(group: Dict[str, Any], meta: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    remaining_items = remaining_milestone_items(meta)
    remaining_count = len(remaining_items)
    result: Dict[str, Any] = {
        "remaining_milestones": remaining_count,
        "estimated_remaining_seconds": None,
        "eta_at": None,
        "eta_human": "unknown",
        "eta_basis": "",
        "eta_unavailable_reason": "",
    }
    if not meta:
        result["eta_basis"] = "no group milestone registry configured"
        result["eta_unavailable_reason"] = "no_group_milestone_registry"
        return result
    if not bool(meta.get("milestone_coverage_complete")):
        result["eta_basis"] = "group milestone coverage incomplete"
        result["eta_unavailable_reason"] = "group_milestone_coverage_incomplete"
        return result
    if remaining_count == 0:
        result.update(
            {
                "estimated_remaining_seconds": 0,
                "eta_at": iso(now),
                "eta_human": "0s",
                "eta_basis": "all defined group milestones complete",
            }
        )
        return result
    result["eta_basis"] = "group milestones are defined, but no milestone task-to-ETA model is configured"
    result["eta_unavailable_reason"] = "group_milestone_eta_model_missing"
    return result


def estimate_group_program_eta(meta: Dict[str, Any], milestone_eta: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "estimated_remaining_seconds": None,
        "eta_at": None,
        "eta_human": "unknown",
        "eta_basis": "",
        "eta_unavailable_reason": "",
    }
    if not meta:
        result["eta_basis"] = "no program registry configured for this group"
        result["eta_unavailable_reason"] = "no_program_registry"
        return result
    if not bool(meta.get("design_coverage_complete")):
        result["eta_basis"] = "program milestone coverage incomplete"
        result["eta_unavailable_reason"] = "program_coverage_incomplete"
        return result
    if int(milestone_eta.get("remaining_milestones") or 0) == 0:
        result.update(
            {
                "estimated_remaining_seconds": 0,
                "eta_at": iso(now),
                "eta_human": "0s",
                "eta_basis": "program responsibilities are fully mapped and the current group milestone set is complete",
            }
        )
        return result
    result["eta_basis"] = "program coverage is complete, but no group program ETA model is configured"
    result["eta_unavailable_reason"] = "program_eta_model_missing"
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
        "bottleneck": "",
        "eta_mode": "unknown",
    }
    if not meta:
        result["eta_basis"] = "no design coverage registry configured"
        result["eta_unavailable_reason"] = "no_design_registry"
        return result
    if remaining_weight <= 0:
        result.update(
            {
                "estimated_remaining_seconds": 0,
                "eta_at": iso(now),
                "eta_human": "0s",
                "eta_basis": "weighted design milestones and uncovered scope are complete",
                "confidence": "high" if bool(meta.get("design_coverage_complete")) else "medium",
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
        result["bottleneck"] = "coverage_materialization" if uncovered_scope_count > 0 else ("blocked_execution" if blocked_weight > 0 else "delivery_velocity")
        return result
    coverage_complete = bool(meta.get("milestone_coverage_complete")) and bool(meta.get("design_coverage_complete"))
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


class GitHubRateLimitError(RuntimeError):
    def __init__(self, message: str, *, reset_at: Optional[dt.datetime] = None):
        super().__init__(message)
        self.reset_at = reset_at


@dataclass
class DispatchCandidate:
    row: sqlite3.Row
    project_cfg: Dict[str, Any]
    queue: List[Any]
    queue_index: int
    slice_item: Any
    slice_name: Optional[str]
    task_meta: Dict[str, Any]
    runtime_status: str
    cooldown_until: Optional[dt.datetime]
    dispatchable: bool


@dataclass
class PlannedLaunch:
    project_id: str
    candidate: DispatchCandidate
    decision: Dict[str, Any]
    account_alias: str
    selected_model: str
    selection_note: str
    selection_trace: List[Dict[str, Any]]


def plan_candidate_launch(
    config: Dict[str, Any],
    candidate: DispatchCandidate,
    *,
    reserved_account_counts: Optional[Dict[str, int]] = None,
) -> Optional[PlannedLaunch]:
    project_id = str(candidate.project_cfg["id"])
    if not candidate.dispatchable or not candidate.slice_name:
        return None
    feedback_files = selected_feedback_files(config, candidate.project_cfg)
    decision = classify_tier(config, candidate.project_cfg, candidate.row, candidate.slice_item, feedback_files)
    alias, selected_model, selection_note, selection_trace = pick_account_and_model(
        config,
        candidate.project_cfg,
        decision,
        reserved_account_counts=reserved_account_counts,
    )
    if not alias or not selected_model:
        update_project_status(
            project_id,
            status="awaiting_account",
            current_slice=candidate.slice_name,
            active_run_id=None,
            cooldown_until=None,
            last_run_at=parse_iso(candidate.row["last_run_at"]),
            last_error=selection_note,
            consecutive_failures=candidate.row["consecutive_failures"],
            spider_tier=decision["tier"],
            spider_model=None,
            spider_reason=decision["reason"],
        )
        return None
    return PlannedLaunch(
        project_id=project_id,
        candidate=candidate,
        decision=decision,
        account_alias=alias,
        selected_model=selected_model,
        selection_note=selection_note,
        selection_trace=selection_trace,
    )


def gate_clearing_priority(candidate: DispatchCandidate) -> Tuple[int, int, int, str]:
    status = str(candidate.runtime_status or "").strip().lower()
    slice_name = str(candidate.slice_name or "")
    if status == "review_fix_required":
        bucket = 0
    elif status == "blocked":
        bucket = 1
    elif is_contract_remediation_slice(slice_name):
        bucket = 2
    else:
        bucket = 3
    return (
        bucket,
        -project_dispatch_priority(candidate.project_cfg),
        int(candidate.queue_index),
        str(candidate.project_cfg.get("id") or ""),
    )


def dispatch_backfill_priority(
    *,
    config: Dict[str, Any],
    row: sqlite3.Row,
    candidate: Optional[DispatchCandidate],
    running_by_group: Dict[str, int],
    pressure_high: bool,
) -> Tuple[Any, ...]:
    group_cfg = (project_group_defs(config, row["id"]) or [{"id": f"solo-{row['id']}", "captain": DEFAULT_CAPTAIN_POLICY}])[0]
    candidate_priority = gate_clearing_priority(candidate) if candidate else (99, 0, 999999, str(row["id"] or ""))
    return (
        candidate_priority[0],
        captain_dispatch_key(group_cfg=group_cfg, running_by_group=running_by_group, pressure_high=pressure_high),
        candidate_priority[1],
        candidate_priority[2],
        candidate_priority[3],
    )


def named_bridge_aliases(config: Dict[str, Any]) -> List[str]:
    return [str(service.get("primary_alias") or "").strip() for service in bridge_service_definitions(config)]


def candidate_supports_any_alias(candidate: Optional[DispatchCandidate], aliases: set[str]) -> bool:
    if not candidate or not aliases:
        return False
    return any(alias in aliases for alias in ordered_project_aliases(candidate.project_cfg))


def select_lockstep_wave_candidates(
    *,
    group: Dict[str, Any],
    group_meta: Dict[str, Any],
    member_ids: List[str],
    candidates: Dict[str, DispatchCandidate],
    available_slots: int,
) -> List[str]:
    if available_slots <= 0:
        return []
    if str(group.get("mode", "") or "").strip().lower() != "lockstep":
        return []
    has_contract_blockers = bool(text_items(group_meta.get("contract_blockers")))
    gated_members = [
        project_id
        for project_id in member_ids
        if not candidates.get(project_id) or not candidates[project_id].dispatchable or not candidates[project_id].slice_name
    ]
    slot_limited = len(member_ids) > available_slots
    if not has_contract_blockers and not gated_members and not slot_limited:
        return []
    dispatchable_ids = [
        project_id
        for project_id in member_ids
        if candidates.get(project_id) and candidates[project_id].dispatchable and candidates[project_id].slice_name
    ]
    if not dispatchable_ids:
        return []
    preferred_ids = [
        project_id
        for project_id in dispatchable_ids
        if str(candidates[project_id].runtime_status or "").strip().lower() == "review_fix_required"
        or is_contract_remediation_slice(candidates[project_id].slice_name or "")
    ]
    selected_pool = preferred_ids or dispatchable_ids
    ordered = sorted(selected_pool, key=lambda project_id: gate_clearing_priority(candidates[project_id]))
    return ordered[:available_slots]


def get_project_cfg(config: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    for project in config.get("projects", []):
        if project["id"] == project_id:
            return project
    raise KeyError(project_id)


def studio_published_root(project_cfg: Dict[str, Any]) -> pathlib.Path:
    return pathlib.Path(project_cfg["path"]) / STUDIO_PUBLISHED_DIRNAME


def studio_published_files(project_cfg: Dict[str, Any]) -> List[pathlib.Path]:
    root = studio_published_root(project_cfg)
    files: List[pathlib.Path] = []
    for name in STUDIO_PUBLISHED_FILES:
        path = root / name
        if path.exists() and path.is_file():
            files.append(path)
    return files


def apply_queue_overlay(project_cfg: Dict[str, Any], queue: List[str]) -> List[str]:
    overlay_path = studio_published_root(project_cfg) / "QUEUE.generated.yaml"
    if not overlay_path.exists() or not overlay_path.is_file():
        return queue
    try:
        data = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return queue
    if isinstance(data, list):
        items = [str(item).strip() for item in data if str(item).strip()]
        mode = "append"
    elif isinstance(data, dict):
        mode = str(data.get("mode", "append")).strip().lower() or "append"
        raw_items = data.get("items")
        if raw_items is None:
            raw_items = data.get("queue")
        items = [str(item).strip() for item in (raw_items or []) if str(item).strip()]
    else:
        return queue
    if not items:
        return queue
    if mode == "replace":
        return items
    if mode == "prepend":
        return items + list(queue)
    return list(queue) + items


def resolve_project_queue(project_cfg: Dict[str, Any]) -> List[str]:
    queue = list(project_cfg.get("queue") or [])
    for source_cfg in project_cfg.get("queue_sources") or []:
        queue = apply_queue_source(project_cfg, queue, source_cfg)
    return apply_queue_overlay(project_cfg, queue)


def apply_queue_source(project_cfg: Dict[str, Any], queue: List[str], source_cfg: Dict[str, Any]) -> List[str]:
    fallback_only_if_empty = bool(source_cfg.get("fallback_only_if_empty"))
    if fallback_only_if_empty and queue:
        return list(queue)

    items = load_queue_source_items(project_cfg, source_cfg)
    mode = str(source_cfg.get("mode", "append")).strip().lower() or "append"
    if mode == "replace":
        return items
    if mode == "prepend":
        return items + list(queue)
    return list(queue) + items


def load_queue_source_items(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    kind = str(source_cfg.get("kind", "") or "").strip().lower()
    if kind == "worklist":
        return load_worklist_queue(project_cfg, source_cfg)
    if kind == "tasks_work_log":
        return load_tasks_work_log_queue(project_cfg, source_cfg)
    if kind == "milestone_capabilities":
        return load_milestone_capability_queue(project_cfg, source_cfg)
    return []


def resolve_project_file(project_cfg: Dict[str, Any], source_path: str) -> pathlib.Path:
    path = pathlib.Path(str(source_path or "").strip())
    if path.is_absolute():
        return path
    return pathlib.Path(project_cfg["path"]) / path


def markdown_table_cells(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


WORKLIST_CHECKLIST_RE = re.compile(
    r"^\s*[-*]\s+\[(?P<status>[^\]]+)\]\s+(?:(?P<task_id>[A-Za-z0-9._-]+)\s+)?(?P<task>.+?)\s*$"
)


def normalized_backlog_task_key(task: str) -> str:
    return " ".join(str(task or "").strip().strip("`").split()).lower()


def select_latest_active_tasks(entries: List[Tuple[str, str]]) -> List[str]:
    latest_status_by_key: Dict[str, str] = {}
    latest_task_by_key: Dict[str, str] = {}
    latest_order_by_key: Dict[str, int] = {}
    ordered_keys: List[str] = []

    for order, (status, task) in enumerate(entries):
        task_text = str(task or "").strip().strip("`")
        if not task_text or task_text.startswith("<"):
            continue
        key = normalized_backlog_task_key(task_text)
        if not key:
            continue
        latest_status_by_key[key] = str(status or "").strip().lower().replace("_", " ")
        latest_task_by_key[key] = task_text
        latest_order_by_key[key] = order
        if key not in ordered_keys:
            ordered_keys.append(key)

    active_items: List[Tuple[int, str]] = []
    for key in ordered_keys:
        if latest_status_by_key.get(key) in ACTIVE_QUEUE_STATUSES:
            active_items.append((int(latest_order_by_key.get(key, 0)), latest_task_by_key.get(key, "")))

    active_items.sort(key=lambda item: item[0])
    return [task for _, task in active_items if task]


def load_worklist_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = resolve_project_file(project_cfg, str(source_cfg.get("path", "WORKLIST.md")))
    if not path.exists() or not path.is_file():
        return []

    entries: List[Tuple[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    for line in lines:
        cells = markdown_table_cells(line)
        if len(cells) >= 6:
            task_id = cells[0].strip("` ").lower()
            status = cells[1].strip("` ").strip().lower().replace("_", " ")
            task = cells[3].strip("` ").strip()
            if task_id in {"id", "---"} or not task_id.startswith("wl-"):
                continue
            entries.append((status, task))
            continue
        match = WORKLIST_CHECKLIST_RE.match(line)
        if not match:
            continue
        status = str(match.group("status") or "").strip().lower().replace("_", " ")
        task = str(match.group("task") or "").strip().strip("`")
        entries.append((status, task))
    return select_latest_active_tasks(entries)


def load_tasks_work_log_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = resolve_project_file(project_cfg, str(source_cfg.get("path", "TASKS_WORK_LOG.md")))
    if not path.exists() or not path.is_file():
        return []

    items: List[str] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    for line in lines:
        cells = markdown_table_cells(line)
        if len(cells) < 5:
            continue
        task_id = cells[0].strip("` ").lower()
        task = cells[2].strip("` ").strip()
        status = cells[4].strip("` ").strip().lower().replace("_", " ")
        if task_id in {"id", "---"} or task.startswith("<"):
            continue
        if task_id.startswith("q-") or status in ACTIVE_QUEUE_STATUSES:
            if task and task not in seen:
                items.append(task)
                seen.add(task)
    return items


def load_milestone_capability_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = resolve_project_file(project_cfg, str(source_cfg.get("path", "MILESTONE.json")))
    if not path.exists() or not path.is_file():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    include_statuses = {
        str(status).strip().lower()
        for status in (source_cfg.get("include_statuses") or [])
        if str(status).strip()
    }
    exclude_statuses = {
        str(status).strip().lower()
        for status in (source_cfg.get("exclude_statuses") or MILESTONE_TERMINAL_STATUSES)
        if str(status).strip()
    }
    label_prefix = str(source_cfg.get("label_prefix", "Promote milestone capability: ")).strip()

    items: List[str] = []
    seen: set[str] = set()
    for capability in data.get("capabilities") or []:
        if not isinstance(capability, dict):
            continue
        status = str(capability.get("status", "")).strip().lower()
        if include_statuses and status not in include_statuses:
            continue
        if status in exclude_statuses:
            continue
        name = str(capability.get("name", "")).strip()
        if not name:
            continue
        label = f"{label_prefix}{name}"
        if label in seen:
            continue
        items.append(label)
        seen.add(label)
    return items


def project_queue_source_files(project_cfg: Dict[str, Any]) -> List[pathlib.Path]:
    files: List[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for source_cfg in project_cfg.get("queue_sources") or []:
        source_path = str(source_cfg.get("path", "") or "").strip()
        if not source_path:
            continue
        path = resolve_project_file(project_cfg, source_path)
        if not path.exists() or not path.is_file() or path in seen:
            continue
        files.append(path)
        seen.add(path)
    return files


def read_state_file(project_path: str, state_file: str) -> Dict[str, Any]:
    path = pathlib.Path(project_path) / state_file
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def unread_feedback_files(project_cfg: Dict[str, Any]) -> List[pathlib.Path]:
    repo = pathlib.Path(project_cfg["path"])
    feedback_dir = repo / project_cfg.get("feedback_dir", "feedback")
    applied_log = feedback_dir / ".applied.log"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    if not applied_log.exists():
        applied_log.touch()
    applied = {line.strip() for line in applied_log.read_text(encoding="utf-8").splitlines() if line.strip()}
    files: List[pathlib.Path] = []
    for child in feedback_dir.iterdir():
        if child.name in {"README.md", ".applied.log"} or not child.is_file():
            continue
        rel = f"feedback/{child.name}"
        if rel not in applied:
            files.append(child)
    files.sort(key=lambda path: (path.stat().st_mtime, path.name))
    return files


def selected_feedback_files(config: Dict[str, Any], project_cfg: Dict[str, Any]) -> List[pathlib.Path]:
    spider = project_cfg.get("spider") or config.get("spider") or DEFAULT_SPIDER
    limit = max(0, int(spider.get("feedback_file_window", 2) or 0))
    files = unread_feedback_files(project_cfg)
    if limit == 0:
        return []
    return files[:limit]


def mark_feedback_applied(project_cfg: Dict[str, Any], run_id: int, files: List[pathlib.Path]) -> None:
    if not files:
        return
    repo = pathlib.Path(project_cfg["path"])
    feedback_dir = repo / project_cfg.get("feedback_dir", "feedback")
    applied_log = feedback_dir / ".applied.log"
    existing = {line.strip() for line in applied_log.read_text(encoding="utf-8").splitlines() if line.strip()} if applied_log.exists() else set()
    new_lines = []
    for file_path in files:
        rel = f"feedback/{file_path.name}"
        if rel not in existing:
            new_lines.append(rel)
    if new_lines:
        with applied_log.open("a", encoding="utf-8") as f:
            for rel in new_lines:
                f.write(rel + "\n")
        now = iso(utc_now())
        with db() as conn:
            for rel in new_lines:
                conn.execute(
                    "INSERT OR REPLACE INTO feedback_history(project_id, rel_path, run_id, applied_at) VALUES (?, ?, ?, ?)",
                    (project_cfg["id"], rel, run_id, now),
                )


def prompt_instruction_items(project_cfg: Dict[str, Any]) -> List[str]:
    repo = pathlib.Path(project_cfg["path"])
    instructions: List[str] = []
    for rel in ["instructions.md", ".agent-memory.md", "AGENT_MEMORY.md", "audit.md"]:
        path = repo / rel
        if path.exists():
            instructions.append(rel)
    design_doc = project_cfg.get("design_doc", "")
    if design_doc:
        design_path = pathlib.Path(design_doc)
        instructions.append(design_doc if design_path.is_absolute() else design_path.name)
    instructions.extend(project_design_mirror_instruction_items(project_cfg))
    for path in project_queue_source_files(project_cfg):
        if path.is_absolute() and repo in path.parents:
            instructions.append(path.relative_to(repo).as_posix())
        else:
            instructions.append(str(path))
    for path in studio_published_files(project_cfg):
        instructions.append(path.relative_to(repo).as_posix())
    queue_overlay = studio_published_root(project_cfg) / "QUEUE.generated.yaml"
    if queue_overlay.exists():
        instructions.append(queue_overlay.relative_to(repo).as_posix())
    instructions.extend(["AGENTS.md if present", "unread feedback files in feedback/, oldest first"])
    return instructions


def build_prompt(project_cfg: Dict[str, Any], slice_name: str, decision: Dict[str, Any], feedback_files: List[pathlib.Path]) -> str:
    instructions = [f"- {item}" for item in prompt_instruction_items(project_cfg)]
    feedback_block = "No unread feedback files."
    runner = project_cfg.get("runner") or {}
    posture_lines: List[str] = []
    if bool(runner.get("always_continue", True)):
        posture_lines.append(
            "Continue autonomously through analysis, implementation, verification, and follow-up fixes until this slice is truly complete or blocked by missing information."
        )
    if bool(runner.get("avoid_permission_escalation", True)):
        posture_lines.append(
            "Avoid permission escalation. First take the largest sandbox-safe step available, and only report a precise blocker if the slice cannot move further without more access."
        )
    posture_lines.append(
        "Keep command output compact. Prefer quiet or minimal build and test flags, and avoid verbose diagnostics unless a smaller probe already failed."
    )
    if not posture_lines:
        posture_lines.append("Continue until the current slice is complete or truly blocked.")
    if feedback_files:
        rendered = []
        for path in feedback_files:
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as exc:
                content = f"<unable to read: {exc}>"
            rendered.append(f"## {path.name}\n{content}")
        feedback_block = "Unread feedback files to incorporate in order:\n\n" + "\n\n".join(rendered)

    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        instructions="\n".join(instructions),
        slice_name=slice_name,
        tier=decision["tier"],
        model=decision["selected_model"],
        reasoning_effort=decision["reasoning_effort"],
        reason=decision["reason"],
        worker_posture_block="\n".join(posture_lines),
        feedback_block=feedback_block,
    ) + "\n"
    return apply_codex_prompt_directives(prompt)


def estimate_prompt_chars(project_cfg: Dict[str, Any], slice_name: str, feedback_files: List[pathlib.Path]) -> int:
    total = len(SYSTEM_PROMPT_TEMPLATE) + len(slice_name) + len(project_cfg.get("id", "")) + len(project_cfg.get("path", ""))
    total += sum(len(directive) for directive in CODEX_PROMPT_DIRECTIVES) + 2
    total += 512
    for item in prompt_instruction_items(project_cfg):
        total += len(item) + 4
    for path in feedback_files:
        try:
            total += len(path.name) + len(path.read_text(encoding="utf-8")) + 8
        except Exception:
            total += 200
    return total


def contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def predict_changed_files(task_class: str) -> int:
    return {
        "inspect": 0,
        "draft": 1,
        "groundwork": 1,
        "micro_edit": 2,
        "bounded_fix": 3,
        "multi_file_impl": 6,
        "cross_repo_contract": 8,
    }.get(task_class, 4)


def promote_task_class(task_class: str) -> str:
    if task_class in {"inspect", "draft", "micro_edit"}:
        return "bounded_fix"
    if task_class == "bounded_fix":
        return "multi_file_impl"
    if task_class == "multi_file_impl":
        return "cross_repo_contract"
    return task_class


def route_class_evidence(window_runs: int = 120) -> Dict[str, Dict[str, Any]]:
    if not table_exists("runs"):
        return {}
    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                spider_tier,
                COUNT(*) AS run_count,
                SUM(CASE WHEN status='complete' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN status IN ('failed', 'abandoned', 'blocked', 'review_failed') THEN 1 ELSE 0 END) AS failure_count,
                AVG(
                    CASE
                        WHEN finished_at IS NOT NULL THEN (julianday(finished_at) - julianday(started_at)) * 86400.0
                        ELSE NULL
                    END
                ) AS avg_duration_seconds
            FROM (
                SELECT spider_tier, status, started_at, finished_at
                FROM runs
                WHERE spider_tier IS NOT NULL AND TRIM(spider_tier) != ''
                ORDER BY id DESC
                LIMIT ?
            ) recent
            GROUP BY spider_tier
            """,
            (max(1, int(window_runs)),),
        ).fetchall()
    evidence: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        tier = str(row["spider_tier"] or "").strip()
        if not tier:
            continue
        run_count = int(row["run_count"] or 0)
        success_count = int(row["success_count"] or 0)
        failure_count = int(row["failure_count"] or 0)
        evidence[tier] = {
            "run_count": run_count,
            "success_rate": round((success_count / run_count), 3) if run_count > 0 else None,
            "failure_rate": round((failure_count / run_count), 3) if run_count > 0 else None,
            "avg_duration_seconds": float(row["avg_duration_seconds"] or 0.0),
        }
    return evidence


def classify_tier(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    project_row: sqlite3.Row,
    slice_item: Any,
    feedback_files: List[pathlib.Path],
) -> Dict[str, Any]:
    spider = project_cfg.get("spider") or config.get("spider") or DEFAULT_SPIDER
    lanes = normalize_lanes_config(config.get("lanes"))
    task_meta = normalize_task_queue_item(slice_item, lanes=lanes)
    pr_row = pull_request_row(str(project_cfg.get("id") or "")) or {}
    review_status = str(pr_row.get("review_status") or "").strip().lower()
    review_attempts = int(pr_row.get("local_review_attempts") or 0)
    loop_stage = review_loop_stage(pr_row)
    _, review_focus_meta = decode_review_focus(str(pr_row.get("review_focus") or ""))
    if task_meta.get("workflow_kind") == "groundwork_review_loop":
        task_meta["review_round"] = int(pr_row.get("review_round") or review_attempts)
        task_meta["first_review_complete"] = bool(pr_row.get("first_review_complete_at")) or review_attempts > 0
        if bool(pr_row.get("needs_core_rescue")) or review_focus_meta.get("core_rescue_required") == "true":
            task_meta["needs_core_rescue"] = True
    slice_name = str(task_meta.get("title") or normalize_slice_text(slice_item) or "").strip()
    classification_mode = str(spider.get("classification_mode") or "evidence_v1").strip() or "evidence_v1"
    slice_text = str(slice_name or "").lower()
    prompt_chars = estimate_prompt_chars(project_cfg, slice_name, feedback_files)
    failures = int(project_row["consecutive_failures"] or 0)
    reason_parts: List[str] = []
    tier = "bounded_fix"

    inspect_hit = contains_any(slice_text, spider.get("inspect_keywords", []))
    draft_hit = contains_any(slice_text, spider.get("draft_keywords", []))
    groundwork_hit = contains_any(slice_text, spider.get("groundwork_keywords", []))
    micro_hit = contains_any(slice_text, spider.get("micro_edit_keywords", []))
    bounded_hit = contains_any(slice_text, spider.get("bounded_fix_keywords", []))
    impl_hit = contains_any(slice_text, spider.get("multi_file_impl_keywords", []))
    contract_hit = contains_any(slice_text, spider.get("cross_repo_contract_keywords", []))
    code_change_hit = bounded_hit or impl_hit or contract_hit or contains_any(
        slice_text,
        ["fix", "implement", "build", "wire", "normalize", "align", "refactor", "add ", "create ", "support "],
    )

    if contract_hit:
        tier = "cross_repo_contract"
        reason_parts.append("slice matches contract or lockstep keywords")
    elif groundwork_hit and not code_change_hit:
        tier = "groundwork"
        reason_parts.append("slice looks like complex non-urgent analysis")
    elif inspect_hit and not code_change_hit:
        tier = "inspect"
        reason_parts.append("slice is inspection or triage only")
    elif draft_hit and not code_change_hit:
        tier = "draft"
        reason_parts.append("slice is drafting or backlog decomposition")
    elif micro_hit and prompt_chars <= 12000 and len(feedback_files) <= 1:
        tier = "micro_edit"
        reason_parts.append("slice looks like a small bounded edit")
    elif bounded_hit:
        tier = "bounded_fix"
        reason_parts.append("slice looks like a bounded fix")
    elif impl_hit or code_change_hit:
        tier = "multi_file_impl"
        reason_parts.append("slice looks like a multi-file implementation")
    else:
        tier = "bounded_fix" if prompt_chars <= 16000 else "multi_file_impl"
        reason_parts.append("default route class from prompt size and coding scope")

    if len(feedback_files) >= 2 and tier in {"inspect", "draft", "micro_edit"}:
        tier = promote_task_class(tier)
        reason_parts.append("multiple injected feedback notes widen the coordination scope")

    if prompt_chars > 12000 and tier in {"inspect", "draft", "micro_edit"}:
        tier = promote_task_class(tier)
        reason_parts.append("prompt estimate widens the route class")
    if prompt_chars > 24000 and tier != "cross_repo_contract":
        tier = promote_task_class(tier)
        reason_parts.append("large prompt estimate escalates the route class")

    escalate_after = int(spider.get("escalate_to_complex_after_failures", 1))
    if failures >= escalate_after:
        tier = promote_task_class(tier)
        reason_parts.append(f"previous failure count {failures} promotes the route class")

    if classification_mode.startswith("evidence"):
        evidence = route_class_evidence(int(spider.get("evidence_window_runs") or 120))
        min_sample = max(3, int(spider.get("evidence_min_sample") or 6))
        tier_evidence = evidence.get(tier) or {}
        if int(tier_evidence.get("run_count") or 0) >= min_sample:
            reason_parts.append(
                f"recent {tier} evidence: success={tier_evidence.get('success_rate')} failure={tier_evidence.get('failure_rate')}"
            )
            if float(tier_evidence.get("failure_rate") or 0.0) >= 0.45 and tier not in {"cross_repo_contract", "inspect"}:
                promoted_tier = promote_task_class(tier)
                promoted_evidence = evidence.get(promoted_tier) or {}
                if promoted_tier != tier and (
                    int(promoted_evidence.get("run_count") or 0) < min_sample
                    or float(promoted_evidence.get("failure_rate") or 0.0) <= float(tier_evidence.get("failure_rate") or 0.0)
                ):
                    tier = promoted_tier
                    reason_parts.append("recent failure evidence promotes to a broader route class")

    difficulty = str(task_meta.get("difficulty") or "auto")
    risk_level = str(task_meta.get("risk_level") or "auto")
    branch_policy = str(task_meta.get("branch_policy") or "auto")
    acceptance_level = str(task_meta.get("acceptance_level") or "auto")
    if difficulty == "easy" and tier in {"multi_file_impl", "cross_repo_contract"}:
        tier = "bounded_fix"
        reason_parts.append("task difficulty marks this slice as easy")
    elif difficulty == "hard" and tier in {"inspect", "draft", "micro_edit", "bounded_fix"}:
        tier = "multi_file_impl"
        reason_parts.append("task difficulty marks this slice as hard")
    if risk_level == "high" and tier in {"inspect", "draft", "micro_edit", "bounded_fix"}:
        tier = "multi_file_impl"
        reason_parts.append("high risk forces core-grade implementation routing")
    if branch_policy == "protected_branch" or acceptance_level == "merge_ready":
        reason_parts.append("protected-branch or merge-ready policy requires core authority")

    tier_prefs = spider.get("tier_preferences", {}).get(tier, {})
    models = list(tier_prefs.get("models") or [])
    reasoning_effort = str(tier_prefs.get("reasoning_effort", "low"))
    est_prompt_tokens = max(256, int(prompt_chars / 4))
    est_output_tokens = int(tier_prefs.get("estimated_output_tokens", 1024))
    predicted_files = predict_changed_files(tier)
    requires_contract_authority = (
        tier == "cross_repo_contract"
        or branch_policy == "protected_branch"
        or acceptance_level == "merge_ready"
    )
    allowed_lanes = list(task_meta.get("allowed_lanes") or ["easy", "repair", "core"])
    if bool(task_meta.get("protected_runtime")):
        allowed_lanes = ["core"]
        requires_contract_authority = True
    if task_meta.get("workflow_kind") == "groundwork_review_loop":
        if loop_stage in {JURY_REWORK_REQUIRED_STATUS, CORE_RESCUE_PENDING_STATUS} or review_status == "review_fix_required":
            current_round = int(task_meta.get("review_round") or review_attempts or 0)
            reason_parts.append(f"jury loop round {current_round or 1} requested another implementation pass")
            if loop_stage == CORE_RESCUE_PENDING_STATUS or bool(task_meta.get("needs_core_rescue")) or current_round >= int(task_meta.get("core_rescue_after_round") or 3):
                allowed_lanes = ["core"]
                requires_contract_authority = True
                reason_parts.append("cheap jury loop exhausted or requested core rescue")
            elif "groundwork" in lanes:
                allowed_lanes = ["groundwork", *[lane for lane in allowed_lanes if lane != "groundwork"]]
        elif "groundwork" in lanes and "groundwork" not in allowed_lanes and "core" not in allowed_lanes:
            allowed_lanes = ["groundwork", *allowed_lanes]
    if tier == "groundwork" and "groundwork" in lanes and "groundwork" not in allowed_lanes:
        allowed_lanes = ["groundwork", *allowed_lanes]
    lane_preferences = ordered_lane_preferences(tier_prefs, allowed_lanes)
    if isinstance(slice_item, dict) and slice_item.get("allowed_lanes"):
        lane_preferences = [*allowed_lanes, *[lane for lane in lane_preferences if lane not in allowed_lanes]]
    preferred_lane = lane_preferences[0] if lane_preferences else "core"
    lane_submode = "mcp"
    escalation_reason = "cheap_first_default"
    if preferred_lane == "jury":
        lane_submode = "responses_audit"
        escalation_reason = "audit_or_risk_signal"
    elif tier == "groundwork" and "groundwork" in lanes and "groundwork" in allowed_lanes:
        preferred_lane = "groundwork"
        lane_submode = "responses_groundwork"
        escalation_reason = "complex_nonurgent_analysis"
        reasoning_effort = "medium"
    elif preferred_lane == "groundwork":
        lane_submode = "responses_groundwork"
        escalation_reason = "groundwork_policy_default"
        reasoning_effort = "medium"
    elif preferred_lane == "easy" and tier in {"bounded_fix", "micro_edit"} and "repair" in allowed_lanes:
        preferred_lane = "repair"
        lane_submode = "responses_fast"
        escalation_reason = "bounded_patch_generation"
    if preferred_lane in {"easy", "repair"} and (
        tier in {"multi_file_impl", "cross_repo_contract"}
        or risk_level in {"medium", "high"}
        or requires_contract_authority
    ) and "core" in allowed_lanes:
        preferred_lane = "core"
        lane_submode = "responses_hard"
        escalation_reason = "high_risk_scope"
    elif preferred_lane == "easy":
        lane_submode = "mcp"
        escalation_reason = "interactive_or_first_pass"
    elif preferred_lane == "repair":
        lane_submode = "responses_fast"
        escalation_reason = "bounded_patch_generation"
    lane_snapshots = ea_lane_capacity_snapshot(lanes)
    primary_lane_before_capacity = preferred_lane
    easy_snapshot = lane_snapshots.get("easy") or {}
    repair_snapshot = lane_snapshots.get("repair") or {}
    groundwork_snapshot = lane_snapshots.get("groundwork") or {}
    core_snapshot = lane_snapshots.get("core") or {}
    survival_snapshot = lane_snapshots.get("survival") or {}
    task_low_risk = (
        risk_level in {"auto", "low"}
        and not requires_contract_authority
        and acceptance_level not in {"reviewed", "merge_ready"}
    )
    if preferred_lane == "groundwork" and not lane_capacity_available(groundwork_snapshot):
        if "easy" in allowed_lanes and lane_capacity_available(easy_snapshot):
            preferred_lane = "easy"
            lane_submode = "mcp"
            escalation_reason = "groundwork_capacity_shifted_to_easy"
        elif "repair" in allowed_lanes and lane_capacity_available(repair_snapshot):
            preferred_lane = "repair"
            lane_submode = "responses_fast"
            escalation_reason = "groundwork_capacity_shifted_to_repair"
        elif "core" in allowed_lanes and lane_capacity_available(core_snapshot):
            preferred_lane = "core"
            lane_submode = "responses_hard"
            escalation_reason = "groundwork_capacity_shifted_to_core"
    if preferred_lane == "core" and task_low_risk and (not lane_capacity_available(core_snapshot) or lane_capacity_tight(core_snapshot)):
        if "repair" in allowed_lanes and lane_capacity_available(repair_snapshot):
            preferred_lane = "repair"
            lane_submode = "responses_fast"
            escalation_reason = "core_capacity_tight_demoted_to_repair"
        elif "easy" in allowed_lanes and lane_capacity_available(easy_snapshot):
            preferred_lane = "easy"
            lane_submode = "mcp"
            escalation_reason = "core_capacity_tight_demoted_to_easy"
    if preferred_lane in {"easy", "repair"}:
        current_snapshot = lane_snapshots.get(preferred_lane) or {}
        if not lane_capacity_available(current_snapshot):
            sibling_lane = "repair" if preferred_lane == "easy" else "easy"
            sibling_snapshot = lane_snapshots.get(sibling_lane) or {}
            if sibling_lane in allowed_lanes and lane_capacity_available(sibling_snapshot):
                preferred_lane = sibling_lane
                lane_submode = "responses_fast" if sibling_lane == "repair" else "mcp"
                escalation_reason = f"{primary_lane_before_capacity}_capacity_shifted_to_{sibling_lane}"
    if (
        preferred_lane in {"easy", "repair", "core"}
        and task_low_risk
        and "survival" not in allowed_lanes
        and lane_capacity_available(survival_snapshot)
    ):
        primary_snapshot = lane_snapshots.get(preferred_lane) or {}
        if not lane_capacity_available(primary_snapshot):
            allowed_lanes = [*allowed_lanes, "survival"]
    if preferred_lane in {"easy", "repair", "core"} and "survival" in allowed_lanes:
        primary_snapshot = lane_snapshots.get(preferred_lane) or {}
        if not lane_capacity_available(primary_snapshot) and lane_capacity_available(survival_snapshot):
            preferred_lane = "survival"
            lane_submode = "responses_survival"
            escalation_reason = "capacity_exhausted_survival_fallback"
    spark_eligible = (
        tier in {"micro_edit", "bounded_fix"}
        and predicted_files <= 3
        and failures == 0
        and len(feedback_files) <= 1
        and prompt_chars <= 12000
        and not requires_contract_authority
        and preferred_lane == "easy"
    )
    if not spark_eligible:
        models = [model for model in models if model != SPARK_MODEL]
    lane_runtime_model = str((lanes.get(preferred_lane) or {}).get("runtime_model") or "").strip()
    if lane_runtime_model:
        models = [lane_runtime_model, *[model for model in models if model != lane_runtime_model]]
    selected_profile = EA_PROFILE_NAME_BY_LANE.get(preferred_lane, preferred_lane)
    lane_capacity = lane_snapshots.get(preferred_lane) or {}
    why_not_cheaper = why_not_cheaper_lane(
        preferred_lane,
        allowed_lanes=allowed_lanes,
        tier=tier,
        escalation_reason=escalation_reason,
        requires_contract_authority=requires_contract_authority,
        task_meta=task_meta,
        lane_snapshots=lane_snapshots,
    )
    expected_allowance_burn = lane_allowance_burn_snapshot(preferred_lane, lanes, lane_capacity)
    signoff_requirements = [str(item).strip() for item in task_meta.get("signoff_requirements") or [] if str(item).strip()]
    reason_parts.append(f"predicted changed files: {predicted_files}")
    reason_parts.append("spark eligible" if spark_eligible else "spark not eligible")
    reason_parts.append(f"allowed lanes: {', '.join(allowed_lanes)}")
    reason_parts.append(f"lane preferences: {', '.join(lane_preferences)}")
    reason_parts.append(f"selected lane: {preferred_lane}")
    reason_parts.append(f"selected profile: {selected_profile}")
    reason_parts.append(f"lane submode: {lane_submode}")
    reason_parts.append(f"why not cheaper: {why_not_cheaper}")
    if signoff_requirements:
        reason_parts.append(f"signoff requirements: {', '.join(signoff_requirements)}")
    if lane_snapshots:
        reason_parts.append(f"lane capacity state: {str(lane_capacity.get('state') or 'unknown')}")
        remaining = lane_snapshot_remaining_percent(lane_capacity)
        if remaining is not None:
            reason_parts.append(f"lane remaining percent: {remaining:.1f}")

    return {
        "tier": tier,
        "model_preferences": models,
        "reasoning_effort": reasoning_effort,
        "reason": "; ".join(reason_parts),
        "estimated_prompt_chars": prompt_chars,
        "estimated_input_tokens": est_prompt_tokens,
        "estimated_output_tokens": est_output_tokens,
        "predicted_changed_files": predicted_files,
        "requires_contract_authority": requires_contract_authority,
        "lane": preferred_lane,
        "lane_submode": lane_submode,
        "selected_profile": selected_profile,
        "why_not_cheaper": why_not_cheaper,
        "escalation_reason": escalation_reason,
        "expected_allowance_burn": expected_allowance_burn,
        "allowed_lanes": allowed_lanes,
        "required_reviewer_lane": str(task_meta.get("required_reviewer_lane") or lanes["core"]["id"]),
        "final_reviewer_lane": str(task_meta.get("final_reviewer_lane") or ""),
        "task_meta": task_meta,
        "runtime_model": str((lanes.get(preferred_lane) or {}).get("runtime_model") or ""),
        "spark_eligible": spark_eligible,
        "lane_capacity": lane_capacity,
    }


def estimate_cost_usd_for_model(price_table: Dict[str, Any], model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> Optional[float]:
    pricing = price_table.get(model)
    if not pricing:
        return None
    uncached = max(input_tokens - cached_input_tokens, 0)
    return round(
        (uncached / 1_000_000) * float(pricing["input"])
        + (cached_input_tokens / 1_000_000) * float(pricing["cached_input"])
        + (output_tokens / 1_000_000) * float(pricing["output"]),
        6,
    )


def usage_for_account(alias: str, period: str) -> Dict[str, float]:
    now = utc_now()
    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(period)
    with db() as conn:
        row = conn.execute(
            """
            SELECT
              COALESCE(SUM(input_tokens), 0) AS input_tokens,
              COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
              COALESCE(SUM(output_tokens), 0) AS output_tokens,
              COALESCE(SUM(estimated_cost_usd), 0.0) AS cost
            FROM runs
            WHERE account_alias=? AND started_at >= ?
            """,
            (alias, iso(start)),
        ).fetchone()
    return dict(row) if row else {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "cost": 0.0}


def active_run_count_for_account(alias: str) -> int:
    with db() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM runs
            WHERE account_alias=?
              AND status IN ('starting', 'running')
              AND COALESCE(NULLIF(TRIM(job_kind), ''), 'coding') IN ('coding', 'healing', 'local_review')
            """,
            (alias,),
        ).fetchone()
    return int(row[0] if row else 0)


def active_run_count_for_aliases(aliases: Sequence[str]) -> int:
    clean_aliases = [str(alias or "").strip() for alias in aliases if str(alias or "").strip()]
    if not clean_aliases:
        return 0
    placeholders = ",".join("?" for _ in clean_aliases)
    with db() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM runs
            WHERE account_alias IN ({placeholders})
              AND status IN ('starting', 'running')
              AND COALESCE(NULLIF(TRIM(job_kind), ''), 'coding') IN ('coding', 'healing', 'local_review')
            """,
            tuple(clean_aliases),
        ).fetchone()
    return int(row[0] if row else 0)


def account_execution_family(account_alias: str) -> str:
    alias = str(account_alias or "").strip().lower()
    if alias.startswith("acct-ea-"):
        return "ea"
    return "codex_user"


def active_run_families_for_aliases(aliases: Sequence[str]) -> set[str]:
    clean_aliases = [str(alias or "").strip() for alias in aliases if str(alias or "").strip()]
    if not clean_aliases:
        return set()
    placeholders = ",".join("?" for _ in clean_aliases)
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT account_alias
            FROM runs
            WHERE account_alias IN ({placeholders})
              AND status IN ('starting', 'running', 'verifying')
              AND COALESCE(NULLIF(TRIM(job_kind), ''), 'coding') IN ('coding', 'healing', 'local_review')
            """,
            tuple(clean_aliases),
        ).fetchall()
    return {account_execution_family(row["account_alias"]) for row in rows if row["account_alias"]}


def record_account_selection(alias: str, model: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE accounts SET last_selected_model=?, updated_at=? WHERE alias=?",
            (str(model or "").strip(), iso(utc_now()), alias),
        )


def record_account_run_outcome(alias: str, model: str, *, success: bool) -> None:
    timestamp = iso(utc_now())
    with db() as conn:
        existing = conn.execute(
            "SELECT auth_kind, capability_models_json FROM accounts WHERE alias=?",
            (alias,),
        ).fetchone()
        capability_models = normalize_allowed_models_for_account(
            str(existing["auth_kind"] or "api_key") if existing else "api_key",
            json_field(existing["capability_models_json"], []) if existing else [],
        )
        if success and str(model or "").strip() and model not in capability_models:
            capability_models.append(str(model).strip())
        if success:
            conn.execute(
                """
                UPDATE accounts
                SET success_count=COALESCE(success_count, 0) + 1,
                    capability_models_json=?,
                    capability_checked_at=?,
                    capability_status='observed_success',
                    last_selected_model=?,
                    last_model_success_at=?,
                    updated_at=?
                WHERE alias=?
                """,
                (json.dumps(capability_models), timestamp, str(model or "").strip(), timestamp, timestamp, alias),
            )
        else:
            conn.execute(
                """
                UPDATE accounts
                SET failure_count=COALESCE(failure_count, 0) + 1,
                    capability_checked_at=?,
                    capability_status='observed_failure',
                    last_selected_model=?,
                    last_model_failure_at=?,
                    updated_at=?
                WHERE alias=?
                """,
                (timestamp, str(model or "").strip(), timestamp, timestamp, alias),
            )


def account_model_evidence(alias: str, model: str, *, lookback_hours: int = 168) -> Dict[str, Any]:
    start = iso(utc_now() - dt.timedelta(hours=max(1, int(lookback_hours))))
    with db() as conn:
        row = conn.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN status IN ('complete', 'awaiting_review') THEN 1 ELSE 0 END), 0) AS successes,
              COALESCE(SUM(CASE WHEN status IN ('failed', 'review_failed', 'rate_limited', 'rejected', 'abandoned') THEN 1 ELSE 0 END), 0) AS failures,
              MAX(CASE WHEN status IN ('complete', 'awaiting_review') THEN finished_at ELSE NULL END) AS last_success_at,
              MAX(CASE WHEN status IN ('failed', 'review_failed', 'rate_limited', 'rejected', 'abandoned') THEN finished_at ELSE NULL END) AS last_failure_at
            FROM runs
            WHERE account_alias=?
              AND model=?
              AND started_at >= ?
            """,
            (alias, model, start),
        ).fetchone()
    return {
        "successes": int((row["successes"] if row else 0) or 0),
        "failures": int((row["failures"] if row else 0) or 0),
        "last_success_at": row["last_success_at"] if row else None,
        "last_failure_at": row["last_failure_at"] if row else None,
    }


def update_project_status(
    project_id: str,
    *,
    status: str,
    current_slice: Optional[str],
    active_run_id: Optional[int],
    cooldown_until: Optional[dt.datetime],
    last_run_at: Optional[dt.datetime],
    last_error: Optional[str] = None,
    consecutive_failures: Optional[int] = None,
    spider_tier: Optional[str] = None,
    spider_model: Optional[str] = None,
    spider_reason: Optional[str] = None,
) -> None:
    previous_status = ""
    with db() as conn:
        row = conn.execute("SELECT status, consecutive_failures FROM projects WHERE id=?", (project_id,)).fetchone()
        previous_status = str((row["status"] if row else "") or "").strip()
        failures = row["consecutive_failures"] if row else 0
        if consecutive_failures is not None:
            failures = consecutive_failures
        conn.execute(
            """
            UPDATE projects
            SET status=?, current_slice=?, active_run_id=?, cooldown_until=?, last_run_at=?, last_error=?, consecutive_failures=?, spider_tier=?, spider_model=?, spider_reason=?, updated_at=?
            WHERE id=?
            """,
            (
                status,
                current_slice,
                active_run_id,
                iso(cooldown_until),
                iso(last_run_at),
                last_error,
                failures,
                spider_tier,
                spider_model,
                spider_reason,
                iso(utc_now()),
                project_id,
            ),
        )
    if status == "blocked" and previous_status != "blocked":
        handle_blocked_incidents(project_id, current_slice=current_slice, last_error=last_error)
    elif status != "blocked":
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[BLOCKED_UNRESOLVED_INCIDENT_KIND])
        for group in project_group_defs(normalize_config(), project_id):
            group_id = str(group.get("id") or "").strip()
            if group_id:
                resolve_incidents(scope_type="group", scope_id=group_id, incident_kinds=[BLOCKED_UNRESOLVED_INCIDENT_KIND])
    if status in {"review_failed", "review_fix_required"} or previous_status in {"review_failed", "review_fix_required"}:
        handle_review_incidents(project_id, status=status, current_slice=current_slice, last_error=last_error)


def increment_queue(project_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE projects SET queue_index = queue_index + 1, consecutive_failures = 0, updated_at=? WHERE id=?",
            (iso(utc_now()), project_id),
        )


def set_account_backoff(alias: str, backoff_until: Optional[dt.datetime], last_error: Optional[str] = None, touch_last_used: bool = False) -> None:
    aliases = account_source_aliases(alias) or [str(alias or "").strip()]
    if not aliases:
        return
    with db() as conn:
        now_iso = iso(utc_now())
        placeholders = ",".join("?" for _ in aliases)
        if touch_last_used:
            conn.execute(
                f"UPDATE accounts SET backoff_until=?, last_error=?, last_used_at=?, updated_at=? WHERE alias IN ({placeholders})",
                (iso(backoff_until), last_error, now_iso, now_iso, *aliases),
            )
        else:
            conn.execute(
                f"UPDATE accounts SET backoff_until=?, last_error=?, updated_at=? WHERE alias IN ({placeholders})",
                (iso(backoff_until), last_error, now_iso, *aliases),
            )


def set_account_spark_backoff(alias: str, backoff_until: Optional[dt.datetime], last_error: Optional[str] = None) -> None:
    with db() as conn:
        row = conn.execute("SELECT auth_kind, auth_json_file FROM accounts WHERE alias=?", (alias,)).fetchone()
        if row and str(row["auth_kind"] or "") in CHATGPT_AUTH_KINDS and str(row["auth_json_file"] or "").strip():
            conn.execute(
                "UPDATE accounts SET spark_backoff_until=?, spark_last_error=?, updated_at=? WHERE auth_kind=? AND auth_json_file=?",
                (iso(backoff_until), last_error, iso(utc_now()), row["auth_kind"], row["auth_json_file"]),
            )
            return
        conn.execute(
            "UPDATE accounts SET spark_backoff_until=?, spark_last_error=?, updated_at=? WHERE alias=?",
            (iso(backoff_until), last_error, iso(utc_now()), alias),
        )


def normalize_usage_limit_account_backoffs(config: Dict[str, Any]) -> None:
    probe_seconds = max(300, int(get_policy(config, "chatgpt_usage_limit_probe_interval_seconds", 7200) or 7200))
    now = utc_now()
    with db() as conn:
        rows = conn.execute("SELECT alias, backoff_until, last_error FROM accounts ORDER BY alias").fetchall()
    for row in rows:
        alias = str(row["alias"] or "").strip()
        last_error = str(row["last_error"] or "")
        lower = last_error.lower()
        if "usage-limited" not in lower and "usage limit" not in lower:
            continue
        backoff_until = parse_iso(row["backoff_until"])
        if backoff_until is None or backoff_until <= now:
            continue
        reset_at = parse_usage_limit_reset_hint(last_error)
        reprobe_until = now + dt.timedelta(seconds=probe_seconds)
        target_until = min(backoff_until, reprobe_until)
        if reset_at is not None and reset_at < target_until:
            target_until = reset_at
        if abs((backoff_until - target_until).total_seconds()) < 60:
            continue
        message = (
            f"usage-limited; recheck at {iso(target_until)} (provider reset {iso(reset_at)})"
            if reset_at and reset_at > target_until
            else f"usage-limited until {iso(reset_at) or iso(target_until)}"
            if reset_at
            else f"usage-limited; recheck at {iso(target_until)}"
        )
        set_account_backoff(alias, target_until, message)


def touch_account(alias: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE accounts SET last_used_at=?, updated_at=? WHERE alias=?",
            (iso(utc_now()), iso(utc_now()), alias),
        )


def incident_context_for_project(project_id: str, *, current_slice: Optional[str], last_error: Optional[str]) -> Dict[str, Any]:
    pr = dict(pull_request_row(project_id) or {})
    group_ids = [str(group.get("id") or "").strip() for group in project_group_defs(normalize_config(), project_id)]
    return {
        "project_id": project_id,
        "group_ids": [item for item in group_ids if item],
        "current_slice": str(current_slice or "").strip(),
        "last_error": str(last_error or "").strip(),
        "pr_number": pr.get("pr_number"),
        "pr_url": pr.get("pr_url"),
        "review_mode": pr.get("review_mode"),
        "review_status": pr.get("review_status"),
        "review_requested_at": pr.get("review_requested_at"),
        "review_completed_at": pr.get("review_completed_at"),
        "review_findings_count": int(pr.get("review_findings_count") or 0),
        "review_blocking_findings_count": int(pr.get("review_blocking_findings_count") or 0),
        "review_sync_failures": int(pr.get("review_sync_failures") or 0),
        "review_retrigger_count": int(pr.get("review_retrigger_count") or 0),
        "last_retrigger_at": pr.get("last_retrigger_at"),
        "next_retry_at": pr.get("next_retry_at"),
        "review_rate_limit_reset_at": pr.get("review_rate_limit_reset_at"),
        "review_eta": review_eta_payload(pr, cooldown_until=pr.get("next_retry_at")),
    }


def is_transient_review_failure(error_text: str) -> bool:
    lower = str(error_text or "").lower()
    return any(
        marker in lower
        for marker in [
            "rate limit",
            "429",
            "secondary rate limit",
            "temporarily unavailable",
            "timed out",
            "timeout",
            "connection reset",
            "usage limit",
            "send a request to your admin",
            "worker session went stale",
            "stale_heartbeat",
        ]
    )


def is_retryable_push_rejection(error_text: str) -> bool:
    lower = str(error_text or "").lower()
    return "failed to push some refs" in lower or "fetch first" in lower


def handle_review_incidents(project_id: str, *, status: str, current_slice: Optional[str], last_error: Optional[str]) -> None:
    context = incident_context_for_project(project_id, current_slice=current_slice, last_error=last_error)
    if status == "review_failed":
        failures = int(context.get("review_sync_failures") or 0)
        transient = is_transient_review_failure(str(context.get("last_error") or ""))
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_STALLED_INCIDENT_KIND])
        if failures < REVIEW_FAILURE_INCIDENT_THRESHOLD or transient:
            resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_FAILED_INCIDENT_KIND])
            return
        context["operator_required"] = True
        context["can_resolve"] = False
        context["transient"] = transient
        open_or_update_incident(
            scope_type="project",
            scope_id=project_id,
            incident_kind=REVIEW_FAILED_INCIDENT_KIND,
            severity="critical",
            title=f"{project_id} review failed",
            summary="GitHub review orchestration has failed repeatedly and the healer has not recovered the review lane yet.",
            context=context,
        )
        return
    if status == "review_fix_required":
        resolve_incidents(
            scope_type="project",
            scope_id=project_id,
            incident_kinds=[REVIEW_FAILED_INCIDENT_KIND, REVIEW_STALLED_INCIDENT_KIND],
        )
        return
    resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_FAILED_INCIDENT_KIND])


def review_request_stalled(project_id: str, *, now: Optional[dt.datetime] = None) -> bool:
    pr = pull_request_row(project_id)
    if not pr:
        return False
    review_status = str(pr["review_status"] or "").strip().lower()
    if review_status not in REVIEW_WAITING_STATUSES:
        return False
    if parse_iso(pr["review_completed_at"]):
        return False
    review_eta = review_eta_payload(pr, cooldown_until=pr.get("next_retry_at"), now=now)
    reset_at = parse_iso(str(review_eta.get("reset_at") or ""))
    if bool(review_eta.get("throttled")) and reset_at and reset_at > (now or utc_now()):
        return False
    requested_at = review_hold_requested_at(pr_row=pr)
    if not requested_at:
        return False
    current = now or utc_now()
    stall_minutes = int(get_policy(normalize_config(), "review_stall_sla_minutes", 10))
    return requested_at <= current - dt.timedelta(minutes=max(1, stall_minutes))


def handle_review_lane_incidents(project_id: str, *, status: str, current_slice: Optional[str], last_error: Optional[str]) -> None:
    if status not in REVIEW_HOLD_STATUSES:
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_STALLED_INCIDENT_KIND])
        return
    pr = pull_request_row(project_id) or {}
    review_eta = review_eta_payload(pr, cooldown_until=pr.get("next_retry_at"))
    reset_at = parse_iso(str(review_eta.get("reset_at") or ""))
    if bool(review_eta.get("throttled")) and reset_at and reset_at > utc_now():
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_STALLED_INCIDENT_KIND])
        return
    if not review_request_stalled(project_id):
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_STALLED_INCIDENT_KIND])
        return
    context = incident_context_for_project(project_id, current_slice=current_slice, last_error=last_error)
    max_retriggers = max(0, get_int_policy(normalize_config(), "max_review_retriggers_per_head", 3))
    retrigger_count = int(context.get("review_retrigger_count") or 0)
    if retrigger_count < max_retriggers:
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_STALLED_INCIDENT_KIND])
        return
    context["operator_required"] = True
    context["can_resolve"] = False
    context["max_review_retriggers_per_head"] = max_retriggers
    open_or_update_incident(
        scope_type="project",
        scope_id=project_id,
        incident_kind=REVIEW_STALLED_INCIDENT_KIND,
        severity="high",
        title=f"{project_id} review lane stalled",
        summary="GitHub review was requested repeatedly, but no Codex review landed within the configured SLA and retry budget.",
        context=context,
    )


def handle_blocked_incidents(project_id: str, *, current_slice: Optional[str], last_error: Optional[str]) -> None:
    config = normalize_config()
    group_ids = [str(group.get("id") or "").strip() for group in project_group_defs(config, project_id) if str(group.get("id") or "").strip()]
    results: List[Dict[str, Any]] = [trigger_auditor_run_now(scope_type="project", scope_id=project_id)]
    results.extend(trigger_auditor_run_now(scope_type="group", scope_id=group_id) for group_id in group_ids)
    can_resolve = any(bool(item.get("can_resolve")) for item in results)
    context = incident_context_for_project(project_id, current_slice=current_slice, last_error=last_error)
    context["targeted_auditor_results"] = results
    context["can_resolve"] = can_resolve
    if can_resolve:
        with db() as conn:
            project_row = conn.execute(
                "SELECT spider_tier, spider_model, spider_reason FROM projects WHERE id=?",
                (project_id,),
            ).fetchone()
        update_project_status(
            project_id,
            status=HEALING_STATUS,
            current_slice=current_slice,
            active_run_id=None,
            cooldown_until=utc_now() + dt.timedelta(seconds=1),
            last_run_at=utc_now(),
            last_error=last_error,
            spider_tier=project_row["spider_tier"] if project_row else None,
            spider_model=project_row["spider_model"] if project_row else None,
            spider_reason=project_row["spider_reason"] if project_row else None,
        )
        resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[BLOCKED_UNRESOLVED_INCIDENT_KIND])
        for group_id in group_ids:
            resolve_incidents(scope_type="group", scope_id=group_id, incident_kinds=[BLOCKED_UNRESOLVED_INCIDENT_KIND])
        return
    open_or_update_incident(
        scope_type="project",
        scope_id=project_id,
        incident_kind=BLOCKED_UNRESOLVED_INCIDENT_KIND,
        severity="high",
        title=f"{project_id} is blocked and unresolved",
        summary="Repeated failures blocked execution and the targeted auditor could not produce a publishable resolution.",
        context=context,
    )
    for group_id in group_ids:
        open_or_update_incident(
            scope_type="group",
            scope_id=group_id,
            incident_kind=BLOCKED_UNRESOLVED_INCIDENT_KIND,
            severity="high",
            title=f"{group_id} has a blocked project the auditor could not resolve",
            summary=f"{project_id} is blocked and still needs an operator decision because the targeted auditor could not resolve it.",
            context=context,
        )


def reconcile_project_incidents() -> None:
    if not table_exists("projects"):
        return
    with db() as conn:
        rows = conn.execute("SELECT id, status, current_slice, last_error FROM projects ORDER BY id").fetchall()
    for row in rows:
        project_id = str(row["id"] or "").strip()
        status = str(row["status"] or "").strip()
        current_slice = row["current_slice"]
        last_error = row["last_error"]
        if not project_id:
            continue
        pr_row = pull_request_row(project_id) or {}
        current_pr_check_incident(project_id, head_sha=str(pr_row.get("head_sha") or ""))
        if status in {"review_failed", "review_fix_required"}:
            handle_review_incidents(project_id, status=status, current_slice=current_slice, last_error=last_error)
        else:
            resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_FAILED_INCIDENT_KIND])
        if status in REVIEW_HOLD_STATUSES:
            handle_review_lane_incidents(project_id, status=status, current_slice=current_slice, last_error=last_error)
        else:
            resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_STALLED_INCIDENT_KIND])
        if status == "blocked" and not latest_open_incident(
            "project",
            project_id,
            incident_kinds=[BLOCKED_UNRESOLVED_INCIDENT_KIND],
        ):
            handle_blocked_incidents(project_id, current_slice=current_slice, last_error=last_error)
        elif status != "blocked":
            resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[BLOCKED_UNRESOLVED_INCIDENT_KIND])


def account_runtime_state(row: sqlite3.Row, account_cfg: Dict[str, Any], now: dt.datetime) -> str:
    configured = str(account_cfg.get("health_state", "ready") or "ready").strip().lower()
    if configured in {"disabled", "draining", "exhausted", "auth_stale"}:
        return configured
    backoff_until = parse_iso(row["backoff_until"])
    if backoff_until and backoff_until > now:
        return "cooldown"
    return "ready"


def account_spark_runtime_state(
    row: sqlite3.Row,
    account_cfg: Dict[str, Any],
    allowed_models: List[str],
    now: dt.datetime,
) -> str:
    base_state = account_runtime_state(row, account_cfg, now)
    if base_state != "ready":
        return base_state
    auth_kind = str(row["auth_kind"] or account_cfg.get("auth_kind") or "api_key")
    if not account_supports_spark(auth_kind, account_cfg, allowed_models):
        return "disabled"
    spark_backoff_until = parse_iso(row["spark_backoff_until"]) if "spark_backoff_until" in row.keys() else None
    if spark_backoff_until and spark_backoff_until > now:
        return "cooldown"
    return "ready"


def account_supports_spark(auth_kind: str, account_cfg: Dict[str, Any], allowed_models: List[str]) -> bool:
    if auth_kind not in CHATGPT_AUTH_KINDS:
        return False
    if not bool(account_cfg.get("spark_enabled", SPARK_MODEL in allowed_models)):
        return False
    return (not allowed_models) or (SPARK_MODEL in allowed_models)


def model_supported_for_auth_kind(model: str, auth_kind: str) -> bool:
    if auth_kind in CHATGPT_AUTH_KINDS:
        return model in CHATGPT_SUPPORTED_MODELS
    return True


def auth_compatible_model_preferences(wanted_models: List[str], auth_kind: str) -> List[str]:
    if auth_kind not in CHATGPT_AUTH_KINDS:
        return list(wanted_models)
    compatible: List[str] = []
    for model in wanted_models:
        if model in CHATGPT_SUPPORTED_MODELS and model not in compatible:
            compatible.append(model)
    if CHATGPT_STANDARD_MODEL not in compatible:
        compatible.append(CHATGPT_STANDARD_MODEL)
    return compatible


def project_account_policy(project_cfg: Dict[str, Any]) -> Dict[str, Any]:
    raw = dict(project_cfg.get("account_policy") or {})
    raw.setdefault("preferred_accounts", list(project_cfg.get("accounts") or []))
    raw.setdefault("burst_accounts", [])
    raw.setdefault("reserve_accounts", [])
    raw.setdefault("allow_chatgpt_accounts", True)
    raw.setdefault("allow_api_accounts", True)
    raw.setdefault("spark_enabled", True)
    return raw


def ordered_project_aliases(project_cfg: Dict[str, Any]) -> List[str]:
    policy = project_account_policy(project_cfg)
    ordered: List[str] = []
    for alias in (
        list(policy.get("preferred_accounts") or [])
        + list(policy.get("burst_accounts") or [])
        + list(policy.get("reserve_accounts") or [])
        + list(project_cfg.get("accounts") or [])
    ):
        text = str(alias or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return ordered


def account_lane(alias: str, policy: Dict[str, Any]) -> Tuple[int, str]:
    if alias in {str(item).strip() for item in policy.get("preferred_accounts") or [] if str(item).strip()}:
        return (0, "preferred")
    if alias in {str(item).strip() for item in policy.get("burst_accounts") or [] if str(item).strip()}:
        return (1, "burst")
    if alias in {str(item).strip() for item in policy.get("reserve_accounts") or [] if str(item).strip()}:
        return (2, "reserve")
    return (3, "fallback")


def bridge_service_definitions(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    services: List[Dict[str, Any]] = []
    accounts_cfg = config.get("accounts") or {}
    seen_names: set[str] = set()
    for alias, account_cfg in accounts_cfg.items():
        clean_alias = str(alias or "").strip()
        bridge_name = str((account_cfg or {}).get("bridge_name") or "").strip()
        if not clean_alias or not bridge_name or bridge_name in seen_names:
            continue
        aliases: List[str] = [clean_alias]
        configured_fallbacks = account_cfg.get("bridge_fallback_accounts") or DEFAULT_BRIDGE_FALLBACK_ACCOUNTS.get(clean_alias, [])
        for fallback_alias in configured_fallbacks:
            clean_fallback = str(fallback_alias or "").strip()
            if clean_fallback and clean_fallback in accounts_cfg and clean_fallback not in aliases:
                aliases.append(clean_fallback)
        services.append(
            {
                "name": bridge_name,
                "priority": max(0, int(account_cfg.get("bridge_priority") or 0)),
                "primary_alias": clean_alias,
                "aliases": aliases,
            }
        )
        seen_names.add(bridge_name)
    services.sort(key=lambda item: (int(item.get("priority") or 999), str(item.get("name") or "")))
    return services


def bridge_service_alias_map(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    alias_map: Dict[str, Dict[str, Any]] = {}
    for service in bridge_service_definitions(config):
        for alias in service.get("aliases") or []:
            clean_alias = str(alias or "").strip()
            if clean_alias:
                alias_map[clean_alias] = service
    return alias_map


def account_bridge_priority_for_alias(config: Dict[str, Any], alias: str) -> int:
    service = bridge_service_alias_map(config).get(str(alias or "").strip())
    if not service:
        return 999
    return max(0, int(service.get("priority") or 0))


def account_has_bridge_name(config: Dict[str, Any], alias: str) -> bool:
    account_cfg = ((config.get("accounts") or {}).get(alias) or {})
    return bool(str(account_cfg.get("bridge_name") or "").strip())


def alias_supports_bridge_service(config: Dict[str, Any], alias: str) -> bool:
    return str(alias or "").strip() in bridge_service_alias_map(config)


def project_pins_special_accounts(config: Dict[str, Any], project_cfg: Dict[str, Any]) -> bool:
    policy = project_account_policy(project_cfg)
    if bool(policy.get("pin_special_accounts", False)):
        return True
    preferred = [str(item).strip() for item in policy.get("preferred_accounts") or [] if str(item).strip()]
    if not preferred:
        return False
    named_preferred = [alias for alias in preferred if alias_supports_bridge_service(config, alias)]
    special_preferred = [alias for alias in preferred if not alias_supports_bridge_service(config, alias)]
    return bool(special_preferred) and not named_preferred


def idle_bridge_service_aliases(
    config: Dict[str, Any],
    *,
    reserved_account_counts: Optional[Dict[str, int]] = None,
) -> set[str]:
    reserved_account_counts = dict(reserved_account_counts or {})
    idle_aliases: set[str] = set()
    for service in bridge_service_definitions(config):
        aliases = [str(alias or "").strip() for alias in service.get("aliases") or [] if str(alias or "").strip()]
        if not aliases:
            continue
        if any(active_run_count_for_account(alias) + int(reserved_account_counts.get(alias) or 0) > 0 for alias in aliases):
            continue
        idle_aliases.update(aliases)
    return idle_aliases


def active_bridge_service_count(
    config: Dict[str, Any],
    *,
    reserved_account_counts: Optional[Dict[str, int]] = None,
) -> int:
    reserved_account_counts = dict(reserved_account_counts or {})
    count = 0
    for service in bridge_service_definitions(config):
        aliases = [str(alias or "").strip() for alias in service.get("aliases") or [] if str(alias or "").strip()]
        if aliases and any(active_run_count_for_account(alias) + int(reserved_account_counts.get(alias) or 0) > 0 for alias in aliases):
            count += 1
    return count


def pick_account_and_model(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    decision: Dict[str, Any],
    *,
    reserved_account_counts: Optional[Dict[str, int]] = None,
) -> Tuple[Optional[str], Optional[str], str, List[Dict[str, Any]]]:
    policy = project_account_policy(project_cfg)
    aliases = ordered_project_aliases(project_cfg)
    if not aliases:
        return None, None, "project has no configured accounts", []
    reserved_account_counts = dict(reserved_account_counts or {})
    price_table = config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE
    now = utc_now()
    wanted_models = list(decision["model_preferences"])
    if not bool(policy.get("spark_enabled", True)):
        wanted_models = [model for model in wanted_models if model != SPARK_MODEL]
    if not wanted_models:
        return None, None, "route class produced no eligible models after filtering", []
    candidates: List[Tuple[int, int, int, int, int, int, int, dt.datetime, int, int, str, str, str, int]] = []
    config_accounts = config.get("accounts") or {}
    rejections: List[str] = []
    selection_trace: List[Dict[str, Any]] = []

    with db() as conn:
        for alias_order, alias in enumerate(aliases):
            lane_rank, lane_name = account_lane(alias, policy)
            trace: Dict[str, Any] = {
                "alias": alias,
                "lane": lane_name,
                "requested_lane": str(decision.get("lane") or ""),
                "lane_submode": str(decision.get("lane_submode") or ""),
                "escalation_reason": str(decision.get("escalation_reason") or ""),
                "selected": False,
            }
            row = conn.execute("SELECT * FROM accounts WHERE alias=?", (alias,)).fetchone()
            if not row:
                trace.update({"state": "rejected", "reason": "missing account record"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: missing account record")
                continue
            account_cfg = config_accounts.get(alias) or {}
            configured_lane = infer_account_lane(account_cfg, alias=alias)
            trace["configured_lane"] = configured_lane
            requested_lane = str(decision.get("lane") or "").strip()
            trace["requested_lane_exact_match"] = configured_lane == requested_lane
            allowed_lanes = [str(item).strip() for item in decision.get("allowed_lanes") or [] if str(item).strip()]
            if allowed_lanes and configured_lane not in allowed_lanes:
                trace.update({"state": "rejected", "reason": f"lane={configured_lane} not in allowed lanes"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: lane={configured_lane} not in allowed lanes")
                continue
            auth_kind = row["auth_kind"]
            trace["auth_kind"] = auth_kind
            bridge_priority = account_bridge_priority_for_alias(config, alias)
            trace["bridge_priority"] = bridge_priority
            bridge_service = bridge_service_alias_map(config).get(alias) or {}
            trace["bridge_service"] = str(bridge_service.get("name") or "")
            trace["configured_state"] = (
                row["health_state"] if "health_state" in row.keys() else str(account_cfg.get("health_state", "ready") or "ready")
            ) or "ready"

            project_allowlist = [str(item).strip() for item in account_cfg.get("project_allowlist") or [] if str(item).strip()]
            if project_allowlist and project_cfg.get("id") not in project_allowlist:
                trace.update({"state": "rejected", "reason": "project not in allowlist"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: project not in allowlist")
                continue

            pool_state = account_runtime_state(row, account_cfg, now)
            trace["pool_state"] = pool_state
            if pool_state != "ready":
                trace.update({"state": "rejected", "reason": f"state={pool_state}"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: state={pool_state}")
                continue

            source_aliases = account_source_aliases(alias)
            active_aliases = source_aliases if auth_kind in CHATGPT_AUTH_KINDS else [alias]
            active = active_run_count_for_aliases(active_aliases) + sum(int(reserved_account_counts.get(item) or 0) for item in active_aliases)
            max_parallel_runs = int(row["max_parallel_runs"] or 1)
            trace["active_runs"] = active
            trace["reserved_runs"] = sum(int(reserved_account_counts.get(item) or 0) for item in active_aliases)
            trace["max_parallel_runs"] = max_parallel_runs
            trace["shared_source_aliases"] = active_aliases
            active_families = active_run_families_for_aliases(active_aliases)
            selected_family = account_execution_family(alias)
            trace["active_families"] = sorted(active_families)
            trace["selected_family"] = selected_family
            if active_families and (len(active_families) > 1 or selected_family not in active_families):
                reason = (
                    "source shared with active run family="
                    f"{','.join(sorted(active_families))}"
                    " on active run"
                )
                trace.update({"state": "rejected", "reason": reason})
                selection_trace.append(trace)
                rejections.append(f"{alias}: {reason}")
                continue
            if active >= max_parallel_runs:
                trace.update({"state": "rejected", "reason": "parallel cap reached"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: parallel cap reached")
                continue

            if auth_kind in CHATGPT_AUTH_KINDS and not bool(policy.get("allow_chatgpt_accounts", True)):
                trace.update({"state": "rejected", "reason": "project disallows chatgpt-auth accounts"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: project disallows chatgpt-auth accounts")
                continue
            if auth_kind == "api_key" and not bool(policy.get("allow_api_accounts", True)):
                trace.update({"state": "rejected", "reason": "project disallows api-key accounts"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: project disallows api-key accounts")
                continue
            if auth_kind == "api_key":
                if not has_api_key(row):
                    trace.update({"state": "rejected", "reason": "api key unavailable"})
                    selection_trace.append(trace)
                    rejections.append(f"{alias}: api key unavailable")
                    continue
            else:
                auth_json_raw = str(row["auth_json_file"] or "").strip()
                auth_json_file = pathlib.Path(auth_json_raw) if auth_json_raw else None
                if not auth_json_file or not auth_json_file.exists():
                    trace.update({"state": "rejected", "reason": "auth json missing"})
                    selection_trace.append(trace)
                    rejections.append(f"{alias}: auth json missing")
                    continue

            capability_models = normalize_allowed_models_for_account(auth_kind, json_field(row["capability_models_json"], []))
            allowed = normalize_allowed_models_for_account(auth_kind, json_field(row["allowed_models_json"], []))
            if capability_models:
                allowed = [model for model in allowed if model in capability_models] or list(capability_models)
            trace["allowed_models"] = list(allowed)
            trace["capability_models"] = list(capability_models)
            trace["capability_status"] = str(row["capability_status"] or "").strip()
            trace["capability_checked_at"] = row["capability_checked_at"]
            spark_pool_state = account_spark_runtime_state(row, account_cfg, allowed, now)
            trace["spark_pool_state"] = spark_pool_state
            available_models: List[Tuple[int, str]] = []
            compatible_wanted_models = auth_compatible_model_preferences(wanted_models, auth_kind)
            trace["compatible_wanted_models"] = list(compatible_wanted_models)
            for model_index, model in enumerate(compatible_wanted_models):
                if allowed and model not in allowed:
                    continue
                if not model_supported_for_auth_kind(model, auth_kind):
                    continue
                if model == SPARK_MODEL and (
                    not account_supports_spark(auth_kind, account_cfg, allowed) or spark_pool_state != "ready"
                ):
                    continue
                available_models.append((model_index, model))
            trace["candidate_models"] = [model for _, model in available_models]
            if not available_models:
                trace.update({"state": "rejected", "reason": f"no allowed model for route class {decision['tier']}"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: no allowed model for route class {decision['tier']}")
                continue

            day_usage = usage_for_account(alias, "day")
            month_usage = usage_for_account(alias, "month")
            last_used = parse_iso(row["last_used_at"]) or dt.datetime.fromtimestamp(0, tz=UTC)
            budget_notes: List[str] = []
            affordable_choice: Optional[Tuple[int, str, float]] = None
            for model_index, chosen_model in available_models:
                est_cost = estimate_cost_usd_for_model(
                    price_table,
                    chosen_model,
                    int(decision["estimated_input_tokens"]),
                    0,
                    int(decision["estimated_output_tokens"]),
                ) or 0.0

                if row["daily_budget_usd"] is not None and (float(day_usage["cost"]) + est_cost) > float(row["daily_budget_usd"]):
                    budget_notes.append(f"{chosen_model}: day budget exceeded")
                    continue

                if row["monthly_budget_usd"] is not None and (float(month_usage["cost"]) + est_cost) > float(row["monthly_budget_usd"]):
                    budget_notes.append(f"{chosen_model}: month budget exceeded")
                    continue

                affordable_choice = (model_index, chosen_model, est_cost)
                break

            if not affordable_choice:
                reason = "; ".join(budget_notes[:2]) if budget_notes else f"no budget-compatible model for route class {decision['tier']}"
                trace.update({"state": "rejected", "reason": reason})
                selection_trace.append(trace)
                rejections.append(f"{alias}: {reason}")
                continue

            model_index, chosen_model, est_cost = affordable_choice
            evidence = account_model_evidence(alias, chosen_model)
            recent_failure_penalty = 1 if evidence["failures"] > evidence["successes"] else 0
            trace_idx = len(selection_trace)
            trace.update(
                {
                    "state": "candidate",
                    "selected_model": chosen_model,
                    "estimated_cost_usd": round(est_cost, 4),
                    "model_successes": evidence["successes"],
                    "model_failures": evidence["failures"],
                    "last_model_success_at": evidence["last_success_at"],
                    "last_model_failure_at": evidence["last_failure_at"],
                    "last_used_at": iso(last_used),
                    "reason": f"eligible on {chosen_model}",
                }
            )
            selection_trace.append(trace)
            candidates.append(
                (
                    0 if configured_lane == requested_lane else 1,
                    lane_rank,
                    active,
                    bridge_priority,
                    recent_failure_penalty,
                    -int(evidence["successes"]),
                    int(evidence["failures"]),
                    last_used,
                    model_index,
                    alias_order,
                    alias,
                    chosen_model,
                    (
                        f"route={decision['tier']}; task_lane={decision.get('lane')}; submode={decision.get('lane_submode')}; "
                        f"account_lane={configured_lane}; escalation={decision.get('escalation_reason')}; "
                        f"policy_bucket={lane_name}; state={pool_state}; auth={auth_kind}; estimated cost ${est_cost:.4f}"
                    ),
                    trace_idx,
                )
            )

    if not candidates:
        detail = "; ".join(rejections[:4]) if rejections else "all candidates filtered"
        return None, None, f"no eligible account/model after auth, pool state, allowlist, or budget filtering ({detail})", selection_trace
    pinned_special_accounts = project_pins_special_accounts(config, project_cfg)
    idle_named_aliases = idle_bridge_service_aliases(config, reserved_account_counts=reserved_account_counts)

    def candidate_sort_key(item: Tuple[int, int, int, int, int, int, int, dt.datetime, int, int, str, str, str, int]) -> Tuple[Any, ...]:
        alias = item[10]
        if pinned_special_accounts:
            named_lane_reservation_rank = 0
        elif idle_named_aliases:
            if alias in idle_named_aliases:
                named_lane_reservation_rank = 0
            elif alias_supports_bridge_service(config, alias):
                named_lane_reservation_rank = 1
            else:
                named_lane_reservation_rank = 2
        else:
            named_lane_reservation_rank = 0
        return (
            named_lane_reservation_rank,
            item[0],
            item[1],
            bridge_service_rank,
            item[2],
            item[3],
            item[4],
            item[5],
            item[6],
            item[7],
            item[8],
            item[9],
        )

    candidates.sort(key=candidate_sort_key)
    _, _, _, _, _, _, _, _, _, _, alias, model, why, selected_trace_idx = candidates[0]
    for idx, trace in enumerate(selection_trace):
        if idx == selected_trace_idx:
            trace["selected"] = True
            trace["state"] = "selected"
            trace["reason"] = why
            continue
        if trace.get("state") == "candidate":
            trace["state"] = "eligible_not_selected"
            trace["reason"] = f"{trace.get('reason') or 'eligible fallback'}; kept behind {alias} on lane, availability, and model ordering"
    return alias, model, why, selection_trace


def write_toml_string(value: str) -> str:
    return json.dumps(value)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seed_auth_json(home: pathlib.Path, source_path: pathlib.Path) -> None:
    if not source_path.exists():
        raise RuntimeError(f"missing auth_json_file: {source_path}")
    source_bytes = source_path.read_bytes()
    source_hash = sha256_bytes(source_bytes)
    marker = home / ".auth_source.sha256"
    target = home / "auth.json"
    existing_hash = marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    if (not target.exists()) or (existing_hash != source_hash):
        target.write_bytes(source_bytes)
        marker.write_text(source_hash, encoding="utf-8")


def account_value(account_cfg: Any, key: str, default: Any = None) -> Any:
    if isinstance(account_cfg, sqlite3.Row):
        return account_cfg[key] if key in account_cfg.keys() else default
    if isinstance(account_cfg, dict):
        return account_cfg.get(key, default)
    return default


def account_credential_source_key(account_cfg: Any) -> str:
    auth_kind = str(account_value(account_cfg, "auth_kind", "api_key") or "api_key").strip()
    if auth_kind in CHATGPT_AUTH_KINDS:
        auth_json_file = str(account_value(account_cfg, "auth_json_file", "") or "").strip()
        return f"{auth_kind}:{auth_json_file}" if auth_json_file else ""
    api_key_env = str(account_value(account_cfg, "api_key_env", "") or "").strip()
    if api_key_env:
        return f"{auth_kind}:env:{api_key_env}"
    api_key_file = str(account_value(account_cfg, "api_key_file", "") or "").strip()
    return f"{auth_kind}:file:{api_key_file}" if api_key_file else ""


def shared_chatgpt_home_key(account_cfg: Any) -> str:
    auth_kind = str(account_value(account_cfg, "auth_kind", "api_key") or "api_key").strip()
    if auth_kind not in CHATGPT_AUTH_KINDS:
        return ""
    source_key = account_credential_source_key(account_cfg)
    if not source_key:
        return ""
    return hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:16]


def account_home(alias: str, account_cfg: Any = None) -> pathlib.Path:
    shared_key = shared_chatgpt_home_key(account_cfg)
    if shared_key:
        path = CODEX_HOME_ROOT / f"chatgpt-{shared_key}"
    else:
        path = CODEX_HOME_ROOT / alias
    path.mkdir(parents=True, exist_ok=True)
    return path


def account_source_aliases(alias: str) -> List[str]:
    clean_alias = str(alias or "").strip()
    if not clean_alias:
        return []
    with db() as conn:
        row = conn.execute(
            "SELECT alias, auth_kind, auth_json_file, api_key_env, api_key_file FROM accounts WHERE alias=?",
            (clean_alias,),
        ).fetchone()
        if not row:
            return [clean_alias]
        auth_kind = str(row["auth_kind"] or "").strip()
        if auth_kind in CHATGPT_AUTH_KINDS and str(row["auth_json_file"] or "").strip():
            rows = conn.execute(
                "SELECT alias FROM accounts WHERE auth_kind=? AND auth_json_file=? ORDER BY alias",
                (auth_kind, str(row["auth_json_file"] or "").strip()),
            ).fetchall()
            aliases = [str(item["alias"] or "").strip() for item in rows if str(item["alias"] or "").strip()]
            return aliases or [clean_alias]
        if auth_kind == "api_key" and str(row["api_key_env"] or "").strip():
            rows = conn.execute(
                "SELECT alias FROM accounts WHERE auth_kind=? AND api_key_env=? ORDER BY alias",
                (auth_kind, str(row["api_key_env"] or "").strip()),
            ).fetchall()
            aliases = [str(item["alias"] or "").strip() for item in rows if str(item["alias"] or "").strip()]
            return aliases or [clean_alias]
        if auth_kind == "api_key" and str(row["api_key_file"] or "").strip():
            rows = conn.execute(
                "SELECT alias FROM accounts WHERE auth_kind=? AND api_key_file=? ORDER BY alias",
                (auth_kind, str(row["api_key_file"] or "").strip()),
            ).fetchall()
            aliases = [str(item["alias"] or "").strip() for item in rows if str(item["alias"] or "").strip()]
            return aliases or [clean_alias]
    return [clean_alias]


def read_api_key_from_file(api_key_file: pathlib.Path) -> str:
    if not api_key_file.exists():
        raise RuntimeError(f"missing api_key_file: {api_key_file}")
    api_key = api_key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        raise RuntimeError(f"empty api_key_file: {api_key_file}")
    return api_key


def read_api_key(account_cfg: Any) -> str:
    api_key_env = str(account_value(account_cfg, "api_key_env", "") or "").strip()
    if api_key_env:
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            raise RuntimeError(f"missing environment variable for api_key_env: {api_key_env}")
        return api_key

    api_key_file = pathlib.Path(str(account_value(account_cfg, "api_key_file", "") or "").strip())
    return read_api_key_from_file(api_key_file)


def has_api_key(account_cfg: Any) -> bool:
    try:
        return bool(read_api_key(account_cfg))
    except Exception:
        return False


def prepare_account_environment(alias: str, account_cfg: Dict[str, Any]) -> Dict[str, str]:
    home = account_home(alias, account_cfg)
    config_lines = ['cli_auth_credentials_store = "file"']
    forced_login_method = account_cfg.get("forced_login_method")
    if forced_login_method:
        config_lines.append(f"forced_login_method = {write_toml_string(str(forced_login_method))}")
    forced_workspace_id = account_cfg.get("forced_chatgpt_workspace_id")
    if forced_workspace_id:
        config_lines.append(f"forced_chatgpt_workspace_id = {write_toml_string(str(forced_workspace_id))}")
    (home / "config.toml").write_text("\n".join(config_lines) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["HOME"] = str(home)

    auth_kind = account_cfg.get("auth_kind", "api_key")
    if auth_kind == "api_key":
        env["CODEX_API_KEY"] = read_api_key(account_cfg)
    elif auth_kind in {"chatgpt_auth_json", "auth_json"}:
        auth_json_file = pathlib.Path(account_cfg.get("auth_json_file", ""))
        seed_auth_json(home, auth_json_file)
    else:
        raise RuntimeError(f"unsupported auth_kind for {alias}: {auth_kind}")

    if account_cfg.get("openai_base_url"):
        env["OPENAI_BASE_URL"] = str(account_cfg["openai_base_url"])
    return env


@dataclass
class CommandResult:
    exit_code: int
    timed_out: bool = False
    timeout_seconds: Optional[int] = None
    idle_timed_out: bool = False
    idle_timeout_seconds: Optional[int] = None


async def _terminate_process(proc: asyncio.subprocess.Process, grace_seconds: float = 5.0) -> None:
    if proc.returncode is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(proc.pid, 15)
        else:
            proc.terminate()
    except ProcessLookupError:
        return
    except Exception:
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=grace_seconds)
        return
    except asyncio.TimeoutError:
        pass
    try:
        if os.name == "posix":
            os.killpg(proc.pid, 9)
        else:
            proc.kill()
    except ProcessLookupError:
        return
    except Exception:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()


async def run_command(
    cmd: List[str],
    *,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    input_text: Optional[str] = None,
    log_path: Optional[pathlib.Path] = None,
    timeout_seconds: Optional[int] = None,
    idle_timeout_seconds: Optional[int] = None,
) -> CommandResult:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.PIPE if input_text is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=(os.name == "posix"),
    )
    timed_out = False
    idle_timed_out = False
    started_monotonic = time.monotonic()
    last_output_monotonic = started_monotonic

    if input_text is not None and proc.stdin is not None:
        proc.stdin.write(input_text.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()

    async def _pump_stdout() -> None:
        nonlocal last_output_monotonic
        assert proc.stdout is not None
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab") as f:
                while True:
                    chunk = await proc.stdout.read(65536)
                    if not chunk:
                        break
                    last_output_monotonic = time.monotonic()
                    f.write(chunk)
                    f.flush()
        else:
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                last_output_monotonic = time.monotonic()

    pump_task = asyncio.create_task(_pump_stdout())
    try:
        wall_deadline = started_monotonic + float(timeout_seconds) if timeout_seconds and timeout_seconds > 0 else None
        idle_limit = float(idle_timeout_seconds) if idle_timeout_seconds and idle_timeout_seconds > 0 else None
        while True:
            now_monotonic = time.monotonic()
            wait_budget = 1.0
            if wall_deadline is not None:
                wait_budget = min(wait_budget, max(0.0, wall_deadline - now_monotonic))
            if idle_limit is not None:
                wait_budget = min(wait_budget, max(0.0, (last_output_monotonic + idle_limit) - now_monotonic))
            if wait_budget <= 0:
                if wall_deadline is not None and now_monotonic >= wall_deadline:
                    raise asyncio.TimeoutError
                if idle_limit is not None and (now_monotonic - last_output_monotonic) >= idle_limit:
                    idle_timed_out = True
                    raise asyncio.TimeoutError
                wait_budget = 0.1
            try:
                await asyncio.wait_for(proc.wait(), timeout=wait_budget)
                break
            except asyncio.TimeoutError:
                now_monotonic = time.monotonic()
                if wall_deadline is not None and now_monotonic >= wall_deadline:
                    raise
                if idle_limit is not None and (now_monotonic - last_output_monotonic) >= idle_limit:
                    idle_timed_out = True
                    raise
    except asyncio.CancelledError:
        await _terminate_process(proc)
        raise
    except asyncio.TimeoutError:
        timed_out = True
        if log_path:
            with log_path.open("ab") as f:
                if idle_timed_out:
                    f.write((f'\n{{"type":"controller.idle_timeout","idle_timeout_seconds":{int(idle_timeout_seconds or 0)}}}\n').encode("utf-8"))
                else:
                    f.write((f'\n{{"type":"controller.timeout","timeout_seconds":{int(timeout_seconds or 0)}}}\n').encode("utf-8"))
                f.flush()
        await _terminate_process(proc)
    finally:
        await pump_task

    exit_code = proc.returncode if proc.returncode is not None else 124
    if timed_out and exit_code == 0:
        exit_code = 124
    return CommandResult(
        exit_code=int(exit_code),
        timed_out=timed_out,
        timeout_seconds=timeout_seconds,
        idle_timed_out=idle_timed_out,
        idle_timeout_seconds=idle_timeout_seconds,
    )


def parse_jsonl_usage(log_path: pathlib.Path) -> Tuple[int, int, int]:
    if not log_path.exists():
        return 0, 0, 0
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw_line = raw_line.strip()
        if not raw_line or not raw_line.startswith("{"):
            continue
        try:
            event = json.loads(raw_line)
        except Exception:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
            input_tokens = int(usage.get("input_tokens") or 0)
            cached_input_tokens = int(usage.get("cached_input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
    return input_tokens, cached_input_tokens, output_tokens


def parse_backoff_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = text.lower()
    if "429" not in lower and "rate limit" not in lower and "too many requests" not in lower:
        return None
    patterns = [
        (r"retry after\s+(\d+)\s*s", 1),
        (r"try again in\s+(\d+)\s*s", 1),
        (r"after\s+(\d+)\s*seconds", 1),
        (r"after\s+(\d+)\s*minutes", 60),
        (r"(\d+)\s*seconds?", 1),
        (r"(\d+)\s*minutes?", 60),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, lower)
        if match:
            return max(int(match.group(1)) * multiplier, default_seconds)
    return default_seconds


def parse_auth_failure_message(text: str) -> Optional[str]:
    lower = str(text or "").lower()
    markers = [
        ("refresh_token_reused", "chatgpt auth refresh token was invalidated by another session"),
        ("access token could not be refreshed", "chatgpt auth refresh token is stale"),
        ("refresh token was already used", "chatgpt auth refresh token is stale"),
        ("provided authentication token is expired", "chatgpt auth session is expired"),
        ("please log out and sign in again", "chatgpt auth session requires a fresh login"),
        ("incorrect api key provided", "api key is invalid or revoked"),
        ("invalid api key", "api key is invalid or revoked"),
    ]
    for needle, message in markers:
        if needle in lower:
            return message
    if "401 unauthorized" in lower and ("token" in lower or "api key" in lower or "auth" in lower):
        return "authentication failed for this account"
    return None


def parse_usage_limit_reset_at(text: str) -> Optional[dt.datetime]:
    raw = str(text or "")
    lower = raw.lower()
    if "usage limit" not in lower and "send a request to your admin" not in lower:
        return None
    match = re.search(r"try again at\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\s+\d{1,2}:\d{2}\s+[AP]M)", raw, re.IGNORECASE)
    if not match:
        return None
    candidate = re.sub(r"(\d)(st|nd|rd|th)", r"\1", match.group(1), flags=re.IGNORECASE).strip()
    for fmt in ("%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p"):
        try:
            return dt.datetime.strptime(candidate, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse_usage_limit_reset_hint(text: str) -> Optional[dt.datetime]:
    raw = str(text or "")
    for pattern in (
        r"provider reset\s+([0-9T:\-\.]+Z)",
        r"usage-limited until\s+([0-9T:\-\.]+Z)",
    ):
        match = re.search(pattern, raw, re.IGNORECASE)
        if not match:
            continue
        parsed = parse_iso(match.group(1))
        if parsed is not None:
            return parsed
    return parse_usage_limit_reset_at(raw)


def parse_usage_limit_backoff_seconds(text: str, default_seconds: int, *, now: Optional[dt.datetime] = None) -> Optional[int]:
    raw = str(text or "")
    lower = raw.lower()
    if "usage limit" not in lower and "send a request to your admin" not in lower:
        return None
    current = now or utc_now()
    reset_at = parse_usage_limit_reset_at(raw)
    if reset_at is None:
        return default_seconds
    seconds = int((reset_at - current).total_seconds())
    return max(seconds, default_seconds) if seconds > 0 else default_seconds


def parse_spark_pool_backoff_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = text.lower()
    spark_signals = ("spark", "codex spark", "spark pool", "spark token", "spark quota", "spark credits")
    exhaustion_signals = ("depleted", "exhausted", "empty", "unavailable", "quota exceeded", "limit reached", "out of")
    if not any(signal in lower for signal in spark_signals):
        return None
    if not any(signal in lower for signal in exhaustion_signals) and "429" not in lower and "rate limit" not in lower:
        return None
    return parse_backoff_seconds(text, default_seconds) or default_seconds


def parse_unsupported_chatgpt_model(text: str) -> Optional[str]:
    raw = str(text or "")
    lower = raw.lower()
    if "not supported when using codex with a chatgpt account" not in lower:
        return None
    match = re.search(r"'([^']+)'", raw)
    if match:
        return str(match.group(1) or "").strip() or None
    return "unknown"


@dataclass
class RuntimeState:
    tasks: Dict[str, Any]
    stop: asyncio.Event
    last_design_mirror_sync_at: Optional[dt.datetime] = None
    controller_loop: Optional[asyncio.AbstractEventLoop] = None


state = RuntimeState(tasks={}, stop=asyncio.Event())
app = FastAPI(title=APP_TITLE)


def prune_finished_tasks() -> None:
    for project_id, task in list(state.tasks.items()):
        if task.done():
            state.tasks.pop(project_id, None)


def reconcile_runtime_tasks(active_project_ids: set[str]) -> None:
    prune_finished_tasks()
    for project_id, task in list(state.tasks.items()):
        if task.done():
            state.tasks.pop(project_id, None)
            continue
        if project_id not in active_project_ids:
            task.cancel()
            state.tasks.pop(project_id, None)


async def execute_project_slice(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    project_row: sqlite3.Row,
    slice_name: str,
    decision: Dict[str, Any],
    account_alias: str,
    selected_model: str,
    selection_note: str,
    selection_trace: List[Dict[str, Any]],
) -> None:
    project_id = project_cfg["id"]
    account_cfg = (config.get("accounts") or {}).get(account_alias, {})
    initial_status = str(project_row["status"] or "").strip().lower()
    job_kind = (
        "healing"
        if initial_status in {HEALING_STATUS, QUEUE_REFILLING_STATUS, SOURCE_BACKLOG_OPEN_STATUS, "review_fix_required", DECISION_REQUIRED_STATUS}
        else "coding"
    )
    baseline_snapshot = git_dirty_snapshot(str(project_cfg["path"]))
    feedback_files = selected_feedback_files(config, project_cfg)
    decision_reason = f"{decision['reason']}; {selection_note}"
    pending_local_review_reason: Optional[str] = None
    runner = project_cfg.get("runner") or {}
    runtime_model = (
        str(decision.get("runtime_model") or "").strip()
        or str(runner.get("runtime_model") or "").strip()
        or str(selected_model)
    )
    prompt = build_prompt(
        project_cfg,
        slice_name,
        {
            "tier": decision["tier"],
            "selected_model": runtime_model,
            "reasoning_effort": decision["reasoning_effort"],
            "reason": decision_reason,
        },
        feedback_files,
    )

    started_at = utc_now()
    ts = started_at.strftime("%Y%m%dT%H%M%SZ")
    safe_slice = re.sub(r"[^a-zA-Z0-9._-]+", "-", slice_name)[:80]
    log_path = LOG_DIR / project_id / f"{ts}-{safe_slice}.jsonl"
    prompt_path = LOG_DIR / project_id / f"{ts}-{safe_slice}.prompt.txt"
    final_message_path = LOG_DIR / project_id / f"{ts}-{safe_slice}.final.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    decision_meta = {
        "classification_mode": str(config.get("spider", {}).get("classification_mode") or "evidence_v1"),
        "estimated_prompt_chars": int(decision["estimated_prompt_chars"]),
        "estimated_input_tokens": int(decision["estimated_input_tokens"]),
        "estimated_output_tokens": int(decision["estimated_output_tokens"]),
        "predicted_changed_files": int(decision["predicted_changed_files"]),
        "requires_contract_authority": bool(decision["requires_contract_authority"]),
        "lane": str(decision.get("lane") or ""),
        "lane_submode": str(decision.get("lane_submode") or ""),
        "selected_profile": str(decision.get("selected_profile") or ""),
        "why_not_cheaper": str(decision.get("why_not_cheaper") or ""),
        "escalation_reason": str(decision.get("escalation_reason") or ""),
        "expected_allowance_burn": dict(decision.get("expected_allowance_burn") or {}),
        "allowed_lanes": list(decision.get("allowed_lanes") or []),
        "required_reviewer_lane": str(decision.get("required_reviewer_lane") or ""),
        "final_reviewer_lane": str(decision.get("final_reviewer_lane") or ""),
        "task_meta": dict(decision.get("task_meta") or {}),
        "operator_override_required": bool((decision.get("task_meta") or {}).get("operator_override_required")),
        "signoff_requirements": list((decision.get("task_meta") or {}).get("signoff_requirements") or []),
        "spark_eligible": bool(decision["spark_eligible"]),
        "feedback_count": len(feedback_files),
        "planner_model": selected_model,
        "runtime_model": runtime_model,
        "lane_capacity": dict(decision.get("lane_capacity") or {}),
    }

    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
            VALUES (?, ?, ?, ?, 'starting', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                account_alias,
                job_kind,
                slice_name,
                runtime_model,
                decision["reasoning_effort"],
                decision["tier"],
                decision_reason,
                iso(started_at),
                str(log_path),
                str(final_message_path),
                str(prompt_path),
            ),
        )
        run_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO spider_decisions(
                project_id,
                slice_name,
                account_alias,
                selected_model,
                spider_tier,
                reason,
                estimated_prompt_chars,
                decision_meta_json,
                selection_trace_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                slice_name,
                account_alias,
                selected_model,
                decision["tier"],
                decision_reason,
                int(decision["estimated_prompt_chars"]),
                json.dumps(decision_meta, sort_keys=True),
                json.dumps(selection_trace, sort_keys=True),
                iso(started_at),
            ),
        )

    record_account_selection(account_alias, selected_model)
    update_project_status(
        project_id,
        status="starting",
        current_slice=slice_name,
        active_run_id=run_id,
        cooldown_until=None,
        last_run_at=started_at,
        last_error=None,
        spider_tier=decision["tier"],
        spider_model=selected_model,
        spider_reason=decision_reason,
    )

    account_run_succeeded = False
    try:
        env = prepare_account_environment(account_alias, account_cfg)
        touch_account(account_alias)
        with db() as conn:
            conn.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
        update_project_status(
            project_id,
            status="running",
            current_slice=slice_name,
            active_run_id=run_id,
            cooldown_until=None,
            last_run_at=started_at,
            spider_tier=decision["tier"],
            spider_model=selected_model,
            spider_reason=decision_reason,
        )

        cmd = [
            "codex",
            "--ask-for-approval",
            str(runner.get("approval_policy", "never")),
            "exec",
            "--json",
            "--cd",
            project_cfg["path"],
            "--sandbox",
            str(runner.get("sandbox", "workspace-write")),
            "--model",
            runtime_model,
            "--output-last-message",
            str(final_message_path),
        ]
        if runner.get("profile"):
            cmd += ["--profile", str(runner["profile"])]
        if runner.get("skip_git_repo_check"):
            cmd += ["--skip-git-repo-check"]
        if decision.get("reasoning_effort"):
            cmd += ["-c", f"model_reasoning_effort={json.dumps(decision['reasoning_effort'])}"]
        for override in runner.get("config_overrides", []) or []:
            cmd += ["-c", str(override)]
        cmd += ["-"]

        exec_timeout_seconds = int((runner.get("exec_timeout_seconds") or get_policy(config, "exec_timeout_seconds", 5400)))
        exec_idle_timeout_seconds = int(
            runner.get("exec_idle_timeout_seconds")
            or get_policy(config, "exec_idle_timeout_seconds", min(exec_timeout_seconds, 1200))
        )
        rc_result = await run_command(
            cmd,
            cwd=project_cfg["path"],
            env=env,
            input_text=prompt,
            log_path=log_path,
            timeout_seconds=exec_timeout_seconds,
            idle_timeout_seconds=exec_idle_timeout_seconds,
        )
        rc = rc_result.exit_code
        finished_at = utc_now()
        raw_log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        input_tokens, cached_input_tokens, output_tokens = parse_jsonl_usage(log_path)
        est_cost = estimate_cost_usd_for_model(
            config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE,
            selected_model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        )

        if rc == 0:
            verify_rc = None
            verify_cmd = (project_cfg.get("verify_cmd") or "").strip()
            if verify_cmd:
                with log_path.open("ab") as f:
                    f.write(b'\n{"type":"verify.started"}\n')
                update_project_status(
                    project_id,
                    status="verifying",
                    current_slice=slice_name,
                    active_run_id=run_id,
                    cooldown_until=None,
                    last_run_at=started_at,
                    spider_tier=decision["tier"],
                    spider_model=selected_model,
                    spider_reason=decision_reason,
                )
                with db() as conn:
                    conn.execute("UPDATE runs SET status='verifying' WHERE id=?", (run_id,))
                verify_timeout_seconds = int((runner.get("verify_timeout_seconds") or get_policy(config, "verify_timeout_seconds", 1800)))
                verify_idle_timeout_seconds = int(
                    runner.get("verify_idle_timeout_seconds")
                    or get_policy(config, "verify_idle_timeout_seconds", min(verify_timeout_seconds, 900))
                )
                verify_result = await run_command(
                    ["bash", "-lc", verify_cmd],
                    cwd=project_cfg["path"],
                    env=env,
                    log_path=log_path,
                    timeout_seconds=verify_timeout_seconds,
                    idle_timeout_seconds=verify_idle_timeout_seconds,
                )
                verify_rc = verify_result.exit_code

            if verify_rc in (None, 0):
                review = project_review_policy(project_cfg)
                review_required = decision_requires_serial_review(project_cfg, decision)
                review_mode = str(review.get("mode") or "github").strip().lower()
                if review_required and review_mode == "github":
                    branch_info: Optional[Dict[str, Any]] = None
                    repo_meta: Optional[Dict[str, Any]] = None
                    try:
                        token = github_token()
                        if not token:
                            raise RuntimeError("GitHub review is enabled but no GitHub token is available in fleet")
                        repo_meta = project_github_repo(project_cfg, token)
                        branch_info = commit_and_push_review_branch(
                            project_cfg,
                            repo_meta,
                            slice_name,
                            token,
                            baseline_snapshot=baseline_snapshot,
                        )
                        if not branch_info.get("changed"):
                            mark_feedback_applied(project_cfg, run_id, feedback_files)
                            increment_queue(project_id)
                            with db() as conn:
                                conn.execute(
                                    """
                                    UPDATE runs
                                    SET status='complete', exit_code=?, verify_exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                                    WHERE id=?
                                    """,
                                    (rc, verify_rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
                                )
                                row = conn.execute("SELECT queue_json, queue_index FROM projects WHERE id=?", (project_id,)).fetchone()
                            queue = json.loads(row["queue_json"] or "[]")
                            idx = int(row["queue_index"])
                            next_status = "complete" if idx >= len(queue) else READY_STATUS
                            next_slice = normalize_slice_text(queue[idx]) if idx < len(queue) else None
                            update_project_status(
                                project_id,
                                status=next_status,
                                current_slice=next_slice,
                                active_run_id=None,
                                cooldown_until=utc_now() + dt.timedelta(seconds=1),
                                last_run_at=finished_at,
                                spider_tier=decision["tier"],
                                spider_model=selected_model,
                                spider_reason=decision_reason,
                            )
                        else:
                            pr = ensure_pull_request(
                                project_cfg,
                                repo_meta,
                                str(branch_info["branch"]),
                                str(branch_info["head_sha"]),
                                slice_name,
                                token,
                            )
                            pr_row = pull_request_row(project_id)
                            review_trigger = str(review.get("trigger") or "manual_comment").strip().lower()
                            if pr_row and review_trigger == "manual_comment" and str(pr_row["last_review_head_sha"] or "") != str(branch_info["head_sha"]):
                                request_github_review(project_cfg, pr_row, token, str(branch_info["head_sha"]))
                            with db() as conn:
                                conn.execute(
                                    """
                                    UPDATE runs
                                    SET status='awaiting_review', exit_code=?, verify_exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                                    WHERE id=?
                                    """,
                                    (rc, verify_rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
                                )
                            upsert_github_review_run(
                                project_id,
                                slice_name=slice_name,
                                pr_number=int(pr["number"]),
                                pr_url=str(pr["url"]),
                                review_status="requested" if review_trigger == "manual_comment" else "queued",
                                review_focus=review_focus_text(project_cfg, slice_name),
                            )
                            update_project_status(
                                project_id,
                                status="review_requested" if review_trigger == "manual_comment" else "awaiting_pr",
                                current_slice=slice_name,
                                active_run_id=None,
                                cooldown_until=None,
                                last_run_at=finished_at,
                                last_error=None,
                                spider_tier=decision["tier"],
                                spider_model=selected_model,
                                spider_reason=decision_reason,
                            )
                            account_run_succeeded = True
                    except Exception as review_exc:
                        review_message = str(review_exc)
                        backoff_seconds = int(get_policy(config, "rate_limit_backoff_base", 60))
                        retry_at = utc_now() + dt.timedelta(seconds=backoff_seconds if is_transient_review_failure(review_message) else max(backoff_seconds, 120))
                        if is_transient_review_failure(review_message) and repo_meta and branch_info and bool(branch_info.get("changed")):
                            persist_pending_review_request(
                                project_cfg,
                                repo_meta=repo_meta,
                                branch_name=str(branch_info.get("branch") or ""),
                                head_sha=str(branch_info.get("head_sha") or ""),
                                slice_name=slice_name,
                                requested_at=finished_at,
                            )
                        with db() as conn:
                            conn.execute(
                                """
                                UPDATE runs
                                SET status='review_failed', exit_code=?, verify_exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='review', error_message=?
                                WHERE id=?
                                """,
                                (rc, verify_rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, review_message, run_id),
                            )
                        update_project_status(
                            project_id,
                            status="review_failed",
                            current_slice=slice_name,
                            active_run_id=None,
                            cooldown_until=retry_at,
                            last_run_at=finished_at,
                            last_error=review_message,
                            consecutive_failures=0,
                            spider_tier=decision["tier"],
                            spider_model=selected_model,
                            spider_reason=decision_reason,
                        )
                elif review_required and review_mode == "local":
                    task_meta = dict(decision.get("task_meta") or {})
                    reviewer_lane = reviewer_lane_for_dispatch(task_meta, execution_lane=str(decision.get("lane") or ""))
                    reviewer_model = reviewer_runtime_model_for_lane(config.get("lanes") or {}, reviewer_lane)
                    review_round = review_round_for_dispatch(task_meta, execution_lane=str(decision.get("lane") or ""))
                    changed_paths = changed_paths_since_snapshot(str(project_cfg["path"]), baseline_snapshot)
                    packet = review_packet_payload(
                        project_id=project_id,
                        slice_name=slice_name,
                        decision=decision,
                        changed_paths=changed_paths,
                        verify_rc=verify_rc,
                        run_id=run_id,
                    )
                    review_focus = encode_review_focus(
                        review_focus_text(project_cfg, slice_name),
                        reviewer_lane=reviewer_lane,
                        reviewer_model=reviewer_model,
                        metadata={
                            **review_focus_metadata(task_meta, slice_name=slice_name),
                            "review_round": str(review_round),
                            "changed_files": json.dumps(changed_paths[:12]),
                            "review_packet": json.dumps(packet, sort_keys=True),
                        },
                    )
                    pr_row = upsert_local_review_request(
                        project_cfg,
                        slice_name=slice_name,
                        requested_at=finished_at,
                        review_focus=review_focus,
                        workflow_state={
                            "workflow_kind": str(task_meta.get("workflow_kind") or "default"),
                            "review_round": review_round,
                            "max_review_rounds": int(task_meta.get("max_review_rounds") or 0),
                            "groundwork_time_ms": run_duration_ms(iso(started_at), iso(finished_at))
                            if str(decision.get("lane") or "") == "groundwork"
                            else 0,
                            "core_time_ms": run_duration_ms(iso(started_at), iso(finished_at))
                            if str(decision.get("lane") or "") == "core"
                            else 0,
                            "allowance_burn_by_lane": {
                                str(decision.get("lane") or ""): {
                                    "estimated_cost_usd": est_cost or 0.0,
                                    "runs": 1,
                                }
                            },
                        },
                    )
                    with db() as conn:
                        conn.execute(
                            """
                            UPDATE runs
                            SET status='awaiting_review', exit_code=?, verify_exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                            WHERE id=?
                            """,
                            (rc, verify_rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
                        )
                    update_project_status(
                        project_id,
                        status=review_hold_status_for_project(project_id, project_cfg=project_cfg, pr_row=pr_row),
                        current_slice=slice_name,
                        active_run_id=None,
                        cooldown_until=None,
                        last_run_at=finished_at,
                        last_error=None,
                        spider_tier=decision["tier"],
                        spider_model=selected_model,
                        spider_reason=decision_reason,
                    )
                    pending_local_review_reason = (
                        f"post-verify {str(decision.get('lane') or 'unknown')} output requires {reviewer_lane} review before queue advance"
                    )
                    account_run_succeeded = True
                else:
                    mark_feedback_applied(project_cfg, run_id, feedback_files)
                    increment_queue(project_id)
                    with db() as conn:
                        conn.execute(
                            """
                            UPDATE runs
                            SET status='complete', exit_code=?, verify_exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                            WHERE id=?
                            """,
                            (rc, verify_rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
                        )
                        row = conn.execute("SELECT queue_json, queue_index FROM projects WHERE id=?", (project_id,)).fetchone()
                    queue = json.loads(row["queue_json"] or "[]")
                    idx = int(row["queue_index"])
                    next_status = "complete" if idx >= len(queue) else READY_STATUS
                    next_slice = normalize_slice_text(queue[idx]) if idx < len(queue) else None
                    update_project_status(
                        project_id,
                        status=next_status,
                        current_slice=next_slice,
                        active_run_id=None,
                        cooldown_until=utc_now() + dt.timedelta(seconds=1),
                        last_run_at=finished_at,
                        spider_tier=decision["tier"],
                        spider_model=selected_model,
                        spider_reason=decision_reason,
                    )
                    account_run_succeeded = True
            else:
                verify_timed_out = 'verify_result' in locals() and bool(verify_result.timed_out)
                verify_idle_timed_out = verify_timed_out and bool(verify_result.idle_timed_out)
                if verify_idle_timed_out:
                    msg = f"verify stalled without log output for {verify_result.idle_timeout_seconds}s"
                    error_class = "verify_stalled"
                elif verify_timed_out:
                    msg = f"verify timed out after {verify_result.timeout_seconds}s"
                    error_class = "verify_timeout"
                else:
                    msg = f"verify failed with exit {verify_rc}"
                    error_class = "verify"
                with db() as conn:
                    conn.execute(
                        """
                        UPDATE runs
                        SET status='failed', exit_code=?, verify_exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class=?, error_message=?
                        WHERE id=?
                        """,
                        (rc, verify_rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, error_class, msg, run_id),
                    )
                    row = conn.execute("SELECT consecutive_failures FROM projects WHERE id=?", (project_id,)).fetchone()
                    failures = int((row["consecutive_failures"] if row else 0) + 1)
                max_failures = int(get_policy(config, "max_consecutive_failures", 3))
                status = "blocked" if failures >= max_failures else READY_STATUS
                cooldown = utc_now() + dt.timedelta(seconds=int(get_policy(config, "restart_cooldown_seconds", 120)))
                update_project_status(
                    project_id,
                    status=status,
                    current_slice=slice_name,
                    active_run_id=None,
                    cooldown_until=cooldown,
                    last_run_at=finished_at,
                    last_error=msg,
                    consecutive_failures=failures,
                    spider_tier=decision["tier"],
                    spider_model=selected_model,
                    spider_reason=decision_reason,
                )
        else:
            failures = int(project_row["consecutive_failures"] or 0) + 1
            if rc_result.timed_out:
                if rc_result.idle_timed_out:
                    msg = f"codex exec stalled without log output for {rc_result.idle_timeout_seconds}s"
                    timeout_error_class = "stalled"
                else:
                    msg = f"codex exec timed out after {rc_result.timeout_seconds}s"
                    timeout_error_class = "timeout"
                with db() as conn:
                    conn.execute(
                        """
                        UPDATE runs
                        SET status='failed', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class=?, error_message=?
                        WHERE id=?
                        """,
                        (rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, timeout_error_class, msg, run_id),
                    )
                max_failures = int(get_policy(config, "max_consecutive_failures", 3))
                status = "blocked" if failures >= max_failures else READY_STATUS
                cooldown = utc_now() + dt.timedelta(seconds=int(get_policy(config, "restart_cooldown_seconds", 120)))
                update_project_status(
                    project_id,
                    status=status,
                    current_slice=slice_name,
                    active_run_id=None,
                    cooldown_until=cooldown,
                    last_run_at=finished_at,
                    last_error=msg,
                    consecutive_failures=failures,
                    spider_tier=decision["tier"],
                    spider_model=selected_model,
                    spider_reason=decision_reason,
                )
            else:
                spark_backoff = None
                if selected_model == SPARK_MODEL:
                    spark_backoff = parse_spark_pool_backoff_seconds(
                        raw_log,
                        int(get_policy(config, "spark_pool_backoff_seconds", 900)),
                    )
                if spark_backoff is not None:
                    until = utc_now() + dt.timedelta(seconds=spark_backoff)
                    set_account_spark_backoff(account_alias, until, f"spark pool unavailable for {spark_backoff}s")
                    with db() as conn:
                        conn.execute(
                            """
                            UPDATE runs
                            SET status='rate_limited', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='spark_pool', error_message=?
                            WHERE id=?
                            """,
                            (
                                rc,
                                iso(finished_at),
                                input_tokens,
                                cached_input_tokens,
                                output_tokens,
                                est_cost,
                                f"spark pool unavailable for {spark_backoff}s",
                                run_id,
                            ),
                        )
                    update_project_status(
                        project_id,
                        status=READY_STATUS,
                        current_slice=slice_name,
                        active_run_id=None,
                        cooldown_until=utc_now() + dt.timedelta(seconds=1),
                        last_run_at=finished_at,
                        last_error=f"spark pool unavailable for {spark_backoff}s",
                        consecutive_failures=0,
                        spider_tier=decision["tier"],
                        spider_model=selected_model,
                        spider_reason=decision_reason,
                    )
                else:
                    auth_failure = parse_auth_failure_message(raw_log)
                    if auth_failure is not None:
                        until = finished_at + dt.timedelta(
                            seconds=max(600, int(get_policy(config, "auth_failure_backoff_seconds", 43200) or 43200))
                        )
                        message = f"{auth_failure}; recheck after credentials are refreshed"
                        set_account_backoff(account_alias, until, message)
                        with db() as conn:
                            conn.execute(
                                """
                                UPDATE runs
                                SET status='rejected', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='auth', error_message=?
                                WHERE id=?
                                """,
                                (rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, message, run_id),
                            )
                        update_project_status(
                            project_id,
                            status=READY_STATUS,
                            current_slice=slice_name,
                            active_run_id=None,
                            cooldown_until=until,
                            last_run_at=finished_at,
                            last_error=message,
                            consecutive_failures=0,
                            spider_tier=decision["tier"],
                            spider_model=selected_model,
                            spider_reason=decision_reason,
                        )
                    else:
                        usage_limit_backoff = parse_usage_limit_backoff_seconds(
                            raw_log,
                            int(get_policy(config, "chatgpt_usage_limit_backoff_seconds", 21600)),
                            now=finished_at,
                        )
                        if usage_limit_backoff is not None:
                            reset_at = parse_usage_limit_reset_at(raw_log)
                            reprobe_seconds = max(
                                300,
                                int(get_policy(config, "chatgpt_usage_limit_probe_interval_seconds", 7200) or 7200),
                            )
                            until = finished_at + dt.timedelta(seconds=min(usage_limit_backoff, reprobe_seconds))
                            if reset_at is not None and reset_at < until:
                                until = reset_at
                            message = (
                                f"usage-limited; recheck at {iso(until)} (provider reset {iso(reset_at)})"
                                if reset_at and reset_at > until
                                else f"usage-limited until {iso(reset_at) or iso(until)}"
                                if reset_at
                                else f"usage-limited; recheck at {iso(until)}"
                            )
                            set_account_backoff(account_alias, until, message)
                            with db() as conn:
                                conn.execute(
                                    """
                                    UPDATE runs
                                    SET status='rate_limited', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='usage_limit', error_message=?
                                    WHERE id=?
                                    """,
                                    (rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, message, run_id),
                                )
                            update_project_status(
                                project_id,
                                status=READY_STATUS,
                                current_slice=slice_name,
                                active_run_id=None,
                                cooldown_until=finished_at + dt.timedelta(seconds=5),
                                last_run_at=finished_at,
                                last_error=message,
                                consecutive_failures=0,
                                spider_tier=decision["tier"],
                                spider_model=selected_model,
                                spider_reason=decision_reason,
                            )
                        else:
                            unsupported_model = parse_unsupported_chatgpt_model(raw_log)
                            if unsupported_model is not None:
                                until = utc_now() + dt.timedelta(hours=12)
                                message = (
                                    f"chatgpt auth rejected model {unsupported_model}; "
                                    "quarantine this account until credentials are replaced with a Codex-compatible auth flow"
                                )
                                set_account_backoff(account_alias, until, message)
                                with db() as conn:
                                    conn.execute(
                                        """
                                        UPDATE runs
                                        SET status='rejected', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='model_compat', error_message=?
                                        WHERE id=?
                                        """,
                                        (rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, message, run_id),
                                    )
                                update_project_status(
                                    project_id,
                                    status=READY_STATUS,
                                    current_slice=slice_name,
                                    active_run_id=None,
                                    cooldown_until=utc_now() + dt.timedelta(seconds=5),
                                    last_run_at=finished_at,
                                    last_error=message,
                                    consecutive_failures=0,
                                    spider_tier=decision["tier"],
                                    spider_model=selected_model,
                                    spider_reason=decision_reason,
                                )
                            else:
                                backoff = parse_backoff_seconds(raw_log, int(get_policy(config, "rate_limit_backoff_base", 60)))
                                if backoff is not None:
                                    until = utc_now() + dt.timedelta(seconds=backoff)
                                    set_account_backoff(account_alias, until, f"rate limited for {backoff}s")
                                    with db() as conn:
                                        conn.execute(
                                            """
                                            UPDATE runs
                                            SET status='rate_limited', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='rate_limit', error_message=?
                                            WHERE id=?
                                            """,
                                            (rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, f"rate limited for {backoff}s", run_id),
                                        )
                                    update_project_status(
                                        project_id,
                                        status=READY_STATUS,
                                        current_slice=slice_name,
                                        active_run_id=None,
                                        cooldown_until=until,
                                        last_run_at=finished_at,
                                        last_error=f"rate limited for {backoff}s",
                                        consecutive_failures=failures,
                                        spider_tier=decision["tier"],
                                        spider_model=selected_model,
                                        spider_reason=decision_reason,
                                    )
                                else:
                                    msg = f"codex exec failed with exit {rc}"
                                    with db() as conn:
                                        conn.execute(
                                            """
                                            UPDATE runs
                                            SET status='failed', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='exec', error_message=?
                                            WHERE id=?
                                            """,
                                            (rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, msg, run_id),
                                        )
                                    max_failures = int(get_policy(config, "max_consecutive_failures", 3))
                                    status = "blocked" if failures >= max_failures else READY_STATUS
                                    cooldown = utc_now() + dt.timedelta(seconds=int(get_policy(config, "restart_cooldown_seconds", 120)))
                                    update_project_status(
                                        project_id,
                                        status=status,
                                        current_slice=slice_name,
                                        active_run_id=None,
                                        cooldown_until=cooldown,
                                        last_run_at=finished_at,
                                        last_error=msg,
                                        consecutive_failures=failures,
                                        spider_tier=decision["tier"],
                                        spider_model=selected_model,
                                        spider_reason=decision_reason,
                                    )
    except Exception as exc:
        finished_at = utc_now()
        msg = str(exc)
        with db() as conn:
            conn.execute(
                "UPDATE runs SET status='failed', finished_at=?, error_class='controller', error_message=? WHERE id=?",
                (iso(finished_at), msg, run_id),
            )
            row = conn.execute("SELECT consecutive_failures FROM projects WHERE id=?", (project_id,)).fetchone()
            failures = int((row["consecutive_failures"] if row else 0) + 1)
        max_failures = int(get_policy(config, "max_consecutive_failures", 3))
        status = "blocked" if failures >= max_failures else READY_STATUS
        cooldown = utc_now() + dt.timedelta(seconds=int(get_policy(config, "restart_cooldown_seconds", 120)))
        update_project_status(
            project_id,
            status=status,
            current_slice=slice_name,
            active_run_id=None,
            cooldown_until=cooldown,
            last_run_at=finished_at,
            last_error=msg,
            consecutive_failures=failures,
            spider_tier=decision["tier"],
            spider_model=selected_model,
            spider_reason=decision_reason,
        )
    finally:
        record_account_run_outcome(account_alias, selected_model, success=account_run_succeeded)
        state.tasks.pop(project_id, None)
        if pending_local_review_reason:
            with db() as conn:
                fresh_project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            pr_row = pull_request_row(project_id)
            if fresh_project_row and pr_row:
                task = asyncio.create_task(
                    execute_local_review_fallback(
                        config,
                        project_cfg,
                        fresh_project_row,
                        pr_row,
                        reason=pending_local_review_reason,
                    )
                )
                state.tasks[project_id] = task


async def execute_local_review_fallback(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    project_row: sqlite3.Row,
    pr_row: Dict[str, Any],
    *,
    reason: str,
) -> None:
    project_id = str(project_cfg["id"] or "").strip()
    slice_name = current_slice(project_row) or review_slice_name(project_id) or f"Review {project_id}"
    review = project_review_policy(project_cfg)
    encoded_review_focus = str(pr_row.get("review_focus") or review_focus_text(project_cfg, slice_name)).strip()
    review_focus, review_metadata = decode_review_focus(encoded_review_focus)
    reviewer_lane = str(review_metadata.get("reviewer_lane") or "core").strip().lower() or "core"
    reviewer_model = str(
        review_metadata.get("reviewer_model") or reviewer_runtime_model_for_lane(config.get("lanes") or {}, reviewer_lane)
    ).strip()
    workflow_kind = str(review_metadata.get("workflow_kind") or "default").strip().lower()
    max_review_rounds = int(review_metadata.get("max_review_rounds") or 0)
    review_round = max(1, int(pr_row.get("review_round") or review_metadata.get("review_round") or 1))
    final_reviewer_lane = review_focus_final_reviewer_lane(review_metadata)
    jury_acceptance_required = metadata_flag(review_metadata.get("jury_acceptance_required"))
    final_review_required = workflow_kind == WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP and jury_acceptance_required
    final_reviewer_pending = final_review_required and reviewer_lane == final_reviewer_lane
    review_packet = json_field(review_metadata.get("review_packet"), {}) if review_metadata.get("review_packet") else {}
    base_branch = str(pr_row.get("base_branch") or review.get("base_branch") or "main").strip() or "main"
    prompt = build_local_review_prompt(
        project_cfg,
        slice_name=slice_name,
        base_branch=base_branch,
        review_focus=review_focus,
        reason=reason,
        review_round=review_round,
        max_review_rounds=max_review_rounds,
        review_packet=review_packet if isinstance(review_packet, dict) else {},
    )
    decision = {
        "tier": "inspect",
        "model_preferences": [reviewer_model] if reviewer_model else ["gpt-5-mini", "gpt-5.4", "gpt-5.3-codex"],
        "reasoning_effort": "medium" if reviewer_lane in {"core", "jury"} else "low",
        "estimated_input_tokens": max(512, len(prompt) // 4),
        "estimated_output_tokens": 1200,
        "estimated_prompt_chars": len(prompt),
        "reason": f"local review fallback: {reason}; reviewer_lane={reviewer_lane}",
    }
    account_alias = choose_review_account_alias(config, project_cfg, reviewer_lane=reviewer_lane)
    selected_model = reviewer_model
    selection_note = f"reviewer_lane={reviewer_lane}; reviewer_model={reviewer_model or 'unset'}"
    selection_trace = [
        {
            "alias": account_alias or "",
            "requested_lane": reviewer_lane,
            "selected": bool(account_alias and selected_model),
            "state": "selected" if account_alias and selected_model else "rejected",
            "reason": selection_note if account_alias and selected_model else f"no ready reviewer account for lane {reviewer_lane}",
        }
    ]
    if not account_alias or not selected_model:
        retry_at = utc_now() + dt.timedelta(seconds=max(60, int(get_policy(config, "review_poll_interval_seconds", 30) or 30)))
        update_project_status(
            project_id,
            status=review_hold_status_for_project(project_id),
            current_slice=slice_name,
            active_run_id=None,
            cooldown_until=retry_at,
            last_run_at=utc_now(),
            last_error=f"local review fallback could not select an account/model: {selection_note}",
            spider_tier="inspect",
            spider_model=None,
            spider_reason=str(reason),
        )
        state.tasks.pop(project_id, None)
        return

    started_at = utc_now()
    ts = started_at.strftime("%Y%m%dT%H%M%SZ")
    safe_slice = re.sub(r"[^a-zA-Z0-9._-]+", "-", slice_name)[:80]
    log_path = LOG_DIR / project_id / f"{ts}-{safe_slice}.local-review.jsonl"
    prompt_path = LOG_DIR / project_id / f"{ts}-{safe_slice}.local-review.prompt.txt"
    final_message_path = LOG_DIR / project_id / f"{ts}-{safe_slice}.local-review.final.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    decision_reason = f"{decision['reason']}; {selection_note}"

    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
            VALUES (?, ?, 'local_review', ?, 'starting', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                account_alias,
                slice_name,
                selected_model,
                decision["reasoning_effort"],
                "inspect",
                decision_reason,
                iso(started_at),
                str(log_path),
                str(final_message_path),
                str(prompt_path),
            ),
        )
        run_id = int(cur.lastrowid)
        conn.execute(
            """
            UPDATE pull_requests
            SET review_status=?,
                local_review_attempts=local_review_attempts + 1,
                review_round=?,
                local_review_last_at=?,
                next_retry_at=NULL,
                review_rate_limit_reset_at=NULL,
                updated_at=?
            WHERE project_id=?
            """,
            (LOCAL_REVIEW_PENDING_STATUS, review_round, iso(started_at), iso(started_at), project_id),
        )

    update_project_status(
        project_id,
        status="running",
        current_slice=slice_name,
        active_run_id=run_id,
        cooldown_until=None,
        last_run_at=started_at,
        last_error=f"local fallback review running: {reason}",
        spider_tier="inspect",
        spider_model=selected_model,
        spider_reason=decision_reason,
    )

    pending_followup_local_review_reason: Optional[str] = None
    try:
        account_cfg = (config.get("accounts") or {}).get(account_alias, {})
        runner = project_cfg.get("runner") or {}
        env = prepare_account_environment(account_alias, account_cfg)
        touch_account(account_alias)
        with db() as conn:
            conn.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
        cmd = [
            "codex",
            "--ask-for-approval",
            "never",
            "exec",
            "--json",
            "--cd",
            project_cfg["path"],
            "--sandbox",
            "read-only",
            "--model",
            selected_model,
            "--output-last-message",
            str(final_message_path),
        ]
        if reviewer_model.startswith("ea-"):
            for override in runner.get("config_overrides", []) or []:
                cmd += ["-c", str(override)]
        cmd += ["-c", f"model_reasoning_effort={json.dumps(decision['reasoning_effort'])}"]
        cmd += ["-"]
        timeout_seconds = max(600, int(get_policy(config, "verify_timeout_seconds", 1800) or 1800))
        idle_timeout_seconds = max(300, min(timeout_seconds, 900))
        rc_result = await run_command(
            cmd,
            cwd=project_cfg["path"],
            env=env,
            input_text=prompt,
            log_path=log_path,
            timeout_seconds=timeout_seconds,
            idle_timeout_seconds=idle_timeout_seconds,
        )
        finished_at = utc_now()
        raw_log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        final_text = final_message_path.read_text(encoding="utf-8", errors="replace") if final_message_path.exists() else ""
        input_tokens, cached_input_tokens, output_tokens = parse_jsonl_usage(log_path)
        est_cost = estimate_cost_usd_for_model(
            config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE,
            selected_model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        )

        if rc_result.exit_code != 0:
            if rc_result.idle_timed_out:
                error_message = f"local fallback review stalled without log output for {rc_result.idle_timeout_seconds}s"
            elif rc_result.timed_out:
                error_message = f"local fallback review timed out after {rc_result.timeout_seconds}s"
            else:
                error_message = f"local fallback review failed with exit {rc_result.exit_code}"
            auth_failure = parse_auth_failure_message(raw_log)
            if auth_failure is not None:
                cooldown_until = finished_at + dt.timedelta(
                    seconds=max(600, int(get_policy(config, "auth_failure_backoff_seconds", 43200) or 43200))
                )
                error_message = f"{auth_failure}; recheck after credentials are refreshed"
                set_account_backoff(account_alias, cooldown_until, error_message)
            else:
                usage_limit_backoff = parse_usage_limit_backoff_seconds(
                    raw_log,
                    int(get_policy(config, "chatgpt_usage_limit_backoff_seconds", 21600) or 21600),
                    now=finished_at,
                )
                if usage_limit_backoff is not None:
                    reset_at = parse_usage_limit_reset_at(raw_log)
                    reprobe_seconds = max(
                        300,
                        int(get_policy(config, "chatgpt_usage_limit_probe_interval_seconds", 7200) or 7200),
                    )
                    cooldown_until = finished_at + dt.timedelta(seconds=min(usage_limit_backoff, reprobe_seconds))
                    if reset_at is not None and reset_at < cooldown_until:
                        cooldown_until = reset_at
                    error_message = (
                        f"usage-limited; recheck at {iso(cooldown_until)} (provider reset {iso(reset_at)})"
                        if reset_at and reset_at > cooldown_until
                        else f"usage-limited until {iso(reset_at) or iso(cooldown_until)}"
                        if reset_at
                        else f"usage-limited; recheck at {iso(cooldown_until)}"
                    )
                    set_account_backoff(account_alias, cooldown_until, error_message)
                else:
                    backoff = parse_backoff_seconds(raw_log, int(get_policy(config, "rate_limit_backoff_base", 60) or 60))
                    cooldown_until = utc_now() + dt.timedelta(seconds=backoff or max(60, int(get_policy(config, "review_poll_interval_seconds", 30) or 30)))
                    if backoff is not None:
                        set_account_backoff(account_alias, cooldown_until, f"local review fallback rate limited for {backoff}s")
            with db() as conn:
                conn.execute(
                    """
                    UPDATE runs
                    SET status='review_failed', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='local_review', error_message=?
                    WHERE id=?
                    """,
                    (rc_result.exit_code, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, error_message, run_id),
                )
                conn.execute(
                    """
                    UPDATE pull_requests
                    SET review_status=?,
                        local_review_last_at=?,
                        next_retry_at=?,
                        updated_at=?
                    WHERE project_id=?
                    """,
                    (review_hold_status_for_project(project_id), iso(finished_at), iso(cooldown_until), iso(finished_at), project_id),
                )
            update_project_status(
                project_id,
                status=review_hold_status_for_project(project_id),
                current_slice=slice_name,
                active_run_id=None,
                cooldown_until=cooldown_until,
                last_run_at=finished_at,
                last_error=error_message,
                spider_tier="inspect",
                spider_model=selected_model,
                spider_reason=decision_reason,
            )
            return

        latest_pr = pull_request_row(project_id) or {}
        if str(latest_pr.get("review_status") or "").strip().lower() != LOCAL_REVIEW_PENDING_STATUS:
            with db() as conn:
                conn.execute(
                    """
                    UPDATE runs
                    SET status='abandoned', finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='local_review_superseded', error_message=?
                    WHERE id=?
                    """,
                    (iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, "local fallback review was superseded by a newer review state", run_id),
                )
            runtime_status = persisted_review_runtime_status(project_id) or review_hold_status_for_project(project_id)
            update_project_status(
                project_id,
                status=runtime_status,
                current_slice=review_slice_name(project_id, fallback=slice_name),
                active_run_id=None,
                cooldown_until=utc_now() + dt.timedelta(seconds=1),
                last_run_at=finished_at,
                last_error="local fallback review was superseded by GitHub review state",
                spider_tier="inspect",
                spider_model=selected_model,
                spider_reason=decision_reason,
            )
            return

        parsed = parse_local_review_result(final_text or raw_log)
        findings = parsed["findings"]
        blocking_issues = list(parsed.get("blocking_issues") or [])
        non_blocking_issues = list(parsed.get("non_blocking_issues") or [])
        verdict = str(parsed["verdict"] or "accept").strip().lower()
        summary = str(parsed.get("summary") or "").strip()
        repeat_issue_ids = [str(item).strip() for item in parsed.get("repeat_issue_ids") or [] if str(item).strip()]
        pr_number = int(latest_pr.get("pr_number") or 0)
        pr_url = str(latest_pr.get("pr_url") or "")
        now_iso = iso(finished_at)
        review_duration = run_duration_ms(iso(started_at), now_iso)
        blocking_count = sum(1 for item in findings if bool(item.get("blocking")))
        issue_ids = [str(item.get("external_id") or "").strip() for item in findings if str(item.get("external_id") or "").strip()]
        history = list(json_field(latest_pr.get("jury_feedback_history_json"), []))
        history.append(
            {
                "reviewer_lane": reviewer_lane,
                "reviewer_model": reviewer_model,
                "review_round": review_round,
                "verdict": verdict,
                "summary": summary,
                "blocking_issue_count": blocking_count,
                "blocking_issues": blocking_issues,
                "non_blocking_issues": non_blocking_issues,
                "repeat_issue_ids": repeat_issue_ids,
                "confidence": parsed.get("confidence"),
                "core_rescue_recommended": bool(parsed.get("core_rescue_recommended")),
            }
        )
        issue_fingerprints_json = _merge_issue_fingerprints(latest_pr.get("issue_fingerprints_json"), [*issue_ids, *repeat_issue_ids])
        blocking_by_round_json = _set_round_metric(latest_pr.get("blocking_issue_count_by_round_json"), review_round, blocking_count)
        repeat_by_round_json = _set_round_metric(latest_pr.get("repeat_issue_count_by_round_json"), review_round, len(repeat_issue_ids))
        allowance_burn_json = _merge_allowance_burn(latest_pr.get("allowance_burn_by_lane_json"), reviewer_lane, est_cost)

        workflow_is_groundwork_loop = workflow_kind == WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP
        loop_exhausted = workflow_is_groundwork_loop and max_review_rounds > 0 and review_round >= max_review_rounds
        core_used = bool(int(latest_pr.get("core_time_ms") or 0))
        requested_core_rescue = verdict == "core_rescue_required" or bool(parsed.get("core_rescue_recommended")) or loop_exhausted
        pending_core_rescue = requested_core_rescue and not core_used
        updated_focus_metadata = dict(review_metadata)
        updated_focus_metadata["slice_key"] = str(updated_focus_metadata.get("slice_key") or review_slice_key(slice_name))
        updated_focus_metadata["review_round"] = str(review_round)
        updated_focus_metadata["final_reviewer_lane"] = final_reviewer_lane
        updated_focus_metadata["core_rescue_required"] = "true" if pending_core_rescue else "false"
        updated_focus_metadata["review_packet"] = json.dumps(review_packet if isinstance(review_packet, dict) else {}, sort_keys=True)
        encoded_focus = encode_review_focus(
            review_focus,
            reviewer_lane=reviewer_lane,
            reviewer_model=reviewer_model,
            metadata=updated_focus_metadata,
        )
        accepted_on_round = "core" if core_used else str(review_round)
        pass_without_core = 0 if core_used else 1

        if verdict == "accept":
            if workflow_is_groundwork_loop and final_review_required and not final_reviewer_pending:
                sync_review_findings(project_id, pr_number, [])
                jury_model = reviewer_runtime_model_for_lane(config.get("lanes") or {}, final_reviewer_lane)
                jury_focus = encode_review_focus(
                    review_focus,
                    reviewer_lane=final_reviewer_lane,
                    reviewer_model=jury_model,
                    metadata=updated_focus_metadata,
                )
                with db() as conn:
                    conn.execute(
                        """
                        UPDATE pull_requests
                        SET review_status=?,
                            review_focus=?,
                            review_completed_at=?,
                            review_round=?,
                            review_findings_count=0,
                            review_blocking_findings_count=0,
                            first_review_complete_at=COALESCE(first_review_complete_at, ?),
                            needs_core_rescue=0,
                            core_rescue_reason='',
                            jury_feedback_history_json=?,
                            issue_fingerprints_json=?,
                            blocking_issue_count_by_round_json=?,
                            repeat_issue_count_by_round_json=?,
                            jury_time_ms=COALESCE(jury_time_ms, 0) + ?,
                            allowance_burn_by_lane_json=?,
                            last_synced_at=?,
                            review_sync_failures=0,
                            review_wakeup_miss_count=0,
                            local_review_last_at=?,
                            next_retry_at=NULL,
                            review_rate_limit_reset_at=NULL,
                            updated_at=?
                        WHERE project_id=?
                        """,
                        (
                            REVIEW_FALLBACK_CLEAN_STATUS,
                            encoded_focus,
                            now_iso,
                            review_round,
                            now_iso,
                            json.dumps(history, sort_keys=True),
                            issue_fingerprints_json,
                            blocking_by_round_json,
                            repeat_by_round_json,
                            review_duration,
                            allowance_burn_json,
                            now_iso,
                            now_iso,
                            now_iso,
                            project_id,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE runs
                        SET status=?, exit_code=0, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                        WHERE id=?
                        """,
                        (JURY_REVIEW_PENDING_STATUS, now_iso, input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
                    )
                followup_pr = upsert_local_review_request(
                    project_cfg,
                    slice_name=slice_name,
                    requested_at=finished_at,
                    review_focus=jury_focus,
                    workflow_state={
                        "workflow_kind": workflow_kind,
                        "review_round": review_round,
                        "max_review_rounds": max_review_rounds,
                    },
                )
                upsert_github_review_run(
                    project_id,
                    slice_name=slice_name,
                    pr_number=pr_number,
                    pr_url=pr_url,
                    review_status=JURY_REVIEW_PENDING_STATUS,
                    review_focus=f"{review_focus} ; fallback=local_review".strip(),
                )
                update_project_status(
                    project_id,
                    status=review_hold_status_for_project(project_id, project_cfg=project_cfg, pr_row=followup_pr),
                    current_slice=slice_name,
                    active_run_id=None,
                    cooldown_until=utc_now() + dt.timedelta(seconds=1),
                    last_run_at=finished_at,
                    last_error=f"{reviewer_lane} accepted round {review_round}; requesting {final_reviewer_lane} final signoff",
                    spider_tier="inspect",
                    spider_model=selected_model,
                    spider_reason=decision_reason,
                )
                pending_followup_local_review_reason = (
                    f"{reviewer_lane} accepted round {review_round}; request {final_reviewer_lane} final signoff"
                )
                return
            run_status = (
                accepted_loop_review_status(review_round, core_used=core_used)
                if workflow_is_groundwork_loop
                else REVIEW_FALLBACK_CLEAN_STATUS
            )
            sync_review_findings(project_id, pr_number, [])
            with db() as conn:
                conn.execute(
                    """
                    UPDATE pull_requests
                    SET review_status=?,
                        review_focus=?,
                        review_completed_at=?,
                        review_round=?,
                        review_findings_count=0,
                        review_blocking_findings_count=0,
                        first_review_complete_at=COALESCE(first_review_complete_at, ?),
                        accepted_on_round=?,
                        needs_core_rescue=0,
                        core_rescue_reason='',
                        jury_feedback_history_json=?,
                        issue_fingerprints_json=?,
                        blocking_issue_count_by_round_json=?,
                        repeat_issue_count_by_round_json=?,
                        jury_time_ms=COALESCE(jury_time_ms, 0) + ?,
                        allowance_burn_by_lane_json=?,
                        pass_without_core=?,
                        last_synced_at=?,
                        review_sync_failures=0,
                        review_wakeup_miss_count=0,
                        local_review_last_at=?,
                        next_retry_at=NULL,
                        review_rate_limit_reset_at=NULL,
                        updated_at=?
                    WHERE project_id=?
                    """,
                    (
                        REVIEW_FALLBACK_CLEAN_STATUS,
                        encoded_focus,
                        now_iso,
                        review_round,
                        now_iso,
                        accepted_on_round,
                        json.dumps(history, sort_keys=True),
                        issue_fingerprints_json,
                        blocking_by_round_json,
                        repeat_by_round_json,
                        review_duration,
                        allowance_burn_json,
                        pass_without_core,
                        now_iso,
                        now_iso,
                        now_iso,
                        project_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE runs
                    SET status=?, exit_code=0, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                    WHERE id=?
                    """,
                    (run_status, now_iso, input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
                )
            upsert_github_review_run(
                project_id,
                slice_name=slice_name,
                pr_number=pr_number,
                pr_url=pr_url,
                review_status=run_status,
                review_focus=f"{review_focus} ; fallback=local_review".strip(),
            )
            complete_project_slice_after_review(project_cfg, finished_at)
            return

        sync_review_findings(project_id, pr_number, findings)
        publish_review_feedback(project_cfg, pr_url or f"local://{project_id}", findings)
        if workflow_is_groundwork_loop:
            if verdict == "manual_hold":
                next_status = MANUAL_HOLD_STATUS
            elif final_reviewer_pending and core_used:
                next_status = MANUAL_HOLD_STATUS
                pending_core_rescue = False
            elif pending_core_rescue:
                next_status = CORE_RESCUE_PENDING_STATUS
            else:
                next_status = JURY_REWORK_REQUIRED_STATUS
        else:
            next_status = MANUAL_HOLD_STATUS if verdict == "manual_hold" else "review_fix_required"
        error_summary = summary or (
            f"{reviewer_lane} requested manual hold"
            if verdict == "manual_hold"
            else f"{reviewer_lane} rejected the slice after core rescue; manual hold required"
            if next_status == MANUAL_HOLD_STATUS and final_reviewer_pending and core_used
            else f"{reviewer_lane} requested core rescue"
            if pending_core_rescue
            else f"{reviewer_lane} published findings for follow-up"
        )
        with db() as conn:
            conn.execute(
                """
                UPDATE pull_requests
                SET review_status=?,
                    review_focus=?,
                    review_completed_at=?,
                    review_round=?,
                    review_findings_count=?,
                    review_blocking_findings_count=?,
                    first_review_complete_at=COALESCE(first_review_complete_at, ?),
                    needs_core_rescue=?,
                    core_rescue_reason=?,
                    jury_feedback_history_json=?,
                    issue_fingerprints_json=?,
                    blocking_issue_count_by_round_json=?,
                    repeat_issue_count_by_round_json=?,
                    jury_time_ms=COALESCE(jury_time_ms, 0) + ?,
                    allowance_burn_by_lane_json=?,
                    last_synced_at=?,
                    review_sync_failures=0,
                    review_wakeup_miss_count=0,
                    local_review_last_at=?,
                    next_retry_at=NULL,
                    review_rate_limit_reset_at=NULL,
                    updated_at=?
                WHERE project_id=?
                """,
                (
                    next_status,
                    encoded_focus,
                    now_iso,
                    review_round,
                    len(findings),
                    blocking_count,
                    now_iso,
                    1 if pending_core_rescue else 0,
                    error_summary if pending_core_rescue else "",
                    json.dumps(history, sort_keys=True),
                    issue_fingerprints_json,
                    blocking_by_round_json,
                    repeat_by_round_json,
                    review_duration,
                    allowance_burn_json,
                    now_iso,
                    now_iso,
                    now_iso,
                    project_id,
                ),
            )
            conn.execute(
                """
                UPDATE runs
                SET status=?, exit_code=0, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                WHERE id=?
                """,
                (next_status, now_iso, input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
            )
        upsert_github_review_run(
            project_id,
            slice_name=slice_name,
            pr_number=pr_number,
            pr_url=pr_url,
            review_status=next_status,
            review_focus=f"{review_focus} ; fallback=local_review".strip(),
        )
        update_project_status(
            project_id,
            status=next_status,
            current_slice=slice_name,
            active_run_id=None,
            cooldown_until=utc_now() + dt.timedelta(seconds=1),
            last_run_at=finished_at,
            last_error=error_summary,
            spider_tier="inspect",
            spider_model=selected_model,
            spider_reason=decision_reason,
        )
    finally:
        state.tasks.pop(project_id, None)
        if pending_followup_local_review_reason:
            with db() as conn:
                fresh_project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            fresh_pr_row = pull_request_row(project_id)
            if fresh_project_row and fresh_pr_row:
                task = asyncio.create_task(
                    execute_local_review_fallback(
                        config,
                        project_cfg,
                        fresh_project_row,
                        fresh_pr_row,
                        reason=pending_followup_local_review_reason,
                    )
                )
                state.tasks[project_id] = task


async def scheduler_loop() -> None:
    while not state.stop.is_set():
        prune_finished_tasks()
        config = normalize_config()
        try:
            if bool(get_policy(config, "auto_heal_enabled", True)):
                auto_publish_approved_audit_candidates(config)
            config = normalize_config()
            sync_config_to_db(config)
            normalize_usage_limit_account_backoffs(config)
            sync_design_repo_mirrors_if_safe(config)
            reconcile_stale_worker_sessions(config)
            reconcile_finished_run_links()
            heal_pending_pull_request_reviews(config)
            heal_orphaned_local_reviews(config)
            sync_pending_github_reviews(config)
            heal_stalled_github_reviews(config)
            reconcile_project_incidents()
            sync_group_runtime_phase(config)
            request_due_group_audits(config)
            max_parallel = int(get_policy(config, "max_parallel_runs", 3))
            with db() as conn:
                projects = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
            now = utc_now()
            registry = load_program_registry(config)
            group_runtime = group_runtime_rows()
            active_project_ids = {
                str(row["id"] or "").strip()
                for row in projects
                if str(row["id"] or "").strip()
                and (bool(row["active_run_id"]) or str(row["status"] or "").strip() in {"starting", "running", "verifying"})
            }
            active_codex_projects = codex_active_project_ids(projects)
            reconcile_runtime_tasks(active_project_ids)
            running_count = len(active_codex_projects)
            reserved_account_counts: Dict[str, int] = {}
            candidates: Dict[str, DispatchCandidate] = {}
            for row in projects:
                project_id = row["id"]
                if project_id in active_project_ids or (project_id in state.tasks and not state.tasks[project_id].done()):
                    continue
                project_cfg = get_project_cfg(config, project_id)
                candidates[project_id] = prepare_dispatch_candidate(config, project_cfg, row, now)

            handled_projects: set[str] = set()
            running_by_group: Dict[str, int] = {}
            for running_project_id in active_codex_projects:
                for running_group in project_group_defs(config, running_project_id):
                    group_id = str(running_group.get("id") or "").strip()
                    if group_id:
                        running_by_group[group_id] = int(running_by_group.get(group_id) or 0) + 1
            bridge_services = bridge_service_definitions(config)
            active_named_bridge_count = active_bridge_service_count(
                config,
                reserved_account_counts=reserved_account_counts,
            )
            pressure_high = max_parallel > 0 and running_count >= max_parallel
            lockstep_groups = sorted(
                [group for group in (config.get("project_groups") or []) if str(group.get("mode", "") or "").strip().lower() == "lockstep"],
                key=lambda group: captain_dispatch_key(group_cfg=group, running_by_group=running_by_group, pressure_high=pressure_high),
            )
            for group in lockstep_groups:
                if str(group.get("mode", "") or "").strip().lower() != "lockstep":
                    continue
                member_ids = [project_id for project_id in (group.get("projects") or []) if project_id in candidates]
                if not member_ids:
                    continue
                if any(project_id in active_project_ids for project_id in member_ids):
                    continue
                group_projects = [
                    {
                        "id": project_id,
                        "status_internal": candidates[project_id].runtime_status,
                        "queue_index": candidates[project_id].queue_index,
                        "queue": candidates[project_id].queue,
                        "cooldown_until": iso(candidates[project_id].cooldown_until),
                        "enabled": bool(candidates[project_id].project_cfg.get("enabled", True)),
                    }
                    for project_id in member_ids
                ]
                group_meta = effective_group_meta(group, registry, group_runtime)
                dispatch = group_dispatch_state(group, group_meta, group_projects, now)
                launch_plan: List[PlannedLaunch] = []
                if dispatch["dispatch_ready"] and running_count + len(member_ids) <= max_parallel:
                    group_blocked = False
                    group_reserved_account_counts: Dict[str, int] = {}
                    for project_id in member_ids:
                        effective_reserved_account_counts = dict(reserved_account_counts)
                        for alias, count in group_reserved_account_counts.items():
                            effective_reserved_account_counts[alias] = int(effective_reserved_account_counts.get(alias) or 0) + int(count)
                        planned = plan_candidate_launch(
                            config,
                            candidates[project_id],
                            reserved_account_counts=effective_reserved_account_counts,
                        )
                        if not planned:
                            group_blocked = True
                            break
                        launch_plan.append(planned)
                        group_reserved_account_counts[planned.account_alias] = int(group_reserved_account_counts.get(planned.account_alias) or 0) + 1
                    if group_blocked:
                        launch_plan = []
                    else:
                        for alias, count in group_reserved_account_counts.items():
                            reserved_account_counts[alias] = int(reserved_account_counts.get(alias) or 0) + int(count)
                else:
                    available_slots = max(0, max_parallel - running_count)
                    wave_ids = select_lockstep_wave_candidates(
                        group=group,
                        group_meta=group_meta,
                        member_ids=member_ids,
                        candidates=candidates,
                        available_slots=available_slots,
                    )
                    group_reserved_account_counts = {}
                    for project_id in wave_ids:
                        effective_reserved_account_counts = dict(reserved_account_counts)
                        for alias, count in group_reserved_account_counts.items():
                            effective_reserved_account_counts[alias] = int(effective_reserved_account_counts.get(alias) or 0) + int(count)
                        planned = plan_candidate_launch(
                            config,
                            candidates[project_id],
                            reserved_account_counts=effective_reserved_account_counts,
                        )
                        if planned:
                            launch_plan.append(planned)
                            group_reserved_account_counts[planned.account_alias] = int(group_reserved_account_counts.get(planned.account_alias) or 0) + 1
                    for alias, count in group_reserved_account_counts.items():
                        reserved_account_counts[alias] = int(reserved_account_counts.get(alias) or 0) + int(count)
                if not launch_plan:
                    continue
                handled_projects.update(planned.project_id for planned in launch_plan)

                for planned in launch_plan:
                    project_id = planned.project_id
                    candidate = planned.candidate
                    task = asyncio.create_task(
                        execute_project_slice(
                            config,
                            candidate.project_cfg,
                            candidate.row,
                            candidate.slice_name or "",
                            planned.decision,
                            planned.account_alias,
                            planned.selected_model,
                            planned.selection_note,
                            planned.selection_trace,
                        )
                    )
                    state.tasks[project_id] = task
                    running_count += 1
                if launch_plan:
                    launch_mode = "lockstep" if dispatch["dispatch_ready"] and len(launch_plan) == len(member_ids) else "lockstep_wave"
                    log_group_run(
                        str(group.get("id") or ""),
                        run_kind="dispatch",
                        phase="running",
                        status="dispatched",
                        member_projects=[planned.project_id for planned in launch_plan],
                        details={
                            "mode": launch_mode,
                            "slices": {planned.project_id: planned.candidate.slice_name for planned in launch_plan},
                            "blocked_members": [
                                project_id
                                for project_id in member_ids
                                if project_id not in {planned.project_id for planned in launch_plan}
                            ],
                        },
                    )
                    running_by_group[str(group.get("id") or "")] = int(running_by_group.get(str(group.get("id") or "")) or 0) + len(launch_plan)

            idle_named_bridge_aliases = idle_bridge_service_aliases(
                config,
                reserved_account_counts=reserved_account_counts,
            )
            named_bridge_floor = max(0, int(get_policy(config, "named_bridge_service_floor", 2)))
            prioritize_named_bridge_fill = (
                bool(idle_named_bridge_aliases)
                and active_named_bridge_count < min(named_bridge_floor, len(bridge_services))
            )

            ordered_rows = sorted(
                projects,
                key=lambda item: dispatch_backfill_priority(
                    config=config,
                    row=item,
                    candidate=candidates.get(item["id"]),
                    running_by_group=running_by_group,
                    pressure_high=max_parallel > 0 and running_count >= max_parallel,
                ),
            )
            if prioritize_named_bridge_fill:
                ordered_rows = sorted(
                    ordered_rows,
                    key=lambda item: (
                        0 if candidate_supports_any_alias(candidates.get(item["id"]), idle_named_bridge_aliases) else 1,
                        dispatch_backfill_priority(
                            config=config,
                            row=item,
                            candidate=candidates.get(item["id"]),
                            running_by_group=running_by_group,
                            pressure_high=max_parallel > 0 and running_count >= max_parallel,
                        ),
                    ),
                )
            for row in ordered_rows:
                project_id = row["id"]
                if (
                    project_id in active_project_ids
                    or (project_id in state.tasks and not state.tasks[project_id].done())
                    or project_id in handled_projects
                ):
                    continue
                candidate = candidates.get(project_id)
                if not candidate or not candidate.dispatchable or not candidate.slice_name:
                    continue
                project_groups = project_group_defs(config, project_id)
                if project_groups:
                    group = project_groups[0]
                    group_meta = effective_group_meta(group, registry, group_runtime)
                    dispatch = group_dispatch_state(
                        group,
                        group_meta,
                        [
                            {
                                "id": project_id,
                                "status_internal": candidate.runtime_status,
                                "queue_index": candidate.queue_index,
                                "queue": candidate.queue,
                                "cooldown_until": iso(candidate.cooldown_until),
                                "enabled": bool(candidate.project_cfg.get("enabled", True)),
                                "current_queue_item": candidate.slice_name,
                            }
                        ],
                        now,
                    )
                    if not dispatch["dispatch_ready"]:
                        continue

                if running_count >= max_parallel:
                    break

                planned = plan_candidate_launch(
                    config,
                    candidate,
                    reserved_account_counts=reserved_account_counts,
                )
                if not planned:
                    continue
                reserved_account_counts[planned.account_alias] = int(reserved_account_counts.get(planned.account_alias) or 0) + 1

                task = asyncio.create_task(
                    execute_project_slice(
                        config,
                        planned.candidate.project_cfg,
                        planned.candidate.row,
                        planned.candidate.slice_name or "",
                        planned.decision,
                        planned.account_alias,
                        planned.selected_model,
                        planned.selection_note,
                        planned.selection_trace,
                    )
                )
                state.tasks[project_id] = task
                running_count += 1
                if project_groups:
                    running_by_group[str(project_groups[0].get("id") or "")] = int(running_by_group.get(str(project_groups[0].get("id") or "")) or 0) + 1
                    log_group_run(
                        str(project_groups[0].get("id") or ""),
                        run_kind="dispatch",
                        phase="running",
                        status="dispatched",
                        member_projects=[project_id],
                        details={
                            "mode": str(project_groups[0].get("mode") or "singleton"),
                            "slices": {project_id: planned.candidate.slice_name},
                        },
                    )
            launched_floor = maintain_active_worker_floor(config, candidates, running_count=running_count)
            running_count += launched_floor
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(int(get_policy(config, "scheduler_interval_seconds", 15)))


def alliance_window_start(config: Dict[str, Any]) -> dt.datetime:
    hours = int(config.get("spider", {}).get("token_alliance_window_hours", 24))
    return utc_now() - dt.timedelta(hours=hours)


def summarize_alliance(config: Dict[str, Any]) -> Dict[str, Any]:
    start = alliance_window_start(config)
    with db() as conn:
        totals = conn.execute(
            """
            SELECT
              COALESCE(SUM(input_tokens), 0) AS input_tokens,
              COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
              COALESCE(SUM(output_tokens), 0) AS output_tokens,
              COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd
            FROM runs
            WHERE started_at >= ?
            """,
            (iso(start),),
        ).fetchone()
        by_account = conn.execute(
            """
            SELECT
              account_alias,
              COALESCE(SUM(input_tokens), 0) AS input_tokens,
              COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
              COALESCE(SUM(output_tokens), 0) AS output_tokens,
              COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd,
              COUNT(*) AS run_count
            FROM runs
            WHERE started_at >= ?
            GROUP BY account_alias
            ORDER BY estimated_cost_usd DESC, account_alias
            """,
            (iso(start),),
        ).fetchall()
        by_model = conn.execute(
            """
            SELECT
              model,
              COALESCE(SUM(input_tokens), 0) AS input_tokens,
              COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
              COALESCE(SUM(output_tokens), 0) AS output_tokens,
              COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd,
              COUNT(*) AS run_count
            FROM runs
            WHERE started_at >= ?
            GROUP BY model
            ORDER BY estimated_cost_usd DESC, model
            """,
            (iso(start),),
        ).fetchall()
    return {
        "window_start": iso(start),
        "totals": dict(totals) if totals else {},
        "by_account": [dict(row) for row in by_account],
        "by_model": [dict(row) for row in by_model],
    }


def estimate_project_eta(config: Dict[str, Any], conn: sqlite3.Connection, project: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    queue = project.get("queue") or []
    queue_index = int(project.get("queue_index") or 0)
    remaining_slices = max(len(queue) - queue_index, 0)
    status = str(project.get("status") or "")
    if status == SOURCE_BACKLOG_OPEN_STATUS:
        remaining_slices = len(queue)
    scheduler_gap = max(0, int(get_policy(config, "scheduler_interval_seconds", 15)))
    default_slice_seconds = max(900, int(get_policy(config, "exec_timeout_seconds", 5400)) // 2)
    result: Dict[str, Any] = {
        "remaining_slices": remaining_slices,
        "estimated_slice_seconds": None,
        "estimated_remaining_seconds": 0 if remaining_slices == 0 else None,
        "eta_at": iso(now) if remaining_slices == 0 else None,
        "eta_human": "0s" if remaining_slices == 0 else "",
        "eta_basis": "configured queue exhausted; product/design completion not implied" if remaining_slices == 0 else "",
        "eta_unavailable_reason": "",
    }

    if remaining_slices == 0:
        result["_schedule"] = None
        return result

    if status == SOURCE_BACKLOG_OPEN_STATUS:
        result["eta_human"] = "unknown"
        result["eta_basis"] = "configured queue ETA unavailable; source backlog still open after runtime queue exhaustion"
        result["eta_unavailable_reason"] = SOURCE_BACKLOG_OPEN_STATUS
        result["_schedule"] = None
        return result

    if status == "awaiting_account":
        result["eta_human"] = "unknown"
        result["eta_basis"] = "configured queue ETA unavailable; waiting for an eligible account"
        result["eta_unavailable_reason"] = "awaiting_account"
        result["_schedule"] = None
        return result

    rows = conn.execute(
        """
        SELECT status, started_at, finished_at
        FROM runs
        WHERE project_id=?
          AND job_kind='coding'
          AND finished_at IS NOT NULL
          AND status NOT IN ('starting', 'running', 'verifying', 'abandoned')
        ORDER BY id DESC
        LIMIT 12
        """,
        (project["id"],),
    ).fetchall()
    durations = [seconds for seconds in (wall_seconds(row["started_at"], row["finished_at"]) for row in rows) if seconds is not None]
    completed_runs = sum(1 for row in rows if row["status"] == "complete")
    sample_count = len(durations)
    base_slice_seconds = median_seconds(durations)
    basis_parts: List[str] = []
    if base_slice_seconds is None:
        base_slice_seconds = float(default_slice_seconds)
        basis_parts.append("fallback from exec timeout policy")
    else:
        basis_parts.append(f"median of last {sample_count} finished runs")

    if rows:
        if completed_runs > 0:
            retry_multiplier = min(max(len(rows) / completed_runs, 1.0), 3.0)
            if retry_multiplier > 1.05:
                basis_parts.append(f"{retry_multiplier:.2f}x retry factor")
        else:
            retry_multiplier = min(float(len(rows)), 3.0)
            basis_parts.append("no recent completes")
    else:
        retry_multiplier = 1.0
        basis_parts.append("no run history")

    estimated_slice_seconds = max(60, int(round(base_slice_seconds * retry_multiplier)))
    cooldown_until = parse_iso(project.get("cooldown_until"))
    initial_delay_seconds = 0
    if cooldown_until and cooldown_until > now and status not in {"starting", "running", "verifying"}:
        initial_delay_seconds = int((cooldown_until - now).total_seconds())
        basis_parts.append("includes cooldown")

    running_statuses = {"starting", "running", "verifying"}
    active_started_at = None
    if status in running_statuses and project.get("active_run_id"):
        active_row = conn.execute("SELECT started_at FROM runs WHERE id=?", (project["active_run_id"],)).fetchone()
        active_started_at = parse_iso(active_row["started_at"]) if active_row else None
    elapsed_seconds = int((now - active_started_at).total_seconds()) if active_started_at else 0
    if active_started_at:
        first_slice_seconds = max(60, estimated_slice_seconds - max(elapsed_seconds, 0))
        basis_parts.append("discounts elapsed time on active slice")
    else:
        first_slice_seconds = estimated_slice_seconds

    estimated_remaining_seconds = initial_delay_seconds + first_slice_seconds
    if remaining_slices > 1:
        estimated_remaining_seconds += (remaining_slices - 1) * (estimated_slice_seconds + scheduler_gap)

    result.update(
        {
            "estimated_slice_seconds": estimated_slice_seconds,
            "estimated_remaining_seconds": estimated_remaining_seconds,
            "eta_at": iso(now + dt.timedelta(seconds=estimated_remaining_seconds)),
            "eta_human": human_duration(estimated_remaining_seconds),
            "eta_basis": "; ".join(basis_parts),
            "_schedule": {
                "project_id": project["id"],
                "order": int(project.get("_project_order", 0)),
                "remaining_slices": remaining_slices,
                "slice_seconds": estimated_slice_seconds,
                "first_slice_seconds": first_slice_seconds,
                "initial_delay_seconds": initial_delay_seconds,
                "dispatch_gap_seconds": scheduler_gap,
                "running": bool(active_started_at),
            },
        }
    )
    return result


def estimate_fleet_eta(config: Dict[str, Any], projects: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    remaining_slices = sum(int(project.get("remaining_slices") or 0) for project in projects)
    unavailable = [
        project["id"]
        for project in projects
        if int(project.get("remaining_slices") or 0) > 0 and project.get("eta_unavailable_reason")
    ]
    result: Dict[str, Any] = {
        "remaining_slices": remaining_slices,
        "estimated_remaining_seconds": 0 if remaining_slices == 0 else None,
        "eta_at": iso(now) if remaining_slices == 0 else None,
        "eta_human": "0s" if remaining_slices == 0 else "",
        "unavailable_projects": unavailable,
        "basis": "configured queue burn-down from per-project recent run history",
        "eta_basis": "configured queue burn-down from per-project recent run history",
    }
    if remaining_slices == 0:
        result["basis"] = "configured queues exhausted; program/product completion not implied"
        result["eta_basis"] = result["basis"]
        return result
    if unavailable:
        result["eta_human"] = "unknown"
        result["basis"] = f"configured queue ETA unavailable; waiting on: {', '.join(unavailable)}"
        result["eta_basis"] = result["basis"]
        return result

    max_parallel = max(1, int(get_policy(config, "max_parallel_runs", 3)))
    states = []
    for project in projects:
        schedule = project.get("_schedule")
        if not schedule:
            continue
        states.append(dict(schedule))
    active: List[Tuple[float, int, str]] = []
    project_map = {state["project_id"]: state for state in states}

    for state in states:
        if state["running"] and state["remaining_slices"] > 0:
            finish_at = float(state["first_slice_seconds"])
            heapq.heappush(active, (finish_at, state["order"], state["project_id"]))
            state["remaining_slices"] -= 1
            state["next_ready_at"] = finish_at + state["dispatch_gap_seconds"]
            state["started_slices"] = 1
            state["active"] = True
        else:
            state["next_ready_at"] = float(state["initial_delay_seconds"])
            state["started_slices"] = 0
            state["active"] = False

    now_seconds = 0.0
    while True:
        ready = [
            state
            for state in states
            if state["remaining_slices"] > 0 and not state["active"] and state["next_ready_at"] <= now_seconds
        ]
        ready.sort(key=lambda item: item["order"])
        while ready and len(active) < max_parallel:
            state = ready.pop(0)
            duration = float(state["first_slice_seconds"] if state["started_slices"] == 0 else state["slice_seconds"])
            finish_at = now_seconds + duration
            heapq.heappush(active, (finish_at, state["order"], state["project_id"]))
            state["remaining_slices"] -= 1
            state["started_slices"] += 1
            state["next_ready_at"] = finish_at + state["dispatch_gap_seconds"]
            state["active"] = True

        if not active:
            waiting = [state["next_ready_at"] for state in states if state["remaining_slices"] > 0 and not state["active"]]
            if not waiting:
                break
            now_seconds = min(waiting)
            continue

        finish_at, _, project_id = heapq.heappop(active)
        now_seconds = finish_at
        project_map[project_id]["active"] = False

    result["estimated_remaining_seconds"] = int(round(now_seconds))
    result["eta_at"] = iso(now + dt.timedelta(seconds=int(round(now_seconds))))
    result["eta_human"] = human_duration(now_seconds)
    result["eta_basis"] = result["basis"]
    return result


@app.on_event("startup")
async def startup() -> None:
    ensure_dirs()
    init_db()
    reconcile_abandoned_runs()
    sync_design_repo_mirrors(normalize_config(), skip_dirty_repos=True)
    state.last_design_mirror_sync_at = utc_now()
    state.controller_loop = asyncio.get_running_loop()
    state.stop.clear()
    app.state.scheduler = asyncio.create_task(scheduler_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    state.stop.set()
    state.controller_loop = None
    task = getattr(app.state, "scheduler", None)
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    config = normalize_config()
    registry = load_program_registry(config)
    now = utc_now()
    usage_start = usage_window_start(config)
    group_runtime = group_runtime_rows()
    pr_rows = pull_request_rows()
    review_summary = review_findings_summary()
    open_incident_items = incident_rows(status="open", limit=400)
    latest_decisions = latest_spider_decision_by_project()
    with db() as conn:
        projects = [dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY id")]
        accounts = [dict(row) for row in conn.execute("SELECT * FROM accounts ORDER BY alias")]
        recent_runs = [dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 50")]
        recent_decisions = [
            hydrate_spider_decision(dict(row))
            for row in conn.execute("SELECT * FROM spider_decisions ORDER BY id DESC LIMIT 50")
        ]
        for idx, project in enumerate(projects):
            project["_project_order"] = idx
            project["queue"] = json.loads(project.pop("queue_json") or "[]")
            project_cfg = get_project_cfg(config, project["id"])
            pr_row = normalized_pull_request_row(project_cfg, pr_rows.get(project["id"]))
            lifecycle_state = normalize_lifecycle_state(project_cfg.get("lifecycle"), "dispatchable")
            project_groups = project_group_defs(config, project["id"])
            active_run = active_run_row(project.get("active_run_id"))
            active_run_account_alias = str(active_run.get("account_alias") or "").strip()
            active_run_backend, active_run_identity = run_backend_and_identity(
                active_run_account_alias,
                (config.get("accounts") or {}),
            )
            active_run_model = str(active_run.get("model") or "")
            active_run_brain = run_brain_label(
                active_run_account_alias,
                active_run_model,
                active_run_identity,
            )
            has_queue_sources = bool(project_cfg.get("queue_sources"))
            project["enabled"] = bool(project_cfg.get("enabled", True))
            project["lifecycle"] = project_cfg.get("lifecycle")
            runtime_status = effective_project_status(
                project_id=project["id"],
                stored_status=project.get("status"),
                queue=project["queue"],
                queue_index=int(project.get("queue_index") or 0),
                enabled=project["enabled"],
                active_run_id=project.get("active_run_id"),
                source_backlog_open=has_queue_sources and bool(project["queue"]),
            )
            if active_run:
                runtime_status = runtime_status_for_active_run(runtime_status, active_run)
            project["active_run_account_alias"] = active_run_account_alias if active_run_account_alias else None
            project["active_run_account_backend"] = active_run_backend
            project["active_run_account_identity"] = active_run_identity
            project["active_run_model"] = active_run_model if active_run else ""
            project["active_run_brain"] = active_run_brain if active_run else "not active"
            project["status_internal"] = runtime_status
            project["status"] = runtime_status
            project["dispatch_participant"] = project_dispatch_participates(project_cfg)
            project["completion_basis"] = project_completion_basis(
                runtime_status=runtime_status,
                queue=project["queue"],
                queue_index=int(project.get("queue_index") or 0),
                has_queue_sources=has_queue_sources,
            )
            project["group_ids"] = [group["id"] for group in project_groups]
            project["agent_state"] = read_state_file(project["path"], project["state_file"] or ".agent-state.json")
            current_task_item = (
                project["queue"][project["queue_index"]]
                if project["queue_index"] < len(project["queue"])
                else project.get("current_slice")
            )
            current_task_meta = normalize_task_queue_item(current_task_item, lanes=config.get("lanes"))
            project["current_queue_item"] = (
                str(current_task_meta.get("title") or "").strip() or None
            )
            project["current_task_meta"] = current_task_meta
            latest_decision = latest_decisions.get(project["id"], {})
            latest_decision_meta = dict(latest_decision.get("decision_meta") or {})
            project["latest_decision_meta"] = latest_decision_meta
            project["decision_meta_summary"] = str(latest_decision.get("decision_meta_summary") or "")
            project["selection_trace_summary"] = str(latest_decision.get("selection_trace_summary") or "")
            project["selected_lane"] = str(latest_decision_meta.get("lane") or "")
            project["selected_lane_submode"] = str(latest_decision_meta.get("lane_submode") or "")
            project["selected_profile"] = str(latest_decision_meta.get("selected_profile") or "")
            project["selected_lane_reason"] = str(latest_decision_meta.get("escalation_reason") or "")
            project["selected_lane_why_not_cheaper"] = str(latest_decision_meta.get("why_not_cheaper") or "")
            project["selected_lane_allowance"] = dict(latest_decision_meta.get("expected_allowance_burn") or {})
            project["selected_lane_capacity"] = dict(latest_decision_meta.get("lane_capacity") or {})
            project["selected_lane_capacity_state"] = str((project["selected_lane_capacity"] or {}).get("state") or "")
            project["selected_lane_capacity_remaining_percent"] = lane_snapshot_remaining_percent(project["selected_lane_capacity"])
            project["allowed_lanes"] = list(current_task_meta.get("allowed_lanes") or [])
            project["required_reviewer_lane"] = str(current_task_meta.get("required_reviewer_lane") or "")
            project["task_final_reviewer_lane"] = str(current_task_meta.get("final_reviewer_lane") or "")
            project["task_difficulty"] = str(current_task_meta.get("difficulty") or "")
            project["task_risk_level"] = str(current_task_meta.get("risk_level") or "")
            project["task_branch_policy"] = str(current_task_meta.get("branch_policy") or "")
            project["task_acceptance_level"] = str(current_task_meta.get("acceptance_level") or "")
            project["task_budget_class"] = str(current_task_meta.get("budget_class") or "")
            project["task_latency_class"] = str(current_task_meta.get("latency_class") or "")
            project["task_design_owner"] = str(current_task_meta.get("design_owner") or "")
            project["task_design_sensitive"] = bool(current_task_meta.get("design_sensitive"))
            project["task_architecture_sensitive"] = bool(current_task_meta.get("architecture_sensitive"))
            project["task_dispatchability_state"] = str(current_task_meta.get("dispatchability_state") or "")
            project["task_workflow_kind"] = str(current_task_meta.get("workflow_kind") or "default")
            project["task_max_review_rounds"] = int(current_task_meta.get("max_review_rounds") or 0)
            project["task_first_review_required"] = bool(current_task_meta.get("first_review_required"))
            project["task_jury_acceptance_required"] = bool(current_task_meta.get("jury_acceptance_required"))
            project["task_core_rescue_after_round"] = int(current_task_meta.get("core_rescue_after_round") or 0)
            project["task_groundwork_required"] = bool(current_task_meta.get("groundwork_required"))
            project["task_jury_required"] = bool(current_task_meta.get("jury_required"))
            project["task_operator_override_required"] = bool(current_task_meta.get("operator_override_required"))
            project["task_protected_runtime"] = bool(current_task_meta.get("protected_runtime"))
            project["task_signoff_requirements"] = list(current_task_meta.get("signoff_requirements") or [])
            project["task_publish_truth_sources"] = list(current_task_meta.get("publish_truth_sources") or [])
            project.update(estimate_project_eta(config, conn, project, now))
            project["queue_eta"] = queue_eta_payload(project)
            project_meta = registry["projects"].get(project["id"], {})
            project_group_meta = effective_group_meta(project_groups[0], registry, group_runtime) if project_groups else {}
            project["group_signed_off"] = group_is_signed_off(project_group_meta)
            project["group_audit_task_counts"] = audit_task_candidate_counts_for_scope("group", project["group_ids"])
            if lifecycle_state == "signoff_only":
                project["group_audit_task_counts"] = {"open": 0, "approved": 0, "published": 0}
            project["remaining_milestones"] = remaining_milestone_items(project_meta)
            project["modeled_uncovered_scope"] = text_items(project_meta.get("uncovered_scope"))
            project["modeled_uncovered_scope_count"] = len(project["modeled_uncovered_scope"])
            project["uncovered_scope"] = project_actionable_uncovered_scope(
                project["id"],
                project["modeled_uncovered_scope"],
                project["queue"],
                project["current_queue_item"],
            )
            project["uncovered_scope_count"] = len(project["uncovered_scope"])
            project["milestone_coverage_complete"] = bool(project_meta.get("milestone_coverage_complete"))
            project["design_coverage_complete"] = bool(project_meta.get("design_coverage_complete"))
            project["milestone_eta"] = estimate_project_milestone_eta(project, project_meta, now)
            design_uncovered_scope_count = max(
                int(project.get("uncovered_scope_count") or 0),
                int(project.get("modeled_uncovered_scope_count") or 0),
            )
            project["design_progress"] = design_progress_payload(
                meta=project_meta,
                runtime_status=runtime_status,
                uncovered_scope_count=design_uncovered_scope_count,
                project_ids=[str(project.get("id") or "")],
                active_workers=1 if project_has_live_worker(project) else 0,
                now=now,
            )
            project["design_eta"] = dict(project["design_progress"].get("eta") or {})
            project["audit_task_counts"] = audit_task_counts(project["id"])
            if lifecycle_state == "signoff_only":
                project["audit_task_counts"] = {"open": 0, "approved": 0, "published": 0}
            project["pull_request"] = pr_row
            project["review_rounds_used"] = int((pr_row or {}).get("review_round") or (pr_row or {}).get("local_review_attempts") or 0)
            project["first_review_complete"] = bool((pr_row or {}).get("first_review_complete_at")) or project["review_rounds_used"] > 0
            project["active_reviewer_lane"] = str(decode_review_focus(str((pr_row or {}).get("review_focus") or ""))[1].get("reviewer_lane") or "")
            accepted_on_round = str((pr_row or {}).get("accepted_on_round") or "").strip()
            if not accepted_on_round and str((pr_row or {}).get("review_status") or "").strip().lower() == REVIEW_FALLBACK_CLEAN_STATUS:
                accepted_on_round = str(project["review_rounds_used"]) if project["review_rounds_used"] > 0 else ""
            project["accepted_on_round"] = accepted_on_round or None
            project["workflow_stage"] = project_workflow_stage(current_task_meta, pr_row, runtime_status)
            project["review_eta"] = review_eta_payload(
                project["pull_request"],
                cooldown_until=project.get("cooldown_until"),
                now=now,
                review_active=bool(project.get("active_run_id")),
            )
            project["review_findings"] = review_summary.get(project["id"], {"count": 0, "blocking_count": 0})
            project["incidents"] = []
            project["open_incident_count"] = 0
            project["primary_incident"] = None
            project.update(
                project_stop_context(
                    project_cfg=project_cfg,
                    runtime_status=runtime_status,
                    queue_len=len(project["queue"]),
                    uncovered_scope_count=project["uncovered_scope_count"],
                    modeled_uncovered_scope_count=project["modeled_uncovered_scope_count"],
                    open_task_count=project["audit_task_counts"]["open"],
                    approved_task_count=project["audit_task_counts"]["approved"],
                    group_open_task_count=int((project.get("group_audit_task_counts") or {}).get("open") or 0),
                    group_approved_task_count=int((project.get("group_audit_task_counts") or {}).get("approved") or 0),
                    last_error=project.get("last_error"),
                    cooldown_until=project.get("cooldown_until"),
                    review_eta=project.get("review_eta"),
                    pull_request=project.get("pull_request"),
                    milestone_coverage_complete=project["milestone_coverage_complete"],
                    design_coverage_complete=project["design_coverage_complete"],
                    group_signed_off=project["group_signed_off"],
                )
            )
            project["status"] = public_project_status(
                runtime_status,
                lifecycle=project.get("lifecycle"),
                cooldown_until=project.get("cooldown_until"),
                needs_refill=bool(project.get("needs_refill")),
                open_task_count=int(project["audit_task_counts"]["open"]),
                approved_task_count=int(project["audit_task_counts"]["approved"]),
                group_signed_off=project["group_signed_off"],
            )
            project["runtime_status"] = project["status"]
            project["pressure_state"] = project_pressure_state(project)
            project["allowance_usage"] = recent_usage_for_scope([project["id"]], usage_start)
            project["delivery_progress"] = delivery_progress_payload_for_project(project)
            if (
                not project.get("active_run_id")
                and runtime_status == "complete"
                and not bool(project.get("needs_refill"))
                and int(project["audit_task_counts"]["open"]) <= 0
                and int(project["audit_task_counts"]["approved"]) <= 0
            ):
                project["current_slice"] = None
            project["runtime_completion_state"] = runtime_completion_state(project["status"], str(project.get("lifecycle") or ""))
            project["design_completion_state"] = design_completion_state(
                milestone_coverage_complete=bool(project.get("milestone_coverage_complete")),
                design_coverage_complete=bool(project.get("design_coverage_complete")),
                group_signed_off=bool(project.get("group_signed_off")),
            )
            project["completion_axes"] = {
                "lifecycle": normalize_lifecycle_state(project.get("lifecycle"), "dispatchable"),
                "runtime": project["runtime_completion_state"],
                "design": project["design_completion_state"],
                "closure": str(project.get("closure_state") or "open"),
            }
        open_incident_items = filter_runtime_relevant_incidents(open_incident_items, projects)
        for project in projects:
            project["incidents"] = [
                item
                for item in open_incident_items
                if str(item.get("scope_type") or "") == "project" and str(item.get("scope_id") or "") == project["id"]
            ]
            project["open_incident_count"] = len(project["incidents"])
            project["primary_incident"] = project["incidents"][0] if project["incidents"] else None
        fleet_eta = estimate_fleet_eta(config, projects, now)
        groups = []
        project_map = {project["id"]: project for project in projects}
        for group_cfg in config.get("project_groups") or []:
            group_meta = effective_group_meta(group_cfg, registry, group_runtime)
            group_projects = [project_map[project_id] for project_id in group_cfg.get("projects") or [] if project_id in project_map]
            group_row = dict(group_cfg)
            group_row["dispatch_member_count"] = len([project for project in group_projects if project_dispatch_participates(project)])
            group_row["scaffold_member_count"] = len([project for project in group_projects if normalize_lifecycle_state(project.get("lifecycle"), "dispatchable") == "scaffold"])
            group_row["signoff_only_member_count"] = len([project for project in group_projects if normalize_lifecycle_state(project.get("lifecycle"), "dispatchable") == "signoff_only"])
            group_row["captain"] = group_captain_policy(group_cfg)
            group_row["signed_off"] = group_is_signed_off(group_meta)
            group_row["signoff_state"] = str(group_meta.get("signoff_state") or ("signed_off" if group_row["signed_off"] else "open"))
            group_row["signed_off_at"] = group_meta.get("signed_off_at")
            group_row["reopened_at"] = group_meta.get("reopened_at")
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
            group_row["project_statuses"] = [{"id": project["id"], "status": project["status"]} for project in group_projects]
            group_row["review_waiting_count"] = sum(
                1
                for project in group_projects
                if str((project.get("pull_request") or {}).get("review_status") or "") in {"queued", "requested"}
            )
            group_row["review_blocking_count"] = sum(
                int((project.get("review_findings") or {}).get("blocking_count") or 0) for project in group_projects
            )
            group_row.update(group_dispatch_state(group_cfg, group_meta, group_projects, now))
            group_row["dispatch_blockers_internal"] = list(group_row.get("dispatch_blockers") or [])
            group_row["dispatch_blockers"] = operator_relevant_dispatch_blockers(group_row.get("dispatch_blockers_internal") or [])
            group_row["status"] = effective_group_status(group_cfg, group_meta, group_projects)
            group_row["phase"] = derive_group_phase(group_row, group_projects)
            group_row["milestone_eta"] = estimate_group_milestone_eta(group_cfg, group_meta, now)
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
            group_row["allowance_usage"] = recent_usage_for_scope([project["id"] for project in group_projects], usage_start)
            group_row["pool_sufficiency"] = group_pool_sufficiency(config, group_cfg, group_projects, now)
            group_row["bottleneck"] = "; ".join((group_row.get("contract_blockers") or [])[:1] + (group_row.get("dispatch_blockers") or [])[:1]) or str(group_row.get("dispatch_basis") or "")
            group_row["remaining_slices"] = int(((group_row.get("pool_sufficiency") or {}).get("remaining_slices") or 0))
            group_row["pressure_state"] = group_pressure_state(group_row, group_projects)
            group_row["delivery_progress"] = delivery_progress_payload_for_group(group_projects)
            if (
                str(group_row.get("status") or "") in {"group_blocked", "contract_blocked"}
                and active_group_workers <= 0
                and int((group_row.get("delivery_progress") or {}).get("percent_blocked") or 0) <= 0
                and int((group_row.get("delivery_progress") or {}).get("percent_inflight") or 0) > 0
            ):
                group_row["delivery_progress"]["percent_blocked"] = int(group_row["delivery_progress"].get("percent_inflight") or 0)
                group_row["delivery_progress"]["percent_inflight"] = 0
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
            groups.append(group_row)
        primary_group = groups[0] if len(groups) == 1 else None
        notifications = sorted(
            [dict(group.get("notification") or {}, group_id=group.get("id")) for group in groups if group.get("notification_needed")],
            key=lambda item: (
                0 if str(item.get("severity") or "") in {"critical", "high"} else 1,
                -int(item.get("incident_count") or 0),
                -int(item.get("ready_project_count") or 0),
                str(item.get("group_id") or ""),
            ),
        )
    for project in projects:
        project.pop("_project_order", None)
        project.pop("_schedule", None)
    for account in accounts:
        account["allowed_models"] = json.loads(account.pop("allowed_models_json") or "[]")
        account_cfg = (config.get("accounts") or {}).get(account["alias"], {})
        account_backend, account_identity = run_backend_and_identity(account["alias"], (config.get("accounts") or {}))
        account["daily_usage"] = usage_for_account(account["alias"], "day")
        account["monthly_usage"] = usage_for_account(account["alias"], "month")
        account["active_runs"] = active_run_count_for_account(account["alias"])
        account["account_backend"] = account_backend
        account["account_identity"] = account_identity
        account["configured_health_state"] = str(account_cfg.get("health_state", "ready") or "ready")
        account["pool_state"] = account_runtime_state(account, account_cfg, now)
        account["spark_enabled"] = account_supports_spark(str(account.get("auth_kind") or ""), account_cfg, account["allowed_models"])
        account["spark_pool_state"] = account_spark_runtime_state(account, account_cfg, account["allowed_models"], now)
        account["codex_home"] = str(account_home(account["alias"], account))
        account["configured_lane"] = infer_account_lane(account_cfg, alias=str(account.get("alias") or ""))
        account["lane_policy"] = dict((config.get("lanes") or {}).get(account["configured_lane"]) or {})
    for run in recent_runs:
        backend, identity = run_backend_and_identity(run.get("account_alias") or "", config.get("accounts") or {})
        run_model = str(run.get("model") or "")
        run_brain = run_brain_label(run.get("account_alias") or "", run_model, identity)
        run["account_backend"] = backend
        run["account_identity"] = identity
        run["run_model"] = run_model
        run["run_brain"] = run_brain
    return {
        "config": {
            "policies": config.get("policies", {}),
            "spider": config.get("spider", {}),
            "lanes": (config.get("lanes") or DEFAULT_LANES),
            "project_count": len(config.get("projects", [])),
            "group_count": len(config.get("project_groups", [])),
            "account_count": len(config.get("accounts", {})),
        },
        "projects": projects,
        "eta": fleet_eta,
        "queue_eta": fleet_eta,
        "groups": groups,
        "notifications": notifications,
        "incidents": open_incident_items,
        "milestone_eta": (primary_group or {}).get("milestone_eta") if primary_group else {},
        "program_eta": (primary_group or {}).get("program_eta") if primary_group else {},
        "accounts": accounts,
        "recent_runs": recent_runs,
        "recent_decisions": recent_decisions,
        "group_publish_events": group_publish_events(),
        "group_runs": group_runs(),
        "token_alliance": summarize_alliance(config),
    }


def request_project_github_review_now(project_id: str) -> Dict[str, Any]:
    config = normalize_config()
    project_cfg = get_project_cfg(config, project_id)
    review = project_review_policy(project_cfg)
    if not bool(review.get("enabled", True)) or str(review.get("mode") or "github").strip().lower() != "github":
        raise HTTPException(400, "github review is not enabled for this project")
    token = github_token()
    if not token:
        raise HTTPException(500, "github token is unavailable in fleet")
    repo_meta = project_github_repo(project_cfg, token)
    pr_row = pull_request_row(project_id)
    with db() as conn:
        project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project_row:
        raise HTTPException(404, "unknown project")
    slice_name = current_slice(project_row) or str(project_row["current_slice"] or "") or f"Review {project_id}"
    review_hold_status = review_hold_status_for_project(project_id)

    def defer_review_request(error_text: str) -> Dict[str, Any]:
        retry_at = utc_now() + dt.timedelta(seconds=max(60, int(get_policy(config, "review_poll_interval_seconds", 180) or 180)))
        update_project_status(
            project_id,
            status=review_hold_status,
            current_slice=slice_name,
            active_run_id=None,
            cooldown_until=retry_at,
            last_run_at=utc_now(),
            last_error=error_text,
            spider_tier=project_row["spider_tier"],
            spider_model=project_row["spider_model"],
            spider_reason=project_row["spider_reason"],
        )
        if table_exists("pull_requests"):
            with db() as conn:
                conn.execute(
                    """
                    UPDATE pull_requests
                    SET review_status=?,
                        next_retry_at=?,
                        updated_at=?
                    WHERE project_id=?
                    """,
                    (review_hold_status, iso(retry_at), iso(utc_now()), project_id),
                )
        return {
            "project_id": project_id,
            "review_status": review_hold_status,
            "retry_at": iso(retry_at),
            "healing": True,
        }

    if not pr_row:
        try:
            _, pr_row = ensure_review_pull_request_record(project_cfg, repo_meta, slice_name, token)
        except RuntimeError as exc:
            if is_transient_review_failure(str(exc)):
                return defer_review_request(str(exc))
            raise
    if not pr_row:
        raise HTTPException(500, "unable to create pull request record")
    try:
        request_github_review(project_cfg, pr_row, token, str(pr_row["head_sha"] or git_head_sha(str(project_cfg["path"]))))
    except RuntimeError as exc:
        if is_transient_review_failure(str(exc)):
            return defer_review_request(str(exc))
        raise
    upsert_github_review_run(
        project_id,
        slice_name=slice_name,
        pr_number=int(pr_row["pr_number"]),
        pr_url=str(pr_row["pr_url"] or ""),
        review_status="requested",
        review_focus=str(pr_row["review_focus"] or ""),
    )
    update_project_status(
        project_id,
        status="review_requested",
        current_slice=slice_name,
        active_run_id=None,
        cooldown_until=None,
        last_run_at=utc_now(),
        last_error=None,
        spider_tier=project_row["spider_tier"],
        spider_model=project_row["spider_model"],
        spider_reason=project_row["spider_reason"],
    )
    return {
        "project_id": project_id,
        "pr_number": int(pr_row["pr_number"]),
        "pr_url": str(pr_row["pr_url"] or ""),
        "review_status": "requested",
    }


def request_project_local_review_now(project_id: str) -> Dict[str, Any]:
    config = normalize_config()
    project_cfg = get_project_cfg(config, project_id)
    review = project_review_policy(project_cfg)
    if not bool(review.get("enabled", True)) or str(review.get("mode") or "github").strip().lower() != "local":
        raise HTTPException(400, "local review is not enabled for this project")
    with db() as conn:
        project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project_row:
        raise HTTPException(404, "unknown project")
    if active_local_review_run(project_id):
        pr_row = pull_request_row(project_id) or {}
        return {
            "project_id": project_id,
            "review_status": str(pr_row.get("review_status") or LOCAL_REVIEW_PENDING_STATUS),
            "local": True,
            "launched": False,
        }
    if project_id in state.tasks and not state.tasks[project_id].done():
        raise HTTPException(409, "project already has an active task")
    slice_name = current_slice(project_row) or str(project_row["current_slice"] or "") or f"Review {project_id}"
    queue_items = json.loads(project_row["queue_json"] or "[]") if "queue_json" in project_row.keys() else []
    queue_index = int(project_row["queue_index"] or 0) if "queue_index" in project_row.keys() else 0
    current_task_item = queue_items[queue_index] if queue_index < len(queue_items) else slice_name
    current_task_meta = normalize_task_queue_item(current_task_item, lanes=config.get("lanes"))
    execution_lane = "core" if bool(current_task_meta.get("needs_core_rescue")) else ""
    reviewer_lane = reviewer_lane_for_dispatch(current_task_meta, execution_lane=execution_lane)
    reviewer_model = reviewer_runtime_model_for_lane(config.get("lanes") or {}, reviewer_lane)
    review_round = max(
        1,
        int(current_task_meta.get("review_round") or 0)
        or (1 if str(current_task_meta.get("workflow_kind") or "default").strip().lower() == WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP else 0),
    )
    review_focus = encode_review_focus(
        review_focus_text(project_cfg, slice_name),
        reviewer_lane=reviewer_lane,
        reviewer_model=reviewer_model,
        metadata={**review_focus_metadata(current_task_meta, slice_name=slice_name), "review_round": str(review_round)},
    )
    pr_row = upsert_local_review_request(
        project_cfg,
        slice_name=slice_name,
        requested_at=utc_now(),
        review_focus=review_focus,
        workflow_state={
            "workflow_kind": str(current_task_meta.get("workflow_kind") or "default"),
            "review_round": review_round,
            "max_review_rounds": int(current_task_meta.get("max_review_rounds") or 0),
        },
    )
    update_project_status(
        project_id,
        status=review_hold_status_for_project(project_id, project_cfg=project_cfg, pr_row=pr_row),
        current_slice=slice_name,
        active_run_id=None,
        cooldown_until=None,
        last_run_at=utc_now(),
        last_error=None,
        spider_tier=project_row["spider_tier"],
        spider_model=project_row["spider_model"],
        spider_reason=project_row["spider_reason"],
    )
    launched = launch_local_review_fallback(config, project_id, pr_row, reason="local review requested manually")
    return {
        "project_id": project_id,
        "review_status": LOCAL_REVIEW_PENDING_STATUS if launched else str(pr_row.get("review_status") or LOCAL_REVIEW_PENDING_STATUS),
        "local": True,
        "launched": launched,
    }


@app.post("/api/projects/{project_id}/review/request")
def api_request_project_review(project_id: str) -> Dict[str, Any]:
    config = normalize_config()
    project_cfg = get_project_cfg(config, project_id)
    review_mode = str(project_review_policy(project_cfg).get("mode") or "github").strip().lower()
    if review_mode == "local":
        return request_project_local_review_now(project_id)
    return request_project_github_review_now(project_id)


@app.post("/api/projects/{project_id}/retry")
def api_retry_project(project_id: str) -> Dict[str, Any]:
    config = normalize_config()
    get_project_cfg(config, project_id)
    now = utc_now()
    with db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"unknown project: {project_id}")
    update_project_status(
        project_id,
        status=READY_STATUS,
        current_slice=row["current_slice"],
        active_run_id=None,
        cooldown_until=None,
        last_run_at=now,
        last_error=None,
        consecutive_failures=0,
        spider_tier=row["spider_tier"],
        spider_model=row["spider_model"],
        spider_reason=row["spider_reason"],
    )
    return {"ok": True, "project_id": project_id, "status": READY_STATUS, "action": "retry"}


@app.post("/api/projects/{project_id}/run-now")
def api_run_project_now(project_id: str) -> Dict[str, Any]:
    return api_retry_project(project_id)


@app.post("/api/projects/{project_id}/review/sync")
def api_sync_project_review(project_id: str) -> Dict[str, Any]:
    config = normalize_config()
    project_cfg = get_project_cfg(config, project_id)
    review_mode = str(project_review_policy(project_cfg).get("mode") or "github").strip().lower()
    if review_mode == "local":
        return request_project_local_review_now(project_id)
    try:
        return sync_github_review_state(config, project_id)
    except GitHubRateLimitError as exc:
        return defer_review_sync_due_to_rate_limit(project_id, exc)


@app.post("/api/github/webhooks")
async def api_github_webhooks(request: Request) -> Dict[str, Any]:
    body = await request.body()
    if not verify_github_webhook_signature(body, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(401, "invalid github webhook signature")
    event_name = str(request.headers.get("X-GitHub-Event", "") or "").strip().lower()
    if event_name == "ping":
        return {"ok": True, "event": "ping"}
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception as exc:
        raise HTTPException(400, f"invalid github webhook payload: {exc}") from exc

    matched_projects = webhook_project_ids(payload if isinstance(payload, dict) else {})
    if event_name not in {"pull_request", "pull_request_review", "check_run", "check_suite", "issue_comment"}:
        return {"ok": True, "event": event_name, "matched_projects": matched_projects, "synced": []}

    config = normalize_config()
    synced: List[Dict[str, Any]] = []
    for project_id in matched_projects:
        try:
            synced.append(sync_github_review_state(config, project_id))
        except GitHubRateLimitError as exc:
            synced.append(defer_review_sync_due_to_rate_limit(project_id, exc))
        except Exception as exc:
            synced.append({"project_id": project_id, "error": str(exc)})
    return {"ok": True, "event": event_name, "matched_projects": matched_projects, "synced": synced}


@app.get("/api/logs/{run_id}", response_class=PlainTextResponse)
def api_logs(run_id: int) -> str:
    with db() as conn:
        row = conn.execute("SELECT log_path FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, "run not found")
    path = pathlib.Path(row["log_path"])
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


@app.get("/api/final/{run_id}", response_class=PlainTextResponse)
def api_final(run_id: int) -> str:
    with db() as conn:
        row = conn.execute("SELECT final_message_path FROM runs WHERE id=?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(404, "run not found")
    path = pathlib.Path(row["final_message_path"])
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    status = api_status()
    alliance = status["token_alliance"]
    fleet_eta = status.get("queue_eta") or status.get("eta") or {}
    milestone_eta = status.get("milestone_eta") or {}
    program_eta = status.get("program_eta") or {}

    def td(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    def render_summary_list(items: List[Any], render_item) -> str:
        if not items:
            return '<p class="muted">None right now.</p>'
        rendered = "".join(f"<li>{render_item(item)}</li>" for item in items[:5])
        if len(items) > 5:
            rendered += f'<li class="muted">+{len(items) - 5} more</li>'
        return f"<ul>{rendered}</ul>"

    project_rows = []
    stopped_not_signed_off = [p for p in status["projects"] if p.get("stopped_not_signed_off")]
    proposed_task_projects = [
        p
        for p in status["projects"]
        if p.get("status") in {"proposed_tasks", HEALING_STATUS, QUEUE_REFILLING_STATUS, DECISION_REQUIRED_STATUS}
    ]
    account_attention = [a for a in status["accounts"] if a.get("pool_state") != "ready" or a.get("last_error")]
    group_attention = [
        g for g in status.get("groups", []) if (g.get("contract_blockers") or g.get("dispatch_blockers") or not g.get("dispatch_ready", True))
    ]
    notifications = status.get("notifications") or []
    audit_required_groups = [g for g in status.get("groups", []) if g.get("status") in {"audit_required", "audit_requested"}]
    high_pressure_groups = [g for g in status.get("groups", []) if str(g.get("pressure_state") or "") in {"critical", "high"}]
    tight_pool_groups = [
        g for g in status.get("groups", []) if str((g.get("pool_sufficiency") or {}).get("level") or "") in {"blocked", "insufficient", "tight"}
    ]
    ready_groups = [
        g
        for g in status.get("groups", [])
        if g.get("dispatch_ready") and g.get("status") not in {"audit_required", "audit_requested", "proposed_tasks", "product_signed_off"}
    ]
    review_waiting_projects = [
        p for p in status["projects"] if str((p.get("pull_request") or {}).get("review_status") or "") in {"queued", "requested"}
    ]
    review_blocking_projects = [
        p for p in status["projects"] if int((p.get("review_findings") or {}).get("blocking_count") or 0) > 0
    ]
    review_clean_projects = [
        p for p in status["projects"] if str((p.get("pull_request") or {}).get("review_status") or "") == "clean"
    ]
    for p in status["projects"]:
        heartbeat = (p.get("agent_state") or {}).get("updated_at_utc", "")
        queue_len = len(p["queue"])
        if queue_len <= 0:
            progress_label = "0 / 0"
        elif p.get("status") in {
            "complete",
            CONFIGURED_QUEUE_COMPLETE_STATUS,
            SCAFFOLD_QUEUE_COMPLETE_STATUS,
            COMPLETED_SIGNED_OFF_STATUS,
        }:
            progress_label = f"{queue_len} / {queue_len}"
        else:
            progress_label = f"{min(p['queue_index'] + 1, queue_len)} / {queue_len}"
        review_row = p.get("pull_request") or {}
        review_counts = p.get("review_findings") or {}
        review_label = review_row.get("review_status") or "not_requested"
        review_link = (
            f'<a href="{html.escape(str(review_row.get("pr_url")))}">PR #{td(review_row.get("pr_number"))}</a>'
            if review_row.get("pr_url")
            else ""
        )
        project_rows.append(
            f"""
            <tr>
              <td>{td(p['id'])}</td>
              <td><div>{td(p.get('status'))}</div><div class="muted">{td(p.get('completion_basis'))}</div><div class="muted">pressure: {td(p.get('pressure_state'))}</div><div class="muted">review: {td(review_label)} / blocking {td(review_counts.get('blocking_count'))}</div></td>
              <td><div>{td(p.get('stop_reason'))}</div><div class="muted">{td(p.get('next_action'))}</div><div class="muted">audit tasks: approved {td(p.get('approved_audit_task_count'))} / open {td(p.get('open_audit_task_count'))}</div></td>
              <td><div>{td(p.get('current_queue_item'))}</div><div class="muted">{td(p.get('backlog_source'))}</div></td>
              <td>{progress_label}</td>
              <td>{td(p.get('remaining_slices'))}</td>
              <td><div>{review_link or td(review_label)}</div><div class="muted">requested {td(review_row.get('review_requested_at') or '')}</div><div class="muted">{td((p.get('review_eta') or {}).get('summary') or '')}</div></td>
              <td><div>{td(p.get('eta_human'))}</div><div class="muted">{td(p.get('eta_basis'))}</div></td>
              <td><div>{td((p.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((p.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td>{td(p.get('uncovered_scope_count'))}</td>
              <td>
                <div>{td(p.get('spider_tier'))}</div>
                <div class="muted">configured model: {td(p.get('spider_model'))}</div>
                <div class="muted">selected lane: {td(p.get('selected_lane') or 'unknown')} / {td(p.get('selected_lane_submode') or 'n/a')}</div>
                <div class="muted">capacity: {td(p.get('selected_lane_capacity_state') or 'unknown')} / {td(p.get('selected_lane_capacity_remaining_percent') if p.get('selected_lane_capacity_remaining_percent') is not None else 'n/a')}%</div>
                <div class="muted">review: {td(p.get('required_reviewer_lane') or 'n/a')} -> {td(p.get('task_final_reviewer_lane') or p.get('required_reviewer_lane') or 'n/a')}</div>
                <div class="muted">active review: {td(p.get('active_reviewer_lane') or 'n/a')}</div>
                <div class="muted">active brain: {td(p.get('active_run_brain') or 'n/a')}</div>
                <div class="muted">backend: {td(p.get('active_run_account_backend') or 'n/a')} / {td(p.get('active_run_account_identity') or 'n/a')}</div>
                <div class="muted">run model: {td(p.get('active_run_model') or 'n/a')}</div>
              </td>
              <td><div>{td(p.get('spider_reason'))}</div><div class="muted">{td(p.get('decision_meta_summary') or '')}</div><div class="muted">{td(p.get('selection_trace_summary') or '')}</div></td>
              <td>{td(p.get('last_error'))}</td>
              <td>{td(p.get('cooldown_until'))}</td>
              <td>{td(heartbeat)}</td>
            </tr>
            """
        )

    group_rows = []
    for group in status.get("groups", []):
        members = ", ".join(str(project_id) for project_id in (group.get("projects") or []))
        contracts = ", ".join(str(name) for name in (group.get("contract_sets") or []))
        group_rows.append(
            f"""
            <tr>
              <td>{td(group.get('id'))}</td>
              <td><div>{td(group.get('status'))}</div><div class="muted">phase: {td(group.get('phase'))}</div><div class="muted">{td(group.get('mode'))}</div><div class="muted">pressure: {td(group.get('pressure_state'))}</div><div class="muted">{td(group.get('signoff_state') or ('signed_off' if group.get('signed_off') else 'open'))}</div><div class="muted">dispatch-eligible projects: {td(group.get('ready_project_count'))} / incidents: {td(group.get('open_incident_count'))} / auditor solve: {td('yes' if group.get('auditor_can_solve') else 'no')}</div></td>
              <td><div>{td('dispatchable' if group.get('dispatch_ready') else 'blocked')}</div><div class="muted">{td(group.get('dispatch_basis'))}</div></td>
              <td>{td(members)}</td>
              <td><div>{td(contracts)}</div><div class="muted">captain: p{td((group.get('captain') or {}).get('priority'))} / floor {td((group.get('captain') or {}).get('service_floor'))} / shed {td((group.get('captain') or {}).get('shed_order'))}</div><div class="muted">question: {td(group.get('operator_question'))}</div></td>
              <td>{td(len(group.get('contract_blockers') or []))}</td>
              <td>{td(len(group.get('dispatch_blockers') or []))}</td>
              <td>{td(group.get('uncovered_scope_count'))}</td>
              <td><div>{td((group.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td><div>{td((group.get('program_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('program_eta') or {}).get('eta_basis'))}</div><div class="muted">pool: {td((group.get('pool_sufficiency') or {}).get('level'))} / slots {td((group.get('pool_sufficiency') or {}).get('eligible_parallel_slots'))}</div><div class="muted">allowance: ${float((group.get('allowance_usage') or {}).get('estimated_cost_usd') or 0.0):.4f}</div></td>
            </tr>
            """
        )

    account_rows = []
    for a in status["accounts"]:
        daily = a.get("daily_usage") or {}
        monthly = a.get("monthly_usage") or {}
        account_rows.append(
            f"""
            <tr>
              <td>{td(a['alias'])}</td>
              <td>{td(a.get('account_backend'))}</td>
              <td>{td(a.get('account_identity'))}</td>
              <td>{td(a.get('auth_kind'))}</td>
              <td>{td(a.get('pool_state'))}</td>
              <td>{td('yes' if a.get('spark_enabled') else 'no')}</td>
              <td>{td(", ".join(a.get('allowed_models') or []))}</td>
              <td>{td(a.get('active_runs'))} / {td(a.get('max_parallel_runs'))}</td>
              <td>${float(daily.get('cost', 0.0)):.4f}</td>
              <td>${float(monthly.get('cost', 0.0)):.4f}</td>
              <td>{td(a.get('daily_budget_usd'))}</td>
              <td>{td(a.get('monthly_budget_usd'))}</td>
              <td>{td(a.get('backoff_until'))}</td>
              <td>{td(a.get('last_error'))}</td>
            </tr>
            """
        )

    alliance_account_rows = []
    for row in alliance.get("by_account", []):
        alliance_account_rows.append(
            f"""
            <tr>
              <td>{td(row.get('account_alias'))}</td>
              <td>{td(row.get('run_count'))}</td>
              <td>{td(row.get('input_tokens'))}</td>
              <td>{td(row.get('cached_input_tokens'))}</td>
              <td>{td(row.get('output_tokens'))}</td>
              <td>${float(row.get('estimated_cost_usd') or 0.0):.4f}</td>
            </tr>
            """
        )

    alliance_model_rows = []
    for row in alliance.get("by_model", []):
        alliance_model_rows.append(
            f"""
            <tr>
              <td>{td(row.get('model'))}</td>
              <td>{td(row.get('run_count'))}</td>
              <td>{td(row.get('input_tokens'))}</td>
              <td>{td(row.get('cached_input_tokens'))}</td>
              <td>{td(row.get('output_tokens'))}</td>
              <td>${float(row.get('estimated_cost_usd') or 0.0):.4f}</td>
            </tr>
            """
        )

    decision_rows = []
    for row in status["recent_decisions"][:20]:
        detail_bits = [bit for bit in [row.get("decision_meta_summary"), row.get("selection_trace_summary")] if bit]
        decision_rows.append(
            f"""
            <tr>
              <td>{td(row.get('id'))}</td>
              <td>{td(row.get('project_id'))}</td>
              <td>{td(row.get('slice_name'))}</td>
              <td>{td(row.get('spider_tier'))}</td>
              <td>{td(row.get('selected_model'))}</td>
              <td>{td(row.get('account_alias'))}</td>
              <td><div>{td(row.get('reason'))}</div><div class="muted">{td(' | '.join(detail_bits))}</div></td>
              <td>{td(row.get('created_at'))}</td>
            </tr>
            """
        )

    run_rows = []
    for row in status["recent_runs"][:20]:
        run_rows.append(
            f"""
            <tr>
              <td>{td(row.get('id'))}</td>
              <td>{td(row.get('project_id'))}</td>
              <td>{td(row.get('account_alias'))}</td>
              <td>{td(row.get('account_identity'))}</td>
              <td>{td(row.get('account_backend'))}</td>
              <td>{td(row.get('run_brain'))}</td>
              <td>{td(row.get('slice_name'))}</td>
              <td>{td(row.get('model'))}</td>
              <td>{td(row.get('spider_tier'))}</td>
              <td>{td(row.get('status'))}</td>
              <td>{td(row.get('input_tokens'))}</td>
              <td>{td(row.get('output_tokens'))}</td>
              <td>${float(row.get('estimated_cost_usd') or 0.0):.4f}</td>
              <td>{td(row.get('started_at'))}</td>
              <td>{td(row.get('finished_at'))}</td>
              <td><a href="/api/logs/{row['id']}">log</a></td>
              <td><a href="/api/final/{row['id']}">final</a></td>
            </tr>
            """
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
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin: 24px 0; }}
          .panel {{ border: 1px solid #ccc; padding: 16px; }}
          .panel h2 {{ margin-top: 0; }}
          ul {{ margin: 8px 0 0 18px; padding: 0; }}
        </style>
      </head>
      <body>
        <h1>{APP_TITLE}</h1>
        <p><a href="/admin">Open Admin</a> · <a href="/studio">Open Studio</a></p>
        <p>Cloudflare target from a container attached to the fleet network: <code>http://fleet-dashboard:{APP_PORT}</code></p>
        <p><strong>Configured Queue ETA:</strong> {td(fleet_eta.get('eta_human') or 'unknown')} ({td(fleet_eta.get('eta_at'))}) across {td(fleet_eta.get('remaining_slices'))} remaining slices.</p>
        <p><strong>Milestone ETA:</strong> {td(milestone_eta.get('eta_human') or 'unknown')} ({td(milestone_eta.get('eta_at'))})</p>
        <p><strong>Program ETA:</strong> {td(program_eta.get('eta_human') or 'unknown')} ({td(program_eta.get('eta_at'))})</p>
        <p class="muted">ETA basis: {td(fleet_eta.get('eta_basis') or fleet_eta.get('basis'))}.</p>
        <p class="muted">This is queue burn-down only. It uses recent coding run wall time per project, retry pressure, and the fleet parallelism cap. It is not a full product-completion forecast unless the queue fully materializes the roadmap.</p>
        <p class="muted">Token alliance window starts at {td(alliance.get('window_start'))}.</p>
        <p class="muted"><strong>Attention:</strong> {td(len(stopped_not_signed_off))} stopped without signoff, {td(len(group_attention))} groups blocked, {td(len(account_attention))} accounts need attention, {td(len(notifications))} operator notifications.</p>
        <button id="enable-notifications" type="button">Enable browser notifications</button>

        <div class="grid">
          <div class="panel">
            <h2>Notifications</h2>
            <p><strong>{td(len(notifications))}</strong></p>
            {render_summary_list(notifications, lambda n: f"{td(n.get('group_id'))}: {td(n.get('question'))}")}
          </div>
          <div class="panel">
            <h2>Needs attention</h2>
            <p><strong>{td(len(stopped_not_signed_off))}</strong></p>
            {render_summary_list(stopped_not_signed_off, lambda p: f"{td(p.get('id'))}: {td(p.get('stop_reason'))}")}
          </div>
          <div class="panel">
            <h2>Proposed tasks</h2>
            <p><strong>{td(len(proposed_task_projects))}</strong></p>
            {render_summary_list(proposed_task_projects, lambda p: f"{td(p.get('id'))}: approved {td(p.get('approved_audit_task_count'))} / open {td(p.get('open_audit_task_count'))}")}
          </div>
          <div class="panel">
            <h2>Audit-required groups</h2>
            <p><strong>{td(len(audit_required_groups))}</strong></p>
            {render_summary_list(audit_required_groups, lambda g: f"{td(g.get('id'))}: uncovered={td(g.get('uncovered_scope_count'))}")}
          </div>
          <div class="panel">
            <h2>Accounts near limit</h2>
            <p><strong>{td(len(account_attention))}</strong></p>
            {render_summary_list(account_attention, lambda a: f"{td(a.get('alias'))}: {td(a.get('pool_state'))}")}
          </div>
          <div class="panel">
            <h2>High-pressure groups</h2>
            <p><strong>{td(len(high_pressure_groups))}</strong></p>
            {render_summary_list(high_pressure_groups, lambda g: f"{td(g.get('id'))}: pressure={td(g.get('pressure_state'))}")}
          </div>
          <div class="panel">
            <h2>Tight pool groups</h2>
            <p><strong>{td(len(tight_pool_groups))}</strong></p>
            {render_summary_list(tight_pool_groups, lambda g: f"{td(g.get('id'))}: pool={td((g.get('pool_sufficiency') or {}).get('level'))}")}
          </div>
          <div class="panel">
            <h2>Group blockers</h2>
            <p><strong>{td(len(group_attention))}</strong></p>
            {render_summary_list(group_attention, lambda g: f"{td(g.get('id'))}: {td(g.get('dispatch_basis'))}")}
          </div>
          <div class="panel">
            <h2>Ready to run now</h2>
            <p><strong>{td(len(ready_groups))}</strong></p>
            {render_summary_list(ready_groups, lambda g: f"{td(g.get('id'))}: {td(g.get('status'))}")}
          </div>
          <div class="panel">
            <h2>PRs waiting for review</h2>
            <p><strong>{td(len(review_waiting_projects))}</strong></p>
            {render_summary_list(review_waiting_projects, lambda p: f"{td(p.get('id'))}: {td((p.get('pull_request') or {}).get('review_status'))}")}
          </div>
          <div class="panel">
            <h2>Blocking review findings</h2>
            <p><strong>{td(len(review_blocking_projects))}</strong></p>
            {render_summary_list(review_blocking_projects, lambda p: f"{td(p.get('id'))}: blocking {td((p.get('review_findings') or {}).get('blocking_count'))}")}
          </div>
          <div class="panel">
            <h2>Clean review PRs</h2>
            <p><strong>{td(len(review_clean_projects))}</strong></p>
            {render_summary_list(review_clean_projects, lambda p: f"{td(p.get('id'))}: {td((p.get('pull_request') or {}).get('pr_url'))}")}
          </div>
        </div>

        <h2>Projects</h2>
        <table>
          <thead>
            <tr>
              <th>Project</th><th>Queue Status</th><th>Why Stopped</th><th>Current Slice / Backlog Source</th><th>Progress</th><th>Remaining</th><th>Review</th><th>Queue ETA</th><th>Milestone ETA</th><th>Uncovered Scope</th><th>Route / Model</th><th>Routing Reason</th><th>Last Error</th><th>Cooldown</th><th>Repo Heartbeat</th>
            </tr>
          </thead>
          <tbody>
            {''.join(project_rows) or '<tr><td colspan="15">No projects configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Groups</h2>
        <table>
          <thead>
            <tr>
              <th>Group</th><th>Status</th><th>Dispatch</th><th>Projects</th><th>Contract Sets</th><th>Contract Blockers</th><th>Dispatch Blockers</th><th>Uncovered Scope</th><th>Milestone ETA</th><th>Program ETA</th>
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
              <th>Alias</th><th>Backend</th><th>Identity</th><th>Auth</th><th>Pool state</th><th>Spark</th><th>Allowed models</th><th>Active</th><th>Day cost</th><th>Month cost</th><th>Day budget</th><th>Month budget</th><th>Backoff</th><th>Last error</th>
            </tr>
          </thead>
          <tbody>
            {''.join(account_rows) or '<tr><td colspan="14">No accounts configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Token alliance by account</h2>
        <table>
          <thead>
            <tr>
              <th>Account</th><th>Runs</th><th>Input tokens</th><th>Cached input</th><th>Output tokens</th><th>Estimated cost</th>
            </tr>
          </thead>
          <tbody>
            {''.join(alliance_account_rows) or '<tr><td colspan="6">No usage yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Token alliance by model</h2>
        <table>
          <thead>
            <tr>
              <th>Model</th><th>Runs</th><th>Input tokens</th><th>Cached input</th><th>Output tokens</th><th>Estimated cost</th>
            </tr>
          </thead>
          <tbody>
            {''.join(alliance_model_rows) or '<tr><td colspan="6">No usage yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Recent spider decisions</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th><th>Project</th><th>Slice</th><th>Route class</th><th>Model</th><th>Account</th><th>Reason</th><th>At</th>
            </tr>
          </thead>
          <tbody>
            {''.join(decision_rows) or '<tr><td colspan="8">No decisions yet.</td></tr>'}
          </tbody>
        </table>

        <h2>Recent runs</h2>
        <table>
            <thead>
              <tr>
                <th>ID</th><th>Project</th><th>Account</th><th>Auth</th><th>Backend</th><th>Brain</th><th>Slice</th><th>Model</th><th>Route class</th><th>Status</th><th>Input</th><th>Output</th><th>Cost</th><th>Started</th><th>Finished</th><th>Log</th><th>Final</th>
              </tr>
            </thead>
          <tbody>
            {''.join(run_rows) or '<tr><td colspan="16">No runs yet.</td></tr>'}
          </tbody>
        </table>

        <script>
          const fleetNotifications = {json.dumps(notifications)};
          const enableButton = document.getElementById('enable-notifications');
          if (enableButton) {{
            enableButton.addEventListener('click', async () => {{
              if (!('Notification' in window)) {{
                alert('Browser notifications are not supported here.');
                return;
              }}
              const permission = await Notification.requestPermission();
              if (permission === 'granted') {{
                enableButton.textContent = 'Browser notifications enabled';
              }}
            }});
            if (!('Notification' in window)) {{
              enableButton.textContent = 'Browser notifications unavailable';
            }} else if (Notification.permission === 'granted') {{
              enableButton.textContent = 'Browser notifications enabled';
            }}
          }}
          if ('Notification' in window && Notification.permission === 'granted') {{
            const seenKey = 'fleet-dashboard-notifications-v1';
            let seen = {{}};
            try {{
              seen = JSON.parse(localStorage.getItem(seenKey) || '{{}}');
            }} catch (err) {{
              seen = {{}};
            }}
            for (const item of fleetNotifications) {{
              if (!item || !item.notification_key || seen[item.notification_key]) {{
                continue;
              }}
              new Notification(item.title || 'Fleet notification', {{
                body: item.question || item.reason || '',
                tag: item.notification_key,
              }});
              seen[item.notification_key] = new Date().toISOString();
            }}
            localStorage.setItem(seenKey, JSON.stringify(seen));
          }}
        </script>
      </body>
    </html>
    """
