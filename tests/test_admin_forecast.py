from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/admin/app.py")


def load_admin_module():
    spec = importlib.util.spec_from_file_location("test_admin_app_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdminForecastTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = load_admin_module()

    def test_queue_candidate_confidence_tracks_runtime_risk(self) -> None:
        self.assertEqual(
            self.admin.queue_candidate_confidence({"runtime_status": self.admin.READY_STATUS, "selected_lane_capacity_state": "ready"}),
            "stable",
        )
        self.assertEqual(
            self.admin.queue_candidate_confidence({"runtime_status": "review_requested", "selected_lane_capacity_state": "ready"}),
            "likely",
        )
        self.assertEqual(
            self.admin.queue_candidate_confidence({"runtime_status": self.admin.WAITING_CAPACITY_STATUS, "selected_lane_capacity_state": "degraded"}),
            "volatile",
        )

    def test_capacity_forecast_marks_core_runway(self) -> None:
        payload = self.admin.capacity_forecast_payload(
            {"projects": [], "groups": []},
            lane_capacities={
                "core": {
                    "state": "ready",
                    "profile": "core",
                    "model": "ea-coder-hard",
                    "providers": [
                        {
                            "provider_key": "onemin",
                            "remaining_percent_of_max": 68.0,
                            "estimated_hours_remaining_at_current_pace": 48.0,
                        }
                    ],
                },
                "easy": {"state": "unknown", "providers": []},
                "jury": {"state": "ready", "providers": []},
            },
            runway={"accounts": [{"projected_exhaustion": "14h"}]},
        )

        self.assertEqual(payload["critical_path_lane"], "core")
        self.assertEqual(payload["pool_runway"], "14h")
        self.assertTrue(any(item["lane"] == "core" and item["remaining_text"] == "68%" for item in payload["lanes"]))

    def test_mission_forecast_headline_includes_capacity_summary(self) -> None:
        queue_forecast = {
            "now": {"title": "surface lane/backend/capacity posture", "remaining_human": "31m"},
            "next": {"title": "allowance-aware EA capacity probing"},
        }
        payload = self.admin.mission_forecast_payload(
            {
                "groups": [
                    {"id": "fleet", "status": "running", "program_eta": {"eta_human": "13d"}, "design_progress": {"summary": "Main mission group"}},
                ]
            },
            queue_forecast=queue_forecast,
            lane_capacities={
                "core": {"providers": [{"remaining_percent_of_max": 68.0}]},
                "easy": {"providers": []},
                "jury": {"providers": [{"remaining_percent_of_max": 91.0}]},
            },
        )

        self.assertIn("Working now: surface lane/backend/capacity posture.", payload["headline"])
        self.assertIn("Capacity: Core 68%, Easy n/a, Jury 91%.", payload["headline"])

    def test_ea_lane_capacity_snapshot_keeps_repair_profile_distinct_from_easy(self) -> None:
        self.admin.ea_codex_profiles = lambda: {
            "profiles": [
                {"profile": "easy", "model": "ea-coder-fast", "provider_hint_order": ["magixai"]},
                {"profile": "repair", "model": "ea-coder-fast", "provider_hint_order": ["magixai"]},
            ],
            "provider_health": {"providers": {"magixai": {"state": "ready"}}},
        }

        snapshots = self.admin.ea_lane_capacity_snapshot({"repair": {"provider_hint_order": ["magixai"]}})

        self.assertEqual(snapshots["repair"]["profile"], "repair")
        self.assertEqual(snapshots["repair"]["model"], "ea-coder-fast")


if __name__ == "__main__":
    unittest.main()
