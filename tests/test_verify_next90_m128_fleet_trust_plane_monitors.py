from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from tests.test_materialize_next90_m128_fleet_trust_plane_monitors import _fixture_tree
except ModuleNotFoundError:
    from test_materialize_next90_m128_fleet_trust_plane_monitors import _fixture_tree


VERIFIER = Path("/docker/fleet/scripts/verify_next90_m128_fleet_trust_plane_monitors.py")
SCRIPT = Path("/docker/fleet/scripts/materialize_next90_m128_fleet_trust_plane_monitors.py")


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
            "--localization-system",
            str(paths["localization"]),
            "--telemetry-model",
            str(paths["telemetry_model"]),
            "--telemetry-schema",
            str(paths["telemetry_schema"]),
            "--privacy-boundaries",
            str(paths["privacy"]),
            "--crash-reporting",
            str(paths["crash_reporting"]),
            "--support-status",
            str(paths["support_status"]),
            "--flagship-readiness",
            str(paths["flagship"]),
            "--support-packets",
            str(paths["support_packets"]),
            "--weekly-product-pulse",
            str(paths["weekly_pulse"]),
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
            "--localization-system",
            str(paths["localization"]),
            "--telemetry-model",
            str(paths["telemetry_model"]),
            "--telemetry-schema",
            str(paths["telemetry_schema"]),
            "--privacy-boundaries",
            str(paths["privacy"]),
            "--crash-reporting",
            str(paths["crash_reporting"]),
            "--support-status",
            str(paths["support_status"]),
            "--flagship-readiness",
            str(paths["flagship"]),
            "--support-packets",
            str(paths["support_packets"]),
            "--weekly-product-pulse",
            str(paths["weekly_pulse"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class VerifyNext90M128FleetTrustPlaneMonitorsTests(unittest.TestCase):
    def test_verifier_accepts_regenerated_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m128-verify-") as temp_dir:
            paths = _fixture_tree(
                Path(temp_dir),
                runtime_locales=["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"],
                feedback_status="ready",
                refresh_mode="remote_live",
                refresh_error="",
                open_packet_count=0,
            )
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            result = _verify(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("M128 trust-plane monitors verifier passed", result.stdout)

    def test_verifier_rejects_monitor_summary_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m128-verify-") as temp_dir:
            paths = _fixture_tree(
                Path(temp_dir),
                runtime_locales=["en-us", "de-de", "fr-fr", "ja-jp", "pt-br", "zh-cn"],
                feedback_status="ready",
                refresh_mode="remote_live",
                refresh_error="",
                open_packet_count=0,
            )
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["monitor_summary"]["trust_plane_status"] = "blocked"
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = _verify(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("monitor summary drifted", result.stderr)


if __name__ == "__main__":
    unittest.main()
