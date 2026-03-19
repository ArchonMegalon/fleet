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


def _seed_valid_repo(root: Path, *, parts: list[str], horizons: list[str]) -> None:
    for rel in (
        "README.md",
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
        "UPDATES/2026-03.md",
    ):
        _write(root, rel)
    (root / "README.md").write_text(
        "## How can I help?\nHOW_CAN_I_HELP.md\nparticipate/codex\n",
        encoding="utf-8",
    )
    (root / "HOW_CAN_I_HELP.md").write_text(
        "booster\nparticipate/codex\nreview\ncheap baseline\nfree later\nprivate recognition settings remain valid even when badges or leaderboards exist\n",
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
    _seed_valid_repo(tmp_path, parts=["design", "core", "ui"], horizons=["alice", "jackpoint"])

    result = verify.verify_repo(tmp_path)

    assert result["parts"] == ["design", "core", "ui"]
    assert result["horizons"] == ["alice", "jackpoint"]
    assert result["updates"] == ["2026-03.md"]


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
    (tmp_path / "HOW_CAN_I_HELP.md").write_text("participate/codex only\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="HOW_CAN_I_HELP.md is missing support tokens"):
        verify.verify_repo(tmp_path)
