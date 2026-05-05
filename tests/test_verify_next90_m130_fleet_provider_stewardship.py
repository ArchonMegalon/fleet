from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m130_fleet_provider_stewardship import _fixture_tree


VERIFIER = Path("/docker/fleet/scripts/verify_next90_m130_fleet_provider_stewardship.py")
SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m130_fleet_provider_stewardship.py")


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
            "--external-tools-plane",
            str(paths["external_tools"]),
            "--ltd-capability-map",
            str(paths["ltd_map"]),
            "--provider-route-stewardship",
            str(paths["stewardship"]),
            "--weekly-governor-packet",
            str(paths["weekly"]),
            "--admin-status",
            str(paths["admin_status"]),
            "--provider-credit",
            str(paths["provider_credit"]),
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
            "--external-tools-plane",
            str(paths["external_tools"]),
            "--ltd-capability-map",
            str(paths["ltd_map"]),
            "--provider-route-stewardship",
            str(paths["stewardship"]),
            "--weekly-governor-packet",
            str(paths["weekly"]),
            "--admin-status",
            str(paths["admin_status"]),
            "--provider-credit",
            str(paths["provider_credit"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class VerifyNext90M130FleetProviderStewardshipTests(unittest.TestCase):
    def test_verifier_accepts_regenerated_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m130-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            result = _verify(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("M130 provider stewardship verifier passed", result.stdout)

    def test_verifier_rejects_runtime_monitor_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m130-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["runtime_monitors"]["provider_routes"]["governed_route_count"] = 99
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = _verify(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime monitor sections drifted", result.stderr)


if __name__ == "__main__":
    unittest.main()
