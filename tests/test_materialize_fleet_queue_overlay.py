from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_fleet_queue_overlay.py")


def _queue_fingerprint(items: list[object]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return __import__("hashlib").sha1(payload.encode("utf-8")).hexdigest()


def test_materialize_fleet_queue_overlay_binds_current_source_queue(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    published.mkdir(parents=True, exist_ok=True)
    (repo_root / "WORKLIST.md").write_text(
        "\n".join(
            [
                "# Worklist Queue",
                "",
                "| ID | Status | Priority | Task | Owner | Notes |",
                "|---|---|---|---|---|---|",
                "| WL-300 | queued | P0 | Source Queue Slice | agent | note |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    projects_dir = tmp_path / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    (projects_dir / "fleet.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "fleet",
                "path": str(repo_root),
                "queue": ["Base Queue Slice"],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "append"}],
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
            "fleet",
            "--projects-dir",
            str(projects_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load((published / "QUEUE.generated.yaml").read_text(encoding="utf-8"))
    assert payload["mode"] == "append"
    assert payload["items"] == []
    assert payload["source_queue_fingerprint"] == _queue_fingerprint(["Base Queue Slice", "Source Queue Slice"])


def test_published_fleet_queue_overlay_matches_generated_payload(tmp_path: Path) -> None:
    repo_root = Path("/docker/fleet")
    out_path = tmp_path / "QUEUE.generated.yaml"

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
    actual = yaml.safe_load((repo_root / ".codex-studio" / "published" / "QUEUE.generated.yaml").read_text(encoding="utf-8"))
    expected = yaml.safe_load(out_path.read_text(encoding="utf-8"))

    assert actual == expected
