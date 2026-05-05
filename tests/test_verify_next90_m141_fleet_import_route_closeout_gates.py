from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tests.test_materialize_next90_m141_fleet_import_route_closeout_gates import _fixture_tree
except ModuleNotFoundError:
    from test_materialize_next90_m141_fleet_import_route_closeout_gates import _fixture_tree


MATERIALIZE = Path("/docker/fleet/scripts/materialize_next90_m141_fleet_import_route_closeout_gates.py")
VERIFY = Path("/docker/fleet/scripts/verify_next90_m141_fleet_import_route_closeout_gates.py")


class VerifyNext90M141FleetImportRouteCloseoutGatesTest(unittest.TestCase):
    def test_verifier_accepts_freshly_materialized_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, use_old_shape=False)
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZE),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--parity-acceptance-matrix", str(fixture["matrix"]),
                    "--legacy-chrome-policy", str(fixture["policy"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-release-gate", str(fixture["ui_release"]),
                    "--import-receipts-doc", str(fixture["receipts_doc"]),
                    "--import-parity-certification", str(fixture["import_cert"]),
                    "--engine-proof-pack", str(fixture["engine_pack"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY),
                    "--artifact", str(artifact),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--parity-acceptance-matrix", str(fixture["matrix"]),
                    "--legacy-chrome-policy", str(fixture["policy"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-release-gate", str(fixture["ui_release"]),
                    "--import-receipts-doc", str(fixture["receipts_doc"]),
                    "--import-parity-certification", str(fixture["import_cert"]),
                    "--engine-proof-pack", str(fixture["engine_pack"]),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            assert payload["status"] == "pass"


if __name__ == "__main__":
    unittest.main()
