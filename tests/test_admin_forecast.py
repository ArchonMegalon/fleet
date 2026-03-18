from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/admin/app.py")


def install_fastapi_stubs() -> None:
    if "fastapi" in sys.modules and "fastapi.responses" in sys.modules:
        return

    fastapi = types.ModuleType("fastapi")
    responses = types.ModuleType("fastapi.responses")

    class DummyFastAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __getattr__(self, _name):
            def decorator(*args, **kwargs):
                def wrapper(func):
                    return func

                return wrapper

            return decorator

    class DummyHTTPException(Exception):
        pass

    class DummyRequest:
        pass

    class DummyResponse:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    def dummy_form(*args, **kwargs):
        return None

    fastapi.FastAPI = DummyFastAPI
    fastapi.Form = dummy_form
    fastapi.HTTPException = DummyHTTPException
    fastapi.Request = DummyRequest
    responses.HTMLResponse = DummyResponse
    responses.JSONResponse = DummyResponse
    responses.PlainTextResponse = DummyResponse
    responses.RedirectResponse = DummyResponse
    responses.Response = DummyResponse
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def load_admin_module():
    install_fastapi_stubs()
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

    def test_capacity_forecast_includes_review_light_native_allowance_and_local_burn(self) -> None:
        payload = self.admin.capacity_forecast_payload(
            {"config": {"lanes": {"review_light": {}}}, "projects": [], "groups": []},
            lane_capacities={
                "review_light": {
                    "state": "ready",
                    "profile": "review_light",
                    "model": "ea-review-light",
                    "providers": [
                        {
                            "provider_key": "chatplayground",
                            "remaining_percent_of_max": 91.0,
                            "estimated_remaining_credits_total": 1200,
                            "estimated_burn_credits_per_hour": 40,
                        }
                    ],
                }
            },
            runway={"lanes": [{"lane": "review_light", "estimated_cost_usd": 1.25, "run_count": 3}]},
        )

        review_light = payload["lanes"][0]
        self.assertEqual(review_light["lane"], "review_light")
        self.assertEqual(review_light["native_allowance"]["estimated_remaining_credits_total"], 1200)
        self.assertEqual(review_light["local_estimated_burn_usd"], 1.25)
        self.assertEqual(review_light["sustainable_runway"], "91% allowance")

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

    def test_execution_loop_payload_tracks_zero_credit_jury_landing(self) -> None:
        payload = self.admin.execution_loop_payload(
            {
                "projects": [
                    {
                        "id": "fleet",
                        "current_slice": "Refresh mission board",
                        "runtime_status": "running",
                        "selected_lane": "groundwork",
                        "task_workflow_kind": self.admin.WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP,
                        "task_max_review_rounds": 3,
                        "review_rounds_used": 1,
                        "required_reviewer_lane": "review_light",
                        "task_final_reviewer_lane": "jury",
                        "task_landing_lane": "jury",
                        "task_allow_credit_burn": False,
                        "task_allow_paid_fast_lane": False,
                        "task_allow_core_rescue": False,
                        "task_core_rescue_after_round": 0,
                        "workflow_stage": self.admin.REVIEW_LIGHT_PENDING_STATUS,
                        "next_reviewer_lane": "review_light",
                        "core_rescue_likely_next": False,
                        "active_run_account_backend": "gemini_vortex",
                        "active_run_brain": "ea-groundwork-gemini",
                    }
                ]
            },
            queue_forecast={
                "now": {
                    "project_id": "fleet",
                    "title": "Refresh mission board",
                    "lane": "groundwork",
                    "provider": "gemini_vortex",
                    "brain": "ea-groundwork-gemini",
                    "remaining_human": "22m",
                    "verify_or_review_ahead": True,
                }
            },
            blocker_forecast={"now": "awaiting review_light"},
        )

        self.assertEqual(payload["landing_lane"], "jury")
        self.assertFalse(payload["allow_credit_burn"])
        self.assertFalse(payload["allow_core_rescue"])
        self.assertEqual(payload["current_stage_label"], "Review Light")
        self.assertEqual(payload["round_label"], "r1 / r3")
        self.assertEqual(payload["provider"], "gemini_vortex")

    def test_lane_runway_payload_marks_core_policy_off_when_credit_burn_disabled(self) -> None:
        lane_payload = self.admin.lane_runway_payload(
            {
                "projects": [
                    {
                        "id": "fleet",
                        "allowed_lanes": ["groundwork", "easy"],
                    }
                ]
            },
            capacity_forecast={
                "critical_path_lane": "groundwork",
                "lanes": [
                    {
                        "lane": "easy",
                        "provider": "gemini_vortex",
                        "model": "ea-gemini-flash",
                        "state": "ready",
                        "remaining_text": "91%",
                        "sustainable_runway": "91% allowance",
                    },
                    {
                        "lane": "core",
                        "provider": "onemin",
                        "model": "ea-coder-hard",
                        "state": "ready",
                        "remaining_text": "68%",
                        "sustainable_runway": "48h",
                    },
                ],
            },
            execution_loop={
                "project_id": "fleet",
                "workflow_kind": self.admin.WORKFLOW_KIND_GROUNDWORK_REVIEW_LOOP,
                "current_lane": "groundwork",
                "required_reviewer_lane": "review_light",
                "final_reviewer_lane": "jury",
                "landing_lane": "jury",
                "allow_credit_burn": False,
                "allow_paid_fast_lane": False,
            },
        )

        by_lane = {item["lane"]: item for item in lane_payload}
        self.assertTrue(by_lane["easy"]["policy_enabled"])
        self.assertFalse(by_lane["core"]["policy_enabled"])
        self.assertEqual(by_lane["core"]["policy_reason"], "credit burn disabled")


if __name__ == "__main__":
    unittest.main()
