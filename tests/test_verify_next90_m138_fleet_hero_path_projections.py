from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tests.test_materialize_next90_m138_fleet_hero_path_projections import _fixture_tree
except ModuleNotFoundError:
    from test_materialize_next90_m138_fleet_hero_path_projections import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m138_fleet_hero_path_projections.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m138_fleet_hero_path_projections.py")


class VerifyNext90M138FleetHeroPathProjectionsTest(unittest.TestCase):
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
            "--ready-for-tonight-gates",
            str(fixture["ready_for_tonight_gates"]),
            "--public-onboarding-paths",
            str(fixture["public_onboarding"]),
            "--role-kit-registry",
            str(fixture["role_kit_registry"]),
            "--source-aware-explain",
            str(fixture["source_aware_explain"]),
            "--campaign-adoption-flow",
            str(fixture["campaign_adoption"]),
            "--foundry-first-handoff",
            str(fixture["foundry"]),
            "--vtt-export-target-acceptance",
            str(fixture["vtt_acceptance"]),
            "--public-faq-registry",
            str(fixture["public_faq_registry"]),
            "--public-guide-community-hub",
            str(fixture["community_hub"]),
            "--open-run-journey",
            str(fixture["open_run_journey"]),
            "--public-feature-registry",
            str(fixture["public_feature_registry"]),
            "--public-landing-manifest",
            str(fixture["public_landing_manifest"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
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

    def test_verifier_rejects_projection_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [sys.executable, str(MATERIALIZER), "--output", str(artifact), "--markdown-output", str(markdown), *self._common_args(fixture, artifact)[2:]],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["projections"]["newcomer_path"]["public_claim_posture"] = "broken"
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
        self.assertTrue(any("projection bodies drifted" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
