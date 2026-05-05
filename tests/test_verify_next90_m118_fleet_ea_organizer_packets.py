from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from test_materialize_next90_m118_fleet_ea_organizer_packets import _closure_reason, _fixture_tree, _materialize, _queue_payload, _write_yaml
except ModuleNotFoundError:
    from tests.test_materialize_next90_m118_fleet_ea_organizer_packets import _closure_reason, _fixture_tree, _materialize, _queue_payload, _write_yaml


VERIFIER = Path("/docker/fleet/scripts/verify_next90_m118_fleet_ea_organizer_packets.py")


class VerifyNext90M118FleetEaOrganizerPacketsTests(unittest.TestCase):
    def test_verifier_accepts_regenerated_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=False)
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            result = subprocess.run(
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
                    "--support-packets",
                    str(paths["support"]),
                    "--hub-local-release-proof",
                    str(paths["hub"]),
                    "--hub-organizer-verifier",
                    str(paths["organizer_verifier"]),
                    "--hub-creator-publication-verifier",
                    str(paths["creator_verifier"]),
                    "--ea-operator-safe-pack",
                    str(paths["ea_safe_pack"]),
                    "--ea-organizer-packet-pack",
                    str(paths["ea_organizer_pack"]),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("M118 organizer operator packet verifier passed", result.stdout)

    def test_verifier_rejects_artifact_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=False)
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["support_risk"]["state"] = "high"
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
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
                    "--support-packets",
                    str(paths["support"]),
                    "--hub-local-release-proof",
                    str(paths["hub"]),
                    "--hub-organizer-verifier",
                    str(paths["organizer_verifier"]),
                    "--hub-creator-publication-verifier",
                    str(paths["creator_verifier"]),
                    "--ea-operator-safe-pack",
                    str(paths["ea_safe_pack"]),
                    "--ea-organizer-packet-pack",
                    str(paths["ea_organizer_pack"]),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("support risk drifted", result.stderr)

    def test_verifier_rejects_source_packet_link_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            payload = json.loads(paths["artifact"].read_text(encoding="utf-8"))
            payload["source_packet_links"]["hub_publication_receipts"]["receipt_ids"] = ["artifact_shelf:v2"]
            paths["artifact"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
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
                    "--support-packets",
                    str(paths["support"]),
                    "--hub-local-release-proof",
                    str(paths["hub"]),
                    "--hub-organizer-verifier",
                    str(paths["organizer_verifier"]),
                    "--hub-creator-publication-verifier",
                    str(paths["creator_verifier"]),
                    "--ea-operator-safe-pack",
                    str(paths["ea_safe_pack"]),
                    "--ea-organizer-packet-pack",
                    str(paths["ea_organizer_pack"]),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source packet links drifted", result.stderr)

    def test_verifier_rejects_source_input_timestamp_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            support_payload = json.loads(paths["support"].read_text(encoding="utf-8"))
            support_payload["generated_at"] = "2026-05-05T10:31:53Z"
            paths["support"].write_text(json.dumps(support_payload, indent=2) + "\n", encoding="utf-8")

            result = subprocess.run(
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
                    "--support-packets",
                    str(paths["support"]),
                    "--hub-local-release-proof",
                    str(paths["hub"]),
                    "--hub-organizer-verifier",
                    str(paths["organizer_verifier"]),
                    "--hub-creator-publication-verifier",
                    str(paths["creator_verifier"]),
                    "--ea-operator-safe-pack",
                    str(paths["ea_safe_pack"]),
                    "--ea-organizer-packet-pack",
                    str(paths["ea_organizer_pack"]),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source input timestamps or packet status drifted", result.stderr)

    def test_verifier_accepts_partial_completed_closeout_guard_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fleet-m118-verify-") as temp_dir:
            paths = _fixture_tree(Path(temp_dir), include_ea_organizer_pack=True)
            queue_payload = _queue_payload()
            queue_payload["items"][0]["status"] = "complete"
            queue_payload["items"][0]["completion_action"] = "verify_closed_package_only"
            queue_payload["items"][0]["do_not_reopen_reason"] = _closure_reason()
            _write_yaml(paths["queue"], queue_payload)

            materialize = _materialize(paths)
            self.assertEqual(materialize.returncode, 0, msg=materialize.stderr)

            result = subprocess.run(
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
                    "--support-packets",
                    str(paths["support"]),
                    "--hub-local-release-proof",
                    str(paths["hub"]),
                    "--hub-organizer-verifier",
                    str(paths["organizer_verifier"]),
                    "--hub-creator-publication-verifier",
                    str(paths["creator_verifier"]),
                    "--ea-operator-safe-pack",
                    str(paths["ea_safe_pack"]),
                    "--ea-organizer-packet-pack",
                    str(paths["ea_organizer_pack"]),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("M118 organizer operator packet verifier passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
