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

    def test_choose_review_account_alias_honors_review_preferred_account_without_broad_project_chatgpt_enablement(self) -> None:
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
                    VALUES(?, 'chatgpt_auth_json', '[]', 1, 'ready', ?)
                    """,
                    ("acct-chatgpt-archon", now),
                )

            alias = self.controller.choose_review_account_alias(
                {
                    "accounts": {
                        "acct-chatgpt-archon": {
                            "lane": "core",
                            "auth_kind": "chatgpt_auth_json",
                            "allowed_models": ["gpt-5.3-codex"],
                        }
                    }
                },
                {
                    "accounts": ["acct-ea-groundwork"],
                    "account_policy": {
                        "preferred_accounts": ["acct-ea-groundwork"],
                        "allow_chatgpt_accounts": False,
                    },
                    "worker_topology": {"core_rescue": "acct-ea-core"},
                    "review": {"preferred_accounts": ["acct-chatgpt-archon"]},
                },
                reviewer_lane="core",
            )

        self.assertEqual(alias, "acct-chatgpt-archon")

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

    def test_ea_codex_status_falls_back_to_persisted_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.controller.DB_PATH = Path(tmpdir) / "fleet.db"
            self.controller.LOG_DIR = Path(tmpdir) / "logs"
            self.controller.CODEX_HOME_ROOT = Path(tmpdir) / "homes"
            self.controller.GROUP_ROOT = Path(tmpdir) / "groups"
            self.controller.init_db()
            self.controller._EA_STATUS_CACHE = {"fetched_at": 0.0, "payload": {}, "window": "7d"}
            persisted = {"onemin_billing_aggregate": {"sum_free_credits": 900000}}
            self.controller.save_runtime_cache(self.controller.RUNTIME_CACHE_KEY_EA_CODEX_STATUS, persisted)

            with mock.patch("urllib.request.urlopen", side_effect=OSError("ea-down")):
                payload = self.controller.ea_codex_status(force=True)

        self.assertEqual(payload["onemin_billing_aggregate"]["sum_free_credits"], 900000)

    def test_participant_burst_metrics_scale_one_ready_lane_at_a_time_from_credit_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            self.controller._EA_STATUS_CACHE = {"fetched_at": 0.0, "payload": {}, "window": "7d"}

            config = {
                "projects": [
                    {
                        "id": "core",
                        "path": str(repo_root),
                        "participant_burst": {
                            "enabled": True,
                            "max_active_workers": 1,
                            "allow_chatgpt_accounts": True,
                            "eligible_task_classes": ["multi_file_impl"],
                            "credit_guard": {
                                "enabled": True,
                                "provider": "onemin",
                                "require_survive_until_next_topup": True,
                            },
                            "autoscale": {
                                "enabled": True,
                                "min_active_workers": 1,
                                "max_active_workers": 3,
                                "increase_when": {
                                    "sponsor_ready_lanes_gte": 1,
                                    "premium_queue_depth_gte": 1,
                                    "jury_oldest_wait_seconds_lt": 3600,
                                },
                                "decrease_when": {
                                    "jury_oldest_wait_seconds_gt": 0,
                                    "jury_queue_depth_gt": 99,
                                    "premium_queue_depth_eq": 99,
                                },
                            },
                        },
                    }
                ],
                "accounts": {},
                "core_backends": {},
                "lanes": {},
            }
            self.controller.sync_config_to_db(config)
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', 'feedback', '', ?, 0, 0, 'dispatch_pending', 'Ship core booster slice', NULL, NULL, NULL, '', '', '', '', ?)
                    ON CONFLICT(id) DO UPDATE SET queue_json=excluded.queue_json, queue_index=excluded.queue_index, updated_at=excluded.updated_at
                    """,
                    (
                        "core",
                        str(repo_root),
                        json.dumps(
                            [
                                {
                                    "title": "Ship core booster slice",
                                    "participant_eligible": True,
                                    "allowed_lanes": ["core"],
                                    "allow_credit_burn": True,
                                }
                            ]
                        ),
                        self.controller.iso(self.controller.utc_now()),
                    ),
                )

            self.controller.save_runtime_cache(
                self.controller.RUNTIME_CACHE_KEY_EA_CODEX_STATUS,
                {
                    "onemin_billing_aggregate": {
                        "sum_free_credits": 2000000,
                        "hours_until_next_topup": 10,
                        "hours_remaining_at_current_pace_no_topup": 20,
                        "slot_count_with_billing_snapshot": 1,
                        "slot_count_with_member_reconciliation": 1,
                    }
                },
            )

            metrics = self.controller.participant_burst_metrics(config, "core")
            self.assertEqual(metrics["effective_max_active_workers"], 1)
            self.assertEqual(metrics["sponsor_ready_lanes"], 0)

            lane_one = self.controller.create_participant_lane_record(
                config,
                {"project_id": "core", "subject_id": "pilot-1", "subject_label": "Pilot One"},
            )
            self.controller.participant_lane_auth_path(lane_one["lane_id"]).write_text("{}", encoding="utf-8")

            metrics = self.controller.participant_burst_metrics(config, "core")
            self.assertEqual(metrics["sponsor_ready_lanes"], 1)
            self.assertEqual(metrics["effective_max_active_workers"], 2)
            self.assertTrue(metrics["credit_guard"]["next_worker_safe"])

            lane_two = self.controller.create_participant_lane_record(
                config,
                {"project_id": "core", "subject_id": "pilot-2", "subject_label": "Pilot Two"},
            )
            self.controller.participant_lane_auth_path(lane_two["lane_id"]).write_text("{}", encoding="utf-8")

            metrics = self.controller.participant_burst_metrics(config, "core")
            self.assertEqual(metrics["sponsor_ready_lanes"], 2)
            self.assertEqual(metrics["effective_max_active_workers"], 3)

    def test_normalize_config_tolerates_blocking_consistency_warnings_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "fleet.yaml"
            accounts_path = root / "accounts.yaml"
            config_path.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "id": "core",
                                "path": str(root / "repo"),
                                "accounts": ["acct-missing"],
                                "queue": [],
                            }
                        ],
                        "lanes": {},
                    }
                ),
                encoding="utf-8",
            )
            accounts_path.write_text(json.dumps({"accounts": {}}), encoding="utf-8")
            self.controller.CONFIG_PATH = config_path
            self.controller.ACCOUNTS_PATH = accounts_path
            self.controller.POLICIES_PATH = config_path.with_name("policies.yaml")
            self.controller.ROUTING_PATH = config_path.with_name("routing.yaml")
            self.controller.GROUPS_PATH = config_path.with_name("groups.yaml")
            self.controller.PROJECTS_DIR = config_path.parent / "projects"
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller._CONFIG_CONSISTENCY_BLOCKERS = []
            self.controller._CONFIG_CONSISTENCY_BLOCKER_SIGNATURE = ""

            config = self.controller.normalize_config()

        self.assertEqual(config["projects"][0]["id"], "core")
        self.assertEqual(self.controller._CONFIG_CONSISTENCY_BLOCKERS[0]["kind"], "unknown_account_alias")

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

    def test_pick_account_and_model_uses_shared_easy_lane_fallback_for_easy_only_slice(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            api_key_file = root / "api-key.txt"
            api_key_file.write_text("test-key\n", encoding="utf-8")
            auth_json = root / "auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, api_key_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'api_key', ?, ?, 1, 'ready', ?)
                    """,
                    ("acct-ea-fleet", str(api_key_file), json.dumps(["gpt-5-mini"]), now),
                )
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'chatgpt_auth_json', ?, ?, 1, 'ready', ?)
                    """,
                    ("acct-chatgpt-archon", str(auth_json), json.dumps(["gpt-5.3-codex"]), now),
                )

            config = {
                "accounts": {
                    "acct-ea-fleet": {
                        "lane": "easy",
                        "auth_kind": "api_key",
                    },
                    "acct-chatgpt-archon": {
                        "auth_kind": "chatgpt_auth_json",
                    },
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "mobile",
                "accounts": ["acct-chatgpt-archon"],
                "account_policy": {
                    "preferred_accounts": ["acct-chatgpt-archon"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": True,
                },
            }
            decision = {
                "tier": "bounded_fix",
                "lane": "easy",
                "lane_submode": "mcp",
                "escalation_reason": "cheap_first_default",
                "allowed_lanes": ["easy"],
                "model_preferences": ["gpt-5-mini"],
                "estimated_input_tokens": 800,
                "estimated_output_tokens": 200,
            }

            with mock.patch.object(self.controller, "has_api_key", return_value=True):
                alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-fleet")
        self.assertEqual(model, "gpt-5-mini")
        self.assertIn("route=bounded_fix", why)
        self.assertIn("acct-ea-fleet", {item["alias"] for item in trace})

    def test_eligible_account_aliases_include_shared_lane_fallback_for_current_easy_slice(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            api_key_file = root / "api-key.txt"
            api_key_file.write_text("test-key\n", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, api_key_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'api_key', ?, ?, 1, 'ready', ?)
                    """,
                    ("acct-ea-fleet", str(api_key_file), json.dumps(["gpt-5-mini"]), now),
                )
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', 'feedback', '', ?, 0, 0, 'awaiting_account', ?, NULL, NULL, NULL, '', '', '', '', ?)
                    """,
                    (
                        "mobile",
                        str(repo_root),
                        json.dumps([{"title": "Backfill mobile shell", "allowed_lanes": ["easy"]}]),
                        "Backfill mobile shell",
                        now,
                    ),
                )

            config = {
                "accounts": {
                    "acct-ea-fleet": {
                        "lane": "easy",
                        "auth_kind": "api_key",
                    },
                },
                "lanes": self.controller.normalize_lanes_config({}),
            }
            project_cfg = {
                "id": "mobile",
                "path": str(repo_root),
                "accounts": [],
                "account_policy": {
                    "preferred_accounts": [],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": False,
                },
            }

            with mock.patch.object(self.controller, "has_api_key", return_value=True):
                eligible = self.controller.eligible_account_aliases(config, project_cfg, self.controller.utc_now())

        self.assertEqual(eligible, ["acct-ea-fleet"])

    def test_pick_account_and_model_falls_back_to_core_when_cheap_pool_is_starved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            auth_json = root / "auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'chatgpt_auth_json', ?, ?, 1, 'ready', ?)
                    """,
                    ("acct-chatgpt-archon", str(auth_json), json.dumps(["gpt-5.3-codex"]), now),
                )

            config = {
                "accounts": {
                    "acct-chatgpt-archon": {
                        "auth_kind": "chatgpt_auth_json",
                    },
                },
                "lanes": {
                    "core": {"runtime_model": "ea-coder-hard"},
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "mobile",
                "accounts": ["acct-chatgpt-archon"],
                "account_policy": {
                    "preferred_accounts": ["acct-chatgpt-archon"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": True,
                },
            }
            decision = {
                "tier": "bounded_fix",
                "lane": "easy",
                "lane_submode": "mcp",
                "escalation_reason": "cheap_first_default",
                "allowed_lanes": ["easy"],
                "model_preferences": ["gpt-5-mini"],
                "estimated_input_tokens": 800,
                "estimated_output_tokens": 200,
            }

            alias, model, why, _trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-chatgpt-archon")
        self.assertEqual(model, "gpt-5.3-codex")
        self.assertIn("starvation fallback", why)

    def test_pick_account_and_model_falls_back_from_survival_to_core_when_survival_pool_is_starved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            auth_json = root / "auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'chatgpt_auth_json', ?, ?, 1, 'ready', ?)
                    """,
                    ("acct-chatgpt-archon", str(auth_json), json.dumps(["gpt-5.3-codex"]), now),
                )

            config = {
                "accounts": {
                    "acct-chatgpt-archon": {
                        "auth_kind": "chatgpt_auth_json",
                    },
                },
                "lanes": {
                    "core": {"runtime_model": "ea-coder-hard"},
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "mobile",
                "accounts": ["acct-chatgpt-archon"],
                "account_policy": {
                    "preferred_accounts": ["acct-chatgpt-archon"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": True,
                },
            }
            decision = {
                "tier": "bounded_fix",
                "lane": "survival",
                "lane_submode": "responses_survival",
                "escalation_reason": "capacity_exhausted_survival_fallback",
                "allowed_lanes": ["easy", "survival"],
                "model_preferences": ["ea-coder-survival", "gpt-5-mini"],
                "estimated_input_tokens": 800,
                "estimated_output_tokens": 200,
            }

            alias, model, why, _trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-chatgpt-archon")
        self.assertEqual(model, "gpt-5.3-codex")
        self.assertIn("starvation fallback", why)

    def test_pick_account_and_model_falls_back_to_core_for_multi_file_impl_when_cheap_pool_is_starved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            auth_json = root / "auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'chatgpt_auth_json', ?, ?, 1, 'ready', ?)
                    """,
                    ("acct-chatgpt-archon", str(auth_json), json.dumps(["gpt-5.3-codex"]), now),
                )

            config = {
                "accounts": {
                    "acct-chatgpt-archon": {
                        "auth_kind": "chatgpt_auth_json",
                    },
                },
                "lanes": {
                    "core": {"runtime_model": "ea-coder-hard"},
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "hub-registry",
                "accounts": ["acct-chatgpt-archon"],
                "account_policy": {
                    "preferred_accounts": ["acct-chatgpt-archon"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": True,
                },
            }
            decision = {
                "tier": "multi_file_impl",
                "lane": "survival",
                "lane_submode": "responses_survival",
                "escalation_reason": "capacity_exhausted_survival_fallback",
                "allowed_lanes": ["easy", "survival"],
                "model_preferences": ["ea-coder-survival", "gpt-5.4", "gpt-5.3-codex"],
                "estimated_input_tokens": 1200,
                "estimated_output_tokens": 800,
            }

            alias, model, why, _trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-chatgpt-archon")
        self.assertEqual(model, "gpt-5.3-codex")
        self.assertIn("starvation fallback", why)

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

    def test_runtime_task_cache_tracks_scheduled_launch_intents(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            self.controller.sync_config_to_db(
                {
                    "projects": [
                        {
                            "id": "fleet",
                            "path": str(repo_root),
                            "queue": ["persist survival queue state"],
                            "enabled": True,
                        }
                    ]
                }
            )

            self.controller.upsert_runtime_task(
                "fleet",
                task_kind="coding",
                task_state="scheduled",
                payload={"slice_name": "persist survival queue state"},
            )
            has_runtime_task = self.controller.project_has_runtime_task("fleet")
            cache_payload, _ = self.controller.load_runtime_cache(self.controller.RUNTIME_TASK_CACHE_KEY)

        self.assertTrue(has_runtime_task)
        self.assertEqual(cache_payload["active_project_ids"], ["fleet"])
        self.assertEqual(cache_payload["tasks"][0]["task_kind"], "coding")
        self.assertEqual(cache_payload["tasks"][0]["slice_name"], "persist survival queue state")

    def test_rehydrate_runtime_tasks_relaunches_scheduled_coding_intent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            config = {
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "queue": ["persist survival queue state"],
                        "enabled": True,
                    }
                ]
            }
            self.controller.sync_config_to_db(config)
            self.controller.upsert_runtime_task(
                "fleet",
                task_kind="coding",
                task_state="scheduled",
                payload={
                    "slice_name": "persist survival queue state",
                    "account_alias": "acct-ea-groundwork",
                    "selected_model": "ea-groundwork-gemini",
                    "selection_note": "rehydrate",
                    "selection_trace": [],
                    "decision": {"reason": "test", "tier": "multi_file_impl", "reasoning_effort": "low"},
                },
            )

            launched: list[str] = []

            async def fake_execute(*args, **kwargs):
                launched.append(str(args[3]))
                self.controller.clear_runtime_task("fleet")

            with mock.patch.object(self.controller, "execute_project_slice", side_effect=fake_execute):
                async def _run() -> None:
                    self.controller.state.controller_loop = asyncio.get_running_loop()
                    relaunched = self.controller.rehydrate_runtime_tasks(config)
                    self.assertEqual(relaunched, 1)
                    await self.controller.state.tasks["fleet"]
                    self.controller.prune_finished_tasks()
                    self.controller.state.controller_loop = None

                asyncio.run(_run())
            has_runtime_task = self.controller.project_has_runtime_task("fleet")

        self.assertEqual(launched, ["persist survival queue state"])
        self.assertFalse(has_runtime_task)

    def test_api_pause_project_cancels_live_runtime_and_marks_project_paused(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            self.controller.sync_config_to_db(
                {
                    "projects": [
                        {
                            "id": "fleet",
                            "path": str(repo_root),
                            "queue": ["persist survival queue state"],
                            "enabled": False,
                        }
                    ]
                }
            )

            with self.controller.db() as conn:
                run_id = int(
                    conn.execute(
                        """
                        INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                        VALUES('fleet', 'acct-ea-core', 'coding', 'persist survival queue state', 'running', 'gpt-5.4', 'medium', 'core', 'test', ?, '', '', '')
                        """,
                        (self.controller.iso(self.controller.utc_now()),),
                    ).lastrowid
                )
                conn.execute("UPDATE projects SET status='running', current_slice='persist survival queue state', active_run_id=? WHERE id='fleet'", (run_id,))
            self.controller.upsert_runtime_task(
                "fleet",
                task_kind="coding",
                task_state="running",
                payload={"slice_name": "persist survival queue state"},
                run_id=run_id,
                started_at=self.controller.utc_now(),
            )

            class FakeTask:
                def __init__(self) -> None:
                    self.cancelled = False

                def done(self) -> bool:
                    return False

                def cancel(self) -> bool:
                    self.cancelled = True
                    return True

            fake_task = FakeTask()
            self.controller.state.tasks["fleet"] = fake_task

            with mock.patch.object(self.controller, "normalize_config", return_value={"projects": [{"id": "fleet", "path": str(repo_root), "enabled": False}]}):
                with mock.patch.object(self.controller, "get_project_cfg", return_value={"id": "fleet", "path": str(repo_root), "enabled": False}):
                    result = self.controller.api_pause_project("fleet")

            with self.controller.db() as conn:
                project_row = conn.execute("SELECT status, active_run_id, last_error FROM projects WHERE id='fleet'").fetchone()

        self.assertTrue(fake_task.cancelled)
        self.assertEqual(result["status"], "paused")
        self.assertTrue(result["cancel_requested"])
        self.assertEqual(project_row["status"], "paused")
        self.assertIsNone(project_row["active_run_id"])
        self.assertIn("pause requested", str(project_row["last_error"] or ""))

    def test_execute_project_slice_cancellation_marks_run_paused_when_project_disabled(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        now = self.controller.iso(self.controller.utc_now())
        project_cfg["enabled"] = False
        with self.controller.db() as conn:
            conn.execute("UPDATE projects SET status='running', current_slice=?, last_run_at=? WHERE id='fleet'", (str(slice_item["title"]), now))
            project_row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()
        self.assertIsNotNone(project_row)
        decision = {
            "tier": "groundwork",
            "reasoning_effort": "low",
            "estimated_prompt_chars": 2048,
            "estimated_input_tokens": 512,
            "estimated_output_tokens": 512,
            "predicted_changed_files": 1,
            "requires_contract_authority": False,
            "reason": "test cancellation",
            "lane": "groundwork",
            "lane_submode": "responses_groundwork",
            "selected_profile": "default",
            "why_not_cheaper": "",
            "escalation_reason": "",
            "expected_allowance_burn": {},
            "allowed_lanes": ["groundwork"],
            "required_reviewer_lane": "jury",
            "final_reviewer_lane": "jury",
            "task_meta": {},
            "spark_eligible": False,
            "runtime_model": "ea-groundwork-gemini",
            "lane_capacity": {},
        }

        async def fake_run_command(*_args, **_kwargs):
            raise asyncio.CancelledError

        with mock.patch.object(self.controller, "prepare_account_environment", return_value={}):
            with mock.patch.object(self.controller, "touch_account"):
                with mock.patch.object(self.controller, "record_account_selection"):
                    with mock.patch.object(self.controller, "build_prompt", return_value="prompt"):
                        with mock.patch.object(self.controller, "git_dirty_snapshot", return_value={}):
                            with mock.patch.object(self.controller, "run_command", side_effect=fake_run_command):
                                with mock.patch.object(self.controller, "project_enabled_in_desired_state", return_value=False):
                                    with self.assertRaises(asyncio.CancelledError):
                                        asyncio.run(
                                            self.controller.execute_project_slice(
                                                config,
                                                project_cfg,
                                                project_row,
                                                str(slice_item["title"]),
                                                decision,
                                                "acct-ea-groundwork",
                                                "ea-groundwork-gemini",
                                                "test note",
                                                [],
                                            )
                                        )

        with self.controller.db() as conn:
            run_row = conn.execute("SELECT status, error_class, error_message FROM runs ORDER BY id DESC LIMIT 1").fetchone()
            project_row = conn.execute("SELECT status, active_run_id, last_error FROM projects WHERE id='fleet'").fetchone()

        self.assertEqual(run_row["status"], "paused")
        self.assertEqual(run_row["error_class"], "operator_pause")
        self.assertEqual(project_row["status"], "paused")
        self.assertIsNone(project_row["active_run_id"])
        self.assertIn("pause requested", str(project_row["last_error"] or ""))

    def test_execute_project_slice_uses_selected_model_over_lane_runtime_model(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        now = self.controller.iso(self.controller.utc_now())
        project_cfg["enabled"] = False
        config["accounts"]["acct-chatgpt-archon"] = {"auth_kind": "chatgpt_auth_json"}
        with self.controller.db() as conn:
            conn.execute(
                """
                INSERT INTO accounts(
                    alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                )
                VALUES(?, 'chatgpt_auth_json', ?, ?, 1, 'ready', ?)
                """,
                ("acct-chatgpt-archon", str(repo_root / "auth.json"), json.dumps(["gpt-5.3-codex"]), now),
            )
            conn.execute("UPDATE projects SET status='running', current_slice=?, last_run_at=? WHERE id='fleet'", (str(slice_item["title"]), now))
            project_row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()
        self.assertIsNotNone(project_row)
        decision = {
            "tier": "bounded_fix",
            "reasoning_effort": "low",
            "estimated_prompt_chars": 2048,
            "estimated_input_tokens": 512,
            "estimated_output_tokens": 512,
            "predicted_changed_files": 1,
            "requires_contract_authority": False,
            "reason": "test runtime model handoff",
            "lane": "survival",
            "lane_submode": "responses_survival",
            "selected_profile": "survival",
            "why_not_cheaper": "",
            "escalation_reason": "capacity_exhausted_survival_fallback",
            "expected_allowance_burn": {},
            "allowed_lanes": ["easy", "survival", "core"],
            "required_reviewer_lane": "core",
            "final_reviewer_lane": "core",
            "task_meta": {},
            "spark_eligible": False,
            "runtime_model": "ea-coder-survival",
            "lane_capacity": {},
        }

        captured: dict[str, str] = {}

        def fake_build_prompt(_project_cfg, _slice_name, decision_payload, _feedback_files):
            captured["prompt_model"] = str(decision_payload.get("selected_model") or "")
            return "prompt"

        async def fake_run_command(*_args, **_kwargs):
            raise asyncio.CancelledError

        def fake_record_account_selection(_alias: str, model: str) -> None:
            captured["runtime_model"] = model

        with mock.patch.object(self.controller, "prepare_account_environment", return_value={}):
            with mock.patch.object(self.controller, "touch_account"):
                with mock.patch.object(self.controller, "record_account_selection", side_effect=fake_record_account_selection):
                    with mock.patch.object(self.controller, "build_prompt", side_effect=fake_build_prompt):
                        with mock.patch.object(self.controller, "git_dirty_snapshot", return_value={}):
                            with mock.patch.object(self.controller, "run_command", side_effect=fake_run_command):
                                with mock.patch.object(self.controller, "project_enabled_in_desired_state", return_value=False):
                                    with self.assertRaises(asyncio.CancelledError):
                                        asyncio.run(
                                            self.controller.execute_project_slice(
                                                config,
                                                project_cfg,
                                                project_row,
                                                str(slice_item["title"]),
                                                decision,
                                                "acct-chatgpt-archon",
                                                "gpt-5.3-codex",
                                                "test note",
                                                [],
                                            )
                                        )

        self.assertEqual(captured["prompt_model"], "gpt-5.3-codex")
        self.assertEqual(captured["runtime_model"], "gpt-5.3-codex")

    def test_execute_local_review_cancellation_marks_run_paused_and_does_not_auto_relaunch(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        project_cfg["enabled"] = False
        self._upsert_loop_review_request(
            config,
            project_cfg,
            str(slice_item["title"]),
            {**dict(slice_item), "review_round": 1},
            execution_lane="groundwork",
        )
        with self.controller.db() as conn:
            project_row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()
        pr_row = self.controller.pull_request_row("fleet")
        self.assertIsNotNone(project_row)
        self.assertIsNotNone(pr_row)

        async def fake_run_command(*_args, **_kwargs):
            raise asyncio.CancelledError

        with mock.patch.object(self.controller, "prepare_account_environment", return_value={}):
            with mock.patch.object(self.controller, "touch_account"):
                with mock.patch.object(self.controller, "project_enabled_in_desired_state", return_value=False):
                    with mock.patch.object(self.controller, "run_command", side_effect=fake_run_command):
                        with self.assertRaises(asyncio.CancelledError):
                            asyncio.run(
                                self.controller.execute_local_review_fallback(
                                    config,
                                    project_cfg,
                                    project_row,
                                    pr_row,
                                    reason="resume pending local review fallback after interrupted controller task",
                                )
                            )

        with self.controller.db() as conn:
            run_row = conn.execute("SELECT status, error_class FROM runs ORDER BY id DESC LIMIT 1").fetchone()
            project_row = conn.execute("SELECT status, active_run_id FROM projects WHERE id='fleet'").fetchone()

        self.assertEqual(run_row["status"], "paused")
        self.assertEqual(run_row["error_class"], "operator_pause")
        self.assertEqual(project_row["status"], "paused")
        self.assertIsNone(project_row["active_run_id"])

        healed = self.controller.heal_orphaned_local_reviews({"projects": [project_cfg]})
        self.assertEqual(healed, 0)

    def test_review_hold_status_prefers_local_review_when_pr_row_is_local(self) -> None:
        status = self.controller.review_hold_status_for_project(
            "core",
            project_cfg={"id": "core", "review": {"mode": "github"}},
            pr_row={"review_mode": "local", "review_status": "review_requested"},
        )

        self.assertEqual(status, self.controller.LOCAL_REVIEW_PENDING_STATUS)

    def test_select_local_review_model_falls_back_to_chatgpt_supported_model(self) -> None:
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
                    INSERT INTO accounts(alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at)
                    VALUES(?, 'auth_json', '/tmp/reviewer-auth.json', ?, 1, 'ready', ?)
                    """,
                    ("acct-chatgpt-review", json.dumps(["gpt-5.3-codex"]), now),
                )

            selected_model = self.controller.select_local_review_model(
                {"accounts": {"acct-chatgpt-review": {"auth_kind": "auth_json"}}},
                "acct-chatgpt-review",
                reviewer_model="ea-coder-hard",
            )

        self.assertEqual(selected_model, "gpt-5.3-codex")

    def test_local_review_sandbox_candidates_default_to_workspace_write(self) -> None:
        self.assertEqual(
            self.controller.local_review_sandbox_candidates({}),
            ["workspace-write"],
        )
        self.assertEqual(
            self.controller.local_review_sandbox_candidates(
                {
                    "review": {"sandbox": "read-only"},
                    "runner": {"sandbox": "workspace-write"},
                }
            ),
            ["read-only", "workspace-write"],
        )

    def test_execute_local_review_retries_namespace_failure_with_next_sandbox(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        project_cfg["review"] = {
            **dict(project_cfg.get("review") or {}),
            "sandbox": "read-only",
        }
        project_cfg["runner"] = {"sandbox": "workspace-write"}
        self._upsert_loop_review_request(
            config,
            project_cfg,
            str(slice_item["title"]),
            {**dict(slice_item), "review_round": 1},
            execution_lane="groundwork",
        )
        with self.controller.db() as conn:
            project_row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()
        pr_row = self.controller.pull_request_row("fleet")
        self.assertIsNotNone(project_row)
        self.assertIsNotNone(pr_row)

        parse_result = {
            "review_round": 1,
            "verdict": "manual_hold",
            "confidence": 0.2,
            "summary": "manual hold requested after successful retry",
            "findings": [
                {
                    "external_id": "needs-operator",
                    "source_kind": "local_review",
                    "author_login": "fleet-local-review",
                    "review_state": "LOCAL_FALLBACK",
                    "path": "",
                    "line": None,
                    "body": "[review] needs-operator\nfollow-up is still needed",
                    "html_url": "",
                    "severity": "high",
                    "blocking": True,
                }
            ],
            "blocking_issues": [
                {
                    "issue_id": "needs-operator",
                    "category": "review",
                    "severity": "blocking",
                    "evidence": ["follow-up is still needed"],
                    "fix_expectation": "rerun after operator action",
                }
            ],
            "non_blocking_issues": [],
            "repeat_issue_ids": [],
            "core_rescue_recommended": False,
        }
        sandboxes: list[str] = []

        async def fake_run_command(cmd, **kwargs):
            sandboxes.append(cmd[cmd.index("--sandbox") + 1])
            log_path = kwargs["log_path"]
            if len(sandboxes) == 1:
                log_path.write_text(
                    "bwrap: No permissions to create a new namespace, likely because the kernel does not allow non-privileged user namespaces.\n",
                    encoding="utf-8",
                )
                return self.controller.CommandResult(exit_code=1)
            log_path.write_text(
                '{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"output_tokens":1}}\n',
                encoding="utf-8",
            )
            return self.controller.CommandResult(exit_code=0)

        with mock.patch.object(self.controller, "prepare_account_environment", return_value={}):
            with mock.patch.object(self.controller, "run_command", side_effect=fake_run_command):
                with mock.patch.object(self.controller, "parse_local_review_result", return_value=parse_result):
                    with mock.patch.object(self.controller, "publish_review_feedback"):
                        asyncio.run(
                            self.controller.execute_local_review_fallback(
                                config,
                                project_cfg,
                                project_row,
                                pr_row,
                                reason="retry namespace-limited review",
                            )
                        )

        self.assertEqual(sandboxes, ["read-only", "workspace-write"])
        with self.controller.db() as conn:
            run_row = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(run_row)
        self.assertEqual(run_row["status"], "manual_hold")

    def test_execute_local_review_chatgpt_fallback_skips_ea_provider_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()

            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            config = {
                "lanes": {
                    "core": {"id": "core", "runtime_model": "ea-coder-hard"},
                },
                "accounts": {
                    "acct-chatgpt-review": {
                        "auth_kind": "chatgpt_auth_json",
                        "auth_json_file": "/tmp/reviewer.auth.json",
                        "allowed_models": ["gpt-5.3-codex"],
                        "lane": "core",
                    }
                },
            }
            project_cfg = {
                "id": "fleet",
                "path": str(repo_root),
                "accounts": ["acct-chatgpt-review"],
                "worker_topology": {"core_rescue": "acct-chatgpt-review"},
                "runner": {
                    "config_overrides": [
                        'model_provider="ea"',
                        'model_providers.ea.base_url="http://host.docker.internal:8090/v1"',
                    ]
                },
                "review": {
                    "enabled": True,
                    "mode": "local",
                    "trigger": "local",
                    "required_before_queue_advance": True,
                    "base_branch": "main",
                },
            }

            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at)
                    VALUES(?, 'chatgpt_auth_json', '/tmp/reviewer.auth.json', ?, 1, 'ready', ?)
                    """,
                    ("acct-chatgpt-review", json.dumps(["gpt-5.3-codex"]), now),
                )
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', 'feedback', '', '[]', 0, 0, 'dispatch_pending', ?, NULL, NULL, NULL, '', '', '', '', ?)
                    """,
                    ("fleet", str(repo_root), "Review fleet", now),
                )

            review_focus = self.controller.encode_review_focus(
                self.controller.review_focus_text(project_cfg, "Review fleet"),
                reviewer_lane="core",
                reviewer_model="ea-coder-hard",
                metadata={
                    "review_round": "1",
                    "review_packet": json.dumps({}, sort_keys=True),
                },
            )
            pr_row = self.controller.upsert_local_review_request(
                project_cfg,
                slice_name="Review fleet",
                requested_at=self.controller.utc_now(),
                review_focus=review_focus,
                workflow_state={
                    "workflow_kind": "default",
                    "review_round": 1,
                    "max_review_rounds": 0,
                },
            )
            with self.controller.db() as conn:
                project_row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()

            self.assertIsNotNone(project_row)
            self.assertIsNotNone(pr_row)

            parse_result = {
                "review_round": 1,
                "verdict": "manual_hold",
                "confidence": 0.2,
                "summary": "manual hold requested after successful review",
                "findings": [
                    {
                        "external_id": "needs-operator",
                        "source_kind": "local_review",
                        "author_login": "fleet-local-review",
                        "review_state": "LOCAL_FALLBACK",
                        "path": "",
                        "line": None,
                        "body": "[review] needs-operator\nfollow-up is still needed",
                        "html_url": "",
                        "severity": "high",
                        "blocking": True,
                    }
                ],
                "blocking_issues": [
                    {
                        "issue_id": "needs-operator",
                        "category": "review",
                        "severity": "blocking",
                        "evidence": ["follow-up is still needed"],
                        "fix_expectation": "rerun after operator action",
                    }
                ],
                "non_blocking_issues": [],
                "repeat_issue_ids": [],
                "core_rescue_recommended": False,
            }
            captured_cmd: list[str] = []

            async def fake_run_command(cmd, **kwargs):
                captured_cmd[:] = list(cmd)
                kwargs["log_path"].write_text(
                    '{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"output_tokens":1}}\n',
                    encoding="utf-8",
                )
                return self.controller.CommandResult(exit_code=0)

            with mock.patch.object(self.controller, "prepare_account_environment", return_value={}):
                with mock.patch.object(self.controller, "run_command", side_effect=fake_run_command):
                    with mock.patch.object(self.controller, "parse_local_review_result", return_value=parse_result):
                        with mock.patch.object(self.controller, "publish_review_feedback"):
                            asyncio.run(
                                self.controller.execute_local_review_fallback(
                                    config,
                                    project_cfg,
                                    project_row,
                                    pr_row,
                                    reason="chatgpt fallback review",
                                )
                            )

        self.assertIn("--model", captured_cmd)
        self.assertIn("gpt-5.3-codex", captured_cmd)
        self.assertNotIn('model_provider="ea"', captured_cmd)
        self.assertNotIn('model_providers.ea.base_url="http://host.docker.internal:8090/v1"', captured_cmd)

    def test_heal_orphaned_local_reviews_relaunches_local_mode_review_requested_rows(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        project_cfg["review"] = {
            **dict(project_cfg.get("review") or {}),
            "mode": "github",
            "trigger": "manual_comment",
        }
        full_config = {**config, "projects": [project_cfg]}
        self._upsert_loop_review_request(
            full_config,
            project_cfg,
            str(slice_item["title"]),
            {**dict(slice_item), "review_round": 1},
            execution_lane="groundwork",
        )
        with self.controller.db() as conn:
            conn.execute(
                "UPDATE pull_requests SET review_status='review_requested', updated_at=? WHERE project_id='fleet'",
                (self.controller.iso(self.controller.utc_now()),),
            )
            conn.execute(
                "UPDATE projects SET status='review_requested', active_run_id=NULL WHERE id='fleet'"
            )

        with mock.patch.object(self.controller, "launch_local_review_fallback", return_value=True) as launch_local_review_fallback:
            healed = self.controller.heal_orphaned_local_reviews(full_config)

        self.assertEqual(healed, 1)
        launch_local_review_fallback.assert_called_once()

    def test_low_priority_drain_blocks_groundwork_selection(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        config["accounts"]["acct-ea-groundwork"]["health_state"] = self.controller.LOW_PRIORITY_DRAINING_STATE
        config["accounts"]["acct-ea-groundwork-2"]["health_state"] = self.controller.LOW_PRIORITY_DRAINING_STATE
        decision = {
            "tier": "groundwork",
            "lane": "groundwork",
            "lane_submode": "responses_groundwork",
            "escalation_reason": "groundwork_policy_default",
            "model_preferences": ["ea-groundwork-gemini"],
            "estimated_input_tokens": 512,
            "estimated_output_tokens": 512,
            "allowed_lanes": ["groundwork"],
        }

        with mock.patch.object(self.controller, "has_api_key", return_value=True):
            alias, model, note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertIsNone(alias)
        self.assertIsNone(model)
        self.assertIn("low_priority_drain", note)
        self.assertTrue(any("low_priority_draining" in str(item.get("reason") or "") for item in trace))

    def test_low_priority_drain_still_allows_core_selection(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        config["accounts"]["acct-ea-core"]["health_state"] = self.controller.LOW_PRIORITY_DRAINING_STATE
        decision = {
            "tier": "cross_repo_contract",
            "lane": "core",
            "lane_submode": "default",
            "escalation_reason": "contract_authority",
            "model_preferences": ["ea-coder-hard"],
            "estimated_input_tokens": 1024,
            "estimated_output_tokens": 1024,
            "allowed_lanes": ["core"],
        }

        with mock.patch.object(self.controller, "has_api_key", return_value=True):
            alias, model, note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-core")
        self.assertEqual(model, "ea-coder-hard")
        selected = next(item for item in trace if item.get("alias") == "acct-ea-core")
        self.assertTrue(selected.get("low_priority_drain_override"))

    def test_create_participant_lane_record_persists_hub_sponsor_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            config = {
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "participant_burst": {
                            "enabled": True,
                            "allow_chatgpt_accounts": True,
                            "max_active_workers": 2,
                            "preferred_models": ["gpt-5.4", "gpt-5.3-codex"],
                            "roles": {
                                "review": {
                                    "dispatch_lane": "review_light",
                                    "backend": "chatgpt_participant",
                                    "min_authorization_tier": "plus",
                                }
                            },
                        },
                    }
                ],
                "core_backends": {
                    "chatgpt_participant": {
                        "auth_class": "chatgpt_auth_json",
                        "runtime_model": "gpt-5.4",
                        "allowed_models": ["gpt-5.4", "gpt-5.3-codex"],
                    }
                },
                "accounts": {},
            }
            self.controller.sync_config_to_db(config)

            lane = self.controller.create_participant_lane_record(
                config,
                {
                    "project_id": "fleet",
                    "subject_id": "subject-1",
                    "subject_label": "Pilot One",
                    "hub_user_id": "usr_1",
                    "hub_group_id": "grp_1",
                    "boost_campaign_id": "cmp_1",
                    "sponsor_session_id": "sps_1",
                    "public_contribution_visibility": "group",
                    "lane_role": "review",
                    "authorization_tier": "pro",
                    "tier_source": "user_declared",
                },
            )

            self.assertEqual(lane["hub_user_id"], "usr_1")
            self.assertEqual(lane["hub_group_id"], "grp_1")
            self.assertEqual(lane["boost_campaign_id"], "cmp_1")
            self.assertEqual(lane["sponsor_session_id"], "sps_1")
            self.assertEqual(lane["public_contribution_visibility"], "group")
            self.assertEqual(lane["lane_role"], "review")
            self.assertEqual(lane["authorization_tier"], "pro")
            self.assertEqual(lane["tier_source"], "user_declared")

            account_cfg = self.controller.participant_lane_account_config(
                lane,
                self.controller.normalize_core_backends_config(config.get("core_backends")),
            )
            self.assertEqual(account_cfg["lane"], "review_light")
            self.assertEqual(account_cfg["participant_hub_user_id"], "usr_1")
            self.assertEqual(account_cfg["participant_hub_group_id"], "grp_1")
            self.assertEqual(account_cfg["participant_sponsor_session_id"], "sps_1")
            self.assertEqual(account_cfg["participant_lane_role"], "review")

    def test_activate_participant_lane_marks_receipt_status_when_targets_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            config = {
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "participant_burst": {
                            "enabled": True,
                            "allow_chatgpt_accounts": True,
                            "max_active_workers": 2,
                            "preferred_models": ["gpt-5.4"],
                        },
                    }
                ],
                "core_backends": {
                    "chatgpt_participant": {
                        "auth_class": "chatgpt_auth_json",
                        "runtime_model": "gpt-5.4",
                    }
                },
                "accounts": {},
            }
            self.controller.sync_config_to_db(config)

            lane = self.controller.create_participant_lane_record(
                config,
                {
                    "project_id": "fleet",
                    "subject_id": "subject-1",
                    "subject_label": "Pilot One",
                },
            )
            self.controller.participant_lane_auth_path(lane["lane_id"]).write_text("{}", encoding="utf-8")
            activated = self.controller.activate_participant_lane_record(config, lane["lane_id"])
            refreshed = self.controller.participant_lane_row(activated["lane_id"], refresh=False)

            self.assertIsNotNone(refreshed)
            self.assertEqual(refreshed["reward_receipt_status"], "not_configured")
            self.assertEqual(refreshed["telemetry"]["receipts"]["last_event_kind"], "lane_activated")
            self.assertEqual(refreshed["authorization_tier"], "unknown")

    def test_participant_receipt_carries_authorization_tier(self) -> None:
        lane_row = {
            "lane_id": "participant-demo",
            "project_id": "fleet",
            "hub_user_id": "usr_1",
            "hub_group_id": "grp_1",
            "sponsor_session_id": "sps_1",
            "activated_at": "2026-03-19T10:00:00Z",
            "telemetry": {
                "authorization_tier": "business",
                "tier_source": "fleet_detected",
            },
        }

        receipt = self.controller.build_participant_contribution_receipt(
            lane_row,
            event_kind="slice_landed",
            project_id="fleet",
            slice_id="slice-1",
            accepted_on_round="1",
            verified=True,
        )

        self.assertEqual(receipt["authorization_tier_at_receipt"], "business")
        self.assertEqual(receipt["tier_source"], "fleet_detected")

    def test_design_mirror_tracks_future_capability_registry_docs(self) -> None:
        for rel in (
            ".codex-design/product/HORIZONS.md",
            ".codex-design/product/HORIZON_SIGNAL_POLICY.md",
            ".codex-design/product/LTD_CAPABILITY_MAP.md",
            ".codex-design/product/PUBLIC_GUIDE_POLICY.md",
            ".codex-design/product/PUBLIC_MEDIA_AND_GUIDE_ASSET_POLICY.md",
            ".codex-design/product/EXTERNAL_TOOLS_PLANE.md",
        ):
            self.assertIn(rel, self.controller.DESIGN_MIRROR_PRODUCT_FILES)


if __name__ == "__main__":
    unittest.main()
