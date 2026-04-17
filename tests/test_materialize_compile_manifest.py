from __future__ import annotations

import datetime as dt
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
    assert payload["dispatchable_truth_contract"]["scope"] == "execution_truth_only"
    assert payload["dispatchable_truth_contract"]["package_compile_required_separately"] is True
    assert payload["dispatchable_truth_contract"]["capacity_compile_required_separately"] is True
    assert payload["stages"]["package_compile"] is True
    assert "WORKPACKAGES.generated.yaml" in payload["artifacts"]


def test_published_compile_manifest_matches_generated_payload(tmp_path: Path) -> None:
    repo_root = Path("/docker/fleet")
    published = repo_root / ".codex-studio" / "published"
    out_path = tmp_path / "compile.manifest.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--out",
            str(out_path),
            "--projects-dir",
            str(repo_root / "config" / "projects"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd="/docker/fleet",
    )

    assert result.returncode == 0, result.stderr
    actual = json.loads((published / "compile.manifest.json").read_text(encoding="utf-8"))
    expected = json.loads(out_path.read_text(encoding="utf-8"))
    actual_published_at = str(actual.pop("published_at") or "")
    expected.pop("published_at", None)

    assert actual == expected
    assert actual_published_at.endswith("Z")
    dt.datetime.fromisoformat(actual_published_at.replace("Z", "+00:00"))


def test_materialize_compile_manifest_accepts_generated_release_proof_artifacts(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    published = repo_root / ".codex-studio" / "published"
    projects_dir = tmp_path / "config" / "projects"
    published.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)

    (projects_dir / "ui.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "chummer6-ui",
                "path": str(repo_root),
                "lifecycle": "live",
                "queue": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (published / "WORKPACKAGES.generated.yaml").write_text("source_queue_fingerprint: 97d170e1550eee4afc0af065b78cda302a97674c\nwork_packages: []\n", encoding="utf-8")
    (published / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").write_text("{}\n", encoding="utf-8")
    (published / "UI_LOCAL_RELEASE_PROOF.generated.json").write_text("{}\n", encoding="utf-8")
    (published / "RELEASE_CHANNEL.generated.json").write_text("{}\n", encoding="utf-8")
    (published / "releases.json").write_text("{}\n", encoding="utf-8")

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
    assert "UI_LINUX_DESKTOP_EXIT_GATE.generated.json" in payload["artifacts"]
    assert "UI_LOCAL_RELEASE_PROOF.generated.json" in payload["artifacts"]
    assert "RELEASE_CHANNEL.generated.json" in payload["artifacts"]
    assert "releases.json" in payload["artifacts"]


def test_materialize_compile_manifest_ignores_leaked_atomic_temp_artifacts(tmp_path: Path) -> None:
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
        "source_queue_fingerprint: 97d170e1550eee4afc0af065b78cda302a97674c\nwork_packages: []\n",
        encoding="utf-8",
    )
    (published / "JOURNEY_GATES.generated.json").write_text("{}\n", encoding="utf-8")
    (published / "JOURNEY_GATES.generated.654xn6et.json").write_text("{}\n", encoding="utf-8")
    (published / "SUPPORT_CASE_SOURCE_MIRROR.generated.q19zfnwe.json").write_text("{}\n", encoding="utf-8")

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
    assert "JOURNEY_GATES.generated.json" in payload["artifacts"]
    assert "JOURNEY_GATES.generated.654xn6et.json" not in payload["artifacts"]
    assert "SUPPORT_CASE_SOURCE_MIRROR.generated.q19zfnwe.json" not in payload["artifacts"]
