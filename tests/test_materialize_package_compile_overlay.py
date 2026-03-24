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
