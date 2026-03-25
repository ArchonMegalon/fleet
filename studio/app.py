import asyncio
import contextlib
import datetime as dt
import hashlib
import hmac
import html
import json
import os
import pathlib
import re
import sqlite3
import traceback
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml
try:
    from fastapi import FastAPI, Form, HTTPException, Request
except ImportError:  # pragma: no cover - test stubs may omit Form
    from fastapi import FastAPI, HTTPException, Request

    def Form(*_args, **_kwargs):
        return None

from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8091"))
APP_TITLE = "Codex Fleet Studio"

DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", "/var/lib/codex-fleet/fleet.db"))
LOG_DIR = pathlib.Path(os.environ.get("FLEET_LOG_DIR", "/var/lib/codex-fleet/studio-logs"))
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
ACCOUNTS_PATH = pathlib.Path(os.environ.get("FLEET_ACCOUNTS_PATH", "/app/config/accounts.yaml"))
POLICIES_PATH = CONFIG_PATH.with_name("policies.yaml")
ROUTING_PATH = CONFIG_PATH.with_name("routing.yaml")
GROUPS_PATH = CONFIG_PATH.with_name("groups.yaml")
PROJECTS_DIR = CONFIG_PATH.parent / "projects"
PROJECT_INDEX_PATH = PROJECTS_DIR / "_index.yaml"
CODEX_HOME_ROOT = pathlib.Path(os.environ.get("FLEET_CODEX_HOME_ROOT", "/var/lib/codex-fleet/codex-homes"))
GROUP_ROOT = pathlib.Path(os.environ.get("FLEET_GROUP_ROOT", str(DB_PATH.parent / "groups")))

STUDIO_DIRNAME = ".codex-studio"
STUDIO_PUBLISHED_DIRNAME = f"{STUDIO_DIRNAME}/published"
STUDIO_DRAFTS_DIRNAME = f"{STUDIO_DIRNAME}/drafts"
ALLOWED_STUDIO_FILES = {
    "VISION.md",
    "ROADMAP.md",
    "ARCHITECTURE.md",
    "runtime-instructions.generated.md",
    "QUEUE.generated.yaml",
    "WORKPACKAGES.generated.yaml",
    "STATUS_PLANE.generated.yaml",
    "SUPPORT_CASE_PACKETS.generated.json",
    "PROGRESS_REPORT.generated.json",
    "PROGRESS_HISTORY.generated.json",
    "GROUP_BLOCKERS.md",
    "CONTRACT_SETS.yaml",
    "PROGRAM_MILESTONES.generated.yaml",
    "SESSION_EVENTS_VNEXT.md",
    "DTO_COMPATIBILITY_MATRIX.md",
}
DESIGN_MIRROR_FILES = [
    ".codex-design/product/README.md",
    ".codex-design/product/LEAD_DESIGNER_OPERATING_MODEL.md",
    ".codex-design/product/PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md",
    ".codex-design/product/PRODUCT_HEALTH_SCORECARD.yaml",
    ".codex-design/product/VISION.md",
    ".codex-design/product/ARCHITECTURE.md",
    ".codex-design/product/PUBLIC_DOWNLOADS_POLICY.md",
    ".codex-design/product/DESKTOP_AUTO_UPDATE_SYSTEM.md",
    ".codex-design/product/PUBLIC_AUTO_UPDATE_POLICY.md",
    ".codex-design/product/FEEDBACK_AND_CRASH_REPORTING_SYSTEM.md",
    ".codex-design/product/FEEDBACK_AND_SIGNAL_OODA_LOOP.md",
    ".codex-design/product/FEEDBACK_AND_CRASH_STATUS_MODEL.md",
    ".codex-design/product/PROGRAM_MILESTONES.yaml",
    ".codex-design/product/CONTRACT_SETS.yaml",
    ".codex-design/product/GROUP_BLOCKERS.md",
    ".codex-design/product/OWNERSHIP_MATRIX.md",
    ".codex-design/repo/IMPLEMENTATION_SCOPE.md",
    ".codex-design/review/REVIEW_CONTEXT.md",
]
DESIGN_COMPILE_REQUIRED_FILES = [
    ".codex-design/product/VISION.md",
    ".codex-design/product/ARCHITECTURE.md",
    ".codex-design/repo/IMPLEMENTATION_SCOPE.md",
    ".codex-design/review/REVIEW_CONTEXT.md",
]

DEFAULT_PRICE_TABLE = {
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5.3-codex": {"input": 1.75, "cached_input": 0.175, "output": 14.00},
}
CHATGPT_STANDARD_MODEL = "gpt-5.3-codex"
SPARK_MODEL = "gpt-5.3-codex-spark"
CHATGPT_AUTH_KINDS = {"chatgpt_auth_json", "auth_json"}
CHATGPT_SUPPORTED_MODELS = {CHATGPT_STANDARD_MODEL, SPARK_MODEL}
EA_AUTH_KIND = "ea"

DEFAULT_STUDIO = {
    "max_parallel_runs": 1,
    "default_accounts": [],
    "session_message_window": 8,
    "publish_feedback_note": True,
    "autonomy": {
        "enabled": False,
        "poll_seconds": 60,
        "auto_publish_recommended": True,
        "roles": {
            "designer": {
                "enabled": False,
                "target_type": "fleet",
                "target_id": "fleet",
                "interval_seconds": 1800,
                "min_interval_seconds": 600,
                "title": "Autonomous design contradiction sweep",
            },
            "product_governor": {
                "enabled": False,
                "target_type": "fleet",
                "target_id": "fleet",
                "interval_seconds": 600,
                "min_interval_seconds": 300,
                "title": "Autonomous product pulse and reroute check",
            },
        },
    },
    "roles": {
        "designer": {
            "models": [CHATGPT_STANDARD_MODEL, "gpt-5-mini"],
            "reasoning_effort": "medium",
            "sandbox": "danger-full-access",
            "approval_policy": "never",
            "exec_timeout_seconds": 1800,
            "skip_git_repo_check": True,
        },
        "product_governor": {
            "models": [CHATGPT_STANDARD_MODEL, "gpt-5-mini"],
            "reasoning_effort": "medium",
            "sandbox": "danger-full-access",
            "approval_policy": "never",
            "exec_timeout_seconds": 1800,
            "skip_git_repo_check": True,
        },
        "project_manager": {
            "models": ["gpt-5-mini", CHATGPT_STANDARD_MODEL],
            "reasoning_effort": "low",
            "sandbox": "danger-full-access",
            "approval_policy": "never",
            "exec_timeout_seconds": 1500,
            "skip_git_repo_check": True,
        },
        "architect": {
            "models": [CHATGPT_STANDARD_MODEL, "gpt-5-mini"],
            "reasoning_effort": "medium",
            "sandbox": "danger-full-access",
            "approval_policy": "never",
            "exec_timeout_seconds": 1800,
            "skip_git_repo_check": True,
        },
    },
}
DESIRED_STATE_SCHEMA_VERSION = "2026-03-10.v1"
VALID_LIFECYCLE_STATES = {"planned", "scaffold", "dispatchable", "live", "signoff_only"}
COMPILE_MANIFEST_FILENAME = "compile.manifest.json"
DEFAULT_COMPILE_FRESHNESS_HOURS = {
    "planned": 720,
    "scaffold": 336,
    "dispatchable": 168,
    "live": 168,
    "signoff_only": 720,
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
WORKLIST_CHECKLIST_RE = re.compile(
    r"^\s*[-*]\s+\[(?P<status>[^\]]+)\]\s+(?:(?P<task_id>[A-Za-z0-9._-]+)\s+)?(?P<task>.+?)\s*$"
)

DEFAULT_SINGLETON_GROUP_ROLES = ["auditor", "project_manager"]
OPERATOR_AUTH_REQUIRED = str(os.environ.get("FLEET_OPERATOR_AUTH_REQUIRED", "false") or "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
OPERATOR_PASSWORD = str(os.environ.get("FLEET_OPERATOR_PASSWORD", "") or "")
OPERATOR_COOKIE_NAME = str(os.environ.get("FLEET_OPERATOR_COOKIE_NAME", "fleet_operator_session") or "fleet_operator_session").strip() or "fleet_operator_session"

ROLE_LABELS = {
    "designer": "Designer",
    "product_governor": "Product Governor",
    "project_manager": "Project Manager",
    "architect": "Architect",
    "program_manager": "Program Manager",
    "contract_steward": "Contract Steward",
    "auditor": "Auditor",
}

ROLE_ALIASES = {
    "operator": "product_governor",
    "product-governor": "product_governor",
    "governor": "product_governor",
    "lead_designer": "designer",
    "lead-designer": "designer",
}

CONTROL_DECISION_PRIMARY_LANES = [
    "code",
    "docs",
    "queue",
    "support",
    "policy",
    "canon",
    "release",
    "defer",
    "mixed",
]

CONTROL_DECISION_CHANGE_CLASSES = [
    "none",
    "type_a",
    "type_b",
    "type_c",
    "type_d",
    "type_e",
    "type_f",
    "type_g",
]

ROLE_READ_FIRST_FILES = {
    "designer": [
        ".codex-design/product/LEAD_DESIGNER_OPERATING_MODEL.md",
        ".codex-design/product/OWNERSHIP_MATRIX.md",
        ".codex-design/product/CONTRACT_SETS.yaml",
        ".codex-design/product/PROGRAM_MILESTONES.yaml",
        ".codex-design/product/GROUP_BLOCKERS.md",
        ".codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
    ],
    "product_governor": [
        ".codex-design/product/PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md",
        ".codex-design/product/PRODUCT_HEALTH_SCORECARD.yaml",
        ".codex-design/product/FEEDBACK_AND_SIGNAL_OODA_LOOP.md",
        ".codex-design/product/FEEDBACK_AND_CRASH_STATUS_MODEL.md",
        ".codex-studio/published/STATUS_PLANE.generated.yaml",
        ".codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
        ".codex-studio/published/PROGRESS_REPORT.generated.json",
    ],
}

ROLE_AUTONOMY_TRIGGER_FILES = {
    "designer": [
        ".codex-design/product/LEAD_DESIGNER_OPERATING_MODEL.md",
        ".codex-design/product/OWNERSHIP_MATRIX.md",
        ".codex-design/product/CONTRACT_SETS.yaml",
        ".codex-design/product/PROGRAM_MILESTONES.yaml",
        ".codex-design/product/GROUP_BLOCKERS.md",
        ".codex-studio/published/STATUS_PLANE.generated.yaml",
        ".codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
    ],
    "product_governor": [
        ".codex-design/product/PRODUCT_GOVERNOR_AND_AUTOPILOT_LOOP.md",
        ".codex-design/product/PRODUCT_HEALTH_SCORECARD.yaml",
        ".codex-design/product/FEEDBACK_AND_SIGNAL_OODA_LOOP.md",
        ".codex-design/product/FEEDBACK_AND_CRASH_STATUS_MODEL.md",
        ".codex-studio/published/STATUS_PLANE.generated.yaml",
        ".codex-studio/published/SUPPORT_CASE_PACKETS.generated.json",
        ".codex-studio/published/PROGRESS_REPORT.generated.json",
    ],
}

if OPERATOR_AUTH_REQUIRED and not OPERATOR_PASSWORD:
    raise RuntimeError("FLEET_OPERATOR_PASSWORD is required when FLEET_OPERATOR_AUTH_REQUIRED=true")

STUDIO_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "assistant_reply": {"type": "string"},
        "session_summary": {"type": "string"},
        "proposal": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "recommended_publish_mode": {
                    "type": "string",
                    "enum": ["hold", "publish_artifacts", "publish_artifacts_and_feedback"],
                },
                "files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                },
                "targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "target_type": {
                                "type": "string",
                                "enum": ["project", "group", "fleet"],
                            },
                            "target_id": {"type": "string"},
                            "files": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "content": {"type": "string"},
                                    },
                                    "required": ["path", "content"],
                                    "additionalProperties": False,
                                },
                            },
                            "feedback_note": {"type": "string"},
                        },
                        "required": ["target_type", "target_id", "files", "feedback_note"],
                        "additionalProperties": False,
                    },
                },
                "feedback_note": {"type": "string"},
                "coding_tier_hint": {
                    "type": "string",
                    "enum": ["nano", "mini", "full", "mixed"],
                },
                "routing_notes": {"type": "string"},
                "control_decision": {
                    "type": "object",
                    "properties": {
                        "primary_lane": {
                            "type": "string",
                            "enum": CONTROL_DECISION_PRIMARY_LANES,
                        },
                        "change_class": {
                            "type": "string",
                            "enum": CONTROL_DECISION_CHANGE_CLASSES,
                        },
                        "reason": {"type": "string"},
                        "exit_condition": {"type": "string"},
                        "affected_canon_files": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "primary_lane",
                        "change_class",
                        "reason",
                        "exit_condition",
                        "affected_canon_files",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": [
                "title",
                "summary",
                "recommended_publish_mode",
                "files",
                "feedback_note",
                "coding_tier_hint",
                "routing_notes",
                "control_decision",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["assistant_reply", "session_summary", "proposal"],
    "additionalProperties": False,
}

STUDIO_PROMPT_TEMPLATE = """
You are the {role_label} inside the Codex Fleet Studio for {target_type} `{target_id}`.
You are advising the admin operator about vision, sequencing, instruction quality, and worker direction.
This is a design-control turn, not a coding-worker turn.
Do not modify files directly. Return structured JSON only.

Read from disk before you answer:
{context_files}

Role-priority files:
{role_priority_files}

Current runtime brief:
{role_runtime_brief}

Project constraints:
- preserve architectural boundaries already documented in repo instructions and design docs
- discuss tradeoffs, scope, and direction with the admin user
- when useful, draft publishable artifacts instead of vague advice
- any draft file path must be relative to `{published_dir}`
- preferred publishable filenames are: VISION.md, ROADMAP.md, ARCHITECTURE.md, runtime-instructions.generated.md, QUEUE.generated.yaml
- group-aware filenames may also include: GROUP_BLOCKERS.md, CONTRACT_SETS.yaml, PROGRAM_MILESTONES.generated.yaml, SESSION_EVENTS_VNEXT.md, DTO_COMPATIBILITY_MATRIX.md
- queue overlays should use YAML with `mode: append | prepend | replace` and an `items:` list
- when the request spans multiple repos or scopes, use `proposal.targets` to publish a coordinated multi-target proposal instead of forcing everything into one target
- when proposing review-gated work, default to GitHub PR review via `@codex review`; local review is fallback-only
- if no file update is needed, return an empty files array

Running summary:
{session_summary}

Recent conversation:
{conversation}

Role guidance:
{role_guidance_block}

Return JSON that matches the schema exactly.
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
    GROUP_ROOT.mkdir(parents=True, exist_ok=True)


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
                spark_backoff_until TEXT,
                last_used_at TEXT,
                last_error TEXT,
                spark_last_error TEXT,
                health_state TEXT NOT NULL DEFAULT 'ready',
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
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS studio_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT 'project',
                target_id TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL,
                title TEXT NOT NULL,
                origin_type TEXT NOT NULL DEFAULT 'admin',
                origin_name TEXT NOT NULL DEFAULT 'admin',
                automation_fingerprint TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'idle',
                summary TEXT NOT NULL DEFAULT '',
                active_run_id INTEGER,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS studio_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                actor_type TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES studio_sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS studio_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                run_id INTEGER,
                project_id TEXT NOT NULL,
                target_type TEXT NOT NULL DEFAULT 'project',
                target_id TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                draft_dir TEXT,
                published_dir TEXT,
                published_feedback_rel TEXT,
                published_targets_json TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                published_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES studio_sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS studio_publish_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                source_target_type TEXT NOT NULL,
                source_target_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                published_targets_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(proposal_id) REFERENCES studio_proposals(id) ON DELETE CASCADE,
                FOREIGN KEY(session_id) REFERENCES studio_sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS studio_automation_state (
                role TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                trigger_fingerprint TEXT NOT NULL DEFAULT '',
                last_session_id INTEGER,
                last_proposal_id INTEGER,
                last_published_proposal_id INTEGER,
                last_run_at TEXT,
                last_publish_at TEXT,
                last_status TEXT NOT NULL DEFAULT '',
                last_message TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(role, target_type, target_id)
            );
            """
        )
        migrate_db(conn)


def migrate_db(conn: sqlite3.Connection) -> None:
    account_cols = {row["name"] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "api_key_env" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN api_key_env TEXT")
    if "spark_backoff_until" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN spark_backoff_until TEXT")
    if "spark_last_error" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN spark_last_error TEXT")
    if "health_state" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN health_state TEXT NOT NULL DEFAULT 'ready'")

    run_cols = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "job_kind" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN job_kind TEXT NOT NULL DEFAULT 'coding'")

    session_cols = {row["name"] for row in conn.execute("PRAGMA table_info(studio_sessions)").fetchall()}
    if "target_type" not in session_cols:
        conn.execute("ALTER TABLE studio_sessions ADD COLUMN target_type TEXT NOT NULL DEFAULT 'project'")
    if "target_id" not in session_cols:
        conn.execute("ALTER TABLE studio_sessions ADD COLUMN target_id TEXT NOT NULL DEFAULT ''")
    if "origin_type" not in session_cols:
        conn.execute("ALTER TABLE studio_sessions ADD COLUMN origin_type TEXT NOT NULL DEFAULT 'admin'")
    if "origin_name" not in session_cols:
        conn.execute("ALTER TABLE studio_sessions ADD COLUMN origin_name TEXT NOT NULL DEFAULT 'admin'")
    if "automation_fingerprint" not in session_cols:
        conn.execute("ALTER TABLE studio_sessions ADD COLUMN automation_fingerprint TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE studio_sessions SET target_id=project_id WHERE target_id='' OR target_id IS NULL")

    proposal_cols = {row["name"] for row in conn.execute("PRAGMA table_info(studio_proposals)").fetchall()}
    if "target_type" not in proposal_cols:
        conn.execute("ALTER TABLE studio_proposals ADD COLUMN target_type TEXT NOT NULL DEFAULT 'project'")
    if "target_id" not in proposal_cols:
        conn.execute("ALTER TABLE studio_proposals ADD COLUMN target_id TEXT NOT NULL DEFAULT ''")
    if "published_targets_json" not in proposal_cols:
        conn.execute("ALTER TABLE studio_proposals ADD COLUMN published_targets_json TEXT")
    conn.execute("UPDATE studio_proposals SET target_id=project_id WHERE target_id='' OR target_id IS NULL")

    conn.execute(
        """
        INSERT INTO studio_publish_events(
            proposal_id,
            session_id,
            source_target_type,
            source_target_id,
            mode,
            published_targets_json,
            created_at
        )
        SELECT
            p.id,
            p.session_id,
            COALESCE(NULLIF(p.target_type, ''), 'project'),
            COALESCE(NULLIF(p.target_id, ''), p.project_id),
            'publish_artifacts_and_feedback',
            COALESCE(p.published_targets_json, '[]'),
            COALESCE(p.published_at, p.updated_at, p.created_at)
        FROM studio_proposals p
        WHERE p.status='published'
          AND NOT EXISTS (
              SELECT 1 FROM studio_publish_events e WHERE e.proposal_id = p.id
          )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_automation_state (
            role TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            trigger_fingerprint TEXT NOT NULL DEFAULT '',
            last_session_id INTEGER,
            last_proposal_id INTEGER,
            last_published_proposal_id INTEGER,
            last_run_at TEXT,
            last_publish_at TEXT,
            last_status TEXT NOT NULL DEFAULT '',
            last_message TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY(role, target_type, target_id)
        )
        """
    )


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json_object(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def file_sha256(path: pathlib.Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in (b or {}).items():
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def normalize_lifecycle_state(value: Any, default: str = "dispatchable") -> str:
    clean = str(value or "").strip().lower() or str(default or "dispatchable").strip().lower()
    return clean if clean in VALID_LIFECYCLE_STATES else str(default or "dispatchable").strip().lower()


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
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet.setdefault("policies", {})
    spider = fleet.get("spider") or {}
    spider["price_table"] = deep_merge(DEFAULT_PRICE_TABLE, spider.get("price_table") or {})
    fleet["spider"] = spider
    compile_cfg = fleet["policies"].setdefault("compile", {})
    compile_cfg["freshness_hours"] = {
        **DEFAULT_COMPILE_FRESHNESS_HOURS,
        **(compile_cfg.get("freshness_hours") or {}),
    }
    fleet["accounts"] = accounts_cfg.get("accounts", {}) or {}
    fleet["studio"] = deep_merge(DEFAULT_STUDIO, fleet.get("studio") or {})
    fleet["studio"]["roles"] = deep_merge(DEFAULT_STUDIO["roles"], (fleet["studio"].get("roles") or {}))
    fleet["project_groups"] = normalized_project_groups(fleet["projects"], fleet["project_groups"])
    for project in fleet["projects"]:
        project["lifecycle"] = normalize_lifecycle_state(project.get("lifecycle"), "dispatchable")
        project.setdefault("feedback_dir", "feedback")
        project.setdefault("state_file", ".agent-state.json")
        project.setdefault("design_doc", "")
        project.setdefault("accounts", [])
    for group in fleet["project_groups"]:
        group["lifecycle"] = normalize_lifecycle_state(group.get("lifecycle"), "live")
    return fleet


def studio_autonomy_specs(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    studio_cfg = config.get("studio", {}) or {}
    autonomy_cfg = studio_cfg.get("autonomy", {}) or {}
    if not bool(autonomy_cfg.get("enabled")):
        return []
    role_cfgs = dict(autonomy_cfg.get("roles") or {})
    specs: List[Dict[str, Any]] = []
    for raw_role, raw_spec in role_cfgs.items():
        role_name = normalize_studio_role_name(raw_role, (studio_cfg.get("roles") or {}))
        spec = dict(raw_spec or {})
        if not bool(spec.get("enabled")):
            continue
        specs.append(
            {
                "role": role_name,
                "target_type": str(spec.get("target_type") or "fleet").strip() or "fleet",
                "target_id": str(spec.get("target_id") or "fleet").strip() or "fleet",
                "interval_seconds": max(60, int(spec.get("interval_seconds") or 900)),
                "min_interval_seconds": max(30, int(spec.get("min_interval_seconds") or 300)),
                "title": str(spec.get("title") or f"Autonomous {role_name.replace('_', ' ')} pulse").strip(),
                "auto_publish_recommended": bool(
                    spec.get("auto_publish_recommended", autonomy_cfg.get("auto_publish_recommended", True))
                ),
            }
        )
    specs.sort(key=lambda item: (str(item["target_type"]), str(item["target_id"]), str(item["role"])))
    return specs


def studio_session_is_active(role_name: str, target_type: str, target_id: str) -> bool:
    with db() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM studio_sessions
            WHERE role=? AND target_type=? AND target_id=? AND status IN ('queued', 'awaiting_account', 'running')
            LIMIT 1
            """,
            (role_name, target_type, target_id),
        ).fetchone()
    return bool(row)


def studio_automation_state_row(role_name: str, target_type: str, target_id: str) -> Optional[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM studio_automation_state WHERE role=? AND target_type=? AND target_id=?",
            (role_name, target_type, target_id),
        ).fetchone()


def update_studio_automation_state(
    role_name: str,
    target_type: str,
    target_id: str,
    **fields: Any,
) -> None:
    existing = studio_automation_state_row(role_name, target_type, target_id)
    payload = {
        "trigger_fingerprint": str(
            fields["trigger_fingerprint"] if "trigger_fingerprint" in fields else (existing["trigger_fingerprint"] if existing else "")
        ),
        "last_session_id": fields["last_session_id"] if "last_session_id" in fields else (existing["last_session_id"] if existing else None),
        "last_proposal_id": fields["last_proposal_id"] if "last_proposal_id" in fields else (existing["last_proposal_id"] if existing else None),
        "last_published_proposal_id": fields["last_published_proposal_id"] if "last_published_proposal_id" in fields else (existing["last_published_proposal_id"] if existing else None),
        "last_run_at": fields["last_run_at"] if "last_run_at" in fields else (existing["last_run_at"] if existing else None),
        "last_publish_at": fields["last_publish_at"] if "last_publish_at" in fields else (existing["last_publish_at"] if existing else None),
        "last_status": str(fields["last_status"] if "last_status" in fields else (existing["last_status"] if existing else "")),
        "last_message": str(fields["last_message"] if "last_message" in fields else (existing["last_message"] if existing else "")),
        "updated_at": iso(utc_now()),
    }
    with db() as conn:
        conn.execute(
            """
            INSERT INTO studio_automation_state(
                role, target_type, target_id, trigger_fingerprint, last_session_id, last_proposal_id,
                last_published_proposal_id, last_run_at, last_publish_at, last_status, last_message, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(role, target_type, target_id) DO UPDATE SET
                trigger_fingerprint=excluded.trigger_fingerprint,
                last_session_id=excluded.last_session_id,
                last_proposal_id=excluded.last_proposal_id,
                last_published_proposal_id=excluded.last_published_proposal_id,
                last_run_at=excluded.last_run_at,
                last_publish_at=excluded.last_publish_at,
                last_status=excluded.last_status,
                last_message=excluded.last_message,
                updated_at=excluded.updated_at
            """,
            (
                role_name,
                target_type,
                target_id,
                payload["trigger_fingerprint"],
                payload["last_session_id"],
                payload["last_proposal_id"],
                payload["last_published_proposal_id"],
                payload["last_run_at"],
                payload["last_publish_at"],
                payload["last_status"],
                payload["last_message"],
                payload["updated_at"],
            ),
        )


def automation_open_incident_summary(limit: int = 12) -> List[Dict[str, Any]]:
    with db() as conn:
        tables = {
            str(row["name"])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "incidents" not in tables:
            return []
        rows = conn.execute(
            """
            SELECT scope_type, scope_id, incident_kind, severity, updated_at
            FROM incidents
            WHERE status='open'
            ORDER BY COALESCE(updated_at, '') DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "scope_type": str(row["scope_type"] or ""),
            "scope_id": str(row["scope_id"] or ""),
            "incident_kind": str(row["incident_kind"] or ""),
            "severity": str(row["severity"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }
        for row in rows
    ]


def automation_trigger_fingerprint(target_cfg: Dict[str, Any], role_name: str) -> Tuple[str, Dict[str, Any]]:
    if target_cfg["target_type"] == "group":
        payload = {
            "role": role_name,
            "target_type": target_cfg["target_type"],
            "target_id": target_cfg["target_id"],
            "member_projects": [
                {
                    "project_id": str(project_cfg.get("id") or "").strip(),
                    "files": {
                        label: file_sha256(path)
                        for label, path in project_trigger_paths(project_cfg, role_name)
                    },
                }
                for project_cfg in (target_cfg.get("project_cfgs") or [])
            ],
            "open_incidents": automation_open_incident_summary() if role_name == "product_governor" else [],
        }
    else:
        root = pathlib.Path(target_cfg["path"])
        files_payload: Dict[str, str] = {}
        for rel in ROLE_AUTONOMY_TRIGGER_FILES.get(role_name, []):
            files_payload[rel] = file_sha256(root / rel)
        payload = {
            "role": role_name,
            "target_type": target_cfg["target_type"],
            "target_id": target_cfg["target_id"],
            "files": files_payload,
            "open_incidents": automation_open_incident_summary() if role_name == "product_governor" else [],
        }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), payload


def studio_autonomy_should_queue(
    spec: Dict[str, Any],
    state_row: Optional[sqlite3.Row],
    *,
    now: dt.datetime,
    trigger_fingerprint: str,
) -> Tuple[bool, str]:
    if not state_row:
        return True, "first autonomous pulse"
    last_run_at = parse_iso(str(state_row["last_run_at"] or ""))
    last_fingerprint = str(state_row["trigger_fingerprint"] or "")
    if not last_run_at:
        return True, "no recorded autonomous run"
    elapsed = max(0, int((now - last_run_at).total_seconds()))
    if trigger_fingerprint != last_fingerprint and elapsed >= int(spec.get("min_interval_seconds") or 300):
        return True, "trigger inputs changed"
    if elapsed >= int(spec.get("interval_seconds") or 900):
        return True, "interval pulse due"
    return False, "not due"


def automation_message_for_role(spec: Dict[str, Any], reason: str, trigger_payload: Dict[str, Any]) -> str:
    role_name = str(spec.get("role") or "designer")
    if role_name == "product_governor":
        open_incidents = list(trigger_payload.get("open_incidents") or [])
        incident_text = f"{len(open_incidents)} open runtime incidents observed." if open_incidents else "No open runtime incidents observed."
        return (
            f"Autonomous product-governor pulse for {spec['target_type']}:{spec['target_id']}. "
            f"Trigger reason: {reason}. {incident_text} "
            "Review whole-product health, release readiness, blocker pressure, and public-promise drift. "
            "Route the next action into code, docs, queue, policy, canon, release, or defer, and publish automatically when the recommendation is not hold."
        )
    return (
        f"Autonomous designer pulse for {spec['target_type']}:{spec['target_id']}. "
        f"Trigger reason: {reason}. "
        "Review canon contradictions, missing seams, milestone or blocker drift, and public-story drift. "
        "Classify any canon change explicitly, name the affected files, and publish automatically when the recommendation is not hold."
    )


def sync_accounts_to_db(config: Dict[str, Any]) -> None:
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
                    health_state=CASE
                        WHEN excluded.health_state IN ('disabled', 'draining', 'exhausted') THEN excluded.health_state
                        WHEN accounts.health_state='auth_stale' THEN accounts.health_state
                        ELSE excluded.health_state
                    END,
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


def get_project_cfg(config: Dict[str, Any], project_id: str) -> Dict[str, Any]:
    for project in config.get("projects", []):
        if project["id"] == project_id:
            return project
    raise KeyError(project_id)


def get_group_cfg(config: Dict[str, Any], group_id: str) -> Dict[str, Any]:
    for group in config.get("project_groups", []):
        if str(group.get("id")) == group_id:
            return group
    raise KeyError(group_id)


def fleet_repo_root() -> pathlib.Path:
    return CONFIG_PATH.parent.parent


def project_repo_root(project_cfg: Dict[str, Any]) -> pathlib.Path:
    return pathlib.Path(project_cfg["path"])


def resolve_project_path(project_cfg: Dict[str, Any], source_path: str) -> pathlib.Path:
    path = pathlib.Path(str(source_path or "").strip())
    if path.is_absolute():
        return path
    return project_repo_root(project_cfg) / path


def project_design_doc_path(project_cfg: Dict[str, Any]) -> Optional[pathlib.Path]:
    design_doc = str(project_cfg.get("design_doc") or "").strip()
    if not design_doc:
        return None
    return resolve_project_path(project_cfg, design_doc)


def project_state_file_path(project_cfg: Dict[str, Any]) -> Optional[pathlib.Path]:
    state_file = str(project_cfg.get("state_file") or "").strip()
    if not state_file:
        return None
    return resolve_project_path(project_cfg, state_file)


def project_queue_source_paths(project_cfg: Dict[str, Any]) -> List[pathlib.Path]:
    items: List[pathlib.Path] = []
    seen: set[str] = set()
    for source_cfg in project_cfg.get("queue_sources") or []:
        if not isinstance(source_cfg, dict):
            continue
        raw_path = str(source_cfg.get("path") or "").strip()
        if not raw_path:
            continue
        path = resolve_project_path(project_cfg, raw_path)
        key = path.as_posix()
        if key in seen:
            continue
        items.append(path)
        seen.add(key)
    return items


def project_context_paths(project_cfg: Dict[str, Any]) -> List[pathlib.Path]:
    repo = project_repo_root(project_cfg)
    items: List[pathlib.Path] = []
    seen: set[str] = set()

    def add(path: Optional[pathlib.Path]) -> None:
        if path is None or not path.exists():
            return
        key = path.as_posix()
        if key in seen:
            return
        items.append(path)
        seen.add(key)

    for rel in ["instructions.md", ".agent-memory.md", "AGENT_MEMORY.md", "audit.md"]:
        add(repo / rel)
    add(project_design_doc_path(project_cfg))
    add(project_state_file_path(project_cfg))
    for path in project_queue_source_paths(project_cfg):
        add(path)
    for rel in DESIGN_MIRROR_FILES:
        add(repo / rel)
    return items


def project_path_label(project_cfg: Dict[str, Any], path: pathlib.Path) -> str:
    try:
        return path.relative_to(project_repo_root(project_cfg)).as_posix()
    except ValueError:
        return path.as_posix()


def project_trigger_paths(project_cfg: Dict[str, Any], role_name: str) -> List[Tuple[str, pathlib.Path]]:
    repo = project_repo_root(project_cfg)
    project_id = str(project_cfg.get("id") or "").strip() or "project"
    items: List[Tuple[str, pathlib.Path]] = []
    seen: set[str] = set()

    def add(label: str, path: Optional[pathlib.Path]) -> None:
        clean_label = str(label or "").strip()
        if path is None or not clean_label or clean_label in seen:
            return
        items.append((clean_label, path))
        seen.add(clean_label)

    for rel in ROLE_AUTONOMY_TRIGGER_FILES.get(role_name, []):
        add(f"{project_id}:{rel}", repo / rel)
    design_doc = project_design_doc_path(project_cfg)
    if design_doc is not None:
        add(f"{project_id}:design_doc:{project_path_label(project_cfg, design_doc)}", design_doc)
    state_file = project_state_file_path(project_cfg)
    if state_file is not None:
        add(f"{project_id}:state:{project_path_label(project_cfg, state_file)}", state_file)
    for path in project_queue_source_paths(project_cfg):
        add(f"{project_id}:queue_source:{project_path_label(project_cfg, path)}", path)
    return items


def target_root(target_cfg: Dict[str, Any]) -> pathlib.Path:
    if target_cfg["target_type"] == "project":
        return pathlib.Path(target_cfg["path"])
    if target_cfg["target_type"] == "group":
        return GROUP_ROOT / target_cfg["target_id"]
    return fleet_repo_root()


def studio_published_root(target_cfg: Dict[str, Any]) -> pathlib.Path:
    return target_root(target_cfg) / STUDIO_PUBLISHED_DIRNAME


def studio_drafts_root(target_cfg: Dict[str, Any]) -> pathlib.Path:
    return target_root(target_cfg) / STUDIO_DRAFTS_DIRNAME


def target_feedback_root(target_cfg: Dict[str, Any]) -> pathlib.Path:
    if target_cfg["target_type"] == "project":
        return pathlib.Path(target_cfg["path"]) / target_cfg.get("feedback_dir", "feedback")
    return target_root(target_cfg) / "feedback"


def studio_control_run_project_id(config: Dict[str, Any]) -> str:
    projects = config.get("projects") or []
    for project in projects:
        if str(project.get("id") or "").strip() == "fleet":
            return "fleet"
    if projects:
        return str(projects[0].get("id") or "").strip() or "fleet"
    return "fleet"


def resolve_target_cfg(config: Dict[str, Any], target_type: str, target_id: str) -> Dict[str, Any]:
    target_type = str(target_type or "project").strip() or "project"
    target_id = str(target_id or "").strip()
    if target_type == "project":
        project_cfg = get_project_cfg(config, target_id)
        return {
            "target_type": "project",
            "target_id": project_cfg["id"],
            "label": f"project:{project_cfg['id']}",
            "path": project_cfg["path"],
            "feedback_dir": project_cfg.get("feedback_dir", "feedback"),
            "design_doc": project_cfg.get("design_doc", ""),
            "accounts": project_cfg.get("accounts") or [],
            "project_cfg": project_cfg,
            "run_project_id": project_cfg["id"],
        }
    if target_type == "group":
        group_cfg = get_group_cfg(config, target_id)
        project_ids = [str(item).strip() for item in (group_cfg.get("projects") or []) if str(item).strip()]
        project_cfgs = [get_project_cfg(config, project_id) for project_id in project_ids]
        return {
            "target_type": "group",
            "target_id": str(group_cfg["id"]),
            "label": f"group:{group_cfg['id']}",
            "path": str(fleet_repo_root()),
            "feedback_dir": "feedback",
            "design_doc": "",
            "accounts": [],
            "group_cfg": group_cfg,
            "project_ids": project_ids,
            "project_cfgs": project_cfgs,
            # Group control work runs inside the Fleet repo and must attach to a real project row.
            "run_project_id": studio_control_run_project_id(config),
        }
    if target_type == "fleet":
        return {
            "target_type": "fleet",
            "target_id": target_id or "fleet",
            "label": f"fleet:{target_id or 'fleet'}",
            "path": str(fleet_repo_root()),
            "feedback_dir": "feedback",
            "design_doc": "",
            "accounts": [],
            # Fleet-wide control work also executes under the canonical Fleet project row.
            "run_project_id": studio_control_run_project_id(config),
        }
    raise KeyError(f"unsupported target type: {target_type}")


def normalize_studio_role_name(role_name: Any, available_roles: Optional[Dict[str, Any]] = None) -> str:
    clean = str(role_name or "").strip().replace("-", "_") or "designer"
    clean = ROLE_ALIASES.get(clean, clean)
    if available_roles is not None and clean not in available_roles:
        return "designer"
    return clean or "designer"


def existing_context_files(target_cfg: Dict[str, Any]) -> List[str]:
    repo = target_root(target_cfg)
    items: List[str] = []
    if target_cfg["target_type"] == "project":
        for rel in ["instructions.md", ".agent-memory.md", "AGENT_MEMORY.md", "audit.md"]:
            if (repo / rel).exists():
                items.append(rel)
        design_doc = target_cfg.get("design_doc") or ""
        if design_doc:
            design_path = pathlib.Path(design_doc)
            items.append(design_doc if design_path.is_absolute() else design_path.name)
        for rel in DESIGN_MIRROR_FILES:
            if (repo / rel).exists():
                items.append(rel)
    elif target_cfg["target_type"] == "group":
        member_projects = list(target_cfg.get("project_cfgs") or [])
        items.extend([
            "config/fleet.yaml",
            "config/program_milestones.yaml",
            f"group members: {', '.join(str(project.get('id') or '').strip() for project in member_projects if str(project.get('id') or '').strip())}",
            "shared Chummer feedback and published group artifacts when present",
        ])
        for project_cfg in member_projects:
            project_id = str(project_cfg.get("id") or "").strip() or "project"
            items.append(f"{project_id} repo: {project_repo_root(project_cfg)}")
            for path in project_context_paths(project_cfg):
                items.append(path.as_posix())
    else:
        items.extend([
            "config/fleet.yaml",
            "config/program_milestones.yaml",
            "feedback/*.md in the fleet repo when relevant",
            "admin, controller, studio, and auditor runtime files when relevant",
        ])
    for rel in sorted(ALLOWED_STUDIO_FILES):
        path = studio_published_root(target_cfg) / rel
        if path.exists():
            items.append(f"{STUDIO_PUBLISHED_DIRNAME}/{rel}")
    items.append("AGENTS.md if present")
    items.append("unread feedback files in feedback/, oldest first")
    return items


def fleet_status_plane_payload() -> Dict[str, Any]:
    return load_yaml(fleet_repo_root() / STUDIO_PUBLISHED_DIRNAME / "STATUS_PLANE.generated.yaml")


def fleet_progress_report_payload() -> Dict[str, Any]:
    return load_json_object(fleet_repo_root() / STUDIO_PUBLISHED_DIRNAME / "PROGRESS_REPORT.generated.json")


def fleet_support_case_packets_payload() -> Dict[str, Any]:
    path = fleet_repo_root() / STUDIO_PUBLISHED_DIRNAME / "SUPPORT_CASE_PACKETS.generated.json"
    return load_json_object(path) if path.exists() else {}


def _status_entry(items: Any, item_id: str) -> Dict[str, Any]:
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").strip() == item_id:
            return dict(item)
    return {}


def studio_role_priority_files(target_cfg: Dict[str, Any], role_name: str) -> List[str]:
    items = list(ROLE_READ_FIRST_FILES.get(role_name, []))
    design_doc = str(target_cfg.get("design_doc") or "").strip()
    if design_doc and role_name == "designer":
        items.insert(0, design_doc)
    if role_name == "designer" and target_cfg["target_type"] == "group":
        design_docs: List[str] = []
        for project_cfg in (target_cfg.get("project_cfgs") or []):
            path = project_design_doc_path(project_cfg)
            if path is not None:
                design_docs.append(path.as_posix())
        items = design_docs + items
    if role_name == "product_governor" and target_cfg["target_type"] in {"group", "fleet"}:
        items.append(".codex-design/product/GROUP_BLOCKERS.md")
    return items


def studio_role_runtime_brief(target_cfg: Dict[str, Any], role_name: str) -> str:
    status_payload = fleet_status_plane_payload()
    progress_payload = fleet_progress_report_payload()
    support_payload = fleet_support_case_packets_payload()
    lines: List[str] = []
    target_type = str(target_cfg.get("target_type") or "project")
    target_id = str(target_cfg.get("target_id") or "").strip()

    if target_type == "fleet":
        readiness = dict(status_payload.get("readiness_summary") or {})
        dispatch = dict(status_payload.get("dispatch_policy") or {})
        if readiness:
            counts = dict(readiness.get("counts") or {})
            count_bits = [f"{key}={value}" for key, value in counts.items() if value]
            if count_bits:
                lines.append(f"Readiness ladder: {', '.join(count_bits[:5])}.")
            lines.append(
                f"Warnings {int(readiness.get('warning_count') or 0)}; final-claim ready {int(readiness.get('final_claim_ready') or 0)}."
            )
        if dispatch:
            operator_only = ", ".join(
                str(item).strip() for item in (dispatch.get("operator_only_projects") or []) if str(item).strip()
            ) or "none"
            lines.append(
                "Dispatch posture: "
                f"{int(dispatch.get('participant_dispatch_canary_count') or 0)} participant canaries; "
                f"operator-only {operator_only}."
            )
    elif target_type == "group":
        group = _status_entry(status_payload.get("groups"), target_id)
        if group:
            lines.append(
                f"Group status: phase {str(group.get('phase') or 'unknown').strip()} · pressure {str(group.get('pressure_state') or 'unknown').strip()} · lifecycle {str(group.get('lifecycle') or 'unknown').strip()}."
            )
            lines.append(
                f"Deployment posture: {str(group.get('deployment_status') or group.get('deployment_access_posture') or 'undeclared').strip()}."
            )
        members = ", ".join(str(item).strip() for item in (target_cfg.get("project_ids") or []) if str(item).strip())
        if members:
            lines.append(f"Control-plane members: {members}.")
    else:
        project = _status_entry(status_payload.get("projects"), target_id)
        if project:
            lines.append(
                f"Project status: runtime {str(project.get('runtime_status') or 'unknown').strip()} · readiness {str(project.get('readiness_stage') or 'unknown').strip()} -> {str(project.get('readiness_terminal_stage') or 'unknown').strip()}."
            )
            lines.append(
                f"Deployment posture: {str(project.get('deployment_status') or 'undeclared').strip()} / {str(project.get('deployment_promotion_stage') or 'undeclared').strip()}."
            )

    if progress_payload:
        percent = progress_payload.get("overall_progress_percent")
        phase = str(progress_payload.get("phase_label") or "").strip()
        eta_low = progress_payload.get("next_checkpoint_eta_weeks_low")
        eta_high = progress_payload.get("next_checkpoint_eta_weeks_high")
        if percent is not None or phase or eta_low is not None or eta_high is not None:
            percent_text = f"{percent}%" if percent is not None else "unknown progress"
            phase_text = phase or "unknown phase"
            if eta_low is not None and eta_high is not None:
                eta_text = f"{eta_low}-{eta_high} weeks"
            elif eta_low is not None:
                eta_text = f"{eta_low}+ weeks"
            else:
                eta_text = "unknown ETA band"
            lines.append(f"Public progress contract: {percent_text} · {phase_text} · next checkpoint {eta_text}.")

    if role_name in {"designer", "product_governor"} and support_payload:
        summary = dict(support_payload.get("summary") or {})
        open_cases = int(summary.get("open_case_count") or 0)
        design_impact = int(summary.get("design_impact_count") or 0)
        lane_counts = dict(summary.get("lane_counts") or {})
        owner_counts = dict(summary.get("owner_repo_counts") or {})
        if open_cases or design_impact or lane_counts or owner_counts:
            lane_text = ", ".join(f"{key}={value}" for key, value in lane_counts.items()) or "none"
            owner_text = ", ".join(f"{key}={value}" for key, value in owner_counts.items()) or "none"
            lines.append(
                f"Support pulse: {open_cases} open cases, {design_impact} design-impact candidates, lanes {lane_text}, owners {owner_text}."
            )

    if role_name == "designer":
        lines.append(
            "Designer decision rule: classify canon work as type_a/type_b/type_c/type_d/type_e/type_f/type_g and name the affected canonical files."
        )
    if role_name == "product_governor":
        lines.append(
            "Governor decision rule: choose one primary lane, one bounded reason, and one exit condition when routing code/docs/queue/policy/canon/release action."
        )

    if not lines:
        lines.append("No published runtime brief is available for this target yet; rely on mirrored canon plus current repo truth.")
    return "\n".join(f"- {line}" for line in lines)


def session_messages(session_id: int) -> List[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM studio_messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()


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


def set_account_backoff(alias: str, backoff_until: Optional[dt.datetime], last_error: Optional[str] = None, touch_last_used: bool = False) -> None:
    with db() as conn:
        row = conn.execute("SELECT last_used_at FROM accounts WHERE alias=?", (alias,)).fetchone()
        last_used = iso(utc_now()) if touch_last_used else (row["last_used_at"] if row else None)
        conn.execute(
            "UPDATE accounts SET backoff_until=?, last_error=?, last_used_at=?, updated_at=? WHERE alias=?",
            (iso(backoff_until), last_error, last_used, iso(utc_now()), alias),
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


def touch_account(alias: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE accounts SET last_used_at=?, updated_at=? WHERE alias=?",
            (iso(utc_now()), iso(utc_now()), alias),
        )


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
    freshest_bytes = source_bytes
    freshest_mtime = source_path.stat().st_mtime
    for candidate_home in CODEX_HOME_ROOT.iterdir() if CODEX_HOME_ROOT.exists() else []:
        marker = candidate_home / ".auth_source.sha256"
        candidate_auth = candidate_home / "auth.json"
        if not marker.exists() or not candidate_auth.exists():
            continue
        if marker.read_text(encoding="utf-8").strip() != source_hash:
            continue
        candidate_mtime = candidate_auth.stat().st_mtime
        if candidate_mtime > freshest_mtime:
            freshest_bytes = candidate_auth.read_bytes()
            freshest_mtime = candidate_mtime
    marker = home / ".auth_source.sha256"
    target = home / "auth.json"
    target_hash = sha256_bytes(target.read_bytes()) if target.exists() else None
    if target_hash != sha256_bytes(freshest_bytes):
        target.write_bytes(freshest_bytes)
        marker.write_text(source_hash, encoding="utf-8")
    elif not marker.exists() or marker.read_text(encoding="utf-8").strip() != source_hash:
        marker.write_text(source_hash, encoding="utf-8")


def parse_auth_failure_message(raw_log: str) -> Optional[str]:
    lower = raw_log.lower()
    if "refresh_token_reused" in lower or "refresh token has already been used" in lower:
        return "chatgpt auth refresh token was already used; sign in again"
    if "token_expired" in raw_log or "provided authentication token is expired" in lower:
        return "chatgpt auth token expired; sign in again"
    if "please log out and sign in again" in lower:
        return "chatgpt auth is stale; sign in again"
    if "missing bearer or basic authentication in header" in lower or "missing bearer token" in lower:
        return "ea runtime auth token is missing"
    if "missing x-ea-principal-id" in lower:
        return "ea runtime principal is missing"
    if "401 unauthorized" in lower and ("basic authentication" in lower or "bearer" in lower):
        return "ea runtime auth is missing or invalid"
    if "401 unauthorized" in lower and ("token" in lower or "api key" in lower or "auth" in lower):
        return "authentication failed for this account"
    if "incorrect api key provided" in lower or "invalid api key" in lower:
        return "api key is invalid or revoked"
    return None


def parse_auth_retry_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = text.lower()
    patterns = (
        (r"retry after\s+(\d+)\s*([sm]?)", 1),
        (r"after\s+(\d+)\s*([sm]?)", 1),
        (r"try again in\s+(\d+)\s*([sm]?)", 1),
    )
    for pattern, _multiplier in patterns:
        match = re.search(pattern, lower)
        if not match:
            continue
        value = int(match.group(1))
        unit = (match.group(2) or "").strip().lower()
        multiplier = 60 if unit == "m" else 1
        return max(value * multiplier, default_seconds)
    return default_seconds


def set_account_auth_stale(alias: str, last_error: str) -> None:
    with db() as conn:
        row = conn.execute("SELECT auth_kind, auth_json_file FROM accounts WHERE alias=?", (alias,)).fetchone()
        if row and str(row["auth_kind"] or "") in CHATGPT_AUTH_KINDS and str(row["auth_json_file"] or "").strip():
            conn.execute(
                "UPDATE accounts SET health_state='auth_stale', last_error=?, updated_at=? WHERE auth_kind=? AND auth_json_file=?",
                (last_error, iso(utc_now()), row["auth_kind"], row["auth_json_file"]),
            )
            return
        conn.execute(
            "UPDATE accounts SET health_state='auth_stale', last_error=?, updated_at=? WHERE alias=?",
            (last_error, iso(utc_now()), alias),
        )


def account_value(account_cfg: Any, key: str, default: Any = None) -> Any:
    if isinstance(account_cfg, sqlite3.Row):
        return account_cfg[key] if key in account_cfg.keys() else default
    if isinstance(account_cfg, dict):
        return account_cfg.get(key, default)
    return default


def account_runtime_state(row: sqlite3.Row, account_cfg: Dict[str, Any], now: dt.datetime) -> str:
    configured = str(account_value(row, "health_state", account_cfg.get("health_state", "ready")) or "ready").strip().lower()
    if configured in {"disabled", "draining", "exhausted", "auth_stale"}:
        return configured
    backoff_until = parse_iso(account_value(row, "backoff_until"))
    if backoff_until and backoff_until > now:
        return "cooldown"
    return "ready"


def account_supports_spark(auth_kind: str, account_cfg: Dict[str, Any], allowed_models: List[str]) -> bool:
    if auth_kind not in CHATGPT_AUTH_KINDS:
        return False
    if not bool(account_cfg.get("spark_enabled", SPARK_MODEL in allowed_models)):
        return False
    return (not allowed_models) or (SPARK_MODEL in allowed_models)


def account_spark_runtime_state(row: sqlite3.Row, account_cfg: Dict[str, Any], allowed_models: List[str], now: dt.datetime) -> str:
    base_state = account_runtime_state(row, account_cfg, now)
    if base_state != "ready":
        return base_state
    auth_kind = str(account_value(row, "auth_kind", account_cfg.get("auth_kind", "api_key")) or "api_key")
    if not account_supports_spark(auth_kind, account_cfg, allowed_models):
        return "disabled"
    spark_backoff_until = parse_iso(account_value(row, "spark_backoff_until"))
    if spark_backoff_until and spark_backoff_until > now:
        return "cooldown"
    return "ready"


def model_supported_for_auth_kind(model: str, auth_kind: str) -> bool:
    if auth_kind in CHATGPT_AUTH_KINDS:
        return model in CHATGPT_SUPPORTED_MODELS
    if str(auth_kind or "").strip() == EA_AUTH_KIND:
        return str(model or "").strip().startswith("ea-")
    return True


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


def has_ea_runtime_credentials(_: Any) -> bool:
    runtime_cfg = resolved_ea_runtime_settings()
    return bool(runtime_cfg.get("base_url")) and bool(runtime_cfg.get("api_token"))


def resolved_ea_runtime_settings() -> Dict[str, str]:
    base_url = str(os.environ.get("EA_BASE_URL") or os.environ.get("EA_MCP_BASE_URL") or "").strip()
    api_token = str(os.environ.get("EA_API_TOKEN") or os.environ.get("EA_MCP_API_TOKEN") or "").strip()
    principal_id = str(os.environ.get("EA_PRINCIPAL_ID") or os.environ.get("EA_MCP_PRINCIPAL_ID") or "").strip()
    if not base_url:
        base_url, _ = runtime_env_value("EA_BASE_URL", "EA_MCP_BASE_URL")
    if not api_token:
        api_token, _ = runtime_env_value("EA_API_TOKEN", "EA_MCP_API_TOKEN")
    if not principal_id:
        principal_id, _ = runtime_env_value("EA_PRINCIPAL_ID", "EA_MCP_PRINCIPAL_ID", "EA_DEFAULT_PRINCIPAL_ID")
    runtime_ea_env_candidates = []
    if "FLEET_RUNTIME_EA_ENV_PATH" in os.environ:
        runtime_ea_env_candidates.append(os.environ.get("FLEET_RUNTIME_EA_ENV_PATH", "").strip())
    if "CODEXEA_RUNTIME_EA_ENV_PATH" in os.environ:
        runtime_ea_env_candidates.append(os.environ.get("CODEXEA_RUNTIME_EA_ENV_PATH", "").strip())
    if not runtime_ea_env_candidates:
        runtime_ea_env_candidates = ["/docker/fleet/runtime.ea.env"]
    runtime_env_candidates = []
    if "FLEET_RUNTIME_ENV_PATH" in os.environ:
        runtime_env_candidates.append(os.environ.get("FLEET_RUNTIME_ENV_PATH", "").strip())
    if not runtime_env_candidates:
        runtime_env_candidates = ["/docker/fleet/runtime.env"]
    runtime_ea_env_path = str(next((path for path in runtime_ea_env_candidates if path.strip()), "/docker/fleet/runtime.ea.env"))
    runtime_env_path = str(next((path for path in runtime_env_candidates if path.strip()), "/docker/fleet/runtime.env"))
    if not principal_id:
        principal_id = "codex-fleet"
    return {
        "base_url": base_url.rstrip("/"),
        "api_token": api_token,
        "principal_id": principal_id,
        "runtime_ea_env_path": runtime_ea_env_path,
        "runtime_env_path": runtime_env_path,
    }


def runtime_env_value(*names: str) -> Tuple[str, Optional[pathlib.Path]]:
    env_path = []
    runtime_candidates = [
        os.environ.get("FLEET_RUNTIME_EA_ENV_PATH"),
        os.environ.get("CODEXEA_RUNTIME_EA_ENV_PATH"),
        "/docker/fleet/runtime.ea.env",
        "/docker/fleet/runtime.env",
        "/docker/fleet/.env",
        "/docker/.env",
    ]
    runtime_candidates = [path for path in runtime_candidates if str(path or "").strip()]
    unique = []
    seen = set()
    for candidate in runtime_candidates:
        path = pathlib.Path(str(candidate))
        if path in seen:
            continue
        unique.append(path)
        seen.add(path)
    for candidate in unique:
        if not candidate.exists():
            continue
        try:
            for raw_line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() not in names:
                    continue
                return value.strip().strip('"').strip("'"), candidate
        except OSError:
            continue
    return "", None


def codexea_binary() -> str:
    return str(os.environ.get("FLEET_CODEXEA_BIN") or "/docker/fleet/scripts/codex-shims/codexea").strip() or "/docker/fleet/scripts/codex-shims/codexea"


def lane_for_ea_runtime_model(runtime_model: str, fallback_lane: str = "groundwork") -> str:
    normalized = str(runtime_model or "").strip()
    mapping = {
        "ea-gemini-flash": "easy",
        "ea-coder-fast": "repair",
        "ea-groundwork-gemini": "groundwork",
        "ea-review-light": "jury",
        "ea-coder-hard": "core",
        "ea-coder-hard-batch": "core",
        "ea-audit-jury": "jury",
        "ea-coder-survival": "survival",
    }
    return mapping.get(normalized, str(fallback_lane or "groundwork").strip() or "groundwork")


def ea_shim_safe_runner_overrides(overrides: Sequence[Any]) -> List[str]:
    blocked_prefixes = (
        "model=",
        "model_provider=",
        "model_reasoning_effort=",
        "openai_base_url=",
        "chatgpt_base_url=",
        "model_providers.ea.",
    )
    filtered: List[str] = []
    for item in overrides or []:
        text = str(item or "").strip()
        if not text:
            continue
        if any(text.startswith(prefix) for prefix in blocked_prefixes):
            continue
        filtered.append(text)
    return filtered


def prepare_account_environment(alias: str, account_cfg: Dict[str, Any]) -> Dict[str, str]:
    home = account_home(alias)
    config_lines = ['cli_auth_credentials_store = "file"']
    forced_login_method = account_cfg.get("forced_login_method")
    if forced_login_method:
        config_lines.append(f"forced_login_method = {json.dumps(str(forced_login_method))}")
    forced_workspace_id = account_cfg.get("forced_chatgpt_workspace_id")
    if forced_workspace_id:
        config_lines.append(f"forced_chatgpt_workspace_id = {json.dumps(str(forced_workspace_id))}")
    (home / "config.toml").write_text("\n".join(config_lines) + "\n", encoding="utf-8")

    env = os.environ.copy()
    env["CODEX_HOME"] = str(home)
    env["HOME"] = str(home)

    auth_kind = account_cfg.get("auth_kind", "api_key")
    if auth_kind == "api_key":
        env["CODEX_API_KEY"] = read_api_key(account_cfg)
    elif str(auth_kind or "").strip() == EA_AUTH_KIND:
        ea_runtime = resolved_ea_runtime_settings()
        if not ea_runtime["api_token"]:
            raise RuntimeError("EA runtime token is not configured")
        if not ea_runtime["base_url"]:
            raise RuntimeError("EA runtime base URL is not configured")
        if ea_runtime["base_url"]:
            env["EA_BASE_URL"] = ea_runtime["base_url"]
            env["EA_MCP_BASE_URL"] = ea_runtime["base_url"]
        if ea_runtime["api_token"]:
            env["EA_API_TOKEN"] = ea_runtime["api_token"]
            env["EA_MCP_API_TOKEN"] = ea_runtime["api_token"]
        if ea_runtime["principal_id"]:
            env["EA_PRINCIPAL_ID"] = ea_runtime["principal_id"]
            env["EA_MCP_PRINCIPAL_ID"] = ea_runtime["principal_id"]
        env["CODEXEA_RUNTIME_EA_ENV_PATH"] = ea_runtime["runtime_ea_env_path"]
        env["FLEET_RUNTIME_EA_ENV_PATH"] = ea_runtime["runtime_ea_env_path"]
        env["FLEET_RUNTIME_ENV_PATH"] = ea_runtime["runtime_env_path"]
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
                while True:
                    chunk = await proc.stdout.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    f.flush()
        else:
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break

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


def parse_spark_pool_backoff_seconds(text: str, default_seconds: int) -> Optional[int]:
    lower = text.lower()
    spark_signals = ("spark", "codex spark", "spark pool", "spark token", "spark quota", "spark credits")
    exhaustion_signals = ("depleted", "exhausted", "empty", "unavailable", "quota exceeded", "limit reached", "out of")
    if not any(signal in lower for signal in spark_signals):
        return None
    if not any(signal in lower for signal in exhaustion_signals) and "429" not in lower and "rate limit" not in lower:
        return None
    return parse_backoff_seconds(text, default_seconds) or default_seconds


def truncate_title(text: str, max_len: int = 72) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= max_len:
        return clean or "Studio session"
    return clean[: max_len - 1].rstrip() + "…"


def pick_studio_account_and_model(config: Dict[str, Any], project_cfg: Dict[str, Any], role_name: str, role_cfg: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    aliases = list(role_cfg.get("accounts") or config.get("studio", {}).get("default_accounts") or project_cfg.get("accounts") or [])
    if not aliases:
        aliases = list((config.get("accounts") or {}).keys())
    if not aliases:
        return None, None, "no configured accounts"

    now = utc_now()
    price_table = config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE
    models = list(role_cfg.get("models") or [CHATGPT_STANDARD_MODEL])
    alias_priority = {alias: index for index, alias in enumerate(aliases)}
    candidates: List[Tuple[int, dt.datetime, str, str, str]] = []

    with db() as conn:
        for alias in aliases:
            account_cfg = (config.get("accounts") or {}).get(alias)
            if not account_cfg:
                continue
            row = conn.execute("SELECT * FROM accounts WHERE alias=?", (alias,)).fetchone()
            auth_kind = str(account_value(row, "auth_kind", account_cfg.get("auth_kind", "api_key")) or "api_key")
            allowed = list(account_cfg.get("allowed_models") or [])
            if row and account_runtime_state(row, account_cfg, now) != "ready":
                continue
            active = active_run_count_for_account(alias)
            max_parallel = int((account_value(row, "max_parallel_runs", account_cfg.get("max_parallel_runs", 1))) or 1)
            if active >= max_parallel:
                continue

            if auth_kind == "api_key":
                if not has_api_key(account_cfg):
                    continue
            elif str(auth_kind or "").strip() == EA_AUTH_KIND:
                if not has_ea_runtime_credentials(account_cfg):
                    continue
            else:
                secret = pathlib.Path(account_cfg.get("auth_json_file", ""))
                if not secret.exists():
                    continue

            spark_state = account_spark_runtime_state(row, account_cfg, allowed, now) if row else "disabled"
            available_models: List[str] = []
            for model in models:
                if allowed and model not in allowed:
                    continue
                if not model_supported_for_auth_kind(model, auth_kind):
                    continue
                if model == SPARK_MODEL and spark_state != "ready":
                    continue
                available_models.append(model)
            if not available_models:
                continue
            chosen_model = available_models[0]
            est_cost = estimate_cost_usd_for_model(price_table, chosen_model, 2500, 0, 1200) or 0.0
            day_usage = usage_for_account(alias, "day")
            day_budget = account_cfg.get("daily_budget_usd")
            if day_budget is not None and (float(day_usage["cost"]) + est_cost) > float(day_budget):
                continue
            month_usage = usage_for_account(alias, "month")
            month_budget = account_cfg.get("monthly_budget_usd")
            if month_budget is not None and (float(month_usage["cost"]) + est_cost) > float(month_budget):
                continue

            last_used = parse_iso(row["last_used_at"]) if row else None
            last_used = last_used or dt.datetime.fromtimestamp(0, tz=UTC)
            note = f"studio role {role_name} via {alias}"
            candidates.append((alias_priority.get(alias, len(alias_priority)), last_used, alias, chosen_model, note))

    if not candidates:
        return None, None, "no studio account available after auth, backoff, allowlist, or budget checks"
    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, alias, model, note = candidates[0]
    return alias, model, note


def build_conversation_window(session_id: int, limit: int) -> str:
    messages = session_messages(session_id)
    trimmed = messages[-limit:] if limit > 0 else messages
    rendered: List[str] = []
    for row in trimmed:
        label = f"{row['actor_type']}:{row['actor_name']}"
        rendered.append(f"{label}\n{row['content']}")
    return "\n\n".join(rendered) if rendered else "<no prior messages>"


def write_schema_file(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(STUDIO_RESPONSE_SCHEMA, indent=2), encoding="utf-8")


def parse_jsonish(text: str) -> Dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def safe_relative_publish_path(raw: str) -> pathlib.Path:
    raw = raw.strip().replace("\\", "/")
    if raw.startswith(f"{STUDIO_PUBLISHED_DIRNAME}/"):
        raw = raw[len(STUDIO_PUBLISHED_DIRNAME) + 1 :]
    rel = pathlib.PurePosixPath(raw)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError(f"unsafe path: {raw}")
    rel_str = rel.as_posix()
    if rel_str in ALLOWED_STUDIO_FILES:
        return pathlib.Path(rel_str)
    if rel.parts and rel.parts[0] == "ADR" and rel.suffix == ".md":
        return pathlib.Path(*rel.parts)
    raise ValueError(f"unsupported published path: {raw}")


def write_proposal_drafts(target_cfg: Dict[str, Any], proposal_id: int, files: List[Dict[str, str]], *, prefix: Optional[str] = None) -> pathlib.Path:
    draft_root = studio_drafts_root(target_cfg) / f"proposal-{proposal_id}"
    if prefix:
        draft_root = draft_root / prefix
    draft_root.mkdir(parents=True, exist_ok=True)
    for item in files:
        rel = safe_relative_publish_path(item["path"])
        out = draft_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(item.get("content", ""), encoding="utf-8")
    return draft_root


def feedback_filename() -> str:
    return utc_now().strftime("%Y-%m-%d-%H%M%S-studio-publication.md")


def work_package_source_queue_fingerprint(items: List[Any]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _resolve_project_file(project_cfg: Dict[str, Any], source_path: str) -> pathlib.Path:
    return resolve_project_path(project_cfg, source_path)


def _markdown_table_cells(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _select_latest_active_tasks(entries: List[Tuple[str, str]]) -> List[str]:
    latest_status_by_key: Dict[str, str] = {}
    latest_task_by_key: Dict[str, str] = {}
    latest_order_by_key: Dict[str, int] = {}
    ordered_keys: List[str] = []
    for order, (status, task) in enumerate(entries):
        task_text = str(task or "").strip().strip("`")
        if not task_text or task_text.startswith("<"):
            continue
        key = " ".join(task_text.split()).lower()
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


def _load_worklist_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = _resolve_project_file(project_cfg, str(source_cfg.get("path", "WORKLIST.md")))
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    entries: List[Tuple[str, str]] = []
    for line in lines:
        cells = _markdown_table_cells(line)
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
    return _select_latest_active_tasks(entries)


def _load_tasks_work_log_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = _resolve_project_file(project_cfg, str(source_cfg.get("path", "TASKS_WORK_LOG.md")))
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    items: List[str] = []
    seen: set[str] = set()
    for line in lines:
        cells = _markdown_table_cells(line)
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


def _load_milestone_capability_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = _resolve_project_file(project_cfg, str(source_cfg.get("path", "MILESTONE.json")))
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


def _apply_queue_source(project_cfg: Dict[str, Any], queue: List[Any], source_cfg: Dict[str, Any]) -> List[Any]:
    fallback_only_if_empty = bool(source_cfg.get("fallback_only_if_empty"))
    if fallback_only_if_empty and queue:
        return list(queue)
    kind = str(source_cfg.get("kind", "") or "").strip().lower()
    if kind == "worklist":
        items = _load_worklist_queue(project_cfg, source_cfg)
    elif kind == "tasks_work_log":
        items = _load_tasks_work_log_queue(project_cfg, source_cfg)
    elif kind == "milestone_capabilities":
        items = _load_milestone_capability_queue(project_cfg, source_cfg)
    else:
        items = []
    mode = str(source_cfg.get("mode", "append")).strip().lower() or "append"
    if mode == "replace":
        return list(items)
    if mode == "prepend":
        return list(items) + list(queue)
    return list(queue) + list(items)


def _base_queue_for_target(target_cfg: Dict[str, Any]) -> List[Any]:
    project_cfg = dict(target_cfg.get("project_cfg") or {})
    queue = list(project_cfg.get("queue") or [])
    for source_cfg in project_cfg.get("queue_sources") or []:
        if isinstance(source_cfg, dict):
            queue = _apply_queue_source(project_cfg, queue, source_cfg)
    return queue


def _design_compile_present_for_target(target_cfg: Dict[str, Any]) -> bool:
    raw_root = str(
        target_cfg.get("path")
        or ((target_cfg.get("project_cfg") or {}).get("path") or "")
    ).strip()
    root = pathlib.Path(raw_root) if raw_root else fleet_repo_root()
    if all((root / rel).is_file() for rel in DESIGN_COMPILE_REQUIRED_FILES):
        return True
    design_doc = str(
        target_cfg.get("design_doc")
        or ((target_cfg.get("project_cfg") or {}).get("design_doc") or "")
    ).strip()
    if not design_doc:
        return False
    path = pathlib.Path(design_doc)
    if not path.is_absolute():
        path = root / path
    return path.is_file()


def _parse_queue_overlay_payload(payload: Any) -> Optional[Dict[str, Any]]:
    if isinstance(payload, list):
        return {
            "mode": "append",
            "items": list(payload),
            "source_queue_fingerprint": "",
        }
    if not isinstance(payload, dict):
        return None
    raw_items = payload.get("items")
    if raw_items is None:
        raw_items = payload.get("queue")
    normalized = dict(payload)
    normalized["mode"] = str(payload.get("mode") or "append").strip().lower() or "append"
    normalized["items"] = list(raw_items or [])
    normalized.pop("queue", None)
    normalized["source_queue_fingerprint"] = str(payload.get("source_queue_fingerprint") or payload.get("queue_fingerprint") or "").strip()
    normalized.pop("queue_fingerprint", None)
    return normalized


def _apply_queue_overlay(base_queue: List[Any], overlay_payload: Dict[str, Any]) -> List[Any]:
    mode = str(overlay_payload.get("mode") or "append").strip().lower() or "append"
    items = list(overlay_payload.get("items") or [])
    if not items:
        return list(base_queue)
    if mode == "replace":
        return items
    if mode == "prepend":
        return items + list(base_queue)
    return list(base_queue) + items


def queue_overlay_payload_from_content(raw_content: str) -> Optional[Dict[str, Any]]:
    try:
        payload = yaml.safe_load(raw_content) or {}
    except Exception:
        return None
    return _parse_queue_overlay_payload(payload)


def queue_overlay_payload_for_publish(target_cfg: Dict[str, Any], raw_content: str) -> Optional[Dict[str, Any]]:
    overlay_payload = queue_overlay_payload_from_content(raw_content)
    if overlay_payload is None:
        return None
    overlay_payload["source_queue_fingerprint"] = work_package_source_queue_fingerprint(_base_queue_for_target(target_cfg))
    return overlay_payload


def queue_overlay_text_for_publish(target_cfg: Dict[str, Any], raw_content: str) -> str:
    overlay_payload = queue_overlay_payload_for_publish(target_cfg, raw_content)
    if overlay_payload is None:
        return raw_content
    return yaml.safe_dump(overlay_payload, sort_keys=False)


def queue_dispatchable_truth_ready(target_cfg: Dict[str, Any], files: List[Dict[str, str]]) -> bool:
    content_by_rel = {
        safe_relative_publish_path(item["path"]).as_posix(): str(item.get("content") or "")
        for item in files
        if str(item.get("path") or "").strip()
    }
    raw_content = content_by_rel.get("QUEUE.generated.yaml")
    if raw_content is None:
        return False
    overlay_payload = queue_overlay_payload_from_content(raw_content)
    if overlay_payload is None:
        return False
    expected_queue_fingerprint = str(overlay_payload.get("source_queue_fingerprint") or "").strip()
    if not expected_queue_fingerprint:
        return False
    return expected_queue_fingerprint == work_package_source_queue_fingerprint(_base_queue_for_target(target_cfg))


def effective_publish_queue(target_cfg: Dict[str, Any], files: List[Dict[str, str]]) -> List[Any]:
    base_queue = _base_queue_for_target(target_cfg)
    content_by_rel = {
        safe_relative_publish_path(item["path"]).as_posix(): str(item.get("content") or "")
        for item in files
        if str(item.get("path") or "").strip()
    }
    raw_content = content_by_rel.get("QUEUE.generated.yaml")
    if raw_content is None:
        return list(base_queue)
    overlay_payload = queue_overlay_payload_from_content(raw_content)
    if overlay_payload is None:
        return list(base_queue)
    expected_queue_fingerprint = str(overlay_payload.get("source_queue_fingerprint") or "").strip()
    if not expected_queue_fingerprint:
        return list(base_queue)
    if expected_queue_fingerprint != work_package_source_queue_fingerprint(base_queue):
        return list(base_queue)
    return _apply_queue_overlay(base_queue, overlay_payload)


def workpackages_dispatchable_truth_ready(target_cfg: Dict[str, Any], files: List[Dict[str, str]]) -> bool:
    content_by_rel = {
        safe_relative_publish_path(item["path"]).as_posix(): str(item.get("content") or "")
        for item in files
        if str(item.get("path") or "").strip()
    }
    raw_content = content_by_rel.get("WORKPACKAGES.generated.yaml")
    if raw_content is None:
        return False
    try:
        payload = yaml.safe_load(raw_content) or {}
    except Exception:
        return False
    expected_queue_fingerprint = ""
    if isinstance(payload, dict):
        expected_queue_fingerprint = str(payload.get("source_queue_fingerprint") or payload.get("queue_fingerprint") or "").strip()
    current_queue = effective_publish_queue(target_cfg, files)
    if expected_queue_fingerprint:
        return expected_queue_fingerprint == work_package_source_queue_fingerprint(current_queue)
    return not current_queue


def compile_manifest_payload(target_cfg: Dict[str, Any], files: List[Dict[str, str]]) -> Dict[str, Any]:
    rel_paths = [safe_relative_publish_path(item["path"]).as_posix() for item in files]
    design_files = {"VISION.md", "ROADMAP.md", "ARCHITECTURE.md"}
    policy_files = {
        "runtime-instructions.generated.md",
        "QUEUE.generated.yaml",
        "WORKPACKAGES.generated.yaml",
        "STATUS_PLANE.generated.yaml",
        "PROGRAM_MILESTONES.generated.yaml",
        "CONTRACT_SETS.yaml",
        "GROUP_BLOCKERS.md",
    }
    dispatchable_artifacts = {"QUEUE.generated.yaml", "WORKPACKAGES.generated.yaml"}
    lifecycle = normalize_lifecycle_state(
        (target_cfg.get("project_cfg") or target_cfg.get("group_cfg") or {}).get("lifecycle"),
        "dispatchable" if target_cfg["target_type"] == "project" else "live",
    )
    queue_truth_ready = queue_dispatchable_truth_ready(target_cfg, files)
    workpackages_truth_ready = workpackages_dispatchable_truth_ready(target_cfg, files)
    design_compile_present = _design_compile_present_for_target(target_cfg)
    design_compile_required = lifecycle in {"scaffold", "dispatchable", "live", "signoff_only"}
    policy_compile_required = lifecycle in {"dispatchable", "live", "signoff_only"}
    execution_compile_required = lifecycle in {"dispatchable", "live"}
    return {
        "schema_version": DESIRED_STATE_SCHEMA_VERSION,
        "published_at": iso(utc_now()),
        "target_type": target_cfg["target_type"],
        "target_id": target_cfg["target_id"],
        "lifecycle": lifecycle,
        "artifacts": rel_paths,
        "dispatchable_truth_contract": {
            "scope": "execution_truth_only",
            "design_compile_required_separately": design_compile_required,
            "policy_compile_required_separately": policy_compile_required,
            "execution_compile_required": execution_compile_required,
            "package_compile_required_separately": lifecycle in {"dispatchable", "live"},
            "capacity_compile_required_separately": lifecycle in {"dispatchable", "live"},
        },
        "stages": {
            "design_compile": design_compile_present or any(path in design_files for path in rel_paths),
            "policy_compile": any(path in policy_files for path in rel_paths),
            "execution_compile": any(path in dispatchable_artifacts for path in rel_paths),
            "package_compile": "WORKPACKAGES.generated.yaml" in rel_paths,
            "capacity_compile": any(path in dispatchable_artifacts for path in rel_paths) or "runtime-instructions.generated.md" in rel_paths,
        },
        "dispatchable_truth_ready": lifecycle in {"dispatchable", "live"} and (queue_truth_ready or workpackages_truth_ready),
    }


def publish_target_files(
    target_cfg: Dict[str, Any],
    files: List[Dict[str, str]],
    *,
    publish_feedback: bool,
    feedback_note: str,
) -> Tuple[pathlib.Path, Optional[str]]:
    published_root = studio_published_root(target_cfg)
    published_root.mkdir(parents=True, exist_ok=True)
    normalized_files: List[Dict[str, str]] = []
    for item in files:
        rel = safe_relative_publish_path(item["path"]).as_posix()
        content = str(item.get("content") or "")
        if rel == "QUEUE.generated.yaml":
            content = queue_overlay_text_for_publish(target_cfg, content)
        normalized_files.append(
            {
                "path": item["path"],
                "content": content,
            }
        )
    for item in normalized_files:
        rel = safe_relative_publish_path(item["path"])
        out = published_root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(item.get("content", ""), encoding="utf-8")
    (published_root / COMPILE_MANIFEST_FILENAME).write_text(
        json.dumps(compile_manifest_payload(target_cfg, normalized_files), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    feedback_rel = None
    note = str(feedback_note or "").strip()
    if publish_feedback and note:
        feedback_dir = target_feedback_root(target_cfg)
        feedback_dir.mkdir(parents=True, exist_ok=True)
        rel_name = feedback_filename()
        path = feedback_dir / rel_name
        files_list = "\n".join(f"- {safe_relative_publish_path(item['path']).as_posix()}" for item in normalized_files)
        content = (
            f"# Studio Publication\n\n"
            f"Published artifacts are now authoritative under `{STUDIO_PUBLISHED_DIRNAME}`.\n\n"
            f"## Published files\n{files_list or '- <none>'}\n\n"
            f"## Steering note\n{note}\n"
        )
        path.write_text(content, encoding="utf-8")
        if target_cfg["target_type"] == "project":
            feedback_rel = f"feedback/{rel_name}"
        elif target_cfg["target_type"] == "group":
            feedback_rel = f"groups/{target_cfg['target_id']}/feedback/{rel_name}"
        else:
            feedback_rel = f"feedback/{rel_name}"
    return published_root, feedback_rel


def proposal_targets_from_payload(
    config: Dict[str, Any],
    session_target_cfg: Dict[str, Any],
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    proposal = payload.get("proposal", {}) or {}
    targets = proposal.get("targets") or []
    if targets:
        normalized: List[Dict[str, Any]] = []
        for item in targets:
            if not isinstance(item, dict):
                continue
            target_type = str(item.get("target_type") or "").strip()
            target_id = str(item.get("target_id") or "").strip()
            target_cfg = resolve_target_cfg(config, target_type, target_id)
            normalized.append(
                {
                    "target_cfg": target_cfg,
                    "files": list(item.get("files") or []),
                    "feedback_note": str(item.get("feedback_note") or ""),
                }
            )
        return normalized
    return [
        {
            "target_cfg": session_target_cfg,
            "files": list(proposal.get("files") or []),
            "feedback_note": str(proposal.get("feedback_note") or ""),
        }
    ]


def update_session_status(session_id: int, *, status: str, summary: Optional[str] = None, active_run_id: Optional[int] = None, last_error: Optional[str] = None) -> None:
    with db() as conn:
        row = conn.execute("SELECT summary FROM studio_sessions WHERE id=?", (session_id,)).fetchone()
        current_summary = row["summary"] if row else ""
        conn.execute(
            """
            UPDATE studio_sessions
            SET status=?, summary=?, active_run_id=?, last_error=?, updated_at=?
            WHERE id=?
            """,
            (
                status,
                summary if summary is not None else current_summary,
                active_run_id,
                last_error,
                iso(utc_now()),
                session_id,
            ),
        )


def insert_message(session_id: int, actor_type: str, actor_name: str, content: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO studio_messages(session_id, actor_type, actor_name, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, actor_type, actor_name, content, iso(utc_now())),
        )
        conn.execute("UPDATE studio_sessions SET updated_at=? WHERE id=?", (iso(utc_now()), session_id))


def build_prompt(config: Dict[str, Any], target_cfg: Dict[str, Any], session_row: sqlite3.Row) -> str:
    studio_cfg = config.get("studio", {}) or {}
    role_name = normalize_studio_role_name(session_row["role"], (studio_cfg.get("roles") or {}))
    role_label = ROLE_LABELS.get(role_name, role_name.replace("_", " ").title())
    context_files = "\n".join(f"- {item}" for item in existing_context_files(target_cfg))
    role_priority_files = "\n".join(f"- {item}" for item in studio_role_priority_files(target_cfg, role_name)) or "- No role-priority files configured."
    role_runtime_brief = studio_role_runtime_brief(target_cfg, role_name)
    conversation = build_conversation_window(int(session_row["id"]), int(studio_cfg.get("session_message_window", 8)))
    summary = session_row["summary"] or "No prior summary yet."
    role_guidance_lines = [
        "Keep the answer concise, decisive, and publish-ready.",
        "Prefer precise artifacts and queue overlays over vague summaries.",
        "Always fill proposal.control_decision with the primary lane, change class, bounded reason, exit condition, and affected canon files.",
    ]
    if role_name == "designer":
        role_guidance_lines.extend(
            [
                "Treat feedback clusters as design inputs only after they are synthesized into a clear contradiction, missing seam, or public-story drift.",
                "Prefer canon, policy, and instruction updates over implementation guesses when the real problem is missing product truth.",
                "Use proposal.control_decision.change_class to name the canon change type, and keep affected canon files explicit instead of implied.",
            ]
        )
    if role_name == "product_governor":
        role_guidance_lines.extend(
            [
                "Judge whole-product health, release readiness, support closure, and public-promise drift rather than just local repo polish.",
                "Route issues explicitly into code, docs, queue, policy, canon, freeze, or reroute actions with one bounded reason and one exit condition.",
                "When the right answer is freeze, rollback, reroute, or defer, make proposal.control_decision.primary_lane and exit_condition concrete enough for an operator to act on immediately.",
            ]
        )
    if role_name == "auditor":
        role_guidance_lines.extend(
            [
                "Decompose messy human input into scoped findings, candidate tasks, and publishable artifacts.",
                "When the request spans several repos, prefer proposal.targets with coordinated group and project outputs.",
                "Treat feedback injection as a slice-boundary action: publish notes, queue overlays, and artifacts for later disposable runs rather than trying to change an in-flight worker.",
            ]
        )
    return STUDIO_PROMPT_TEMPLATE.format(
        role_label=role_label,
        target_type=target_cfg["target_type"],
        target_id=target_cfg["target_id"],
        context_files=context_files,
        role_priority_files=role_priority_files,
        role_runtime_brief=role_runtime_brief,
        published_dir=STUDIO_PUBLISHED_DIRNAME,
        session_summary=summary,
        conversation=conversation,
        role_guidance_block="\n".join(f"- {line}" for line in role_guidance_lines),
    ) + "\n"


@dataclass
class RuntimeState:
    tasks: Dict[int, asyncio.Task]
    stop: asyncio.Event


state = RuntimeState(tasks={}, stop=asyncio.Event())
app = FastAPI(title=APP_TITLE)


def operator_auth_enabled() -> bool:
    return OPERATOR_AUTH_REQUIRED and bool(OPERATOR_PASSWORD)


def operator_session_value() -> str:
    return hashlib.sha256(OPERATOR_PASSWORD.encode("utf-8")).hexdigest()


def safe_next_path(value: Optional[str], default: str = "/studio") -> str:
    candidate = str(value or "").strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return default
    return candidate


def operator_login_url(request: Request) -> str:
    target = safe_next_path(
        f"{request.url.path}{'?' + request.url.query if request.url.query else ''}",
        "/studio",
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
    return path == "/health"


def operator_auth_protected_path(path: str) -> bool:
    return path.startswith("/studio") or path.startswith("/api/studio")


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


async def execute_studio_turn(session_id: int) -> None:
    config = normalize_config()
    sync_accounts_to_db(config)
    role_cfg = None
    run_id = None
    target_cfg: Dict[str, Any]

    with db() as conn:
        session_row = conn.execute("SELECT * FROM studio_sessions WHERE id=?", (session_id,)).fetchone()
    if not session_row:
        state.tasks.pop(session_id, None)
        return

    try:
        target_cfg = resolve_target_cfg(
            config,
            str(session_row["target_type"] or "project"),
            str(session_row["target_id"] or session_row["project_id"] or ""),
        )
        role_cfg = (config.get("studio", {}).get("roles") or {}).get(session_row["role"], DEFAULT_STUDIO["roles"]["designer"])
        alias, model, pick_reason = pick_studio_account_and_model(config, target_cfg, session_row["role"], role_cfg)
        if not alias or not model:
            update_session_status(session_id, status="awaiting_account", last_error=pick_reason)
            if str(session_row["origin_type"] or "") == "automation":
                update_studio_automation_state(
                    str(session_row["role"] or ""),
                    str(session_row["target_type"] or "project"),
                    str(session_row["target_id"] or session_row["project_id"] or ""),
                    trigger_fingerprint=str(session_row["automation_fingerprint"] or ""),
                    last_session_id=session_id,
                    last_status="awaiting_account",
                    last_message=pick_reason,
                )
            return

        prompt = build_prompt(config, target_cfg, session_row)
        started_at = utc_now()
        ts = started_at.strftime("%Y%m%dT%H%M%SZ")
        project_id = target_cfg["run_project_id"]
        role_name = session_row["role"]
        session_dir = LOG_DIR / target_cfg["target_type"] / target_cfg["target_id"] / f"session-{session_id}"
        log_path = session_dir / f"{ts}-{role_name}.jsonl"
        prompt_path = session_dir / f"{ts}-{role_name}.prompt.txt"
        final_path = session_dir / f"{ts}-{role_name}.final.json"
        schema_path = session_dir / f"{ts}-{role_name}.schema.json"
        session_dir.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        write_schema_file(schema_path)

        decision_reason = f"studio:{role_name}; {pick_reason}"
        with db() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                VALUES (?, ?, 'studio', ?, 'starting', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    alias,
                    f"Studio {role_name} session {session_id}",
                    model,
                    role_cfg.get("reasoning_effort", "low"),
                    role_name,
                    decision_reason,
                    iso(started_at),
                    str(log_path),
                    str(final_path),
                    str(prompt_path),
                ),
            )
            run_id = int(cur.lastrowid)
        update_session_status(session_id, status="running", active_run_id=run_id, last_error=None)

        env = prepare_account_environment(alias, (config.get("accounts") or {})[alias])
        touch_account(alias)
        with db() as conn:
            conn.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))

        use_ea_shim = model.startswith("ea-") and str((config.get("accounts") or {}).get(alias, {}).get("auth_kind") or "") == EA_AUTH_KIND
        if use_ea_shim:
            env["CODEXEA_MODEL"] = model
            if role_cfg.get("reasoning_effort"):
                env["CODEXEA_REASONING_EFFORT"] = str(role_cfg["reasoning_effort"])
            cmd = [
                codexea_binary(),
                lane_for_ea_runtime_model(model, "groundwork"),
                "exec",
                "--json",
                "--cd",
                target_cfg["path"],
                "--sandbox",
                str(role_cfg.get("sandbox", "danger-full-access")),
                "--output-last-message",
                str(final_path),
                "--output-schema",
                str(schema_path),
            ]
        else:
            cmd = [
                "codex",
                "--ask-for-approval",
                str(role_cfg.get("approval_policy", "never")),
                "exec",
                "--json",
                "--cd",
                target_cfg["path"],
                "--sandbox",
                str(role_cfg.get("sandbox", "danger-full-access")),
                "--model",
                model,
                "--output-last-message",
                str(final_path),
                "--output-schema",
                str(schema_path),
            ]
        if role_cfg.get("profile"):
            cmd += ["--profile", str(role_cfg["profile"])]
        if role_cfg.get("skip_git_repo_check"):
            cmd += ["--skip-git-repo-check"]
        if role_cfg.get("reasoning_effort") and not use_ea_shim:
            cmd += ["-c", f"model_reasoning_effort={json.dumps(str(role_cfg['reasoning_effort']))}"]
        overrides = (
            ea_shim_safe_runner_overrides(role_cfg.get("config_overrides", []) or [])
            if use_ea_shim
            else [str(item) for item in (role_cfg.get("config_overrides", []) or [])]
        )
        for override in overrides:
            cmd += ["-c", str(override)]
        cmd += ["-"]

        timeout_seconds = int(role_cfg.get("exec_timeout_seconds") or 1800)
        rc_result = await run_command(
            cmd,
            cwd=target_cfg["path"],
            env=env,
            input_text=prompt,
            log_path=log_path,
            timeout_seconds=timeout_seconds,
        )
        finished_at = utc_now()
        raw_log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        input_tokens, cached_input_tokens, output_tokens = parse_jsonl_usage(log_path)
        est_cost = estimate_cost_usd_for_model(
            config.get("spider", {}).get("price_table", {}) or DEFAULT_PRICE_TABLE,
            model,
            input_tokens,
            cached_input_tokens,
            output_tokens,
        )

        if rc_result.exit_code == 0:
            payload = parse_jsonish(final_path.read_text(encoding="utf-8"))
            proposal = payload.get("proposal") or {}
            publish_targets = proposal_targets_from_payload(config, target_cfg, payload)
            for target in publish_targets:
                for item in target["files"]:
                    safe_relative_publish_path(str(item.get("path", "")))
            with db() as conn:
                conn.execute(
                    """
                    UPDATE runs
                    SET status='complete', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?
                    WHERE id=?
                    """,
                    (rc_result.exit_code, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, run_id),
                )
                insert_cur = conn.execute(
                    """
                    INSERT INTO studio_proposals(session_id, run_id, project_id, target_type, target_id, role, title, summary, payload_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        run_id,
                        project_id,
                        target_cfg["target_type"],
                        target_cfg["target_id"],
                        role_name,
                        str(proposal.get("title") or f"{ROLE_LABELS.get(role_name, role_name)} proposal"),
                        str(proposal.get("summary") or ""),
                        json.dumps(payload, indent=2),
                        iso(finished_at),
                        iso(finished_at),
                    ),
                )
                proposal_id = int(insert_cur.lastrowid)
            draft_dir = studio_drafts_root(target_cfg) / f"proposal-{proposal_id}"
            draft_dir.mkdir(parents=True, exist_ok=True)
            for target in publish_targets:
                draft_prefix = None
                if len(publish_targets) > 1:
                    draft_prefix = f"{target['target_cfg']['target_type']}-{target['target_cfg']['target_id']}"
                write_proposal_drafts(target["target_cfg"], proposal_id, target["files"], prefix=draft_prefix)
            with db() as conn:
                conn.execute(
                    "UPDATE studio_proposals SET draft_dir=?, updated_at=? WHERE id=?",
                    (str(draft_dir), iso(utc_now()), proposal_id),
                )
            insert_message(session_id, "assistant", role_name, str(payload.get("assistant_reply") or ""))
            update_session_status(
                session_id,
                status="idle",
                summary=str(payload.get("session_summary") or session_row["summary"] or ""),
                active_run_id=None,
                last_error=None,
            )
            if str(session_row["origin_type"] or "") == "automation":
                recommended_mode = str((proposal or {}).get("recommended_publish_mode") or "publish_artifacts_and_feedback").strip() or "publish_artifacts_and_feedback"
                update_studio_automation_state(
                    str(session_row["role"] or ""),
                    str(session_row["target_type"] or "project"),
                    str(session_row["target_id"] or session_row["project_id"] or ""),
                    trigger_fingerprint=str(session_row["automation_fingerprint"] or ""),
                    last_session_id=session_id,
                    last_proposal_id=proposal_id,
                    last_status="proposal_created",
                    last_message=recommended_mode,
                )
                if bool((((config.get("studio", {}) or {}).get("autonomy") or {}).get("auto_publish_recommended", True))):
                    role_autonomy_cfg = ((((config.get("studio", {}) or {}).get("autonomy") or {}).get("roles") or {}).get(str(session_row["role"] or ""), {}) or {})
                    if bool(role_autonomy_cfg.get("auto_publish_recommended", True)) and recommended_mode != "hold":
                        publish_result = publish_proposal(proposal_id, mode=recommended_mode)
                        update_studio_automation_state(
                            str(session_row["role"] or ""),
                            str(session_row["target_type"] or "project"),
                            str(session_row["target_id"] or session_row["project_id"] or ""),
                            trigger_fingerprint=str(session_row["automation_fingerprint"] or ""),
                            last_session_id=session_id,
                            last_proposal_id=proposal_id,
                            last_published_proposal_id=proposal_id,
                            last_publish_at=iso(utc_now()),
                            last_status="published",
                            last_message=str(publish_result.get("mode") or recommended_mode),
                        )
                    elif recommended_mode == "hold":
                        update_studio_automation_state(
                            str(session_row["role"] or ""),
                            str(session_row["target_type"] or "project"),
                            str(session_row["target_id"] or session_row["project_id"] or ""),
                            trigger_fingerprint=str(session_row["automation_fingerprint"] or ""),
                            last_session_id=session_id,
                            last_proposal_id=proposal_id,
                            last_status="held",
                            last_message="proposal recommended hold",
                        )
        else:
            if rc_result.timed_out:
                msg = f"studio turn timed out after {rc_result.timeout_seconds}s"
                error_class = "timeout"
            else:
                backoff = None
                spark_backoff = parse_spark_pool_backoff_seconds(raw_log, 60) if model == SPARK_MODEL else None
                if spark_backoff is not None:
                    until = utc_now() + dt.timedelta(seconds=spark_backoff)
                    set_account_spark_backoff(alias, until, f"spark pool unavailable for {spark_backoff}s")
                    msg = f"spark pool unavailable for {spark_backoff}s"
                    error_class = "spark_pool"
                else:
                    backoff = parse_backoff_seconds(raw_log, 60)
                    if backoff is not None:
                        until = utc_now() + dt.timedelta(seconds=backoff)
                        set_account_backoff(alias, until, f"rate limited for {backoff}s")
                        msg = f"rate limited for {backoff}s"
                        error_class = "rate_limit"
                    else:
                        auth_failure = parse_auth_failure_message(raw_log)
                        if auth_failure:
                            account_cfg = (config.get("accounts") or {}).get(alias, {})
                            is_ea_account = str(account_cfg.get("auth_kind") or "") == EA_AUTH_KIND
                            auth_backoff_seconds = parse_auth_retry_seconds(raw_log, 30 if is_ea_account else 120)
                            if is_ea_account:
                                backoff_until = utc_now() + dt.timedelta(seconds=auth_backoff_seconds)
                                set_account_backoff(alias, backoff_until, auth_failure)
                                msg = f"{auth_failure} for {auth_backoff_seconds}s"
                                error_class = "auth"
                            else:
                                set_account_auth_stale(alias, auth_failure)
                                msg = auth_failure
                                error_class = "auth"
                        else:
                            msg = f"studio turn failed with exit {rc_result.exit_code}"
                            error_class = "exec"
            with db() as conn:
                conn.execute(
                    """
                    UPDATE runs
                    SET status='failed', exit_code=?, finished_at=?, input_tokens=?, cached_input_tokens=?, output_tokens=?, estimated_cost_usd=?, error_class=?, error_message=?
                    WHERE id=?
                    """,
                    (rc_result.exit_code, iso(finished_at), input_tokens, cached_input_tokens, output_tokens, est_cost, error_class, msg, run_id),
                )
            next_status = "awaiting_account" if error_class in {"rate_limit", "spark_pool", "auth"} else "idle"
            update_session_status(session_id, status=next_status, active_run_id=None, last_error=msg)
            if str(session_row["origin_type"] or "") == "automation":
                update_studio_automation_state(
                    str(session_row["role"] or ""),
                    str(session_row["target_type"] or "project"),
                    str(session_row["target_id"] or session_row["project_id"] or ""),
                    trigger_fingerprint=str(session_row["automation_fingerprint"] or ""),
                    last_session_id=session_id,
                    last_status=next_status,
                    last_message=msg,
                )
    except Exception as exc:
        traceback.print_exc()
        finished_at = utc_now()
        if run_id is not None:
            with db() as conn:
                conn.execute(
                    "UPDATE runs SET status='failed', finished_at=?, error_class='studio', error_message=? WHERE id=?",
                    (iso(finished_at), str(exc), run_id),
                )
        update_session_status(session_id, status="idle", active_run_id=None, last_error=str(exc))
        if str(session_row["origin_type"] or "") == "automation":
            update_studio_automation_state(
                str(session_row["role"] or ""),
                str(session_row["target_type"] or "project"),
                str(session_row["target_id"] or session_row["project_id"] or ""),
                trigger_fingerprint=str(session_row["automation_fingerprint"] or ""),
                last_session_id=session_id,
                last_status="error",
                last_message=str(exc),
            )
    finally:
        state.tasks.pop(session_id, None)


async def scheduler_loop() -> None:
    while not state.stop.is_set():
        try:
            config = normalize_config()
            sync_accounts_to_db(config)
            maybe_queue_automated_sessions(config)
            max_parallel = int((config.get("studio", {}) or {}).get("max_parallel_runs", 1))
            with db() as conn:
                sessions = conn.execute(
                    """
                    SELECT *
                    FROM studio_sessions
                    WHERE status IN ('queued', 'awaiting_account')
                    ORDER BY CASE status WHEN 'queued' THEN 0 ELSE 1 END, updated_at ASC, id ASC
                    """
                ).fetchall()
            running_count = len(state.tasks)
            for row in sessions:
                session_id = int(row["id"])
                if session_id in state.tasks:
                    continue
                if running_count >= max_parallel:
                    break
                task = asyncio.create_task(execute_studio_turn(session_id))
                state.tasks[session_id] = task
                running_count += 1
        except Exception:
            traceback.print_exc()
        autonomy_poll = int((((config.get("studio", {}) or {}).get("autonomy") or {}).get("poll_seconds") or 60) if 'config' in locals() else 60)
        await asyncio.sleep(max(5, autonomy_poll))


@app.on_event("startup")
async def startup() -> None:
    ensure_dirs()
    init_db()
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


@app.get("/api/studio/status")
def api_status() -> Dict[str, Any]:
    config = normalize_config()
    with db() as conn:
        sessions = [dict(row) for row in conn.execute("SELECT * FROM studio_sessions ORDER BY updated_at DESC, id DESC LIMIT 100")]
        proposals = [dict(row) for row in conn.execute("SELECT * FROM studio_proposals ORDER BY id DESC LIMIT 100")]
        automation = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM studio_automation_state ORDER BY updated_at DESC, role ASC, target_type ASC, target_id ASC"
            )
        ]
    return {
        "targets": studio_targets(config),
        "projects": [
            {
                "id": project["id"],
                "path": project["path"],
                "accounts": project.get("accounts") or [],
                "design_doc": project.get("design_doc") or "",
            }
            for project in config.get("projects", [])
        ],
        "studio": config.get("studio", {}),
        "sessions": sessions,
        "proposals": proposals,
        "automation": automation,
    }


@app.get("/api/studio/sessions/{session_id}")
def api_session(session_id: int) -> Dict[str, Any]:
    with db() as conn:
        session_row = conn.execute("SELECT * FROM studio_sessions WHERE id=?", (session_id,)).fetchone()
        if not session_row:
            raise HTTPException(404, "session not found")
        proposals = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM studio_proposals WHERE session_id=? ORDER BY id DESC",
                (session_id,),
            )
        ]
    messages = [dict(row) for row in session_messages(session_id)]
    return {"session": dict(session_row), "messages": messages, "proposals": proposals}


@app.post("/api/studio/sessions")
def api_create_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    target_type = str(payload.get("target_type") or "").strip() or "project"
    target_id = str(payload.get("target_id") or "").strip()
    project_id = str(payload.get("project_id") or "").strip()
    if project_id and not target_id:
        target_type = "project"
        target_id = project_id
    role = str(payload.get("role") or "designer").strip() or "designer"
    title = str(payload.get("title") or "").strip()
    message = str(payload.get("message") or "").strip()
    if not target_id or not message:
        raise HTTPException(400, "target_type/target_id and message are required")
    session_id = create_session(target_type, target_id, role, title, message)
    return {"session_id": session_id}


@app.post("/api/studio/sessions/{session_id}/message")
def api_add_message(session_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "message is required")
    enqueue_message(session_id, message)
    return {"ok": True}


@app.post("/api/studio/proposals/{proposal_id}/publish")
def api_publish_proposal(proposal_id: int, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    mode = str((payload or {}).get("mode") or "").strip() or None
    result = publish_proposal(proposal_id, mode=mode)
    return result


def create_session(
    target_type: str,
    target_id: str,
    role: str,
    title: str,
    message: str,
    *,
    origin_type: str = "admin",
    origin_name: str = "admin",
    automation_fingerprint: str = "",
) -> int:
    config = normalize_config()
    try:
        target_cfg = resolve_target_cfg(config, target_type, target_id)
    except KeyError as exc:
        raise HTTPException(404, f"unknown studio target: {target_type}:{target_id}") from exc
    studio_roles = (config.get("studio", {}).get("roles") or {})
    role = normalize_studio_role_name(role, studio_roles)
    now = iso(utc_now())
    if not title:
        title = truncate_title(message)
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO studio_sessions(
                project_id, target_type, target_id, role, title, origin_type, origin_name, automation_fingerprint, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
            """,
            (
                target_cfg["target_id"],
                target_cfg["target_type"],
                target_cfg["target_id"],
                role,
                title,
                str(origin_type or "admin"),
                str(origin_name or "admin"),
                str(automation_fingerprint or ""),
                now,
                now,
            ),
        )
        session_id = int(cur.lastrowid)
    insert_message(session_id, str(origin_type or "admin"), str(origin_name or "admin"), message)
    update_session_status(session_id, status="queued", active_run_id=None, last_error=None)
    return session_id


def enqueue_message(session_id: int, message: str) -> None:
    with db() as conn:
        row = conn.execute("SELECT status FROM studio_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "session not found")
    if row["status"] == "running":
        raise HTTPException(409, "session is currently running; wait for the current turn to finish")
    insert_message(session_id, "admin", "admin", message)
    update_session_status(session_id, status="queued", active_run_id=None, last_error=None)


def maybe_queue_automated_sessions(config: Dict[str, Any]) -> None:
    now = utc_now()
    for spec in studio_autonomy_specs(config):
        role_name = str(spec["role"])
        target_type = str(spec["target_type"])
        target_id = str(spec["target_id"])
        if studio_session_is_active(role_name, target_type, target_id):
            continue
        try:
            target_cfg = resolve_target_cfg(config, target_type, target_id)
        except KeyError:
            update_studio_automation_state(
                role_name,
                target_type,
                target_id,
                last_status="target_missing",
                last_message=f"unknown automation target {target_type}:{target_id}",
            )
            continue
        trigger_fingerprint, trigger_payload = automation_trigger_fingerprint(target_cfg, role_name)
        state_row = studio_automation_state_row(role_name, target_type, target_id)
        should_queue, reason = studio_autonomy_should_queue(
            spec,
            state_row,
            now=now,
            trigger_fingerprint=trigger_fingerprint,
        )
        if not should_queue:
            continue
        session_id = create_session(
            target_type,
            target_id,
            role_name,
            str(spec.get("title") or ""),
            automation_message_for_role(spec, reason, trigger_payload),
            origin_type="automation",
            origin_name=f"{role_name}.autopilot",
            automation_fingerprint=trigger_fingerprint,
        )
        update_studio_automation_state(
            role_name,
            target_type,
            target_id,
            trigger_fingerprint=trigger_fingerprint,
            last_session_id=session_id,
            last_run_at=iso(now),
            last_status="queued",
            last_message=reason,
        )


def publish_proposal(proposal_id: int, mode: Optional[str] = None) -> Dict[str, Any]:
    config = normalize_config()
    with db() as conn:
        proposal_row = conn.execute("SELECT * FROM studio_proposals WHERE id=?", (proposal_id,)).fetchone()
        if not proposal_row:
            raise HTTPException(404, "proposal not found")
    payload = json.loads(proposal_row["payload_json"])
    try:
        target_cfg = resolve_target_cfg(
            config,
            str(proposal_row["target_type"] or "project"),
            str(proposal_row["target_id"] or proposal_row["project_id"] or ""),
        )
    except KeyError as exc:
        raise HTTPException(404, "proposal target is no longer configured") from exc
    proposed_mode = mode or str((payload.get("proposal", {}) or {}).get("recommended_publish_mode") or "publish_artifacts_and_feedback")
    publish_feedback = proposed_mode == "publish_artifacts_and_feedback" and bool((config.get("studio", {}) or {}).get("publish_feedback_note", True))
    try:
        publish_targets = proposal_targets_from_payload(config, target_cfg, payload)
    except KeyError as exc:
        raise HTTPException(400, f"proposal includes an unknown publish target: {exc}") from exc
    published_targets: List[Dict[str, Any]] = []
    feedback_rel = None
    for item in publish_targets:
        published_root, target_feedback_rel = publish_target_files(
            item["target_cfg"],
            item["files"],
            publish_feedback=publish_feedback,
            feedback_note=item["feedback_note"],
        )
        if target_feedback_rel and not feedback_rel:
            feedback_rel = target_feedback_rel
        published_targets.append(
            {
                "target_type": item["target_cfg"]["target_type"],
                "target_id": item["target_cfg"]["target_id"],
                "published_dir": str(published_root),
                "feedback_rel": target_feedback_rel,
                "file_count": len(item["files"]),
            }
        )
    now = iso(utc_now())
    with db() as conn:
        conn.execute(
            "UPDATE studio_proposals SET status='published', published_at=?, published_dir=?, published_feedback_rel=?, published_targets_json=?, updated_at=? WHERE id=?",
            (
                now,
                published_targets[0]["published_dir"] if len(published_targets) == 1 else "<multi-target>",
                feedback_rel,
                json.dumps(published_targets, indent=2),
                now,
                proposal_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO studio_publish_events(
                proposal_id,
                session_id,
                source_target_type,
                source_target_id,
                mode,
                published_targets_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                int(proposal_row["session_id"]),
                str(proposal_row["target_type"] or "project"),
                str(proposal_row["target_id"] or proposal_row["project_id"] or ""),
                proposed_mode,
                json.dumps(published_targets, indent=2),
                now,
            ),
        )
    return {
        "proposal_id": proposal_id,
        "published_dir": published_targets[0]["published_dir"] if len(published_targets) == 1 else "<multi-target>",
        "feedback_rel": feedback_rel,
        "published_targets": published_targets,
        "mode": proposed_mode,
    }


def td(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def studio_targets(config: Dict[str, Any]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for project in config.get("projects", []):
        items.append(
            {
                "target_type": "project",
                "target_id": project["id"],
                "label": f"project:{project['id']} — {project['path']}",
            }
        )
    for group in config.get("project_groups", []):
        items.append(
            {
                "target_type": "group",
                "target_id": str(group.get("id")),
                "label": f"group:{group.get('id')} — {', '.join(group.get('projects') or [])}",
            }
        )
    items.append({"target_type": "fleet", "target_id": "fleet", "label": "fleet:fleet — /docker/fleet"})
    return items


def target_options_html(config: Dict[str, Any], selected: Optional[str] = None) -> str:
    items: List[str] = []
    for target in studio_targets(config):
        value = f"{target['target_type']}:{target['target_id']}"
        sel = " selected" if value == selected else ""
        items.append(f'<option value="{html.escape(value)}"{sel}>{html.escape(target["label"])}</option>')
    return "\n".join(items)


def role_options_html(selected: Optional[str] = None) -> str:
    config = normalize_config()
    roles = (config.get("studio", {}).get("roles") or {})
    items = []
    for role_name in roles.keys():
        sel = " selected" if role_name == selected else ""
        items.append(f'<option value="{html.escape(role_name)}"{sel}>{html.escape(ROLE_LABELS.get(role_name, role_name))}</option>')
    return "\n".join(items)


@app.post("/studio/create")
def studio_create(
    target_key: str = Form(...),
    role: str = Form("designer"),
    title: str = Form(""),
    message: str = Form(...),
):
    target_type, _, target_id = target_key.partition(":")
    session_id = create_session(target_type, target_id, role, title, message)
    return RedirectResponse(url=f"/studio?session={session_id}", status_code=303)


@app.post("/studio/sessions/{session_id}/message")
def studio_add_message(session_id: int, message: str = Form(...)):
    enqueue_message(session_id, message)
    return RedirectResponse(url=f"/studio?session={session_id}", status_code=303)


@app.post("/studio/proposals/{proposal_id}/publish")
def studio_publish(proposal_id: int, mode: str = Form("")):
    result = publish_proposal(proposal_id, mode=mode or None)
    with db() as conn:
        row = conn.execute("SELECT session_id FROM studio_proposals WHERE id=?", (proposal_id,)).fetchone()
    session_id = int(row["session_id"]) if row else 0
    target = f"/studio?session={session_id}&published={proposal_id}"
    if result.get("feedback_rel"):
        target += f"&feedback={result['feedback_rel']}"
    return RedirectResponse(url=target, status_code=303)


@app.get("/studio", response_class=HTMLResponse)
def studio_dashboard(session: Optional[int] = None, published: Optional[int] = None, feedback: Optional[str] = None) -> str:
    config = normalize_config()
    with db() as conn:
        sessions = conn.execute("SELECT * FROM studio_sessions ORDER BY updated_at DESC, id DESC LIMIT 100").fetchall()
    selected_session = None
    selected_messages: List[sqlite3.Row] = []
    selected_proposals: List[sqlite3.Row] = []
    selected_run = None
    auto_refresh = False
    if session is not None:
        with db() as conn:
            selected_session = conn.execute("SELECT * FROM studio_sessions WHERE id=?", (session,)).fetchone()
            if selected_session:
                selected_messages = session_messages(session)
                selected_proposals = conn.execute(
                    "SELECT * FROM studio_proposals WHERE session_id=? ORDER BY id DESC",
                    (session,),
                ).fetchall()
                if selected_session["active_run_id"]:
                    selected_run = conn.execute("SELECT * FROM runs WHERE id=?", (selected_session["active_run_id"],)).fetchone()
                auto_refresh = selected_session["status"] in {"queued", "awaiting_account", "running"}

    # keep status updates manual; running sessions should be polled via UI refresh on demand
    target_options = target_options_html(config, "project:core")

    session_rows = []
    for row in sessions:
        link = f"/studio?session={row['id']}"
        row_target_type = row["target_type"] or "project"
        row_target_id = row["target_id"] or row["project_id"]
        session_rows.append(
            f"<tr><td><a href=\"{link}\">{row['id']}</a></td><td>{td(row_target_type)}</td><td>{td(row_target_id)}</td><td>{td(row['role'])}</td><td>{td(row['status'])}</td><td>{td(row['title'])}</td><td>{td(row['updated_at'])}</td><td>{td(row['last_error'])}</td></tr>"
        )

    messages_html = "<p>No session selected.</p>"
    proposals_html = ""
    session_header = ""
    if selected_session:
        selected_target_type = selected_session["target_type"] or "project"
        selected_target_id = selected_session["target_id"] or selected_session["project_id"]
        session_header = (
            f"<h2>Session {selected_session['id']} — {td(selected_session['title'])}</h2>"
            f"<p><strong>Target:</strong> {td(selected_target_type)}:{td(selected_target_id)} &nbsp; "
            f"<strong>Role:</strong> {td(selected_session['role'])} &nbsp; "
            f"<strong>Status:</strong> {td(selected_session['status'])}</p>"
            f"<p><strong>Summary:</strong> {td(selected_session['summary'])}</p>"
        )
        if selected_run:
            session_header += (
                f"<p><strong>Active run:</strong> #{selected_run['id']} &nbsp; <strong>Model:</strong> {td(selected_run['model'])} &nbsp; "
                f"<strong>Account:</strong> {td(selected_run['account_alias'])}</p>"
            )
        if published:
            session_header += f"<p><strong>Published proposal:</strong> #{published}</p>"
        if feedback:
            session_header += f"<p><strong>Feedback note:</strong> {td(feedback)}</p>"

        message_cards = []
        for row in selected_messages:
            border = "#bbb" if row["actor_type"] == "admin" else "#6a8"
            message_cards.append(
                f"<div style=\"border:1px solid {border};padding:10px;margin:8px 0;border-radius:8px;\">"
                f"<div><strong>{td(row['actor_type'])}:{td(row['actor_name'])}</strong> &nbsp; <span>{td(row['created_at'])}</span></div>"
                f"<pre style=\"white-space:pre-wrap;margin:8px 0 0 0;\">{html.escape(row['content'])}</pre>"
                f"</div>"
            )
        if auto_refresh:
            message_cards.insert(0, "<p>Session is active. Reopen this session or refresh the page to check latest status.</p>")
        messages_html = "\n".join(message_cards)

        proposal_blocks = []
        for row in selected_proposals:
            payload = json.loads(row["payload_json"])
            proposal = payload.get("proposal") or {}
            files = proposal.get("files") or []
            proposal_targets = proposal.get("targets") or []
            file_list = "".join(f"<li>{td(item.get('path'))}</li>" for item in files) or "<li>&lt;none&gt;</li>"
            target_list = "".join(
                f"<li>{td(item.get('target_type'))}:{td(item.get('target_id'))} ({td(len(item.get('files') or []))} files)</li>"
                for item in proposal_targets
            ) or "<li>&lt;single target proposal&gt;</li>"
            publish_mode = str(proposal.get("recommended_publish_mode") or "publish_artifacts_and_feedback")
            publish_controls = ""
            if row["status"] != "published":
                publish_controls = (
                    f"<form method=\"post\" action=\"/studio/proposals/{row['id']}/publish\">"
                    f"<input type=\"hidden\" name=\"mode\" value=\"{html.escape(publish_mode)}\">"
                    f"<button type=\"submit\">Publish</button>"
                    f"</form>"
                )
            proposal_blocks.append(
                f"<div style=\"border:1px solid #889;padding:10px;margin:10px 0;border-radius:8px;\">"
                f"<div><strong>Proposal #{row['id']}</strong> — {td(row['status'])}</div>"
                f"<div><strong>Title:</strong> {td(row['title'])}</div>"
                f"<div><strong>Summary:</strong> {td(row['summary'])}</div>"
                f"<div><strong>Mode:</strong> {td(publish_mode)}</div>"
                f"<div><strong>Coding tier hint:</strong> {td(proposal.get('coding_tier_hint'))}</div>"
                f"<div><strong>Routing notes:</strong> {td(proposal.get('routing_notes'))}</div>"
                f"<div><strong>Files:</strong><ul>{file_list}</ul></div>"
                f"<div><strong>Targets:</strong><ul>{target_list}</ul></div>"
                f"<div><strong>Feedback note:</strong><pre style=\"white-space:pre-wrap;\">{html.escape(str(proposal.get('feedback_note') or ''))}</pre></div>"
                f"{publish_controls}"
                f"</div>"
            )
        proposals_html = "<h3>Proposals</h3>" + "\n".join(proposal_blocks)

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset=\"utf-8\">
      <title>{APP_TITLE}</title>
      <style>
        body {{ font-family: system-ui, sans-serif; margin: 24px; line-height: 1.45; }}
        textarea {{ width: 100%; min-height: 120px; }}
        select, input, button {{ font: inherit; padding: 6px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }}
        .grid {{ display: grid; grid-template-columns: 360px 1fr; gap: 24px; align-items: start; }}
        .panel {{ border: 1px solid #ddd; border-radius: 10px; padding: 16px; }}
        pre {{ overflow-x: auto; }}
      </style>
    </head>
    <body>
      <p><a href=\"/\">← Fleet dashboard</a></p>
      <h1>{APP_TITLE}</h1>
        <div class=\"grid\">
        <div class=\"panel\">
          <h2>New session</h2>
          <form method=\"post\" action=\"/studio/create\">
            <label>Target<br><select name=\"target_key\">{target_options}</select></label><br><br>
            <label>Role<br><select name=\"role\">{role_options_html('designer')}</select></label><br><br>
            <label>Title (optional)<br><input type=\"text\" name=\"title\" style=\"width:100%;\"></label><br><br>
            <label>Admin message<br><textarea name=\"message\" required placeholder=\"Discuss direction, vision, instruction quality, queue changes, or ask for a publishable proposal.\"></textarea></label><br><br>
            <button type=\"submit\">Start session</button>
          </form>

          <h2>Sessions</h2>
          <table>
            <thead><tr><th>ID</th><th>Type</th><th>Target</th><th>Role</th><th>Status</th><th>Title</th><th>Updated</th><th>Error</th></tr></thead>
            <tbody>{''.join(session_rows) or '<tr><td colspan="8">No sessions yet.</td></tr>'}</tbody>
          </table>
        </div>
        <div class=\"panel\">
          {session_header}
          {f'''<form method="post" action="/studio/sessions/{session}/message">
              <label>Follow-up message<br><textarea name="message" required placeholder="Ask the designer/architect/PM to refine the proposal or draft better instructions."></textarea></label><br><br>
              <button type="submit">Send follow-up</button>
            </form><hr>''' if selected_session else ''}
          <h3>Conversation</h3>
          {messages_html}
          {proposals_html}
        </div>
      </div>
    </body>
    </html>
    """
