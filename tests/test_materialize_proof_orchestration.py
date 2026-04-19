from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_proof_orchestration.py")


def _write_json(path: Path, generated_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"generated_at": generated_at}) + "\n", encoding="utf-8")


def test_materialize_proof_orchestration_orders_dependencies_and_freshness(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    queue = repo / ".codex-studio" / "published" / "QUEUE.generated.yaml"
    status = repo / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text("mode: append\nitems: []\n", encoding="utf-8")
    _write_json(status, "2026-04-15T06:00:00Z")
    project_config = tmp_path / "fleet.yaml"
    project_config.write_text(
        yaml.safe_dump(
            {
                "id": "fleet",
                "path": str(repo),
                "supervisor_contract": {
                    "proof_jobs": [
                        {
                            "id": "status_plane",
                            "title": "Status plane",
                            "command": "python3 scripts/materialize_status_plane.py",
                            "freshness_window_minutes": 90,
                            "retry": {"max_attempts": 2, "delay_seconds": 5, "retry_on": ["transient_io"]},
                            "dependencies": ["queue_overlay"],
                            "outputs": [
                                {
                                    "path": str(status),
                                    "freshness_window_minutes": 90,
                                    "required": True,
                                }
                            ],
                        },
                        {
                            "id": "queue_overlay",
                            "title": "Queue overlay",
                            "command": "python3 scripts/materialize_fleet_queue_overlay.py",
                            "freshness_window_minutes": 90,
                            "retry": {"max_attempts": 2, "delay_seconds": 5, "retry_on": ["transient_io"]},
                            "dependencies": [],
                            "outputs": [
                                {
                                    "path": str(queue),
                                    "freshness_window_minutes": 90,
                                    "required": True,
                                }
                            ],
                        },
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "PROOF_ORCHESTRATION.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-config",
            str(project_config),
            "--out",
            str(out),
            "--now",
            "2026-04-15T06:30:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert [job["id"] for job in payload["jobs"]] == ["queue_overlay", "status_plane"]
    assert payload["jobs"][0]["output_states"][0]["state"] == "fresh"
    assert payload["summary"]["stale_output_count"] == 0
    assert payload["summary"]["missing_output_count"] == 0


def test_materialize_proof_orchestration_fails_invalid_dependency(tmp_path: Path) -> None:
    project_config = tmp_path / "fleet.yaml"
    project_config.write_text(
        yaml.safe_dump(
            {
                "id": "fleet",
                "supervisor_contract": {
                    "proof_jobs": [
                        {
                            "id": "journey_gates",
                            "freshness_window_minutes": 90,
                            "retry": {"max_attempts": 1},
                            "dependencies": ["missing_status_plane"],
                            "outputs": [{"path": str(tmp_path / "JOURNEY_GATES.generated.json")}],
                        }
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "PROOF_ORCHESTRATION.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-config",
            str(project_config),
            "--out",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert any("depends on unknown job" in error for error in payload["errors"])


def test_materialize_proof_orchestration_fails_fresh_output_with_unacceptable_status(tmp_path: Path) -> None:
    proof = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    proof.write_text(
        json.dumps({"generated_at": "2026-04-15T06:00:00Z", "status": "fail"}) + "\n",
        encoding="utf-8",
    )
    project_config = tmp_path / "fleet.yaml"
    project_config.write_text(
        yaml.safe_dump(
            {
                "id": "fleet",
                "supervisor_contract": {
                    "proof_jobs": [
                        {
                            "id": "flagship_readiness",
                            "freshness_window_minutes": 90,
                            "retry": {"max_attempts": 1},
                            "outputs": [
                                {
                                    "path": str(proof),
                                    "freshness_window_minutes": 90,
                                    "required": True,
                                    "acceptable_statuses": ["pass", "passed", "ready"],
                                }
                            ],
                        }
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "PROOF_ORCHESTRATION.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-config",
            str(project_config),
            "--out",
            str(out),
            "--now",
            "2026-04-15T06:30:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    output_state = payload["jobs"][0]["output_states"][0]
    assert payload["status"] == "fail"
    assert output_state["state"] == "failed_status"
    assert output_state["payload_status"] == "fail"
    assert payload["summary"]["failed_status_output_count"] == 1


def test_published_proof_orchestration_matches_generated_payload(tmp_path: Path) -> None:
    repo_root = Path("/docker/fleet")
    published = repo_root / ".codex-studio" / "published"
    out_path = tmp_path / "PROOF_ORCHESTRATION.generated.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--project-config",
            str(repo_root / "config" / "projects" / "fleet.yaml"),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd="/docker/fleet",
    )

    assert result.returncode == 0, result.stderr
    actual = json.loads((published / "PROOF_ORCHESTRATION.generated.json").read_text(encoding="utf-8"))
    expected = json.loads(out_path.read_text(encoding="utf-8"))
    actual_generated_at = str(actual.pop("generated_at") or "")
    expected.pop("generated_at", None)

    assert actual == expected
    assert actual_generated_at.endswith("Z")
    dt.datetime.fromisoformat(actual_generated_at.replace("Z", "+00:00"))
