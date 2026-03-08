import asyncio
import contextlib
import datetime as dt
import hashlib
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
}

DEFAULT_SPIDER = {
    "escalate_to_complex_after_failures": 1,
    "classification_mode": "heuristic",
    "tier_preferences": {
        "trivial": {
            "models": ["gpt-5-nano", "gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "none",
            "estimated_output_tokens": 512,
        },
        "standard": {
            "models": ["gpt-5-mini", "gpt-5.4"],
            "reasoning_effort": "low",
            "estimated_output_tokens": 2048,
        },
        "complex": {
            "models": ["gpt-5.4"],
            "reasoning_effort": "medium",
            "estimated_output_tokens": 4096,
        },
    },
    "trivial_keywords": [
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
    "complex_keywords": [
        "compile recovery",
        "contract hardening",
        "structured explain",
        "runtime",
        "rulepack",
        "determinism",
        "backend primitives",
        "identity",
        "registry",
        "publication foundation",
        "relay",
        "runtime bundle",
        "orchestration",
        "clean-room",
        "generated asset",
        "api hardening",
        "ai gateway",
        "session shell",
        "gm board",
        "spider feed",
        "foundation",
        "parser",
        "rulesets",
    ],
    "token_alliance_window_hours": 24,
}

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
- selected tier: {tier}
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
    fleet["spider"] = deep_merge(DEFAULT_SPIDER, fleet.get("spider") or {})
    price_table = deep_merge(DEFAULT_PRICE_TABLE, (fleet["spider"].get("price_table") or {}))
    fleet["spider"]["price_table"] = price_table
    fleet["accounts"] = accounts_cfg.get("accounts", {}) or {}

    for project in fleet["projects"]:
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("verify_cmd", "")
        project.setdefault("design_doc", "")
        project.setdefault("accounts", [])
        project["queue"] = apply_queue_overlay(project, list(project.get("queue") or []))
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
            row = conn.execute("SELECT queue_index, queue_json FROM projects WHERE id=?", (project["id"],)).fetchone()
            existing_index = row["queue_index"] if row else 0
            existing_queue = json.loads(row["queue_json"]) if row and row["queue_json"] else []
            new_queue = project.get("queue", [])
            if existing_queue == new_queue:
                queue_index = existing_index
            else:
                queue_index = min(existing_index, len(new_queue))
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


def current_slice(project_row: sqlite3.Row) -> Optional[str]:
    queue = json.loads(project_row["queue_json"] or "[]")
    idx = project_row["queue_index"]
    if 0 <= idx < len(queue):
        return queue[idx]
    return None


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


def build_prompt(project_cfg: Dict[str, Any], slice_name: str, decision: Dict[str, Any], feedback_files: List[pathlib.Path]) -> str:
    repo = pathlib.Path(project_cfg["path"])
    instructions = []
    for rel in ["instructions.md", ".agent-memory.md", "AGENT_MEMORY.md", "audit.md"]:
        path = repo / rel
        if path.exists():
            instructions.append(f"- {rel}")
    design_doc = project_cfg.get("design_doc", "")
    if design_doc:
        design_path = pathlib.Path(design_doc)
        instructions.append(f"- {design_doc if design_path.is_absolute() else design_path.name}")
    for path in studio_published_files(project_cfg):
        instructions.append(f"- {path.relative_to(repo).as_posix()}")
    queue_overlay = studio_published_root(project_cfg) / "QUEUE.generated.yaml"
    if queue_overlay.exists():
        instructions.append(f"- {queue_overlay.relative_to(repo).as_posix()}")
    instructions.extend(["- AGENTS.md if present", "- unread feedback files in feedback/, oldest first"])

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
    design = project_cfg.get("design_doc", "")
    total = len(slice_name) + len(project_cfg.get("id", "")) + len(project_cfg.get("path", "")) + len(design)
    total += 800
    for path in feedback_files + studio_published_files(project_cfg):
        try:
            total += len(path.read_text(encoding="utf-8"))
        except Exception:
            total += 200
    queue_overlay = studio_published_root(project_cfg) / "QUEUE.generated.yaml"
    if queue_overlay.exists():
        try:
            total += len(queue_overlay.read_text(encoding="utf-8"))
        except Exception:
            total += 200
    return total


def classify_tier(config: Dict[str, Any], project_cfg: Dict[str, Any], project_row: sqlite3.Row, slice_name: str, feedback_files: List[pathlib.Path]) -> Dict[str, Any]:
    spider = project_cfg.get("spider") or config.get("spider") or DEFAULT_SPIDER
    slice_text = f"{project_cfg.get('id', '')} {slice_name}".lower()
    prompt_chars = estimate_prompt_chars(project_cfg, slice_name, feedback_files)
    failures = int(project_row["consecutive_failures"] or 0)
    reason_parts: List[str] = []
    tier = "standard"

    trivial_hit = any(keyword in slice_text for keyword in spider.get("trivial_keywords", []))
    complex_hit = any(keyword in slice_text for keyword in spider.get("complex_keywords", []))
    code_change_hit = any(keyword in slice_text for keyword in ["fix", "implement", "integrat", "build", "compile", "hardening", "foundation", "runtime", "wire", "orchestration"])

    if complex_hit:
        tier = "complex"
        reason_parts.append("slice matches complex keyword policy")
    elif trivial_hit and not code_change_hit:
        tier = "trivial"
        reason_parts.append("slice matches trivial keyword policy")
    else:
        tier = "standard"
        reason_parts.append("default coding tier")

    if len(feedback_files) >= 2 and tier == "trivial":
        tier = "standard"
        reason_parts.append("multiple unread feedback files raise coordination cost")
    elif len(feedback_files) >= 4:
        tier = "complex"
        reason_parts.append("large feedback backlog escalates complexity")

    if prompt_chars > 24000 and tier == "trivial":
        tier = "standard"
        reason_parts.append("large prompt estimate escalates trivial tier")
    if prompt_chars > 48000:
        tier = "complex"
        reason_parts.append("large prompt estimate escalates complexity")

    escalate_after = int(spider.get("escalate_to_complex_after_failures", 1))
    if failures >= escalate_after:
        tier = "complex"
        reason_parts.append(f"previous failure count {failures} triggers complex tier")

    tier_prefs = spider.get("tier_preferences", {}).get(tier, {})
    models = list(tier_prefs.get("models") or [])
    reasoning_effort = str(tier_prefs.get("reasoning_effort", "low"))
    est_prompt_tokens = max(256, int(prompt_chars / 4))
    est_output_tokens = int(tier_prefs.get("estimated_output_tokens", 1024))

    return {
        "tier": tier,
        "model_preferences": models,
        "reasoning_effort": reasoning_effort,
        "reason": "; ".join(reason_parts),
        "estimated_prompt_chars": prompt_chars,
        "estimated_input_tokens": est_prompt_tokens,
        "estimated_output_tokens": est_output_tokens,
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


def pick_account_and_model(config: Dict[str, Any], project_cfg: Dict[str, Any], decision: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    aliases = project_cfg.get("accounts") or []
    if not aliases:
        return None, None, "project has no configured accounts"
    price_table = config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE
    now = utc_now()
    wanted_models = list(decision["model_preferences"])
    candidates: List[Tuple[dt.datetime, str, str, str]] = []

    with db() as conn:
        for alias in aliases:
            row = conn.execute("SELECT * FROM accounts WHERE alias=?", (alias,)).fetchone()
            if not row:
                continue

            backoff_until = parse_iso(row["backoff_until"])
            if backoff_until and backoff_until > now:
                continue

            active = active_run_count_for_account(alias)
            if active >= int(row["max_parallel_runs"] or 1):
                continue

            auth_kind = row["auth_kind"]
            if auth_kind == "api_key":
                if not has_api_key(row):
                    continue
            else:
                auth_json_file = pathlib.Path(row["auth_json_file"] or "")
                if not auth_json_file.exists():
                    continue

            allowed = json.loads(row["allowed_models_json"] or "[]")
            if allowed:
                available_models = [model for model in wanted_models if model in allowed]
            else:
                available_models = wanted_models
            if not available_models:
                continue

            chosen_model = available_models[0]
            est_cost = estimate_cost_usd_for_model(
                price_table,
                chosen_model,
                int(decision["estimated_input_tokens"]),
                0,
                int(decision["estimated_output_tokens"]),
            ) or 0.0

            day_usage = usage_for_account(alias, "day")
            if row["daily_budget_usd"] is not None and (float(day_usage["cost"]) + est_cost) > float(row["daily_budget_usd"]):
                continue

            month_usage = usage_for_account(alias, "month")
            if row["monthly_budget_usd"] is not None and (float(month_usage["cost"]) + est_cost) > float(row["monthly_budget_usd"]):
                continue

            last_used = parse_iso(row["last_used_at"]) or dt.datetime.fromtimestamp(0, tz=UTC)
            candidates.append((last_used, alias, chosen_model, f"fits tier {decision['tier']} with estimated cost ${est_cost:.4f}"))

    if not candidates:
        return None, None, "no account available after filtering by auth, backoff, model allowlist, or budget"
    candidates.sort(key=lambda item: item[0])
    _, alias, model, why = candidates[0]
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
    feedback_files = unread_feedback_files(project_cfg)
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
                next_status = "complete" if idx >= len(queue) else "idle"
                next_slice = None if next_status == "complete" else queue[idx]
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

            for row in projects:
                project_id = row["id"]
                if project_id in state.tasks:
                    continue

                queue = json.loads(row["queue_json"] or "[]")
                idx = int(row["queue_index"])
                if idx >= len(queue):
                    update_project_status(
                        project_id,
                        status="complete",
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
                    continue

                cooldown_until = parse_iso(row["cooldown_until"])
                if cooldown_until and cooldown_until > now:
                    continue

                if running_count >= max_parallel:
                    break

                project_cfg = get_project_cfg(config, project_id)
                slice_name = queue[idx]
                feedback_files = unread_feedback_files(project_cfg)
                decision = classify_tier(config, project_cfg, row, slice_name, feedback_files)
                alias, selected_model, selection_note = pick_account_and_model(config, project_cfg, decision)

                if not alias or not selected_model:
                    update_project_status(
                        project_id,
                        status="awaiting_account",
                        current_slice=slice_name,
                        active_run_id=None,
                        cooldown_until=None,
                        last_run_at=parse_iso(row["last_run_at"]),
                        last_error=selection_note,
                        consecutive_failures=row["consecutive_failures"],
                        spider_tier=decision["tier"],
                        spider_model=None,
                        spider_reason=decision["reason"],
                    )
                    continue

                task = asyncio.create_task(
                    execute_project_slice(config, project_cfg, row, slice_name, decision, alias, selected_model, selection_note)
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
    with db() as conn:
        projects = [dict(row) for row in conn.execute("SELECT * FROM projects ORDER BY id")]
        accounts = [dict(row) for row in conn.execute("SELECT * FROM accounts ORDER BY alias")]
        recent_runs = [dict(row) for row in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 50")]
        recent_decisions = [dict(row) for row in conn.execute("SELECT * FROM spider_decisions ORDER BY id DESC LIMIT 50")]
    for project in projects:
        project["queue"] = json.loads(project.pop("queue_json") or "[]")
        project["agent_state"] = read_state_file(project["path"], project["state_file"] or ".agent-state.json")
        project["current_queue_item"] = project["queue"][project["queue_index"]] if project["queue_index"] < len(project["queue"]) else None
    for account in accounts:
        account["allowed_models"] = json.loads(account.pop("allowed_models_json") or "[]")
        account["daily_usage"] = usage_for_account(account["alias"], "day")
        account["monthly_usage"] = usage_for_account(account["alias"], "month")
        account["active_runs"] = active_run_count_for_account(account["alias"])
    return {
        "config": {
            "policies": config.get("policies", {}),
            "spider": config.get("spider", {}),
            "project_count": len(config.get("projects", [])),
            "account_count": len(config.get("accounts", {})),
        },
        "projects": projects,
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

    def td(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    project_rows = []
    for p in status["projects"]:
        heartbeat = (p.get("agent_state") or {}).get("updated_at_utc", "")
        project_rows.append(
            f"""
            <tr>
              <td>{td(p['id'])}</td>
              <td>{td(p.get('status'))}</td>
              <td>{td(p.get('current_queue_item'))}</td>
              <td>{p['queue_index'] + 1} / {len(p['queue'])}</td>
              <td>{td(p.get('spider_tier'))}</td>
              <td>{td(p.get('spider_model'))}</td>
              <td>{td(p.get('spider_reason'))}</td>
              <td>{td(p.get('last_error'))}</td>
              <td>{td(p.get('cooldown_until'))}</td>
              <td>{td(heartbeat)}</td>
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
        <p><a href="/studio">Open Studio</a></p>
        <p>Cloudflare target from a container attached to the fleet network: <code>http://fleet-dashboard:{APP_PORT}</code></p>
        <p class="muted">Token alliance window starts at {td(alliance.get('window_start'))}.</p>

        <h2>Projects</h2>
        <table>
          <thead>
            <tr>
              <th>Project</th><th>Status</th><th>Current slice</th><th>Progress</th><th>Spider tier</th><th>Spider model</th><th>Spider reason</th><th>Last error</th><th>Cooldown</th><th>Repo heartbeat</th>
            </tr>
          </thead>
          <tbody>
            {''.join(project_rows) or '<tr><td colspan="10">No projects configured.</td></tr>'}
          </tbody>
        </table>

        <h2>Accounts</h2>
        <table>
          <thead>
            <tr>
              <th>Alias</th><th>Auth</th><th>Allowed models</th><th>Active</th><th>Day cost</th><th>Month cost</th><th>Day budget</th><th>Month budget</th><th>Backoff</th><th>Last error</th>
            </tr>
          </thead>
          <tbody>
            {''.join(account_rows) or '<tr><td colspan="10">No accounts configured.</td></tr>'}
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
              <th>ID</th><th>Project</th><th>Slice</th><th>Tier</th><th>Model</th><th>Account</th><th>Reason</th><th>At</th>
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
              <th>ID</th><th>Project</th><th>Account</th><th>Slice</th><th>Model</th><th>Tier</th><th>Status</th><th>Input</th><th>Output</th><th>Cost</th><th>Started</th><th>Finished</th><th>Log</th><th>Final</th>
            </tr>
          </thead>
          <tbody>
            {''.join(run_rows) or '<tr><td colspan="14">No runs yet.</td></tr>'}
          </tbody>
        </table>
      </body>
    </html>
    """
