from __future__ import annotations

import importlib.util
import json
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
    assert set(finish.HORIZONS) == set(finish.canonical_horizon_slugs())


def test_horizon_pages_carry_design_public_body_and_readable_foundations() -> None:
    finish = _load_module()

    black_ledger = finish.horizon_page("black-ledger", finish.HORIZONS["black-ledger"])
    karma_forge = finish.horizon_page("karma-forge", finish.HORIZONS["karma-forge"])

    assert "## Mission Market" in black_ledger
    assert "## Rule Environment" in karma_forge
    assert "## Canon Links" not in black_ledger
    assert "## Canon Links" not in karma_forge
    assert "products/chummer/" not in black_ledger
    assert "products/chummer/" not in karma_forge
    assert "## What would need to exist first" not in black_ledger
    assert "## What would need to exist first" not in karma_forge
    assert "- C0" not in black_ledger
    assert "- D2" not in karma_forge


def test_audit_generated_repo_rejects_any_svg_asset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(finish, "GUIDE_REPO", tmp_path)
    monkeypatch.setattr(finish, "PARTS", {"core": {}})
    monkeypatch.setattr(finish, "HORIZONS", {"alice": {}})
    monkeypatch.setattr(
        finish,
        "FAQ_SECTIONS",
        {"using_chummer6": {"entries": [{"question": "Can I actually use this now?", "required": True}]}},
    )

    for rel in (
        "README.md",
        "DOWNLOAD.md",
        "START_HERE.md",
        "WHAT_CHUMMER6_IS.md",
        "WHERE_TO_GO_DEEPER.md",
        "HOW_CAN_I_HELP.md",
        "PARTS/README.md",
        "HORIZONS/README.md",
        "assets/hero/chummer6-hero.png",
        "assets/hero/preview-warning.png",
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
            if rel == "README.md":
                path.write_text(
                    "## Pick your path\n## Current posture\n## What Changed Lately\nUPDATES/README.md\n## Try it now\nDOWNLOAD.md\n## What this means at a real table\n## Why this is worth watching\n## How can I help?\nHOW_CAN_I_HELP.md\nhttps://chummer.run/participate\n## Preview builds\nhttps://github.com/ArchonMegalon/Chummer6/releases\n",
                    encoding="utf-8",
                )
            elif rel == "DOWNLOAD.md":
                path.write_text("## Current build matrix\nSHA256\nGitHub releases\n", encoding="utf-8")
            elif rel == "HOW_CAN_I_HELP.md":
                path.write_text("booster\nhttps://chummer.run/participate\ncheap baseline\nreview\nfree later\n", encoding="utf-8")
            elif rel == "FAQ.md":
                path.write_text("### Can I actually use this now?\n\nplaceholder\n", encoding="utf-8")
            else:
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


def test_main_docs_only_generates_markdown_without_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    guide_root = tmp_path / "guide"
    design_scope = tmp_path / "design" / "guide.md"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    status_plane.write_text(
        """
readiness_summary:
  counts: {}
deployment_posture:
  promotion_stage: protected_preview
  access_posture: protected_preview
projects: []
groups: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(finish, "GUIDE_REPO", guide_root)
    monkeypatch.setattr(finish, "DESIGN_SCOPE", design_scope)
    monkeypatch.setattr(finish, "STATUS_PLANE_PATH", status_plane)
    monkeypatch.setattr(finish, "ensure_github_repo", lambda: None)
    monkeypatch.setattr(finish, "ensure_local_repo", lambda: None)
    monkeypatch.setattr(finish, "publish_generated_repo", lambda: None)
    monkeypatch.setattr(finish.sys, "argv", ["finish_chummer6_guide.py", "--docs-only"])

    assert finish.main() == 0
    assert (guide_root / "README.md").exists()
    assert (guide_root / "FAQ.md").exists()
    assert (guide_root / "UPDATES" / "README.md").exists()
    assert (guide_root / "assets").exists() is False
    assert design_scope.exists()


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


def test_hub_participate_url_uses_override(monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setenv("CHUMMER6_HUB_PARTICIPATE_URL", "https://example.com/custom/")

    assert finish.hub_participate_url() == "https://example.com/custom"


def test_download_page_markdown_projects_release_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(
        finish,
        "_release_matrix_payload",
        lambda: {
            "version": "v-test",
            "channel": "preview",
            "publishedAt": "2026-03-19T17:00:00Z",
            "artifacts": [
                {
                    "platform": "windows",
                    "arch": "x64",
                    "head": "avalonia",
                    "kind": "archive",
                    "platform_label": "Chummer 6 Avalonia Windows x64",
                    "url": "https://chummer.run/downloads/files/chummer-win-x64.zip",
                    "filename": "chummer-win-x64.zip",
                    "sha256": "abc123",
                    "sizeBytes": 123456,
                }
            ],
        },
    )

    text = finish.download_page_markdown()

    assert "## Current build matrix" in text
    assert "Chummer 6 Avalonia Windows x64" in text
    assert "advanced manual preview archive" in text
    assert "GitHub releases" in text


def test_release_matrix_payload_normalizes_registry_artifact_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    registry_payload = {
        "version": "unpublished",
        "channelId": "preview",
        "publishedAt": "2026-03-25T11:08:24Z",
        "artifacts": [
            {
                "artifactId": "avalonia-linux-x64-archive",
                "head": "avalonia",
                "platform": "linux",
                "arch": "x64",
                "kind": "archive",
                "fileName": "chummer-avalonia-linux-x64.tar.gz",
                "downloadUrl": "/downloads/files/chummer-avalonia-linux-x64.tar.gz",
                "sha256": "abc123",
                "sizeBytes": 42,
                "platformLabel": "Avalonia Desktop Linux X64",
            }
        ],
    }
    registry_path = tmp_path / "RELEASE_CHANNEL.generated.json"
    registry_path.write_text(json.dumps(registry_payload), encoding="utf-8")
    monkeypatch.setattr(finish, "REGISTRY_RELEASE_CHANNEL_PATH", registry_path)
    monkeypatch.setattr(finish, "EA_RELEASE_MATRIX_PATH", tmp_path / "unused_state.json")
    monkeypatch.setattr(finish, "REGISTRY_COMPAT_RELEASES_PATH", tmp_path / "unused_releases.json")
    monkeypatch.setattr(finish, "maybe_refresh_release_matrix", lambda: None)

    payload = finish._release_matrix_payload()

    assert payload["channel"] == "preview"
    assert payload["artifacts"] == [
        {
            "id": "avalonia-linux-x64-archive",
            "platform": "linux",
            "arch": "x64",
            "head": "avalonia",
            "kind": "archive",
            "platform_label": "Avalonia Desktop Linux X64",
            "url": "https://chummer.run/downloads/files/chummer-avalonia-linux-x64.tar.gz",
            "filename": "chummer-avalonia-linux-x64.tar.gz",
            "sha256": "abc123",
            "sizeBytes": 42,
        }
    ]


def test_page_markdown_dedents_body_blocks() -> None:
    finish = _load_module()

    rendered = finish.page_markdown(
        "Example",
        """
                ## Heading

                - first
                - second
        """,
    )

    assert rendered.startswith("# Example\n\n## Heading\n")
    assert "\n                ## Heading" not in rendered


def test_recent_change_entries_filter_noise_and_dedupe_topics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    finish = _load_module()
    guide = tmp_path / "guide"
    hub = tmp_path / "hub"
    guide.mkdir()
    hub.mkdir()
    (guide / ".git").mkdir()
    (hub / ".git").mkdir()

    monkeypatch.setattr(
        finish,
        "CHANGELOG_REPOS",
        (
            ("guide", "Guide", guide),
            ("hub", "chummer.run", hub),
        ),
    )
    monkeypatch.setattr(finish, "CHANGELOG_REPO_RANK", {"guide": 0, "hub": 1})

    def fake_run(*args: str, cwd=None, check: bool = True):
        cwd = Path(cwd)
        if cwd == guide:
            stdout = "\n".join(
                [
                    "aaa1111\t100\t2026-03-19\tRefresh guide download surface",
                    "aaa1112\t99\t2026-03-19\tPublish regenerated Chummer6 docs (docs-only)",
                    "aaa1113\t98\t2026-03-19\tWipe Chummer6 repository contents",
                    "bbb2222\t90\t2026-03-19\tchore: checkpoint current work",
                ]
            )
        elif cwd == hub:
            stdout = "\n".join(
                [
                    "ccc3333\t110\t2026-03-20\tCanonize guide download surface",
                    "ddd4444\t80\t2026-03-19\tRefresh mirrored public guide canon",
                    "eee5555\t70\t2026-03-19\tAdd Emailit-backed identity mail delivery",
                ]
            )
        else:
            stdout = ""
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(finish, "run", fake_run)

    entries = finish.recent_change_entries(limit=5, per_repo_limit=5)

    assert len(entries) == 2
    assert entries[0]["repo_id"] == "hub"
    assert entries[0]["title"] == "The download shelf got more honest."
    assert entries[1]["title"] == "Account mail moved closer to real delivery."


def test_updates_index_markdown_mentions_excluded_repos(monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    monkeypatch.setattr(
        finish,
        "recent_change_entries",
        lambda limit=9, per_repo_limit=12: [
            {
                "date": "2026-03-20",
                "title": "The download shelf got more honest.",
                "repo_label": "Guide",
                "subject": "Refresh guide download surface",
                "what_changed_for_you": "Preview artifacts are easier to find.",
                "still_not_promised": "installer-grade polish everywhere.",
            }
        ],
    )

    text = finish.updates_index_markdown()

    assert "Fleet and EA pushes do not appear here." not in text
    assert "Latest visible changes" in text
    assert "Monthly archive" in text


def test_status_plane_current_status_lines_use_canonical_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    status_plane.write_text(
        """
contract_name: fleet.status_plane
readiness_summary:
  counts:
    repo_local_complete: 1
    boundary_pure: 2
deployment_posture:
  promotion_stage: protected_preview
  access_posture: protected_preview
projects:
  - id: guide
    deployment_access_posture: protected_preview
groups:
  - id: chummer-vnext
    publicly_promoted: false
    blocking_owner_projects: [guide]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(finish, "STATUS_PLANE_PATH", status_plane)

    lines = finish.status_plane_current_status_short_lines()

    assert any("STATUS_PLANE.generated.yaml" in line for line in lines)
    assert any("repo_local_complete:1" in line and "boundary_pure:2" in line for line in lines)
    assert any("promotion `protected_preview`" in line for line in lines)


def test_require_status_plane_payload_fails_when_required_sections_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finish = _load_module()
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    status_plane.write_text("projects: []\ngroups: []\n", encoding="utf-8")
    monkeypatch.setattr(finish, "STATUS_PLANE_PATH", status_plane)

    with pytest.raises(ValueError, match="missing readiness/deployment posture"):
        finish.require_status_plane_payload()


def test_status_plane_public_surface_lines_list_preview_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finish = _load_module()
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    status_plane.write_text(
        """
projects:
  - id: guide
    deployment_access_posture: protected_preview
    deployment_promotion_stage: protected_preview
  - id: fleet
    deployment_access_posture: internal
    deployment_promotion_stage: internal
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(finish, "STATUS_PLANE_PATH", status_plane)

    lines = finish.status_plane_public_surface_lines()

    assert lines == ["guide (protected_preview, promotion protected_preview)"]
