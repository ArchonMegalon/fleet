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

    def test_ea_lane_capacity_snapshot_prefers_provider_registry_details(self) -> None:
        self.admin.ea_codex_profiles = lambda: {
            "profiles": [
                {"profile": "review_light", "model": "ea-review-light", "provider_hint_order": ["browseract"]},
            ],
            "provider_health": {"providers": {"chatplayground": {"state": "ready"}}},
            "provider_registry": {
                "contract_name": "ea.provider_registry",
                "lanes": [
                    {
                        "profile": "review_light",
                        "public_model": "ea-review-light",
                        "brain": "ea-review-light",
                        "backend": "chatplayground",
                        "health_provider_key": "chatplayground",
                        "primary_provider_key": "browseract",
                        "provider_hint_order": ["browseract"],
                        "review_required": False,
                        "merge_policy": "auto_if_low_risk",
                        "capacity_summary": {"state": "ready", "configured_slots": 2, "ready_slots": 1, "slot_owners": ["audit"]},
                        "providers": [
                            {
                                "provider_key": "browseract",
                                "backend": "chatplayground",
                                "state": "ready",
                                "capacity": {"state": "ready"},
                                "slot_pool": {"configured_slots": 2, "ready_slots": 1, "owners": ["audit"]},
                            }
                        ],
                    }
                ],
            },
        }

        snapshots = self.admin.ea_lane_capacity_snapshot({"review_light": {"provider_hint_order": ["browseract"]}})

        self.assertEqual(snapshots["review_light"]["backend"], "chatplayground")
        self.assertEqual(snapshots["review_light"]["brain"], "ea-review-light")
        self.assertEqual(snapshots["review_light"]["primary_provider_key"], "browseract")
        self.assertEqual(snapshots["review_light"]["capacity_summary"]["ready_slots"], 1)
        self.assertEqual(snapshots["review_light"]["provider_registry_contract"], "ea.provider_registry")

    def test_build_worker_posture_payload_keeps_provider_distinct_from_backend(self) -> None:
        payload = self.admin.build_worker_posture_payload(
            {
                "config": {"accounts": {}},
                "projects": [
                    {
                        "id": "fleet",
                        "current_slice": "Route jury review",
                        "selected_lane": "review_light",
                        "selected_profile": "review_light",
                        "selected_lane_capacity_state": "ready",
                        "selected_lane_capacity": {
                            "lane": "review_light",
                            "profile": "review_light",
                            "backend": "chatplayground",
                            "primary_provider_key": "browseract",
                            "capacity_summary": {"configured_slots": 2, "ready_slots": 1, "slot_owners": ["audit"]},
                            "providers": [{"provider_key": "browseract", "backend": "chatplayground"}],
                        },
                    }
                ],
                "recent_runs": [],
            },
            workers=[
                {
                    "worker_id": "run-1",
                    "project_id": "fleet",
                    "phase": "coding",
                    "current_slice": "Route jury review",
                    "selected_lane": "review_light",
                    "selected_profile": "review_light",
                    "capacity_backend": "chatplayground",
                    "brain": "ea-review-light",
                    "capacity_state": "ready",
                    "configured_slots": 2,
                    "ready_slots": 1,
                    "slot_owners": ["audit"],
                    "elapsed_human": "4m",
                }
            ],
        )

        active = payload["active"][0]
        self.assertEqual(active["backend"], "chatplayground")
        self.assertEqual(active["provider"], "browseract")
        self.assertEqual(active["brain"], "ea-review-light")

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
                        "required_reviewer_lane": "jury",
                        "task_final_reviewer_lane": "jury",
                        "task_landing_lane": "jury",
                        "task_allow_credit_burn": False,
                        "task_allow_paid_fast_lane": False,
                        "task_allow_core_rescue": False,
                        "task_core_rescue_after_round": 0,
                        "workflow_stage": self.admin.JURY_REVIEW_PENDING_STATUS,
                        "next_reviewer_lane": "jury",
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
            blocker_forecast={"now": "awaiting jury"},
        )

        self.assertEqual(payload["landing_lane"], "jury")
        self.assertFalse(payload["allow_credit_burn"])
        self.assertFalse(payload["allow_core_rescue"])
        self.assertEqual(payload["current_stage_label"], "Jury")
        self.assertEqual(payload["round_label"], "r1 / r3")
        self.assertEqual(payload["rounds_remaining"], 2)
        self.assertEqual(payload["provider"], "gemini_vortex")
        self.assertEqual(payload["next_reviewer_summary"], "next reviewer jury")
        self.assertEqual(payload["landing_summary"], "landing via jury")

    def test_execution_loop_payload_includes_landed_telemetry_rollups(self) -> None:
        self.admin.load_latest_telemetry_payload = lambda _status: {
            "summary": {"total_landed_slices": 5},
            "review_loop": {
                "accepted_on_round_counts": {"1": 2, "2": 2, "3": 1},
                "core_rescue_rate": 0.2,
                "shadow_assist_rate": 0.4,
            },
            "worker_utilization": {
                "groundwork_primary_busy_percent": 31.5,
                "groundwork_shadow_busy_percent": 18.5,
                "jury_busy_percent": 22.0,
            },
        }

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
                        "review_rounds_used": 2,
                        "required_reviewer_lane": "jury",
                        "task_final_reviewer_lane": "jury",
                        "task_landing_lane": "jury",
                        "task_allow_credit_burn": False,
                        "task_allow_paid_fast_lane": False,
                        "task_allow_core_rescue": False,
                        "workflow_stage": self.admin.JURY_REWORK_REQUIRED_STATUS,
                        "next_reviewer_lane": "jury",
                    }
                ]
            },
            queue_forecast={"now": {"project_id": "fleet", "title": "Refresh mission board"}},
            blocker_forecast={"now": "awaiting jury"},
        )

        self.assertEqual(payload["telemetry_review_loop"]["accepted_on_round_counts"]["1"], 2)
        self.assertEqual(payload["telemetry_worker_utilization"]["groundwork_shadow_busy_percent"], 18.5)
        self.assertEqual(payload["telemetry_summary"]["total_landed_slices"], 5)

    def test_jury_telemetry_payload_surfaces_queue_latency_and_shared_participant_pressure(self) -> None:
        def fake_jury_review_run_rows(_config, *, active_only=False, finished_since=None):
            if active_only:
                return [
                    {
                        "project_id": "ui",
                        "status": "running",
                        "duration_ms": 240000,
                    }
                ]
            if finished_since is not None:
                return [
                    {"project_id": "fleet", "status": "complete", "duration_ms": 300000},
                    {"project_id": "fleet", "status": "complete", "duration_ms": 600000},
                    {"project_id": "ui", "status": "complete", "duration_ms": 900000},
                ]
            return []

        self.admin.jury_review_run_rows = fake_jury_review_run_rows
        self.admin.participant_lane_rows_for_admin = lambda statuses=None: [
            {"project_id": "fleet", "hub_user_id": "usr_1", "subject_id": "subject-1", "lane_role": "review", "telemetry": {"auth_ready": True}, "auth_completed_at": "2026-03-19T08:10:00Z"},
            {"project_id": "fleet", "hub_user_id": "usr_1", "subject_id": "subject-1", "lane_role": "coding", "telemetry": {"auth_ready": True}, "auth_completed_at": "2026-03-19T08:11:00Z"},
        ]

        payload = self.admin.jury_telemetry_payload(
            {
                "config": {
                    "accounts": {},
                    "lanes": {"jury": {}},
                    "projects": [
                        {
                            "id": "fleet",
                            "participant_burst": {
                                "enabled": True,
                                "max_active_workers": 2,
                                "eligible_task_classes": ["bounded_fix", "multi_file_impl"],
                                "autoscale": {
                                    "enabled": True,
                                    "max_active_workers": 8,
                                    "increase_when": {
                                        "sponsor_ready_lanes_gte": 2,
                                        "jury_oldest_wait_seconds_lt": 86400,
                                        "premium_queue_depth_gte": 1,
                                    },
                                },
                            },
                        },
                    ],
                },
                "projects": [
                    {
                        "id": "fleet",
                        "current_slice": "Refresh mission board",
                        "runtime_status": "review_requested",
                        "queue": [{"title": "tighten review flow", "participant_eligible": True}],
                        "queue_index": 0,
                        "required_reviewer_lane": "jury",
                        "task_final_reviewer_lane": "jury",
                        "next_reviewer_lane": "jury",
                        "active_reviewer_lane": "",
                        "workflow_stage": self.admin.JURY_REVIEW_PENDING_STATUS,
                        "pull_request": {"review_requested_at": "2026-03-19T08:00:00Z"},
                    },
                    {
                        "id": "ui",
                        "current_slice": "Tighten cockpit chrome",
                        "runtime_status": "review_requested",
                        "required_reviewer_lane": "jury",
                        "task_final_reviewer_lane": "jury",
                        "next_reviewer_lane": "",
                        "active_reviewer_lane": "jury",
                        "workflow_stage": self.admin.JURY_REVIEW_PENDING_STATUS,
                        "pull_request": {"review_requested_at": "2026-03-19T09:00:00Z"},
                    },
                ],
            },
            lane_capacities={
                "jury": {
                    "state": "degraded",
                    "capacity_summary": {"configured_slots": 2, "ready_slots": 1, "degraded_slots": 1},
                    "providers": [
                        {
                            "provider_key": "chatplayground",
                            "state": "degraded",
                            "detail": "challenge",
                            "configured_slots": 2,
                            "ready_slots": 1,
                        }
                    ],
                }
            },
        )

        self.assertEqual(payload["active_jury_jobs"], 1)
        self.assertEqual(payload["queued_jury_jobs"], 1)
        self.assertEqual(payload["blocked_coding_workers"], 2)
        self.assertEqual(payload["blocked_participant_workers"], 2)
        self.assertEqual(payload["blocked_total_workers"], 4)
        self.assertEqual(payload["last_24h_jury_completions"], 3)
        self.assertEqual(payload["median_turnaround_ms"], 600000)
        self.assertEqual(payload["p95_turnaround_ms"], 900000)
        self.assertEqual(payload["oldest_waiting_item"]["project_id"], "fleet")
        self.assertTrue(payload["service_serialized"])
        self.assertIn("single_ready_slot", payload["serialization_reasons"])
        self.assertIn("provider_challenge_state", payload["serialization_reasons"])
        self.assertIn("shared_participant_identity", payload["serialization_reasons"])
        self.assertTrue(payload["participant_burst"]["shared_subject_serialized"])
        self.assertEqual(payload["participant_burst"]["active_by_role"]["review"], 1)
        self.assertEqual(payload["participant_burst"]["active_by_role"]["coding"], 1)
        self.assertEqual(payload["participant_burst"]["sponsor_ready_lanes"], 2)
        self.assertEqual(payload["participant_burst"]["premium_queue_depth"], 1)
        self.assertIn("fleet", payload["participant_burst"]["surge_mode_projects"])

    def test_mission_board_payload_includes_jury_telemetry(self) -> None:
        self.admin.load_latest_telemetry_payload = lambda _status: {"summary": {}, "review_loop": {}, "worker_utilization": {}}
        self.admin.jury_telemetry_payload = lambda status, lane_capacities: {
            "active_jury_jobs": 1,
            "queued_jury_jobs": 2,
            "blocked_total_workers": 3,
        }
        self.admin.ea_codex_status = lambda force=False, window="7d": {"onemin_billing_aggregate": {}}

        payload = self.admin.mission_board_payload(
            {"projects": [], "groups": [], "config": {"spider": {}, "lanes": {}}, "account_pools": []},
            mission_snapshot={},
            queue_forecast={"now": {}, "next": {}},
            vision_forecast={},
            capacity_forecast={"lanes": [], "critical_path_lane": "jury", "mission_runway": "forever", "pool_runway": "7d"},
            blocker_forecast={"now": "none", "next": "none", "vision": "none"},
            attention=[],
        )

        self.assertEqual(payload["jury_telemetry"]["active_jury_jobs"], 1)
        self.assertEqual(payload["jury_telemetry"]["queued_jury_jobs"], 2)

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
                "required_reviewer_lane": "jury",
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

    def test_mission_board_payload_includes_billing_truth_card(self) -> None:
        self.admin.ea_codex_status = lambda force=False, window="7d": {
            "topup_summary": {"last_actual_balance_check_at": "2026-03-18T09:00:00Z"},
            "onemin_billing_aggregate": {
                "sum_free_credits": 1_000_000,
                "sum_max_credits": 2_000_000,
                "remaining_percent_total": 50.0,
                "next_topup_at": "2026-03-31T00:00:00Z",
                "topup_amount": 2_000_000,
                "hours_until_next_topup": 320.5,
                "hours_remaining_at_current_pace_no_topup": 38.8,
                "hours_remaining_including_next_topup_at_current_pace": 510.2,
                "days_remaining_including_next_topup_at_7d_avg": 167.0,
                "depletes_before_next_topup": False,
                "basis_summary": "actual_billing_usage_page x2",
                "basis_counts": {"actual_billing_usage_page": 2},
                "slot_count_with_billing_snapshot": 2,
                "slot_count_with_member_reconciliation": 1,
            },
        }

        payload = self.admin.mission_board_payload(
            {"projects": [], "groups": [], "config": {"spider": {}}, "account_pools": []},
            mission_snapshot={},
            queue_forecast={"now": {}, "next": {}},
            vision_forecast={},
            capacity_forecast={"lanes": [], "critical_path_lane": "groundwork", "mission_runway": "forever", "pool_runway": "7d"},
            blocker_forecast={"now": "none", "next": "none", "vision": "none"},
            attention=[],
        )

        credit = payload["provider_credit_card"]
        self.assertEqual(payload["contract_name"], "fleet.mission_board")
        self.assertEqual(payload["contract_version"], "2026-03-18")
        self.assertEqual(credit["provider"], "1min")
        self.assertEqual(credit["free_credits"], 1_000_000)
        self.assertEqual(credit["next_topup_at"], "2026-03-31T00:00:00Z")
        self.assertEqual(credit["topup_amount"], 2_000_000)
        self.assertEqual(credit["basis_quality"], "actual")
        self.assertEqual(credit["slot_count_with_billing_snapshot"], 2)
        self.assertEqual(credit["slot_count_with_member_reconciliation"], 1)

    def test_status_surface_payload_promotes_canonical_views(self) -> None:
        status = {
            "generated_at": "2026-03-18T12:00:00Z",
            "cockpit": {
                "mission_board": {"contract_name": "fleet.mission_board", "contract_version": "2026-03-18"},
                "mission_snapshot": {"headline": "Truth -> Slice -> Review -> Land"},
                "queue_forecast": {"now": {"title": "current"}},
                "vision_forecast": {"milestone_title": "A0"},
                "capacity_forecast": {"critical_path_lane": "groundwork"},
                "blocker_forecast": {"now": "none"},
            },
        }

        payload = self.admin.status_surface_payload(status)

        self.assertIn("explorer", payload)
        self.assertIn("public_status", payload)
        self.assertEqual(payload["explorer"], status["cockpit"])
        self.assertEqual(payload["mission_board"]["contract_name"], "fleet.mission_board")
        self.assertEqual(payload["mission_snapshot"]["headline"], "Truth -> Slice -> Review -> Land")
        self.assertEqual(payload["queue_forecast"]["now"]["title"], "current")
        self.assertEqual(payload["vision_forecast"]["milestone_title"], "A0")
        self.assertEqual(payload["capacity_forecast"]["critical_path_lane"], "groundwork")
        self.assertEqual(payload["blocker_forecast"]["now"], "none")
        self.assertEqual(payload["public_status"]["contract_name"], "fleet.public_status")

    def test_public_dashboard_status_payload_is_minimal_and_usable(self) -> None:
        self.admin.admin_status_payload = lambda: {
            "generated_at": "2026-03-18T12:00:00Z",
            "projects": [
                {
                    "id": "fleet",
                    "current_slice": "persist survival lane queue state",
                    "runtime_status": "dispatch_pending",
                    "selected_lane": "easy",
                    "next_reviewer_lane": "jury",
                    "required_reviewer_lane": "jury",
                    "task_final_reviewer_lane": "jury",
                    "task_landing_lane": "jury",
                    "task_workflow_kind": "groundwork_review_loop",
                    "review_rounds_used": 1,
                    "task_max_review_rounds": 3,
                    "task_allow_credit_burn": False,
                    "task_allow_paid_fast_lane": False,
                    "task_allow_core_rescue": False,
                    "sustainable_runway": "7d",
                    "decision_meta_summary": "lane=easy/mcp",
                    "deployment": {"status": "preview", "target_url": "https://fleet.example/fleet", "display": "preview | https://fleet.example/fleet"},
                    "readiness": {
                        "stage": "repo_local_complete",
                        "label": "Repo-Local Complete",
                        "next_stage": "package_canonical",
                        "terminal_stage": "boundary_pure",
                        "final_claim_allowed": False,
                        "summary": "Repo-local complete, but package-canonical evidence is not locked.",
                    },
                }
            ],
            "groups": [
                {
                    "id": "chummer-vnext",
                    "phase": "dispatch_pending",
                    "pressure_state": "nominal",
                    "dispatch_basis": "ready",
                    "lifecycle": "live",
                    "projects": ["fleet"],
                    "deployment": {"status": "public", "target_url": "https://fleet.example", "display": "public | https://fleet.example"},
                    "deployment_readiness": {
                        "publicly_promoted": False,
                        "summary": "Deployment is still preview; public promotion is not yet claimed.",
                    },
                }
            ],
            "cockpit": {
                "summary": {"fleet_health": "ok", "scheduler_posture": "steady", "blocked_groups": 0, "open_incidents": 0, "review_waiting_projects": 0},
                "mission_board": {"contract_name": "fleet.mission_board", "contract_version": "2026-03-18"},
            },
        }

        payload = self.admin.public_dashboard_status_payload()

        self.assertEqual(payload["contract_name"], "fleet.public_status")
        self.assertEqual(payload["mission_board"]["contract_name"], "fleet.mission_board")
        self.assertEqual(payload["projects"][0]["id"], "fleet")
        self.assertEqual(payload["projects"][0]["task_landing_lane"], "jury")
        self.assertFalse(payload["projects"][0]["task_allow_paid_fast_lane"])
        self.assertEqual(payload["projects"][0]["readiness"]["stage"], "repo_local_complete")
        self.assertEqual(payload["groups"][0]["id"], "chummer-vnext")
        self.assertIn("deployment_readiness", payload["groups"][0])
        self.assertEqual(payload["deployment_posture"]["command_deck_path"], "/admin")
        self.assertEqual(payload["deployment_posture"]["public_target_count"], 2)
        self.assertIn("readiness_summary", payload)
        self.assertNotIn("config", payload)
        self.assertNotIn("accounts", payload)

    def test_queue_forecast_uses_dispatchable_slice_when_no_worker_is_running(self) -> None:
        status = {
            "projects": [
                {
                    "id": "fleet",
                    "current_slice": "persist survival lane queue state",
                    "runtime_status": self.admin.READY_STATUS,
                    "selected_lane": "easy",
                    "selected_lane_capacity_state": "fallback_ready",
                    "decision_meta_summary": "lane=easy/mcp",
                    "required_reviewer_lane": "jury",
                    "task_difficulty": "hard",
                    "task_risk_level": "high",
                    "task_acceptance_level": "reviewed",
                }
            ]
        }

        payload = self.admin.queue_forecast_payload(status, workers=[])

        self.assertEqual(payload["now"]["project_id"], "fleet")
        self.assertEqual(payload["now"]["title"], "persist survival lane queue state")
        self.assertEqual(payload["now"]["lane"], "easy")
        self.assertNotEqual(payload["now"]["title"], "Idle")


if __name__ == "__main__":
    unittest.main()
