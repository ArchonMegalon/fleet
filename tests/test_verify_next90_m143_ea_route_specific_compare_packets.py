from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tests.test_materialize_next90_m143_ea_route_specific_compare_packets import _fixture_tree
except ModuleNotFoundError:
    from test_materialize_next90_m143_ea_route_specific_compare_packets import _fixture_tree


MATERIALIZE = Path("/docker/fleet/scripts/materialize_next90_m143_ea_route_specific_compare_packets.py")
VERIFY = Path("/docker/fleet/scripts/verify_next90_m143_ea_route_specific_compare_packets.py")


class VerifyNext90M143EaRouteSpecificComparePacketsTest(unittest.TestCase):
    def test_verifier_accepts_freshly_materialized_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.yaml"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZE),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--task-local-telemetry", str(fixture["telemetry"]),
                    "--runtime-handoff", str(fixture["handoff"]),
                    "--readiness", str(fixture["readiness"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                    "--fleet-m143-gate", str(fixture["fleet_gate"]),
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
                    "--markdown-artifact", str(markdown),
                    "--task-local-telemetry", str(fixture["telemetry"]),
                    "--runtime-handoff", str(fixture["handoff"]),
                    "--readiness", str(fixture["readiness"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                    "--fleet-m143-gate", str(fixture["fleet_gate"]),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            assert payload["status"] == "pass"

    def test_verifier_resolves_task_local_telemetry_from_runtime_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path)
            artifact = tmp_path / "artifact.yaml"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZE),
                    "--output", str(artifact),
                    "--markdown-output", str(markdown),
                    "--runtime-handoff", str(fixture["handoff"]),
                    "--readiness", str(fixture["readiness"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                    "--fleet-m143-gate", str(fixture["fleet_gate"]),
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
                    "--markdown-artifact", str(markdown),
                    "--runtime-handoff", str(fixture["handoff"]),
                    "--readiness", str(fixture["readiness"]),
                    "--workflow-pack", str(fixture["workflow_pack"]),
                    "--parity-audit", str(fixture["parity_audit"]),
                    "--screenshot-review-gate", str(fixture["screenshot_gate"]),
                    "--section-host-ruleset-parity", str(fixture["section_host"]),
                    "--generated-dialog-parity", str(fixture["dialog_parity"]),
                    "--m114-rule-studio", str(fixture["rule_studio"]),
                    "--core-m143-receipts-doc", str(fixture["core_doc"]),
                    "--fleet-m143-gate", str(fixture["fleet_gate"]),
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
