from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/external_proof_paths.py")


def _load_module():
    previous_sys_path = list(sys.path)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("external_proof_paths", SCRIPT)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = previous_sys_path


def _write_release_channel(path: Path, *, status: str, generated_at: str, artifacts: int = 1) -> None:
    payload = {
        "status": status,
        "generatedAt": generated_at,
        "artifacts": [{"artifactId": f"artifact-{index}"} for index in range(artifacts)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_resolve_release_channel_path_prefers_newer_published_portal_shelf(tmp_path: Path) -> None:
    module = _load_module()
    registry = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    portal = tmp_path / "portal" / "RELEASE_CHANNEL.generated.json"
    docker = tmp_path / "docker" / "RELEASE_CHANNEL.generated.json"
    _write_release_channel(registry, status="published", generated_at="2026-04-08T03:11:24Z")
    _write_release_channel(portal, status="published", generated_at="2026-04-09T08:03:08Z")
    _write_release_channel(docker, status="unpublished", generated_at="2026-04-09T11:32:21Z")

    resolved = module.resolve_release_channel_path(candidates=(registry, portal, docker))

    assert resolved == portal


def test_resolve_release_channel_path_falls_back_to_newest_artifactful_candidate_when_none_are_published(tmp_path: Path) -> None:
    module = _load_module()
    registry = tmp_path / "registry" / "RELEASE_CHANNEL.generated.json"
    portal = tmp_path / "portal" / "RELEASE_CHANNEL.generated.json"
    docker = tmp_path / "docker" / "RELEASE_CHANNEL.generated.json"
    _write_release_channel(registry, status="draft", generated_at="2026-04-08T03:11:24Z", artifacts=0)
    _write_release_channel(portal, status="draft", generated_at="2026-04-09T08:03:08Z")
    _write_release_channel(docker, status="unpublished", generated_at="2026-04-09T11:32:21Z")

    resolved = module.resolve_release_channel_path(candidates=(registry, portal, docker))

    assert resolved == docker
