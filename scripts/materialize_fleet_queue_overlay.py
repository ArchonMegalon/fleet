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

from admin.readiness import (
    _load_next90_queue_staging_queue,
    _load_milestone_capability_queue,
    _load_tasks_work_log_queue,
    _load_worklist_queue,
    _queue_entry_active,
)


PROJECTS_CONFIG_DIR = ROOT / "config" / "projects"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize Fleet's published queue overlay as an empty, queue-bound artifact so stale solved slices cannot poison live queue truth."
    )
    parser.add_argument("--repo-root", required=True, help="repo root that owns .codex-studio/published/QUEUE.generated.yaml")
    parser.add_argument("--out", default=None, help="optional explicit output path for QUEUE.generated.yaml")
    parser.add_argument("--project-id", default=None, help="optional Fleet project id override")
    parser.add_argument(
        "--projects-dir",
        default=str(PROJECTS_CONFIG_DIR),
        help="directory containing Fleet project config YAML files",
    )
    return parser.parse_args(argv)


def queue_fingerprint(items: List[Any]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def apply_queue_source(project_cfg: dict[str, Any], queue: List[Any], source_cfg: dict[str, Any]) -> List[Any]:
    """Match Studio's publish-time base queue semantics for artifact fingerprints."""
    queue = [item for item in queue if _queue_entry_active(item)]
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


def resolve_project_queue(repo_root: Path, projects_dir: Path, explicit_project_id: str | None = None) -> tuple[str, List[Any]]:
    clean_explicit = str(explicit_project_id or "").strip()
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
        project_id = str(payload.get("id") or "").strip() or path.stem
        raw_project_path = str(payload.get("path") or "").strip()
        if not raw_project_path:
            continue
        try:
            project_root = Path(raw_project_path).expanduser().resolve()
        except Exception:
            project_root = Path(raw_project_path).expanduser()
        if clean_explicit and project_id != clean_explicit:
            continue
        if project_root != resolved_root:
            continue
        queue = list(payload.get("queue") or [])
        for source_cfg in payload.get("queue_sources") or []:
            if isinstance(source_cfg, dict):
                queue = apply_queue_source(payload, queue, source_cfg)
        return project_id, queue
    raise FileNotFoundError(f"could not resolve Fleet project config for {repo_root}")


def build_overlay(queue_items: List[Any]) -> dict[str, Any]:
    return {
        "mode": "append",
        "items": [],
        "source_queue_fingerprint": queue_fingerprint(queue_items),
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    projects_dir = Path(args.projects_dir).resolve()
    out_path = Path(args.out).resolve() if args.out else (repo_root / ".codex-studio" / "published" / "QUEUE.generated.yaml")
    _project_id, queue_items = resolve_project_queue(repo_root, projects_dir, explicit_project_id=args.project_id)
    payload = build_overlay(queue_items)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    if repo_root_for_published_path(out_path) == repo_root:
        write_compile_manifest(repo_root)
    print(f"wrote queue overlay: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
