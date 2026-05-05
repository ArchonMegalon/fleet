from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m139_fleet_release_health_public_trust_projections import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m139_fleet_release_health_public_trust_projections.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m139_fleet_release_health_public_trust_projections.py")


class VerifyNext90M139FleetReleaseHealthPublicTrustProjectionsTest(unittest.TestCase):
    def _common_args(self, fixture: dict[str, Path], artifact: Path) -> list[str]:
        return [
            "--artifact", str(artifact),
            "--successor-registry", str(fixture["registry"]),
            "--fleet-queue-staging", str(fixture["fleet_queue"]),
            "--design-queue-staging", str(fixture["design_queue"]),
            "--next90-guide", str(fixture["guide"]),
            "--prep-packet-factory", str(fixture["prep"]),
            "--opposition-packet-registry", str(fixture["opposition"]),
            "--world-broadcast-cadence", str(fixture["broadcast"]),
            "--world-broadcast-recipe-registry", str(fixture["broadcast_registry"]),
            "--community-safety-doc", str(fixture["safety_doc"]),
            "--community-safety-states", str(fixture["safety_states"]),
            "--creator-analytics-doc", str(fixture["creator_doc"]),
            "--creator-analytics-schema", str(fixture["creator_schema"]),
            "--creator-trust-policy", str(fixture["creator_policy"]),
            "--product-analytics-model", str(fixture["product_analytics"]),
            "--accessibility-release-bar", str(fixture["accessibility_doc"]),
            "--accessibility-gates", str(fixture["accessibility_gates"]),
            "--public-faq-registry", str(fixture["faq_registry"]),
            "--public-feature-registry", str(fixture["feature_registry"]),
            "--public-landing-manifest", str(fixture["landing"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run([sys.executable, str(MATERIALIZER), "--output", str(artifact), "--markdown-output", str(markdown), *self._common_args(fixture, artifact)[2:]], check=True)
            completed = subprocess.run([sys.executable, str(VERIFIER), *self._common_args(fixture, artifact), "--json"], check=True, capture_output=True, text=True)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "pass")

    def test_verifier_rejects_projection_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run([sys.executable, str(MATERIALIZER), "--output", str(artifact), "--markdown-output", str(markdown), *self._common_args(fixture, artifact)[2:]], check=True)
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["projections"]["world_broadcast_cadence"]["projection_kind"] = "broken"
            artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            completed = subprocess.run([sys.executable, str(VERIFIER), *self._common_args(fixture, artifact), "--json"], check=False, capture_output=True, text=True)
        result = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("projections drifted" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
