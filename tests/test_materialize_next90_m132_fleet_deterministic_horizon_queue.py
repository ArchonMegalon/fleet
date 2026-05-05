from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m132_fleet_deterministic_horizon_queue.py")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _registry(*, deterministic_gate_status: str) -> dict:
    return {
        "program_wave": "next_90_day_product_advance",
        "milestones": [
            {
                "id": 132,
                "title": "Deterministic horizon implementation tranche: NEXUS-PAN, ALICE, KARMA FORGE, Knowledge Fabric, and Local Co-Processor",
                "wave": "W20",
                "status": "not_started",
                "owners": ["fleet", "chummer6-design", "chummer6-core"],
                "dependencies": [114, 115, 126],
                "work_tasks": [
                    {
                        "id": "132.6",
                        "owner": "fleet",
                        "title": "Schedule deterministic horizon slices only after owner handoff gates, proof scopes, and stop conditions are satisfied.",
                        "status": "not_started",
                    },
                    {
                        "id": "132.7",
                        "owner": "chummer6-design",
                        "title": "Close deterministic horizon canon, public claim language, owner handoff gates, and build-path promotion criteria.",
                        "status": deterministic_gate_status,
                    },
                ],
            },
            {
                "id": 126,
                "title": "Horizon handoff gates and bounded research-to-build conversion",
                "wave": "W17",
                "status": "complete",
                "owners": ["fleet", "chummer6-design"],
                "dependencies": [114, 115, 123, 124, 125],
                "work_tasks": [
                    {
                        "id": "126.1",
                        "owner": "chummer6-design",
                        "title": "Add horizon handoff gates, build-path promotion criteria, and public-claim stop rules to the horizon registry and guide canon.",
                        "status": "complete",
                    }
                ],
            },
        ],
    }


def _queue_item() -> dict:
    return {
        "title": "Schedule deterministic horizon slices only after owner handoff gates, proof scopes, and stop conditions are satisfied.",
        "task": "Schedule deterministic horizon slices only after owner handoff gates, proof scopes, and stop conditions are satisfied.",
        "package_id": "next90-m132-fleet-schedule-deterministic-horizon-slices-only-after-owner-h",
        "milestone_id": 132,
        "work_task_id": "132.6",
        "frontier_id": 8249224665,
        "status": "not_started",
        "wave": "W20",
        "repo": "fleet",
        "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
        "owned_surfaces": ["schedule_deterministic_horizon_slices_only:fleet"],
    }


def _next90_guide() -> str:
    return """# Next 90 day product advance guide

## Wave 20 - implement rules, source, and deterministic horizon tranche

### 132. Deterministic horizon implementation tranche: NEXUS-PAN, ALICE, KARMA FORGE, Knowledge Fabric, and Local Co-Processor

Exit: deterministic horizons move from public storytelling to bounded implementation only through owner handoff gates and executable proof, without assistant-side rules invention.
"""


def _horizon_registry(*, complete_handoff: bool) -> str:
    payload = {
        "product": "chummer",
        "version": 2,
        "rules": [
            "A horizon listed here is a future-capability lane, not a shipment promise.",
            "A horizon must define an eventual build path before it is treated as more than public storytelling.",
            "A horizon does not count as flagship or near-term release scope until its build path advances beyond `horizon`, its owner handoff gate is materially satisfied, and owning repos can cite executable proof instead of public-guide ambition.",
            "Open flagship blockers and lived-system release blockers outrank horizon storytelling; horizons must not dilute or outrun current release truth.",
        ],
        "horizons": [
            {
                "id": "alice",
                "title": "ALICE",
                "owning_repos": ["chummer6-core", "fleet"],
                "owner_handoff_gate": "Core receipts and explicit apply flow required.",
            }
        ],
    }
    if complete_handoff:
        payload["horizons"][0]["allowed_surfaces"] = ["build", "proof"]
        payload["horizons"][0]["proof_gate"] = "proof_contract_required"
        payload["horizons"][0]["public_claim_posture"] = "research_only_until_owner_proof"
        payload["horizons"][0]["stop_condition"] = "do_not_stage_when_owner_proof_is_missing"
    return yaml.safe_dump(payload, sort_keys=False)


def _fixture_tree(tmp_path: Path, *, deterministic_gate_status: str, complete_handoff: bool) -> dict[str, Path]:
    registry_path = tmp_path / "registry.yaml"
    queue_path = tmp_path / "queue.yaml"
    design_queue_path = tmp_path / "design_queue.yaml"
    horizon_registry_path = tmp_path / "HORIZON_REGISTRY.yaml"
    next90_guide_path = tmp_path / "NEXT90_GUIDE.md"

    _write_yaml(registry_path, _registry(deterministic_gate_status=deterministic_gate_status))
    _write_yaml(queue_path, {"items": [_queue_item()]})
    _write_yaml(design_queue_path, {"items": [_queue_item()]})
    _write_text(horizon_registry_path, _horizon_registry(complete_handoff=complete_handoff))
    _write_text(next90_guide_path, _next90_guide())
    return {
        "registry": registry_path,
        "queue": queue_path,
        "design_queue": design_queue_path,
        "horizon_registry": horizon_registry_path,
        "next90_guide": next90_guide_path,
    }


class MaterializeNext90M132FleetDeterministicHorizonQueueTest(unittest.TestCase):
    def _run_materializer(self, fixture: dict[str, Path], artifact_path: Path) -> dict:
        markdown_path = artifact_path.with_suffix(".md")
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--output",
                str(artifact_path),
                "--markdown-output",
                str(markdown_path),
                "--successor-registry",
                str(fixture["registry"]),
                "--queue-staging",
                str(fixture["queue"]),
                "--design-queue-staging",
                str(fixture["design_queue"]),
                "--horizon-registry",
                str(fixture["horizon_registry"]),
                "--next90-guide",
                str(fixture["next90_guide"]),
            ],
            check=True,
        )
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def test_deterministic_queue_rows_stay_blocked_until_design_gate_is_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, deterministic_gate_status="not_started", complete_handoff=True)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json")

        self.assertEqual(payload["status"], "pass")
        monitor = payload["queue_gate_monitor"]
        self.assertFalse(monitor["deterministic_design_gate_task_done"])
        self.assertEqual(monitor["blocked_deterministic_queue_item_count"], 1)
        self.assertEqual(monitor["ready_deterministic_queue_item_count"], 0)

    def test_deterministic_queue_rows_open_when_design_gate_and_handoff_truth_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, deterministic_gate_status="complete", complete_handoff=True)
            payload = self._run_materializer(fixture, tmp_path / "artifact.json")

        self.assertEqual(payload["status"], "pass")
        monitor = payload["queue_gate_monitor"]
        self.assertTrue(monitor["deterministic_design_gate_task_done"])
        self.assertEqual(monitor["blocked_deterministic_queue_item_count"], 0)
        self.assertEqual(monitor["ready_deterministic_queue_item_count"], 1)


if __name__ == "__main__":
    unittest.main()
