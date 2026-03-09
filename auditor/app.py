import asyncio
import contextlib
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import traceback
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

UTC = dt.timezone.utc
APP_PORT = int(os.environ.get("APP_PORT", "8093"))
APP_TITLE = "Codex Fleet Auditor"
DEFAULT_SINGLETON_GROUP_ROLES = ["auditor", "project_manager"]
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

            CREATE TABLE IF NOT EXISTS group_runtime (
                group_id TEXT PRIMARY KEY,
                signoff_state TEXT NOT NULL DEFAULT 'open',
                signed_off_at TEXT,
                reopened_at TEXT,
                last_audit_requested_at TEXT,
                last_refill_requested_at TEXT,
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
            """
        )


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


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


def normalize_config() -> Dict[str, Any]:
    fleet = load_yaml(CONFIG_PATH)
    fleet.setdefault("policies", {})
    fleet.setdefault("projects", [])
    fleet.setdefault("project_groups", [])
    fleet.setdefault("studio", {})
    fleet["studio"].setdefault("roles", {})
    fleet["project_groups"] = normalized_project_groups(fleet["projects"], fleet["project_groups"])
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


def group_runtime_rows() -> Dict[str, Dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM group_runtime ORDER BY group_id").fetchall()
    return {str(row["group_id"]): dict(row) for row in rows}


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
        for key in ("signed_off_at", "reopened_at", "last_audit_requested_at", "last_refill_requested_at"):
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
        "session_events_vnext",
        "runtime_dtos_vnext",
        "event envelope",
        "shared contract",
        "package consumption",
        "explain",
        "ai platform",
    ]
    return any(keyword in lower for keyword in keywords)


def group_dispatch_state(group: Dict[str, Any], meta: Dict[str, Any], group_projects: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    blockers: List[str] = []
    contract_blockers = text_items(meta.get("contract_blockers"))
    contract_phase_allowed = bool(contract_blockers) and bool(group_projects) and all(
        is_contract_remediation_slice(current_queue_item_text(project))
        and int(project.get("queue_index") or 0) < project_queue_length(project)
        for project in group_projects
    )
    if contract_blockers and not contract_phase_allowed:
        blockers.extend(f"contract blocker: {item}" for item in contract_blockers)

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
    return {"dispatch_ready": not blockers, "dispatch_blockers": blockers, "contract_phase_allowed": contract_phase_allowed}


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


def read_text_safe(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def file_sha256(path: pathlib.Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def glob_paths(root: pathlib.Path, pattern: str) -> List[pathlib.Path]:
    try:
        return sorted(path for path in root.rglob(pattern) if path.is_file())
    except Exception:
        return []


def extract_record_parameter_names(text: str, record_name: str) -> List[str]:
    match = re.search(rf"record\s+{re.escape(record_name)}\s*\((.*?)\);", text, flags=re.S)
    if not match:
        return []
    body = match.group(1)
    names: List[str] = []
    for part in body.split(","):
        tokens = [token for token in re.split(r"\s+", part.strip()) if token]
        if len(tokens) >= 2:
            names.append(tokens[-1].strip(")"))
    return names


def extract_dot_event_names(text: str) -> List[str]:
    values = sorted(
        {
            match.group(1)
            for match in re.finditer(r'"([a-z][a-z0-9_-]*\.[a-z0-9._-]+)"', text)
            if "." in match.group(1)
        }
    )
    return values


def scan_chummer_contract_shape(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    project_map = {str(project.get("id")): project for project in config.get("projects") or []}
    core_root = pathlib.Path(str((project_map.get("core") or {}).get("path") or ""))
    ui_root = pathlib.Path(str((project_map.get("ui") or {}).get("path") or ""))
    hub_root = pathlib.Path(str((project_map.get("hub") or {}).get("path") or ""))
    if not core_root.exists() or not ui_root.exists() or not hub_root.exists():
        return []

    findings: List[Dict[str, Any]] = []
    core_contract_root = core_root / "Chummer.Contracts"
    ui_contract_root = ui_root / "Chummer.Contracts"
    if core_contract_root.is_dir() and ui_contract_root.is_dir():
        findings.append(
            make_finding(
                scope_type="group",
                scope_id="chummer-vnext",
                finding_key="group.shared_contract_source_duplicated",
                severity="high",
                title="Shared Chummer contract source is duplicated across repos",
                summary="Both core and UI still carry a source-owned `Chummer.Contracts` tree, so shared DTO ownership remains physically duplicated instead of package-canonical.",
                evidence=[
                    {"kind": "filesystem", "path": str(core_contract_root)},
                    {"kind": "filesystem", "path": str(ui_contract_root)},
                ],
                candidate_tasks=[
                    {"title": "Canonicalize shared contract ownership", "detail": "Publish a single shared contract package from core and delete duplicate shared DTO source trees from UI."},
                ],
            )
        )
        findings.append(
            make_finding(
                scope_type="project",
                scope_id="ui",
                finding_key="project.shared_contract_source_copy_present",
                severity="high",
                title="UI still carries shared contract source copies",
                summary="UI still contains a local `Chummer.Contracts` source tree, so shared DTO ownership is duplicated instead of package-consumed.",
                evidence=[
                    {"kind": "filesystem", "path": str(ui_contract_root)},
                ],
                candidate_tasks=[
                    {"title": "Remove shared contract source copies from UI", "detail": "Replace duplicated `Chummer.Contracts` source in UI with package consumption from the canonical shared contract owner."},
                ],
            )
        )

    core_presentation_contracts = glob_paths(core_root / "Chummer.Contracts" / "Presentation", "*.cs")
    if core_presentation_contracts:
        findings.append(
            make_finding(
                scope_type="project",
                scope_id="core",
                finding_key="project.presentation_contract_surface_present",
                severity="medium",
                title="Core still owns presentation contract surface",
                summary="Core still carries presentation-oriented contract files, so repo authority boundaries remain broader than the intended release architecture.",
                evidence=[{"kind": "filesystem", "path": str(path)} for path in core_presentation_contracts[:12]],
                candidate_tasks=[
                    {"title": "Remove presentation-owned contract surface from core", "detail": "Move presentation-specific contract families out of core-owned source and leave only engine-authored shared DTOs in the canonical package."},
                ],
            )
        )

    hosted_only_names = {
        "AiGatewayContracts.cs",
        "AiMediaContracts.cs",
        "AiMediaQueueContracts.cs",
        "AiPromptRegistryContracts.cs",
        "AiHubProjectSearchContracts.cs",
        "AiTranscriptContracts.cs",
        "AiApprovalContracts.cs",
    }
    leaked_files = [
        path for path in glob_paths(core_root, "*.cs") if path.name in hosted_only_names and "Chummer.Contracts" in str(path)
    ]
    if leaked_files:
        findings.append(
            make_finding(
                scope_type="project",
                scope_id="core",
                finding_key="project.hosted_contract_leakage",
                severity="high",
                title="Hosted-service contract families still leak into core",
                summary="Core still contains hosted AI/media/approval/search contract families under engine-owned contract source, which keeps the authority split descriptive instead of enforced.",
                evidence=[{"kind": "filesystem", "path": str(path)} for path in leaked_files[:12]],
                candidate_tasks=[
                    {"title": "Move hosted-only DTO families out of core", "detail": "Relocate AI/media/approval/search hosted contract families into `Chummer.Run.Contracts` and leave only engine-owned DTOs in core."},
                ],
            )
        )

    core_explain_files = glob_paths(core_root, "AiExplainContracts.cs")
    ui_explain_files = glob_paths(ui_root, "AiExplainContracts.cs")
    if core_explain_files and ui_explain_files:
        core_hash = file_sha256(core_explain_files[0])
        ui_hash = file_sha256(ui_explain_files[0])
        finding_key = "group.explain_contract_source_split"
        summary = "Both core and UI still carry an `AiExplainContracts.cs` source file, so Explain envelope ownership is still physically forked."
        severity = "medium"
        if core_hash and ui_hash and core_hash != ui_hash:
            finding_key = "group.explain_contract_hash_drift"
            summary = "Core and UI both ship `AiExplainContracts.cs`, and the extracted file hashes differ, so Explain DTO drift is now evidence-backed instead of just structural."
            severity = "high"
        findings.append(
            make_finding(
                scope_type="group",
                scope_id="chummer-vnext",
                finding_key=finding_key,
                severity=severity,
                title="Explain contract source remains split across core and UI",
                summary=summary,
                evidence=[
                    {"kind": "filesystem", "path": str(core_explain_files[0]), "sha256": core_hash},
                    {"kind": "filesystem", "path": str(ui_explain_files[0]), "sha256": ui_hash},
                ],
                candidate_tasks=[
                    {"title": "Canonicalize Explain envelope ownership", "detail": "Keep one authoritative Explain contract source and make presentation consume that shared package instead of carrying its own copy."},
                ],
            )
        )

    core_session_file = core_root / "Chummer.Contracts" / "Session" / "SessionContracts.cs"
    if not core_session_file.exists():
        session_candidates = glob_paths(core_root / "Chummer.Contracts" / "Session", "*.cs")
        core_session_file = session_candidates[0] if session_candidates else core_session_file
    hub_session_candidates = [
        path
        for path in [
            hub_root / "Chummer.Run.Contracts" / "SessionRelayContracts.cs",
            hub_root / "Chummer.Run.Contracts" / "AIPlatformContracts.cs",
        ]
        if path.exists()
    ]
    if core_session_file.exists() and hub_session_candidates:
        hub_session_file = hub_session_candidates[0]
        core_text = read_text_safe(core_session_file)
        hub_text = read_text_safe(hub_session_file)
        core_fields = extract_record_parameter_names(core_text, "SessionEventEnvelope")
        hub_fields = extract_record_parameter_names(hub_text, "SessionEventEnvelope")
        if core_fields and hub_fields and core_fields != hub_fields:
            findings.append(
                make_finding(
                    scope_type="group",
                    scope_id="chummer-vnext",
                    finding_key="group.session_event_envelope_structural_drift",
                    severity="high",
                    title="Session event envelopes diverge structurally across core and hub",
                    summary="The extracted `SessionEventEnvelope` parameter lists differ between core and hub, so relay, reducer, and client cache truth are not using one canonical envelope.",
                    evidence=[
                        {"kind": "filesystem", "path": str(core_session_file), "record": "SessionEventEnvelope", "fields": core_fields},
                        {"kind": "filesystem", "path": str(hub_session_file), "record": "SessionEventEnvelope", "fields": hub_fields},
                    ],
                    candidate_tasks=[
                        {"title": "Unify session event envelope fields", "detail": "Make hub consume the same session event envelope shape that core publishes, including scene identity, actor/device metadata, and canonical payload semantics."},
                    ],
                )
            )

        core_events = extract_dot_event_names(core_text)
        hub_events = extract_dot_event_names(hub_text)
        if core_events and hub_events and set(core_events) != set(hub_events):
            findings.append(
                make_finding(
                    scope_type="group",
                    scope_id="chummer-vnext",
                    finding_key="group.session_event_names_drift",
                    severity="medium",
                    title="Session event name sets drift across core and hub",
                    summary="The extracted dot-style session event names differ between core and hub contract sources, so vNext event naming is not yet canonical across reducer and relay surfaces.",
                    evidence=[
                        {"kind": "filesystem", "path": str(core_session_file), "event_names": core_events[:32]},
                        {"kind": "filesystem", "path": str(hub_session_file), "event_names": hub_events[:32]},
                    ],
                    candidate_tasks=[
                        {"title": "Canonicalize session event names", "detail": "Publish one event-name set for reducer, relay, and play clients and isolate any legacy names behind compatibility shims."},
                    ],
                )
            )

        if "SessionOverlayEventDto" in hub_text:
            findings.append(
                make_finding(
                    scope_type="project",
                    scope_id="hub",
                    finding_key="project.session_overlay_compat_shim_present",
                    severity="medium",
                    title="Hub still exposes legacy session overlay compatibility DTOs",
                    summary="Hub still ships `SessionOverlayEventDto` compatibility wrappers, so canonical session envelope migration is not complete yet.",
                    evidence=[
                        {"kind": "filesystem", "path": str(hub_session_file), "detail": "SessionOverlayEventDto still present"},
                    ],
                    candidate_tasks=[
                        {"title": "Retire hub session overlay compatibility DTOs", "detail": "Keep compatibility wrappers server-side only during migration and stop exposing them as a peer contract surface."},
                    ],
                )
            )

    hub_platform_file = hub_root / "Chummer.Run.Contracts" / "AIPlatformContracts.cs"
    if hub_platform_file.exists():
        findings.append(
            make_finding(
                scope_type="project",
                scope_id="hub",
                finding_key="project.ai_platform_contract_catchall",
                severity="medium",
                title="Hub still centralizes broad hosted DTO surface in AIPlatformContracts.cs",
                summary="Hub still uses a large catch-all `AIPlatformContracts.cs` file, which makes hosted contract ownership broad and difficult to govern by domain.",
                evidence=[{"kind": "filesystem", "path": str(hub_platform_file)}],
                candidate_tasks=[
                    {"title": "Split AIPlatformContracts.cs by hosted domain", "detail": "Break the catch-all contract file into narrower hosted contract families for relay, memory, media, docs, and AI gateway surfaces."},
                ],
            )
        )

    return findings


def collect_findings(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    now = utc_now()
    registry = load_program_registry(config)
    runtime_rows = project_runtime_rows()
    group_runtime = group_runtime_rows()
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
        group_meta = effective_group_meta(group_cfg, registry, group_runtime)
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

        if group_is_signed_off(group_meta):
            continue

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
    findings.extend(scan_chummer_contract_shape(config))
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
                        status=CASE
                            WHEN audit_task_candidates.status IN ('approved', 'published', 'rejected')
                                THEN audit_task_candidates.status
                            ELSE 'open'
                        END,
                        last_seen_at=excluded.last_seen_at,
                        resolved_at=CASE
                            WHEN audit_task_candidates.status IN ('approved', 'published', 'rejected')
                                THEN audit_task_candidates.resolved_at
                            ELSE NULL
                        END
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


@app.post("/api/auditor/run-now")
async def api_run_now() -> Dict[str, Any]:
    await run_audit_pass()
    return auditor_status()
