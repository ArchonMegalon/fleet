from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_materialize_next90_m144_fleet_desktop_proof_integrity_closeout_gates import _fixture_tree


MATERIALIZE = Path("/docker/fleet/scripts/materialize_next90_m144_fleet_desktop_proof_integrity_closeout_gates.py")
VERIFY = Path("/docker/fleet/scripts/verify_next90_m144_fleet_desktop_proof_integrity_closeout_gates.py")


class VerifyNext90M144FleetDesktopProofIntegrityCloseoutGatesTest(unittest.TestCase):
    def test_verifier_accepts_freshly_materialized_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=False)
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
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
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
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            assert payload["status"] == "pass"

    def test_verifier_rejects_stale_artifact_after_fail_closed_logic_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(tmp_path, stale_versions=True, startup_smoke_digest_matches_release=False)
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
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["status"] = "pass"
            artifact.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY),
                    "--artifact", str(artifact),
                    "--successor-registry", str(fixture["registry"]),
                    "--fleet-queue-staging", str(fixture["fleet_queue"]),
                    "--design-queue-staging", str(fixture["design_queue"]),
                    "--next90-guide", str(fixture["guide"]),
                    "--flagship-readiness", str(fixture["flagship"]),
                    "--ui-windows-exit-gate", str(fixture["windows_gate"]),
                    "--desktop-executable-exit-gate", str(fixture["executable_gate"]),
                    "--release-channel", str(fixture["release_channel"]),
                    "--startup-smoke-receipt", str(fixture["startup_smoke"]),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            verify_payload = json.loads(result.stdout)
            assert result.returncode == 1
            assert verify_payload["status"] == "fail"
            assert "closeout-gate status drifted from recomputed M144 truth" in verify_payload["issues"]


if __name__ == "__main__":
    unittest.main()
