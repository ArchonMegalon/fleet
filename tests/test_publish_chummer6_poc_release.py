from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/scripts/publish_chummer6_poc_release.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("publish_chummer6_poc_release", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_release_payload_prefers_existing_nonempty_registry_projection(monkeypatch, tmp_path: Path) -> None:
    publisher = _load_module()
    canonical = tmp_path / "RELEASE_CHANNEL.generated.json"
    compat = tmp_path / "releases.json"
    canonical.write_text(
        json.dumps(
            {
                "version": "smoke-2026-03-24",
                "channelId": "preview",
                "publishedAt": "2026-03-24T11:33:23Z",
                "artifacts": [{"artifactId": "avalonia-linux-x64-archive"}],
            }
        ),
        encoding="utf-8",
    )
    compat.write_text(
        json.dumps(
            {
                "version": "compat-only",
                "channel": "preview",
                "publishedAt": "2026-03-24T11:33:23Z",
                "downloads": [],
            }
        ),
        encoding="utf-8",
    )
    refreshed: list[bool] = []
    monkeypatch.setattr(publisher, "DOWNLOADS_MANIFEST", canonical)
    monkeypatch.setattr(publisher, "COMPAT_DOWNLOADS_MANIFEST", compat)
    monkeypatch.setattr(publisher, "refresh_release_projection", lambda: refreshed.append(True))

    payload = publisher.load_release_payload()

    assert payload["version"] == "smoke-2026-03-24"
    assert refreshed == []
