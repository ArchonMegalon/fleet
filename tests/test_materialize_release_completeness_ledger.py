from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_release_completeness_ledger.py")


class ReleaseCompletenessLedgerTests(unittest.TestCase):
    def test_materialize_release_completeness_ledger_builds_expected_tick_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            flagship = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
            journeys = tmp_path / "JOURNEY_GATES.generated.json"
            progress = tmp_path / "PROGRESS_REPORT.generated.json"
            frontier = tmp_path / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
            out = tmp_path / "LTT_AND_12_TICKS_RELEASE_COMPLETENESS.generated.json"

            flagship.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-19T18:00:00Z",
                        "ready_keys": [
                            "desktop_client",
                            "rules_engine_and_import",
                            "hub_and_registry",
                            "mobile_play_shell",
                            "ui_kit_and_flagship_polish",
                            "media_artifacts",
                            "horizons_and_public_surface",
                            "fleet_and_operator_loop",
                        ],
                        "warning_keys": [],
                        "missing_keys": [],
                    }
                ),
                encoding="utf-8",
            )
            journeys.write_text(
                json.dumps(
                    {
                        "journeys": [
                            {"id": "install_claim_restore_continue", "title": "Install", "state": "ready"},
                            {"id": "build_explain_publish", "title": "Build", "state": "ready"},
                            {"id": "campaign_session_recover_recap", "title": "Campaign", "state": "ready"},
                            {"id": "recover_from_sync_conflict", "title": "Conflict", "state": "ready"},
                            {"id": "report_cluster_release_notify", "title": "Release", "state": "ready"},
                            {"id": "organize_community_and_close_loop", "title": "Community", "state": "ready"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            progress.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-05-19T18:01:00Z",
                        "public_route_cards": [
                            {"id": "downloads", "title": "Downloads", "route": "/downloads", "proof_state": "public-stable"},
                            {"id": "workbench", "title": "Workbench", "route": "/home/work", "proof_state": "public-stable"},
                            {"id": "account", "title": "Account", "route": "/account/access", "proof_state": "public-stable"},
                            {"id": "support", "title": "Support", "route": "/account/support", "proof_state": "preview-bounded"},
                            {"id": "feedback", "title": "Feedback", "route": "/feedback", "proof_state": "public-stable"},
                            {"id": "governance", "title": "Governance", "route": "/roadmap", "proof_state": "preview-bounded"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            frontier.write_text(
                yaml.safe_dump(
                    {
                        "completion_audit": {"status": "fail", "reason": "repo backlog still open"},
                        "repo_backlog_audit": {"status": "fail", "reason": "one item open", "open_item_count": 1},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--flagship-readiness",
                    str(flagship),
                    "--journey-gates",
                    str(journeys),
                    "--progress-report",
                    str(progress),
                    "--completion-frontier",
                    str(frontier),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["ltt_inventory_count"], 20)
            self.assertEqual(payload["summary"]["tick_count"], 12)
            self.assertEqual(payload["summary"]["pass_count"], 10)
            self.assertFalse(payload["summary"]["absolute_finish_allowed"])
            self.assertEqual(payload["release_claim_guard"]["incomplete_tick_ids"], ["support", "governance"])


if __name__ == "__main__":
    unittest.main()
