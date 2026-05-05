from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tests.test_materialize_next90_m136_fleet_sr4_sr6_readiness_closeout import _fixture_tree
except ModuleNotFoundError:
    from test_materialize_next90_m136_fleet_sr4_sr6_readiness_closeout import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_sr4_sr6_readiness_closeout.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m136_fleet_sr4_sr6_readiness_closeout.py")


class VerifyNext90M136FleetSr4Sr6ReadinessCloseoutTest(unittest.TestCase):
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
            "--flagship-readiness-planes",
            str(fixture["planes"]),
            "--flagship-product-bar",
            str(fixture["bar"]),
            "--flagship-product-readiness",
            str(fixture["flagship"]),
            "--sr4-workflow-parity",
            str(fixture["sr4"]),
            "--sr6-workflow-parity",
            str(fixture["sr6"]),
            "--sr4-sr6-frontier",
            str(fixture["frontier"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
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
            fixture = _fixture_tree(tmp_path)
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
            payload["monitor_summary"]["sr6_ready"] = False
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
