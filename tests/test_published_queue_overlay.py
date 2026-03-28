from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml


QUEUE_PATH = Path("/docker/fleet/.codex-studio/published/QUEUE.generated.yaml")


def _queue_fingerprint(items: list[object]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def test_published_fleet_queue_overlay_contains_no_stale_solved_tasks() -> None:
    payload = yaml.safe_load(QUEUE_PATH.read_text(encoding="utf-8")) or {}
    items = [str(item).strip() for item in (payload.get("items") or []) if str(item).strip()]

    assert payload.get("source_queue_fingerprint") == _queue_fingerprint([])
    assert items == []
