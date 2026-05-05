from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_materialize_next90_m120_fleet_launch_pulse import _fixture_tree


VERIFIER = Path("/docker/fleet/scripts/verify_next90_m120_fleet_launch_pulse.py")
SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m120_fleet_launch_pulse.py")


def _materialize(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(paths["artifact"]),
            "--successor-registry",
            str(paths["registry"]),
            "--queue-staging",
            str(paths["queue"]),
            "--design-queue-staging",
            str(paths["design_queue"]),
            "--weekly-governor-packet",
            str(paths["weekly"]),
            "--weekly-product-pulse",
            str(paths["pulse"]),
            "--support-packets",
            str(paths["support"]),
            "--progress-report",
            str(paths["progress"]),
            "--flagship-readiness",
            str(paths["flagship"]),
            "--journey-gates",
            str(paths["journey"]),
            "--proof-orchestration",
            str(paths["proof"]),
            "--status-plane",
            str(paths["status_plane"]),
            "--markdown-output",
            str(paths["markdown"]),
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
            "--weekly-governor-packet",
            str(paths["weekly"]),
            "--weekly-product-pulse",
            str(paths["pulse"]),
            "--support-packets",
            str(paths["support"]),
            "--progress-report",
            str(paths["progress"]),
            "--flagship-readiness",
            str(paths["flagship"]),
            "--journey-gates",
            str(paths["journey"]),
            "--proof-orchestration",
            str(paths["proof"]),
            "--status-plane",
            str(paths["status_plane"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class VerifyNext90M120FleetLaunchPulseTests(unittest.TestCase):
    def test_verifier_accepts_regenerated_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m120-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            result = _verify(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("M120 launch-pulse verifier passed", result.stdout)

    def test_verifier_rejects_source_link_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m120-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["source_packet_links"]["support_case_packets"]["contract_name"] = "fleet.support_case_packets.v2"
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = _verify(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_packet_links::support_case_packets.contract_name drifted", result.stderr)

    def test_verifier_rejects_launch_action_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m120-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["launch_pulse"]["alignment_ok"] = False
            payload["launch_pulse"]["state"] = "watch"
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = _verify(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("launch_pulse state drifted", result.stderr)


if __name__ == "__main__":
    unittest.main()
