from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m120_fleet_launch_pulse.py")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _base_registry() -> dict:
    return {
        "milestones": [
            {
                "id": 120,
                "title": "Public launch posture, publication readiness, and governor alignment",
                "dependencies": [101, 106, 111, 116, 117, 119],
                "work_tasks": [
                    {
                        "id": "120.3",
                        "owner": "fleet",
                        "title": "Compile launch pulse, adoption health, support risk, and proof freshness into governor-ready public status packets.",
                    }
                ],
            }
        ]
    }


def _queue_item() -> dict:
    return {
        "items": [
            {
                "title": "Compile launch pulse and adoption health into governor packets",
                "task": "Produce launch pulse, adoption health, support risk, proof freshness, and public followthrough packets from governed release truth.",
                "package_id": "next90-m120-fleet-launch-pulse",
                "milestone_id": 120,
                "work_task_id": 120.3,
                "status": "in_progress",
                "wave": "W14",
                "repo": "fleet",
                "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
                "owned_surfaces": ["launch_pulse", "adoption_health:governor"],
            }
        ]
    }


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    now = dt.datetime.now(dt.timezone.utc)
    generated = (now - dt.timedelta(hours=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    registry = tmp_path / "registry.yaml"
    queue = tmp_path / "queue.yaml"
    design_queue = tmp_path / "design_queue.yaml"
    weekly = tmp_path / "WEEKLY_GOVERNOR_PACKET.generated.json"
    pulse = tmp_path / "WEEKLY_PRODUCT_PULSE.generated.json"
    support = tmp_path / "SUPPORT_CASE_PACKETS.generated.json"
    progress = tmp_path / "PROGRESS_REPORT.generated.json"
    flagship = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    journey = tmp_path / "JOURNEY_GATES.generated.json"
    proof = tmp_path / "PROOF_ORCHESTRATION.generated.json"
    status_plane = tmp_path / "STATUS_PLANE.generated.yaml"
    artifact = tmp_path / "NEXT90_M120_FLEET_LAUNCH_PULSE.generated.json"
    markdown = tmp_path / "NEXT90_M120_FLEET_LAUNCH_PULSE.generated.md"

    _write_yaml(registry, _base_registry())
    _write_yaml(queue, _queue_item())
    _write_yaml(design_queue, _queue_item())
    _write_json(
        weekly,
        {
            "generated_at": generated,
            "as_of": "2026-05-04",
            "contract_name": "chummer.weekly_gov",
            "decision_alignment": {
                "actual_action": "launch_expand",
                "expected_action": "launch_expand",
                "status": "pass",
            },
            "decision_board": {
                "current_launch_action": "launch_expand",
            },
            "decision_gate_ledger": {
                "freeze_launch": [{"state": "blocked"}],
                "launch_expand": [{"state": "allowed"}],
            },
            "governor_decisions": [
                {
                    "action": "launch_expand",
                    "reason": "Adoption and support risk are stable under current proof truth.",
                }
            ],
            "public_status_copy": {
                "state": "launch_expand",
                "headline": "Launch expansion is governed.",
                "body": "All launch proofs are currently aligned.",
            },
        },
    )
    _write_json(
        pulse,
        {
            "generated_at": generated,
            "as_of": "2026-05-04",
            "contract_name": "chummer.weekly_product_pulse",
            "governor_decisions": [
                {
                    "action": "launch_expand",
                    "reason": "Measured adoption and support posture is stable enough for expansion.",
                }
            ],
            "supporting_signals": {
                "adoption_health": {
                    "state": "clear",
                    "local_release_proof_status": "passed",
                    "proven_journey_count": 5,
                    "proven_route_count": 10,
                    "history_snapshot_count": 20,
                    "summary": "Current signals pass for launch expansion.",
                },
                "successor_dependency_posture": {"state": "ready"},
            },
        },
    )
    _write_json(
        support,
        {
            "generated_at": generated,
            "contract_name": "fleet.support_case_packets",
            "summary": {
                "open_packet_count": 0,
                "needs_human_response": 0,
                "update_required_case_count": 0,
                "closure_waiting_on_release_truth": 0,
            },
            "packets": [],
            "successor_package_verification": {"status": "pass"},
        },
    )
    _write_json(
        progress,
        {
            "generated_at": generated,
            "as_of": "2026-05-04",
            "overall_status": "complete",
            "percent_complete": 99,
            "contract_name": "fleet.public_progress_report",
        },
    )
    _write_json(
        flagship,
        {
            "generated_at": generated,
            "status": "pass",
            "scoped_status": "pass",
        },
    )
    _write_json(
        journey,
        {
            "generated_at": generated,
            "summary": {"overall_state": "ready"},
        },
    )
    _write_json(
        proof,
        {
            "generated_at": generated,
            "jobs": [
                {"id": "proof_orchestration", "state": "ready"},
            ],
        },
    )
    _write_yaml(
        status_plane,
        {
            "generated_at": generated,
            "whole_product_final_claim_status": "pass",
        },
    )

    return {
        "registry": registry,
        "queue": queue,
        "design_queue": design_queue,
        "weekly": weekly,
        "pulse": pulse,
        "support": support,
        "progress": progress,
        "flagship": flagship,
        "journey": journey,
        "proof": proof,
        "status_plane": status_plane,
        "artifact": artifact,
        "markdown": markdown,
    }


def _materialize(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    _write_yaml(paths["queue"], _queue_item())
    _write_yaml(paths["design_queue"], _queue_item())

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
            "--weekly-governor-packet",
            str(paths["weekly"]),
            "--weekly-product-pulse",
            str(paths["pulse"]),
            "--support-packets",
            str(paths["support"]),
            "--progress-report",
            str(paths["progress"]),
            "--flagship-readiness",
            str(paths["flagship"]),
            "--journey-gates",
            str(paths["journey"]),
            "--proof-orchestration",
            str(paths["proof"]),
            "--status-plane",
            str(paths["status_plane"]),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class MaterializeNext90M120FleetLaunchPulseTests(unittest.TestCase):
    def test_materialize_next90_m120_fleet_launch_pulse_passes_with_stable_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m120-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))

            self.assertEqual(payload["status"], "pass")
            self.assertEqual(payload["agreement"]["queue_scope_matches_package"], True)
            self.assertEqual(payload["launch_pulse"]["state"], "pass")
            self.assertEqual(payload["launch_pulse"]["alignment_ok"], True)
            self.assertEqual(payload["adoption_health"]["state"], "pass")
            self.assertEqual(payload["support_risk"]["state"], "low")
            self.assertEqual(payload["proof_freshness"]["state"], "pass")
            self.assertEqual(payload["public_followthrough"]["state"], "pass")
            self.assertTrue(paths["markdown"].is_file())

    def test_materialize_blocks_on_launch_action_misalignment(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m120-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            pulse = json.loads(paths["pulse"].read_text(encoding="utf-8"))
            pulse["governor_decisions"][0]["action"] = "freeze_launch"
            _write_json(paths["pulse"], pulse)
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))

            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["launch_pulse"]["state"], "watch")
            self.assertFalse(payload["launch_pulse"]["alignment_ok"])
            self.assertIn("Align weekly pulse launch action", payload["next_actions"][0])

    def test_materialize_marks_stale_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m120-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            support = json.loads(paths["support"].read_text(encoding="utf-8"))
            old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            support["generated_at"] = old
            _write_json(paths["support"], support)
            result = _materialize(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))

            self.assertEqual(payload["status"], "blocked")
            self.assertEqual(payload["proof_freshness"]["state"], "blocked")
            self.assertEqual(payload["proof_freshness"]["missing_input_count"], 0)
            self.assertEqual(payload["proof_freshness"]["stale_input_count"], 1)
            self.assertEqual(payload["proof_freshness"]["source_rows"]["support_packets"]["status"], "stale")
            self.assertIn("Refresh stale or missing source proofs", payload["next_actions"][0])


if __name__ == "__main__":
    unittest.main()
