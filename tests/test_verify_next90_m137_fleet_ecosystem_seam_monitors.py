from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tests.test_materialize_next90_m137_fleet_ecosystem_seam_monitors import _fixture_tree
except ModuleNotFoundError:
    from test_materialize_next90_m137_fleet_ecosystem_seam_monitors import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m137_fleet_ecosystem_seam_monitors.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m137_fleet_ecosystem_seam_monitors.py")


class VerifyNext90M137FleetEcosystemSeamMonitorsTest(unittest.TestCase):
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
            str(fixture["next90_guide"]),
            "--roadmap",
            str(fixture["roadmap"]),
            "--horizon-registry",
            str(fixture["horizon_registry"]),
            "--ltd-integration-guide",
            str(fixture["ltd_guide"]),
            "--external-tools-plane",
            str(fixture["external_tools"]),
            "--open-runs-community-hub",
            str(fixture["open_runs"]),
            "--open-runs-honors",
            str(fixture["open_runs_honors"]),
            "--community-safety-states",
            str(fixture["community_safety"]),
            "--creator-publication-policy",
            str(fixture["creator_policy"]),
            "--public-concierge-workflows",
            str(fixture["concierge"]),
            "--public-feature-registry",
            str(fixture["feature_registry"]),
            "--public-landing-manifest",
            str(fixture["landing_manifest"]),
            "--public-release-experience",
            str(fixture["release_experience"]),
            "--public-guide-root",
            str(fixture["public_guide_root"]),
            "--m133-media-social-monitors",
            str(fixture["m133"]),
            "--m131-public-guide-gates",
            str(fixture["m131"]),
            "--flagship-readiness",
            str(fixture["flagship"]),
            "--journey-gates",
            str(fixture["journeys"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, blocked_runtime=False)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [sys.executable, str(MATERIALIZER), "--output", str(artifact), "--markdown-output", str(markdown), *self._common_args(fixture, artifact)[2:]],
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
            fixture = _fixture_tree(tmp_path, blocked_runtime=False)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [sys.executable, str(MATERIALIZER), "--output", str(artifact), "--markdown-output", str(markdown), *self._common_args(fixture, artifact)[2:]],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["monitor_summary"]["monitored_public_card_count"] = 999
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
