from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
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
                "acct-ea-groundwork": {
                    "lane": "groundwork",
                    "auth_kind": "api_key",
                    "codex_model_aliases": ["ea-groundwork-gemini"],
                },
                "acct-ea-groundwork-2": {
                    "lane": "groundwork",
                    "auth_kind": "api_key",
                    "codex_model_aliases": ["ea-groundwork-gemini"],
                },
                "acct-ea-review-light": {
                    "lane": "review_light",
                    "auth_kind": "api_key",
                    "codex_model_aliases": ["ea-review-light"],
                },
                "acct-ea-core": {
                    "lane": "core",
                    "auth_kind": "api_key",
                    "codex_model_aliases": ["ea-coder-hard"],
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
            "accounts": ["acct-ea-groundwork", "acct-ea-groundwork-2", "acct-ea-audit-jury", "acct-ea-core"],
            "account_policy": {
                "preferred_accounts": ["acct-ea-groundwork"],
                "burst_accounts": ["acct-ea-groundwork-2"],
                "reserve_accounts": ["acct-ea-audit-jury", "acct-ea-core"],
            },
            "worker_topology": {
                "groundwork_primary": "acct-ea-groundwork",
                "groundwork_shadow": "acct-ea-groundwork-2",
                "jury_reviewer": "acct-ea-audit-jury",
                "core_rescue": "acct-ea-core",
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
            "required_reviewer_lane": "jury",
            "final_reviewer_lane": "jury",
            "landing_lane": "jury",
            "jury_acceptance_required": True,
            "max_review_rounds": 3,
            "allow_credit_burn": True,
            "allow_paid_fast_lane": True,
            "allow_core_rescue": True,
            "core_rescue_after_round": 3,
            "allowed_lanes": ["groundwork", "easy", "repair", "core"],
        }

        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            for alias in ("acct-ea-groundwork", "acct-ea-groundwork-2", "acct-ea-audit-jury", "acct-ea-core"):
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
        landing_result: dict[str, object] | None = None,
    ) -> None:
        with self.controller.db() as conn:
            project_row = conn.execute("SELECT * FROM projects WHERE id=?", ("fleet",)).fetchone()
        pr_row = self.controller.pull_request_row("fleet")
        self.assertIsNotNone(project_row)
        self.assertIsNotNone(pr_row)

        async def fake_run_command(*_args, **_kwargs):
            return self.controller.CommandResult(exit_code=0)

        async def fake_landing(*_args, **_kwargs):
            return landing_result or {
                "landing_lane": "jury",
                "landed_at": "2026-03-18T12:00:00Z",
                "landed_sha": "deadbeef",
                "landing_error": "",
            }

        with mock.patch.object(self.controller, "prepare_account_environment", return_value={}):
            with mock.patch.object(self.controller, "run_command", side_effect=fake_run_command):
                with mock.patch.object(self.controller, "parse_local_review_result", return_value=parse_result):
                    with mock.patch.object(self.controller, "land_reviewed_worktree_to_base_branch", side_effect=fake_landing):
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
        slice_item = {"title": "patch queue retry handling", "allow_paid_fast_lane": True}
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

    def test_api_key_backoff_stays_scoped_to_single_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                for alias in ("acct-ea-core", "acct-ea-repair"):
                    conn.execute(
                        """
                        INSERT INTO accounts(
                            alias, auth_kind, api_key_env, allowed_models_json, max_parallel_runs, health_state, updated_at
                        )
                        VALUES(?, 'api_key', 'OPENAI_API_KEY', '[]', 1, 'ready', ?)
                        """,
                        (alias, now),
                    )

            until = self.controller.utc_now() + self.controller.dt.timedelta(minutes=15)
            self.controller.set_account_backoff("acct-ea-core", until, "core cooled")

            with self.controller.db() as conn:
                core_row = conn.execute("SELECT backoff_until, last_error FROM accounts WHERE alias='acct-ea-core'").fetchone()
                repair_row = conn.execute("SELECT backoff_until, last_error FROM accounts WHERE alias='acct-ea-repair'").fetchone()

        self.assertEqual(core_row["backoff_until"], self.controller.iso(until))
        self.assertEqual(core_row["last_error"], "core cooled")
        self.assertIsNone(repair_row["backoff_until"])
        self.assertIsNone(repair_row["last_error"])

    def test_high_risk_fleet_groundwork_loop_stays_cheap_by_default(self) -> None:
        slice_item = {
            "title": "persist survival lane queue state and cache state in durable storage instead of process-local memory",
            "difficulty": "hard",
            "risk_level": "high",
            "workflow_kind": "groundwork_review_loop",
            "allowed_lanes": ["groundwork", "repair", "easy"],
            "required_reviewer_lane": "jury",
            "final_reviewer_lane": "jury",
            "jury_acceptance_required": True,
            "max_review_rounds": 3,
            "core_rescue_after_round": 3,
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
                    decision = self.controller.classify_tier({"lanes": {}}, {"id": "fleet"}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["tier"], "multi_file_impl")
        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["lane_submode"], "responses_groundwork")
        self.assertEqual(decision["required_reviewer_lane"], "jury")
        self.assertEqual(decision["final_reviewer_lane"], "jury")

    def test_groundwork_capacity_shifts_to_easy_before_repair(self) -> None:
        slice_item = {
            "title": "persist survival lane queue state and cache state in durable storage instead of process-local memory",
            "difficulty": "hard",
            "risk_level": "high",
            "workflow_kind": "groundwork_review_loop",
            "allowed_lanes": ["groundwork", "repair", "easy"],
        }

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": {"state": "ready", "providers": []},
                        "repair": {"state": "ready", "providers": []},
                        "groundwork": {"state": "cooldown", "providers": []},
                        "core": {"state": "ready", "providers": []},
                        "survival": {"state": "ready", "providers": []},
                    },
                ):
                    decision = self.controller.classify_tier({"lanes": {}}, {"id": "fleet"}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["lane"], "easy")
        self.assertEqual(decision["lane_submode"], "mcp")
        self.assertEqual(decision["escalation_reason"], "groundwork_capacity_shifted_to_easy")

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
            "required_reviewer_lane": "jury",
            "task_meta": {"acceptance_level": "verified", "signoff_requirements": []},
        }

        self.assertTrue(self.controller.decision_requires_serial_review(project_cfg, decision))

    def test_groundwork_review_loop_requires_explicit_core_rescue_after_jury_round_limit(self) -> None:
        slice_item = {
            "title": "align workflow state machine",
            "workflow_kind": "groundwork_review_loop",
            "allowed_lanes": ["groundwork", "easy", "repair", "core"],
            "allow_credit_burn": True,
            "allow_paid_fast_lane": True,
            "allow_core_rescue": True,
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

        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["task_meta"]["review_round"], 3)
        self.assertTrue(decision["task_meta"]["first_review_complete"])

    def test_groundwork_review_loop_default_policy_suppresses_core_rescue(self) -> None:
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

        self.assertNotEqual(decision["lane"], "core")
        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["task_meta"]["core_rescue_after_round"], 0)

    def test_groundwork_review_loop_zero_credit_policy_blocks_core_rescue_explicitly(self) -> None:
        _repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        lane_capacity = self._ready_lane_capacity()
        project_row = {"consecutive_failures": 0}
        slice_name = str(slice_item["title"])

        slice_item["allow_credit_burn"] = False
        slice_item["allow_core_rescue"] = False
        slice_item["core_rescue_after_round"] = 0
        slice_item["allowed_lanes"] = ["groundwork", "easy"]

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value=lane_capacity):
                    decision = self.controller.classify_tier(config, project_cfg, project_row, slice_item, [])

        first_pr = self._upsert_loop_review_request(
            config,
            project_cfg,
            slice_name,
            dict(decision["task_meta"]),
            execution_lane="groundwork",
        )
        self.assertEqual(first_pr["review_round"], 1)

        self._run_local_review(
            config,
            project_cfg,
            parse_result={
                "verdict": "core_rescue_required",
                "summary": "A core pass would be needed, but this slice is zero-credit only.",
                "findings": [
                    {
                        "external_id": "ISSUE-ZERO-CREDIT",
                        "blocking": True,
                        "body": "Core rescue would exceed the task credit policy.",
                        "severity": "high",
                    }
                ],
                "blocking_issues": ["Core rescue would exceed the task credit policy."],
                "non_blocking_issues": [],
                "repeat_issue_ids": [],
                "confidence": "high",
                "core_rescue_recommended": True,
            },
            reason="jury round 1",
        )

        blocked_pr = self.controller.pull_request_row("fleet")
        self.assertEqual(blocked_pr["review_status"], "blocked_credit_burn_disabled")
        self.assertFalse(blocked_pr["needs_core_rescue"])
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "blocked_credit_burn_disabled")

        with self.controller.db() as conn:
            project = conn.execute("SELECT status, queue_index, current_slice, last_error FROM projects WHERE id=?", ("fleet",)).fetchone()

        self.assertEqual(project["status"], "blocked_credit_burn_disabled")
        self.assertEqual(project["queue_index"], 0)
        self.assertEqual(project["current_slice"], self.controller.normalize_slice_text(slice_item))
        self.assertIn("credit burn is disabled", project["last_error"])

    def test_gemini_backend_unavailable_unlocks_repair_fallback(self) -> None:
        slice_item = {
            "title": "persist survival lane queue state and cache state in durable storage instead of process-local memory",
            "difficulty": "hard",
            "risk_level": "high",
            "workflow_kind": "groundwork_review_loop",
            "allowed_lanes": ["groundwork", "easy"],
            "allow_paid_fast_lane": True,
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
                    decision = self.controller.classify_tier(
                        {"lanes": {}},
                        {"id": "fleet"},
                        {"consecutive_failures": 0, "last_error": "backend unavailable: gemini_vortex:gemini_vortex_cli_missing"},
                        slice_item,
                        [],
                    )

        self.assertEqual(decision["lane"], "repair")
        self.assertEqual(decision["escalation_reason"], "gemini_backend_unavailable_paid_fallback")
        self.assertIn("repair", decision["allowed_lanes"])

    def test_zero_credit_gemini_unavailable_does_not_unlock_repair_fallback(self) -> None:
        slice_item = {
            "title": "persist survival lane queue state and cache state in durable storage instead of process-local memory",
            "difficulty": "hard",
            "risk_level": "high",
            "workflow_kind": "groundwork_review_loop",
            "allowed_lanes": ["groundwork", "easy"],
            "allow_paid_fast_lane": False,
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
                    decision = self.controller.classify_tier(
                        {"lanes": {}},
                        {"id": "fleet"},
                        {"consecutive_failures": 0, "last_error": "backend unavailable: gemini_vortex:gemini_vortex_cli_missing"},
                        slice_item,
                        [],
                    )

        self.assertNotEqual(decision["lane"], "repair")
        self.assertNotEqual(decision["escalation_reason"], "gemini_backend_unavailable_paid_fallback")
        self.assertNotIn("repair", decision["allowed_lanes"])

    def test_recent_gemini_account_failure_keeps_repair_fallback_unlocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            now = self.controller.utc_now()
            now_iso = self.controller.iso(now)
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, api_key_env, allowed_models_json, max_parallel_runs, backoff_until,
                        last_error, updated_at, last_model_failure_at, health_state
                    )
                    VALUES(?, 'api_key', 'EA_API_TOKEN', '[]', 1, ?, ?, ?, ?, 'ready')
                    """,
                    (
                        "acct-ea-groundwork",
                        self.controller.iso(now + self.controller.dt.timedelta(minutes=2)),
                        "backend unavailable: gemini_vortex:gemini_vortex_cli_missing",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, api_key_env, allowed_models_json, max_parallel_runs, updated_at, health_state
                    )
                    VALUES(?, 'api_key', 'EA_API_TOKEN', '[]', 1, ?, 'ready')
                    """,
                    ("acct-ea-repair", now_iso),
                )

            slice_item = {
                "title": "persist survival lane queue state and cache state in durable storage instead of process-local memory",
                "difficulty": "hard",
                "risk_level": "high",
                "workflow_kind": "groundwork_review_loop",
                "allowed_lanes": ["groundwork", "easy"],
                "allow_paid_fast_lane": True,
            }
            lane_snapshot = {"state": "ready", "providers": []}
            config = {
                "lanes": {},
                "accounts": {
                    "acct-ea-groundwork": {"lane": "groundwork"},
                    "acct-ea-repair": {"lane": "repair"},
                },
            }
            project_cfg = {
                "id": "fleet",
                "accounts": ["acct-ea-groundwork"],
                "account_policy": {"reserve_accounts": ["acct-ea-repair"]},
            }
            project_row = {
                "consecutive_failures": 0,
                "last_error": "no eligible account/model after auth, pool state, allowlist, or budget filtering",
            }

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
                        decision = self.controller.classify_tier(config, project_cfg, project_row, slice_item, [])

        self.assertEqual(decision["lane"], "repair")
        self.assertEqual(decision["escalation_reason"], "gemini_backend_unavailable_paid_fallback")

    def test_persisted_review_runtime_status_uses_groundwork_loop_pending_stages(self) -> None:
        with mock.patch.object(
            self.controller,
            "pull_request_row",
            return_value={
                "workflow_kind": "groundwork_review_loop",
                "review_status": "local_review",
                "review_round": 0,
                "local_review_attempts": 0,
                "review_focus": "reviewer_lane=jury ; final_reviewer_lane=jury ; jury_acceptance_required=true",
            },
        ):
            status = self.controller.persisted_review_runtime_status("fleet")

        self.assertEqual(status, "jury_review_pending")

    def test_persisted_review_runtime_status_uses_jury_pending_after_first_pass(self) -> None:
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
            "required_reviewer_lane": "jury",
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
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "jury_review_pending")

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
            reason="jury round 1",
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
            "jury",
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
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "jury_review_pending")

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
            reason="jury round 2",
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
        self.assertEqual(accepted_pr["landing_lane"], "jury")
        self.assertEqual(accepted_pr["landed_sha"], "deadbeef")
        self.assertTrue(accepted_pr["landed_at"])
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "accepted_after_core")

        history = json.loads(accepted_pr["jury_feedback_history_json"])
        self.assertEqual([item["reviewer_lane"] for item in history], ["jury", "jury", "jury"])
        self.assertEqual(history[-1]["verdict"], "accept")
        self.assertEqual(json.loads(accepted_pr["blocking_issue_count_by_round_json"]), [1, 1])
        self.assertEqual(json.loads(accepted_pr["repeat_issue_count_by_round_json"]), [0, 1])
        self.assertEqual(
            json.loads(accepted_pr["issue_fingerprints_json"]),
            ["ISSUE-STATE", "ISSUE-CORE"],
        )
        self.assertEqual(json.loads(accepted_pr["last_review_feedback_json"])["reviewer_lane"], "jury")

        allowance_burn = json.loads(accepted_pr["allowance_burn_by_lane_json"])
        self.assertEqual(allowance_burn["jury"]["runs"], 3)

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

    def test_groundwork_review_loop_local_fallback_accepts_on_jury_round_two(self) -> None:
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
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "jury_review_pending")

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
            reason="jury round 1",
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
            "jury",
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
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "jury_review_pending")

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
            reason="jury round 2",
        )

        accepted_pr = self.controller.pull_request_row("fleet")
        self.assertEqual(accepted_pr["review_status"], "fallback_clean")
        self.assertEqual(accepted_pr["accepted_on_round"], "2")
        self.assertFalse(accepted_pr["needs_core_rescue"])
        self.assertEqual(accepted_pr["landing_lane"], "jury")
        self.assertEqual(accepted_pr["landed_sha"], "deadbeef")
        self.assertTrue(accepted_pr["landed_at"])
        self.assertEqual(self.controller.persisted_review_runtime_status("fleet"), "accepted_after_r2")

        history = json.loads(accepted_pr["jury_feedback_history_json"])
        self.assertEqual([item["reviewer_lane"] for item in history], ["jury", "jury"])
        self.assertEqual([item["verdict"] for item in history], ["reject", "accept"])
        self.assertEqual(history[-1]["summary"], "The rework fixed the cheap-loop issues.")
        self.assertEqual(json.loads(accepted_pr["blocking_issue_count_by_round_json"]), [1, 0])
        self.assertEqual(json.loads(accepted_pr["repeat_issue_count_by_round_json"]), [0, 0])
        self.assertEqual(json.loads(accepted_pr["issue_fingerprints_json"]), ["ISSUE-METADATA"])
        self.assertEqual(json.loads(accepted_pr["last_review_feedback_json"])["reviewer_lane"], "jury")

        allowance_burn = json.loads(accepted_pr["allowance_burn_by_lane_json"])
        self.assertEqual(allowance_burn["jury"]["runs"], 2)

        with self.controller.db() as conn:
            project = conn.execute("SELECT status, queue_index, current_slice FROM projects WHERE id=?", ("fleet",)).fetchone()
            review_runs = conn.execute(
                "SELECT status FROM runs WHERE project_id=? AND job_kind='local_review' ORDER BY id",
                ("fleet",),
            ).fetchall()

        self.assertEqual(project["status"], "complete")
        self.assertEqual(project["queue_index"], 1)
        self.assertIsNone(project["current_slice"])
        self.assertEqual([row["status"] for row in review_runs], ["jury_rework_required", "accepted_after_r2"])

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

    def test_choose_review_account_alias_prefers_worker_topology_jury_lane(self) -> None:
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
                    ("acct-ea-audit-jury", now),
                )
            alias = self.controller.choose_review_account_alias(
                {
                    "accounts": {
                        "acct-ea-audit-jury": {
                            "lane": "jury",
                            "codex_model_aliases": ["ea-audit-jury"],
                        }
                    }
                },
                {
                    "accounts": ["acct-ea-audit-jury"],
                    "account_policy": {"preferred_accounts": ["acct-ea-audit-jury"]},
                    "worker_topology": {"jury_reviewer": "acct-ea-audit-jury"},
                },
                reviewer_lane="jury",
            )

        self.assertEqual(alias, "acct-ea-audit-jury")

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

    def test_write_landing_telemetry_artifacts_writes_latest_rollups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            tracked = repo_root / "worker.txt"
            tracked.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "worker.txt"], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            tracked.write_text("after\n", encoding="utf-8")

            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            finished_at = self.controller.utc_now()
            started_at = finished_at - self.controller.dt.timedelta(minutes=4)
            review_started = finished_at - self.controller.dt.timedelta(minutes=1)
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', '', '', '[]', 0, 0, 'complete', NULL, NULL, NULL, NULL, '', '', '', '', ?)
                    """,
                    (
                        "fleet",
                        str(repo_root),
                        self.controller.iso(finished_at),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        project_id, account_alias, job_kind, slice_name, status, model, started_at, finished_at
                    )
                    VALUES(?, ?, 'coding', ?, 'complete', ?, ?, ?)
                    """,
                    (
                        "fleet",
                        "acct-ea-groundwork-2",
                        "land telemetry slice",
                        "ea-groundwork-gemini",
                        self.controller.iso(started_at),
                        self.controller.iso(review_started),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        project_id, account_alias, job_kind, slice_name, status, model, started_at, finished_at
                    )
                    VALUES(?, ?, 'local_review', ?, 'accepted_after_r2', ?, ?, ?)
                    """,
                    (
                        "fleet",
                        "acct-ea-audit-jury",
                        "land telemetry slice",
                        "ea-audit-jury",
                        self.controller.iso(review_started),
                        self.controller.iso(finished_at),
                    ),
                )

            config = {
                "accounts": {
                    "acct-ea-groundwork-2": {"lane": "groundwork"},
                    "acct-ea-audit-jury": {"lane": "jury"},
                }
            }
            project_cfg = {
                "id": "fleet",
                "path": str(repo_root),
                "worker_topology": {
                    "groundwork_shadow": "acct-ea-groundwork-2",
                    "jury_reviewer": "acct-ea-audit-jury",
                },
            }

            result = self.controller.write_landing_telemetry_artifacts(
                config,
                project_cfg,
                slice_name="land telemetry slice",
                landing_lane="jury",
                telemetry_context={
                    "workflow_kind": "groundwork_review_loop",
                    "review_round": 2,
                    "accepted_on_round": "2",
                    "jury_feedback_history": [
                        {"reviewer_lane": "jury", "verdict": "reject", "reviewed_at": self.controller.iso(review_started)},
                        {"reviewer_lane": "jury", "verdict": "accept", "reviewed_at": self.controller.iso(finished_at)},
                    ],
                    "blocking_issue_counts": [1, 0],
                    "repeat_issue_counts": [0, 0],
                    "needs_core_rescue": False,
                    "core_rescue_reason": "",
                    "allow_credit_burn": False,
                    "allow_paid_fast_lane": False,
                    "groundwork_time_ms": 180000,
                    "jury_time_ms": 60000,
                    "core_time_ms": 0,
                    "issue_fingerprints": ["ISSUE-STATE"],
                },
                generated_at=finished_at,
            )

            artifact_path = Path(result["artifact_path"])
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            review_loop = json.loads((repo_root / "logs" / "telemetry" / "latest" / "review_loop.json").read_text(encoding="utf-8"))
            worker_utilization = json.loads((repo_root / "logs" / "telemetry" / "latest" / "worker_utilization.json").read_text(encoding="utf-8"))
            self.assertTrue(artifact_path.exists())
            self.assertTrue(payload["shadow_worker_used"])
            self.assertEqual(payload["accepted_on_round"], "2")
            self.assertEqual(review_loop["accepted_on_round_counts"]["2"], 1)
            self.assertEqual(review_loop["zero_credit_slices_landed"], 1)
            self.assertGreater(worker_utilization["groundwork_shadow_busy_percent"], 0.0)

    def test_build_prompt_truncates_large_feedback_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            feedback_dir = repo_root / "feedback"
            feedback_dir.mkdir()
            feedback_path = feedback_dir / "2026-03-18-big-audit.md"
            feedback_path.write_text("# Big audit\n" + ("A" * 12000), encoding="utf-8")

            project_cfg = {
                "id": "fleet",
                "path": str(repo_root),
                "feedback_dir": "feedback",
                "runner": {"always_continue": True, "avoid_permission_escalation": True},
            }
            decision = {
                "tier": "bounded_fix",
                "selected_model": "ea-coder-hard",
                "reasoning_effort": "medium",
                "reason": "test route",
            }

            prompt = self.controller.build_prompt(project_cfg, "test slice", decision, [feedback_path])
            estimated = self.controller.estimate_prompt_chars(project_cfg, "test slice", [feedback_path])

        self.assertIn("[truncated ", prompt)
        self.assertIn("2026-03-18-big-audit.md", prompt)
        self.assertLess(len(prompt), 10000)
        self.assertGreaterEqual(estimated, len(prompt))

    def test_exec_idle_timeout_tracks_ea_stream_idle_timeout(self) -> None:
        runner = {
            "config_overrides": [
                'model_providers.ea.stream_idle_timeout_ms=300000',
            ]
        }

        timeout = self.controller.effective_exec_idle_timeout_seconds({}, runner, 5400)

        self.assertEqual(timeout, 360)

    def test_exec_idle_timeout_prefers_explicit_runner_override(self) -> None:
        runner = {
            "exec_idle_timeout_seconds": 480,
            "config_overrides": [
                'model_providers.ea.stream_idle_timeout_ms=300000',
            ],
        }

        timeout = self.controller.effective_exec_idle_timeout_seconds({}, runner, 5400)

        self.assertEqual(timeout, 480)

    def test_project_restart_cooldown_prefers_runner_override(self) -> None:
        config = {"policies": {"restart_cooldown_seconds": 30}}
        project_cfg = {"runner": {"restart_cooldown_seconds": 5}}

        cooldown = self.controller.project_restart_cooldown_seconds(config, project_cfg)

        self.assertEqual(cooldown, 5)

    def test_reconcile_abandoned_runs_caps_recovery_failure_debt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', '', '', '[]', 0, 15, 'running', 'slice', 7, NULL, ?, '', '', '', '', ?)
                    """,
                    ("fleet", str(root), now, now),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at, job_kind
                    )
                    VALUES(7, 'fleet', 'acct-ea-core', 'slice', 'running', 'ea-coder-hard', ?, NULL, 'coding')
                    """,
                    (now,),
                )

            self.controller.reconcile_abandoned_runs({"policies": {"max_consecutive_failures": 3}})

            with self.controller.db() as conn:
                project = conn.execute("SELECT status, active_run_id, consecutive_failures FROM projects WHERE id='fleet'").fetchone()
                run = conn.execute("SELECT status, finished_at FROM runs WHERE id=7").fetchone()

        self.assertEqual(project["status"], self.controller.READY_STATUS)
        self.assertIsNone(project["active_run_id"])
        self.assertEqual(project["consecutive_failures"], 2)
        self.assertEqual(run["status"], "abandoned")
        self.assertTrue(run["finished_at"])

    def test_apply_exec_stalled_account_backoff_after_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            now = self.controller.utc_now()
            now_iso = self.controller.iso(now)
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES('fleet', ?, '', '', '', '', '[]', 0, 0, 'dispatch_pending', 'slice', NULL, NULL, ?, '', '', '', '', ?)
                    """,
                    (str(root), now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES('acct-ea-core', 'api_key', '[]', 1, 'ready', ?)
                    """,
                    (now_iso,),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at,
                        error_class, error_message, job_kind
                    )
                    VALUES(1, 'fleet', 'acct-ea-core', 'slice', 'failed', 'ea-coder-hard', ?, ?, 'stalled', 'old stall', 'coding')
                    """,
                    (
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=5)),
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=5) + self.controller.dt.timedelta(minutes=1)),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at,
                        error_class, error_message, job_kind
                    )
                    VALUES(2, 'fleet', 'acct-ea-core', 'slice', 'failed', 'ea-coder-hard', ?, ?, 'stalled', 'current stall', 'coding')
                    """,
                    (
                        self.controller.iso(now - self.controller.dt.timedelta(seconds=30)),
                        now_iso,
                    ),
                )

            result = self.controller.apply_exec_stalled_account_backoff(
                {"policies": {
                    "exec_stalled_account_backoff_threshold": 2,
                    "exec_stalled_account_backoff_window_seconds": 3600,
                    "exec_stalled_account_backoff_seconds": 900,
                }},
                alias="acct-ea-core",
                model="ea-coder-hard",
                finished_at=now,
                idle_timeout_seconds=360,
            )

            self.assertIsNotNone(result)
            until, message = result
            self.assertIn("acct-ea-core", message)
            self.assertIn("2 stalled ea-coder-hard runs", message)
            with self.controller.db() as conn:
                account = conn.execute("SELECT backoff_until, last_error FROM accounts WHERE alias='acct-ea-core'").fetchone()
            self.assertEqual(account["backoff_until"], self.controller.iso(until))
            self.assertEqual(account["last_error"], message)

    def test_apply_exec_stalled_account_backoff_prefers_project_runner_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            now = self.controller.utc_now()
            now_iso = self.controller.iso(now)
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES('fleet', ?, '', '', '', '', '[]', 0, 0, 'dispatch_pending', 'slice', NULL, NULL, ?, '', '', '', '', ?)
                    """,
                    (str(root), now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES('acct-ea-repair', 'api_key', '[]', 1, 'ready', ?)
                    """,
                    (now_iso,),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at,
                        error_class, error_message, job_kind
                    )
                    VALUES(1, 'fleet', 'acct-ea-repair', 'slice', 'failed', 'ea-coder-fast', ?, ?, 'stalled', 'old stall', 'coding')
                    """,
                    (
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=4)),
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=3)),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at,
                        error_class, error_message, job_kind
                    )
                    VALUES(2, 'fleet', 'acct-ea-repair', 'slice', 'failed', 'ea-coder-fast', ?, ?, 'stalled', 'current stall', 'coding')
                    """,
                    (
                        self.controller.iso(now - self.controller.dt.timedelta(seconds=15)),
                        now_iso,
                    ),
                )

            result = self.controller.apply_exec_stalled_account_backoff(
                {"policies": {"exec_stalled_account_backoff_seconds": 900}},
                alias="acct-ea-repair",
                model="ea-coder-fast",
                finished_at=now,
                idle_timeout_seconds=60,
                project_cfg={"runner": {"exec_stalled_account_backoff_seconds": 5}},
            )

            self.assertIsNotNone(result)
            until, _message = result
            self.assertEqual(int((until - now).total_seconds()), 5)

    def test_pick_account_and_model_uses_runtime_model_for_failure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            api_key_file = root / "api-key.txt"
            api_key_file.write_text("test-key\n", encoding="utf-8")
            now = self.controller.utc_now()
            now_iso = self.controller.iso(now)
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES('fleet', ?, '', '', '', '', '[]', 0, 0, 'dispatch_pending', 'slice', NULL, NULL, ?, '', '', '', '', ?)
                    """,
                    (str(root), now_iso, now_iso),
                )
                for alias in ("acct-bad", "acct-good"):
                    conn.execute(
                        """
                        INSERT INTO accounts(
                            alias, auth_kind, api_key_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                        )
                        VALUES(?, 'api_key', ?, ?, 1, 'ready', ?)
                        """,
                        (alias, str(api_key_file), json.dumps(["gpt-5-mini"]), now_iso),
                    )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at,
                        error_class, error_message, job_kind
                    )
                    VALUES(1, 'fleet', 'acct-bad', 'slice', 'failed', 'ea-coder-hard', ?, ?, 'stalled', 'stall 1', 'coding')
                    """,
                    (
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=20)),
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=19)),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at,
                        error_class, error_message, job_kind
                    )
                    VALUES(2, 'fleet', 'acct-bad', 'slice', 'failed', 'ea-coder-hard', ?, ?, 'stalled', 'stall 2', 'coding')
                    """,
                    (
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=10)),
                        self.controller.iso(now - self.controller.dt.timedelta(minutes=9)),
                    ),
                )

            config = {
                "accounts": {
                    "acct-bad": {"lane": "core"},
                    "acct-good": {"lane": "core"},
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "fleet",
                "accounts": ["acct-bad", "acct-good"],
                "account_policy": {
                    "preferred_accounts": ["acct-bad", "acct-good"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": False,
                },
            }
            decision = {
                "tier": "multi_file_impl",
                "lane": "core",
                "lane_submode": "mcp",
                "escalation_reason": "",
                "allowed_lanes": ["core"],
                "runtime_model": "ea-coder-hard",
                "model_preferences": ["gpt-5-mini"],
                "estimated_input_tokens": 800,
                "estimated_output_tokens": 200,
            }

            alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-good")
        self.assertEqual(model, "gpt-5-mini")
        bad_trace = next(item for item in trace if item["alias"] == "acct-bad")
        self.assertEqual(bad_trace["evidence_model"], "ea-coder-hard")
        self.assertEqual(bad_trace["model_failures"], 2)
        self.assertIn("route=multi_file_impl", why)

    def test_pick_account_and_model_prefers_primary_bridge_alias_over_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            api_key_file = root / "api-key.txt"
            api_key_file.write_text("test-key\n", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                for alias in ("acct-ea-fallback", "acct-ea-primary"):
                    conn.execute(
                        """
                        INSERT INTO accounts(
                            alias, auth_kind, api_key_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                        )
                        VALUES(?, 'api_key', ?, ?, 1, 'ready', ?)
                        """,
                        (alias, str(api_key_file), json.dumps(["gpt-5-mini"]), now),
                    )

            config = {
                "accounts": {
                    "acct-ea-primary": {
                        "lane": "easy",
                        "bridge_name": "EA Fleet Worker",
                        "bridge_priority": 0,
                        "bridge_fallback_accounts": ["acct-ea-fallback"],
                    },
                    "acct-ea-fallback": {
                        "lane": "easy",
                    },
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "fleet",
                "accounts": ["acct-ea-fallback", "acct-ea-primary"],
                "account_policy": {
                    "preferred_accounts": ["acct-ea-fallback", "acct-ea-primary"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": False,
                },
            }
            decision = {
                "tier": "bounded_fix",
                "lane": "easy",
                "lane_submode": "responses_easy",
                "escalation_reason": "",
                "allowed_lanes": ["easy"],
                "model_preferences": ["gpt-5-mini"],
                "estimated_input_tokens": 800,
                "estimated_output_tokens": 200,
            }

            alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-primary")
        self.assertEqual(model, "gpt-5-mini")
        self.assertIn("acct-ea-primary", {item["alias"] for item in trace})
        self.assertIn("route=bounded_fix", why)

    def test_pick_account_and_model_prefers_shadow_groundwork_alias_for_rework(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            api_key_file = root / "api-key.txt"
            api_key_file.write_text("test-key\n", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                for alias in ("acct-ea-groundwork", "acct-ea-groundwork-2"):
                    conn.execute(
                        """
                        INSERT INTO accounts(
                            alias, auth_kind, api_key_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                        )
                        VALUES(?, 'api_key', ?, ?, 1, 'ready', ?)
                        """,
                        (alias, str(api_key_file), json.dumps(["gpt-5-mini"]), now),
                    )

            config = {
                "accounts": {
                    "acct-ea-groundwork": {"lane": "groundwork"},
                    "acct-ea-groundwork-2": {"lane": "groundwork"},
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "fleet",
                "accounts": ["acct-ea-groundwork", "acct-ea-groundwork-2"],
                "account_policy": {
                    "preferred_accounts": ["acct-ea-groundwork"],
                    "burst_accounts": ["acct-ea-groundwork-2"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": False,
                },
                "worker_topology": {
                    "groundwork_primary": "acct-ea-groundwork",
                    "groundwork_shadow": "acct-ea-groundwork-2",
                },
            }
            decision = {
                "tier": "bounded_fix",
                "lane": "groundwork",
                "lane_submode": "responses_groundwork",
                "escalation_reason": "",
                "allowed_lanes": ["groundwork"],
                "model_preferences": ["gpt-5-mini"],
                "estimated_input_tokens": 800,
                "estimated_output_tokens": 200,
                "task_meta": {
                    "workflow_kind": "groundwork_review_loop",
                    "review_round": 1,
                    "first_review_complete": True,
                },
            }

            alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-groundwork-2")
        self.assertEqual(model, "gpt-5-mini")
        self.assertIn("acct-ea-groundwork-2", {item["alias"] for item in trace})
        self.assertIn("route=bounded_fix", why)

    def test_effective_group_status_prefers_waiting_capacity_over_audit(self) -> None:
        status = self.controller.effective_group_status(
            {"id": "solo-fleet", "mode": "singleton"},
            {"milestone_coverage_complete": False, "design_coverage_complete": False},
            [
                {
                    "id": "fleet",
                    "lifecycle": "live",
                    "status": self.controller.WAITING_CAPACITY_STATUS,
                    "runtime_status": self.controller.WAITING_CAPACITY_STATUS,
                    "needs_refill": False,
                    "open_audit_task_count": 0,
                    "approved_audit_task_count": 0,
                    "active_run_id": None,
                }
            ],
        )

        self.assertEqual(status, self.controller.WAITING_CAPACITY_STATUS)

    def test_effective_group_status_prefers_healing_over_audit(self) -> None:
        status = self.controller.effective_group_status(
            {"id": "solo-ea", "mode": "singleton"},
            {"milestone_coverage_complete": False, "design_coverage_complete": False},
            [
                {
                    "id": "ea",
                    "lifecycle": "live",
                    "status": self.controller.HEALING_STATUS,
                    "runtime_status": self.controller.HEALING_STATUS,
                    "needs_refill": False,
                    "open_audit_task_count": 0,
                    "approved_audit_task_count": 0,
                    "active_run_id": None,
                }
            ],
        )

        self.assertEqual(status, self.controller.HEALING_STATUS)

    def test_group_dispatch_state_blocks_singleton_waiting_capacity(self) -> None:
        dispatch = self.controller.group_dispatch_state(
            {"id": "solo-fleet", "mode": "singleton"},
            {},
            [
                {
                    "id": "fleet",
                    "lifecycle": "live",
                    "status": self.controller.WAITING_CAPACITY_STATUS,
                    "runtime_status": self.controller.WAITING_CAPACITY_STATUS,
                    "enabled": True,
                    "queue_index": 0,
                    "queue_len": 1,
                    "current_queue_item": "persist survival queue state",
                }
            ],
            self.controller.utc_now(),
        )

        self.assertFalse(dispatch["dispatch_ready"])
        self.assertIn("awaiting eligible account", dispatch["dispatch_blockers"][0])

    def test_group_dispatch_state_blocks_singleton_healing(self) -> None:
        dispatch = self.controller.group_dispatch_state(
            {"id": "solo-ea", "mode": "singleton"},
            {},
            [
                {
                    "id": "ea",
                    "lifecycle": "live",
                    "status": self.controller.HEALING_STATUS,
                    "runtime_status": self.controller.HEALING_STATUS,
                    "enabled": True,
                    "queue_index": 0,
                    "queue_len": 1,
                    "current_queue_item": "normalize provider contract",
                }
            ],
            self.controller.utc_now(),
        )

        self.assertFalse(dispatch["dispatch_ready"])
        self.assertIn("self-healing still in progress", dispatch["dispatch_blockers"][0])

    def test_request_due_group_audits_skips_waiting_capacity_singleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES('fleet', ?, '', '', '', '', ?, 0, 0, ?, ?, NULL, NULL, ?, '', '', '', '', ?)
                    """,
                    (
                        str(root),
                        json.dumps(["persist survival queue state"]),
                        self.controller.WAITING_CAPACITY_STATUS,
                        "persist survival queue state",
                        now,
                        now,
                    ),
                )

            config = {
                "policies": {"auto_heal_enabled": True},
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(root),
                        "lifecycle": "live",
                        "enabled": True,
                    }
                ],
                "project_groups": [
                    {
                        "id": "solo-fleet",
                        "projects": ["fleet"],
                        "mode": "singleton",
                    }
                ],
            }

            with mock.patch.object(self.controller, "load_program_registry", return_value={"projects": {}, "groups": {}}):
                with mock.patch.object(self.controller, "trigger_auditor_run_now") as trigger_auditor_run_now:
                    requested = self.controller.request_due_group_audits(config)

        self.assertEqual(requested, 0)
        trigger_auditor_run_now.assert_not_called()


if __name__ == "__main__":
    unittest.main()
