from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m126_fleet_horizon_handoff_queue.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _registry(*, design_gate_status: str) -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 126,
                "title": "Horizon handoff gates and bounded research-to-build conversion",
                "wave": "W17",
                "status": "not_started",
                "owners": ["fleet", "chummer6-design"],
                "dependencies": [114, 115, 123, 124, 125],
                "work_tasks": [
                    {
                        "id": "126.1",
                        "owner": "chummer6-design",
                        "title": "Add horizon handoff gates and bounded research packet requirements.",
                        "status": design_gate_status,
                    },
                    {
                        "id": "126.2",
                        "owner": "fleet",
                        "title": "Teach the supervisor to stage bounded horizon-conversion queue slices only after owner handoff gates are satisfied.",
                        "status": "not_started",
                    },
                ],
            },
            {
                "id": 132,
                "title": "Deterministic horizon implementation tranche",
                "wave": "W20",
                "status": "not_started",
                "owners": ["chummer6-core"],
            },
        ],
    }


def _queue_item(package_id: str, work_task_id: str, title: str, task: str, milestone_id: int, repo: str) -> dict:
    return {
        "title": title,
        "task": task,
        "package_id": package_id,
        "milestone_id": milestone_id,
        "work_task_id": work_task_id,
        "frontier_id": 6039766471 if work_task_id == "126.2" else 6039766472,
        "status": "not_started",
        "wave": "W17" if milestone_id == 126 else "W20",
        "repo": repo,
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"] if work_task_id == "126.2" else ["src"],
        "owned_surfaces": ["teach_the_supervisor_to_stage:fleet"] if work_task_id == "126.2" else ["deterministic_horizons:core"],
    }


def _queue_payload() -> dict:
    return {
        "generated_at": "2026-05-05T10:00:00Z",
        "items": [
            _queue_item(
                "next90-m126-fleet-teach-the-supervisor-to-stage-bounded-horizon-conversion",
                "126.2",
                "Teach the supervisor to stage bounded horizon-conversion queue slices only after owner handoff gates are satisfied.",
                "Teach the supervisor to stage bounded horizon-conversion queue slices only after owner handoff gates are satisfied.",
                126,
                "fleet",
            ),
            _queue_item(
                "next90-m132-core-horizon-tranche",
                "132.1",
                "Deterministic horizon implementation tranche",
                "Implement deterministic horizon tranche work only after handoff truth is real.",
                132,
                "chummer6-core",
            ),
        ],
    }


def _horizon_registry(*, complete_handoff: bool) -> dict:
    row = {
        "id": "alice",
        "title": "ALICE",
        "owning_repos": ["chummer6-core"],
        "owner_handoff_gate": "Executable owner proof is required before implementation backlog staging.",
    }
    if complete_handoff:
        row["allowed_surfaces"] = ["simulation", "proof"]
        row["proof_gate"] = "owner_executable_proof_required"
        row["public_claim_posture"] = "research_only_until_owner_proof"
        row["stop_condition"] = "stop_when_owner_proof_is_missing"
    return {"product": "chummer", "horizons": [row]}


def _next90_guide() -> str:
    return """# Next 90 day product advance guide

## Wave 17 - turn public signal and horizons into governed implementation lanes

### 126. Horizon handoff gates and bounded research-to-build conversion

Exit: public-eligible horizons with demand have owner handoff gates, bounded research packets, executable proof requirements, public-claim stop rules, and Fleet scheduling only after Chummer-owned canon names the owner, allowed surface, proof gate, and stop condition.
"""


def _fixture_tree(tmp_path: Path, *, design_gate_status: str, complete_handoff: bool) -> dict[str, Path]:
    registry = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    design_queue = tmp_path / "DESIGN_NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    horizon_registry = tmp_path / "HORIZON_REGISTRY.yaml"
    next90_guide = tmp_path / "NEXT_90_DAY_PRODUCT_ADVANCE_GUIDE.md"
    artifact = tmp_path / "NEXT90_M126_FLEET_HORIZON_HANDOFF_QUEUE.generated.json"
    markdown = tmp_path / "NEXT90_M126_FLEET_HORIZON_HANDOFF_QUEUE.generated.md"

    _write_yaml(registry, _registry(design_gate_status=design_gate_status))
    _write_yaml(queue, _queue_payload())
    _write_yaml(design_queue, _queue_payload())
    _write_yaml(horizon_registry, _horizon_registry(complete_handoff=complete_handoff))
    _write_text(next90_guide, _next90_guide())

    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "horizon_registry": horizon_registry,
        "next90_guide": next90_guide,
        "artifact": artifact,
        "markdown": markdown,
    }


def _run_materializer(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(paths["artifact"]),
            "--markdown-output",
            str(paths["markdown"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--horizon-registry",
            str(paths["horizon_registry"]),
            "--next90-guide",
            str(paths["next90_guide"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class MaterializeNext90M126FleetHorizonHandoffQueueTests(unittest.TestCase):
    def test_materialize_reports_blocked_horizon_items_without_failing_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m126-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), design_gate_status="not_started", complete_handoff=False)

            result = _run_materializer(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["canonical_alignment"]["state"], "pass")
            self.assertEqual(payload["queue_gate_monitor"]["blocked_horizon_queue_item_count"], 1)
            self.assertEqual(payload["queue_gate_monitor"]["ready_horizon_queue_item_count"], 0)
            self.assertIn("design handoff gate task 126.1 is not done", payload["queue_gate_monitor"]["blocked_items"][0]["reasons"])
            self.assertTrue(payload["package_closeout"]["warnings"])

    def test_materialize_marks_horizon_items_ready_once_handoff_truth_is_complete(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m126-materialize-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), design_gate_status="complete", complete_handoff=True)

            result = _run_materializer(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["queue_gate_monitor"]["blocked_horizon_queue_item_count"], 0)
            self.assertEqual(payload["queue_gate_monitor"]["ready_horizon_queue_item_count"], 1)
            self.assertFalse(payload["package_closeout"]["warnings"])
            markdown = paths["markdown"].read_text(encoding="utf-8")
            self.assertIn("blocked horizon queue items: 0", markdown)


if __name__ == "__main__":
    unittest.main()
