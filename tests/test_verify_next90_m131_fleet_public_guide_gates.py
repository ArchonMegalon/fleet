from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m131_fleet_public_guide_gates import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m131_fleet_public_guide_gates.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m131_fleet_public_guide_gates.py")


class VerifyNext90M131FleetPublicGuideGatesTest(unittest.TestCase):
    def _common_args(self, fixture: dict[str, Path], artifact: Path) -> list[str]:
        return [
            "--artifact",
            str(artifact),
            "--successor-registry",
            str(fixture["registry"]),
            "--queue-staging",
            str(fixture["queue"]),
            "--design-queue-staging",
            str(fixture["design_queue"]),
            "--next90-guide",
            str(fixture["next90_guide"]),
            "--growth-stack",
            str(fixture["growth_stack"]),
            "--guide-export-manifest",
            str(fixture["export_manifest"]),
            "--guide-policy",
            str(fixture["guide_policy"]),
            "--visibility-policy",
            str(fixture["visibility_policy"]),
            "--signal-pipeline",
            str(fixture["signal_pipeline"]),
            "--katteb-lane",
            str(fixture["katteb_lane"]),
            "--guide-verify-script",
            str(fixture["guide_verify_script"]),
            "--flagship-queue-script",
            str(fixture["flagship_queue_script"]),
            "--guide-repo-root",
            str(fixture["guide_repo_root"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                guide_verify_success=True,
                flagship_status="pass",
                flagship_findings=[],
                burn_allowed=True,
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

    def test_verifier_rejects_monitor_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                guide_verify_success=True,
                flagship_status="pass",
                flagship_findings=[],
                burn_allowed=True,
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
            payload["monitor_summary"]["flagship_queue_status"] = "fail"
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
