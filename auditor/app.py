import asyncio
import contextlib
import datetime as dt
import json
import os
import pathlib
import sqlite3
import traceback
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8093"))
APP_TITLE = "Codex Fleet Auditor"
DB_PATH = pathlib.Path(os.environ.get("FLEET_DB_PATH", "/var/lib/codex-fleet/fleet.db"))
CONFIG_PATH = pathlib.Path(os.environ.get("FLEET_CONFIG_PATH", "/app/config/fleet.yaml"))
STUDIO_SOURCE_PATH = pathlib.Path(os.environ.get("FLEET_STUDIO_SOURCE_PATH", "/app/studio-src/app.py"))


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


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
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


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def normalize_config() -> Dict[str, Any]:
    fleet = load_yaml(CONFIG_PATH)
    fleet.setdefault("policies", {})
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet.setdefault("studio", {})
    fleet["studio"].setdefault("roles", {})
    for group in fleet["project_groups"]:
        group.setdefault("projects", [])
        group.setdefault("mode", "independent")
        group.setdefault("contract_sets", [])
        group.setdefault("milestone_source", {})
        group.setdefault("group_roles", [])
    for project in fleet["projects"]:
        project.setdefault("enabled", True)
        project.setdefault("queue_sources", [])
    return fleet


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
            if key:
                items[key] = dict(value)
    return items


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


def project_runtime_rows() -> Dict[str, Dict[str, Any]]:
    if not DB_PATH.exists():
        return {}
    with db() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    return {row["id"]: dict(row) for row in rows}


def project_runtime_status(project: Dict[str, Any]) -> str:
    return str(project.get("status") or "").strip() or "idle"


def project_queue_length(project: Dict[str, Any]) -> int:
    queue = project.get("queue")
    if isinstance(queue, list):
        return len(queue)
    if "queue_json" in project:
        try:
            return len(json.loads(project.get("queue_json") or "[]"))
        except Exception:
            return 0
    return 0


def group_dispatch_state(group: Dict[str, Any], meta: Dict[str, Any], group_projects: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    blockers: List[str] = []
    blockers.extend(f"contract blocker: {item}" for item in text_items(meta.get("contract_blockers")))

    if str(group.get("mode", "") or "").strip().lower() == "lockstep":
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
                if status == "source_backlog_open":
                    blockers.append(f"{project_id}: runtime queue exhausted while source backlog remains open")
                else:
                    blockers.append(f"{project_id}: runtime queue exhausted")
    return {"dispatch_ready": not blockers, "dispatch_blockers": blockers}


def make_finding(
    *,
    scope_type: str,
    scope_id: str,
    finding_key: str,
    severity: str,
    title: str,
    summary: str,
    evidence: List[Dict[str, Any]],
    candidate_tasks: List[Dict[str, str]],
) -> Dict[str, Any]:
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "finding_key": finding_key,
        "severity": severity,
        "title": title,
        "summary": summary,
        "evidence": evidence,
        "candidate_tasks": candidate_tasks,
    }


def scan_studio_capabilities() -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    try:
        studio_text = STUDIO_SOURCE_PATH.read_text(encoding="utf-8")
    except Exception:
        studio_text = ""
    if studio_text and "target_type" not in studio_text and "target_id" not in studio_text:
        findings.append(
            make_finding(
                scope_type="fleet",
                scope_id="fleet",
                finding_key="studio.target_scoped_sessions_missing",
                severity="medium",
                title="Studio sessions remain project-scoped",
                summary="Studio runtime still keys sessions by project_id only, so group and fleet targets are not first-class session targets yet.",
                evidence=[
                    {"kind": "code_scan", "path": str(STUDIO_SOURCE_PATH), "detail": "target_type and target_id markers not found"},
                ],
                candidate_tasks=[
                    {"title": "Add target-scoped Studio sessions", "detail": "Replace project-only session targeting with target_type and target_id across Studio session creation and storage."},
                ],
            )
        )
    if studio_text and "targets" not in studio_text:
        findings.append(
            make_finding(
                scope_type="fleet",
                scope_id="fleet",
                finding_key="studio.multi_target_publish_missing",
                severity="medium",
                title="Studio publish remains single-target",
                summary="Studio publish flow does not yet expose a proposal schema that can publish one approved change set into group artifacts and multiple project targets together.",
                evidence=[
                    {"kind": "code_scan", "path": str(STUDIO_SOURCE_PATH), "detail": "multi-target proposal markers not found"},
                ],
                candidate_tasks=[
                    {"title": "Add multi-target Studio publish", "detail": "Support proposals with per-target artifacts, feedback notes, and queue overlays for project, group, and fleet targets."},
                ],
            )
        )
    return findings


def collect_findings(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    now = utc_now()
    registry = load_program_registry(config)
    runtime_rows = project_runtime_rows()
    findings: List[Dict[str, Any]] = []

    for project_cfg in config.get("projects") or []:
        project_id = str(project_cfg.get("id"))
        row = runtime_rows.get(project_id, {})
        queue: List[str]
        try:
            queue = json.loads(row.get("queue_json") or "[]")
        except Exception:
            queue = []
        queue_index = int(row.get("queue_index") or 0)
        project_meta = registry["projects"].get(project_id, {})
        uncovered_scope = text_items(project_meta.get("uncovered_scope"))

        if uncovered_scope:
            findings.append(
                make_finding(
                    scope_type="project",
                    scope_id=project_id,
                    finding_key="project.uncovered_scope",
                    severity="medium",
                    title="Project has uncovered scope",
                    summary=f"{project_id} still has design or milestone responsibilities that are not fully materialized into executable backlog.",
                    evidence=[
                        {"kind": "registry", "path": str(resolve_config_file((next((g.get('milestone_source') or {}).get('path', '') for g in config.get('project_groups') or [] if project_id in (g.get('projects') or [])), '')) or ''), "uncovered_scope_count": len(uncovered_scope)},
                    ],
                    candidate_tasks=[{"title": f"Materialize uncovered scope: {item}", "detail": f"Add milestone mapping or executable queue work for {item}."} for item in uncovered_scope[:12]],
                )
            )

        if uncovered_scope and queue_index >= len(queue):
            findings.append(
                make_finding(
                    scope_type="project",
                    scope_id=project_id,
                    finding_key="project.queue_exhausted_with_uncovered_scope",
                    severity="high",
                    title="Queue exhausted while scope remains uncovered",
                    summary=f"{project_id} has no remaining runtime queue items at the current cursor, but uncovered scope still exists in the milestone registry.",
                    evidence=[
                        {"kind": "runtime", "queue_index": queue_index, "queue_len": len(queue), "status": row.get("status")},
                        {"kind": "registry", "uncovered_scope": uncovered_scope[:12]},
                    ],
                    candidate_tasks=[{"title": f"Queue uncovered scope: {item}", "detail": f"Publish or append runnable backlog for {item}."} for item in uncovered_scope[:12]],
                )
            )

        if project_meta and not bool(project_meta.get("milestone_coverage_complete")):
            findings.append(
                make_finding(
                    scope_type="project",
                    scope_id=project_id,
                    finding_key="project.milestone_coverage_incomplete",
                    severity="medium",
                    title="Project milestone coverage is incomplete",
                    summary=f"{project_id} does not yet have complete milestone coverage in the registry, so milestone ETA and completion truth remain partial.",
                    evidence=[
                        {"kind": "registry", "remaining_milestones": len(remaining_milestone_items(project_meta))},
                    ],
                    candidate_tasks=[
                        {"title": "Complete project milestone registry", "detail": f"Finish milestone coverage modeling for {project_id} so ETA and completion truth are no longer partial."},
                    ],
                )
            )

    for group_cfg in config.get("project_groups") or []:
        group_id = str(group_cfg.get("id"))
        group_meta = registry["groups"].get(group_id, {})
        group_projects: List[Dict[str, Any]] = []
        for project_id in group_cfg.get("projects") or []:
            row = runtime_rows.get(project_id, {})
            group_projects.append(
                {
                    "id": project_id,
                    "status": row.get("status"),
                    "queue_index": int(row.get("queue_index") or 0),
                    "queue_json": row.get("queue_json") or "[]",
                    "cooldown_until": row.get("cooldown_until"),
                    "enabled": bool(next((p.get("enabled", True) for p in config.get("projects") or [] if p.get("id") == project_id), True)),
                }
            )

        contract_blockers = text_items(group_meta.get("contract_blockers"))
        if contract_blockers:
            findings.append(
                make_finding(
                    scope_type="group",
                    scope_id=group_id,
                    finding_key="group.contract_blockers",
                    severity="high",
                    title="Group contract blockers remain open",
                    summary=f"{group_id} still has open contract blockers that prevent trustworthy lockstep progress.",
                    evidence=[{"kind": "registry", "contract_blockers": contract_blockers[:12]}],
                    candidate_tasks=[{"title": f"Resolve contract blocker: {item}", "detail": item} for item in contract_blockers[:12]],
                )
            )

        dispatch = group_dispatch_state(group_cfg, group_meta, group_projects, now)
        if str(group_cfg.get("mode", "") or "").strip().lower() == "lockstep" and not dispatch["dispatch_ready"]:
            findings.append(
                make_finding(
                    scope_type="group",
                    scope_id=group_id,
                    finding_key="group.lockstep_dispatch_blocked",
                    severity="high",
                    title="Lockstep dispatch is blocked",
                    summary=f"{group_id} cannot dispatch all member projects together under the current runtime and contract state.",
                    evidence=[{"kind": "runtime", "dispatch_blockers": dispatch["dispatch_blockers"][:20]}],
                    candidate_tasks=[{"title": "Resolve lockstep blocker", "detail": item} for item in dispatch["dispatch_blockers"][:20]],
                )
            )

        if group_meta and not bool(group_meta.get("milestone_coverage_complete")):
            findings.append(
                make_finding(
                    scope_type="group",
                    scope_id=group_id,
                    finding_key="group.milestone_coverage_incomplete",
                    severity="medium",
                    title="Group milestone coverage is incomplete",
                    summary=f"{group_id} still lacks complete group milestone coverage, so milestone ETA remains partial.",
                    evidence=[{"kind": "registry", "remaining_milestones": len(remaining_milestone_items(group_meta))}],
                    candidate_tasks=[
                        {"title": "Complete group milestone registry", "detail": f"Finish group milestone mapping for {group_id} and tie tasks to group phases."},
                    ],
                )
            )

        if group_meta and not bool(group_meta.get("design_coverage_complete")):
            findings.append(
                make_finding(
                    scope_type="group",
                    scope_id=group_id,
                    finding_key="group.program_coverage_incomplete",
                    severity="medium",
                    title="Program coverage is incomplete",
                    summary=f"{group_id} still has program-level responsibilities that are not fully modeled, so program ETA remains unknown.",
                    evidence=[{"kind": "registry", "uncovered_scope_count": len(text_items(group_meta.get("uncovered_scope")))}],
                    candidate_tasks=[
                        {"title": "Complete program coverage registry", "detail": f"Model all remaining program responsibilities and milestone links for {group_id}."},
                    ],
                )
            )

    findings.extend(scan_studio_capabilities())
    return findings


def persist_findings(findings: List[Dict[str, Any]], now: dt.datetime) -> Tuple[int, int]:
    seen_findings = {(item["scope_type"], item["scope_id"], item["finding_key"]) for item in findings}
    seen_tasks = {
        (item["scope_type"], item["scope_id"], item["finding_key"], index)
        for item in findings
        for index, _task in enumerate(item.get("candidate_tasks") or [])
    }
    now_text = iso(now) or ""
    with db() as conn:
        for item in findings:
            evidence_json = json.dumps(item.get("evidence") or [])
            tasks_json = json.dumps(item.get("candidate_tasks") or [])
            row = conn.execute(
                "SELECT first_seen_at FROM audit_findings WHERE scope_type=? AND scope_id=? AND finding_key=?",
                (item["scope_type"], item["scope_id"], item["finding_key"]),
            ).fetchone()
            first_seen_at = row["first_seen_at"] if row else now_text
            conn.execute(
                """
                INSERT INTO audit_findings(scope_type, scope_id, finding_key, severity, title, summary, status, source, evidence_json, candidate_tasks_json, first_seen_at, last_seen_at, resolved_at)
                VALUES(?, ?, ?, ?, ?, ?, 'open', 'fleet-auditor', ?, ?, ?, ?, NULL)
                ON CONFLICT(scope_type, scope_id, finding_key) DO UPDATE SET
                    severity=excluded.severity,
                    title=excluded.title,
                    summary=excluded.summary,
                    status='open',
                    evidence_json=excluded.evidence_json,
                    candidate_tasks_json=excluded.candidate_tasks_json,
                    last_seen_at=excluded.last_seen_at,
                    resolved_at=NULL
                """,
                (
                    item["scope_type"],
                    item["scope_id"],
                    item["finding_key"],
                    item["severity"],
                    item["title"],
                    item["summary"],
                    evidence_json,
                    tasks_json,
                    first_seen_at,
                    now_text,
                ),
            )
            for index, task in enumerate(item.get("candidate_tasks") or []):
                task_row = conn.execute(
                    "SELECT first_seen_at FROM audit_task_candidates WHERE scope_type=? AND scope_id=? AND finding_key=? AND task_index=?",
                    (item["scope_type"], item["scope_id"], item["finding_key"], index),
                ).fetchone()
                task_first_seen = task_row["first_seen_at"] if task_row else now_text
                conn.execute(
                    """
                    INSERT INTO audit_task_candidates(scope_type, scope_id, finding_key, task_index, title, detail, status, source, first_seen_at, last_seen_at, resolved_at)
                    VALUES(?, ?, ?, ?, ?, ?, 'open', 'fleet-auditor', ?, ?, NULL)
                    ON CONFLICT(scope_type, scope_id, finding_key, task_index) DO UPDATE SET
                        title=excluded.title,
                        detail=excluded.detail,
                        status='open',
                        last_seen_at=excluded.last_seen_at,
                        resolved_at=NULL
                    """,
                    (
                        item["scope_type"],
                        item["scope_id"],
                        item["finding_key"],
                        index,
                        str(task.get("title") or ""),
                        str(task.get("detail") or ""),
                        task_first_seen,
                        now_text,
                    ),
                )

        stale_findings = conn.execute(
            "SELECT scope_type, scope_id, finding_key FROM audit_findings WHERE source='fleet-auditor' AND status='open'"
        ).fetchall()
        for row in stale_findings:
            key = (row["scope_type"], row["scope_id"], row["finding_key"])
            if key not in seen_findings:
                conn.execute(
                    "UPDATE audit_findings SET status='resolved', resolved_at=?, last_seen_at=? WHERE scope_type=? AND scope_id=? AND finding_key=?",
                    (now_text, now_text, row["scope_type"], row["scope_id"], row["finding_key"]),
                )

        stale_tasks = conn.execute(
            "SELECT scope_type, scope_id, finding_key, task_index FROM audit_task_candidates WHERE source='fleet-auditor' AND status='open'"
        ).fetchall()
        for row in stale_tasks:
            key = (row["scope_type"], row["scope_id"], row["finding_key"], int(row["task_index"]))
            if key not in seen_tasks:
                conn.execute(
                    "UPDATE audit_task_candidates SET status='resolved', resolved_at=?, last_seen_at=? WHERE scope_type=? AND scope_id=? AND finding_key=? AND task_index=?",
                    (now_text, now_text, row["scope_type"], row["scope_id"], row["finding_key"], row["task_index"]),
                )
    return len(seen_findings), len(seen_tasks)


async def run_audit_pass() -> None:
    now = utc_now()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO auditor_runs(status, started_at, finding_count, candidate_count) VALUES('running', ?, 0, 0)",
            (iso(now),),
        )
        run_id = int(cur.lastrowid)
    try:
        config = normalize_config()
        findings = collect_findings(config)
        finding_count, candidate_count = persist_findings(findings, utc_now())
        with db() as conn:
            conn.execute(
                "UPDATE auditor_runs SET status='succeeded', finished_at=?, finding_count=?, candidate_count=? WHERE id=?",
                (iso(utc_now()), finding_count, candidate_count, run_id),
            )
    except Exception as exc:
        traceback.print_exc()
        with db() as conn:
            conn.execute(
                "UPDATE auditor_runs SET status='failed', finished_at=?, error_message=? WHERE id=?",
                (iso(utc_now()), str(exc), run_id),
            )


class RuntimeState:
    def __init__(self) -> None:
        self.stop = asyncio.Event()
        self.task: Optional[asyncio.Task] = None


state = RuntimeState()
app = FastAPI(title=APP_TITLE)


async def auditor_loop() -> None:
    while not state.stop.is_set():
        await run_audit_pass()
        config = normalize_config()
        interval = int((config.get("policies") or {}).get("auditor_interval_seconds", 120))
        await asyncio.sleep(max(15, interval))


def auditor_status() -> Dict[str, Any]:
    with db() as conn:
        latest_run = conn.execute("SELECT * FROM auditor_runs ORDER BY id DESC LIMIT 1").fetchone()
        findings = conn.execute(
            "SELECT * FROM audit_findings WHERE status='open' ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, last_seen_at DESC LIMIT 100"
        ).fetchall()
        tasks = conn.execute(
            "SELECT * FROM audit_task_candidates WHERE status='open' ORDER BY last_seen_at DESC LIMIT 100"
        ).fetchall()
    return {
        "generated_at": iso(utc_now()),
        "last_run": dict(latest_run) if latest_run else None,
        "open_finding_count": len(findings),
        "open_task_candidate_count": len(tasks),
        "findings": [dict(row) for row in findings],
        "task_candidates": [dict(row) for row in tasks],
    }


@app.on_event("startup")
async def startup() -> None:
    init_db()
    state.task = asyncio.create_task(auditor_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    state.stop.set()
    task = state.task
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/api/auditor/status")
def api_status() -> Dict[str, Any]:
    return auditor_status()
