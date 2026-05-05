from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m140_fleet_portability_and_cadence_closeout_gates import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m140_fleet_portability_and_cadence_closeout_gates.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m140_fleet_portability_and_cadence_closeout_gates.py")


class VerifyNext90M140FleetPortabilityAndCadenceCloseoutGatesTest(unittest.TestCase):
    def _common_args(self, fixture: dict[str, Path], artifact: Path) -> list[str]:
        return [
            "--artifact", str(artifact),
            "--published-root", str(fixture["published"]),
            "--successor-registry", str(fixture["registry"]),
            "--fleet-queue-staging", str(fixture["fleet_queue"]),
            "--design-queue-staging", str(fixture["design_queue"]),
            "--next90-guide", str(fixture["guide"]),
            "--roadmap", str(fixture["roadmap"]),
            "--runner-passport-doc", str(fixture["passport_doc"]),
            "--runner-passport-acceptance", str(fixture["passport_acceptance"]),
            "--world-dispatch-doc", str(fixture["dispatch_doc"]),
            "--world-dispatch-gates", str(fixture["dispatch_gates"]),
            "--creator-operating-system", str(fixture["creator_doc"]),
            "--ltd-cadence-system", str(fixture["ltd_system"]),
            "--ltd-cadence-registry", str(fixture["ltd_registry"]),
            "--ltd-runtime-registry", str(fixture["ltd_runtime"]),
            "--public-faq", str(fixture["faq_md"]),
            "--public-faq-registry", str(fixture["faq_registry"]),
            "--public-feature-registry", str(fixture["feature_registry"]),
            "--public-landing-manifest", str(fixture["landing"]),
            "--flagship-readiness", str(fixture["flagship"]),
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

    def test_verifier_rejects_runtime_summary_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run([sys.executable, str(MATERIALIZER), "--output", str(artifact), "--markdown-output", str(markdown), *self._common_args(fixture, artifact)[2:]], check=True)
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["monitor_summary"]["warning_count"] = 999
            artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            completed = subprocess.run([sys.executable, str(VERIFIER), *self._common_args(fixture, artifact), "--json"], check=False, capture_output=True, text=True)
        result = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("monitor summary drifted" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
