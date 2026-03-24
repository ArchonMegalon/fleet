from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_compile_manifest.py")


def test_materialize_compile_manifest(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    projects_dir = tmp_path / "config" / "projects"
    published.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)

    (projects_dir / "fleet.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "fleet",
                "path": str(repo_root),
                "lifecycle": "dispatchable",
                "queue": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (published / "WORKPACKAGES.generated.yaml").write_text(
        "\n".join(
            [
                "work_packages:",
                "  - package_id: fleet-a",
                "    title: Overlay Slice",
                "    allowed_paths:",
                "      - src/a.py",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (published / "STATUS_PLANE.generated.yaml").write_text("contract_name: fleet.status_plane\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--out",
            str(published / "compile.manifest.json"),
            "--projects-dir",
            str(projects_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd="/docker/fleet",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    assert payload["target_id"] == "fleet"
    assert payload["target_type"] == "project"
    assert payload["dispatchable_truth_ready"] is True
    assert payload["stages"]["package_compile"] is True
    assert "WORKPACKAGES.generated.yaml" in payload["artifacts"]
