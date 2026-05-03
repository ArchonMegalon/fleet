from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from admin.readiness import _apply_queue_source


QUEUE_PATH = Path("/docker/fleet/.codex-studio/published/QUEUE.generated.yaml")
CONFIG_PATH = Path("/docker/fleet/config/projects/fleet.yaml")


def _queue_fingerprint(items: list[object]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def test_published_fleet_queue_overlay_contains_no_stale_solved_tasks() -> None:
    project_cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    queue = list(project_cfg.get("queue") or [])
    for source_cfg in project_cfg.get("queue_sources") or []:
        if isinstance(source_cfg, dict):
            queue = _apply_queue_source(project_cfg, queue, source_cfg)
    payload = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8")) or {}
    items = list(payload.get("items") or [])

    assert payload.get("source_queue_fingerprint") == _queue_fingerprint(queue)
    assert items == []


def test_apply_queue_source_loads_next90_queue_staging_for_matching_repo(tmp_path: Path) -> None:
    staging_path = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    staging_path.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "package_id": "next90-ui-1",
                        "repo": "chummer6-ui",
                        "status": "not_started",
                        "title": "Desktop continuity lane",
                    },
                    {
                        "package_id": "next90-hub-1",
                        "repo": "chummer6-hub",
                        "status": "not_started",
                        "title": "Hub followthrough lane",
                    },
                    {
                        "package_id": "next90-ui-done",
                        "repo": "chummer6-ui",
                        "status": "done",
                        "title": "Already complete lane",
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    project_cfg = {
        "path": str(tmp_path),
        "review": {"repo": "chummer6-ui"},
    }

    queue = _apply_queue_source(
        project_cfg,
        [],
        {"kind": "next90_queue_staging", "path": str(staging_path), "mode": "append"},
    )

    assert queue == [
        {
            "package_id": "next90-ui-1",
            "repo": "chummer6-ui",
            "status": "not_started",
            "title": "Desktop continuity lane",
        }
    ]
