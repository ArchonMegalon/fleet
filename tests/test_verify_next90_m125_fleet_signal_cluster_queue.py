from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m125_fleet_signal_cluster_queue import _fixture_tree, _materialize


VERIFIER = Path("/docker/fleet/scripts/verify_next90_m125_fleet_signal_cluster_queue.py")


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
            "--public-signal-pipeline",
            str(paths["pipeline"]),
            "--feedback-ooda-loop",
            str(paths["ooda"]),
            "--productlift-bridge",
            str(paths["productlift"]),
            "--katteb-lane",
            str(paths["katteb"]),
            "--clickrank-lane",
            str(paths["clickrank"]),
            "--weekly-product-pulse",
            str(paths["weekly"]),
            "--support-case-packets",
            str(paths["support"]),
            "--signal-source",
            str(paths["signal_source"]),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class VerifyNext90M125FleetSignalClusterQueueTests(unittest.TestCase):
    def test_verifier_accepts_regenerated_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m125-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            result = _verify(paths)
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("M125 signal-cluster queue verifier passed", result.stdout)

    def test_verifier_rejects_queue_synthesis_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m125-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir))
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["queue_synthesis"]["queue_candidate_count"] = 99
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = _verify(paths)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("queue synthesis section drifted", result.stderr)


if __name__ == "__main__":
    unittest.main()
