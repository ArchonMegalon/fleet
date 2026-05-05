from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m136_fleet_aggregate_readiness_parity_gates import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_aggregate_readiness_parity_gates.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m136_fleet_aggregate_readiness_parity_gates.py")


class VerifyNext90M136FleetAggregateReadinessParityGatesTest(unittest.TestCase):
    def _common_args(self, fixture: dict[str, Path], artifact: Path) -> list[str]:
        return [
            "--artifact",
            str(artifact),
            "--successor-registry",
            str(fixture["registry"]),
            "--fleet-queue-staging",
            str(fixture["fleet_queue"]),
            "--design-queue-staging",
            str(fixture["design_queue"]),
            "--next90-guide",
            str(fixture["guide"]),
            "--parity-matrix",
            str(fixture["parity_matrix"]),
            "--flagship-product-readiness",
            str(fixture["flagship"]),
            "--campaign-continuity-liveness",
            str(fixture["continuity"]),
            "--journey-gates",
            str(fixture["journey"]),
            "--parity-audit",
            str(fixture["parity_audit"]),
            "--screenshot-review-gate",
            str(fixture["screenshot"]),
            "--visual-familiarity-gate",
            str(fixture["visual"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                parity_audit_generated_at="2026-05-05T12:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="pass",
                continuity_status="pass",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="fail",
            )
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZER),
                    "--output",
                    str(artifact),
                    "--markdown-output",
                    str(markdown),
                    *self._common_args(fixture, artifact)[2:],
                ],
                check=True,
            )
            completed = subprocess.run(
                [sys.executable, str(VERIFIER), *self._common_args(fixture, artifact), "--json"],
                check=True,
                capture_output=True,
                text=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "pass")

    def test_verifier_rejects_monitor_summary_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                parity_audit_generated_at="2026-05-05T12:00:00Z",
                screenshot_review_generated_at="2026-05-05T12:00:00Z",
                visual_gate_generated_at="2026-05-05T12:00:00Z",
                visual_gate_status="pass",
                continuity_status="pass",
                continuity_generated_at="2026-05-05T12:00:00Z",
                journey_generated_at="2026-05-05T12:00:00Z",
                flagship_status="fail",
            )
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZER),
                    "--output",
                    str(artifact),
                    "--markdown-output",
                    str(markdown),
                    *self._common_args(fixture, artifact)[2:],
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["monitor_summary"]["receipt_runtime_blocker_count"] = 5
            artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(VERIFIER), *self._common_args(fixture, artifact), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("monitor summary drifted" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
