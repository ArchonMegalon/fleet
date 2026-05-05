from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m143_fleet_route_local_output_closeout_gates import _fixture_tree


MATERIALIZE = Path("/docker/fleet/scripts/materialize_next90_m143_fleet_route_local_output_closeout_gates.py")
VERIFY = Path("/docker/fleet/scripts/verify_next90_m143_fleet_route_local_output_closeout_gates.py")


class VerifyNext90M143FleetRouteLocalOutputCloseoutGatesTest(unittest.TestCase):
    def test_verifier_accepts_freshly_materialized_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, direct=True)
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
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
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
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
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
