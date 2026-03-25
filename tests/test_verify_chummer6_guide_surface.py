from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path("/docker/fleet/scripts/verify_chummer6_guide_surface.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("verify_chummer6_guide_surface", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, rel: str) -> None:
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("placeholder\n", encoding="utf-8")


def _seed_valid_repo(root: Path, *, parts: list[str], horizons: list[str], include_readme_updates: bool = True) -> None:
    for rel in (
        "README.md",
        "DOWNLOAD.md",
        "START_HERE.md",
        "WHAT_CHUMMER6_IS.md",
        "WHERE_TO_GO_DEEPER.md",
        "HOW_CAN_I_HELP.md",
        "GLOSSARY.md",
        "FAQ.md",
        "NOW/current-phase.md",
        "NOW/current-status.md",
        "NOW/public-surfaces.md",
        "PARTS/README.md",
        "HORIZONS/README.md",
        "UPDATES/README.md",
        "UPDATES/2026-03.md",
    ):
        _write(root, rel)
    readme_lines = [
        "## Try it now",
        "DOWNLOAD.md",
        "## How can I help?",
        "HOW_CAN_I_HELP.md",
        "https://chummer.run/participate",
    ]
    if include_readme_updates:
        readme_lines[2:2] = ["## What Changed Lately", "UPDATES/README.md"]
    (root / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    (root / "UPDATES/README.md").write_text(
        "## Latest substantial pushes\n\nplaceholder\n\n## Monthly archive\n\n- [2026-03](./2026-03.md)\n",
        encoding="utf-8",
    )
    (root / "DOWNLOAD.md").write_text(
        "## Current build matrix\nSHA256\nGitHub releases\n",
        encoding="utf-8",
    )
    (root / "HOW_CAN_I_HELP.md").write_text(
        "booster\nhttps://chummer.run/participate\nreview\ncheap baseline\nfree later\nprivate recognition settings remain valid even when badges or leaderboards exist\n",
        encoding="utf-8",
    )
    (root / "FAQ.md").write_text("### Can I actually use this now?\n\nplaceholder\n", encoding="utf-8")
    for slug in parts:
        _write(root, f"PARTS/{slug}.md")
    for slug in horizons:
        _write(root, f"HORIZONS/{slug}.md")


def test_verify_repo_accepts_canonical_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verify = _load_module()
    monkeypatch.setattr(verify, "canonical_part_slugs", lambda: ["design", "core", "ui"])
    monkeypatch.setattr(verify, "canonical_horizon_slugs", lambda: ["alice", "jackpoint"])
    monkeypatch.setattr(verify, "readme_updates_teaser_enabled", lambda: False)
    monkeypatch.setattr(
        verify,
        "load_faq_canon",
        lambda: {"using_chummer6": {"entries": [{"question": "Can I actually use this now?", "required": True}]}},
    )
    monkeypatch.setattr(
        verify,
        "load_help_canon",
        lambda: {"privacy_and_review_safety": ["private recognition settings remain valid even when badges or leaderboards exist"]},
    )
    monkeypatch.setattr(
        verify,
        "load_page_registry",
        lambda: {"page_types": {"part_page": {"forbidden_terms": ["principal-to-user mapping"]}}},
    )
    _seed_valid_repo(tmp_path, parts=["design", "core", "ui"], horizons=["alice", "jackpoint"], include_readme_updates=False)

    result = verify.verify_repo(tmp_path)

    assert result["parts"] == ["design", "core", "ui"]
    assert result["horizons"] == ["alice", "jackpoint"]
    assert result["updates"] == ["2026-03.md"]


def test_verify_repo_requires_updates_teaser_when_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verify = _load_module()
    monkeypatch.setattr(verify, "canonical_part_slugs", lambda: ["design", "core"])
    monkeypatch.setattr(verify, "canonical_horizon_slugs", lambda: ["alice"])
    monkeypatch.setattr(verify, "readme_updates_teaser_enabled", lambda: True)
    monkeypatch.setattr(verify, "load_faq_canon", lambda: {"using_chummer6": {"entries": []}})
    monkeypatch.setattr(verify, "load_help_canon", lambda: {"privacy_and_review_safety": []})
    monkeypatch.setattr(verify, "load_page_registry", lambda: {"page_types": {"part_page": {"forbidden_terms": []}}})
    _seed_valid_repo(tmp_path, parts=["design", "core"], horizons=["alice"], include_readme_updates=False)

    with pytest.raises(RuntimeError, match="recent-update guidance"):
        verify.verify_repo(tmp_path)


def test_verify_repo_rejects_noncanonical_horizon_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verify = _load_module()
    monkeypatch.setattr(verify, "canonical_part_slugs", lambda: ["design", "core"])
    monkeypatch.setattr(verify, "canonical_horizon_slugs", lambda: ["alice"])
    monkeypatch.setattr(verify, "load_faq_canon", lambda: {"using_chummer6": {"entries": []}})
    monkeypatch.setattr(verify, "load_help_canon", lambda: {"privacy_and_review_safety": []})
    monkeypatch.setattr(verify, "load_page_registry", lambda: {"page_types": {"part_page": {"forbidden_terms": []}}})
    _seed_valid_repo(tmp_path, parts=["design", "core"], horizons=["alice"])
    _write(tmp_path, "HORIZONS/ghostwire.md")

    with pytest.raises(RuntimeError, match="non-canonical horizon pages"):
        verify.verify_repo(tmp_path)


def test_verify_repo_rejects_missing_support_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verify = _load_module()
    monkeypatch.setattr(verify, "canonical_part_slugs", lambda: ["design", "core"])
    monkeypatch.setattr(verify, "canonical_horizon_slugs", lambda: ["alice"])
    monkeypatch.setattr(verify, "load_faq_canon", lambda: {"using_chummer6": {"entries": []}})
    monkeypatch.setattr(verify, "load_help_canon", lambda: {"privacy_and_review_safety": []})
    monkeypatch.setattr(verify, "load_page_registry", lambda: {"page_types": {"part_page": {"forbidden_terms": []}}})
    _seed_valid_repo(tmp_path, parts=["design", "core"], horizons=["alice"])
    (tmp_path / "HOW_CAN_I_HELP.md").write_text("https://chummer.run/participate only\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="HOW_CAN_I_HELP.md is missing support tokens"):
        verify.verify_repo(tmp_path)
