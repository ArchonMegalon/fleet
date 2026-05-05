from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m133_fleet_media_social_horizon_monitors import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m133_fleet_media_social_horizon_monitors.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m133_fleet_media_social_horizon_monitors.py")


class VerifyNext90M133FleetMediaSocialHorizonMonitorsTest(unittest.TestCase):
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
            "--horizon-registry",
            str(fixture["horizon_registry"]),
            "--media-social-ltd-guide",
            str(fixture["ltd_guide"]),
            "--external-tools-plane",
            str(fixture["external_tools"]),
            "--build-explain-artifact-truth-policy",
            str(fixture["build_explain_policy"]),
            "--community-safety-states",
            str(fixture["community_safety"]),
            "--journey-gates",
            str(fixture["journey_gates"]),
            "--flagship-readiness",
            str(fixture["flagship_readiness"]),
            "--provider-stewardship",
            str(fixture["provider_stewardship"]),
            "--media-local-release-proof",
            str(fixture["media_proof"]),
            "--hub-local-release-proof",
            str(fixture["hub_proof"]),
            "--release-channel",
            str(fixture["release_channel"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, blocked_runtime=False)
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
            fixture = _fixture_tree(tmp_path, blocked_runtime=False)
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
            payload["monitor_summary"]["provider_canary_gate_state"] = "blocked"
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
