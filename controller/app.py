import asyncio
import contextlib
import datetime as dt
import hashlib
import heapq
import html
import json
import os
import pathlib
import re
import shlex
import sqlite3
import textwrap
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

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

DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", "/var/lib/codex-fleet/fleet.db"))
LOG_DIR = pathlib.Path(os.environ.get("FLEET_LOG_DIR", "/var/lib/codex-fleet/logs"))
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
ACCOUNTS_PATH = pathlib.Path(os.environ.get("FLEET_ACCOUNTS_PATH", "/app/config/accounts.yaml"))
CODEX_HOME_ROOT = pathlib.Path(os.environ.get("FLEET_CODEX_HOME_ROOT", "/var/lib/codex-fleet/codex-homes"))

DEFAULT_PRICE_TABLE = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5.3-codex": {"input": 1.75, "cached_input": 0.175, "output": 14.00},
    "gpt-5.3-codex-spark": {"input": 0.0, "cached_input": 0.0, "output": 0.0},
}

SPARK_MODEL = "gpt-5.3-codex-spark"
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}

DEFAULT_SPIDER = {
    "escalate_to_complex_after_failures": 2,
    "classification_mode": "heuristic_v2",
    "feedback_file_window": 2,
    "tier_preferences": {
        "inspect": {
            "models": ["gpt-5-nano", "gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "none",
            "estimated_output_tokens": 384,
        },
        "draft": {
            "models": ["gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "low",
            "estimated_output_tokens": 768,
        },
        "micro_edit": {
            "models": [SPARK_MODEL, "gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "none",
            "estimated_output_tokens": 768,
        },
        "bounded_fix": {
            "models": [SPARK_MODEL, "gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "low",
            "estimated_output_tokens": 1536,
        },
        "multi_file_impl": {
            "models": ["gpt-5.4", "gpt-5.3-codex"],
            "reasoning_effort": "low",
            "estimated_output_tokens": 2048,
        },
        "cross_repo_contract": {
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
CONFIGURED_QUEUE_COMPLETE_STATUS = "configured_queue_complete"

SYSTEM_PROMPT_TEMPLATE = """
System re-entry.

Read from disk before coding:
{instructions}

Then inspect the current repository state before changing anything.
Do not repeat already completed work.
Use scripts/ai/set-status.sh as you work when available.
Use scripts/ai/verify.sh before declaring completion when available.
Continue silently through the queue until fully complete or truly blocked on missing information or missing permissions.

Current slice:
{slice_name}

Spider routing notes:
- selected route class: {tier}
- selected model: {model}
- reasoning effort: {reasoning_effort}
- why: {reason}

{feedback_block}
""".strip()


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


def ensure_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CODEX_HOME_ROOT.mkdir(parents=True, exist_ok=True)


def db() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
                backoff_until TEXT,
                last_used_at TEXT,
                last_error TEXT,
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
                status TEXT NOT NULL DEFAULT 'idle',
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
                status TEXT NOT NULL DEFAULT 'open',
                source TEXT NOT NULL DEFAULT 'fleet-auditor',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                resolved_at TEXT,
                UNIQUE(scope_type, scope_id, finding_key, task_index)
            );
            """
        )
        migrate_db(conn)


def migrate_db(conn: sqlite3.Connection) -> None:
    account_cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "api_key_env" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN api_key_env TEXT")

    run_cols = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "job_kind" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN job_kind TEXT NOT NULL DEFAULT 'coding'")


def reconcile_abandoned_runs() -> None:
    with db() as conn:
        now = iso(utc_now())
        conn.execute(
            "UPDATE runs SET status='abandoned', finished_at=COALESCE(finished_at, ?) WHERE status IN ('starting', 'running', 'verifying')",
            (now,),
        )
        conn.execute(
            "UPDATE projects SET status='idle', active_run_id=NULL, updated_at=? WHERE status IN ('starting', 'running', 'verifying')",
            (now,),
        )


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def normalize_config() -> Dict[str, Any]:
    fleet = load_yaml(CONFIG_PATH)
    accounts_cfg = load_yaml(ACCOUNTS_PATH)
    fleet.setdefault("policies", {})
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet["spider"] = deep_merge(DEFAULT_SPIDER, fleet.get("spider") or {})
    price_table = deep_merge(DEFAULT_PRICE_TABLE, (fleet["spider"].get("price_table") or {}))
    fleet["spider"]["price_table"] = price_table
    fleet["accounts"] = accounts_cfg.get("accounts", {}) or {}

    for group in fleet["project_groups"]:
        group.setdefault("projects", [])
        group.setdefault("mode", "independent")
        group.setdefault("contract_sets", [])
        group.setdefault("milestone_source", {})
        group.setdefault("group_roles", [])

    for project in fleet["projects"]:
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("verify_cmd", "")
        project.setdefault("design_doc", "")
        project.setdefault("enabled", True)
        project.setdefault("accounts", [])
        project.setdefault("queue_sources", [])
        project["queue"] = resolve_project_queue(project)
        project["runner"] = project.get("runner") or {}
        project["spider"] = deep_merge(fleet["spider"], project.get("spider") or {})
    return fleet


def get_policy(config: Dict[str, Any], key: str, default: Any) -> Any:
    return (config.get("policies") or {}).get(key, default)


def sync_config_to_db(config: Dict[str, Any]) -> None:
    now = iso(utc_now())
    with db() as conn:
        for alias, account in (config.get("accounts") or {}).items():
            auth_kind = account.get("auth_kind", "api_key")
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, api_key_file, api_key_env, auth_json_file, allowed_models_json, daily_budget_usd, monthly_budget_usd, max_parallel_runs, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(alias) DO UPDATE SET
                    auth_kind=excluded.auth_kind,
                    api_key_file=excluded.api_key_file,
                    api_key_env=excluded.api_key_env,
                    auth_json_file=excluded.auth_json_file,
                    allowed_models_json=excluded.allowed_models_json,
                    daily_budget_usd=excluded.daily_budget_usd,
                    monthly_budget_usd=excluded.monthly_budget_usd,
                    max_parallel_runs=excluded.max_parallel_runs,
                    updated_at=excluded.updated_at
                """,
                (
                    alias,
                    auth_kind,
                    account.get("api_key_file", ""),
                    account.get("api_key_env", ""),
                    account.get("auth_json_file", ""),
                    json.dumps(account.get("allowed_models", [])),
                    account.get("daily_budget_usd"),
                    account.get("monthly_budget_usd"),
                    int(account.get("max_parallel_runs", 1)),
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
                    stored_status=row["status"],
                    queue=new_queue,
                    queue_index=queue_index,
                    enabled=bool(project.get("enabled", True)),
                    active_run_id=row["active_run_id"],
                    source_backlog_open=bool(project.get("queue_sources")) and bool(new_queue),
                )
                next_slice = new_queue[queue_index] if queue_index < len(new_queue) else None
                if next_status != row["status"] or next_slice != row["current_slice"]:
                    conn.execute(
                        """
                        UPDATE projects
                        SET status=?,
                            current_slice=?,
                            active_run_id=CASE WHEN ? IN ('idle', 'complete', 'paused', 'source_backlog_open') THEN NULL ELSE active_run_id END,
                            updated_at=?
                        WHERE id=?
                        """,
                        (next_status, next_slice, next_status, now, project["id"]),
                    )


def current_slice(project_row: sqlite3.Row) -> Optional[str]:
    queue = json.loads(project_row["queue_json"] or "[]")
    idx = project_row["queue_index"]
    if 0 <= idx < len(queue):
        return queue[idx]
    return None


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
    stored_status: Optional[str],
    queue: List[str],
    queue_index: int,
    enabled: bool,
    active_run_id: Optional[int],
    source_backlog_open: bool,
) -> str:
    status = str(stored_status or "").strip() or "idle"
    if not enabled:
        return "paused"
    if int(queue_index) >= len(queue):
        if status in {"starting", "running", "verifying"} and active_run_id:
            return status
        if source_backlog_open:
            return SOURCE_BACKLOG_OPEN_STATUS
        return "complete"
    if status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS}:
        return "idle"
    return status


def public_project_status(runtime_status: Optional[str]) -> str:
    status = str(runtime_status or "").strip() or "idle"
    if status == "complete":
        return CONFIGURED_QUEUE_COMPLETE_STATUS
    return status


def project_completion_basis(
    *,
    runtime_status: Optional[str],
    queue: List[str],
    queue_index: int,
    has_queue_sources: bool,
) -> str:
    status = str(runtime_status or "").strip() or "idle"
    queue_len = len(queue)
    current = min(max(int(queue_index), 0) + 1, queue_len) if queue_len else 0

    if status == "complete":
        if has_queue_sources and queue_len == 0:
            return "configured repo-native queue currently resolves to zero active items; roadmap/design coverage not audited"
        if has_queue_sources:
            return "configured repo-native queue exhausted; roadmap/design coverage not audited"
        if queue_len == 0:
            return "configured queue is empty; roadmap/design coverage not audited"
        return "configured static queue exhausted; roadmap/design coverage not audited"
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


def prepare_dispatch_candidate(config: Dict[str, Any], project_cfg: Dict[str, Any], row: sqlite3.Row, now: dt.datetime) -> "DispatchCandidate":
    project_id = row["id"]
    queue = json.loads(row["queue_json"] or "[]")
    queue_index = int(row["queue_index"] or 0)
    enabled = bool(project_cfg.get("enabled", True))
    has_queue_sources = bool(project_cfg.get("queue_sources"))

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
            slice_name=current_slice(row),
            runtime_status="paused",
            cooldown_until=None,
            dispatchable=False,
        )

    if queue_index >= len(queue):
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
            slice_name=None,
            runtime_status=exhausted_status,
            cooldown_until=None,
            dispatchable=False,
        )

    runtime_status = str(row["status"] or "").strip() or "idle"
    if runtime_status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS}:
        runtime_status = "idle"
        update_project_status(
            project_id,
            status=runtime_status,
            current_slice=queue[queue_index],
            active_run_id=None,
            cooldown_until=parse_iso(row["cooldown_until"]),
            last_run_at=parse_iso(row["last_run_at"]),
            last_error=row["last_error"],
            consecutive_failures=row["consecutive_failures"],
            spider_tier=row["spider_tier"],
            spider_model=row["spider_model"],
            spider_reason=row["spider_reason"],
        )

    cooldown_until = parse_iso(row["cooldown_until"])
    dispatchable = cooldown_until is None or cooldown_until <= now
    return DispatchCandidate(
        row=row,
        project_cfg=project_cfg,
        queue=queue,
        queue_index=queue_index,
        slice_name=queue[queue_index],
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
        text = str(value).strip()
        if text:
            items.append(text)
    return items


def project_group_defs(config: Dict[str, Any], project_id: str) -> List[Dict[str, Any]]:
    return [group for group in config.get("project_groups") or [] if project_id in (group.get("projects") or [])]


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
    ).strip() or "idle"


def project_queue_length(project: Dict[str, Any]) -> int:
    queue = project.get("queue")
    if isinstance(queue, list):
        return len(queue)
    return int(project.get("queue_len") or 0)


def group_dispatch_state(group: Dict[str, Any], meta: Dict[str, Any], group_projects: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    blockers: List[str] = []
    blockers.extend(f"contract blocker: {item}" for item in text_items(meta.get("contract_blockers")))

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
            elif status in {"starting", "running", "verifying"}:
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
    dispatch = group_dispatch_state(group, meta, group_projects, utc_now())
    if text_items(meta.get("contract_blockers")):
        return "contract_blocked"
    if text_items(meta.get("uncovered_scope")) or not bool(meta.get("milestone_coverage_complete")):
        return "audit_required"
    if remaining_milestone_items(meta):
        if str(group.get("mode", "") or "").strip().lower() == "lockstep" and not dispatch.get("dispatch_ready"):
            active_statuses = {"running", "starting", "verifying"}
            if any(project_runtime_status(project) in active_statuses for project in group_projects):
                return "lockstep_active"
            return "group_blocked"
        return "milestone_backlog_open"
    active_statuses = {"running", "starting", "verifying", "idle", "awaiting_account", "blocked"}
    if any(project_runtime_status(project) in active_statuses for project in group_projects):
        return "lockstep_active"
    return "program_complete"


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


@dataclass
class DispatchCandidate:
    row: sqlite3.Row
    project_cfg: Dict[str, Any]
    queue: List[str]
    queue_index: int
    slice_name: Optional[str]
    runtime_status: str
    cooldown_until: Optional[dt.datetime]
    dispatchable: bool


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


def load_worklist_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = resolve_project_file(project_cfg, str(source_cfg.get("path", "WORKLIST.md")))
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
        if len(cells) < 6:
            continue
        task_id = cells[0].strip("` ").lower()
        status = cells[1].strip("` ").strip().lower().replace("_", " ")
        task = cells[3].strip("` ").strip()
        if task_id in {"id", "---"} or not task_id.startswith("wl-"):
            continue
        if task.startswith("<"):
            continue
        if status in ACTIVE_QUEUE_STATUSES and task and task not in seen:
            items.append(task)
            seen.add(task)
    return items


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
    if feedback_files:
        rendered = []
        for path in feedback_files:
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as exc:
                content = f"<unable to read: {exc}>"
            rendered.append(f"## {path.name}\n{content}")
        feedback_block = "Unread feedback files to incorporate in order:\n\n" + "\n\n".join(rendered)

    return SYSTEM_PROMPT_TEMPLATE.format(
        instructions="\n".join(instructions),
        slice_name=slice_name,
        tier=decision["tier"],
        model=decision["selected_model"],
        reasoning_effort=decision["reasoning_effort"],
        reason=decision["reason"],
        feedback_block=feedback_block,
    ) + "\n"


def estimate_prompt_chars(project_cfg: Dict[str, Any], slice_name: str, feedback_files: List[pathlib.Path]) -> int:
    total = len(SYSTEM_PROMPT_TEMPLATE) + len(slice_name) + len(project_cfg.get("id", "")) + len(project_cfg.get("path", ""))
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


def classify_tier(config: Dict[str, Any], project_cfg: Dict[str, Any], project_row: sqlite3.Row, slice_name: str, feedback_files: List[pathlib.Path]) -> Dict[str, Any]:
    spider = project_cfg.get("spider") or config.get("spider") or DEFAULT_SPIDER
    slice_text = str(slice_name or "").lower()
    prompt_chars = estimate_prompt_chars(project_cfg, slice_name, feedback_files)
    failures = int(project_row["consecutive_failures"] or 0)
    reason_parts: List[str] = []
    tier = "bounded_fix"

    inspect_hit = contains_any(slice_text, spider.get("inspect_keywords", []))
    draft_hit = contains_any(slice_text, spider.get("draft_keywords", []))
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

    tier_prefs = spider.get("tier_preferences", {}).get(tier, {})
    models = list(tier_prefs.get("models") or [])
    reasoning_effort = str(tier_prefs.get("reasoning_effort", "low"))
    est_prompt_tokens = max(256, int(prompt_chars / 4))
    est_output_tokens = int(tier_prefs.get("estimated_output_tokens", 1024))
    predicted_files = predict_changed_files(tier)
    requires_contract_authority = tier == "cross_repo_contract"
    spark_eligible = (
        tier in {"micro_edit", "bounded_fix"}
        and predicted_files <= 3
        and failures == 0
        and len(feedback_files) <= 1
        and prompt_chars <= 12000
        and not requires_contract_authority
    )
    if not spark_eligible:
        models = [model for model in models if model != SPARK_MODEL]
    reason_parts.append(f"predicted changed files: {predicted_files}")
    reason_parts.append("spark eligible" if spark_eligible else "spark not eligible")

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
        "spark_eligible": spark_eligible,
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
            "SELECT COUNT(*) FROM runs WHERE account_alias=? AND status IN ('starting', 'running', 'verifying')",
            (alias,),
        ).fetchone()
    return int(row[0] if row else 0)


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
    with db() as conn:
        row = conn.execute("SELECT consecutive_failures FROM projects WHERE id=?", (project_id,)).fetchone()
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


def increment_queue(project_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE projects SET queue_index = queue_index + 1, consecutive_failures = 0, updated_at=? WHERE id=?",
            (iso(utc_now()), project_id),
        )


def set_account_backoff(alias: str, backoff_until: Optional[dt.datetime], last_error: Optional[str] = None, touch_last_used: bool = False) -> None:
    with db() as conn:
        row = conn.execute("SELECT last_used_at FROM accounts WHERE alias=?", (alias,)).fetchone()
        last_used = iso(utc_now()) if touch_last_used else (row["last_used_at"] if row else None)
        conn.execute(
            "UPDATE accounts SET backoff_until=?, last_error=?, last_used_at=?, updated_at=? WHERE alias=?",
            (iso(backoff_until), last_error, last_used, iso(utc_now()), alias),
        )


def touch_account(alias: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE accounts SET last_used_at=?, updated_at=? WHERE alias=?",
            (iso(utc_now()), iso(utc_now()), alias),
        )


def account_runtime_state(row: sqlite3.Row, account_cfg: Dict[str, Any], now: dt.datetime) -> str:
    configured = str(account_cfg.get("health_state", "ready") or "ready").strip().lower()
    if configured in {"disabled", "draining", "exhausted", "auth_stale"}:
        return configured
    backoff_until = parse_iso(row["backoff_until"])
    if backoff_until and backoff_until > now:
        return "cooldown"
    return "ready"


def account_supports_spark(auth_kind: str, account_cfg: Dict[str, Any], allowed_models: List[str]) -> bool:
    if auth_kind not in CHATGPT_AUTH_KINDS:
        return False
    if not bool(account_cfg.get("spark_enabled", SPARK_MODEL in allowed_models)):
        return False
    return (not allowed_models) or (SPARK_MODEL in allowed_models)


def pick_account_and_model(config: Dict[str, Any], project_cfg: Dict[str, Any], decision: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    aliases = project_cfg.get("accounts") or []
    if not aliases:
        return None, None, "project has no configured accounts"
    price_table = config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE
    now = utc_now()
    wanted_models = list(decision["model_preferences"])
    if not wanted_models:
        return None, None, "route class produced no eligible models after filtering"
    candidates: List[Tuple[int, int, dt.datetime, int, str, str, str]] = []
    config_accounts = config.get("accounts") or {}
    rejections: List[str] = []

    with db() as conn:
        for alias_order, alias in enumerate(aliases):
            row = conn.execute("SELECT * FROM accounts WHERE alias=?", (alias,)).fetchone()
            if not row:
                rejections.append(f"{alias}: missing account record")
                continue
            account_cfg = config_accounts.get(alias) or {}

            project_allowlist = [str(item).strip() for item in account_cfg.get("project_allowlist") or [] if str(item).strip()]
            if project_allowlist and project_cfg.get("id") not in project_allowlist:
                rejections.append(f"{alias}: project not in allowlist")
                continue

            pool_state = account_runtime_state(row, account_cfg, now)
            if pool_state != "ready":
                rejections.append(f"{alias}: state={pool_state}")
                continue

            active = active_run_count_for_account(alias)
            if active >= int(row["max_parallel_runs"] or 1):
                rejections.append(f"{alias}: parallel cap reached")
                continue

            auth_kind = row["auth_kind"]
            if auth_kind == "api_key":
                if not has_api_key(row):
                    rejections.append(f"{alias}: api key unavailable")
                    continue
            else:
                auth_json_file = pathlib.Path(row["auth_json_file"] or "")
                if not auth_json_file.exists():
                    rejections.append(f"{alias}: auth json missing")
                    continue

            allowed = json.loads(row["allowed_models_json"] or "[]")
            available_models: List[Tuple[int, str]] = []
            for model_index, model in enumerate(wanted_models):
                if allowed and model not in allowed:
                    continue
                if model == SPARK_MODEL and not account_supports_spark(auth_kind, account_cfg, allowed):
                    continue
                available_models.append((model_index, model))
            if not available_models:
                rejections.append(f"{alias}: no allowed model for route class {decision['tier']}")
                continue

            day_usage = usage_for_account(alias, "day")
            month_usage = usage_for_account(alias, "month")
            last_used = parse_iso(row["last_used_at"]) or dt.datetime.fromtimestamp(0, tz=UTC)
            for model_index, chosen_model in available_models:
                est_cost = estimate_cost_usd_for_model(
                    price_table,
                    chosen_model,
                    int(decision["estimated_input_tokens"]),
                    0,
                    int(decision["estimated_output_tokens"]),
                ) or 0.0

                if row["daily_budget_usd"] is not None and (float(day_usage["cost"]) + est_cost) > float(row["daily_budget_usd"]):
                    continue

                if row["monthly_budget_usd"] is not None and (float(month_usage["cost"]) + est_cost) > float(row["monthly_budget_usd"]):
                    continue

                candidates.append(
                    (
                        model_index,
                        active,
                        last_used,
                        alias_order,
                        alias,
                        chosen_model,
                        f"route={decision['tier']}; state={pool_state}; auth={auth_kind}; estimated cost ${est_cost:.4f}",
                    )
                )

    if not candidates:
        detail = "; ".join(rejections[:4]) if rejections else "all candidates filtered"
        return None, None, f"no eligible account/model after auth, pool state, allowlist, or budget filtering ({detail})"
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    _, _, _, _, alias, model, why = candidates[0]
    return alias, model, why


def write_toml_string(value: str) -> str:
    return json.dumps(value)


def account_home(alias: str) -> pathlib.Path:
    path = CODEX_HOME_ROOT / alias
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    home = account_home(alias)
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

    if input_text is not None and proc.stdin is not None:
        proc.stdin.write(input_text.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()

    async def _pump_stdout() -> None:
        assert proc.stdout is not None
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab") as f:
                async for chunk in proc.stdout:
                    f.write(chunk)
                    f.flush()
        else:
            async for _ in proc.stdout:
                pass

    pump_task = asyncio.create_task(_pump_stdout())
    try:
        if timeout_seconds and timeout_seconds > 0:
            await asyncio.wait_for(proc.wait(), timeout=timeout_seconds)
        else:
            await proc.wait()
    except asyncio.TimeoutError:
        timed_out = True
        if log_path:
            with log_path.open("ab") as f:
                f.write((f'\n{{"type":"controller.timeout","timeout_seconds":{int(timeout_seconds)}}}\n').encode("utf-8"))
                f.flush()
        await _terminate_process(proc)
    finally:
        await pump_task

    exit_code = proc.returncode if proc.returncode is not None else 124
    if timed_out and exit_code == 0:
        exit_code = 124
    return CommandResult(exit_code=int(exit_code), timed_out=timed_out, timeout_seconds=timeout_seconds)


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


@dataclass
class RuntimeState:
    tasks: Dict[str, asyncio.Task]
    stop: asyncio.Event


state = RuntimeState(tasks={}, stop=asyncio.Event())
app = FastAPI(title=APP_TITLE)


async def execute_project_slice(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    project_row: sqlite3.Row,
    slice_name: str,
    decision: Dict[str, Any],
    account_alias: str,
    selected_model: str,
    selection_note: str,
) -> None:
    project_id = project_cfg["id"]
    account_cfg = (config.get("accounts") or {}).get(account_alias, {})
    feedback_files = selected_feedback_files(config, project_cfg)
    decision_reason = f"{decision['reason']}; {selection_note}"
    prompt = build_prompt(
        project_cfg,
        slice_name,
        {
            "tier": decision["tier"],
            "selected_model": selected_model,
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

    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
            VALUES (?, ?, 'coding', ?, 'starting', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                account_alias,
                slice_name,
                selected_model,
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
            INSERT INTO spider_decisions(project_id, slice_name, account_alias, selected_model, spider_tier, reason, estimated_prompt_chars, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                slice_name,
                account_alias,
                selected_model,
                decision["tier"],
                decision_reason,
                int(decision["estimated_prompt_chars"]),
                iso(started_at),
            ),
        )

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

        runner = project_cfg.get("runner") or {}
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
            selected_model,
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
        rc_result = await run_command(
            cmd,
            cwd=project_cfg["path"],
            env=env,
            input_text=prompt,
            log_path=log_path,
            timeout_seconds=exec_timeout_seconds,
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
                verify_result = await run_command(
                    ["bash", "-lc", verify_cmd],
                    cwd=project_cfg["path"],
                    env=env,
                    log_path=log_path,
                    timeout_seconds=verify_timeout_seconds,
                )
                verify_rc = verify_result.exit_code

            if verify_rc in (None, 0):
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
                next_status = (
                    SOURCE_BACKLOG_OPEN_STATUS
                    if idx >= len(queue) and bool(project_cfg.get("queue_sources")) and bool(queue)
                    else ("complete" if idx >= len(queue) else "idle")
                )
                next_slice = queue[idx] if idx < len(queue) else None
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
                verify_timed_out = 'verify_result' in locals() and bool(verify_result.timed_out)
                msg = f"verify timed out after {verify_result.timeout_seconds}s" if verify_timed_out else f"verify failed with exit {verify_rc}"
                error_class = 'verify_timeout' if verify_timed_out else 'verify'
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
                status = "blocked" if failures >= max_failures else "idle"
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
                msg = f"codex exec timed out after {rc_result.timeout_seconds}s"
                with db() as conn:
                    conn.execute(
                        """
                        UPDATE runs
                        SET status='failed', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class='timeout', error_message=?
                        WHERE id=?
                        """,
                        (rc, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, msg, run_id),
                    )
                max_failures = int(get_policy(config, "max_consecutive_failures", 3))
                status = "blocked" if failures >= max_failures else "idle"
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
                        status="idle",
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
                    status = "blocked" if failures >= max_failures else "idle"
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
        status = "blocked" if failures >= max_failures else "idle"
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
        state.tasks.pop(project_id, None)


async def scheduler_loop() -> None:
    while not state.stop.is_set():
        config = normalize_config()
        try:
            sync_config_to_db(config)
            max_parallel = int(get_policy(config, "max_parallel_runs", 3))
            with db() as conn:
                projects = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
            running_count = len(state.tasks)
            now = utc_now()
            registry = load_program_registry(config)
            candidates: Dict[str, DispatchCandidate] = {}
            for row in projects:
                project_id = row["id"]
                if project_id in state.tasks:
                    continue
                project_cfg = get_project_cfg(config, project_id)
                candidates[project_id] = prepare_dispatch_candidate(config, project_cfg, row, now)

            handled_projects: set[str] = set()
            for group in config.get("project_groups") or []:
                if str(group.get("mode", "") or "").strip().lower() != "lockstep":
                    continue
                member_ids = [project_id for project_id in (group.get("projects") or []) if project_id in candidates]
                if not member_ids:
                    continue
                handled_projects.update(member_ids)
                if any(project_id in state.tasks for project_id in member_ids):
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
                dispatch = group_dispatch_state(group, registry["groups"].get(group["id"], {}), group_projects, now)
                if not dispatch["dispatch_ready"]:
                    continue
                if running_count + len(member_ids) > max_parallel:
                    continue

                launch_plan: List[Tuple[str, DispatchCandidate, Dict[str, Any], str, str, str]] = []
                group_blocked = False
                for project_id in member_ids:
                    candidate = candidates[project_id]
                    if not candidate.dispatchable or not candidate.slice_name:
                        group_blocked = True
                        break
                    feedback_files = selected_feedback_files(config, candidate.project_cfg)
                    decision = classify_tier(config, candidate.project_cfg, candidate.row, candidate.slice_name, feedback_files)
                    alias, selected_model, selection_note = pick_account_and_model(config, candidate.project_cfg, decision)
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
                        group_blocked = True
                        break
                    launch_plan.append((project_id, candidate, decision, alias, selected_model, selection_note))
                if group_blocked:
                    continue

                for project_id, candidate, decision, alias, selected_model, selection_note in launch_plan:
                    task = asyncio.create_task(
                        execute_project_slice(
                            config,
                            candidate.project_cfg,
                            candidate.row,
                            candidate.slice_name or "",
                            decision,
                            alias,
                            selected_model,
                            selection_note,
                        )
                    )
                    state.tasks[project_id] = task
                    running_count += 1

            for row in projects:
                project_id = row["id"]
                if project_id in state.tasks or project_id in handled_projects:
                    continue
                candidate = candidates.get(project_id)
                if not candidate or not candidate.dispatchable or not candidate.slice_name:
                    continue

                if running_count >= max_parallel:
                    break

                feedback_files = selected_feedback_files(config, candidate.project_cfg)
                decision = classify_tier(config, candidate.project_cfg, candidate.row, candidate.slice_name, feedback_files)
                alias, selected_model, selection_note = pick_account_and_model(config, candidate.project_cfg, decision)

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
                    continue

                task = asyncio.create_task(
                    execute_project_slice(
                        config,
                        candidate.project_cfg,
                        candidate.row,
                        candidate.slice_name,
                        decision,
                        alias,
                        selected_model,
                        selection_note,
                    )
                )
                state.tasks[project_id] = task
                running_count += 1
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
    state.stop.clear()
    app.state.scheduler = asyncio.create_task(scheduler_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    state.stop.set()
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
    with db() as conn:
        projects = [dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY id")]
        accounts = [dict(row) for row in conn.execute("SELECT * FROM accounts ORDER BY alias")]
        recent_runs = [dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 50")]
        recent_decisions = [dict(row) for row in conn.execute("SELECT * FROM spider_decisions ORDER BY id DESC LIMIT 50")]
        for idx, project in enumerate(projects):
            project["_project_order"] = idx
            project["queue"] = json.loads(project.pop("queue_json") or "[]")
            project_cfg = get_project_cfg(config, project["id"])
            has_queue_sources = bool(project_cfg.get("queue_sources"))
            project["enabled"] = bool(project_cfg.get("enabled", True))
            runtime_status = effective_project_status(
                stored_status=project.get("status"),
                queue=project["queue"],
                queue_index=int(project.get("queue_index") or 0),
                enabled=project["enabled"],
                active_run_id=project.get("active_run_id"),
                source_backlog_open=has_queue_sources and bool(project["queue"]),
            )
            project["status_internal"] = runtime_status
            project["status"] = runtime_status
            project["completion_basis"] = project_completion_basis(
                runtime_status=runtime_status,
                queue=project["queue"],
                queue_index=int(project.get("queue_index") or 0),
                has_queue_sources=has_queue_sources,
            )
            project["group_ids"] = [group["id"] for group in project_group_defs(config, project["id"])]
            project["agent_state"] = read_state_file(project["path"], project["state_file"] or ".agent-state.json")
            project["current_queue_item"] = project["queue"][project["queue_index"]] if project["queue_index"] < len(project["queue"]) else None
            project.update(estimate_project_eta(config, conn, project, now))
            project["queue_eta"] = queue_eta_payload(project)
            project_meta = registry["projects"].get(project["id"], {})
            project["remaining_milestones"] = remaining_milestone_items(project_meta)
            project["uncovered_scope"] = text_items(project_meta.get("uncovered_scope"))
            project["uncovered_scope_count"] = len(project["uncovered_scope"])
            project["milestone_coverage_complete"] = bool(project_meta.get("milestone_coverage_complete"))
            project["design_coverage_complete"] = bool(project_meta.get("design_coverage_complete"))
            project["milestone_eta"] = estimate_project_milestone_eta(project, project_meta, now)
            project["design_eta"] = estimate_project_design_eta(project_meta, project["milestone_eta"], now)
            project["status"] = public_project_status(runtime_status)
        fleet_eta = estimate_fleet_eta(config, projects, now)
        groups = []
        project_map = {project["id"]: project for project in projects}
        for group_cfg in config.get("project_groups") or []:
            group_meta = registry["groups"].get(group_cfg["id"], {})
            group_projects = [project_map[project_id] for project_id in group_cfg.get("projects") or [] if project_id in project_map]
            group_row = dict(group_cfg)
            group_row["contract_blockers"] = text_items(group_meta.get("contract_blockers"))
            group_row["remaining_milestones"] = remaining_milestone_items(group_meta)
            group_row["uncovered_scope"] = text_items(group_meta.get("uncovered_scope"))
            group_row["uncovered_scope_count"] = len(group_row["uncovered_scope"])
            group_row["milestone_coverage_complete"] = bool(group_meta.get("milestone_coverage_complete"))
            group_row["design_coverage_complete"] = bool(group_meta.get("design_coverage_complete"))
            group_row["project_statuses"] = [{"id": project["id"], "status": project["status"]} for project in group_projects]
            group_row.update(group_dispatch_state(group_cfg, group_meta, group_projects, now))
            group_row["status"] = effective_group_status(group_cfg, group_meta, group_projects)
            group_row["milestone_eta"] = estimate_group_milestone_eta(group_cfg, group_meta, now)
            group_row["program_eta"] = estimate_group_program_eta(group_meta, group_row["milestone_eta"], now)
            groups.append(group_row)
        primary_group = groups[0] if len(groups) == 1 else None
    for project in projects:
        project.pop("_project_order", None)
        project.pop("_schedule", None)
    for account in accounts:
        account["allowed_models"] = json.loads(account.pop("allowed_models_json") or "[]")
        account_cfg = (config.get("accounts") or {}).get(account["alias"], {})
        account["daily_usage"] = usage_for_account(account["alias"], "day")
        account["monthly_usage"] = usage_for_account(account["alias"], "month")
        account["active_runs"] = active_run_count_for_account(account["alias"])
        account["configured_health_state"] = str(account_cfg.get("health_state", "ready") or "ready")
        account["pool_state"] = account_runtime_state(account, account_cfg, now)
        account["spark_enabled"] = account_supports_spark(str(account.get("auth_kind") or ""), account_cfg, account["allowed_models"])
        account["codex_home"] = str(account_home(account["alias"]))
    return {
        "config": {
            "policies": config.get("policies", {}),
            "spider": config.get("spider", {}),
            "project_count": len(config.get("projects", [])),
            "group_count": len(config.get("project_groups", [])),
            "account_count": len(config.get("accounts", {})),
        },
        "projects": projects,
        "eta": fleet_eta,
        "queue_eta": fleet_eta,
        "groups": groups,
        "milestone_eta": (primary_group or {}).get("milestone_eta") if primary_group else {},
        "program_eta": (primary_group or {}).get("program_eta") if primary_group else {},
        "accounts": accounts,
        "recent_runs": recent_runs,
        "recent_decisions": recent_decisions,
        "token_alliance": summarize_alliance(config),
    }


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

    project_rows = []
    for p in status["projects"]:
        heartbeat = (p.get("agent_state") or {}).get("updated_at_utc", "")
        queue_len = len(p["queue"])
        if queue_len <= 0:
            progress_label = "0 / 0"
        elif p.get("status") == CONFIGURED_QUEUE_COMPLETE_STATUS:
            progress_label = f"{queue_len} / {queue_len}"
        else:
            progress_label = f"{min(p['queue_index'] + 1, queue_len)} / {queue_len}"
        project_rows.append(
            f"""
            <tr>
              <td>{td(p['id'])}</td>
              <td><div>{td(p.get('status'))}</div><div class="muted">{td(p.get('completion_basis'))}</div></td>
              <td>{td(p.get('current_queue_item'))}</td>
              <td>{progress_label}</td>
              <td>{td(p.get('remaining_slices'))}</td>
              <td><div>{td(p.get('eta_human'))}</div><div class="muted">{td(p.get('eta_basis'))}</div></td>
              <td><div>{td((p.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((p.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td>{td(p.get('uncovered_scope_count'))}</td>
              <td>{td(p.get('spider_tier'))}</td>
              <td>{td(p.get('spider_model'))}</td>
              <td>{td(p.get('spider_reason'))}</td>
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
              <td><div>{td(group.get('status'))}</div><div class="muted">{td(group.get('mode'))}</div></td>
              <td><div>{td('ready' if group.get('dispatch_ready') else 'blocked')}</div><div class="muted">{td(group.get('dispatch_basis'))}</div></td>
              <td>{td(members)}</td>
              <td>{td(contracts)}</td>
              <td>{td(len(group.get('contract_blockers') or []))}</td>
              <td>{td(len(group.get('dispatch_blockers') or []))}</td>
              <td>{td(group.get('uncovered_scope_count'))}</td>
              <td><div>{td((group.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td><div>{td((group.get('program_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((group.get('program_eta') or {}).get('eta_basis'))}</div></td>
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
        decision_rows.append(
            f"""
            <tr>
              <td>{td(row.get('id'))}</td>
              <td>{td(row.get('project_id'))}</td>
              <td>{td(row.get('slice_name'))}</td>
              <td>{td(row.get('spider_tier'))}</td>
              <td>{td(row.get('selected_model'))}</td>
              <td>{td(row.get('account_alias'))}</td>
              <td>{td(row.get('reason'))}</td>
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

        <h2>Projects</h2>
        <table>
          <thead>
            <tr>
              <th>Project</th><th>Configured Queue Status</th><th>Current slice</th><th>Progress</th><th>Remaining</th><th>Configured Queue ETA</th><th>Milestone ETA</th><th>Uncovered Scope</th><th>Route class</th><th>Model</th><th>Reason</th><th>Last error</th><th>Cooldown</th><th>Repo heartbeat</th>
            </tr>
          </thead>
          <tbody>
            {''.join(project_rows) or '<tr><td colspan="14">No projects configured.</td></tr>'}
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
              <th>Alias</th><th>Auth</th><th>Pool state</th><th>Spark</th><th>Allowed models</th><th>Active</th><th>Day cost</th><th>Month cost</th><th>Day budget</th><th>Month budget</th><th>Backoff</th><th>Last error</th>
            </tr>
          </thead>
          <tbody>
            {''.join(account_rows) or '<tr><td colspan="12">No accounts configured.</td></tr>'}
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
              <th>ID</th><th>Project</th><th>Account</th><th>Slice</th><th>Model</th><th>Route class</th><th>Status</th><th>Input</th><th>Output</th><th>Cost</th><th>Started</th><th>Finished</th><th>Log</th><th>Final</th>
            </tr>
          </thead>
          <tbody>
            {''.join(run_rows) or '<tr><td colspan="14">No runs yet.</td></tr>'}
          </tbody>
        </table>
      </body>
    </html>
    """
