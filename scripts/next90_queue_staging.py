from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def read_next90_queue_staging_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError:
        payload = _parse_append_style_queue(raw)
    if isinstance(payload, list):
        return {"items": payload}
    return dict(payload or {}) if isinstance(payload, dict) else {}


def _parse_append_style_queue(raw: str) -> Dict[str, Any]:
    if "\nmode:" in raw and "\nitems:\n" in raw:
        try:
            prefix, suffix = raw.split("\nmode:", 1)
            prefix_payload = yaml.safe_load(prefix) or []
            suffix_payload = yaml.safe_load("mode:" + suffix) or {}
            if isinstance(prefix_payload, list) and isinstance(suffix_payload, dict):
                combined = dict(suffix_payload)
                suffix_items = combined.get("items") if isinstance(combined.get("items"), list) else []
                combined["items"] = list(prefix_payload) + list(suffix_items)
                return combined
        except yaml.YAMLError:
            return {}
        except Exception:
            return {}
    if "\nitems:\n" not in raw:
        return {}
    try:
        payload = yaml.safe_load("items:\n" + raw.split("\nitems:\n", 1)[1]) or {}
    except yaml.YAMLError:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}
