from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m111_fleet_install_aware_followthrough.py")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _fixture_tree(tmp_path: Path) -> dict[str, Path]:
    support = tmp_path / "published" / "SUPPORT_CASE_PACKETS.generated.json"
    governor = tmp_path / "published" / "WEEKLY_GOVERNOR_PACKET.generated.json"
    pulse = tmp_path / "product" / "WEEKLY_PRODUCT_PULSE.generated.json"
    progress = tmp_path / "product" / "PROGRESS_REPORT.generated.json"
    queue = tmp_path / "published" / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    registry = tmp_path / "product" / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
    out = tmp_path / "published" / "NEXT90_M111_FLEET_INSTALL_AWARE_FOLLOWTHROUGH.generated.json"

    _write_json(
        support,
        {
            "generated_at": "2026-04-23T18:00:00Z",
            "summary": {
                "reporter_followthrough_blocked_missing_install_receipts_count": 0,
                "reporter_followthrough_blocked_receipt_mismatch_count": 0,
                "closure_waiting_on_release_truth": 0,
            },
            "followthrough_receipt_gates": {
                "generated_at": "2026-04-23T18:00:00Z",
                "blocked_missing_install_receipts_count": 0,
                "blocked_receipt_mismatch_count": 0,
                "ready_count": 2,
            },
            "successor_package_verification": {
                "status": "pass",
            },
        },
    )
    _write_json(
        governor,
        {
            "generated_at": "2026-04-23T18:05:00Z",
            "as_of": "2026-04-23",
            "decision_alignment": {
                "actual_action": "launch_expand",
                "expected_action": "launch_expand",
                "status": "pass",
            },
            "decision_board": {
                "freeze_launch": {"state": "available"},
                "launch_expand": {"state": "allowed"},
                "rollback": {"state": "armed"},
            },
            "public_status_copy": {
                "state": "launch_expand_allowed",
                "headline": "Measured launch expansion is allowed.",
                "body": "Readiness, parity, support, canary, dependency, and release-proof gates are green for this weekly packet.",
            },
        },
    )
    _write_json(
        pulse,
        {
            "generated_at": "2026-04-23T18:10:00Z",
            "as_of": "2026-04-23",
            "governor_decisions": [
                {
                    "action": "launch_expand",
                    "reason": "Launch expansion is approved for the next bounded window while canaries and support closure remain clear.",
                }
            ],
        },
    )
    _write_json(
        progress,
        {
            "generated_at": "2026-04-23T18:12:00Z",
            "as_of": "2026-04-23",
            "contract_name": "fleet.public_progress_report",
        },
    )
    _write_yaml(
        queue,
        {
            "items": [
                {
                    "title": "Gate followthrough mail and public proof promotion against install-aware receipts",
                    "task": "Promote release and support concierge artifacts only when install-aware recovery receipts and publication refs agree.",
                    "package_id": "next90-m111-fleet-install-aware-followthrough",
                    "milestone_id": 111,
                    "wave": "W9",
                    "repo": "fleet",
                    "status": "complete",
                    "completion_action": "verify_closed_package_only",
                    "do_not_reopen_reason": (
                        "M111 Fleet install-aware followthrough is complete; future shards must verify the "
                        "install-aware gate receipt, standalone verifier, registry row, queue row, and design queue row "
                        "instead of reopening the followthrough-mail and public-proof promotion package."
                    ),
                    "allowed_paths": ["scripts", "tests", ".codex-studio", "feedback"],
                    "owned_surfaces": ["install_aware_followthrough", "product_governor:artifact_promotion"],
                }
            ]
        },
    )
    _write_yaml(
        registry,
        {
            "milestones": [
                {
                    "id": 111,
                    "title": "Install-aware release, support, and public concierge",
                    "status": "in_progress",
                    "dependencies": [101, 102, 106, 107],
                    "exit_criteria": [
                        "Mail, in-product notices, public trust surfaces, and the public proof shelf all cite the same install-aware release and recovery receipts."
                    ],
                    "work_tasks": [
                        {
                            "id": "111.4",
                            "owner": "fleet",
                            "title": "Gate followthrough mail, public proof promotion, and public concierge rollout against the same install-aware receipts and kill-switch posture.",
                            "status": "complete",
                            "completion_action": "verify_closed_package_only",
                            "do_not_reopen_reason": (
                                "M111 Fleet install-aware followthrough is complete; future shards must verify the "
                                "install-aware gate receipt, standalone verifier, registry row, queue row, and design queue row "
                                "instead of reopening the followthrough-mail and public-proof promotion package."
                            ),
                        }
                    ],
                }
            ]
        },
    )

    return {
        "support": support,
        "governor": governor,
        "pulse": pulse,
        "progress": progress,
        "queue": queue,
        "registry": registry,
        "out": out,
    }


class MaterializeNext90M111InstallAwareFollowthroughTests(unittest.TestCase):
    def test_materialize_next90_m111_install_aware_followthrough_gate(self) -> None:
        tmp_path = Path(self.id().replace(".", "_"))
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            paths = _fixture_tree(tmp_path)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--support-packets",
                    str(paths["support"]),
                    "--weekly-governor-packet",
                    str(paths["governor"]),
                    "--weekly-product-pulse",
                    str(paths["pulse"]),
                    "--progress-report",
                    str(paths["progress"]),
                    "--successor-registry",
                    str(paths["registry"]),
                    "--queue-staging",
                    str(paths["queue"]),
                    "--output",
                    str(paths["out"]),
                ],
                cwd="/docker/fleet",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(paths["out"].read_text(encoding="utf-8"))
            self.assertEqual(payload["contract_name"], "fleet.install_aware_followthrough_gate")
            self.assertEqual(payload["gates"]["followthrough_mail"]["state"], "pass")
            self.assertEqual(payload["gates"]["public_proof_promotion"]["state"], "pass")
            self.assertEqual(payload["queue_status"], "complete")
            self.assertEqual(payload["registry_work_task_status"], "complete")
            self.assertTrue(payload["agreement"]["publication_refs_present"])
            self.assertTrue(payload["agreement"]["publication_ref_as_of_aligned"])
            self.assertTrue(payload["agreement"]["queue_closure_matches_package"])
            self.assertTrue(payload["agreement"]["registry_closure_matches_package"])
            self.assertEqual(payload["launch_truth"]["public_status_state"], "launch_expand_allowed")
            self.assertEqual(
                [row["name"] for row in payload["publication_refs"]],
                [
                    "support_packets",
                    "weekly_governor_packet",
                    "weekly_product_pulse",
                    "progress_report",
                ],
            )
        finally:
            if tmp_path.exists():
                import shutil

                shutil.rmtree(tmp_path)
