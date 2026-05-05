from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m127_fleet_release_truth_gates import _fixture_tree


VERIFIER = Path("/docker/fleet/scripts/verify_next90_m127_fleet_release_truth_gates.py")
SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m127_fleet_release_truth_gates.py")


def _materialize(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(paths["artifact"]),
            "--markdown-output",
            str(paths["markdown"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--next90-guide",
            str(paths["guide"]),
            "--acceptance-matrix",
            str(paths["acceptance"]),
            "--public-downloads-policy",
            str(paths["downloads"]),
            "--public-auto-update-policy",
            str(paths["auto_update"]),
            "--repo-hardening-checklist",
            str(paths["hardening"]),
            "--repo-hygiene-policy",
            str(paths["hygiene"]),
            "--external-proof-runbook",
            str(paths["runbook"]),
            "--flagship-product-readiness",
            str(paths["readiness"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _verify(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--artifact",
            str(paths["artifact"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--next90-guide",
            str(paths["guide"]),
            "--acceptance-matrix",
            str(paths["acceptance"]),
            "--public-downloads-policy",
            str(paths["downloads"]),
            "--public-auto-update-policy",
            str(paths["auto_update"]),
            "--repo-hardening-checklist",
            str(paths["hardening"]),
            "--repo-hygiene-policy",
            str(paths["hygiene"]),
            "--external-proof-runbook",
            str(paths["runbook"]),
            "--flagship-product-readiness",
            str(paths["readiness"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class VerifyNext90M127FleetReleaseTruthGatesTests(unittest.TestCase):
    def test_verifier_accepts_regenerated_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m127-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), unresolved_request_count=0, external_status="pass")
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            result = _verify(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("M127 release-truth gates verifier passed", result.stdout)

    def test_verifier_rejects_runtime_monitor_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m127-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), unresolved_request_count=0, external_status="pass")
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["runtime_monitors"]["external_proof_runbook"]["unresolved_request_count"] = 9
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = _verify(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime monitor sections drifted", result.stderr)


if __name__ == "__main__":
    unittest.main()
