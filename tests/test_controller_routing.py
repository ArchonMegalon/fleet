from __future__ import annotations

import asyncio
import importlib.util
import json
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

    def _ready_lane_capacity(self) -> dict[str, dict[str, object]]:
        lane_snapshot = {"state": "ready", "providers": []}
        return {
            "easy": lane_snapshot,
            "repair": lane_snapshot,
            "groundwork": lane_snapshot,
            "review_light": lane_snapshot,
            "core": lane_snapshot,
            "jury": lane_snapshot,
            "survival": lane_snapshot,
        }

    def _configure_groundwork_loop_fixture(self) -> tuple[Path, dict[str, object], dict[str, object], dict[str, object]]:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        repo_root = root / "repo"
        repo_root.mkdir()

        self.controller.DB_PATH = root / "fleet.db"
        self.controller.LOG_DIR = root / "logs"
        self.controller.CODEX_HOME_ROOT = root / "homes"
        self.controller.GROUP_ROOT = root / "groups"
        self.controller.init_db()

        config: dict[str, object] = {
            "lanes": {
                "easy": {"id": "easy", "runtime_model": "ea-easy"},
                "repair": {"id": "repair", "runtime_model": "ea-coder-hard"},
                "groundwork": {"id": "groundwork", "runtime_model": "ea-groundwork-gemini"},
                "review_light": {"id": "review_light", "runtime_model": "ea-review-light"},
                "core": {"id": "core", "runtime_model": "ea-coder-hard"},
                "jury": {"id": "jury", "runtime_model": "ea-audit-jury"},
                "survival": {"id": "survival", "runtime_model": "ea-survival"},
            },
            "accounts": {
                "acct-ea-review-light": {
                    "lane": "review_light",
                    "auth_kind": "api_key",
                    "codex_model_aliases": ["ea-review-light"],
                },
                "acct-ea-audit-jury": {
                    "lane": "jury",
                    "auth_kind": "api_key",
                    "codex_model_aliases": ["ea-audit-jury"],
                },
            },
        }
        project_cfg: dict[str, object] = {
            "id": "fleet",
            "path": str(repo_root),
            "feedback_dir": "feedback",
            "accounts": ["acct-ea-review-light", "acct-ea-audit-jury"],
            "account_policy": {
                "preferred_accounts": ["acct-ea-review-light", "acct-ea-audit-jury"],
            },
            "review": {
                "enabled": True,
                "mode": "local",
                "trigger": "local",
                "required_before_queue_advance": True,
                "focus_template": "for regressions and missing tests",
                "base_branch": "main",
            },
        }
        slice_item: dict[str, object] = {
            "title": "Align cheap-loop orchestration across controller states",
            "workflow_kind": "groundwork_review_loop",
            "required_reviewer_lane": "review_light",
            "final_reviewer_lane": "jury",
            "jury_acceptance_required": True,
            "max_review_rounds": 3,
            "core_rescue_after_round": 3,
            "allowed_lanes": ["groundwork", "easy", "repair", "core"],
        }

        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            for alias in ("acct-ea-review-light", "acct-ea-audit-jury"):
                conn.execute(
                    """
                    INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                    VALUES(?, 'api_key', '[]', 1, 'ready', ?)
                    """,
                    (alias, now),
                )
            conn.execute(
                """
                INSERT INTO projects(
                    id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                    consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                    last_error, spider_tier, spider_model, spider_reason, updated_at
                )
                VALUES(?, ?, '', '', ?, '', ?, 0, 0, 'dispatch_pending', ?, NULL, NULL, NULL, '', '', '', '', ?)
                """,
                (
                    "fleet",
                    str(repo_root),
                    "feedback",
                    json.dumps([slice_item]),
                    str(slice_item["title"]),
                    now,
                ),
            )

        return repo_root, config, project_cfg, slice_item

    def _upsert_loop_review_request(
        self,
        config: dict[str, object],
        project_cfg: dict[str, object],
        slice_name: str,
        task_meta: dict[str, object],
        *,
        execution_lane: str,
    ) -> dict[str, object]:
        review_round = self.controller.review_round_for_dispatch(task_meta, execution_lane=execution_lane)
        reviewer_lane = self.controller.reviewer_lane_for_dispatch(task_meta, execution_lane=execution_lane)
        reviewer_model = self.controller.reviewer_runtime_model_for_lane(config.get("lanes") or {}, reviewer_lane)
        review_focus = self.controller.encode_review_focus(
            self.controller.review_focus_text(project_cfg, slice_name),
            reviewer_lane=reviewer_lane,
            reviewer_model=reviewer_model,
            metadata={
                **self.controller.review_focus_metadata({**task_meta, "review_round": review_round}, slice_name=slice_name),
                "review_round": str(review_round),
                "review_packet": json.dumps({}, sort_keys=True),
            },
        )
        lane_burn = {
            execution_lane: {
                "estimated_cost_usd": 0.0,
                "runs": 1,
            }
        }
        return self.controller.upsert_local_review_request(
            project_cfg,
            slice_name=slice_name,
            requested_at=self.controller.utc_now(),
            review_focus=review_focus,
            workflow_state={
                "workflow_kind": str(task_meta.get("workflow_kind") or "default"),
                "review_round": review_round,
                "max_review_rounds": int(task_meta.get("max_review_rounds") or 0),
                "groundwork_time_ms": 1000 if execution_lane == "groundwork" else 0,
                "core_time_ms": 1000 if execution_lane == "core" else 0,
                "allowance_burn_by_lane": lane_burn,
            },
        )

    def _run_local_review(
        self,
        config: dict[str, object],
        project_cfg: dict[str, object],
        *,
        parse_result: dict[str, object],
        reason: str,
    ) -> None:
        with self.controller.db() as conn:
            project_row = conn.execute("SELECT * FROM projects WHERE id=?", ("fleet",)).fetchone()
        pr_row = self.controller.pull_request_row("fleet")
        self.assertIsNotNone(project_row)
        self.assertIsNotNone(pr_row)

        async def fake_run_command(*_args, **_kwargs):
            return self.controller.CommandResult(exit_code=0)

        with mock.patch.object(self.controller, "prepare_account_environment", return_value={}):
            with mock.patch.object(self.controller, "run_command", side_effect=fake_run_command):
                with mock.patch.object(self.controller, "parse_local_review_result", return_value=parse_result):
                    asyncio.run(
                        self.controller.execute_local_review_fallback(
                            config,
                            project_cfg,
                            project_row,
                            pr_row,
                            reason=reason,
                        )
                    )

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

    def test_groundwork_review_loop_local_fallback_runs_rework_core_rescue_and_final_jury(self) -> None:
        _repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        lane_capacity = self._ready_lane_capacity()
        project_row = {"consecutive_failures": 0}
        slice_name = str(slice_item["title"])

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value=lane_capacity):
                    first_decision = self.controller.classify_tier(config, project_cfg, project_row, slice_item, [])

        self.assertEqual(first_decision["lane"], "groundwork")
        first_pr = self._upsert_loop_review_request(
            config,
            project_cfg,
            slice_name,
            dict(first_decision["task_meta"]),
            execution_lane="groundwork",
        )
        self.assertEqual(first_pr["review_round"], 1)
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "awaiting_first_review")

        self._run_local_review(
            config,
            project_cfg,
            parse_result={
                "verdict": "reject",
                "summary": "State handoff is still incomplete.",
                "findings": [
                    {
                        "external_id": "ISSUE-STATE",
                        "blocking": True,
                        "body": "Persist the loop state before allowing another pass.",
                        "severity": "high",
                    }
                ],
                "blocking_issues": ["Persist the loop state before allowing another pass."],
                "non_blocking_issues": [],
                "repeat_issue_ids": [],
                "confidence": "high",
                "core_rescue_recommended": False,
            },
            reason="review-light round 1",
        )

        round1_pr = self.controller.pull_request_row("fleet")
        self.assertEqual(round1_pr["review_status"], "jury_rework_required")
        self.assertEqual(round1_pr["review_round"], 1)
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "jury_rework_required")
        self.assertTrue(round1_pr["first_review_complete_at"])
        self.assertFalse(round1_pr["needs_core_rescue"])

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value=lane_capacity):
                    rework_decision = self.controller.classify_tier(config, project_cfg, project_row, slice_item, [])

        self.assertEqual(rework_decision["lane"], "groundwork")
        self.assertEqual(
            self.controller.reviewer_lane_for_dispatch(rework_decision["task_meta"], execution_lane="groundwork"),
            "review_light",
        )
        self.assertEqual(
            self.controller.review_round_for_dispatch(rework_decision["task_meta"], execution_lane="groundwork"),
            2,
        )

        second_pr = self._upsert_loop_review_request(
            config,
            project_cfg,
            slice_name,
            dict(rework_decision["task_meta"]),
            execution_lane="groundwork",
        )
        self.assertEqual(second_pr["review_round"], 2)
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "review_light_pending")

        self._run_local_review(
            config,
            project_cfg,
            parse_result={
                "verdict": "core_rescue_required",
                "summary": "The remaining issues need a core-authority rescue pass.",
                "findings": [
                    {
                        "external_id": "ISSUE-CORE",
                        "blocking": True,
                        "body": "Cross-lane rescue is required to finish the loop safely.",
                        "severity": "high",
                    }
                ],
                "blocking_issues": ["Cross-lane rescue is required to finish the loop safely."],
                "non_blocking_issues": [],
                "repeat_issue_ids": ["ISSUE-STATE"],
                "confidence": "high",
                "core_rescue_recommended": True,
            },
            reason="review-light round 2",
        )

        rescue_pr = self.controller.pull_request_row("fleet")
        self.assertEqual(rescue_pr["review_status"], "core_rescue_pending")
        self.assertEqual(rescue_pr["review_round"], 2)
        self.assertTrue(rescue_pr["needs_core_rescue"])
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "core_rescue_pending")

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value=lane_capacity):
                    core_decision = self.controller.classify_tier(config, project_cfg, project_row, slice_item, [])

        self.assertEqual(core_decision["lane"], "core")
        self.assertEqual(
            self.controller.reviewer_lane_for_dispatch(core_decision["task_meta"], execution_lane="core"),
            "jury",
        )
        self.assertEqual(
            self.controller.review_round_for_dispatch(core_decision["task_meta"], execution_lane="core"),
            2,
        )

        final_pr = self._upsert_loop_review_request(
            config,
            project_cfg,
            slice_name,
            dict(core_decision["task_meta"]),
            execution_lane="core",
        )
        self.assertEqual(final_pr["review_round"], 2)
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "jury_review_pending")

        self._run_local_review(
            config,
            project_cfg,
            parse_result={
                "verdict": "accept",
                "summary": "Core rescue resolved the blocking issues.",
                "findings": [],
                "blocking_issues": [],
                "non_blocking_issues": [],
                "repeat_issue_ids": [],
                "confidence": "high",
                "core_rescue_recommended": False,
            },
            reason="jury final",
        )

        accepted_pr = self.controller.pull_request_row("fleet")
        self.assertEqual(accepted_pr["review_status"], "fallback_clean")
        self.assertEqual(accepted_pr["accepted_on_round"], "core")
        self.assertFalse(accepted_pr["needs_core_rescue"])
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "accepted_after_core")

        history = json.loads(accepted_pr["jury_feedback_history_json"])
        self.assertEqual([item["reviewer_lane"] for item in history], ["review_light", "review_light", "jury"])
        self.assertEqual(history[-1]["verdict"], "accept")
        self.assertEqual(json.loads(accepted_pr["blocking_issue_count_by_round_json"]), [1, 1])
        self.assertEqual(json.loads(accepted_pr["repeat_issue_count_by_round_json"]), [0, 1])
        self.assertEqual(
            json.loads(accepted_pr["issue_fingerprints_json"]),
            ["ISSUE-STATE", "ISSUE-CORE"],
        )
        self.assertEqual(json.loads(accepted_pr["last_review_feedback_json"])["reviewer_lane"], "jury")

        allowance_burn = json.loads(accepted_pr["allowance_burn_by_lane_json"])
        self.assertEqual(allowance_burn["review_light"]["runs"], 2)
        self.assertEqual(allowance_burn["jury"]["runs"], 1)

        with self.controller.db() as conn:
            project = conn.execute("SELECT status, queue_index, current_slice FROM projects WHERE id=?", ("fleet",)).fetchone()
            review_runs = conn.execute(
                "SELECT status FROM runs WHERE project_id=? AND job_kind='local_review' ORDER BY id",
                ("fleet",),
            ).fetchall()

        self.assertEqual(project["status"], "complete")
        self.assertEqual(project["queue_index"], 1)
        self.assertIsNone(project["current_slice"])
        self.assertEqual([row["status"] for row in review_runs], ["jury_rework_required", "core_rescue_pending", "accepted_after_core"])

    def test_groundwork_review_loop_local_fallback_accepts_on_review_light_then_jury_final(self) -> None:
        _repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        lane_capacity = self._ready_lane_capacity()
        project_row = {"consecutive_failures": 0}
        slice_name = str(slice_item["title"])

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value=lane_capacity):
                    first_decision = self.controller.classify_tier(config, project_cfg, project_row, slice_item, [])

        self.assertEqual(first_decision["lane"], "groundwork")
        first_pr = self._upsert_loop_review_request(
            config,
            project_cfg,
            slice_name,
            dict(first_decision["task_meta"]),
            execution_lane="groundwork",
        )
        self.assertEqual(first_pr["review_round"], 1)
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "awaiting_first_review")

        self._run_local_review(
            config,
            project_cfg,
            parse_result={
                "verdict": "reject",
                "summary": "Loop metadata is still incomplete.",
                "findings": [
                    {
                        "external_id": "ISSUE-METADATA",
                        "blocking": True,
                        "body": "Persist the round metadata before letting the slice advance.",
                        "severity": "high",
                    }
                ],
                "blocking_issues": ["Persist the round metadata before letting the slice advance."],
                "non_blocking_issues": [],
                "repeat_issue_ids": [],
                "confidence": "high",
                "core_rescue_recommended": False,
            },
            reason="review-light round 1",
        )

        round1_pr = self.controller.pull_request_row("fleet")
        self.assertEqual(round1_pr["review_status"], "jury_rework_required")
        self.assertEqual(round1_pr["review_round"], 1)
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "jury_rework_required")

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value=lane_capacity):
                    rework_decision = self.controller.classify_tier(config, project_cfg, project_row, slice_item, [])

        self.assertEqual(rework_decision["lane"], "groundwork")
        self.assertEqual(
            self.controller.reviewer_lane_for_dispatch(rework_decision["task_meta"], execution_lane="groundwork"),
            "review_light",
        )
        self.assertEqual(
            self.controller.review_round_for_dispatch(rework_decision["task_meta"], execution_lane="groundwork"),
            2,
        )

        second_pr = self._upsert_loop_review_request(
            config,
            project_cfg,
            slice_name,
            dict(rework_decision["task_meta"]),
            execution_lane="groundwork",
        )
        self.assertEqual(second_pr["review_round"], 2)
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "review_light_pending")

        self._run_local_review(
            config,
            project_cfg,
            parse_result={
                "verdict": "accept",
                "summary": "The rework fixed the cheap-loop issues.",
                "findings": [],
                "blocking_issues": [],
                "non_blocking_issues": [],
                "repeat_issue_ids": [],
                "confidence": "high",
                "core_rescue_recommended": False,
            },
            reason="review-light round 2",
        )

        accepted_pr = self.controller.pull_request_row("fleet")
        self.assertEqual(accepted_pr["review_status"], "fallback_clean")
        self.assertEqual(accepted_pr["accepted_on_round"], "2")
        self.assertFalse(accepted_pr["needs_core_rescue"])
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "accepted_after_r2")

        history = json.loads(accepted_pr["jury_feedback_history_json"])
        self.assertEqual([item["reviewer_lane"] for item in history], ["review_light", "review_light", "jury"])
        self.assertEqual([item["verdict"] for item in history], ["reject", "accept", "accept"])
        self.assertEqual(history[-1]["summary"], "The rework fixed the cheap-loop issues.")
        self.assertEqual(json.loads(accepted_pr["blocking_issue_count_by_round_json"]), [1, 0])
        self.assertEqual(json.loads(accepted_pr["repeat_issue_count_by_round_json"]), [0, 0])
        self.assertEqual(json.loads(accepted_pr["issue_fingerprints_json"]), ["ISSUE-METADATA"])
        self.assertEqual(json.loads(accepted_pr["last_review_feedback_json"])["reviewer_lane"], "jury")

        allowance_burn = json.loads(accepted_pr["allowance_burn_by_lane_json"])
        self.assertEqual(allowance_burn["review_light"]["runs"], 2)
        self.assertEqual(allowance_burn["jury"]["runs"], 1)

        with self.controller.db() as conn:
            project = conn.execute("SELECT status, queue_index, current_slice FROM projects WHERE id=?", ("fleet",)).fetchone()
            review_runs = conn.execute(
                "SELECT status FROM runs WHERE project_id=? AND job_kind='local_review' ORDER BY id",
                ("fleet",),
            ).fetchall()

        self.assertEqual(project["status"], "complete")
        self.assertEqual(project["queue_index"], 1)
        self.assertIsNone(project["current_slice"])
        self.assertEqual([row["status"] for row in review_runs], ["jury_rework_required", "jury_review_pending", "accepted_after_r2"])

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
