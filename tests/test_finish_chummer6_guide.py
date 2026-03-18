from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest


MODULE_PATH = Path("/docker/fleet/scripts/finish_chummer6_guide.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("finish_chummer6_guide", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finisher_uses_canonical_horizon_set() -> None:
    finish = _load_module()

    assert set(finish.PARTS) >= {
        "design",
        "core",
        "ui",
        "mobile",
        "hub",
        "ui-kit",
        "hub-registry",
        "media-factory",
    }
    assert set(finish.HORIZONS) == {
        "alice",
        "jackpoint",
        "karma-forge",
        "nexus-pan",
        "runbook-press",
        "runsite",
    }


def test_audit_generated_repo_rejects_any_svg_asset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(finish, "GUIDE_REPO", tmp_path)
    monkeypatch.setattr(finish, "PARTS", {"core": {}})
    monkeypatch.setattr(finish, "HORIZONS", {"alice": {}})

    for rel in (
        "README.md",
        "START_HERE.md",
        "WHAT_CHUMMER6_IS.md",
        "WHERE_TO_GO_DEEPER.md",
        "PARTS/README.md",
        "HORIZONS/README.md",
        "assets/hero/chummer6-hero.png",
        "assets/hero/poc-warning.png",
        "assets/pages/start-here.png",
        "assets/pages/what-chummer6-is.png",
        "assets/pages/where-to-go-deeper.png",
        "assets/pages/current-phase.png",
        "assets/pages/current-status.png",
        "assets/pages/public-surfaces.png",
        "assets/pages/parts-index.png",
        "assets/pages/horizons-index.png",
        "assets/parts/core.png",
        "assets/horizons/alice.png",
        "assets/horizons/details/alice-scene.png",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            path.write_text("placeholder\n", encoding="utf-8")
        else:
            path.write_bytes(b"png")

    stray = tmp_path / "assets/pages/start-here.svg"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text("<svg/>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="forbidden svg assets"):
        finish.audit_generated_repo()


def test_main_finally_purges_retired_svg_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(finish, "GUIDE_REPO", tmp_path)
    monkeypatch.setattr(finish, "ensure_github_repo", lambda: None)
    monkeypatch.setattr(finish, "ensure_local_repo", lambda: None)
    monkeypatch.setattr(finish, "write_design_scope", lambda: None)
    monkeypatch.setattr(finish, "audit_generated_repo", lambda: None)
    monkeypatch.setattr(finish.sys, "argv", ["finish_chummer6_guide.py"])

    retired_svg = tmp_path / "assets/pages/start-here.svg"

    def _boom() -> None:
        retired_svg.parent.mkdir(parents=True, exist_ok=True)
        retired_svg.write_text("<svg/>", encoding="utf-8")
        raise RuntimeError("boom")

    monkeypatch.setattr(finish, "write_guide_repo", _boom)

    with pytest.raises(RuntimeError, match="boom"):
        finish.main()

    assert not retired_svg.exists()


def test_remove_forbidden_purges_noncanonical_horizon_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(finish, "GUIDE_REPO", tmp_path)
    monkeypatch.setattr(finish, "HORIZONS", {"alice": {}, "jackpoint": {}})

    for rel in (
        "HORIZONS/alice.md",
        "HORIZONS/ghostwire.md",
        "assets/horizons/alice.png",
        "assets/horizons/ghostwire.png",
        "assets/horizons/details/alice-scene.png",
        "assets/horizons/details/ghostwire-scene.png",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".md":
            path.write_text("placeholder\n", encoding="utf-8")
        else:
            path.write_bytes(b"png")

    finish.remove_forbidden()

    assert (tmp_path / "HORIZONS/alice.md").exists()
    assert (tmp_path / "assets/horizons/alice.png").exists()
    assert (tmp_path / "assets/horizons/details/alice-scene.png").exists()
    assert not (tmp_path / "HORIZONS/ghostwire.md").exists()
    assert not (tmp_path / "assets/horizons/ghostwire.png").exists()
    assert not (tmp_path / "assets/horizons/details/ghostwire-scene.png").exists()


def test_require_guide_media_bytes_falls_back_to_horizons_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(finish, "GUIDE_REPO", tmp_path)
    fallback = tmp_path / "assets/pages/horizons-index.png"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    fallback.write_bytes(b"png")

    data = finish.require_guide_media_bytes(tmp_path / "assets/horizons/runsite.png", {})

    assert data == b"png"


def test_publish_generated_repo_commits_and_pushes_when_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(finish, "GUIDE_REPO", tmp_path)
    monkeypatch.setattr(finish, "auto_publish_enabled", lambda: True)

    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str, cwd=None, check: bool = True):
        calls.append(tuple(args))
        stdout = ""
        if args[:4] == ("git", "config", "--get", "user.email"):
            stdout = ""
        elif args[:4] == ("git", "config", "--get", "user.name"):
            stdout = ""
        elif args[:3] == ("git", "status", "--short"):
            stdout = " M README.md\n"
        return types.SimpleNamespace(stdout=stdout)

    monkeypatch.setattr(finish, "run", fake_run)

    finish.publish_generated_repo()

    assert ("git", "add", "-A") in calls
    assert ("git", "commit", "-m", "Refresh Chummer6 guide") in calls
    assert ("git", "push", "origin", "HEAD:main") in calls
