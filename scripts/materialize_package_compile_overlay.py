#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, List

import yaml
try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest
except ModuleNotFoundError:
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin.readiness import _load_milestone_capability_queue, _load_next90_queue_staging_queue, _load_tasks_work_log_queue, _load_worklist_queue

PROJECTS_CONFIG_DIR = ROOT / "config" / "projects"
DEFAULT_TARGET_RELPATH = ".codex-studio/published/WORKPACKAGES.generated.yaml"
RAW_QUEUE_TERMINAL_STATUSES = {"done", "complete", "completed", "shipped", "archived", "cancelled", "canceled", "skipped"}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize a queue-bound package_compile front package for repos that still publish raw queue truth."
    )
    parser.add_argument("--repo-root", required=True, help="repo root that owns .codex-studio/published/QUEUE.generated.yaml")
    parser.add_argument("--out", default=None, help="optional explicit output path for WORKPACKAGES.generated.yaml")
    parser.add_argument("--project-id", default=None, help="optional Fleet project id override")
    parser.add_argument(
        "--projects-dir",
        default=str(PROJECTS_CONFIG_DIR),
        help="directory containing Fleet project config YAML files",
    )
    parser.add_argument(
        "--target-relpath",
        default=DEFAULT_TARGET_RELPATH,
        help="relative path that the package_compile package is allowed to rebuild",
    )
    return parser.parse_args(argv)


def package_safe_token(value: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean.strip("-") or "package"


def work_package_source_queue_fingerprint(items: List[Any]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def queue_item_terminal(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return str(item.get("status") or "").strip().lower() in RAW_QUEUE_TERMINAL_STATUSES


def queue_item_has_explicit_scope(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return bool([value for value in item.get("allowed_paths") or [] if str(value).strip()] or [value for value in item.get("owned_surfaces") or [] if str(value).strip()])


def queue_needs_compile(queue_items: List[Any]) -> bool:
    for item in queue_items:
        if queue_item_terminal(item):
            continue
        if not queue_item_has_explicit_scope(item):
            return True
    return False


def apply_queue_source(project_cfg: dict[str, Any], queue: List[Any], source_cfg: dict[str, Any]) -> List[Any]:
    """Match Studio's publish-time base queue semantics for artifact fingerprints."""
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


def load_queue_items(repo_root: Path) -> List[Any]:
    queue_path = repo_root / ".codex-studio" / "published" / "QUEUE.generated.yaml"
    if not queue_path.exists():
        raise FileNotFoundError(f"missing queue artifact: {queue_path}")
    payload = yaml.safe_load(queue_path.read_text(encoding="utf-8")) or {}
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return list(items)
    return []


def resolve_project_queue(repo_root: Path, projects_dir: Path) -> List[Any]:
    resolved_root = repo_root.resolve()
    for path in sorted(projects_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw_project_path = str(payload.get("path") or "").strip()
        if not raw_project_path:
            continue
        try:
            project_root = Path(raw_project_path).expanduser().resolve()
        except Exception:
            project_root = Path(raw_project_path).expanduser()
        if project_root != resolved_root:
            continue
        queue = payload.get("queue") or []
        resolved_queue = list(queue) if isinstance(queue, list) else []
        for source_cfg in payload.get("queue_sources") or []:
            if isinstance(source_cfg, dict):
                resolved_queue = apply_queue_source(payload, resolved_queue, source_cfg)
        return resolved_queue
    return []


def effective_queue_items(repo_root: Path, projects_dir: Path) -> List[Any]:
    queue_path = repo_root / ".codex-studio" / "published" / "QUEUE.generated.yaml"
    current_items = load_queue_items(repo_root)
    if not queue_path.exists():
        return current_items
    try:
        payload = yaml.safe_load(queue_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return current_items
    if not isinstance(payload, dict):
        return current_items
    mode = str(payload.get("mode") or "append").strip().lower() or "append"
    configured_queue = resolve_project_queue(repo_root, projects_dir)
    if mode == "replace":
        return current_items
    if mode == "prepend":
        return list(current_items) + list(configured_queue)
    return list(configured_queue) + list(current_items)


def resolve_project_id(repo_root: Path, projects_dir: Path, explicit: str | None = None) -> str:
    clean_explicit = str(explicit or "").strip()
    if clean_explicit:
        return clean_explicit
    resolved_root = repo_root.resolve()
    for path in sorted(projects_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw_project_path = str(payload.get("path") or "").strip()
        if not raw_project_path:
            continue
        try:
            project_root = Path(raw_project_path).expanduser().resolve()
        except Exception:
            project_root = Path(raw_project_path).expanduser()
        if project_root == resolved_root:
            return str(payload.get("id") or "").strip() or repo_root.name
    return repo_root.name


def build_overlay(project_id: str, queue_items: List[Any], *, target_relpath: str) -> dict[str, Any]:
    queue_fingerprint = work_package_source_queue_fingerprint(queue_items)
    if not queue_items or not queue_needs_compile(queue_items):
        return {
            "source_queue_fingerprint": queue_fingerprint,
            "work_packages": [],
        }
    package_id = f"{package_safe_token(project_id)}-package-compile-{queue_fingerprint[:10]}"
    return {
        "source_queue_fingerprint": queue_fingerprint,
        "work_packages": [
            {
                "package_id": package_id,
                "package_kind": "package_compile",
                "horizon_family": "package-compile",
                "title": "Compile booster-ready work packages from queue truth",
                "allowed_lanes": ["core_booster", "core_authority"],
                "allow_credit_burn": False,
                "premium_required": False,
                "required_reviewer_lane": "core_authority",
                "final_reviewer_lane": "core_authority",
                "landing_lane": "core_authority",
                "allowed_paths": [target_relpath],
                "denied_paths": [],
                "owned_surfaces": [f"package_compile:{project_id}"],
                "dependencies": [],
                "max_touched_files": 1,
            }
        ],
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    projects_dir = Path(args.projects_dir).resolve()
    out_path = Path(args.out).resolve() if args.out else (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml")
    project_id = resolve_project_id(repo_root, projects_dir, explicit=args.project_id)
    queue_items = effective_queue_items(repo_root, projects_dir)
    payload = build_overlay(project_id, queue_items, target_relpath=str(args.target_relpath or DEFAULT_TARGET_RELPATH).strip() or DEFAULT_TARGET_RELPATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    if repo_root_for_published_path(out_path) == repo_root:
        write_compile_manifest(repo_root)
    print(f"wrote package overlay: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
