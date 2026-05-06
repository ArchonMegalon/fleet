from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional

import yaml


UTC = dt.timezone.utc
STUDIO_PUBLISHED_DIR = ".codex-studio/published"
COMPILE_MANIFEST_FILENAME = "compile.manifest.json"
DESIGN_MIRROR_REQUIRED_FILES = [
    ".codex-design/product/VISION.md",
    ".codex-design/product/ARCHITECTURE.md",
    ".codex-design/repo/IMPLEMENTATION_SCOPE.md",
    ".codex-design/review/REVIEW_CONTEXT.md",
]
DEFAULT_COMPILE_FRESHNESS_HOURS = {
    "planned": 0,
    "scaffold": 336,
    "dispatchable": 168,
    "live": 72,
    "signoff_only": 168,
}
DISPATCH_PARTICIPATION_LIFECYCLES = {"dispatchable", "live"}
READINESS_ORDER = [
    "repo_local_complete",
    "package_canonical",
    "boundary_pure",
    "publicly_promoted",
]
READINESS_LABELS = {
    "pre_repo_local_complete": "Pre-Repo-Local Complete",
    "repo_local_complete": "Repo-Local Complete",
    "package_canonical": "Package-Canonical",
    "boundary_pure": "Boundary-Pure",
    "publicly_promoted": "Publicly Promoted",
}
PROMOTED_DEPLOYMENT_STAGES = {"promoted_preview", "release_candidate", "public_stable"}
BOUNDARY_PURE_SCORE_FLOOR = 0.70
FLEET_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(FLEET_ROOT) not in sys.path:
    sys.path.insert(0, str(FLEET_ROOT))
PROJECTS_CONFIG_DIR = FLEET_ROOT / "config" / "projects"
QUEUE_ARTIFACT = "QUEUE.generated.yaml"
WORKPACKAGES_ARTIFACT = "WORKPACKAGES.generated.yaml"
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
MILESTONE_TERMINAL_STATUSES = {"released", "complete", "completed", "done", "closed"}
WORKLIST_CHECKLIST_RE = re.compile(
    r"^\s*[-*]\s+\[(?P<status>[^\]]+)\]\s+(?:(?P<task_id>[A-Za-z0-9._-]+)\s+)?(?P<task>.+?)\s*$"
)


def _unique_preserve(values: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
    return ordered


def _parse_iso(value: Any) -> Optional[dt.datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None


def _iso(value: Optional[dt.datetime]) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def deployment_promotion_stage(status: Any) -> str:
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
    if clean in {"internal"}:
        return "internal"
    return "undeclared"


def project_repo_slug(project_cfg: Dict[str, Any]) -> str:
    review = project_cfg.get("review") or {}
    repo_name = str(review.get("repo") or "").strip()
    if repo_name:
        return repo_name
    return pathlib.Path(str(project_cfg.get("path") or "")).name


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


def _latest_compile_evidence_mtime(
    repo_root: pathlib.Path,
    artifacts: List[Any],
    design_doc: str = "",
) -> Optional[float]:
    published_dir = repo_root / STUDIO_PUBLISHED_DIR
    times: List[float] = []
    for artifact in artifacts:
        name = str(artifact or "").strip()
        if not name:
            continue
        path = published_dir / name
        if path.exists() and path.is_file():
            times.append(path.stat().st_mtime)
    mirror_mtime = latest_design_compile_mtime(repo_root, design_doc)
    if mirror_mtime is not None:
        times.append(mirror_mtime)
    if not times:
        return None
    return max(times)


def _work_package_source_queue_fingerprint(items: List[Any]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


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
    return {
        "mode": str(payload.get("mode") or "append").strip().lower() or "append",
        "items": list(raw_items or []),
        "source_queue_fingerprint": str(payload.get("source_queue_fingerprint") or payload.get("queue_fingerprint") or "").strip(),
    }


def _resolve_project_file(project_cfg: Dict[str, Any], source_path: str) -> pathlib.Path:
    path = pathlib.Path(str(source_path or "").strip())
    if path.is_absolute():
        return path
    return pathlib.Path(str(project_cfg.get("path") or "")).resolve() / path


def _markdown_table_cells(line: str) -> List[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _select_latest_active_tasks(entries: List[tuple[str, str]]) -> List[str]:
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
    active_items: List[tuple[int, str]] = []
    for key in ordered_keys:
        if latest_status_by_key.get(key) in ACTIVE_QUEUE_STATUSES:
            active_items.append((int(latest_order_by_key.get(key, 0)), latest_task_by_key.get(key, "")))
    active_items.sort(key=lambda item: item[0])
    return [task for _, task in active_items if task]


def _queue_entry_status(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("status") or item.get("state") or "").strip().lower().replace("_", " ")


def _queue_entry_active(item: Any) -> bool:
    status = _queue_entry_status(item)
    if not status:
        return True
    return status not in MILESTONE_TERMINAL_STATUSES


def _load_worklist_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = _resolve_project_file(project_cfg, str(source_cfg.get("path", "WORKLIST.md")))
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    entries: List[tuple[str, str]] = []
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


def _feedback_heading_targeted(heading: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(heading or "").strip().lower())
    normalized = " ".join(normalized.split())
    if not normalized:
        return False
    return normalized in {
        "required next work",
        "required next steps",
        "immediate follow on work",
        "immediate follow on work after current flagship closeout",
        "next work",
    }


def _load_feedback_notes_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[str]:
    path = _resolve_project_file(project_cfg, str(source_cfg.get("path", "feedback")))
    if not path.exists():
        return []
    candidate_paths: List[pathlib.Path] = []
    if path.is_file():
        candidate_paths = [path]
    elif path.is_dir():
        pattern = str(source_cfg.get("glob") or "*.md").strip() or "*.md"
        candidate_paths = sorted(
            (candidate for candidate in path.glob(pattern) if candidate.is_file()),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        max_files = max(0, int(source_cfg.get("max_files") or 0))
        if max_files > 0:
            candidate_paths = candidate_paths[:max_files]
    tasks: List[str] = []
    for candidate in candidate_paths:
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        section_active = False
        section_level = 0
        current_parent = ""
        for raw_line in lines:
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", raw_line)
            if heading_match:
                level = len(heading_match.group(1) or "")
                heading = str(heading_match.group(2) or "").strip()
                if _feedback_heading_targeted(heading):
                    section_active = True
                    section_level = level
                    current_parent = ""
                elif section_active and level <= section_level:
                    section_active = False
                    current_parent = ""
                continue
            if not section_active:
                continue
            bullet_match = re.match(r"^(?P<indent>\s*)-\s+(?P<task>.+?)\s*$", raw_line)
            if not bullet_match:
                continue
            indent = len(str(bullet_match.group("indent") or "").expandtabs(2))
            task = str(bullet_match.group("task") or "").strip().strip("`")
            if not task:
                continue
            if indent <= 1:
                current_parent = task
                if not task.endswith(":"):
                    tasks.append(task)
                continue
            if current_parent:
                parent = current_parent.rstrip(":").strip()
                if parent:
                    tasks.append(f"{parent}: {task}")
                    continue
            tasks.append(task)
    deduped: List[str] = []
    seen: set[str] = set()
    for task in tasks:
        normalized = " ".join(str(task or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


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


def _load_next90_queue_staging_queue(project_cfg: Dict[str, Any], source_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    from scripts.next90_queue_staging import read_next90_queue_staging_yaml

    path = _resolve_project_file(
        project_cfg,
        str(source_cfg.get("path", "/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")),
    )
    if not path.exists() or not path.is_file():
        return []
    try:
        data = read_next90_queue_staging_yaml(path)
    except Exception:
        return []
    raw_items = list((data.get("items") or []) if isinstance(data, dict) else [])
    if not raw_items:
        return []
    include_statuses = {
        str(status).strip().lower()
        for status in (source_cfg.get("include_statuses") or ["in_progress", "not_started"])
        if str(status).strip()
    }
    repos = _unique_preserve(
        [str(item).strip() for item in (source_cfg.get("repos") or []) if str(item).strip()]
        or [project_repo_slug(project_cfg)]
    )
    items: List[Dict[str, Any]] = []
    seen_package_ids: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        status = str(raw_item.get("status") or raw_item.get("state") or "").strip().lower()
        repo = str(raw_item.get("repo") or "").strip()
        package_id = str(raw_item.get("package_id") or "").strip()
        if include_statuses and status not in include_statuses:
            continue
        if repos and repo not in repos:
            continue
        if package_id and package_id in seen_package_ids:
            continue
        item = {key: value for key, value in dict(raw_item).items() if value not in ("", None, [], {})}
        if not item:
            continue
        items.append(item)
        if package_id:
            seen_package_ids.add(package_id)
    return items


def _apply_queue_source(project_cfg: Dict[str, Any], queue: List[Any], source_cfg: Dict[str, Any]) -> List[Any]:
    queue = [item for item in queue if _queue_entry_active(item)]
    fallback_only_if_empty = bool(source_cfg.get("fallback_only_if_empty"))
    if fallback_only_if_empty and queue:
        return list(queue)
    kind = str(source_cfg.get("kind", "") or "").strip().lower()
    if kind == "worklist":
        items = _load_worklist_queue(project_cfg, source_cfg)
    elif kind == "feedback_notes":
        items = _load_feedback_notes_queue(project_cfg, source_cfg)
    elif kind == "tasks_work_log":
        items = _load_tasks_work_log_queue(project_cfg, source_cfg)
    elif kind == "milestone_capabilities":
        items = _load_milestone_capability_queue(project_cfg, source_cfg)
    elif kind == "next90_queue_staging":
        items = _load_next90_queue_staging_queue(project_cfg, source_cfg)
    else:
        items = []
    mode = str(source_cfg.get("mode", "append")).strip().lower() or "append"
    if mode == "replace":
        return list(items)
    if mode == "prepend":
        return list(items) + list(queue)
    return list(queue) + list(items)


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


def _configured_project_queue_for_repo(repo_root: pathlib.Path) -> Optional[List[Any]]:
    if not PROJECTS_CONFIG_DIR.exists():
        return None
    try:
        resolved_root = repo_root.resolve()
    except Exception:
        resolved_root = repo_root
    for path in sorted(PROJECTS_CONFIG_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        project_path = str(payload.get("path") or "").strip()
        if not project_path:
            continue
        try:
            resolved_project_root = pathlib.Path(project_path).expanduser().resolve()
        except Exception:
            resolved_project_root = pathlib.Path(project_path).expanduser()
        if resolved_project_root == resolved_root:
            queue = list(payload.get("queue") or [])
            for source_cfg in payload.get("queue_sources") or []:
                if isinstance(source_cfg, dict):
                    queue = _apply_queue_source(payload, queue, source_cfg)
            return queue
    return None


def _queue_overlay_artifact(repo_root: pathlib.Path) -> Optional[Dict[str, Any]]:
    path = repo_root / STUDIO_PUBLISHED_DIR / QUEUE_ARTIFACT
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return _parse_queue_overlay_payload(payload)


def _queue_overlay_artifact_queue_bound(repo_root: pathlib.Path) -> bool:
    base_queue = _configured_project_queue_for_repo(repo_root)
    overlay_payload = _queue_overlay_artifact(repo_root)
    if base_queue is None or overlay_payload is None:
        return False
    expected_queue_fingerprint = str(overlay_payload.get("source_queue_fingerprint") or "").strip()
    if not expected_queue_fingerprint:
        return False
    return expected_queue_fingerprint == _work_package_source_queue_fingerprint(base_queue)


def _effective_project_queue_for_repo(repo_root: pathlib.Path) -> Optional[List[Any]]:
    base_queue = _configured_project_queue_for_repo(repo_root)
    if base_queue is None:
        return None
    overlay_payload = _queue_overlay_artifact(repo_root)
    if overlay_payload is None:
        return list(base_queue)
    expected_queue_fingerprint = str(overlay_payload.get("source_queue_fingerprint") or "").strip()
    if not expected_queue_fingerprint:
        return list(base_queue)
    if expected_queue_fingerprint != _work_package_source_queue_fingerprint(base_queue):
        return list(base_queue)
    return _apply_queue_overlay(base_queue, overlay_payload)


def _workpackages_artifact_queue_bound(repo_root: pathlib.Path) -> bool:
    path = repo_root / STUDIO_PUBLISHED_DIR / WORKPACKAGES_ARTIFACT
    if not path.exists() or not path.is_file():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    expected_queue_fingerprint = ""
    if isinstance(payload, dict):
        expected_queue_fingerprint = str(payload.get("source_queue_fingerprint") or payload.get("queue_fingerprint") or "").strip()
    current_queue = _effective_project_queue_for_repo(repo_root)
    if current_queue is None:
        return not expected_queue_fingerprint
    if expected_queue_fingerprint:
        return expected_queue_fingerprint == _work_package_source_queue_fingerprint(current_queue)
    return not current_queue


def _dispatchable_truth_ready(repo_root: pathlib.Path, artifacts: List[str]) -> bool:
    names = {str(item or "").strip() for item in artifacts if str(item or "").strip()}
    if WORKPACKAGES_ARTIFACT in names:
        return _workpackages_artifact_queue_bound(repo_root)
    if QUEUE_ARTIFACT in names:
        return _queue_overlay_artifact_queue_bound(repo_root)
    return False


def studio_compile_summary(repo_root: pathlib.Path, design_doc: str = "") -> Dict[str, Any]:
    published_dir = repo_root / STUDIO_PUBLISHED_DIR
    manifest_path = published_dir / COMPILE_MANIFEST_FILENAME
    design_compiled = design_compile_present(repo_root, design_doc)
    dispatchable_artifacts = {QUEUE_ARTIFACT, WORKPACKAGES_ARTIFACT}
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                stages = dict(payload.get("stages") or {})
                artifacts = list(payload.get("artifacts") or [])
                dispatchable_truth_ready = _dispatchable_truth_ready(repo_root, artifacts)
                published_at = _parse_iso(str(payload.get("published_at") or ""))
                evidence_mtime = _latest_compile_evidence_mtime(repo_root, artifacts, design_doc)
                if evidence_mtime is not None:
                    evidence_time = dt.datetime.fromtimestamp(evidence_mtime, UTC)
                    if published_at is None or evidence_time > published_at:
                        published_at = evidence_time
                stages["design_compile"] = bool(stages.get("design_compile")) or design_compiled
                stages["policy_compile"] = bool(stages.get("policy_compile")) or any(
                    path in {
                        "runtime-instructions.generated.md",
                        QUEUE_ARTIFACT,
                        WORKPACKAGES_ARTIFACT,
                        "STATUS_PLANE.generated.yaml",
                        "PROGRAM_MILESTONES.generated.yaml",
                        "CONTRACT_SETS.yaml",
                        "GROUP_BLOCKERS.md",
                    }
                    for path in artifacts
                )
                stages["execution_compile"] = bool(stages.get("execution_compile")) or any(
                    path in dispatchable_artifacts for path in artifacts
                )
                stages["package_compile"] = bool(stages.get("package_compile")) or "WORKPACKAGES.generated.yaml" in artifacts
                stages["capacity_compile"] = bool(stages.get("capacity_compile")) or any(
                    path in dispatchable_artifacts or path == "runtime-instructions.generated.md"
                    for path in artifacts
                )
                return {
                    "published_at": _iso(published_at),
                    "stages": stages,
                    "dispatchable_truth_ready": dispatchable_truth_ready,
                    "artifacts": artifacts,
                    "lifecycle": str(payload.get("lifecycle") or ""),
                }
        except Exception:
            pass
    files = []
    if published_dir.exists():
        files = sorted(child.name for child in published_dir.iterdir() if child.is_file())
    if not files and not design_compiled:
        return {"published_at": "", "stages": {}, "dispatchable_truth_ready": False, "artifacts": [], "lifecycle": ""}
    design_files = {"VISION.md", "ROADMAP.md", "ARCHITECTURE.md"}
    policy_files = {
        "runtime-instructions.generated.md",
        QUEUE_ARTIFACT,
        WORKPACKAGES_ARTIFACT,
        "STATUS_PLANE.generated.yaml",
        "PROGRAM_MILESTONES.generated.yaml",
        "CONTRACT_SETS.yaml",
        "GROUP_BLOCKERS.md",
    }
    mtimes = []
    evidence_mtime = _latest_compile_evidence_mtime(repo_root, files, design_doc)
    if evidence_mtime is not None:
        mtimes.append(evidence_mtime)
    latest_mtime = max(mtimes) if mtimes else dt.datetime.now(tz=UTC).timestamp()
    return {
        "published_at": _iso(dt.datetime.fromtimestamp(latest_mtime, UTC)),
        "stages": {
            "design_compile": design_compiled or any(name in design_files for name in files),
            "policy_compile": any(name in policy_files for name in files),
            "execution_compile": any(name in dispatchable_artifacts for name in files),
            "package_compile": WORKPACKAGES_ARTIFACT in files,
            "capacity_compile": any(name in dispatchable_artifacts for name in files) or "runtime-instructions.generated.md" in files,
        },
        "dispatchable_truth_ready": _dispatchable_truth_ready(repo_root, files),
        "artifacts": files,
        "lifecycle": "",
    }


def compile_health(
    summary: Dict[str, Any],
    lifecycle: str,
    *,
    compile_freshness_hours: Optional[Dict[str, Any]] = None,
    compile_stage_policy: Optional[Dict[str, Any]] = None,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    lifecycle_state = str(lifecycle or "dispatchable").strip().lower() or "dispatchable"
    freshness_hours_map = dict(DEFAULT_COMPILE_FRESHNESS_HOURS)
    freshness_hours_map.update(dict(compile_freshness_hours or {}))
    freshness_hours = int(freshness_hours_map.get(lifecycle_state) or DEFAULT_COMPILE_FRESHNESS_HOURS.get(lifecycle_state, 168))
    current_now = now or dt.datetime.now(tz=UTC)
    published_at = _parse_iso(str(summary.get("published_at") or ""))
    age_hours = None
    if published_at is not None:
        age_hours = max(0, int((current_now - published_at).total_seconds() // 3600))
    stages = dict(summary.get("stages") or {})
    stage_policy = {
        str(key or "").strip(): str(value or "").strip().lower()
        for key, value in dict(compile_stage_policy or {}).items()
        if str(key or "").strip()
    }
    needs_design = lifecycle_state in {"scaffold", "dispatchable", "live", "signoff_only"} and stage_policy.get("design_compile", "required") != "advisory"
    needs_policy = lifecycle_state in {"dispatchable", "live", "signoff_only"} and stage_policy.get("policy_compile", "required") != "advisory"
    needs_execution = lifecycle_state in {"dispatchable", "live"} and stage_policy.get("execution_compile", "required") != "advisory"
    needs_package = lifecycle_state in {"dispatchable", "live"} and stage_policy.get("package_compile", "required") != "advisory"
    needs_capacity = lifecycle_state in {"dispatchable", "live"} and stage_policy.get("capacity_compile", "required") != "advisory"
    missing: List[str] = []
    if needs_design and not stages.get("design_compile"):
        missing.append("design compile")
    if needs_policy and not stages.get("policy_compile"):
        missing.append("policy compile")
    if needs_execution and not bool(summary.get("dispatchable_truth_ready")):
        missing.append("execution compile")
    if needs_package and not stages.get("package_compile"):
        missing.append("package compile")
    if needs_capacity and not stages.get("capacity_compile"):
        missing.append("capacity compile")
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
            "summary": f"missing compile artifacts: {', '.join(missing)}",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if missing:
        return {
            "status": "incomplete",
            "tone": "yellow",
            "summary": f"compile artifacts exist but still miss {', '.join(missing)}",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if age_hours is None:
        return {
            "status": "unknown",
            "tone": "yellow",
            "summary": "compile artifacts exist but their freshness is unknown",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if freshness_hours > 0 and age_hours > freshness_hours:
        return {
            "status": "stale",
            "tone": "yellow",
            "summary": f"compile artifacts are {age_hours}h old; freshness target is {freshness_hours}h",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    return {
        "status": "ready",
        "tone": "green",
        "summary": "compile artifacts are current for the declared lifecycle",
        "freshness_hours": freshness_hours,
        "age_hours": age_hours,
    }


def boundary_purity_registry(design_root: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    path = design_root / "products" / "chummer" / "PROGRAM_MILESTONES.yaml"
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    rows = data.get("repo_boundary_purity") or []
    registry: Dict[str, Dict[str, Any]] = {}
    if not isinstance(rows, list):
        return registry
    for row in rows:
        if not isinstance(row, dict):
            continue
        repo = str(row.get("repo") or "").strip()
        if not repo:
            continue
        registry[repo] = {
            "repo": repo,
            "status": str(row.get("status") or "").strip().lower(),
            "score": float(row.get("score") or 0.0),
            "reason": str(row.get("reason") or "").strip(),
        }
    return registry


def boundary_purity_registry_from_config(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    design_cfg = next((project for project in config.get("projects") or [] if str(project.get("id") or "").strip() == "design"), {})
    design_path = str(design_cfg.get("path") or "").strip() if design_cfg else ""
    if not design_path:
        return {}
    design_root = pathlib.Path(design_path).resolve()
    return boundary_purity_registry(design_root)


def _readiness_basis_for_runtime(runtime_status: str, runtime_completion_state: str) -> str:
    if runtime_completion_state in {"runtime_complete", "scaffold_complete", "signed_off"}:
        return f"runtime completion is {runtime_completion_state}"
    if runtime_completion_state == "signoff_only":
        return "repo is in signoff-only posture"
    return f"runtime is still {runtime_status or runtime_completion_state or 'in_progress'}"


def _repo_local_complete_evidence(
    *,
    lifecycle: str,
    runtime_completion_state: str,
    compile_health_payload: Dict[str, Any],
) -> bool:
    if runtime_completion_state in {"runtime_complete", "scaffold_complete", "signed_off", "signoff_only"}:
        return True
    lifecycle_state = str(lifecycle or "").strip().lower()
    compile_ready = str(compile_health_payload.get("status") or "").strip().lower() in {"ready", "not_required"}
    if lifecycle_state in {"dispatchable", "live"} and compile_ready:
        return True
    return False


def _readiness_basis_for_repo_local(
    lifecycle: str,
    runtime_status: str,
    runtime_completion_state: str,
    compile_health_payload: Dict[str, Any],
) -> str:
    if runtime_completion_state in {"runtime_complete", "scaffold_complete", "signed_off", "signoff_only"}:
        return _readiness_basis_for_runtime(runtime_status, runtime_completion_state)
    lifecycle_state = str(lifecycle or "").strip().lower()
    compile_ready = str(compile_health_payload.get("status") or "").strip().lower() in {"ready", "not_required"}
    if lifecycle_state in {"dispatchable", "live"} and compile_ready:
        return "dispatchable compile/package truth is queue-bound and runnable"
    return _readiness_basis_for_runtime(runtime_status, runtime_completion_state)


def _readiness_basis_for_compile(compile_health_payload: Dict[str, Any]) -> str:
    return str(compile_health_payload.get("summary") or "package-canon evidence is missing").strip()


def _readiness_basis_for_boundary(boundary_meta: Dict[str, Any]) -> str:
    if not boundary_meta:
        return "no boundary-purity record exists in design canon"
    status = str(boundary_meta.get("status") or "unknown").strip().lower() or "unknown"
    score = float(boundary_meta.get("score") or 0.0)
    reason = str(boundary_meta.get("reason") or "").strip()
    summary = f"design canon marks the repo {status} at {score:.2f}"
    return f"{summary}; {reason}".strip("; ")


def _public_promotion_applicable(deployment: Dict[str, Any]) -> bool:
    status = str(deployment.get("status") or "").strip().lower()
    visibility = str(deployment.get("visibility") or "").strip().lower()
    promotion_stage = str(deployment.get("promotion_stage") or deployment_promotion_stage(status)).strip().lower()
    target_url = str(deployment.get("target_url") or "").strip()
    if status == "internal" or visibility == "internal":
        return False
    if promotion_stage == "internal":
        return False
    if visibility == "public":
        return True
    if target_url:
        return True
    return promotion_stage not in {"undeclared", "planned", "internal"}


def derive_project_readiness(
    *,
    project_id: str,
    repo_slug: str,
    lifecycle: str,
    runtime_status: str,
    runtime_completion_state: str,
    compile_summary_payload: Dict[str, Any],
    compile_health_payload: Dict[str, Any],
    deployment: Optional[Dict[str, Any]] = None,
    boundary_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    deployment_payload = dict(deployment or {})
    promotion_stage = str(
        deployment_payload.get("promotion_stage")
        or deployment_promotion_stage(deployment_payload.get("status"))
    ).strip().lower() or "undeclared"
    boundary = dict(boundary_meta or {})
    boundary_status = str(boundary.get("status") or "").strip().lower()
    boundary_score = float(boundary.get("score") or 0.0)
    package_canonical_evidence = str(compile_health_payload.get("status") or "").strip().lower() in {"ready", "not_required"}
    repo_local_complete_evidence = _repo_local_complete_evidence(
        lifecycle=lifecycle,
        runtime_completion_state=runtime_completion_state,
        compile_health_payload=compile_health_payload,
    )
    boundary_pure_evidence = boundary_status == "healthy" or boundary_score >= BOUNDARY_PURE_SCORE_FLOOR
    public_promotion_applicable = _public_promotion_applicable(deployment_payload)
    publicly_promoted_evidence = promotion_stage in PROMOTED_DEPLOYMENT_STAGES
    checks = {
        "repo_local_complete": {
            "evidence_met": repo_local_complete_evidence,
            "basis": _readiness_basis_for_repo_local(
                lifecycle,
                runtime_status,
                runtime_completion_state,
                compile_health_payload,
            ),
        },
        "package_canonical": {
            "evidence_met": package_canonical_evidence,
            "basis": _readiness_basis_for_compile(compile_health_payload),
        },
        "boundary_pure": {
            "evidence_met": boundary_pure_evidence,
            "basis": _readiness_basis_for_boundary(boundary),
            "status": boundary_status or "unknown",
            "score": boundary_score if boundary else None,
        },
        "publicly_promoted": {
            "evidence_met": publicly_promoted_evidence,
            "applicable": public_promotion_applicable,
            "basis": (
                f"deployment promotion stage is {promotion_stage}"
                if public_promotion_applicable
                else "no public promotion gate applies to this repo"
            ),
            "promotion_stage": promotion_stage,
        },
    }
    stage_rank = 0
    for stage_name in READINESS_ORDER:
        check = checks[stage_name]
        if stage_name == "publicly_promoted" and not bool(check.get("applicable")):
            break
        if not bool(check.get("evidence_met")):
            break
        stage_rank += 1
    stage = READINESS_ORDER[stage_rank - 1] if stage_rank > 0 else "pre_repo_local_complete"
    next_stage = ""
    if stage_rank < len(READINESS_ORDER):
        candidate = READINESS_ORDER[stage_rank]
        if candidate != "publicly_promoted" or public_promotion_applicable:
            next_stage = candidate
    terminal_stage = "publicly_promoted" if public_promotion_applicable else "boundary_pure"
    validator_checks: List[Dict[str, Any]] = []
    if publicly_promoted_evidence and not boundary_pure_evidence:
        validator_checks.append(
            {
                "kind": "deployment_ahead_of_boundary",
                "summary": "deployment is promoted beyond the repo's boundary-purity evidence",
            }
        )
    if boundary_pure_evidence and not package_canonical_evidence:
        validator_checks.append(
            {
                "kind": "boundary_ahead_of_package",
                "summary": "design canon says the repo boundary is healthy, but package-canon compile evidence is missing",
            }
        )
    if package_canonical_evidence and not repo_local_complete_evidence:
        validator_checks.append(
            {
                "kind": "package_ahead_of_repo_local",
                "summary": "package-canon evidence exists before the repo has reached repo-local complete",
            }
        )
    if stage == "pre_repo_local_complete":
        summary = f"Not repo-local complete yet. {checks['repo_local_complete']['basis']}."
    elif stage == "repo_local_complete":
        summary = f"Repo-local complete, but package-canonical evidence is not locked. {checks['package_canonical']['basis']}."
    elif stage == "package_canonical":
        summary = f"Package-canonical, but boundary purity is not proven. {checks['boundary_pure']['basis']}."
    elif stage == "boundary_pure" and public_promotion_applicable:
        summary = f"Boundary-pure, but the public surface is still {promotion_stage}. {checks['publicly_promoted']['basis']}."
    elif stage == "boundary_pure":
        summary = "Boundary-pure. No public promotion gate applies to this repo."
    else:
        summary = f"Publicly promoted. {checks['publicly_promoted']['basis']}."
    out_of_order_evidence = [name for name, payload in checks.items() if bool(payload.get("evidence_met")) and READINESS_ORDER.index(name) >= stage_rank]
    return {
        "project_id": project_id,
        "repo_slug": repo_slug,
        "lifecycle": lifecycle,
        "stage": stage,
        "label": READINESS_LABELS.get(stage, stage.replace("_", " ").title()),
        "summary": summary,
        "next_stage": next_stage,
        "next_label": READINESS_LABELS.get(next_stage, next_stage.replace("_", " ").title()) if next_stage else "",
        "terminal_stage": terminal_stage,
        "final_claim_allowed": stage == terminal_stage,
        "checks": checks,
        "validator_checks": validator_checks,
        "warning_count": len(validator_checks),
        "boundary": boundary,
        "compile": {
            "status": str(compile_health_payload.get("status") or "unknown"),
            "summary": str(compile_health_payload.get("summary") or ""),
            "published_at": str(compile_summary_payload.get("published_at") or ""),
        },
        "deployment": {
            "status": str(deployment_payload.get("status") or ""),
            "promotion_stage": promotion_stage,
            "target_url": str(deployment_payload.get("target_url") or ""),
            "visibility": str(deployment_payload.get("visibility") or ""),
        },
        "out_of_order_evidence": out_of_order_evidence,
    }


def derive_group_deployment_readiness(*, group_id: str, deployment: Optional[Dict[str, Any]], owner_projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    deployment_payload = dict(deployment or {})
    promotion_stage = str(
        deployment_payload.get("promotion_stage")
        or deployment_promotion_stage(deployment_payload.get("status"))
    ).strip().lower() or "undeclared"
    public_promotion_applicable = _public_promotion_applicable(deployment_payload)
    relevant_owners = []
    for project in owner_projects:
        readiness = dict(project.get("readiness") or {})
        if not readiness:
            continue
        relevant_owners.append(
            {
                "id": str(project.get("id") or ""),
                "stage": str(readiness.get("stage") or ""),
                "label": str(readiness.get("label") or ""),
                "boundary_pure": bool(((readiness.get("checks") or {}).get("boundary_pure") or {}).get("evidence_met")),
            }
        )
    blocking_owner_projects = _unique_preserve([project["id"] for project in relevant_owners if not project["boundary_pure"]])
    can_claim_publicly_promoted = bool(
        public_promotion_applicable
        and promotion_stage in PROMOTED_DEPLOYMENT_STAGES
        and not blocking_owner_projects
    )
    if not public_promotion_applicable:
        summary = "No public promotion gate applies to this deployment surface."
    elif can_claim_publicly_promoted:
        summary = f"Deployment is publicly promoted at {promotion_stage} and every owner project is boundary-pure."
    elif promotion_stage not in PROMOTED_DEPLOYMENT_STAGES:
        summary = f"Deployment is still {promotion_stage}; public promotion is not yet claimed."
    else:
        summary = "Deployment is promoted, but one or more owner projects are not boundary-pure yet."
    return {
        "group_id": group_id,
        "promotion_stage": promotion_stage,
        "public_promotion_applicable": public_promotion_applicable,
        "publicly_promoted": can_claim_publicly_promoted,
        "blocking_owner_projects": blocking_owner_projects,
        "owner_projects": relevant_owners,
        "summary": summary,
    }
