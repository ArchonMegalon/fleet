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
import subprocess
import textwrap
import traceback
import urllib.error
import urllib.parse
import urllib.request
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
CODEX_HOME_ROOT = pathlib.Path(os.environ.get("FLEET_CODEX_HOME_ROOT", "/var/lib/codex-fleet/codex-homes"))
GROUP_ROOT = pathlib.Path(os.environ.get("FLEET_GROUP_ROOT", str(DB_PATH.parent / "groups")))
GH_HOSTS_PATH = pathlib.Path(os.environ.get("FLEET_GH_HOSTS_PATH", "/run/gh/hosts.yml"))
GITHUB_API_BASE = os.environ.get("FLEET_GITHUB_API_BASE", "https://api.github.com").rstrip("/")
AUDITOR_URL = os.environ.get("FLEET_AUDITOR_URL", "http://fleet-auditor:8093")

DEFAULT_PRICE_TABLE = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5.3-codex": {"input": 1.75, "cached_input": 0.175, "output": 14.00},
    "gpt-5.3-codex-spark": {"input": 0.0, "cached_input": 0.0, "output": 0.0},
}

SPARK_MODEL = "gpt-5.3-codex-spark"
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
CHATGPT_SUPPORTED_MODELS = {"gpt-5.4", "gpt-5.3-codex", SPARK_MODEL}
GITHUB_REVIEW_MODEL = "github-codex-review"
READY_STATUS = "dispatch_pending"
HEALING_STATUS = "healing"
WAITING_CAPACITY_STATUS = "waiting_capacity"
QUEUE_REFILLING_STATUS = "queue_refilling"
DECISION_REQUIRED_STATUS = "decision_required"
REVIEW_FIX_STATUS = "review_fix"
REVIEW_HOLD_STATUSES = {"awaiting_pr", "review_requested", "review_fix_required"}
REVIEW_VISIBLE_STATUSES = REVIEW_HOLD_STATUSES | {"review_failed"}
REVIEW_FAILED_INCIDENT_KIND = "review_failed"
BLOCKED_UNRESOLVED_INCIDENT_KIND = "blocked_unresolved"
DEFAULT_CAPTAIN_POLICY = {
    "priority": 100,
    "service_floor": 1,
    "shed_order": 100,
    "preemption_policy": "slice_boundary",
    "admission_policy": "normal",
}

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

DEFAULT_SINGLETON_GROUP_ROLES = ["auditor", "project_manager"]

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
                phase TEXT NOT NULL DEFAULT 'idle',
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
        conn.execute("ALTER TABLE group_runtime ADD COLUMN phase TEXT NOT NULL DEFAULT 'idle'")
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
    incident_cols = {row["name"] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()}
    if incident_cols and "context_json" not in incident_cols:
        conn.execute("ALTER TABLE incidents ADD COLUMN context_json TEXT NOT NULL DEFAULT '{}'")
    conn.execute("UPDATE projects SET status=? WHERE status IN ('idle', 'ready')", (READY_STATUS,))


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
    if re.search(pattern, existing, flags=re.S):
        updated = re.sub(pattern, managed_block, existing, flags=re.S)
    else:
        updated = existing.rstrip() + managed_block + "\n"
    if updated != existing:
        path.write_text(updated, encoding="utf-8")


def sync_design_repo_mirrors(config: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    results: List[Dict[str, Any]] = []
    for mirror in mirrors:
        if not isinstance(mirror, dict):
            continue
        project_cfg = repo_lookup.get(str(mirror.get("repo") or "").strip())
        if not project_cfg:
            continue
        repo_root = pathlib.Path(str(project_cfg.get("path") or "")).resolve()
        if not repo_root.exists():
            continue
        copied: List[str] = []
        product_target = str(mirror.get("product_target") or mirror.get("target") or ".codex-design/product").strip()
        for source_rel in mirror.get("product_sources") or mirror.get("sources") or []:
            source_path = (design_root / str(source_rel)).resolve()
            if not source_path.is_file():
                continue
            target_path = repo_root / product_target / pathlib.Path(str(source_rel)).name
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
                "project_id": str(project_cfg.get("id") or ""),
                "repo": str(mirror.get("repo") or ""),
                "copied_paths": copied,
            }
        )
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
    group_cfg = next((item for item in config.get("project_groups") or [] if str(item.get("id") or "") == group_id), {})
    log_group_run(
        group_id,
        run_kind="publish",
        phase="proposed_tasks",
        status="published",
        member_projects=[str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()],
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
        approved_rows = conn.execute(
            """
            SELECT *
            FROM audit_task_candidates
            WHERE status='approved'
            ORDER BY CASE scope_type WHEN 'group' THEN 0 ELSE 1 END, scope_id, last_seen_at ASC, task_index ASC
            """
        ).fetchall()
    if not approved_rows:
        return 0

    published = 0
    registry = load_program_registry(config)
    runtime_rows = group_runtime_rows()
    for candidate in approved_rows:
        if audit_task_candidate_meta(candidate).get("bootstrap_project"):
            continue
        scope_type = str(candidate["scope_type"] or "").strip()
        scope_id = str(candidate["scope_id"] or "").strip()
        if scope_type == "group":
            group_cfg = next((item for item in config.get("project_groups") or [] if str(item.get("id")) == scope_id), None)
            if not group_cfg:
                continue
            group_meta = effective_group_meta(group_cfg, registry, runtime_rows)
            if group_is_signed_off(group_meta):
                continue
            project_ids = [str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()]
            if any(project_id in state.tasks for project_id in project_ids):
                continue
            if publish_group_audit_candidate_runtime(config, candidate, source="auto"):
                published += 1
            continue

        if scope_type != "project":
            continue
        row = project_rows.get(scope_id)
        if not row or scope_id in state.tasks:
            continue
        project_groups = project_group_defs(config, scope_id)
        if project_groups:
            group_cfg = project_groups[0]
            group_meta = effective_group_meta(group_cfg, registry, runtime_rows)
            if group_is_signed_off(group_meta):
                continue
            member_ids = [str(project_id).strip() for project_id in (group_cfg.get("projects") or []) if str(project_id).strip()]
            if any(member_id in state.tasks for member_id in member_ids):
                continue
        if publish_project_audit_candidate_runtime(config, candidate, source="auto"):
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


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: pathlib.Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
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
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet["spider"] = deep_merge(DEFAULT_SPIDER, fleet.get("spider") or {})
    price_table = deep_merge(DEFAULT_PRICE_TABLE, (fleet["spider"].get("price_table") or {}))
    fleet["spider"]["price_table"] = price_table
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
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("verify_cmd", "")
        project.setdefault("design_doc", "")
        project.setdefault("enabled", True)
        project.setdefault("accounts", [])
        project.setdefault("account_policy", {})
        project.setdefault("queue_sources", [])
        project["queue"] = resolve_project_queue(project)
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
        review.setdefault("required_before_queue_advance", True)
        review.setdefault("focus_template", "for regressions and missing tests")
        review.setdefault("owner", "")
        review.setdefault("repo", "")
        review.setdefault("base_branch", "")
        review.setdefault("branch_template", f"fleet/{project.get('id', 'project')}")
        review.setdefault("bot_logins", ["codex"])
    sync_design_repo_mirrors(fleet)
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
                    json.dumps(account.get("allowed_models", [])),
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
                            active_run_id=CASE WHEN ? IN ('idle', ?, 'complete', 'paused', 'source_backlog_open') THEN NULL ELSE active_run_id END,
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
    data = None
    headers = github_headers(token)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"github api {method.upper()} {path} failed: {exc.code} {detail}") from exc
    return json.loads(raw) if raw.strip() else {}


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


def commit_and_push_review_branch(project_cfg: Dict[str, Any], repo_meta: Dict[str, Any], slice_name: str, token: str) -> Dict[str, Any]:
    repo_path = str(project_cfg["path"])
    branch = review_branch_name(project_cfg)
    checkout = run_capture(["git", "checkout", "-B", branch], cwd=repo_path, timeout_seconds=60)
    if checkout.returncode != 0:
        raise RuntimeError(checkout.stderr.strip() or "git checkout review branch failed")
    if not git_has_changes(repo_path):
        return {"branch": branch, "head_sha": git_head_sha(repo_path), "changed": False}
    add = run_capture(["git", "add", "-A"], cwd=repo_path, timeout_seconds=60)
    if add.returncode != 0:
        raise RuntimeError(add.stderr.strip() or "git add failed")
    commit_message = f"fleet({project_cfg['id']}): {truncate_title(slice_name, 72)}"
    commit = run_capture(
        ["git", "-c", "user.name=Codex Fleet", "-c", "user.email=fleet@local", "commit", "-m", commit_message],
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


def request_github_review(project_cfg: Dict[str, Any], pr_row: sqlite3.Row, token: str, head_sha: str) -> int:
    owner = str(pr_row["repo_owner"])
    repo = str(pr_row["repo_name"])
    pr_number = int(pr_row["pr_number"])
    focus = str(pr_row["review_focus"] or "").strip()
    body = "@codex review" + (f" {focus}" if focus else "")
    response = github_api_json(token, "POST", f"/repos/{owner}/{repo}/issues/{pr_number}/comments", payload={"body": body})
    now = iso(utc_now())
    with db() as conn:
        conn.execute(
            """
            UPDATE pull_requests
            SET review_status='requested',
                review_requested_at=?,
                review_completed_at=NULL,
                review_findings_count=0,
                review_blocking_findings_count=0,
                last_review_comment_id=?,
                last_review_head_sha=?,
                last_synced_at=?,
                updated_at=?
            WHERE project_id=?
            """,
            (now, str(response.get("id") or ""), head_sha, now, now, project_cfg["id"]),
        )
    return int(response.get("id") or 0)


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
                "UPDATE runs SET status=?, decision_reason=?, finished_at=CASE WHEN ? IN ('clean','findings_open','failed') THEN ? ELSE finished_at END WHERE id=?",
                (review_status, f"pr #{pr_number} {pr_url} ; focus={review_focus}", review_status, now, run_id),
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


def complete_project_slice_after_review(project_cfg: Dict[str, Any], finished_at: dt.datetime) -> None:
    project_id = project_cfg["id"]
    increment_queue(project_id)
    with db() as conn:
        row = conn.execute("SELECT queue_json, queue_index FROM projects WHERE id=?", (project_id,)).fetchone()
    queue = json.loads(row["queue_json"] or "[]")
    idx = int(row["queue_index"])
    next_status = (
        SOURCE_BACKLOG_OPEN_STATUS
        if idx >= len(queue) and bool(project_cfg.get("queue_sources")) and bool(queue)
        else ("complete" if idx >= len(queue) else READY_STATUS)
    )
    next_slice = queue[idx] if idx < len(queue) else None
    update_project_status(
        project_id,
        status=next_status,
        current_slice=next_slice,
        active_run_id=None,
        cooldown_until=utc_now() + dt.timedelta(seconds=1),
        last_run_at=finished_at,
        last_error=None,
    )


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
    requested_at = parse_iso(pr_row["review_requested_at"]) or parse_iso(pr_row["updated_at"]) or utc_now()
    bot_logins = list(project_review_policy(project_cfg).get("bot_logins") or ["codex"])

    pr = github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
    reviews = github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")
    review_comments = github_api_json(token, "GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/comments")
    issue_comments = github_api_json(token, "GET", f"/repos/{owner}/{repo}/issues/{pr_number}/comments")

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

    blocking_count = sum(1 for item in findings if bool(item.get("blocking")))
    sync_review_findings(project_id, pr_number, findings)
    now = iso(utc_now())
    with db() as conn:
        conn.execute(
            """
            UPDATE pull_requests
            SET pr_url=?, pr_state=?, draft=?, head_sha=?, review_status=?, review_completed_at=?, review_findings_count=?, review_blocking_findings_count=?, last_synced_at=?, updated_at=?
            WHERE project_id=?
            """,
            (
                str(pr.get("html_url") or pr_row["pr_url"] or ""),
                str(pr.get("state") or "open"),
                1 if bool(pr.get("draft", True)) else 0,
                str(pr.get("head", {}).get("sha") or pr_row["head_sha"] or ""),
                "findings_open" if findings else ("clean" if (codex_reviews or codex_review_comments or codex_issue_comments) else str(pr_row["review_status"] or "requested")),
                now if (codex_reviews or codex_review_comments or codex_issue_comments) else None,
                len(findings),
                blocking_count,
                now,
                now,
                project_id,
            ),
        )

    if findings:
        upsert_github_review_run(
            project_id,
            slice_name=str((pr_row["pr_title"] or project_cfg.get("id") or "").strip()),
            pr_number=pr_number,
            pr_url=str(pr.get("html_url") or pr_row["pr_url"] or ""),
            review_status="findings_open",
            review_focus=str(pr_row["review_focus"] or ""),
        )
        publish_review_feedback(project_cfg, str(pr.get("html_url") or pr_row["pr_url"] or ""), findings)
        with db() as conn:
            project_row = conn.execute("SELECT current_slice, spider_tier, spider_model, spider_reason FROM projects WHERE id=?", (project_id,)).fetchone()
        update_project_status(
            project_id,
            status="review_fix_required",
            current_slice=str((project_row["current_slice"] if project_row else "") or ""),
            active_run_id=None,
            cooldown_until=utc_now() + dt.timedelta(seconds=1),
            last_run_at=utc_now(),
            last_error="github review findings published for follow-up",
            spider_tier=project_row["spider_tier"] if project_row else None,
            spider_model=project_row["spider_model"] if project_row else None,
            spider_reason=project_row["spider_reason"] if project_row else None,
        )
    elif codex_reviews or codex_review_comments or codex_issue_comments:
        upsert_github_review_run(
            project_id,
            slice_name=str((pr_row["pr_title"] or project_cfg.get("id") or "").strip()),
            pr_number=pr_number,
            pr_url=str(pr.get("html_url") or pr_row["pr_url"] or ""),
            review_status="clean",
            review_focus=str(pr_row["review_focus"] or ""),
        )
        complete_project_slice_after_review(project_cfg, utc_now())

    return {
        "pr_number": pr_number,
        "pr_url": str(pr.get("html_url") or pr_row["pr_url"] or ""),
        "review_status": "findings_open" if findings else ("clean" if (codex_reviews or codex_review_comments or codex_issue_comments) else str(pr_row["review_status"] or "requested")),
        "review_findings_count": len(findings),
        "review_blocking_findings_count": blocking_count,
    }


def sync_pending_github_reviews(config: Dict[str, Any]) -> None:
    if not table_exists("pull_requests"):
        return
    with db() as conn:
        rows = conn.execute(
            """
            SELECT project_id
            FROM pull_requests
            WHERE review_mode='github' AND review_status IN ('queued','requested')
            ORDER BY updated_at ASC, project_id ASC
            """
        ).fetchall()
    for row in rows:
        project_id = str(row["project_id"] or "").strip()
        if not project_id or project_id in state.tasks:
            continue
        try:
            sync_github_review_state(config, project_id)
        except Exception as exc:
            with db() as conn:
                conn.execute(
                    "UPDATE pull_requests SET review_status='failed', last_synced_at=?, updated_at=? WHERE project_id=?",
                    (iso(utc_now()), iso(utc_now()), project_id),
                )
            update_project_status(project_id, status="review_failed", current_slice=None, active_run_id=None, cooldown_until=None, last_run_at=utc_now(), last_error=str(exc))


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
    return [dict(row) for row in rows]


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
    status = str(stored_status or "").strip() or READY_STATUS
    if not enabled:
        return "paused"
    if int(queue_index) >= len(queue):
        if status in {"starting", "running", "verifying"} and active_run_id:
            return status
        if source_backlog_open:
            return SOURCE_BACKLOG_OPEN_STATUS
        return "complete"
    if status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS, "idle"}:
        return READY_STATUS
    return status


def public_project_status(
    runtime_status: Optional[str],
    *,
    cooldown_until: Optional[str] = None,
    needs_refill: bool = False,
    open_task_count: int = 0,
    approved_task_count: int = 0,
    group_signed_off: bool = False,
) -> str:
    status = str(runtime_status or "").strip() or READY_STATUS
    cooldown = parse_iso(cooldown_until)
    if status in {"idle", READY_STATUS} and cooldown and cooldown > utc_now():
        return WAITING_CAPACITY_STATUS
    if status in {"idle", READY_STATUS}:
        return WAITING_CAPACITY_STATUS
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
            return DECISION_REQUIRED_STATUS
        return HEALING_STATUS
    if status == "complete":
        if group_signed_off:
            return COMPLETED_SIGNED_OFF_STATUS
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
        return "local verify passed; waiting to create or update the GitHub pull request"
    if status == "review_requested":
        return "local verify passed; GitHub Codex review has been requested and queue advance is gated on review results"
    if status == "review_failed":
        return "GitHub review orchestration failed and needs operator attention"
    if status == "review_fix_required":
        return "GitHub review returned findings and the slice needs follow-up fixes before queue advance"
    if status == WAITING_CAPACITY_STATUS:
        return "configured queue has remaining work; waiting for scheduler dispatch, account eligibility, cooldown recovery, or higher-level gate release"
    if status == HEALING_STATUS:
        return "the resolver is actively healing the current blockage or refill condition"
    if status == QUEUE_REFILLING_STATUS:
        return "approved resolver tasks are being published into the next queue overlay"
    if status == DECISION_REQUIRED_STATUS:
        return "resolver-generated follow-up work still needs operator approval before queue advance"
    if status == REVIEW_FIX_STATUS:
        return "GitHub review returned findings and the review-fix loop is active"
    if status in {"starting", "running", "verifying"}:
        if queue_len == 0:
            return "configured queue currently resolves to zero active items"
        return f"configured queue has remaining work at {current} / {queue_len}"
    if status in {"idle", READY_STATUS}:
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
        elif runtime_status == "awaiting_pr":
            stop_reason = "local verify passed and the slice is waiting for PR creation or update"
            next_action = "check GitHub repo connectivity or request review again"
            unblocker = "operator"
        elif runtime_status == "review_requested":
            stop_reason = "the slice is waiting on GitHub Codex review"
            next_action = "wait for review, sync review state, or re-request review if needed"
            unblocker = "GitHub Codex review lane"
        elif runtime_status == "review_failed":
            stop_reason = "GitHub review orchestration failed"
            next_action = "let the healer resync review state or repair the PR lane before escalating"
            unblocker = "healer"
        elif runtime_status == "review_fix_required":
            stop_reason = "GitHub review returned findings that must be fixed before queue advance"
            next_action = "let the healer apply the review fixes and re-request GitHub review"
            unblocker = "healer"
        elif runtime_status == "awaiting_account":
            stop_reason = "no eligible account or model is available for the current slice"
            next_action = "let the scheduler spill over to another eligible account or wait for capacity recovery"
            unblocker = "scheduler"
        elif runtime_status == "blocked":
            stop_reason = "repeated failures blocked execution"
            if approved_task_count > 0 or open_task_count > 0:
                next_action = "healing tasks are ready; the resolver will publish the next narrowed follow-up"
                unblocker = "healer"
            else:
                next_action = "the targeted auditor is generating a recovery path before escalation"
                unblocker = "auditor"
        elif cooldown_until:
            stop_reason = "project is cooling down after a recent failure or rate limit"
            next_action = "wait for cooldown expiry or let the scheduler reroute capacity"
            unblocker = "scheduler"
        elif runtime_status == SOURCE_BACKLOG_OPEN_STATUS:
            stop_reason = "the current queue materialization is exhausted, but the backlog source still reports open work"
            if approved_task_count > 0:
                next_action = "approved refill tasks are being published into the next queue overlay"
                unblocker = "healer"
            elif open_task_count > 0:
                next_action = "resolver proposals exist; approve them only if policy does not allow auto-publish"
                unblocker = "operator"
            else:
                next_action = "the auditor is materializing the next scoped queue from backlog evidence"
                unblocker = "auditor"
        elif runtime_status == "complete" and uncovered_scope_count > 0:
            stop_reason = "the current queue is exhausted while uncovered scope remains"
            if approved_task_count > 0:
                next_action = "approved uncovered-scope tasks are being published automatically"
                unblocker = "healer"
            elif open_task_count > 0:
                next_action = "resolver proposals exist; approve them only if policy disallows auto-heal"
                unblocker = "operator"
            else:
                next_action = "the auditor is generating the next scoped queue from uncovered scope"
                unblocker = "auditor"
        elif runtime_status == "complete":
            stop_reason = "the current queue is exhausted"
            next_action = "sign off the product or publish the next scoped queue"
            unblocker = "operator"
        elif queue_len <= 0 and project_cfg.get("queue_sources"):
            stop_reason = "the backlog source produced zero active items"
            if approved_task_count > 0:
                next_action = "approved refill tasks are being published automatically"
                unblocker = "healer"
            elif open_task_count > 0:
                next_action = "resolver proposals exist; approve them only if policy disallows auto-heal"
                unblocker = "operator"
            else:
                next_action = "the auditor is refilling the queue from source-backed backlog evidence"
                unblocker = "auditor"
        elif runtime_status in {"idle", READY_STATUS}:
            stop_reason = "configured queue has remaining work and is waiting for scheduler dispatch"
            next_action = "let the fleet dispatch the next slice automatically or run it now"
            unblocker = "scheduler"
    exhausted_or_empty = runtime_status in {CONFIGURED_QUEUE_COMPLETE_STATUS, SOURCE_BACKLOG_OPEN_STATUS, "complete"} or (
        queue_len <= 0 and bool(project_cfg.get("queue_sources"))
    )
    needs_refill = bool(not active and exhausted_or_empty and runtime_status not in REVIEW_VISIBLE_STATUSES and not group_signed_off)
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


def audit_task_counts(project_id: str) -> Dict[str, int]:
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
    return bool(
        meta.get("signed_off")
        or meta.get("product_signed_off")
        or signoff_state in {"signed_off", "product_signed_off", "complete"}
    )


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
            queue = json.loads(row.get("queue_json") or "[]")
            runtime_status = effective_project_status(
                stored_status=row.get("status"),
                queue=queue,
                queue_index=int(row.get("queue_index") or 0),
                enabled=bool(project_cfg.get("enabled", True)),
                active_run_id=row.get("active_run_id"),
                source_backlog_open=bool(project_cfg.get("queue_sources")) and bool(queue),
            )
            counts = audit_task_counts(str(project_id))
            stop_ctx = project_stop_context(
                project_cfg=project_cfg,
                runtime_status=runtime_status,
                queue_len=len(queue),
                uncovered_scope_count=0,
                open_task_count=int(counts["open"]),
                approved_task_count=int(counts["approved"]),
                last_error=row.get("last_error"),
                cooldown_until=row.get("cooldown_until"),
                milestone_coverage_complete=False,
                design_coverage_complete=False,
                group_signed_off=group_is_signed_off(group_meta),
            )
            project_public_status = public_project_status(
                runtime_status,
                cooldown_until=row.get("cooldown_until"),
                needs_refill=bool(stop_ctx.get("needs_refill")),
                open_task_count=int(counts["open"]),
                approved_task_count=int(counts["approved"]),
            )
            group_projects.append(
                {
                    "id": str(project_id),
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
        current_runtime = runtime_rows.get(group_id, {})
        previous_phase = str(current_runtime.get("phase") or "").strip().lower() or "idle"
        phase_timestamp = current_runtime.get("last_phase_at") if previous_phase == next_phase else iso(now)
        with db() as conn:
            conn.execute(
                """
                INSERT INTO group_runtime(group_id, signoff_state, signed_off_at, reopened_at, last_audit_requested_at, last_refill_requested_at, phase, last_phase_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    phase=excluded.phase,
                    last_phase_at=excluded.last_phase_at,
                    updated_at=excluded.updated_at
                """,
                (
                    group_id,
                    str(current_runtime.get("signoff_state") or "open"),
                    current_runtime.get("signed_off_at"),
                    current_runtime.get("reopened_at"),
                    current_runtime.get("last_audit_requested_at"),
                    current_runtime.get("last_refill_requested_at"),
                    next_phase,
                    phase_timestamp,
                    iso(now),
                ),
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

    runtime_status = str(row["status"] or "").strip() or READY_STATUS
    if runtime_status in {"complete", "paused", SOURCE_BACKLOG_OPEN_STATUS, "idle"}:
        runtime_status = READY_STATUS
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

    if runtime_status in REVIEW_VISIBLE_STATUSES:
        return DispatchCandidate(
            row=row,
            project_cfg=project_cfg,
            queue=queue,
            queue_index=queue_index,
            slice_name=queue[queue_index],
            runtime_status=runtime_status,
            cooldown_until=parse_iso(row["cooldown_until"]),
            dispatchable=False,
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
    status = project_runtime_status(project)
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
    member_ids = [str(project.get("id") or "").strip() for project in group_projects if str(project.get("id") or "").strip()]
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
    remaining_slices = sum(max(project_queue_length(project) - int(project.get("queue_index") or 0), 0) for project in group_projects)
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


def audit_task_candidate_counts_for_scope(scope_type: str, scope_ids: List[str]) -> Dict[str, int]:
    if not table_exists("audit_task_candidates") or not scope_ids:
        return {"open": 0, "approved": 0}
    placeholders = ", ".join("?" for _ in scope_ids)
    counts = {"open": 0, "approved": 0}
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT status, COUNT(*) AS count
            FROM audit_task_candidates
            WHERE scope_type=? AND scope_id IN ({placeholders}) AND status IN ('open', 'approved')
            GROUP BY status
            """,
            (scope_type, *scope_ids),
        ).fetchall()
    for row in rows:
        status = str(row["status"] or "").strip().lower()
        if status in counts:
            counts[status] = int(row["count"] or 0)
    return counts


def group_ready_project_ids(group_projects: List[Dict[str, Any]]) -> List[str]:
    return [
        str(project.get("id") or "")
        for project in group_projects
        if project_runtime_status(project) in {"idle", READY_STATUS}
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


def group_open_incidents(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    group_id = str(group.get("id") or "").strip()
    project_ids = [str(project.get("id") or "").strip() for project in group_projects if str(project.get("id") or "").strip()]
    incidents = incident_rows(status="open", limit=100, scope_type="group", scope_ids=[group_id]) if group_id else []
    incidents.extend(incident_rows(status="open", limit=100, scope_type="project", scope_ids=project_ids))
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
    blockers = list(group.get("contract_blockers") or []) + list(group.get("dispatch_blockers") or [])
    status = str(group.get("status") or "").strip().lower()
    auditor_can_solve = bool(group.get("auditor_can_solve"))
    incidents = list(group.get("incidents") or [])
    if incidents:
        top = incidents[0]
        return f"{group_id}: {short_question_detail(top.get('title') or top.get('summary') or 'an incident needs operator attention')}. Should I apply the proposed recovery, or override it manually?"
    if review_blocking > 0:
        return f"{group_id}: Codex review reported blocking findings. Should I fix them and re-request review, or accept the risk?"
    if review_waiting > 0:
        return f"{group_id}: review is still pending. Should I wait for GitHub review, or override the review gate?"
    if status == "product_signed_off":
        return f"{group_id}: this group is signed off. Should I keep it closed, or reopen it for more work?"
    if blockers:
        first_blocker = short_question_detail(blockers[0])
        if ready_count > 1 and not auditor_can_solve:
            return f"{group_id}: {ready_count} dispatch-eligible projects are blocked above the repo layer and the auditor has no publishable fix. Should I keep the block in place, or choose the missing contract or package direction? First blocker: {first_blocker}"
        return f"{group_id}: blockers remain open. Should I keep the block in place, or override it manually? First blocker: {first_blocker}"
    if status == "proposed_tasks":
        return f"{group_id}: the auditor has proposed follow-up work. Should I publish the approved tasks now, or keep them pending?"
    if status == "audit_required":
        return f"{group_id}: the current queue is exhausted without signoff. Should I run another audit or refill pass, or sign off the group?"
    if ready_count > 0:
        return f"{group_id}: {ready_count} projects are waiting for dispatch. Should I let the group run, or keep it paused?"
    return f"{group_id}: what is the next operator decision for this group?"


def group_notification_payload(group: Dict[str, Any], group_projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    ready_ids = list(group.get("ready_project_ids") or [])
    ready_count = len(ready_ids)
    auditor_can_solve = bool(group.get("auditor_can_solve"))
    blockers = list(group.get("contract_blockers") or []) + list(group.get("dispatch_blockers") or [])
    review_blocking = int(group.get("review_blocking_count") or 0)
    incidents = list(group.get("incidents") or [])
    reason_bits: List[str] = []
    if incidents:
        top = incidents[0]
        reason_bits.append(short_question_detail(top.get("title") or top.get("summary") or "", limit=140))
    if blockers:
        reason_bits.append(short_question_detail(blockers[0], limit=140))
    if review_blocking > 0:
        reason_bits.append(f"{review_blocking} blocking review finding(s)")
    if not reason_bits:
        reason_bits.append(str(group.get("dispatch_basis") or group.get("status") or "operator attention required"))
    needs_notification = bool(incidents) or (ready_count > 1 and not auditor_can_solve and not bool(group.get("signed_off")))
    severity = str((incidents[0] if incidents else {}).get("severity") or ("high" if blockers or review_blocking > 0 else "medium"))
    title = (
        f"{group.get('id')}: {len(incidents)} incident(s) need operator attention"
        if incidents
        else f"{group.get('id')}: {ready_count} dispatch-eligible project(s) need operator attention"
    )
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
        "notification_key": f"{group.get('id')}|{ready_count}|{len(incidents)}|{int(auditor_can_solve)}|{'; '.join(reason_bits)}",
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
    active_statuses = {"running", "starting", "verifying", "idle", READY_STATUS, "awaiting_account", "blocked", "cooldown"}
    if any(project_runtime_status(project) in active_statuses for project in group_projects):
        return "lockstep_active"
    return "audit_required"


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

    return SYSTEM_PROMPT_TEMPLATE.format(
        instructions="\n".join(instructions),
        slice_name=slice_name,
        tier=decision["tier"],
        model=decision["selected_model"],
        reasoning_effort=decision["reasoning_effort"],
        reason=decision["reason"],
        worker_posture_block="\n".join(posture_lines),
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
    }


def handle_review_incidents(project_id: str, *, status: str, current_slice: Optional[str], last_error: Optional[str]) -> None:
    context = incident_context_for_project(project_id, current_slice=current_slice, last_error=last_error)
    if status == "review_failed":
        open_or_update_incident(
            scope_type="project",
            scope_id=project_id,
            incident_kind=REVIEW_FAILED_INCIDENT_KIND,
            severity="critical",
            title=f"{project_id} review failed",
            summary="GitHub review orchestration failed and needs operator attention before queue advance can continue.",
            context=context,
        )
        return
    if status == "review_fix_required":
        open_or_update_incident(
            scope_type="project",
            scope_id=project_id,
            incident_kind=REVIEW_FAILED_INCIDENT_KIND,
            severity="high",
            title=f"{project_id} review returned blocking findings",
            summary="GitHub review reported findings that must be fixed before the slice can advance.",
            context=context,
        )
        return
    resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_FAILED_INCIDENT_KIND])


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
        if status in {"review_failed", "review_fix_required"}:
            handle_review_incidents(project_id, status=status, current_slice=current_slice, last_error=last_error)
        else:
            resolve_incidents(scope_type="project", scope_id=project_id, incident_kinds=[REVIEW_FAILED_INCIDENT_KIND])
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


def pick_account_and_model(
    config: Dict[str, Any],
    project_cfg: Dict[str, Any],
    decision: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str], str, List[Dict[str, Any]]]:
    policy = project_account_policy(project_cfg)
    aliases = ordered_project_aliases(project_cfg)
    if not aliases:
        return None, None, "project has no configured accounts", []
    price_table = config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE
    now = utc_now()
    wanted_models = list(decision["model_preferences"])
    if not bool(policy.get("spark_enabled", True)):
        wanted_models = [model for model in wanted_models if model != SPARK_MODEL]
    if not wanted_models:
        return None, None, "route class produced no eligible models after filtering", []
    candidates: List[Tuple[int, int, dt.datetime, int, int, str, str, str, int]] = []
    config_accounts = config.get("accounts") or {}
    rejections: List[str] = []
    selection_trace: List[Dict[str, Any]] = []

    with db() as conn:
        for alias_order, alias in enumerate(aliases):
            lane_rank, lane_name = account_lane(alias, policy)
            trace: Dict[str, Any] = {"alias": alias, "lane": lane_name, "selected": False}
            row = conn.execute("SELECT * FROM accounts WHERE alias=?", (alias,)).fetchone()
            if not row:
                trace.update({"state": "rejected", "reason": "missing account record"})
                selection_trace.append(trace)
                rejections.append(f"{alias}: missing account record")
                continue
            account_cfg = config_accounts.get(alias) or {}
            auth_kind = row["auth_kind"]
            trace["auth_kind"] = auth_kind
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

            active = active_run_count_for_account(alias)
            max_parallel_runs = int(row["max_parallel_runs"] or 1)
            trace["active_runs"] = active
            trace["max_parallel_runs"] = max_parallel_runs
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

            allowed = json_field(row["allowed_models_json"], [])
            trace["allowed_models"] = list(allowed) if isinstance(allowed, list) else []
            available_models: List[Tuple[int, str]] = []
            for model_index, model in enumerate(wanted_models):
                if allowed and model not in allowed:
                    continue
                if not model_supported_for_auth_kind(model, auth_kind):
                    continue
                if model == SPARK_MODEL and not account_supports_spark(auth_kind, account_cfg, allowed):
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
            trace_idx = len(selection_trace)
            trace.update(
                {
                    "state": "candidate",
                    "selected_model": chosen_model,
                    "estimated_cost_usd": round(est_cost, 4),
                    "last_used_at": iso(last_used),
                    "reason": f"eligible on {chosen_model}",
                }
            )
            selection_trace.append(trace)
            candidates.append(
                (
                    lane_rank,
                    active,
                    last_used,
                    model_index,
                    alias_order,
                    alias,
                    chosen_model,
                    f"route={decision['tier']}; lane={lane_name}; state={pool_state}; auth={auth_kind}; estimated cost ${est_cost:.4f}",
                    trace_idx,
                )
            )

    if not candidates:
        detail = "; ".join(rejections[:4]) if rejections else "all candidates filtered"
        return None, None, f"no eligible account/model after auth, pool state, allowlist, or budget filtering ({detail})", selection_trace
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]))
    _, _, _, _, _, alias, model, why, selected_trace_idx = candidates[0]
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
    selection_trace: List[Dict[str, Any]],
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
    decision_meta = {
        "classification_mode": str(config.get("spider", {}).get("classification_mode") or "heuristic_v2"),
        "estimated_prompt_chars": int(decision["estimated_prompt_chars"]),
        "estimated_input_tokens": int(decision["estimated_input_tokens"]),
        "estimated_output_tokens": int(decision["estimated_output_tokens"]),
        "predicted_changed_files": int(decision["predicted_changed_files"]),
        "requires_contract_authority": bool(decision["requires_contract_authority"]),
        "spark_eligible": bool(decision["spark_eligible"]),
        "feedback_count": len(feedback_files),
    }

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
                review = project_review_policy(project_cfg)
                review_required = bool(review.get("enabled", True)) and bool(review.get("required_before_queue_advance", True))
                if review_required and str(review.get("mode") or "github").strip().lower() == "github":
                    token = github_token()
                    if not token:
                        raise RuntimeError("GitHub review is enabled but no GitHub token is available in fleet")
                    repo_meta = project_github_repo(project_cfg, token)
                    branch_info = commit_and_push_review_branch(project_cfg, repo_meta, slice_name, token)
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
                        next_status = (
                            SOURCE_BACKLOG_OPEN_STATUS
                            if idx >= len(queue) and bool(project_cfg.get("queue_sources")) and bool(queue)
                            else ("complete" if idx >= len(queue) else READY_STATUS)
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
                    next_status = (
                        SOURCE_BACKLOG_OPEN_STATUS
                        if idx >= len(queue) and bool(project_cfg.get("queue_sources")) and bool(queue)
                        else ("complete" if idx >= len(queue) else READY_STATUS)
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
        state.tasks.pop(project_id, None)


async def scheduler_loop() -> None:
    while not state.stop.is_set():
        config = normalize_config()
        try:
            auto_publish_approved_audit_candidates(config)
            config = normalize_config()
            sync_config_to_db(config)
            sync_pending_github_reviews(config)
            reconcile_project_incidents()
            sync_group_runtime_phase(config)
            max_parallel = int(get_policy(config, "max_parallel_runs", 3))
            with db() as conn:
                projects = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
            running_count = len(state.tasks)
            now = utc_now()
            registry = load_program_registry(config)
            group_runtime = group_runtime_rows()
            candidates: Dict[str, DispatchCandidate] = {}
            for row in projects:
                project_id = row["id"]
                if project_id in state.tasks:
                    continue
                project_cfg = get_project_cfg(config, project_id)
                candidates[project_id] = prepare_dispatch_candidate(config, project_cfg, row, now)

            handled_projects: set[str] = set()
            running_by_group: Dict[str, int] = {}
            for running_project_id in state.tasks:
                for running_group in project_group_defs(config, running_project_id):
                    group_id = str(running_group.get("id") or "").strip()
                    if group_id:
                        running_by_group[group_id] = int(running_by_group.get(group_id) or 0) + 1
            pressure_high = running_count >= max(0, max_parallel - 1)
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
                group_meta = effective_group_meta(group, registry, group_runtime)
                dispatch = group_dispatch_state(group, group_meta, group_projects, now)
                if not dispatch["dispatch_ready"]:
                    continue
                if running_count + len(member_ids) > max_parallel:
                    continue

                launch_plan: List[Tuple[str, DispatchCandidate, Dict[str, Any], str, str, str, List[Dict[str, Any]]]] = []
                group_blocked = False
                for project_id in member_ids:
                    candidate = candidates[project_id]
                    if not candidate.dispatchable or not candidate.slice_name:
                        group_blocked = True
                        break
                    feedback_files = selected_feedback_files(config, candidate.project_cfg)
                    decision = classify_tier(config, candidate.project_cfg, candidate.row, candidate.slice_name, feedback_files)
                    alias, selected_model, selection_note, selection_trace = pick_account_and_model(config, candidate.project_cfg, decision)
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
                    launch_plan.append((project_id, candidate, decision, alias, selected_model, selection_note, selection_trace))
                if group_blocked:
                    continue

                for project_id, candidate, decision, alias, selected_model, selection_note, selection_trace in launch_plan:
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
                            selection_trace,
                        )
                    )
                    state.tasks[project_id] = task
                    running_count += 1
                if launch_plan:
                    log_group_run(
                        str(group.get("id") or ""),
                        run_kind="dispatch",
                        phase="running",
                        status="dispatched",
                        member_projects=[project_id for project_id, *_ in launch_plan],
                        details={
                            "mode": "lockstep",
                            "slices": {project_id: candidate.slice_name for project_id, candidate, *_ in launch_plan},
                        },
                    )
                    running_by_group[str(group.get("id") or "")] = int(running_by_group.get(str(group.get("id") or "")) or 0) + len(launch_plan)

            ordered_rows = sorted(
                projects,
                key=lambda item: captain_dispatch_key(
                    group_cfg=(project_group_defs(config, item["id"]) or [{"id": f"solo-{item['id']}", "captain": DEFAULT_CAPTAIN_POLICY}])[0],
                    running_by_group=running_by_group,
                    pressure_high=running_count >= max(0, max_parallel - 1),
                ),
            )
            for row in ordered_rows:
                project_id = row["id"]
                if project_id in state.tasks or project_id in handled_projects:
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

                feedback_files = selected_feedback_files(config, candidate.project_cfg)
                decision = classify_tier(config, candidate.project_cfg, candidate.row, candidate.slice_name, feedback_files)
                alias, selected_model, selection_note, selection_trace = pick_account_and_model(config, candidate.project_cfg, decision)

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
                        selection_trace,
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
                            "slices": {project_id: candidate.slice_name},
                        },
                    )
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
    usage_start = usage_window_start(config)
    group_runtime = group_runtime_rows()
    pr_rows = pull_request_rows()
    review_summary = review_findings_summary()
    open_incident_items = incident_rows(status="open", limit=400)
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
            project_groups = project_group_defs(config, project["id"])
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
            project["group_ids"] = [group["id"] for group in project_groups]
            project["agent_state"] = read_state_file(project["path"], project["state_file"] or ".agent-state.json")
            project["current_queue_item"] = project["queue"][project["queue_index"]] if project["queue_index"] < len(project["queue"]) else None
            project.update(estimate_project_eta(config, conn, project, now))
            project["queue_eta"] = queue_eta_payload(project)
            project_meta = registry["projects"].get(project["id"], {})
            project_group_meta = effective_group_meta(project_groups[0], registry, group_runtime) if project_groups else {}
            project["group_signed_off"] = group_is_signed_off(project_group_meta)
            project["remaining_milestones"] = remaining_milestone_items(project_meta)
            project["uncovered_scope"] = text_items(project_meta.get("uncovered_scope"))
            project["uncovered_scope_count"] = len(project["uncovered_scope"])
            project["milestone_coverage_complete"] = bool(project_meta.get("milestone_coverage_complete"))
            project["design_coverage_complete"] = bool(project_meta.get("design_coverage_complete"))
            project["milestone_eta"] = estimate_project_milestone_eta(project, project_meta, now)
            project["design_eta"] = estimate_project_design_eta(project_meta, project["milestone_eta"], now)
            project["audit_task_counts"] = audit_task_counts(project["id"])
            project["pull_request"] = pr_rows.get(project["id"]) or {}
            project["review_findings"] = review_summary.get(project["id"], {"count": 0, "blocking_count": 0})
            project["incidents"] = [item for item in open_incident_items if str(item.get("scope_type") or "") == "project" and str(item.get("scope_id") or "") == project["id"]]
            project["open_incident_count"] = len(project["incidents"])
            project["primary_incident"] = project["incidents"][0] if project["incidents"] else None
            project.update(
                project_stop_context(
                    project_cfg=project_cfg,
                    runtime_status=runtime_status,
                    queue_len=len(project["queue"]),
                    uncovered_scope_count=project["uncovered_scope_count"],
                    open_task_count=project["audit_task_counts"]["open"],
                    approved_task_count=project["audit_task_counts"]["approved"],
                    last_error=project.get("last_error"),
                    cooldown_until=project.get("cooldown_until"),
                    milestone_coverage_complete=project["milestone_coverage_complete"],
                    design_coverage_complete=project["design_coverage_complete"],
                    group_signed_off=project["group_signed_off"],
                )
            )
            project["pressure_state"] = project_pressure_state(project)
            project["allowance_usage"] = recent_usage_for_scope([project["id"]], usage_start)
            project["status"] = public_project_status(
                runtime_status,
                cooldown_until=project.get("cooldown_until"),
                needs_refill=bool(project.get("needs_refill")),
                open_task_count=int(project["audit_task_counts"]["open"]),
                approved_task_count=int(project["audit_task_counts"]["approved"]),
                group_signed_off=project["group_signed_off"],
            )
        fleet_eta = estimate_fleet_eta(config, projects, now)
        groups = []
        project_map = {project["id"]: project for project in projects}
        for group_cfg in config.get("project_groups") or []:
            group_meta = effective_group_meta(group_cfg, registry, group_runtime)
            group_projects = [project_map[project_id] for project_id in group_cfg.get("projects") or [] if project_id in project_map]
            group_row = dict(group_cfg)
            group_row["captain"] = group_captain_policy(group_cfg)
            group_row["signed_off"] = group_is_signed_off(group_meta)
            group_row["signoff_state"] = str(group_meta.get("signoff_state") or ("signed_off" if group_row["signed_off"] else "open"))
            group_row["signed_off_at"] = group_meta.get("signed_off_at")
            group_row["reopened_at"] = group_meta.get("reopened_at")
            group_row["contract_blockers"] = text_items(group_meta.get("contract_blockers"))
            group_row["remaining_milestones"] = remaining_milestone_items(group_meta)
            group_row["uncovered_scope"] = text_items(group_meta.get("uncovered_scope"))
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
            group_row["status"] = effective_group_status(group_cfg, group_meta, group_projects)
            group_row["phase"] = derive_group_phase(group_row, group_projects)
            group_row["milestone_eta"] = estimate_group_milestone_eta(group_cfg, group_meta, now)
            group_row["program_eta"] = estimate_group_program_eta(group_meta, group_row["milestone_eta"], now)
            group_row["allowance_usage"] = recent_usage_for_scope([project["id"] for project in group_projects], usage_start)
            group_row["pool_sufficiency"] = group_pool_sufficiency(config, group_cfg, group_projects, now)
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
    if not pr_row:
        branch_info = commit_and_push_review_branch(project_cfg, repo_meta, slice_name, token)
        if not branch_info.get("changed"):
            raise HTTPException(400, "no committed or pending changes are available for review")
        ensure_pull_request(project_cfg, repo_meta, str(branch_info["branch"]), str(branch_info["head_sha"]), slice_name, token)
        pr_row = pull_request_row(project_id)
    if not pr_row:
        raise HTTPException(500, "unable to create pull request record")
    request_github_review(project_cfg, pr_row, token, str(pr_row["head_sha"] or git_head_sha(str(project_cfg["path"]))))
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


@app.post("/api/projects/{project_id}/review/request")
def api_request_project_review(project_id: str) -> Dict[str, Any]:
    return request_project_github_review_now(project_id)


@app.post("/api/projects/{project_id}/review/sync")
def api_sync_project_review(project_id: str) -> Dict[str, Any]:
    config = normalize_config()
    return sync_github_review_state(config, project_id)


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
    audit_required_groups = [g for g in status.get("groups", []) if g.get("status") == "audit_required"]
    high_pressure_groups = [g for g in status.get("groups", []) if str(g.get("pressure_state") or "") in {"critical", "high"}]
    tight_pool_groups = [
        g for g in status.get("groups", []) if str((g.get("pool_sufficiency") or {}).get("level") or "") in {"blocked", "insufficient", "tight"}
    ]
    ready_groups = [
        g
        for g in status.get("groups", [])
        if g.get("dispatch_ready") and g.get("status") not in {"audit_required", "proposed_tasks", "product_signed_off"}
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
        elif p.get("status") == CONFIGURED_QUEUE_COMPLETE_STATUS:
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
              <td><div>{review_link or td(review_label)}</div><div class="muted">requested {td(review_row.get('review_requested_at') or '')}</div></td>
              <td><div>{td(p.get('eta_human'))}</div><div class="muted">{td(p.get('eta_basis'))}</div></td>
              <td><div>{td((p.get('milestone_eta') or {}).get('eta_human') or 'unknown')}</div><div class="muted">{td((p.get('milestone_eta') or {}).get('eta_basis'))}</div></td>
              <td>{td(p.get('uncovered_scope_count'))}</td>
              <td><div>{td(p.get('spider_tier'))}</div><div class="muted">{td(p.get('spider_model'))}</div></td>
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
        <p><strong>Queue ETA:</strong> {td(fleet_eta.get('eta_human') or 'unknown')} ({td(fleet_eta.get('eta_at'))}) across {td(fleet_eta.get('remaining_slices'))} remaining slices.</p>
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
