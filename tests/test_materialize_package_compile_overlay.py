from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_package_compile_overlay.py")


def test_materialize_package_compile_overlay_writes_queue_bound_front_package(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    published.mkdir(parents=True, exist_ok=True)
    (published / "QUEUE.generated.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "prepend",
                "items": ["Publish installer proof", "Refresh release-channel docs"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo_root), "--project-id", "ui"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((published / "WORKPACKAGES.generated.yaml").read_text(encoding="utf-8"))
    assert payload["source_queue_fingerprint"]
    assert len(payload["work_packages"]) == 1
    manifest_payload = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    package = payload["work_packages"][0]
    assert package["package_kind"] == "package_compile"
    assert package["allowed_lanes"] == ["core_authority"]
    assert package["allowed_paths"] == [".codex-studio/published/WORKPACKAGES.generated.yaml"]
    assert package["owned_surfaces"] == ["package_compile:ui"]
    assert "WORKPACKAGES.generated.yaml" in manifest_payload["artifacts"]
    assert manifest_payload["stages"]["package_compile"] is True


def test_materialize_package_compile_overlay_writes_empty_overlay_for_empty_queue(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    published.mkdir(parents=True, exist_ok=True)
    (published / "QUEUE.generated.yaml").write_text(
        yaml.safe_dump({"mode": "prepend", "items": []}, sort_keys=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo_root), "--project-id", "core"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((published / "WORKPACKAGES.generated.yaml").read_text(encoding="utf-8"))
    manifest_payload = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    assert payload["source_queue_fingerprint"]
    assert payload["work_packages"] == []
    assert "WORKPACKAGES.generated.yaml" in manifest_payload["artifacts"]


def test_materialize_package_compile_overlay_fingerprints_effective_queue(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    published.mkdir(parents=True, exist_ok=True)
    (published / "QUEUE.generated.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "prepend",
                "items": ["Overlay A", "Overlay B"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    (projects_dir / "ui.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "ui",
                "path": str(repo_root),
                "queue": ["Base Queue Item"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--project-id",
            "ui",
            "--projects-dir",
            str(projects_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((published / "WORKPACKAGES.generated.yaml").read_text(encoding="utf-8"))
    expected_queue = ["Overlay A", "Overlay B", "Base Queue Item"]
    fingerprint = __import__("hashlib").sha1(
        json.dumps(expected_queue, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    assert payload["source_queue_fingerprint"] == fingerprint


def test_materialize_package_compile_overlay_resolves_queue_sources_before_fingerprint(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    published.mkdir(parents=True, exist_ok=True)
    (repo_root / "WORKLIST.md").write_text("- [queued] wl-1 Source Queue Slice\n", encoding="utf-8")
    (published / "QUEUE.generated.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "prepend",
                "items": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    (projects_dir / "ui.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "ui",
                "path": str(repo_root),
                "queue": [],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--project-id",
            "ui",
            "--projects-dir",
            str(projects_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((published / "WORKPACKAGES.generated.yaml").read_text(encoding="utf-8"))
    expected_queue = ["Source Queue Slice"]
    fingerprint = __import__("hashlib").sha1(
        json.dumps(expected_queue, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    assert payload["source_queue_fingerprint"] == fingerprint
    assert len(payload["work_packages"]) == 1


def test_published_package_compile_overlay_matches_generated_payload(tmp_path: Path) -> None:
    repo_root = Path("/docker/fleet")
    published = repo_root / ".codex-studio" / "published"
    out_path = tmp_path / "WORKPACKAGES.generated.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--project-id",
            "fleet",
            "--projects-dir",
            str(repo_root / "config" / "projects"),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd="/docker/fleet",
    )

    assert result.returncode == 0, result.stderr
    actual = yaml.safe_load((published / "WORKPACKAGES.generated.yaml").read_text(encoding="utf-8"))
    expected = yaml.safe_load(out_path.read_text(encoding="utf-8"))

    assert actual == expected
