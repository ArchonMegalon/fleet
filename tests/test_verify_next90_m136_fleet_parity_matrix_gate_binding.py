from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m136_fleet_parity_matrix_gate_binding import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m136_fleet_parity_matrix_gate_binding.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m136_fleet_parity_matrix_gate_binding.py")


class VerifyNext90M136FleetParityMatrixGateBindingTest(unittest.TestCase):
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
            "--parity-spec",
            str(fixture["parity_spec"]),
            "--parity-matrix",
            str(fixture["parity_matrix"]),
            "--flagship-readiness-planes",
            str(fixture["planes"]),
            "--flagship-product-bar",
            str(fixture["bar"]),
            "--parity-audit",
            str(fixture["parity_audit"]),
            "--m136-aggregate-gate",
            str(fixture["m136_gate"]),
            "--flagship-product-readiness",
            str(fixture["flagship"]),
            "--flagship-readiness-script",
            str(fixture["flagship_script"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                include_matrix_in_planes=True,
                prose_only_family=None,
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

    def test_verifier_rejects_runtime_monitor_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                include_fleet_queue_row=True,
                include_matrix_in_planes=True,
                prose_only_family=None,
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
            payload["monitor_summary"]["release_blocking_family_count"] = 99
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
