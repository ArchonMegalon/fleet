from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_materialize_next90_m135_fleet_design_queued_coverage import _fixture_tree


MATERIALIZER = Path("/docker/fleet/scripts/materialize_next90_m135_fleet_design_queued_coverage.py")
VERIFIER = Path("/docker/fleet/scripts/verify_next90_m135_fleet_design_queued_coverage.py")


class VerifyNext90M135FleetDesignQueuedCoverageTest(unittest.TestCase):
    def _common_args(self, fixture: dict[str, Path], artifact: Path) -> list[str]:
        return [
            "--artifact",
            str(artifact),
            "--successor-registry",
            str(fixture["registry"]),
            "--queue-staging",
            str(fixture["queue"]),
            "--design-queue-staging",
            str(fixture["design_queue"]),
            "--next90-guide",
            str(fixture["next90_guide"]),
            "--sync-manifest",
            str(fixture["sync_manifest"]),
            "--mirror-backlog",
            str(fixture["mirror_backlog"]),
            "--mirror-evidence",
            str(fixture["mirror_evidence"]),
            "--program-milestones",
            str(fixture["program_milestones"]),
            "--status-plane",
            str(fixture["status_plane"]),
        ]

    def test_verifier_accepts_matching_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                design_status="done",
                include_ea_in_backlog=True,
                include_ea_in_status_plane=True,
                mirror_latest_at="2026-04-22T10:00:00Z",
                last_reviewed="2026-04-22",
                evidence_source_sha="fixture-sha",
            )
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZER),
                    "--output",
                    str(artifact),
                    "--markdown-output",
                    str(markdown),
                    *self._common_args(fixture, artifact)[2:],
                ],
                check=True,
            )
            completed = subprocess.run(
                [sys.executable, str(VERIFIER), *self._common_args(fixture, artifact), "--json"],
                check=True,
                capture_output=True,
                text=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "pass")

    def test_verifier_rejects_monitor_summary_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture = _fixture_tree(
                tmp_path,
                design_status="done",
                include_ea_in_backlog=True,
                include_ea_in_status_plane=True,
                mirror_latest_at="2026-04-22T10:00:00Z",
                last_reviewed="2026-04-22",
                evidence_source_sha="fixture-sha",
            )
            artifact = tmp_path / "artifact.json"
            markdown = tmp_path / "artifact.md"
            subprocess.run(
                [
                    sys.executable,
                    str(MATERIALIZER),
                    "--output",
                    str(artifact),
                    "--markdown-output",
                    str(markdown),
                    *self._common_args(fixture, artifact)[2:],
                ],
                check=True,
            )
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            payload["monitor_summary"]["queued_work_task_count"] = 0
            artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(VERIFIER), *self._common_args(fixture, artifact), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )

        result = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("monitor summary drifted" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
