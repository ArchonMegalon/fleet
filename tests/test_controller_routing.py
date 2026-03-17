from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path("/docker/fleet/controller/app.py")


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


def load_controller_module():
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location("test_controller_routing", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ControllerRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = load_controller_module()

    def test_groundwork_keywords_promote_groundwork_lane(self) -> None:
        slice_item = {"title": "architecture tradeoff review for fleet routing"}
        lane_snapshot = {"state": "ready", "providers": []}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": lane_snapshot,
                        "repair": lane_snapshot,
                        "groundwork": lane_snapshot,
                        "core": lane_snapshot,
                        "survival": lane_snapshot,
                    },
                ):
                    decision = self.controller.classify_tier({}, {}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["tier"], "groundwork")
        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["lane_submode"], "responses_groundwork")
        self.assertEqual(decision["runtime_model"], "ea-groundwork-gemini")
        self.assertEqual(decision["model_preferences"][0], "ea-groundwork-gemini")
        self.assertEqual(decision["allowed_lanes"][0], "groundwork")

    def test_explicit_groundwork_lane_policy_stays_off_core(self) -> None:
        slice_item = {
            "title": "status class vocabulary pass across fleet maturity labels",
            "difficulty": "medium",
            "risk_level": "medium",
            "allowed_lanes": ["groundwork", "easy", "repair", "core"],
        }
        lane_snapshot = {"state": "ready", "providers": []}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": lane_snapshot,
                        "repair": lane_snapshot,
                        "groundwork": lane_snapshot,
                        "core": lane_snapshot,
                        "survival": lane_snapshot,
                    },
                ):
                    decision = self.controller.classify_tier({}, {}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["lane_submode"], "responses_groundwork")
        self.assertEqual(decision["escalation_reason"], "groundwork_policy_default")

    def test_repair_lane_uses_repair_profile_and_explains_why_not_cheaper(self) -> None:
        slice_item = {"title": "patch queue retry handling"}
        lane_snapshot = {"state": "ready", "providers": []}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": lane_snapshot,
                        "repair": lane_snapshot,
                        "groundwork": lane_snapshot,
                        "core": lane_snapshot,
                        "survival": lane_snapshot,
                    },
                ):
                    decision = self.controller.classify_tier({}, {}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["lane"], "repair")
        self.assertEqual(decision["selected_profile"], "repair")
        self.assertEqual(decision["escalation_reason"], "bounded_patch_generation")
        self.assertEqual(
            decision["why_not_cheaper"],
            "repair is the cheapest implementation lane for bounded code changes",
        )

    def test_protected_runtime_forces_core_lane_and_operator_signoff(self) -> None:
        slice_item = {"title": "rotate runtime credentials", "protected_runtime": True}
        lane_snapshot = {"state": "ready", "providers": []}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": lane_snapshot,
                        "repair": lane_snapshot,
                        "groundwork": lane_snapshot,
                        "core": lane_snapshot,
                        "survival": lane_snapshot,
                    },
                ):
                    decision = self.controller.classify_tier({}, {}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["lane"], "core")
        self.assertEqual(decision["selected_profile"], "core")
        self.assertEqual(decision["why_not_cheaper"], "protected_runtime forces core authority")
        self.assertTrue(decision["task_meta"]["operator_override_required"])
        self.assertIn("operator_signoff", decision["task_meta"]["signoff_requirements"])

    def test_prepare_dispatch_candidate_blocks_design_only_slice(self) -> None:
        row = {
            "id": "fleet",
            "queue_json": '[{"title": "Plan design-only architecture slice", "dispatchability_state": "design_only"}]',
            "queue_index": 0,
            "status": "dispatch_pending",
            "active_run_id": None,
            "cooldown_until": None,
            "last_run_at": "",
            "last_error": "",
            "consecutive_failures": 0,
            "spider_tier": "",
            "spider_model": "",
            "spider_reason": "",
            "current_slice": "",
        }

        with mock.patch.object(self.controller, "persisted_review_runtime_status", return_value=""):
            with mock.patch.object(self.controller, "update_project_status") as mocked_update:
                candidate = self.controller.prepare_dispatch_candidate(
                    {"lanes": {}},
                    {"id": "fleet", "enabled": True, "queue_sources": []},
                    row,
                    self.controller.utc_now(),
                )

        self.assertFalse(candidate.dispatchable)
        self.assertEqual(candidate.runtime_status, "blocked")
        mocked_update.assert_called_once()

    def test_groundwork_requires_serial_review(self) -> None:
        project_cfg = {"id": "fleet", "review": {"enabled": True, "required_before_queue_advance": True}}
        decision = {
            "lane": "groundwork",
            "required_reviewer_lane": "review_light",
            "task_meta": {"acceptance_level": "verified", "signoff_requirements": []},
        }

        self.assertTrue(self.controller.decision_requires_serial_review(project_cfg, decision))

    def test_groundwork_review_loop_escalates_to_core_after_jury_round_limit(self) -> None:
        slice_item = {
            "title": "align workflow state machine",
            "workflow_kind": "groundwork_review_loop",
            "allowed_lanes": ["groundwork", "easy", "repair", "core"],
            "core_rescue_after_round": 3,
        }
        lane_snapshot = {"state": "ready", "providers": []}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(self.controller, "pull_request_row", return_value={"review_status": "review_fix_required", "local_review_attempts": 3, "review_focus": ""}):
                    with mock.patch.object(
                        self.controller,
                        "ea_lane_capacity_snapshot",
                        return_value={
                            "easy": lane_snapshot,
                            "repair": lane_snapshot,
                            "groundwork": lane_snapshot,
                            "core": lane_snapshot,
                            "survival": lane_snapshot,
                        },
                    ):
                        decision = self.controller.classify_tier({"lanes": {}}, {"id": "fleet"}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["lane"], "core")
        self.assertEqual(decision["task_meta"]["review_round"], 3)
        self.assertTrue(decision["task_meta"]["first_review_complete"])

    def test_persisted_review_runtime_status_uses_groundwork_loop_pending_stages(self) -> None:
        with mock.patch.object(
            self.controller,
            "pull_request_row",
            return_value={
                "workflow_kind": "groundwork_review_loop",
                "review_status": "local_review",
                "review_round": 0,
                "local_review_attempts": 0,
                "review_focus": "reviewer_lane=review_light ; final_reviewer_lane=jury ; jury_acceptance_required=true",
            },
        ):
            status = self.controller.persisted_review_runtime_status("fleet")

        self.assertEqual(status, "awaiting_first_review")

    def test_persisted_review_runtime_status_uses_review_light_pending_after_first_pass(self) -> None:
        with mock.patch.object(
            self.controller,
            "pull_request_row",
            return_value={
                "workflow_kind": "groundwork_review_loop",
                "review_status": "local_review",
                "review_round": 1,
                "local_review_attempts": 1,
                "first_review_complete_at": "2026-03-17T10:00:00+00:00",
                "review_focus": "reviewer_lane=review_light ; final_reviewer_lane=jury ; jury_acceptance_required=true",
            },
        ):
            status = self.controller.persisted_review_runtime_status("fleet")

        self.assertEqual(status, "review_light_pending")

    def test_persisted_review_runtime_status_uses_jury_pending_for_final_signoff(self) -> None:
        with mock.patch.object(
            self.controller,
            "pull_request_row",
            return_value={
                "workflow_kind": "groundwork_review_loop",
                "review_status": "local_review",
                "review_round": 1,
                "local_review_attempts": 1,
                "first_review_complete_at": "2026-03-17T10:00:00+00:00",
                "review_focus": "reviewer_lane=jury ; final_reviewer_lane=jury ; jury_acceptance_required=true",
            },
        ):
            status = self.controller.persisted_review_runtime_status("fleet")

        self.assertEqual(status, "jury_review_pending")

    def test_core_dispatch_uses_final_reviewer_without_incrementing_round(self) -> None:
        task_meta = {
            "workflow_kind": "groundwork_review_loop",
            "required_reviewer_lane": "review_light",
            "final_reviewer_lane": "jury",
            "review_round": 3,
            "core_rescue_after_round": 3,
            "jury_acceptance_required": True,
        }

        reviewer_lane = self.controller.reviewer_lane_for_dispatch(task_meta, execution_lane="core")
        review_round = self.controller.review_round_for_dispatch(task_meta, execution_lane="core")

        self.assertEqual(reviewer_lane, "jury")
        self.assertEqual(review_round, 3)

    def test_persisted_review_runtime_status_uses_core_rescue_stage(self) -> None:
        with mock.patch.object(
            self.controller,
            "pull_request_row",
            return_value={
                "workflow_kind": "groundwork_review_loop",
                "review_status": "review_fix_required",
                "review_round": 3,
                "local_review_attempts": 3,
                "needs_core_rescue": 1,
            },
        ):
            status = self.controller.persisted_review_runtime_status("fleet")

        self.assertEqual(status, "core_rescue_pending")

    def test_choose_review_account_alias_selects_review_light_lane(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.controller.DB_PATH = Path(tmpdir) / "fleet.db"
            self.controller.LOG_DIR = Path(tmpdir) / "logs"
            self.controller.CODEX_HOME_ROOT = Path(tmpdir) / "homes"
            self.controller.GROUP_ROOT = Path(tmpdir) / "groups"
            self.controller.init_db()
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                    VALUES(?, 'api_key', '[]', 1, 'ready', ?)
                    """,
                    ("acct-ea-review-light", now),
                )
            alias = self.controller.choose_review_account_alias(
                {
                    "accounts": {
                        "acct-ea-review-light": {
                            "lane": "review_light",
                            "codex_model_aliases": ["ea-review-light"],
                        }
                    }
                },
                {
                    "accounts": ["acct-ea-review-light"],
                    "account_policy": {"preferred_accounts": ["acct-ea-review-light"]},
                },
                reviewer_lane="review_light",
            )

        self.assertEqual(alias, "acct-ea-review-light")

    def test_ea_codex_profiles_falls_back_to_persisted_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.controller.DB_PATH = Path(tmpdir) / "fleet.db"
            self.controller.LOG_DIR = Path(tmpdir) / "logs"
            self.controller.CODEX_HOME_ROOT = Path(tmpdir) / "homes"
            self.controller.GROUP_ROOT = Path(tmpdir) / "groups"
            self.controller.init_db()
            self.controller._EA_PROFILE_CACHE = {"fetched_at": 0.0, "payload": {}}
            persisted = {"profiles": [{"profile": "review_light", "model": "ea-review-light"}]}
            self.controller.save_runtime_cache(self.controller.RUNTIME_CACHE_KEY_EA_CODEX_PROFILES, persisted)

            with mock.patch("urllib.request.urlopen", side_effect=OSError("ea-down")):
                payload = self.controller.ea_codex_profiles(force=True)

        self.assertEqual(payload["profiles"][0]["profile"], "review_light")


if __name__ == "__main__":
    unittest.main()
