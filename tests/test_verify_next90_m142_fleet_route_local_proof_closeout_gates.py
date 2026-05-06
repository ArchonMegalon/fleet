from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_materialize_next90_m142_fleet_route_local_proof_closeout_gates import _fixture_tree


MATERIALIZE = Path("/docker/fleet/scripts/materialize_next90_m142_fleet_route_local_proof_closeout_gates.py")
VERIFY = Path("/docker/fleet/scripts/verify_next90_m142_fleet_route_local_proof_closeout_gates.py")


class VerifyNext90M142FleetRouteLocalProofCloseoutGatesTest(unittest.TestCase):
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
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--desktop-workflow-execution-gate", str(fixture["workflow_gate"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--classic-dense-workbench-gate", str(fixture["dense_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-flagship-release-gate", str(fixture["ui_release"]),
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
                    "--ui-kit-local-release-proof", str(fixture["ui_kit_local_release"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--gm-runboard-route", str(fixture["gm_runboard"]),
                    "--core-dense-receipts-doc", str(fixture["core_doc"]),
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
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--desktop-workflow-execution-gate", str(fixture["workflow_gate"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--classic-dense-workbench-gate", str(fixture["dense_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-flagship-release-gate", str(fixture["ui_release"]),
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
                    "--ui-kit-local-release-proof", str(fixture["ui_kit_local_release"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--gm-runboard-route", str(fixture["gm_runboard"]),
                    "--core-dense-receipts-doc", str(fixture["core_doc"]),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            assert payload["status"] == "pass"

    def test_verifier_ignores_file_mtime_only_drift_on_mirrored_source_inputs(self) -> None:
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
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--desktop-workflow-execution-gate", str(fixture["workflow_gate"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--classic-dense-workbench-gate", str(fixture["dense_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-flagship-release-gate", str(fixture["ui_release"]),
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
                    "--ui-kit-local-release-proof", str(fixture["ui_kit_local_release"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--gm-runboard-route", str(fixture["gm_runboard"]),
                    "--core-dense-receipts-doc", str(fixture["core_doc"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            later = 1_746_450_000
            for key in ("registry", "fleet_queue", "design_queue"):
                os.utime(fixture[key], (later, later))

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
                    "--desktop-visual-familiarity-gate", str(fixture["visual_gate"]),
                    "--desktop-workflow-execution-gate", str(fixture["workflow_gate"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--classic-dense-workbench-gate", str(fixture["dense_gate"]),
                    "--veteran-task-time-gate", str(fixture["veteran_gate"]),
                    "--ui-flagship-release-gate", str(fixture["ui_release"]),
                    "--ui-local-release-proof", str(fixture["ui_local_release"]),
                    "--ui-kit-local-release-proof", str(fixture["ui_kit_local_release"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--gm-runboard-route", str(fixture["gm_runboard"]),
                    "--core-dense-receipts-doc", str(fixture["core_doc"]),
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
