from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import sqlite3
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

    def test_credential_failure_backoff_fans_out_to_shared_api_key_aliases(self) -> None:
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
            with mock.patch.object(
                self.controller,
                "run_credential_repair_command",
                return_value={"status": "not_configured", "reason": "credential repair command is not configured"},
            ), mock.patch.object(
                self.controller,
                "probe_api_key_credential_source",
                return_value={"status": "auth_failed", "reason": "api key is invalid or revoked"},
            ):
                self.controller.set_account_backoff("acct-ea-core", until, "api key is invalid or revoked")

            with self.controller.db() as conn:
                core_row = conn.execute("SELECT backoff_until, last_error FROM accounts WHERE alias='acct-ea-core'").fetchone()
                repair_row = conn.execute("SELECT backoff_until, last_error FROM accounts WHERE alias='acct-ea-repair'").fetchone()

        self.assertEqual(core_row["backoff_until"], self.controller.iso(until))
        self.assertEqual(repair_row["backoff_until"], self.controller.iso(until))
        self.assertIn("api key is invalid or revoked", str(core_row["last_error"] or ""))
        self.assertIn("api key is invalid or revoked", str(repair_row["last_error"] or ""))

    def test_set_account_auth_failure_backoff_applies_even_when_same_ea_source_still_has_active_run(self) -> None:
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
                    INSERT INTO projects(id, path, queue_json, status, queue_index, updated_at)
                    VALUES('fleet', ?, '[]', 'ready', 0, ?)
                    """,
                    (str(root), now),
                )
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES('acct-ea-core', 'ea', '[]', 4, 'ready', ?)
                    """,
                    (now,),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        project_id, account_alias, slice_name, status, model, started_at, job_kind
                    )
                    VALUES('fleet', 'acct-ea-core', 'Active feeder run', 'running', 'ea-coder-hard-batch', ?, 'coding')
                    """,
                    (now,),
                )

            until = self.controller.utc_now() + self.controller.dt.timedelta(minutes=5)
            applied = self.controller.set_account_auth_failure_backoff(
                "acct-ea-core",
                until,
                "authentication failed for this account; recheck at later",
                exclude_run_id=9999,
            )

            self.assertTrue(applied)
            with self.controller.db() as conn:
                row = conn.execute(
                    "SELECT backoff_until, last_error FROM accounts WHERE alias='acct-ea-core'"
                ).fetchone()
            self.assertEqual(row["backoff_until"], self.controller.iso(until))
            self.assertEqual(row["last_error"], "authentication failed for this account; recheck at later")

    def test_set_account_auth_failure_backoff_applies_to_shared_chatgpt_source_even_with_active_sibling_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            auth_json = root / "shared-auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO projects(id, path, queue_json, status, queue_index, updated_at)
                    VALUES('fleet', ?, '[]', 'ready', 0, ?)
                    """,
                    (str(root), now),
                )
                for alias in ("acct-chatgpt-a", "acct-chatgpt-b"):
                    conn.execute(
                        """
                        INSERT INTO accounts(
                            alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                        )
                        VALUES(?, 'chatgpt_auth_json', ?, '[]', 1, 'ready', ?)
                        """,
                        (alias, str(auth_json), now),
                    )
                conn.execute(
                    """
                    INSERT INTO runs(
                        project_id, account_alias, slice_name, status, model, started_at, job_kind
                    )
                    VALUES('fleet', 'acct-chatgpt-b', 'Active shared auth run', 'running', 'gpt-5-mini', ?, 'coding')
                    """,
                    (now,),
                )

            until = self.controller.utc_now() + self.controller.dt.timedelta(minutes=5)
            applied = self.controller.set_account_auth_failure_backoff(
                "acct-chatgpt-a",
                until,
                "chatgpt auth session requires a fresh login",
                exclude_run_id=9999,
            )

            self.assertTrue(applied)
            with self.controller.db() as conn:
                rows = conn.execute(
                    "SELECT alias, backoff_until, last_error FROM accounts ORDER BY alias"
                ).fetchall()
            self.assertEqual(
                [(row["alias"], row["backoff_until"], row["last_error"]) for row in rows],
                [
                    ("acct-chatgpt-a", self.controller.iso(until), "chatgpt auth session requires a fresh login"),
                    ("acct-chatgpt-b", self.controller.iso(until), "chatgpt auth session requires a fresh login"),
                ],
            )

    def test_record_account_run_outcome_success_clears_shared_auth_failure_backoff_once_source_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            auth_json = root / "shared-auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            until = self.controller.utc_now() + self.controller.dt.timedelta(minutes=5)
            with self.controller.db() as conn:
                for alias in ("acct-chatgpt-a", "acct-chatgpt-b"):
                    conn.execute(
                        """
                        INSERT INTO accounts(
                            alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs,
                            health_state, backoff_until, last_error, updated_at
                        )
                        VALUES(?, 'chatgpt_auth_json', ?, '[]', 1, 'ready', ?, 'authentication failed for this account; recheck at later', ?)
                        """,
                        (alias, str(auth_json), self.controller.iso(until), now),
                    )

            self.controller.record_account_run_outcome("acct-chatgpt-a", "gpt-5.3-codex", success=True)

            with self.controller.db() as conn:
                rows = conn.execute(
                    "SELECT alias, backoff_until, last_error, success_count FROM accounts ORDER BY alias"
                ).fetchall()

        self.assertEqual(
            [(row["alias"], row["backoff_until"], row["last_error"], row["success_count"]) for row in rows],
            [
                ("acct-chatgpt-a", None, None, 1),
                ("acct-chatgpt-b", None, None, 0),
            ],
        )

    def test_run_command_handles_closed_stdin_transport_without_controller_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            log_path = root / "run.jsonl"

            class FakeStdout:
                async def read(self, _size: int) -> bytes:
                    return b""

            class FakeStdin:
                def write(self, _data: bytes) -> None:
                    return None

                async def drain(self) -> None:
                    raise RuntimeError(
                        "unable to perform operation on <WriteUnixTransport closed=True reading=False 0x0>; the handler is closed"
                    )

                def close(self) -> None:
                    return None

            class FakeProc:
                def __init__(self) -> None:
                    self.stdin = FakeStdin()
                    self.stdout = FakeStdout()
                    self.returncode = 17
                    self.pid = 1234

                async def wait(self) -> int:
                    self.returncode = 17
                    return 17

            async def _run() -> self.controller.CommandResult:
                with mock.patch.object(
                    self.controller.asyncio,
                    "create_subprocess_exec",
                    return_value=FakeProc(),
                ):
                    return await self.controller.run_command(
                        ["fake-cmd"],
                        input_text="prompt",
                        log_path=log_path,
                        timeout_seconds=5,
                    )

            result = asyncio.run(_run())
            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(result.exit_code, 17)
        self.assertFalse(result.timed_out)
        self.assertIn("controller.stdin_error", log_text)

    def test_set_account_backoff_queues_shared_api_key_alert_only_after_repair_probe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            old_outbox = self.controller.MAIL_OUTBOX_ROOT
            old_state = self.controller.MAIL_STATE_PATH
            old_to = self.controller.CREDENTIAL_ALERT_TO
            old_from = self.controller.CREDENTIAL_ALERT_FROM
            self.controller.MAIL_OUTBOX_ROOT = root / "mail-outbox"
            self.controller.MAIL_STATE_PATH = root / "mail-state.json"
            self.controller.CREDENTIAL_ALERT_TO = "ops@example.com"
            self.controller.CREDENTIAL_ALERT_FROM = "fleet@chummer.run"
            self.addCleanup(setattr, self.controller, "MAIL_OUTBOX_ROOT", old_outbox)
            self.addCleanup(setattr, self.controller, "MAIL_STATE_PATH", old_state)
            self.addCleanup(setattr, self.controller, "CREDENTIAL_ALERT_TO", old_to)
            self.addCleanup(setattr, self.controller, "CREDENTIAL_ALERT_FROM", old_from)
            self.controller.init_db()

            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                for alias in ("acct-ea-core", "acct-ea-fleet"):
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
            with mock.patch.object(
                self.controller,
                "run_credential_repair_command",
                return_value={"status": "attempted", "reason": "browseract tried rotating the shared key"},
            ), mock.patch.object(
                self.controller,
                "probe_api_key_credential_source",
                return_value={"status": "auth_failed", "reason": "api key is invalid or revoked"},
            ):
                self.controller.set_account_backoff("acct-ea-core", until, "api key is invalid or revoked")

            outbox = sorted(self.controller.MAIL_OUTBOX_ROOT.glob("*.eml"))
            self.assertEqual(len(outbox), 1)
            body = outbox[0].read_text(encoding="utf-8")
            self.assertIn("From: fleet@chummer.run", body)
            self.assertIn("To: ops@example.com", body)
            self.assertIn("acct-ea-core, acct-ea-fleet", body)
            self.assertIn("browseract tried rotating the shared key", body)

    def test_set_account_backoff_suppresses_api_key_alert_when_repair_recovery_probe_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            old_outbox = self.controller.MAIL_OUTBOX_ROOT
            old_state = self.controller.MAIL_STATE_PATH
            self.controller.MAIL_OUTBOX_ROOT = root / "mail-outbox"
            self.controller.MAIL_STATE_PATH = root / "mail-state.json"
            self.addCleanup(setattr, self.controller, "MAIL_OUTBOX_ROOT", old_outbox)
            self.addCleanup(setattr, self.controller, "MAIL_STATE_PATH", old_state)
            self.controller.init_db()

            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, api_key_env, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES('acct-ea-core', 'api_key', 'OPENAI_API_KEY', '[]', 1, 'ready', ?)
                    """,
                    (now,),
                )

            until = self.controller.utc_now() + self.controller.dt.timedelta(minutes=15)
            with mock.patch.object(
                self.controller,
                "run_credential_repair_command",
                return_value={"status": "attempted", "reason": "browseract rotated the key"},
            ), mock.patch.object(
                self.controller,
                "probe_api_key_credential_source",
                return_value={"status": "ready", "reason": "key works again"},
            ):
                self.controller.set_account_backoff("acct-ea-core", until, "api key is invalid or revoked")

            self.assertEqual(list(self.controller.MAIL_OUTBOX_ROOT.glob("*.eml")), [])

    def test_set_account_backoff_requires_second_shared_chatgpt_failure_before_alerting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            old_outbox = self.controller.MAIL_OUTBOX_ROOT
            old_state = self.controller.MAIL_STATE_PATH
            old_to = self.controller.CREDENTIAL_ALERT_TO
            self.controller.MAIL_OUTBOX_ROOT = root / "mail-outbox"
            self.controller.MAIL_STATE_PATH = root / "mail-state.json"
            self.controller.CREDENTIAL_ALERT_TO = "ops@example.com"
            self.addCleanup(setattr, self.controller, "MAIL_OUTBOX_ROOT", old_outbox)
            self.addCleanup(setattr, self.controller, "MAIL_STATE_PATH", old_state)
            self.addCleanup(setattr, self.controller, "CREDENTIAL_ALERT_TO", old_to)
            self.controller.init_db()

            auth_json = root / "shared-auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                for alias in ("acct-ea-a", "acct-ui-a"):
                    conn.execute(
                        """
                        INSERT INTO accounts(
                            alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at
                        )
                        VALUES(?, 'chatgpt_auth_json', ?, '[]', 1, 'ready', ?)
                        """,
                        (alias, str(auth_json), now),
                    )

            until = self.controller.utc_now() + self.controller.dt.timedelta(minutes=15)
            with mock.patch.object(
                self.controller,
                "run_credential_repair_command",
                return_value={"status": "not_configured", "reason": "credential repair command is not configured"},
            ):
                self.controller.set_account_backoff(
                    "acct-ea-a",
                    until,
                    "chatgpt auth refresh token was invalidated by another session",
                )
                self.assertEqual(list(self.controller.MAIL_OUTBOX_ROOT.glob("*.eml")), [])
                self.controller.set_account_backoff(
                    "acct-ui-a",
                    until,
                    "chatgpt auth refresh token was invalidated by another session",
                )

            outbox = sorted(self.controller.MAIL_OUTBOX_ROOT.glob("*.eml"))
            self.assertEqual(len(outbox), 1)
            body = outbox[0].read_text(encoding="utf-8")
            self.assertIn("acct-ea-a, acct-ui-a", body)
            self.assertIn("ops@example.com", body)

    def test_read_api_key_falls_back_to_live_runtime_env_file_when_process_env_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_env = root / "runtime.env"
            runtime_env.write_text("OPENAI_API_KEY=sk-local-rotated\n", encoding="utf-8")
            old_mount_root = self.controller.FLEET_MOUNT_ROOT
            old_override = self.controller._SECRET_ENV_PATHS_OVERRIDE
            self.controller.FLEET_MOUNT_ROOT = root
            self.controller._SECRET_ENV_PATHS_OVERRIDE = ""
            self.addCleanup(setattr, self.controller, "FLEET_MOUNT_ROOT", old_mount_root)
            self.addCleanup(setattr, self.controller, "_SECRET_ENV_PATHS_OVERRIDE", old_override)

            with mock.patch.dict(self.controller.os.environ, {"OPENAI_API_KEY": ""}, clear=False):
                resolved = self.controller.read_api_key({"api_key_env": "OPENAI_API_KEY"})

            self.assertEqual(resolved, "sk-local-rotated")

    def test_prepare_account_environment_injects_live_runtime_env_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_env = root / "runtime.env"
            runtime_env.write_text("OPENAI_API_KEY=sk-live-runtime\n", encoding="utf-8")
            old_mount_root = self.controller.FLEET_MOUNT_ROOT
            old_override = self.controller._SECRET_ENV_PATHS_OVERRIDE
            old_homes = self.controller.CODEX_HOME_ROOT
            self.controller.FLEET_MOUNT_ROOT = root
            self.controller._SECRET_ENV_PATHS_OVERRIDE = ""
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.addCleanup(setattr, self.controller, "FLEET_MOUNT_ROOT", old_mount_root)
            self.addCleanup(setattr, self.controller, "_SECRET_ENV_PATHS_OVERRIDE", old_override)
            self.addCleanup(setattr, self.controller, "CODEX_HOME_ROOT", old_homes)

            with mock.patch.dict(self.controller.os.environ, {"OPENAI_API_KEY": ""}, clear=False):
                env = self.controller.prepare_account_environment(
                    "acct-ea-core",
                    {"auth_kind": "api_key", "api_key_env": "OPENAI_API_KEY"},
                )

            self.assertEqual(env["CODEX_API_KEY"], "sk-live-runtime")

    def test_prepare_account_environment_prefers_live_runtime_env_over_container_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_env = root / "runtime.env"
            runtime_env.write_text("OPENAI_API_KEY=sk-file-fresh\n", encoding="utf-8")
            old_mount_root = self.controller.FLEET_MOUNT_ROOT
            old_override = self.controller._SECRET_ENV_PATHS_OVERRIDE
            old_homes = self.controller.CODEX_HOME_ROOT
            self.controller.FLEET_MOUNT_ROOT = root
            self.controller._SECRET_ENV_PATHS_OVERRIDE = ""
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.addCleanup(setattr, self.controller, "FLEET_MOUNT_ROOT", old_mount_root)
            self.addCleanup(setattr, self.controller, "_SECRET_ENV_PATHS_OVERRIDE", old_override)
            self.addCleanup(setattr, self.controller, "CODEX_HOME_ROOT", old_homes)

            with mock.patch.dict(self.controller.os.environ, {"OPENAI_API_KEY": "sk-container-stale"}, clear=False):
                env = self.controller.prepare_account_environment(
                    "acct-ea-core",
                    {"auth_kind": "api_key", "api_key_env": "OPENAI_API_KEY"},
                )

            self.assertEqual(env["CODEX_API_KEY"], "sk-file-fresh")

    def test_credential_source_label_identifies_local_env_file_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_env = root / "runtime.env"
            runtime_env.write_text("OPENAI_API_KEY=sk-live-runtime\n", encoding="utf-8")
            old_mount_root = self.controller.FLEET_MOUNT_ROOT
            old_override = self.controller._SECRET_ENV_PATHS_OVERRIDE
            self.controller.FLEET_MOUNT_ROOT = root
            self.controller._SECRET_ENV_PATHS_OVERRIDE = ""
            self.addCleanup(setattr, self.controller, "FLEET_MOUNT_ROOT", old_mount_root)
            self.addCleanup(setattr, self.controller, "_SECRET_ENV_PATHS_OVERRIDE", old_override)

            with mock.patch.dict(self.controller.os.environ, {"OPENAI_API_KEY": ""}, clear=False):
                label = self.controller.credential_source_label({"auth_kind": "api_key", "api_key_env": "OPENAI_API_KEY"})

            self.assertEqual(label, f"local env file {runtime_env}::OPENAI_API_KEY")

    def test_prepare_account_environment_ea_runtime_exports_ea_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            old_mount_root = self.controller.FLEET_MOUNT_ROOT
            old_homes = self.controller.CODEX_HOME_ROOT
            self.controller.FLEET_MOUNT_ROOT = root
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.addCleanup(setattr, self.controller, "FLEET_MOUNT_ROOT", old_mount_root)
            self.addCleanup(setattr, self.controller, "CODEX_HOME_ROOT", old_homes)

            with mock.patch.dict(
                self.controller.os.environ,
                {
                    "EA_MCP_BASE_URL": "http://host.docker.internal:8090",
                    "EA_MCP_API_TOKEN": "secret-token",
                    "EA_MCP_PRINCIPAL_ID": "codex-fleet",
                },
                clear=False,
            ):
                env = self.controller.prepare_account_environment("acct-ea-core", {"auth_kind": "ea"})

            self.assertNotIn("CODEX_API_KEY", env)
            self.assertEqual(env["EA_BASE_URL"], "http://host.docker.internal:8090")
            self.assertEqual(env["EA_API_TOKEN"], "secret-token")
            self.assertEqual(env["EA_PRINCIPAL_ID"], "codex-fleet")
            self.assertTrue(env["FLEET_RUNTIME_EA_ENV_PATH"].endswith("runtime.ea.env"))

    def test_resolved_ea_runtime_settings_falls_back_to_local_ea_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_ea_env = root / "runtime.ea.env"
            runtime_ea_env.write_text(
                "EA_MCP_BASE_URL=http://host.docker.internal:8090\nEA_MCP_PRINCIPAL_ID=codex-fleet\n",
                encoding="utf-8",
            )
            local_ea_env = root / "ea.env"
            local_ea_env.write_text("EA_API_TOKEN=secret-token-from-ea-env\n", encoding="utf-8")
            old_mount_root = self.controller.FLEET_MOUNT_ROOT
            old_override = self.controller._SECRET_ENV_PATHS_OVERRIDE
            self.controller.FLEET_MOUNT_ROOT = root
            self.controller._SECRET_ENV_PATHS_OVERRIDE = f"{runtime_ea_env}:{local_ea_env}"
            self.addCleanup(setattr, self.controller, "FLEET_MOUNT_ROOT", old_mount_root)
            self.addCleanup(setattr, self.controller, "_SECRET_ENV_PATHS_OVERRIDE", old_override)

            with mock.patch.dict(
                self.controller.os.environ,
                {"EA_MCP_BASE_URL": "", "EA_BASE_URL": "", "EA_MCP_API_TOKEN": "", "EA_API_TOKEN": "", "EA_MCP_PRINCIPAL_ID": "", "EA_PRINCIPAL_ID": ""},
                clear=False,
            ):
                settings = self.controller.resolved_ea_runtime_settings()

            self.assertEqual(settings["base_url"], "http://host.docker.internal:8090")
            self.assertEqual(settings["api_token"], "secret-token-from-ea-env")
            self.assertEqual(settings["principal_id"], "codex-fleet")

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

    def test_easy_capacity_shifts_to_groundwork_before_survival(self) -> None:
        slice_item = {"title": "Backfill admin queue status counters"}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": {"state": "cooldown", "providers": []},
                        "repair": {"state": "ready", "providers": []},
                        "groundwork": {"state": "ready", "providers": []},
                        "core": {"state": "ready", "providers": []},
                        "survival": {"state": "ready", "providers": []},
                    },
                ):
                    decision = self.controller.classify_tier({"lanes": {}}, {"id": "fleet"}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["lane_submode"], "responses_groundwork")
        self.assertEqual(decision["escalation_reason"], "easy_capacity_shifted_to_groundwork")
        self.assertIn("groundwork", decision["allowed_lanes"])

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

    def test_ea_onemin_manager_status_falls_back_to_persisted_runtime_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.controller.DB_PATH = Path(tmpdir) / "fleet.db"
            self.controller.LOG_DIR = Path(tmpdir) / "logs"
            self.controller.CODEX_HOME_ROOT = Path(tmpdir) / "homes"
            self.controller.GROUP_ROOT = Path(tmpdir) / "groups"
            self.controller.init_db()
            self.controller._EA_ONEMIN_MANAGER_CACHE = {"fetched_at": 0.0, "payload": {}}
            persisted = {
                "aggregate": {"sum_free_credits": 910000, "accounts": []},
                "runway": {"next_topup_at": "2026-03-31T00:00:00Z"},
            }
            self.controller.save_runtime_cache(self.controller.RUNTIME_CACHE_KEY_EA_ONEMIN_MANAGER_STATUS, persisted)

            with mock.patch("urllib.request.urlopen", side_effect=OSError("ea-down")):
                payload = self.controller.ea_onemin_manager_status(force=True)

        self.assertEqual(payload["aggregate"]["sum_free_credits"], 910000)

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
                self.controller.RUNTIME_CACHE_KEY_EA_ONEMIN_MANAGER_STATUS,
                {
                    "aggregate": {
                        "sum_free_credits": 2000000,
                        "sum_max_credits": 4000000,
                        "accounts": [
                            {
                                "slot_count": 1,
                                "last_billing_snapshot_at": "2026-03-23T10:00:00Z",
                                "last_member_reconciliation_at": "2026-03-23T10:00:00Z",
                            }
                        ],
                    },
                    "runway": {
                        "hours_remaining_current_pace": 20,
                        "next_topup_at": self.controller.iso(self.controller.utc_now() + self.controller.dt.timedelta(hours=10)),
                    },
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

    def test_participant_burst_hint_only_autoscale_does_not_become_runtime_authority(self) -> None:
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
                                "authority": "capacity_plan_hint_only",
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
                self.controller.RUNTIME_CACHE_KEY_EA_ONEMIN_MANAGER_STATUS,
                {
                    "aggregate": {
                        "sum_free_credits": 2000000,
                        "sum_max_credits": 4000000,
                        "accounts": [
                            {
                                "slot_count": 1,
                                "last_billing_snapshot_at": "2026-03-23T10:00:00Z",
                                "last_member_reconciliation_at": "2026-03-23T10:00:00Z",
                            }
                        ],
                    },
                    "runway": {
                        "hours_remaining_current_pace": 20,
                        "next_topup_at": self.controller.iso(self.controller.utc_now() + self.controller.dt.timedelta(hours=10)),
                    },
                },
            )

            lane_one = self.controller.create_participant_lane_record(
                config,
                {"project_id": "core", "subject_id": "pilot-1", "subject_label": "Pilot One"},
            )
            self.controller.participant_lane_auth_path(lane_one["lane_id"]).write_text("{}", encoding="utf-8")

            metrics = self.controller.participant_burst_metrics(config, "core")

            self.assertEqual(metrics["autoscale_authority"], "capacity_plan_hint_only")
            self.assertEqual(metrics["local_hint_recommended_workers"], 3)
            self.assertEqual(metrics["effective_max_active_workers"], 1)
            self.assertEqual(metrics["mode"], "surge")

    def test_quartermaster_capacity_reconcile_subtracts_active_usage_and_reserved_launches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            self.controller._QUARTERMASTER_RECONCILE_CACHE = {"fetched_at": 0.0, "plan_generated_at": "", "payload": {}}

            config = {
                "projects": [{"id": "core", "path": str(repo_root)}],
                "accounts": {
                    "acct-ea-core": {
                        "lane": "core",
                        "auth_kind": "api_key",
                        "codex_model_aliases": ["ea-coder-hard"],
                    }
                },
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
            }
            self.controller.sync_config_to_db(config)
            now = self.controller.utc_now()
            with self.controller.db() as conn:
                run_id = conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'Ship core booster slice', 'running', 'ea-coder-hard', 'low', 'bounded_fix', 'quartermaster-test', ?, '', '', '')
                    """,
                    ("core", "acct-ea-core", self.controller.iso(now)),
                ).lastrowid
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', 'feedback', '', '[]', 0, 0, 'running', 'Ship core booster slice', ?, NULL, ?, '', 'bounded_fix', 'ea-coder-hard', 'quartermaster-test', ?)
                    ON CONFLICT(id) DO UPDATE SET
                        path=excluded.path,
                        status=excluded.status,
                        current_slice=excluded.current_slice,
                        active_run_id=excluded.active_run_id,
                        last_run_at=excluded.last_run_at,
                        spider_tier=excluded.spider_tier,
                        spider_model=excluded.spider_model,
                        spider_reason=excluded.spider_reason,
                        updated_at=excluded.updated_at
                    """,
                    ("core", str(repo_root), int(run_id), self.controller.iso(now), self.controller.iso(now)),
                )
                conn.execute(
                    """
                    INSERT INTO spider_decisions(
                        project_id, slice_name, account_alias, selected_model, spider_tier, reason, estimated_prompt_chars, decision_meta_json, selection_trace_json, created_at
                    )
                    VALUES(?, 'Ship core booster slice', 'acct-ea-core', 'ea-coder-hard', 'bounded_fix', 'quartermaster-test', 128, ?, '[]', ?)
                    """,
                    (
                        "core",
                        json.dumps({"lane": "core", "requires_contract_authority": False, "task_meta": {}}),
                        self.controller.iso(now),
                    ),
                )

            plan = {
                "generated_at": "2026-03-23T10:00:00Z",
                "lane_targets": {
                    "core_booster": 2,
                    "core_authority": 1,
                },
            }

            snapshot = self.controller.quartermaster_capacity_reconcile(config, plan=plan)
            remaining, remaining_by_lane = self.controller.quartermaster_capacity_remaining(
                plan=plan,
                target_lane="core_booster",
                reserved_lane_counts={"core_booster": 1},
            )

            self.assertEqual(snapshot["usage_by_lane"]["core_booster"], 1)
            self.assertEqual(snapshot["remaining_by_lane"]["core_booster"], 1)
            self.assertEqual(remaining, 0)
            self.assertEqual(remaining_by_lane["core_booster"], 0)

    def test_quartermaster_non_authoritative_plan_blocks_launch(self) -> None:
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
                "projects": [{"id": "alpha", "path": str(repo_root), "queue": ["Ship stale-plan slice"]}],
                "accounts": {
                    "acct-ea-core": {
                        "lane": "core",
                        "auth_kind": "api_key",
                        "codex_model_aliases": ["ea-coder-hard"],
                    }
                },
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
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
                    VALUES(?, ?, '', '', 'feedback', '', ?, 0, 0, 'dispatch_pending', 'Ship stale-plan slice', NULL, NULL, NULL, '', '', '', '', ?)
                    ON CONFLICT(id) DO UPDATE SET queue_json=excluded.queue_json, queue_index=excluded.queue_index, updated_at=excluded.updated_at
                    """,
                    (
                        "alpha",
                        str(repo_root),
                        json.dumps(["Ship stale-plan slice"]),
                        self.controller.iso(self.controller.utc_now()),
                    ),
                )
                row = conn.execute("SELECT * FROM projects WHERE id='alpha'").fetchone()

            candidate = self.controller.prepare_dispatch_candidate(
                config,
                self.controller.get_project_cfg(config, "alpha"),
                row,
                self.controller.utc_now(),
            )
            decision = {
                "tier": "bounded_fix",
                "model_preferences": ["ea-coder-hard"],
                "reasoning_effort": "low",
                "estimated_prompt_chars": 256,
                "estimated_input_tokens": 128,
                "estimated_output_tokens": 128,
                "predicted_changed_files": 1,
                "requires_contract_authority": False,
                "reason": "test stale plan",
                "lane": "core",
                "task_meta": {"allowed_lanes": ["core"], "allow_credit_burn": True},
                "spark_eligible": False,
            }
            stale_generated_at = self.controller.iso(self.controller.utc_now() - self.controller.dt.timedelta(minutes=30))
            plan = {
                "generated_at": stale_generated_at,
                "mode": "enforce",
                "controller_tick": {"plan_ttl_seconds": 60, "max_scale_up_per_tick": 1},
                "lane_targets": {"core_booster": 1},
                "_quartermaster_status": {
                    "generated_at": stale_generated_at,
                    "cache_state": "stale",
                    "degraded": False,
                    "source": "cached_plan",
                },
            }

            with mock.patch.object(self.controller, "classify_tier", return_value=dict(decision)):
                with mock.patch.object(self.controller, "quartermaster_capacity_plan", return_value=plan):
                    with mock.patch.object(self.controller, "pick_account_and_model") as pick_account:
                        planned = self.controller.plan_candidate_launch(config, candidate, reserved_scale_up_count=0)

            self.assertIsNone(planned)
            self.assertFalse(pick_account.called)
            with self.controller.db() as conn:
                project_row = conn.execute("SELECT status, last_error FROM projects WHERE id='alpha'").fetchone()
            self.assertEqual(str(project_row["status"]), self.controller.WAITING_CAPACITY_STATUS)
            self.assertIn("not authoritative", str(project_row["last_error"] or ""))

    def test_quartermaster_scale_up_cap_blocks_second_launch_in_same_tick(self) -> None:
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
                "projects": [{"id": "beta", "path": str(repo_root), "queue": ["Ship capped slice"]}],
                "accounts": {
                    "acct-ea-core": {
                        "lane": "core",
                        "auth_kind": "api_key",
                        "codex_model_aliases": ["ea-coder-hard"],
                    }
                },
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
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
                    VALUES(?, ?, '', '', 'feedback', '', ?, 0, 0, 'dispatch_pending', 'Ship capped slice', NULL, NULL, NULL, '', '', '', '', ?)
                    ON CONFLICT(id) DO UPDATE SET queue_json=excluded.queue_json, queue_index=excluded.queue_index, updated_at=excluded.updated_at
                    """,
                    (
                        "beta",
                        str(repo_root),
                        json.dumps(["Ship capped slice"]),
                        self.controller.iso(self.controller.utc_now()),
                    ),
                )
                row = conn.execute("SELECT * FROM projects WHERE id='beta'").fetchone()

            candidate = self.controller.prepare_dispatch_candidate(
                config,
                self.controller.get_project_cfg(config, "beta"),
                row,
                self.controller.utc_now(),
            )
            decision = {
                "tier": "bounded_fix",
                "model_preferences": ["ea-coder-hard"],
                "reasoning_effort": "low",
                "estimated_prompt_chars": 256,
                "estimated_input_tokens": 128,
                "estimated_output_tokens": 128,
                "predicted_changed_files": 1,
                "requires_contract_authority": False,
                "reason": "test scale cap",
                "lane": "core",
                "task_meta": {"allowed_lanes": ["core"], "allow_credit_burn": True},
                "spark_eligible": False,
            }
            fresh_generated_at = self.controller.iso(self.controller.utc_now())
            plan = {
                "generated_at": fresh_generated_at,
                "mode": "enforce",
                "controller_tick": {"plan_ttl_seconds": 900, "max_scale_up_per_tick": 1},
                "lane_targets": {"core_booster": 2},
                "_quartermaster_status": {
                    "generated_at": fresh_generated_at,
                    "cache_state": "fresh",
                    "degraded": False,
                    "source": "live_admin",
                },
            }

            with mock.patch.object(self.controller, "classify_tier", return_value=dict(decision)):
                with mock.patch.object(self.controller, "quartermaster_capacity_plan", return_value=plan):
                    with mock.patch.object(self.controller, "pick_account_and_model") as pick_account:
                        planned = self.controller.plan_candidate_launch(config, candidate, reserved_scale_up_count=1)

            self.assertIsNone(planned)
            self.assertFalse(pick_account.called)
            with self.controller.db() as conn:
                project_row = conn.execute("SELECT status, last_error FROM projects WHERE id='beta'").fetchone()
            self.assertEqual(str(project_row["status"]), self.controller.WAITING_CAPACITY_STATUS)
            self.assertIn("max_scale_up_per_tick=1", str(project_row["last_error"] or ""))

    def test_quartermaster_enforce_mode_blocks_when_no_plan_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.QUARTERMASTER_PATH = root / "quartermaster.yaml"
            self.controller.QUARTERMASTER_PATH.write_text(
                "\n".join(
                    [
                        "quartermaster:",
                        "  enabled: true",
                        "  mode: enforce",
                        "  driver: controller_tick",
                        "  baseline_tick_seconds: 600",
                        "  event_tick_min_seconds: 90",
                        "  plan_ttl_seconds: 900",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.controller.init_db()
            config = {
                "projects": [{"id": "gamma", "path": str(repo_root), "queue": ["Ship empty-plan slice"]}],
                "accounts": {
                    "acct-ea-core": {
                        "lane": "core",
                        "auth_kind": "api_key",
                        "codex_model_aliases": ["ea-coder-hard"],
                    }
                },
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
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
                    VALUES(?, ?, '', '', 'feedback', '', ?, 0, 0, 'dispatch_pending', 'Ship empty-plan slice', NULL, NULL, NULL, '', '', '', '', ?)
                    ON CONFLICT(id) DO UPDATE SET queue_json=excluded.queue_json, queue_index=excluded.queue_index, updated_at=excluded.updated_at
                    """,
                    (
                        "gamma",
                        str(repo_root),
                        json.dumps(["Ship empty-plan slice"]),
                        self.controller.iso(self.controller.utc_now()),
                    ),
                )
                row = conn.execute("SELECT * FROM projects WHERE id='gamma'").fetchone()

            candidate = self.controller.prepare_dispatch_candidate(
                config,
                self.controller.get_project_cfg(config, "gamma"),
                row,
                self.controller.utc_now(),
            )
            decision = {
                "tier": "bounded_fix",
                "model_preferences": ["ea-coder-hard"],
                "reasoning_effort": "low",
                "estimated_prompt_chars": 256,
                "estimated_input_tokens": 128,
                "estimated_output_tokens": 128,
                "predicted_changed_files": 1,
                "requires_contract_authority": False,
                "reason": "test empty plan",
                "lane": "core",
                "task_meta": {"allowed_lanes": ["core"], "allow_credit_burn": True},
                "spark_eligible": False,
            }

            with mock.patch.object(self.controller, "classify_tier", return_value=dict(decision)):
                with mock.patch.object(self.controller, "quartermaster_capacity_plan", return_value={}):
                    with mock.patch.object(self.controller, "pick_account_and_model") as pick_account:
                        planned = self.controller.plan_candidate_launch(config, candidate)

            self.assertIsNone(planned)
            self.assertFalse(pick_account.called)
            with self.controller.db() as conn:
                project_row = conn.execute("SELECT status, last_error FROM projects WHERE id='gamma'").fetchone()
            self.assertEqual(str(project_row["status"]), self.controller.WAITING_CAPACITY_STATUS)
            self.assertIn("not authoritative", str(project_row["last_error"] or ""))

    def test_quartermaster_capacity_drain_respects_dwell_and_max_scale_down(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_alpha = root / "alpha"
            repo_beta = root / "beta"
            repo_alpha.mkdir()
            repo_beta.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.QUARTERMASTER_PATH = root / "quartermaster.yaml"
            self.controller.QUARTERMASTER_PATH.write_text(
                "\n".join(
                    [
                        "quartermaster:",
                        "  enabled: true",
                        "  mode: enforce",
                        "  driver: controller_tick",
                        "  baseline_tick_seconds: 600",
                        "  event_tick_min_seconds: 90",
                        "  plan_ttl_seconds: 900",
                        "  max_scale_down_per_tick: 1",
                        "  min_worker_dwell_seconds: 900",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.controller.init_db()
            self.controller.state.tasks.clear()
            self.controller._RUNTIME_INTERRUPT_OVERRIDES.clear()
            config = {
                "projects": [
                    {"id": "alpha", "path": str(repo_alpha)},
                    {"id": "beta", "path": str(repo_beta)},
                ],
                "accounts": {
                    "acct-ea-core-a": {"lane": "core", "auth_kind": "api_key", "codex_model_aliases": ["ea-coder-hard"]},
                    "acct-ea-core-b": {"lane": "core", "auth_kind": "api_key", "codex_model_aliases": ["ea-coder-hard"]},
                },
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
            }
            self.controller.sync_config_to_db(config)
            now = self.controller.utc_now()
            old_started_at = now - self.controller.dt.timedelta(minutes=20)
            recent_started_at = now - self.controller.dt.timedelta(minutes=5)
            with self.controller.db() as conn:
                alpha_run_id = conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'Alpha slice', 'running', 'ea-coder-hard', 'low', 'bounded_fix', 'quartermaster-test', ?, '', '', '')
                    """,
                    ("alpha", "acct-ea-core-a", self.controller.iso(old_started_at)),
                ).lastrowid
                beta_run_id = conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'Beta slice', 'running', 'ea-coder-hard', 'low', 'bounded_fix', 'quartermaster-test', ?, '', '', '')
                    """,
                    ("beta", "acct-ea-core-b", self.controller.iso(recent_started_at)),
                ).lastrowid
                for project_id, repo_path, run_id, slice_name in [
                    ("alpha", repo_alpha, alpha_run_id, "Alpha slice"),
                    ("beta", repo_beta, beta_run_id, "Beta slice"),
                ]:
                    conn.execute(
                        """
                        INSERT INTO projects(
                            id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                            consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                            last_error, spider_tier, spider_model, spider_reason, updated_at
                        )
                        VALUES(?, ?, '', '', 'feedback', '', '[]', 0, 0, 'running', ?, ?, NULL, ?, '', 'bounded_fix', 'ea-coder-hard', 'quartermaster-test', ?)
                        ON CONFLICT(id) DO UPDATE SET
                            path=excluded.path,
                            status=excluded.status,
                            current_slice=excluded.current_slice,
                            active_run_id=excluded.active_run_id,
                            last_run_at=excluded.last_run_at,
                            spider_tier=excluded.spider_tier,
                            spider_model=excluded.spider_model,
                            spider_reason=excluded.spider_reason,
                            updated_at=excluded.updated_at
                        """,
                        (project_id, str(repo_path), slice_name, int(run_id), self.controller.iso(now), self.controller.iso(now)),
                    )
                    conn.execute(
                        """
                        INSERT INTO spider_decisions(
                            project_id, slice_name, account_alias, selected_model, spider_tier, reason, estimated_prompt_chars, decision_meta_json, selection_trace_json, created_at
                        )
                        VALUES(?, ?, ?, 'ea-coder-hard', 'bounded_fix', 'quartermaster-test', 128, ?, '[]', ?)
                        """,
                        (
                            project_id,
                            slice_name,
                            "acct-ea-core-a" if project_id == "alpha" else "acct-ea-core-b",
                            json.dumps({"lane": "core", "requires_contract_authority": False, "task_meta": {}}),
                            self.controller.iso(now),
                        ),
                    )

            class DummyTask:
                def __init__(self) -> None:
                    self.cancelled = False

                def done(self) -> bool:
                    return False

                def cancel(self) -> bool:
                    self.cancelled = True
                    return True

            alpha_task = DummyTask()
            beta_task = DummyTask()
            self.controller.state.tasks["alpha"] = alpha_task
            self.controller.state.tasks["beta"] = beta_task
            plan_generated_at = self.controller.iso(now)
            plan = {
                "generated_at": plan_generated_at,
                "mode": "enforce",
                "controller_tick": {"plan_ttl_seconds": 900, "max_scale_down_per_tick": 1},
                "lane_targets": {"core_booster": 0},
                "_quartermaster_status": {
                    "generated_at": plan_generated_at,
                    "cache_state": "fresh",
                    "degraded": False,
                    "source": "live_admin",
                },
            }

            drained = self.controller.quartermaster_capacity_drain(config, plan=plan)

            self.assertEqual(drained["cancelled_count"], 1)
            self.assertEqual(drained["drained_projects"], ["alpha"])
            self.assertTrue(alpha_task.cancelled)
            self.assertFalse(beta_task.cancelled)
            self.assertIn("alpha", self.controller._RUNTIME_INTERRUPT_OVERRIDES)

    def test_quartermaster_tick_if_due_does_not_accept_stale_degraded_tick(self) -> None:
        self.controller._QUARTERMASTER_TICK_CACHE.clear()
        stale_generated_at = self.controller.iso(self.controller.utc_now() - self.controller.dt.timedelta(hours=1))
        stale_plan = {
            "generated_at": stale_generated_at,
            "mode": "enforce",
            "controller_tick": {"plan_ttl_seconds": 900},
            "lane_targets": {"core_booster": 1},
            "_quartermaster_status": {
                "generated_at": stale_generated_at,
                "cache_state": "stale",
                "degraded": True,
                "source": "persisted_capacity_plan",
            },
        }

        with mock.patch.object(
            self.controller,
            "quartermaster_tick_policy",
            return_value={
                "enabled": True,
                "driver": "controller_tick",
                "baseline_tick_seconds": 600,
                "event_tick_min_seconds": 90,
                "triggers": ["review_backpressure"],
                "plan_ttl_seconds": 900,
            },
        ):
            with mock.patch.object(self.controller, "quartermaster_event_snapshot", return_value={"review_backpressure": 1}):
                with mock.patch.object(self.controller, "quartermaster_capacity_tick", return_value=stale_plan):
                    with mock.patch.object(self.controller, "load_runtime_cache", return_value=({}, None)):
                        with mock.patch.object(self.controller, "save_runtime_cache") as save_runtime_cache:
                            returned = self.controller.quartermaster_tick_if_due({})

        self.assertEqual(returned, stale_plan)
        self.assertEqual(float(self.controller._QUARTERMASTER_TICK_CACHE.get("last_tick_at") or 0.0), 0.0)
        self.assertEqual(str(self.controller._QUARTERMASTER_TICK_CACHE.get("event_signature") or ""), "")
        save_runtime_cache.assert_not_called()

    def test_quartermaster_capacity_drain_skips_finished_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_alpha = root / "alpha"
            repo_alpha.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.QUARTERMASTER_PATH = root / "quartermaster.yaml"
            self.controller.QUARTERMASTER_PATH.write_text(
                "\n".join(
                    [
                        "quartermaster:",
                        "  enabled: true",
                        "  mode: enforce",
                        "  driver: controller_tick",
                        "  baseline_tick_seconds: 600",
                        "  event_tick_min_seconds: 90",
                        "  plan_ttl_seconds: 900",
                        "  max_scale_down_per_tick: 1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.controller.init_db()
            self.controller.state.tasks.clear()
            config = {
                "projects": [{"id": "alpha", "path": str(repo_alpha)}],
                "accounts": {"acct-ea-core": {"lane": "core", "auth_kind": "api_key", "codex_model_aliases": ["ea-coder-hard"]}},
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
            }
            self.controller.sync_config_to_db(config)
            now = self.controller.utc_now()
            started_at = now - self.controller.dt.timedelta(minutes=10)
            finished_at = now - self.controller.dt.timedelta(seconds=5)
            with self.controller.db() as conn:
                run_id = conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, finished_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'Alpha slice', 'complete', 'ea-coder-hard', 'low', 'bounded_fix', 'quartermaster-test', ?, ?, '', '', '')
                    """,
                    ("alpha", "acct-ea-core", self.controller.iso(started_at), self.controller.iso(finished_at)),
                ).lastrowid
                conn.execute(
                    """
                    UPDATE projects
                    SET status='running',
                        current_slice='Alpha slice',
                        active_run_id=?,
                        last_run_at=?,
                        spider_tier='bounded_fix',
                        spider_model='ea-coder-hard',
                        spider_reason='quartermaster-test'
                    WHERE id='alpha'
                    """,
                    (int(run_id), self.controller.iso(now)),
                )
                conn.execute(
                    """
                    INSERT INTO spider_decisions(
                        project_id, slice_name, account_alias, selected_model, spider_tier, reason, estimated_prompt_chars, decision_meta_json, selection_trace_json, created_at
                    )
                    VALUES(?, ?, ?, 'ea-coder-hard', 'bounded_fix', 'quartermaster-test', 128, ?, '[]', ?)
                    """,
                    (
                        "alpha",
                        "Alpha slice",
                        "acct-ea-core",
                        json.dumps({"lane": "core", "requires_contract_authority": False, "task_meta": {}}),
                        self.controller.iso(now),
                    ),
                )
            plan_generated_at = self.controller.iso(now)
            plan = {
                "generated_at": plan_generated_at,
                "mode": "enforce",
                "controller_tick": {"plan_ttl_seconds": 900, "max_scale_down_per_tick": 1},
                "lane_targets": {"core_booster": 0},
                "_quartermaster_status": {
                    "generated_at": plan_generated_at,
                    "cache_state": "fresh",
                    "degraded": False,
                    "source": "live_admin",
                },
            }

            drained = self.controller.quartermaster_capacity_drain(config, plan=plan)

            self.assertEqual(drained["cancelled_count"], 0)
            self.assertEqual(drained["drained_projects"], [])
            with self.controller.db() as conn:
                run_row = conn.execute("SELECT status, finished_at FROM runs WHERE id=?", (int(run_id),)).fetchone()
                project_row = conn.execute("SELECT status, active_run_id FROM projects WHERE id='alpha'").fetchone()
            self.assertEqual(str(run_row["status"]), "complete")
            self.assertEqual(str(run_row["finished_at"]), self.controller.iso(finished_at))
            self.assertEqual(str(project_row["status"]), "running")
            self.assertEqual(int(project_row["active_run_id"] or 0), int(run_id))

    def test_quartermaster_event_snapshot_does_not_flag_active_core_boosters_as_idle(self) -> None:
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
                "policies": {"stale_heartbeat_seconds": 1800},
                "projects": [{"id": "core", "path": str(repo_root)}],
                "accounts": {"acct-ea-core": {"lane": "core", "auth_kind": "api_key", "codex_model_aliases": ["ea-coder-hard"]}},
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
            }
            self.controller.sync_config_to_db(config)
            now = self.controller.utc_now()
            with self.controller.db() as conn:
                run_id = conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'Ship active booster slice', 'running', 'ea-coder-hard', 'low', 'bounded_fix', 'quartermaster-test', ?, '', '', '')
                    """,
                    ("core", "acct-ea-core", self.controller.iso(now - self.controller.dt.timedelta(minutes=10))),
                ).lastrowid
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', 'feedback', '', '[]', 0, 0, 'running', 'Ship active booster slice', ?, NULL, ?, '', 'bounded_fix', 'ea-coder-hard', 'quartermaster-test', ?)
                    ON CONFLICT(id) DO UPDATE SET
                        path=excluded.path,
                        status=excluded.status,
                        current_slice=excluded.current_slice,
                        active_run_id=excluded.active_run_id,
                        last_run_at=excluded.last_run_at,
                        spider_tier=excluded.spider_tier,
                        spider_model=excluded.spider_model,
                        spider_reason=excluded.spider_reason,
                        updated_at=excluded.updated_at
                    """,
                    ("core", str(repo_root), int(run_id), self.controller.iso(now), self.controller.iso(now)),
                )
                conn.execute(
                    """
                    INSERT INTO spider_decisions(
                        project_id, slice_name, account_alias, selected_model, spider_tier, reason, estimated_prompt_chars, decision_meta_json, selection_trace_json, created_at
                    )
                    VALUES(?, 'Ship active booster slice', 'acct-ea-core', 'ea-coder-hard', 'bounded_fix', 'quartermaster-test', 128, ?, '[]', ?)
                    """,
                    (
                        "core",
                        json.dumps({"lane": "core", "requires_contract_authority": False, "task_meta": {}}),
                        self.controller.iso(now),
                    ),
                )

            with mock.patch.object(self.controller, "ea_onemin_manager_billing_aggregate", return_value={}):
                with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value={"core": {"providers": []}}):
                    snapshot = self.controller.quartermaster_event_snapshot(config)

            self.assertEqual(snapshot["booster_idle"], 0)

    def test_quartermaster_event_snapshot_flags_booster_supply_starvation(self) -> None:
        config = {
            "quartermaster": {
                "useful_work": {
                    "ready_reserve_multiplier": 2,
                    "minimum_ready_packages": 2,
                    "packages_per_authority_worker": 4,
                }
            },
            "policies": {"capacity_plane": {"plane_caps": {"global_booster_cap": 6}}},
            "projects": [
                {
                    "id": "fleet",
                    "path": "/tmp/fleet",
                    "booster_pool_contract": {
                        "pool": "core_booster",
                        "project_safety_cap": 6,
                    },
                }
            ],
            "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
        }
        ready_package = {
            "package_id": "fleet-ready",
            "task_meta": {"allow_credit_burn": True, "allowed_lanes": ["core_booster", "core"]},
        }
        waiting_package = {
            "package_id": "fleet-next",
            "task_meta": {"allow_credit_burn": True, "allowed_lanes": ["core_booster", "core"]},
        }

        def fake_work_package_rows(*, project_id=None, statuses=None, runtime_states=None):
            if statuses == ["waiting_dependency"]:
                return [waiting_package]
            if statuses == ["blocked", "failed"]:
                return []
            return []

        with mock.patch.object(self.controller, "ea_onemin_manager_billing_aggregate", return_value={}):
            with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value={"core": {"providers": []}}):
                with mock.patch.object(self.controller, "quartermaster_capacity_plan", return_value={"inputs": {"sustainable_booster_cap": 1}}):
                    with mock.patch.object(self.controller, "quartermaster_active_lane_usage", return_value={"core_booster": 1}):
                        with mock.patch.object(self.controller, "quartermaster_useful_booster_work_count", return_value=1):
                            with mock.patch.object(self.controller, "quartermaster_queued_booster_work_count", return_value=0):
                                with mock.patch.object(
                                    self.controller,
                                    "work_package_scope_capacity",
                                    return_value={"active_packages": [ready_package], "ready_packages": [ready_package], "scope_cap": 2, "ready_scope_cap": 1},
                                ):
                                    with mock.patch.object(self.controller, "work_package_rows", side_effect=fake_work_package_rows):
                                        snapshot = self.controller.quartermaster_event_snapshot(config)

        starvation = json.loads(snapshot["booster_supply_starved"])
        self.assertTrue(starvation["starved"])
        self.assertEqual(starvation["ready_booster_packages"], 1)
        self.assertEqual(starvation["waiting_dependency_packages"], 1)
        self.assertEqual(starvation["sustainable_booster_cap"], 1)
        self.assertEqual(starvation["ready_work_reserve_target"], 2)
        self.assertEqual(starvation["ready_work_reserve_shortfall"], 1)

    def test_quartermaster_event_snapshot_flags_queue_only_booster_supply_starvation(self) -> None:
        config = {
            "quartermaster": {
                "useful_work": {
                    "ready_reserve_multiplier": 2,
                    "minimum_ready_packages": 2,
                    "packages_per_authority_worker": 4,
                }
            },
            "policies": {"capacity_plane": {"plane_caps": {"global_booster_cap": 6}}},
            "projects": [
                {
                    "id": "fleet",
                    "path": "/tmp/fleet",
                    "booster_pool_contract": {
                        "pool": "core_booster",
                        "project_safety_cap": 6,
                    },
                }
            ],
            "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
        }

        def fake_work_package_rows(*, project_id=None, statuses=None, runtime_states=None):
            return []

        with mock.patch.object(self.controller, "ea_onemin_manager_billing_aggregate", return_value={}):
            with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value={"core": {"providers": []}}):
                with mock.patch.object(self.controller, "quartermaster_capacity_plan", return_value={"inputs": {"sustainable_booster_cap": 3}}):
                    with mock.patch.object(self.controller, "quartermaster_active_lane_usage", return_value={}):
                        with mock.patch.object(self.controller, "quartermaster_useful_booster_work_count", return_value=1):
                            with mock.patch.object(self.controller, "quartermaster_queued_booster_work_count", return_value=1):
                                with mock.patch.object(
                                    self.controller,
                                    "work_package_scope_capacity",
                                    return_value={"active_packages": [], "ready_packages": [], "scope_cap": 0, "ready_scope_cap": 0},
                                ):
                                    with mock.patch.object(self.controller, "work_package_rows", side_effect=fake_work_package_rows):
                                        snapshot = self.controller.quartermaster_event_snapshot(config)

        starvation = json.loads(snapshot["booster_supply_starved"])
        self.assertTrue(starvation["starved"])
        self.assertEqual(starvation["queued_booster_work"], 1)
        self.assertEqual(starvation["ready_booster_packages"], 0)
        self.assertEqual(starvation["ready_work_reserve_target"], 6)
        self.assertEqual(starvation["ready_work_reserve_shortfall"], 6)

    def test_quartermaster_event_snapshot_tracks_capacity_and_scope_signature_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            base_config = {
                "policies": {
                    "stale_heartbeat_seconds": 1800,
                    "capacity_plane": {
                        "plane_caps": {
                            "global_booster_cap": 5,
                            "review_shard_cap": 5,
                            "audit_shard_cap": 5,
                        }
                    },
                },
                "quartermaster": {
                    "mode": "enforce",
                    "max_scale_up_per_tick": 5,
                    "max_scale_down_per_tick": 5,
                    "plan_ttl_seconds": 900,
                },
                "review_fabric": {
                    "default": {
                        "shards": {
                            "service_floor": 3,
                            "target_parallelism": 5,
                            "max_queue_depth_per_active_reviewer": 2,
                        }
                    }
                },
                "audit_fabric": {"default": {"service_floor": 1, "target_parallelism": 5}},
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "booster_pool_contract": {
                            "pool": "core_booster",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 5,
                        },
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
            }
            raised_config = json.loads(json.dumps(base_config))
            raised_config["policies"]["capacity_plane"]["plane_caps"]["global_booster_cap"] = 20
            raised_config["quartermaster"]["max_scale_up_per_tick"] = 20
            raised_config["review_fabric"]["default"]["shards"]["service_floor"] = 10
            raised_config["projects"][0]["booster_pool_contract"]["project_safety_cap"] = 20

            with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value={"core": {"providers": []}}):
                with mock.patch.object(self.controller, "ea_onemin_manager_billing_aggregate", return_value={}):
                    with mock.patch.object(self.controller, "quartermaster_active_lane_usage", return_value={}):
                        with mock.patch.object(self.controller, "quartermaster_useful_booster_work_count", return_value=0):
                            with mock.patch.object(
                                self.controller,
                                "work_package_scope_capacity",
                                side_effect=[
                                    {"active_packages": [], "ready_packages": [], "scope_cap": 1, "ready_scope_cap": 1},
                                    {"active_packages": [{"package_id": "fleet-a"}], "ready_packages": [{"package_id": "fleet-b"}], "scope_cap": 2, "ready_scope_cap": 1},
                                    {"active_packages": [], "ready_packages": [], "scope_cap": 1, "ready_scope_cap": 1},
                                ],
                            ):
                                base_snapshot = self.controller.quartermaster_event_snapshot(base_config)
                                scope_changed_snapshot = self.controller.quartermaster_event_snapshot(base_config)
                                cap_changed_snapshot = self.controller.quartermaster_event_snapshot(raised_config)

            self.assertNotEqual(base_snapshot["scope_ready_changed"], scope_changed_snapshot["scope_ready_changed"])
            self.assertNotEqual(base_snapshot["capacity_contract_changed"], cap_changed_snapshot["capacity_contract_changed"])

    def test_quartermaster_event_snapshot_uses_pool_default_project_caps_in_contract_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            config_root = root / "config"
            config_root.mkdir()
            (config_root / "booster_pools.yaml").write_text(
                "\n".join(
                    [
                        "booster_pools:",
                        "  core_booster:",
                        "    worker_lane: core_booster",
                        "    authority_lane: core_authority",
                        "    rescue_lane: core_rescue",
                        "    safety:",
                        "      default_project_cap: 3",
                        "      hard_project_cap: 5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.controller.CONFIG_PATH = config_root / "fleet.yaml"
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            config = {
                "policies": {"capacity_plane": {"plane_caps": {"global_booster_cap": 20}}},
                "quartermaster": {"mode": "enforce", "max_scale_up_per_tick": 5, "max_scale_down_per_tick": 5, "plan_ttl_seconds": 900},
                "review_fabric": {"default": {"shards": {"service_floor": 1, "target_parallelism": 1, "max_queue_depth_per_active_reviewer": 2}}},
                "audit_fabric": {"default": {"service_floor": 1, "target_parallelism": 1}},
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "booster_pool_contract": {"pool": "core_booster"},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
            }

            with mock.patch.object(self.controller, "ea_lane_capacity_snapshot", return_value={"core": {"providers": []}}):
                with mock.patch.object(self.controller, "ea_onemin_manager_billing_aggregate", return_value={}):
                    with mock.patch.object(self.controller, "quartermaster_active_lane_usage", return_value={}):
                        with mock.patch.object(self.controller, "quartermaster_useful_booster_work_count", return_value=0):
                            with mock.patch.object(
                                self.controller,
                                "work_package_scope_capacity",
                                return_value={"active_packages": [], "ready_packages": [], "scope_cap": 1, "ready_scope_cap": 1},
                            ):
                                snapshot = self.controller.quartermaster_event_snapshot(config)

        capacity_contract = json.loads(snapshot["capacity_contract_changed"])
        self.assertEqual(capacity_contract["project_contracts"][0]["default_project_cap"], 3)
        self.assertEqual(capacity_contract["project_contracts"][0]["hard_project_cap"], 5)

    def test_ea_onemin_manager_billing_aggregate_backfills_active_leases_from_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            with self.controller.db() as conn:
                now = self.controller.iso(self.controller.utc_now())
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', 'feedback', '', '[]', 0, 0, 'running', 'slice', NULL, NULL, ?, '', 'bounded_fix', 'ea-coder-hard-batch', 'test', ?)
                    """,
                    ("fleet", str(root / "repo"), now, now),
                )
                conn.execute(
                    "INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at) VALUES(?, ?, '[]', 20, 'ready', ?)",
                    ("acct-ea-core", "ea", now),
                )
                conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'slice', 'running', ?, 'medium', 'bounded_fix', 'test', ?, '', '', '')
                    """,
                    ("fleet", "acct-ea-core", "ea-coder-hard-batch", now),
                )

            self.controller.ea_codex_profiles = lambda force=False: {
                "profiles": [
                    {"model": "ea-coder-hard-batch", "provider_hint_order": ["onemin"]},
                ]
            }
            self.controller.ea_onemin_manager_status = lambda force=False: {
                "aggregate": {
                    "sum_free_credits": 1000,
                    "sum_max_credits": 2000,
                    "active_lease_count": 0,
                    "accounts": [],
                },
                "runway": {
                    "current_burn_per_hour": 25,
                    "hours_remaining_current_pace": 40,
                },
            }

            aggregate = self.controller.ea_onemin_manager_billing_aggregate()

            self.assertEqual(aggregate["active_lease_count"], 1)
            self.assertEqual(aggregate["reported_active_lease_count"], 0)
            self.assertEqual(aggregate["runtime_active_lease_count"], 1)
            self.assertEqual(aggregate["active_lease_count_source"], "fleet_runtime_backfill")
            self.assertEqual(aggregate["active_onemin_accounts"], ["acct-ea-core"])

    def test_ea_onemin_manager_billing_aggregate_infers_topup_eta_from_billing_cycle(self) -> None:
        fixed_now = self.controller.dt.datetime(2026, 3, 23, 11, 10, 2, tzinfo=self.controller.dt.timezone.utc)
        with mock.patch.object(self.controller, "utc_now", return_value=fixed_now):
            self.controller.ea_codex_profiles = lambda force=False: {"profiles": []}
            self.controller.ea_onemin_manager_status = lambda force=False: {
                "aggregate": {
                    "sum_free_credits": 101_747_905,
                    "sum_max_credits": 173_550_000,
                    "active_lease_count": 0,
                    "accounts": [
                        {
                            "slot_count": 1,
                            "last_billing_snapshot_at": "2026-03-23T12:10:02+01:00",
                            "last_member_reconciliation_at": "2026-03-23T12:10:02+01:00",
                        }
                    ],
                },
                "runway": {
                    "current_burn_per_hour": 4_318_685.29,
                    "hours_remaining_current_pace": 23.55,
                },
            }

            aggregate = self.controller.ea_onemin_manager_billing_aggregate()

        self.assertEqual(aggregate["topup_eta_source"], "billing_cycle_fallback")
        self.assertEqual(aggregate["next_topup_at"], "2026-04-22T11:10:02Z")
        self.assertAlmostEqual(aggregate["hours_until_next_topup"], 720.0, places=2)
        self.assertTrue(aggregate["depletes_before_next_topup"])

    def test_ea_onemin_manager_billing_aggregate_replaces_stale_past_topup_eta(self) -> None:
        fixed_now = self.controller.dt.datetime(2026, 3, 23, 11, 10, 2, tzinfo=self.controller.dt.timezone.utc)
        with mock.patch.object(self.controller, "utc_now", return_value=fixed_now):
            self.controller.ea_codex_profiles = lambda force=False: {"profiles": []}
            self.controller.ea_onemin_manager_status = lambda force=False: {
                "aggregate": {
                    "sum_free_credits": 101_747_905,
                    "sum_max_credits": 173_550_000,
                    "active_lease_count": 0,
                    "accounts": [
                        {
                            "slot_count": 1,
                            "last_billing_snapshot_at": "2026-03-23T12:10:02+01:00",
                            "last_member_reconciliation_at": "2026-03-23T12:10:02+01:00",
                        }
                    ],
                },
                "runway": {
                    "next_topup_at": "2026-03-23T09:10:02Z",
                    "current_burn_per_hour": 4_318_685.29,
                    "hours_remaining_current_pace": 23.55,
                },
            }

            aggregate = self.controller.ea_onemin_manager_billing_aggregate()

        self.assertEqual(aggregate["topup_eta_source"], "billing_cycle_fallback")
        self.assertEqual(aggregate["next_topup_at"], "2026-04-22T11:10:02Z")
        self.assertAlmostEqual(aggregate["hours_until_next_topup"], 720.0, places=2)

    def test_onemin_runtime_lease_payload_falls_back_to_batch_model_when_profiles_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            with self.controller.db() as conn:
                now = self.controller.iso(self.controller.utc_now())
                conn.execute(
                    """
                    INSERT INTO projects(
                        id, path, design_doc, verify_cmd, feedback_dir, state_file, queue_json, queue_index,
                        consecutive_failures, status, current_slice, active_run_id, cooldown_until, last_run_at,
                        last_error, spider_tier, spider_model, spider_reason, updated_at
                    )
                    VALUES(?, ?, '', '', 'feedback', '', '[]', 0, 0, 'running', 'slice', NULL, NULL, ?, '', 'bounded_fix', 'ea-coder-hard-batch', 'test', ?)
                    """,
                    ("fleet", str(root / "repo"), now, now),
                )
                conn.execute(
                    "INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at) VALUES(?, ?, '[]', 20, 'ready', ?)",
                    ("acct-ea-core", "ea", now),
                )
                conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'slice', 'running', ?, 'medium', 'bounded_fix', 'test', ?, '', '', '')
                    """,
                    ("fleet", "acct-ea-core", "ea-coder-hard-batch", now),
                )

            self.controller.ea_codex_profiles = lambda force=False: {}

            payload = self.controller.onemin_runtime_lease_payload()

            self.assertEqual(payload["active_onemin_codexers"], 1)
            self.assertEqual(payload["active_onemin_accounts"], ["acct-ea-core"])

    def test_quartermaster_lane_admission_ignores_unmanaged_easy_lane(self) -> None:
        plan = {
            "generated_at": "2026-03-23T10:00:00Z",
            "mode": "enforce",
            "lane_targets": {"core_booster": 0},
            "_quartermaster_status": {
                "generated_at": "2026-03-23T10:00:00Z",
                "cache_state": "fresh",
                "degraded": False,
            },
        }

        gate = self.controller.quartermaster_lane_admission({}, target_lane="easy", plan=plan)

        self.assertFalse(gate["blocked"])
        self.assertEqual(gate["target_lane"], "easy")
        self.assertEqual(gate["remaining_by_lane"], {"core_booster": 0})

    def test_quartermaster_active_lane_usage_ignores_unmanaged_easy_runtime_tasks(self) -> None:
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
                "policies": {"stale_heartbeat_seconds": 1800},
                "projects": [{"id": "alpha", "path": str(repo_root)}, {"id": "beta", "path": str(repo_root)}],
                "accounts": {
                    "acct-ea-core": {
                        "lane": "core",
                        "auth_kind": "api_key",
                        "codex_model_aliases": ["ea-coder-hard"],
                    }
                },
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
            }
            self.controller.sync_config_to_db(config)
            now = self.controller.utc_now()
            with self.controller.db() as conn:
                alpha_run_id = conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'Easy fallback slice', 'running', 'ea-coder-hard', 'low', 'bounded_fix', 'easy-fallback', ?, '', '', '')
                    """,
                    ("alpha", "acct-ea-core", self.controller.iso(now)),
                ).lastrowid
                beta_run_id = conn.execute(
                    """
                    INSERT INTO runs(project_id, account_alias, job_kind, slice_name, status, model, reasoning_effort, spider_tier, decision_reason, started_at, log_path, final_message_path, prompt_path)
                    VALUES(?, ?, 'coding', 'Managed booster slice', 'running', 'ea-coder-hard', 'low', 'bounded_fix', 'managed-booster', ?, '', '', '')
                    """,
                    ("beta", "acct-ea-core", self.controller.iso(now)),
                ).lastrowid
                conn.execute(
                    "UPDATE projects SET status='running', active_run_id=?, current_slice='Easy fallback slice', updated_at=? WHERE id='alpha'",
                    (int(alpha_run_id), self.controller.iso(now)),
                )
                conn.execute(
                    "UPDATE projects SET status='running', active_run_id=?, current_slice='Managed booster slice', updated_at=? WHERE id='beta'",
                    (int(beta_run_id), self.controller.iso(now)),
                )
            self.controller.upsert_runtime_task(
                "alpha",
                package_id="alpha-pkg",
                task_kind="coding",
                task_state="running",
                run_id=int(alpha_run_id),
                payload={
                    "account_alias": "acct-ea-core",
                    "decision": {"lane": "easy", "task_meta": {"allowed_lanes": ["easy", "groundwork"]}},
                    "slice_name": "Easy fallback slice",
                },
                started_at=now,
            )
            self.controller.upsert_runtime_task(
                "beta",
                package_id="beta-pkg",
                task_kind="coding",
                task_state="running",
                run_id=int(beta_run_id),
                payload={
                    "account_alias": "acct-ea-core",
                    "decision": {"lane": "core", "task_meta": {"allowed_lanes": ["core_booster", "core"]}},
                    "slice_name": "Managed booster slice",
                },
                started_at=now,
            )

            usage = self.controller.quartermaster_active_lane_usage(config)

            self.assertEqual(usage, {"core_booster": 1})

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

    def test_normalize_config_applies_project_queue_task_defaults_to_overlay_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            overlay_root = repo_root / ".codex-studio" / "published"
            overlay_root.mkdir(parents=True, exist_ok=True)
            (overlay_root / "QUEUE.generated.yaml").write_text(
                "\n".join(
                    [
                        "mode: replace",
                        "items:",
                        "- Compile status plane",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config_path = root / "fleet.yaml"
            accounts_path = root / "accounts.yaml"
            config_path.write_text(
                json.dumps(
                    {
                        "projects": [
                            {
                                "id": "fleet",
                                "path": str(repo_root),
                                "queue": [],
                                "queue_task_defaults": {
                                    "allowed_lanes": ["core_booster", "core"],
                                    "allow_credit_burn": True,
                                    "premium_required": True,
                                },
                            }
                        ]
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

        queue = config["projects"][0]["queue"]
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["title"], "Compile status plane")
        self.assertEqual(queue[0]["allowed_lanes"], ["core_booster", "core"])
        self.assertTrue(queue[0]["allow_credit_burn"])
        self.assertTrue(queue[0]["premium_required"])

    def test_merge_queue_overlay_item_stamps_pre_overlay_queue_fingerprint_from_queue_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "WORKLIST.md").write_text("- [todo] wl-1 Source Queue Slice\n", encoding="utf-8")
            project_cfg = {
                "id": "core",
                "path": str(repo_root),
                "queue": ["Base Queue Slice"],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "append"}],
                "feedback_dir": "feedback",
            }

            overlay_path = self.controller.merge_queue_overlay_item(project_cfg, "Overlay Queue Slice", mode="append")
            payload = self.controller.load_yaml(overlay_path)

        self.assertEqual(
            payload.get("source_queue_fingerprint"),
            self.controller.work_package_source_queue_fingerprint(["Base Queue Slice", "Source Queue Slice"]),
        )
        self.assertEqual(payload.get("items"), ["Overlay Queue Slice"])

    def test_init_db_repairs_work_package_pull_request_foreign_key_after_pull_request_migration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            conn = sqlite3.connect(self.controller.DB_PATH)
            conn.executescript(
                """
                CREATE TABLE pull_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    repo_owner TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    base_branch TEXT NOT NULL,
                    pr_number INTEGER,
                    pr_url TEXT,
                    pr_title TEXT,
                    pr_body TEXT,
                    pr_state TEXT NOT NULL DEFAULT 'draft',
                    draft INTEGER NOT NULL DEFAULT 1,
                    head_sha TEXT,
                    review_mode TEXT NOT NULL DEFAULT 'github',
                    review_trigger TEXT NOT NULL DEFAULT 'manual_comment',
                    review_focus TEXT,
                    review_status TEXT NOT NULL DEFAULT 'queued',
                    review_requested_at TEXT,
                    review_completed_at TEXT,
                    review_findings_count INTEGER NOT NULL DEFAULT 0,
                    review_blocking_findings_count INTEGER NOT NULL DEFAULT 0,
                    last_review_comment_id TEXT,
                    last_review_head_sha TEXT,
                    last_synced_at TEXT,
                    review_sync_failures INTEGER NOT NULL DEFAULT 0,
                    review_retrigger_count INTEGER NOT NULL DEFAULT 0,
                    review_wakeup_miss_count INTEGER NOT NULL DEFAULT 0,
                    local_review_attempts INTEGER NOT NULL DEFAULT 0,
                    local_review_last_at TEXT,
                    workflow_kind TEXT NOT NULL DEFAULT 'default',
                    review_round INTEGER NOT NULL DEFAULT 0,
                    max_review_rounds INTEGER NOT NULL DEFAULT 0,
                    first_review_complete_at TEXT,
                    accepted_on_round TEXT,
                    needs_core_rescue INTEGER NOT NULL DEFAULT 0,
                    core_rescue_reason TEXT,
                    last_review_feedback_json TEXT NOT NULL DEFAULT '{}',
                    jury_feedback_history_json TEXT NOT NULL DEFAULT '[]',
                    issue_fingerprints_json TEXT NOT NULL DEFAULT '[]',
                    blocking_issue_count_by_round_json TEXT NOT NULL DEFAULT '[]',
                    repeat_issue_count_by_round_json TEXT NOT NULL DEFAULT '[]',
                    groundwork_time_ms INTEGER NOT NULL DEFAULT 0,
                    jury_time_ms INTEGER NOT NULL DEFAULT 0,
                    core_time_ms INTEGER NOT NULL DEFAULT 0,
                    allowance_burn_by_lane_json TEXT NOT NULL DEFAULT '{}',
                    pass_without_core INTEGER NOT NULL DEFAULT 0,
                    landed_at TEXT,
                    landed_sha TEXT,
                    landing_lane TEXT,
                    landing_error TEXT,
                    last_retrigger_at TEXT,
                    next_retry_at TEXT,
                    review_rate_limit_reset_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.commit()
            conn.close()

            self.controller.init_db()

            with self.controller.db() as conn:
                work_package_foreign_keys = {
                    str(row["from"] or "").strip(): str(row["table"] or "").strip()
                    for row in conn.execute("PRAGMA foreign_key_list(work_packages)").fetchall()
                }
                scope_claim_foreign_keys = {
                    str(row["from"] or "").strip(): str(row["table"] or "").strip()
                    for row in conn.execute("PRAGMA foreign_key_list(scope_claims)").fetchall()
                }
                merge_queue_foreign_keys = {
                    str(row["from"] or "").strip(): str(row["table"] or "").strip()
                    for row in conn.execute("PRAGMA foreign_key_list(merge_queue)").fetchall()
                }

        self.assertEqual(work_package_foreign_keys.get("latest_pr_id"), "pull_requests")
        self.assertEqual(scope_claim_foreign_keys.get("package_id"), "work_packages")
        self.assertEqual(merge_queue_foreign_keys.get("package_id"), "work_packages")

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

    def test_reconcile_abandoned_runs_requeues_running_runtime_tasks_for_rehydration(self) -> None:
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
                    VALUES(?, ?, '', '', '', '', '[]', 0, 0, 'running', 'slice', 7, NULL, ?, '', '', '', '', ?)
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
                conn.execute(
                    """
                    INSERT INTO runtime_tasks(
                        package_id, project_id, task_kind, task_state, payload_json, run_id, scheduled_at, started_at, updated_at
                    )
                    VALUES(?, ?, 'coding', 'running', ?, 7, ?, ?, ?)
                    """,
                    (
                        "fleet",
                        "fleet",
                        json.dumps(
                            {
                                "slice_name": "slice",
                                "account_alias": "acct-ea-core",
                                "selected_model": "ea-coder-hard",
                                "selection_note": "restart",
                                "selection_trace": [],
                                "decision": {"reason": "test", "tier": "bounded_fix", "reasoning_effort": "low"},
                            },
                            sort_keys=True,
                        ),
                        now,
                        now,
                        now,
                    ),
                )

            self.controller.reconcile_abandoned_runs({"policies": {"max_consecutive_failures": 3}})

            with self.controller.db() as conn:
                task = conn.execute(
                    "SELECT task_state, run_id, started_at FROM runtime_tasks WHERE package_id='fleet'"
                ).fetchone()

        self.assertEqual(task["task_state"], "scheduled")
        self.assertIsNone(task["run_id"])
        self.assertIsNone(task["started_at"])

    def test_reconcile_abandoned_runs_releases_running_work_package_for_redispatch(self) -> None:
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
                    VALUES(?, ?, '', '', '', '', '[]', 0, 0, 'running', 'slice', 7, NULL, ?, '', '', '', '', ?)
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
                conn.execute(
                    """
                    INSERT INTO work_packages(
                        package_id, project_id, queue_index, title, slice_name, created_at, updated_at,
                        status, runtime_state, latest_run_id
                    )
                    VALUES(?, ?, 0, ?, ?, ?, ?, 'running', 'running', 7)
                    """,
                    ("fleet-0000", "fleet", "Slice", "Slice", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO scope_claims(
                        package_id, project_id, claim_type, claim_value, scope_key, claim_state, created_at, activated_at
                    )
                    VALUES(?, ?, 'path', 'src/a.py', 'path:src/a.py', 'active', ?, ?)
                    """,
                    ("fleet-0000", "fleet", now, now),
                )

            self.controller.reconcile_abandoned_runs({"policies": {"max_consecutive_failures": 3}})

            with self.controller.db() as conn:
                package = conn.execute(
                    "SELECT status, runtime_state, latest_run_id FROM work_packages WHERE package_id='fleet-0000'"
                ).fetchone()
                claim = conn.execute(
                    "SELECT claim_state, released_at FROM scope_claims WHERE package_id='fleet-0000'"
                ).fetchone()

        self.assertEqual(str(package["status"]), self.controller.WAITING_CAPACITY_STATUS)
        self.assertEqual(str(package["runtime_state"]), "idle")
        self.assertEqual(int(package["latest_run_id"]), 7)
        self.assertEqual(str(claim["claim_state"]), "released")
        self.assertTrue(claim["released_at"])

    def test_reconcile_finished_run_links_releases_stuck_work_package_for_terminal_run(self) -> None:
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
                    VALUES(?, ?, '', '', '', '', '[]', 0, 0, ?, 'slice', NULL, NULL, ?, '', '', '', '', ?)
                    """,
                    ("fleet", str(root), self.controller.READY_STATUS, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO runs(
                        id, project_id, account_alias, slice_name, status, model, started_at, finished_at, job_kind
                    )
                    VALUES(7, 'fleet', 'acct-ea-core', 'slice', 'abandoned', 'ea-coder-hard', ?, ?, 'coding')
                    """,
                    (now, now),
                )
                conn.execute(
                    """
                    INSERT INTO work_packages(
                        package_id, project_id, queue_index, title, slice_name, created_at, updated_at,
                        status, runtime_state, latest_run_id
                    )
                    VALUES(?, ?, 0, ?, ?, ?, ?, 'running', 'running', 7)
                    """,
                    ("fleet-0000", "fleet", "Slice", "Slice", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO scope_claims(
                        package_id, project_id, claim_type, claim_value, scope_key, claim_state, created_at, activated_at
                    )
                    VALUES(?, ?, 'path', 'src/a.py', 'path:src/a.py', 'active', ?, ?)
                    """,
                    ("fleet-0000", "fleet", now, now),
                )

            reconciled = self.controller.reconcile_finished_run_links()

            with self.controller.db() as conn:
                package = conn.execute(
                    "SELECT status, runtime_state, latest_run_id FROM work_packages WHERE package_id='fleet-0000'"
                ).fetchone()
                claim = conn.execute(
                    "SELECT claim_state, released_at FROM scope_claims WHERE package_id='fleet-0000'"
                ).fetchone()

        self.assertGreaterEqual(reconciled, 1)
        self.assertEqual(str(package["status"]), self.controller.WAITING_CAPACITY_STATUS)
        self.assertEqual(str(package["runtime_state"]), "idle")
        self.assertEqual(int(package["latest_run_id"]), 7)
        self.assertEqual(str(claim["claim_state"]), "released")
        self.assertTrue(claim["released_at"])

    def test_sync_project_progress_prefers_ready_package_compile_over_waiting_dependency(self) -> None:
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
                    VALUES(?, ?, '', '', '', '', '[]', 0, 0, ?, 'stale slice', NULL, NULL, ?, '', '', '', '', ?)
                    """,
                    ("fleet", str(root), "waiting_dependency", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO work_packages(
                        package_id, project_id, queue_index, title, slice_name, package_kind, priority, created_at, updated_at,
                        status, runtime_state
                    )
                    VALUES(?, ?, -1, ?, ?, ?, -100, ?, ?, 'ready', 'idle')
                    """,
                    (
                        "fleet-package-compile-1",
                        "fleet",
                        "Compile booster-ready work packages from queue truth",
                        "Compile booster-ready work packages from queue truth",
                        self.controller.PACKAGE_COMPILE_PACKAGE_KIND,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO work_packages(
                        package_id, project_id, queue_index, title, slice_name, priority, created_at, updated_at,
                        status, runtime_state
                    )
                    VALUES(?, ?, 0, ?, ?, 100, ?, ?, 'waiting_dependency', 'idle')
                    """,
                    (
                        "fleet-0000",
                        "fleet",
                        "Later implementation package",
                        "Later implementation package",
                        now,
                        now,
                    ),
                )

            self.controller.sync_project_progress_from_packages("fleet")

            with self.controller.db() as conn:
                row = conn.execute(
                    "SELECT status, current_slice, active_run_id FROM projects WHERE id='fleet'"
                ).fetchone()

        self.assertEqual(str(row["status"]), self.controller.READY_STATUS)
        self.assertEqual(
            str(row["current_slice"]),
            "Compile booster-ready work packages from queue truth",
        )
        self.assertIsNone(row["active_run_id"])

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

    def test_pick_account_and_model_allows_standard_api_models_when_capability_probe_only_saw_alias(self) -> None:
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
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, api_key_file, allowed_models_json, capability_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'api_key', ?, ?, ?, 1, 'ready', ?)
                    """,
                    (
                        "acct-ea-groundwork",
                        str(api_key_file),
                        json.dumps(["gpt-5-mini", "gpt-5.4"]),
                        json.dumps(["ea-groundwork-gemini"]),
                        now,
                    ),
                )

            config = {
                "accounts": {
                    "acct-ea-groundwork": {
                        "lane": "groundwork",
                        "auth_kind": "api_key",
                    },
                },
                "spider": {"price_table": self.controller.DEFAULT_PRICE_TABLE},
            }
            project_cfg = {
                "id": "fleet",
                "accounts": ["acct-ea-groundwork"],
                "account_policy": {
                    "preferred_accounts": ["acct-ea-groundwork"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": False,
                },
            }
            decision = {
                "tier": "multi_file_impl",
                "lane": "groundwork",
                "lane_submode": "responses_groundwork",
                "escalation_reason": "easy_capacity_shifted_to_groundwork",
                "allowed_lanes": ["groundwork"],
                "model_preferences": ["gpt-5.4", "gpt-5.3-codex"],
                "estimated_input_tokens": 1200,
                "estimated_output_tokens": 800,
            }

            with mock.patch.object(self.controller, "has_api_key", return_value=True):
                alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-groundwork")
        self.assertEqual(model, "gpt-5.4")
        self.assertIn("route=multi_file_impl", why)
        self.assertIn("acct-ea-groundwork", {item["alias"] for item in trace})

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

    def test_pick_account_and_model_uses_shared_groundwork_fallback_for_easy_only_slice(self) -> None:
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
                    ("acct-ea-groundwork-2", str(api_key_file), json.dumps(["gpt-5-mini"]), now),
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
                    "acct-ea-groundwork-2": {
                        "lane": "groundwork",
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

        self.assertEqual(alias, "acct-ea-groundwork-2")
        self.assertEqual(model, "gpt-5-mini")
        self.assertIn("route=bounded_fix", why)
        self.assertIn("acct-ea-groundwork-2", {item["alias"] for item in trace})

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

    def test_eligible_account_aliases_include_shared_groundwork_fallback_for_current_easy_slice(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            now = self.controller.iso(self.controller.utc_now())
            with self.controller.db() as conn:
                conn.execute(
                    """
                    INSERT INTO accounts(
                        alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at
                    )
                    VALUES(?, 'api_key', ?, 1, 'ready', ?)
                    """,
                    ("acct-ea-groundwork-2", json.dumps(["gpt-5-mini"]), now),
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
                    "acct-ea-groundwork-2": {
                        "lane": "groundwork",
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

            eligible = self.controller.eligible_account_aliases(config, project_cfg, self.controller.utc_now())

        self.assertEqual(eligible, ["acct-ea-groundwork-2"])

    def test_eligible_account_aliases_excludes_reserved_and_unclassified_chatgpt_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
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
                    INSERT INTO accounts(alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at)
                    VALUES(?, 'chatgpt_auth_json', ?, ?, 1, 'ready', ?)
                    """,
                    ("acct-unclassified", str(auth_json), json.dumps(["gpt-5-mini"]), now),
                )
                conn.execute(
                    """
                    INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                    VALUES(?, 'api_key', ?, 1, 'ready', ?)
                    """,
                    ("acct-safe-api", json.dumps(["gpt-5-mini"]), now),
                )
                conn.execute(
                    """
                    INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                    VALUES(?, 'api_key', ?, 1, 'ready', ?)
                    """,
                    ("acct-protected", json.dumps(["gpt-5-mini"]), now),
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
                "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                "accounts": {
                    "acct-unclassified": {
                        "lane": "easy",
                        "auth_kind": "chatgpt_auth_json",
                        "auth_json_file": str(auth_json),
                    },
                    "acct-safe-api": {
                        "lane": "easy",
                        "auth_kind": "api_key",
                    },
                    "acct-protected": {
                        "lane": "easy",
                        "auth_kind": "api_key",
                        "owner_id": "tibor.girschele",
                    },
                },
                "lanes": self.controller.normalize_lanes_config({}),
            }
            project_cfg = {
                "id": "mobile",
                "path": str(repo_root),
                "accounts": ["acct-unclassified", "acct-safe-api", "acct-protected"],
                "account_policy": {
                    "preferred_accounts": ["acct-unclassified", "acct-safe-api", "acct-protected"],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": True,
                },
            }

            with mock.patch.object(self.controller, "has_api_key", return_value=True):
                eligible = self.controller.eligible_account_aliases(config, project_cfg, self.controller.utc_now())

        self.assertEqual(eligible, ["acct-safe-api"])

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

            alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertIsNone(alias)
        self.assertIsNone(model)
        rejected = next(item for item in trace if item.get("alias") == "acct-chatgpt-archon")
        self.assertEqual(rejected.get("state"), "rejected")
        self.assertIn("protected operator account reserved", str(rejected.get("reason") or ""))

    def test_pick_account_and_model_marks_chatgpt_core_account_lane_service_as_eligible_for_easy_lane(self) -> None:
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
                "id": "ui",
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
                "lane_submode": "responses_easy",
                "escalation_reason": "",
                "allowed_lanes": ["easy"],
                "model_preferences": ["gpt-5-mini"],
                "estimated_input_tokens": 800,
                "estimated_output_tokens": 200,
            }

            alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertIsNone(alias)
        self.assertIsNone(model)
        rejected = next(item for item in trace if item.get("alias") == "acct-chatgpt-archon")
        self.assertEqual(rejected.get("state"), "rejected")
        self.assertTrue(rejected.get("lane_service_allowed"))
        self.assertFalse(rejected.get("lane_service_is_exact"))
        self.assertIn("protected operator account reserved", str(rejected.get("reason") or ""))

    def test_pick_account_and_model_falls_back_to_explicit_emergency_chatgpt_alias_when_project_disallows_chatgpt(self) -> None:
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
                "id": "fleet",
                "accounts": [],
                "account_policy": {
                    "preferred_accounts": [],
                    "allow_api_accounts": True,
                    "allow_chatgpt_accounts": False,
                    "emergency_chatgpt_fallback_accounts": ["acct-chatgpt-archon"],
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

            alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertIsNone(alias)
        self.assertIsNone(model)
        rejected = next(item for item in trace if item.get("alias") == "acct-chatgpt-archon")
        self.assertEqual(rejected.get("state"), "rejected")
        self.assertIn("protected operator account reserved", str(rejected.get("reason") or ""))

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

            alias, model, why, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertIsNone(alias)
        self.assertIsNone(model)
        rejected = next(item for item in trace if item.get("alias") == "acct-chatgpt-archon")
        self.assertEqual(rejected.get("state"), "rejected")
        self.assertIn("protected operator account reserved", str(rejected.get("reason") or ""))

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

    def test_scheduler_skips_singleton_fallback_after_blocked_lockstep_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_alpha = root / "alpha"
            repo_beta = root / "beta"
            repo_alpha.mkdir()
            repo_beta.mkdir()
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            self.controller.state.tasks.clear()
            self.controller.state.stop = asyncio.Event()
            config = {
                "policies": {"max_parallel_runs": 4, "scheduler_interval_seconds": 0},
                "projects": [
                    {"id": "alpha", "path": str(repo_alpha)},
                    {"id": "beta", "path": str(repo_beta)},
                ],
                "project_groups": [{"id": "duo", "mode": "lockstep", "projects": ["alpha", "beta"]}],
            }
            self.controller.sync_config_to_db(config)
            now = self.controller.utc_now()
            for project_id, slice_name in [("alpha", "Alpha slice"), ("beta", "Beta slice")]:
                self.controller.update_project_status(
                    project_id,
                    status=self.controller.READY_STATUS,
                    current_slice=slice_name,
                    active_run_id=None,
                    cooldown_until=None,
                    last_run_at=now,
                    last_error="",
                    consecutive_failures=0,
                    spider_tier="bounded_fix",
                    spider_model="ea-coder-hard",
                    spider_reason="quartermaster-test",
                )
            with self.controller.db() as conn:
                conn.execute("UPDATE projects SET queue_json=?, queue_index=0 WHERE id='alpha'", (json.dumps(["Alpha slice"]),))
                conn.execute("UPDATE projects SET queue_json=?, queue_index=0 WHERE id='beta'", (json.dumps(["Beta slice"]),))
                project_rows = {
                    str(row["id"]): row
                    for row in conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
                }

            def build_candidate(project_id: str, row) -> object:
                return self.controller.DispatchCandidate(
                    row=row,
                    project_cfg={"id": project_id, "path": str(repo_alpha if project_id == "alpha" else repo_beta), "enabled": True},
                    queue=[f"{project_id.title()} slice"],
                    queue_index=0,
                    slice_item={"title": f"{project_id.title()} slice"},
                    slice_name=f"{project_id.title()} slice",
                    task_meta={},
                    runtime_status=self.controller.READY_STATUS,
                    cooldown_until=None,
                    dispatchable=True,
                )

            candidates = {
                "alpha": build_candidate("alpha", project_rows["alpha"]),
                "beta": build_candidate("beta", project_rows["beta"]),
            }
            launched: list[str] = []

            def planned_launch_for(project_id: str) -> object:
                candidate = candidates[project_id]
                return self.controller.PlannedLaunch(
                    project_id=project_id,
                    candidate=candidate,
                    decision={"tier": "bounded_fix", "reason": "quartermaster-test", "quartermaster": {"target_lane": "core_booster"}},
                    account_alias="acct-ea-core",
                    selected_model="ea-coder-hard",
                    selection_note="quartermaster-test",
                    selection_trace=[],
                )

            def plan_side_effect(_config, candidate, **kwargs):
                project_id = str(candidate.project_cfg["id"])
                reserved_scale_up_count = int(kwargs.get("reserved_scale_up_count") or 0)
                if project_id == "alpha" and reserved_scale_up_count == 0:
                    return planned_launch_for("alpha")
                if project_id == "beta" and reserved_scale_up_count == 1:
                    return None
                return planned_launch_for(project_id)

            async def stop_after_once(_seconds: int) -> None:
                self.controller.state.stop.set()

            no_op = mock.Mock(return_value=None)
            with contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(self.controller, "normalize_config", return_value=config))
                stack.enter_context(mock.patch.object(self.controller, "auto_publish_approved_audit_candidates", no_op))
                stack.enter_context(mock.patch.object(self.controller, "sync_config_to_db", no_op))
                stack.enter_context(mock.patch.object(self.controller, "normalize_usage_limit_account_backoffs", no_op))
                stack.enter_context(mock.patch.object(self.controller, "normalize_auth_failure_account_backoffs", no_op))
                stack.enter_context(mock.patch.object(self.controller, "sync_design_repo_mirrors_if_safe", no_op))
                stack.enter_context(mock.patch.object(self.controller, "reconcile_stale_worker_sessions", return_value=0))
                stack.enter_context(mock.patch.object(self.controller, "reconcile_orphaned_active_runs", return_value=0))
                stack.enter_context(mock.patch.object(self.controller, "reconcile_finished_run_links", return_value=0))
                stack.enter_context(mock.patch.object(self.controller, "heal_pending_pull_request_reviews", no_op))
                stack.enter_context(mock.patch.object(self.controller, "heal_orphaned_local_reviews", no_op))
                stack.enter_context(mock.patch.object(self.controller, "sync_pending_github_reviews", no_op))
                stack.enter_context(mock.patch.object(self.controller, "heal_stalled_github_reviews", no_op))
                stack.enter_context(mock.patch.object(self.controller, "reconcile_project_incidents", no_op))
                stack.enter_context(mock.patch.object(self.controller, "sync_group_runtime_phase", no_op))
                stack.enter_context(mock.patch.object(self.controller, "request_due_group_audits", no_op))
                stack.enter_context(mock.patch.object(self.controller, "load_program_registry", return_value={}))
                stack.enter_context(mock.patch.object(self.controller, "group_runtime_rows", return_value={}))
                stack.enter_context(mock.patch.object(self.controller, "codex_active_project_ids", return_value=set()))
                stack.enter_context(mock.patch.object(self.controller, "reconcile_runtime_tasks", no_op))
                stack.enter_context(mock.patch.object(self.controller, "rehydrate_runtime_tasks", return_value=0))
                stack.enter_context(mock.patch.object(self.controller, "quartermaster_tick_if_due", return_value={"mode": "enforce"}))
                stack.enter_context(mock.patch.object(self.controller, "quartermaster_capacity_reconcile", return_value={}))
                stack.enter_context(mock.patch.object(self.controller, "quartermaster_capacity_drain", return_value={"drained_projects": []}))
                stack.enter_context(
                    mock.patch.object(
                        self.controller,
                        "prepare_dispatch_candidate",
                        side_effect=lambda cfg, project_cfg, row, _now: candidates[str(project_cfg["id"])],
                    )
                )
                stack.enter_context(mock.patch.object(self.controller, "effective_group_meta", return_value={}))
                stack.enter_context(
                    mock.patch.object(
                        self.controller,
                        "group_dispatch_state",
                        return_value={"dispatch_ready": True, "dispatch_blockers": []},
                    )
                )
                stack.enter_context(mock.patch.object(self.controller, "dispatch_backfill_priority", return_value=0))
                stack.enter_context(mock.patch.object(self.controller, "bridge_service_definitions", return_value=[]))
                stack.enter_context(mock.patch.object(self.controller, "active_bridge_service_count", return_value=0))
                stack.enter_context(mock.patch.object(self.controller, "idle_bridge_service_aliases", return_value=[]))
                stack.enter_context(mock.patch.object(self.controller, "plan_candidate_launch", side_effect=plan_side_effect))
                stack.enter_context(
                    mock.patch.object(
                        self.controller,
                        "launch_planned_project_task",
                        side_effect=lambda _cfg, planned: launched.append(planned.project_id) or True,
                    )
                )
                stack.enter_context(mock.patch.object(self.controller, "maintain_active_worker_floor", return_value=0))
                stack.enter_context(mock.patch("asyncio.sleep", side_effect=stop_after_once))
                asyncio.run(self.controller.scheduler_loop())

            self.assertEqual(launched, [])

    def test_maintain_active_worker_floor_threads_reserved_counts(self) -> None:
        config = {"policies": {"min_active_codex_workers": 2, "max_parallel_runs": 2}}

        def candidate(project_id: str) -> object:
            return self.controller.DispatchCandidate(
                row=None,
                project_cfg={"id": project_id, "enabled": True},
                queue=[f"{project_id} slice"],
                queue_index=0,
                slice_item={"title": f"{project_id} slice"},
                slice_name=f"{project_id} slice",
                task_meta={},
                runtime_status=self.controller.READY_STATUS,
                cooldown_until=None,
                dispatchable=True,
            )

        candidates = {
            "alpha": candidate("alpha"),
            "beta": candidate("beta"),
        }
        captured: list[dict[str, object]] = []

        def fake_plan(_config, current_candidate, **kwargs):
            captured.append(
                {
                    "project_id": str(current_candidate.project_cfg["id"]),
                    "reserved_account_counts": dict(kwargs.get("reserved_account_counts") or {}),
                    "reserved_lane_counts": dict(kwargs.get("reserved_lane_counts") or {}),
                    "reserved_scale_up_count": int(kwargs.get("reserved_scale_up_count") or 0),
                }
            )
            return self.controller.PlannedLaunch(
                project_id=str(current_candidate.project_cfg["id"]),
                candidate=current_candidate,
                decision={"quartermaster": {"target_lane": "core_booster"}},
                account_alias="acct-ea-core",
                selected_model="ea-coder-hard",
                selection_note="test floor reservations",
                selection_trace=[],
            )

        with mock.patch.object(self.controller, "plan_candidate_launch", side_effect=fake_plan):
            with mock.patch.object(self.controller, "launch_planned_project_task", return_value=True):
                launched = self.controller.maintain_active_worker_floor(
                    config,
                    candidates,
                    running_count=0,
                    existing_scale_up_count=0,
                    reserved_account_counts={"acct-ea-core": 1},
                    reserved_lane_counts={"core_booster": 1},
                )

        self.assertEqual(launched, 2)
        self.assertEqual(captured[0]["reserved_account_counts"], {"acct-ea-core": 1})
        self.assertEqual(captured[0]["reserved_lane_counts"], {"core_booster": 1})
        self.assertEqual(captured[1]["reserved_account_counts"], {"acct-ea-core": 2})
        self.assertEqual(captured[1]["reserved_lane_counts"], {"core_booster": 2})
        self.assertEqual(captured[1]["reserved_scale_up_count"], 1)

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

    def test_request_auditor_run_with_quartermaster_respects_audit_shard_reservations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()
            generated_at = self.controller.iso(self.controller.utc_now())
            plan = {
                "generated_at": generated_at,
                "mode": "enforce",
                "controller_tick": {"plan_ttl_seconds": 900},
                "lane_targets": {"audit_shard": 1},
                "_quartermaster_status": {
                    "generated_at": generated_at,
                    "cache_state": "fresh",
                    "degraded": False,
                    "source": "live_admin",
                },
            }

            with mock.patch.object(self.controller, "quartermaster_tick_if_due", return_value=plan):
                with mock.patch.object(
                    self.controller,
                    "trigger_auditor_run_now",
                    return_value={"requested": True, "scope_type": "group", "scope_id": "solo", "can_resolve": True},
                ) as trigger_auditor_run_now:
                    first = self.controller.request_auditor_run_with_quartermaster({}, scope_type="group", scope_id="solo")
                    second = self.controller.request_auditor_run_with_quartermaster(
                        {},
                        scope_type="group",
                        scope_id="duo",
                        reserved_lane_counts={"audit_shard": 1},
                    )

        self.assertTrue(first["requested"])
        self.assertFalse(second["requested"])
        self.assertTrue(second["quartermaster_blocked"])
        self.assertIn("target_lane=audit_shard", str(second["error"] or ""))
        trigger_auditor_run_now.assert_called_once()

    def test_launch_local_review_runtime_task_blocks_when_review_shard_is_full(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        root = repo_root.parent
        self.controller.QUARTERMASTER_PATH = root / "quartermaster.yaml"
        self.controller.QUARTERMASTER_PATH.write_text(
            "\n".join(
                [
                    "quartermaster:",
                    "  enabled: true",
                    "  mode: enforce",
                    "  driver: controller_tick",
                    "  baseline_tick_seconds: 600",
                    "  event_tick_min_seconds: 90",
                    "  plan_ttl_seconds: 900",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        full_config = {**config, "projects": [project_cfg]}
        review_focus = self.controller.encode_review_focus(
            self.controller.review_focus_text(project_cfg, str(slice_item["title"])),
            reviewer_lane="core",
            reviewer_model=self.controller.reviewer_runtime_model_for_lane(config.get("lanes") or {}, "core"),
            metadata={
                "workflow_kind": "default",
                "review_round": "1",
                "review_packet": json.dumps({}, sort_keys=True),
            },
        )
        pr_row = self.controller.upsert_local_review_request(
            project_cfg,
            slice_name=str(slice_item["title"]),
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
        generated_at = self.controller.iso(self.controller.utc_now())
        plan = {
            "generated_at": generated_at,
            "mode": "enforce",
            "controller_tick": {"plan_ttl_seconds": 900},
            "lane_targets": {"review_shard": 0},
            "_quartermaster_status": {
                "generated_at": generated_at,
                "cache_state": "fresh",
                "degraded": False,
                "source": "live_admin",
            },
        }

        with mock.patch.object(self.controller, "quartermaster_tick_if_due", return_value=plan):
            launched = self.controller.launch_local_review_runtime_task(
                full_config,
                project_cfg,
                project_row,
                pr_row,
                reason="review shard exhausted",
            )

        self.assertFalse(launched)
        self.assertIsNone(self.controller.runtime_task_row("fleet"))
        with self.controller.db() as conn:
            updated_project = conn.execute("SELECT status, last_error FROM projects WHERE id='fleet'").fetchone()
        self.assertEqual(str(updated_project["status"]), self.controller.LOCAL_REVIEW_PENDING_STATUS)
        self.assertIn("target_lane=review_shard", str(updated_project["last_error"] or ""))

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

    def test_execute_project_slice_chatgpt_fallback_skips_ea_provider_overrides(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        now = self.controller.iso(self.controller.utc_now())
        project_cfg["runner"] = {
            **dict(project_cfg.get("runner") or {}),
            "config_overrides": [
                'model_provider="ea"',
                'model_providers.ea.base_url="http://host.docker.internal:8090/v1"',
            ],
        }
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
            "tier": "multi_file_impl",
            "reasoning_effort": "low",
            "estimated_prompt_chars": 4096,
            "estimated_input_tokens": 1024,
            "estimated_output_tokens": 1024,
            "predicted_changed_files": 4,
            "requires_contract_authority": False,
            "reason": "test chatgpt emergency fallback",
            "lane": "core",
            "lane_submode": "responses_hard",
            "selected_profile": "core",
            "why_not_cheaper": "",
            "escalation_reason": "cheap_pool_starved_core_fallback",
            "expected_allowance_burn": {},
            "allowed_lanes": ["easy", "core"],
            "required_reviewer_lane": "core",
            "final_reviewer_lane": "core",
            "task_meta": {},
            "spark_eligible": False,
            "runtime_model": "ea-coder-hard",
            "lane_capacity": {},
        }

        captured_cmd: list[str] = []

        async def fake_run_command(cmd, **kwargs):
            captured_cmd[:] = list(cmd)
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
                                                "acct-chatgpt-archon",
                                                "gpt-5.3-codex",
                                                "test note",
                                                [],
                                            )
                                        )

        self.assertIn("--model", captured_cmd)
        self.assertIn("gpt-5.3-codex", captured_cmd)
        self.assertNotIn('model_provider="ea"', captured_cmd)

    def test_execute_project_slice_ea_account_uses_codexea_shim(self) -> None:
        repo_root, config, project_cfg, slice_item = self._configure_groundwork_loop_fixture()
        now = self.controller.iso(self.controller.utc_now())
        project_cfg["runner"] = {
            "config_overrides": [
                'model_provider="ea"',
                'model_providers.ea.base_url="http://host.docker.internal:8090/v1"',
                'model_providers.ea.http_headers={"X-EA-Principal-ID"="codex-fleet"}',
                'mcp_servers.ea.required=false',
            ]
        }
        config["accounts"]["acct-ea-core"] = {
            **dict(config["accounts"]["acct-ea-core"]),
            "auth_kind": "ea",
        }
        with self.controller.db() as conn:
            conn.execute("UPDATE accounts SET auth_kind='ea' WHERE alias='acct-ea-core'")
            conn.execute("UPDATE projects SET status='running', current_slice=?, last_run_at=? WHERE id='fleet'", (str(slice_item["title"]), now))
            project_row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()
        self.assertIsNotNone(project_row)
        decision = {
            "tier": "multi_file_impl",
            "reasoning_effort": "high",
            "estimated_prompt_chars": 4096,
            "estimated_input_tokens": 1024,
            "estimated_output_tokens": 1024,
            "predicted_changed_files": 4,
            "requires_contract_authority": False,
            "reason": "test ea shim launch",
            "lane": "core",
            "lane_submode": "responses_core",
            "selected_profile": "core",
            "why_not_cheaper": "",
            "escalation_reason": "",
            "expected_allowance_burn": {},
            "allowed_lanes": ["core"],
            "required_reviewer_lane": "core",
            "final_reviewer_lane": "core",
            "task_meta": {},
            "spark_eligible": False,
            "runtime_model": "ea-coder-hard",
            "lane_capacity": {},
        }

        captured_cmd: list[str] = []
        captured_env: dict[str, str] = {}

        async def fake_run_command(cmd, **kwargs):
            captured_cmd[:] = list(cmd)
            captured_env.update(dict(kwargs.get("env") or {}))
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
                                                "acct-ea-core",
                                                "ea-coder-hard",
                                                "test note",
                                                [],
                                            )
                                        )

        self.assertEqual(captured_cmd[0], "/docker/fleet/scripts/codex-shims/codexea")
        self.assertEqual(captured_cmd[1:3], ["core", "exec"])
        self.assertNotIn("--model", captured_cmd)
        self.assertEqual(captured_env["CODEXEA_MODEL"], "ea-coder-hard")
        self.assertEqual(captured_env["CODEXEA_REASONING_EFFORT"], "high")
        self.assertIn('mcp_servers.ea.required=false', captured_cmd)
        self.assertNotIn('model_provider="ea"', captured_cmd)
        self.assertNotIn('model_providers.ea.base_url="http://host.docker.internal:8090/v1"', captured_cmd)
        self.assertNotIn('model_providers.ea.http_headers={"X-EA-Principal-ID"="codex-fleet"}', captured_cmd)

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

    def test_pick_account_and_model_ignores_cost_budget_for_ea_core_lane(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        decision = {
            "tier": "multi_file_impl",
            "lane": "core",
            "lane_submode": "default",
            "escalation_reason": "complexity",
            "model_preferences": ["ea-coder-hard"],
            "estimated_input_tokens": 1024,
            "estimated_output_tokens": 1024,
            "allowed_lanes": ["core"],
        }
        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            conn.execute(
                """
                UPDATE accounts
                   SET auth_kind='ea',
                       daily_budget_usd=1,
                       monthly_budget_usd=1,
                       allowed_models_json=?,
                       last_used_at=?,
                       updated_at=?
                 WHERE alias='acct-ea-core'
                """,
                (json.dumps(["ea-coder-hard"]), now, now),
            )
        with mock.patch.object(self.controller, "estimate_cost_usd_for_model", return_value=10.0):
            alias, model, note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-core")
        self.assertEqual(model, "ea-coder-hard")
        selected = next(item for item in trace if item.get("alias") == "acct-ea-core")
        self.assertFalse(selected.get("budget_enforced"))

    def test_pick_account_and_model_blocks_protected_operator_for_ordinary_burst(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        config["account_policy"] = {"protected_owner_ids": ["tibor.girschele"]}
        config["accounts"]["acct-chatgpt-core"] = {
            "lane": "core",
            "auth_kind": "api_key",
            "owner_id": "tibor.girschele",
            "drain_policy": "never",
        }
        project_cfg["accounts"] = ["acct-chatgpt-core", "acct-ea-core"]
        project_cfg["account_policy"] = {
            "preferred_accounts": ["acct-chatgpt-core", "acct-ea-core"],
            "allow_api_accounts": True,
            "allow_chatgpt_accounts": True,
        }
        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                VALUES(?, 'api_key', ?, 1, 'ready', ?)
                """,
                ("acct-chatgpt-core", json.dumps(["gpt-5-mini"]), now),
            )
            conn.execute(
                """
                UPDATE accounts
                   SET allowed_models_json=?, updated_at=?
                 WHERE alias='acct-ea-core'
                """,
                (json.dumps(["gpt-5-mini"]), now),
            )
        decision = {
            "tier": "multi_file_impl",
            "lane": "core",
            "lane_submode": "default",
            "escalation_reason": "parallel_impl",
            "model_preferences": ["gpt-5-mini"],
            "estimated_input_tokens": 512,
            "estimated_output_tokens": 256,
            "allowed_lanes": ["core"],
        }

        with mock.patch.object(self.controller, "has_api_key", return_value=True):
            alias, model, _note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-core")
        self.assertEqual(model, "gpt-5-mini")
        protected_trace = next(item for item in trace if item.get("alias") == "acct-chatgpt-core")
        self.assertEqual(protected_trace.get("state"), "rejected")
        self.assertIn("protected operator account reserved", str(protected_trace.get("reason") or ""))

    def test_pick_account_and_model_rejects_unclassified_chatgpt_account_for_ordinary_burst(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        auth_json = repo_root / "acct-unclassified.auth.json"
        auth_json.write_text("{}", encoding="utf-8")
        config["accounts"]["acct-unclassified"] = {
            "lane": "core",
            "auth_kind": "chatgpt_auth_json",
            "auth_json_file": str(auth_json),
        }
        config["accounts"]["acct-safe-api"] = {
            "lane": "core",
            "auth_kind": "api_key",
        }
        project_cfg["accounts"] = ["acct-unclassified", "acct-safe-api"]
        project_cfg["account_policy"] = {
            "preferred_accounts": ["acct-unclassified", "acct-safe-api"],
            "allow_api_accounts": True,
            "allow_chatgpt_accounts": True,
        }
        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, auth_json_file, allowed_models_json, max_parallel_runs, health_state, updated_at)
                VALUES(?, 'chatgpt_auth_json', ?, ?, 1, 'ready', ?)
                """,
                ("acct-unclassified", str(auth_json), json.dumps(["gpt-5-mini"]), now),
            )
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                VALUES(?, 'api_key', ?, 1, 'ready', ?)
                """,
                ("acct-safe-api", json.dumps(["gpt-5-mini"]), now),
            )
        decision = {
            "tier": "multi_file_impl",
            "lane": "core",
            "lane_submode": "default",
            "escalation_reason": "parallel_impl",
            "model_preferences": ["gpt-5-mini"],
            "estimated_input_tokens": 512,
            "estimated_output_tokens": 256,
            "allowed_lanes": ["core"],
        }

        with mock.patch.object(self.controller, "has_api_key", return_value=True):
            alias, model, _note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertNotEqual(alias, "acct-unclassified")
        rejected = next(item for item in trace if item.get("alias") == "acct-unclassified")
        self.assertEqual(rejected.get("state"), "rejected")
        self.assertIn("missing explicit protected/participant/operator classification", str(rejected.get("reason") or ""))

    def test_pick_account_and_model_prefers_protected_operator_for_core_authority(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        config["account_policy"] = {"protected_owner_ids": ["tibor.girschele"]}
        config["accounts"]["acct-chatgpt-core"] = {
            "lane": "core",
            "auth_kind": "api_key",
            "owner_id": "tibor.girschele",
            "drain_policy": "never",
        }
        project_cfg["accounts"] = ["acct-chatgpt-core", "acct-ea-core"]
        project_cfg["account_policy"] = {
            "preferred_accounts": ["acct-chatgpt-core", "acct-ea-core"],
            "allow_api_accounts": True,
            "allow_chatgpt_accounts": True,
        }
        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                VALUES(?, 'api_key', ?, 1, 'ready', ?)
                """,
                ("acct-chatgpt-core", json.dumps(["gpt-5-mini"]), now),
            )
            conn.execute(
                """
                UPDATE accounts
                   SET allowed_models_json=?, updated_at=?
                 WHERE alias='acct-ea-core'
                """,
                (json.dumps(["gpt-5-mini"]), now),
            )
        decision = {
            "tier": "cross_repo_contract",
            "lane": "core",
            "lane_submode": "default",
            "escalation_reason": "contract_authority",
            "requires_contract_authority": True,
            "model_preferences": ["gpt-5-mini"],
            "estimated_input_tokens": 1024,
            "estimated_output_tokens": 256,
            "allowed_lanes": ["core"],
        }

        with mock.patch.object(self.controller, "has_api_key", return_value=True):
            alias, model, _note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-chatgpt-core")
        self.assertEqual(model, "gpt-5-mini")
        protected_trace = next(item for item in trace if item.get("alias") == "acct-chatgpt-core")
        self.assertEqual(protected_trace.get("state"), "selected")
        self.assertEqual(protected_trace.get("dispatch_role"), "core_authority")

    def test_pick_account_and_model_allows_ea_core_for_core_authority_only_package(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        project_cfg["accounts"] = ["acct-ea-core"]
        project_cfg["account_policy"] = {
            "preferred_accounts": ["acct-ea-core"],
            "allow_api_accounts": True,
            "allow_chatgpt_accounts": False,
        }
        now = self.controller.iso(self.controller.utc_now())
        config["accounts"]["acct-ea-core"]["auth_kind"] = "ea"
        with self.controller.db() as conn:
            conn.execute(
                """
                UPDATE accounts
                   SET auth_kind='ea', allowed_models_json=?, health_state='ready', backoff_until=NULL, updated_at=?
                 WHERE alias='acct-ea-core'
                """,
                (json.dumps(["ea-coder-hard-batch"]), now),
            )
        decision = {
            "tier": "bounded_fix",
            "lane": "core_authority",
            "lane_submode": "mcp",
            "escalation_reason": "package_compile_frontier",
            "requires_contract_authority": True,
            "model_preferences": ["ea-coder-hard-batch"],
            "estimated_input_tokens": 1024,
            "estimated_output_tokens": 256,
            "allowed_lanes": ["core_authority"],
        }

        with mock.patch.object(self.controller, "has_ea_runtime_access", return_value=True):
            alias, model, _note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-core")
        self.assertEqual(model, "ea-coder-hard-batch")
        selected_trace = next(item for item in trace if item.get("alias") == "acct-ea-core")
        self.assertEqual(selected_trace.get("state"), "selected")
        self.assertTrue(selected_trace.get("lane_service_allowed"))
        self.assertFalse(selected_trace.get("lane_service_is_exact"))
        self.assertEqual(selected_trace.get("dispatch_role"), "core_authority")

    def test_pick_account_and_model_prefers_participant_funded_for_eligible_burst_work(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        config["accounts"]["acct-participant"] = {
            "lane": "core",
            "auth_kind": "api_key",
            "account_class": "participant_funded",
            "participant_burst_lane": True,
            "participant_lane_role": "coding",
            "participant_project_id": "fleet",
            "explicit_consent": True,
            "token_pool_state": "valid",
        }
        config["accounts"]["acct-ea-core"]["funding_class"] = "operator_funded"
        project_cfg["accounts"] = ["acct-participant", "acct-ea-core"]
        project_cfg["account_policy"] = {
            "preferred_accounts": ["acct-participant", "acct-ea-core"],
            "allow_api_accounts": True,
            "allow_chatgpt_accounts": True,
        }
        project_cfg["participant_burst"] = {
            "enabled": True,
            "allow_chatgpt_accounts": True,
            "eligible_task_classes": ["multi_file_impl"],
            "roles": {
                "coding": {
                    "dispatch_lane": "core",
                    "backend": "chatgpt_participant",
                    "min_authorization_tier": "free",
                }
            },
        }
        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                VALUES(?, 'api_key', ?, 1, 'ready', ?)
                """,
                ("acct-participant", json.dumps(["gpt-5-mini"]), now),
            )
            conn.execute(
                """
                UPDATE accounts
                   SET allowed_models_json=?, updated_at=?
                 WHERE alias='acct-ea-core'
                """,
                (json.dumps(["gpt-5-mini"]), now),
            )
        decision = {
            "tier": "multi_file_impl",
            "lane": "core",
            "lane_submode": "default",
            "escalation_reason": "parallel_impl",
            "model_preferences": ["gpt-5-mini"],
            "estimated_input_tokens": 512,
            "estimated_output_tokens": 256,
            "allowed_lanes": ["core"],
            "task_meta": {
                "participant_eligible": True,
                "premium_required": True,
            },
        }

        with mock.patch.object(self.controller, "has_api_key", return_value=True), mock.patch.object(
            self.controller,
            "quartermaster_capacity_plan",
            return_value={
                "account_order_recommendations": {
                    "core_booster": {
                        "preferred_account_classes": ["participant_funded", "operator_funded"],
                        "blocked_account_classes": ["protected_operator"],
                    }
                }
            },
        ):
            alias, model, _note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-participant")
        self.assertEqual(model, "gpt-5-mini")
        selected = next(item for item in trace if item.get("alias") == "acct-participant")
        self.assertEqual(selected.get("account_order_rank"), 0)

    def test_pick_account_and_model_prefers_operator_funded_when_quartermaster_flags_credit_waste_risk(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        config["accounts"]["acct-participant"] = {
            "lane": "core",
            "auth_kind": "api_key",
            "account_class": "participant_funded",
            "participant_burst_lane": True,
            "participant_lane_role": "coding",
            "participant_project_id": "fleet",
            "explicit_consent": True,
            "token_pool_state": "valid",
        }
        config["accounts"]["acct-ea-core"]["funding_class"] = "operator_funded"
        project_cfg["accounts"] = ["acct-participant", "acct-ea-core"]
        project_cfg["account_policy"] = {
            "preferred_accounts": ["acct-participant", "acct-ea-core"],
            "allow_api_accounts": True,
            "allow_chatgpt_accounts": True,
        }
        project_cfg["participant_burst"] = {
            "enabled": True,
            "allow_chatgpt_accounts": True,
            "eligible_task_classes": ["multi_file_impl"],
            "roles": {
                "coding": {
                    "dispatch_lane": "core",
                    "backend": "chatgpt_participant",
                    "min_authorization_tier": "free",
                }
            },
        }
        now = self.controller.iso(self.controller.utc_now())
        with self.controller.db() as conn:
            conn.execute(
                """
                INSERT INTO accounts(alias, auth_kind, allowed_models_json, max_parallel_runs, health_state, updated_at)
                VALUES(?, 'api_key', ?, 1, 'ready', ?)
                """,
                ("acct-participant", json.dumps(["gpt-5-mini"]), now),
            )
            conn.execute(
                """
                UPDATE accounts
                   SET allowed_models_json=?, updated_at=?
                 WHERE alias='acct-ea-core'
                """,
                (json.dumps(["gpt-5-mini"]), now),
            )
        decision = {
            "tier": "multi_file_impl",
            "lane": "core",
            "lane_submode": "default",
            "escalation_reason": "parallel_impl",
            "model_preferences": ["gpt-5-mini"],
            "estimated_input_tokens": 512,
            "estimated_output_tokens": 256,
            "allowed_lanes": ["core"],
            "task_meta": {
                "participant_eligible": True,
                "premium_required": True,
            },
        }

        with mock.patch.object(self.controller, "has_api_key", return_value=True), mock.patch.object(
            self.controller,
            "quartermaster_capacity_plan",
            return_value={
                "typed_findings": [{"type": "onemin_credit_waste_risk"}],
            },
        ):
            alias, model, _note, trace = self.controller.pick_account_and_model(config, project_cfg, decision)

        self.assertEqual(alias, "acct-ea-core")
        self.assertEqual(model, "gpt-5-mini")
        selected = next(item for item in trace if item.get("alias") == "acct-ea-core")
        self.assertEqual(selected.get("account_order_rank"), 0)

    def test_quartermaster_account_order_recommendation_fallback_prefers_operator_when_participant_pool_is_not_drainable(self) -> None:
        repo_root, config, project_cfg, _slice_item = self._configure_groundwork_loop_fixture()
        config["accounts"]["acct-participant"] = {
            "lane": "core",
            "auth_kind": "chatgpt_auth_json",
            "account_class": "participant_funded",
            "participant_burst_lane": True,
            "explicit_consent": False,
            "token_pool_state": "invalid",
        }
        with mock.patch.object(self.controller, "quartermaster_capacity_plan", return_value={}):
            recommendation = self.controller.quartermaster_account_order_recommendation(config, "core_booster")
        self.assertEqual(recommendation["preferred_account_classes"], ["operator_funded"])

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

    def test_sync_config_to_db_materializes_generated_work_packages_and_scope_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-a",
                        "    title: Slice A",
                        "    allowed_paths:",
                        "      - src/a.py",
                        "  - package_id: fleet-b",
                        "    title: Slice B",
                        "    allowed_paths:",
                        "      - src/b.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)

            packages = self.controller.work_package_rows(project_id="fleet")
            claims = self.controller.scope_claim_rows(project_id="fleet")

            self.assertEqual([row["package_id"] for row in packages], ["fleet-a", "fleet-b"])
            self.assertEqual([row["status"] for row in packages], ["ready", "ready"])
            self.assertEqual(
                [(row["package_id"], row["claim_type"], row["claim_value"], row["claim_state"]) for row in claims],
                [
                    ("fleet-a", "path", "src/a.py", "prepared"),
                    ("fleet-b", "path", "src/b.py", "prepared"),
                ],
            )

    def test_generated_work_packages_require_queue_parity_when_project_queue_is_nonempty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-overlay",
                        "    title: Overlay Slice",
                        "    allowed_paths:",
                        "      - src/overlay.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": ["Queue Slice"],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)

            packages = self.controller.work_package_rows(project_id="fleet")
            self.assertEqual(len(packages), 1)
            self.assertEqual(packages[0]["source_kind"], "queue")
            self.assertEqual(packages[0]["title"], "Queue Slice")
            self.assertNotEqual(packages[0]["package_id"], "fleet-overlay")

    def test_generated_work_packages_use_overlay_when_source_queue_fingerprint_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            queue_items = ["Queue Slice"]
            queue_fingerprint = self.controller.work_package_source_queue_fingerprint(queue_items)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        f"source_queue_fingerprint: {queue_fingerprint}",
                        "work_packages:",
                        "  - package_id: fleet-overlay",
                        "    title: Overlay Slice",
                        "    allowed_paths:",
                        "      - src/overlay.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": list(queue_items),
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)

            packages = self.controller.work_package_rows(project_id="fleet")
            self.assertEqual(len(packages), 1)
            self.assertEqual(packages[0]["source_kind"], "generated")
            self.assertEqual(packages[0]["package_id"], "fleet-overlay")

    def test_generated_work_packages_use_overlay_when_normalized_queue_keeps_raw_source_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            raw_queue_items = ["Queue Slice"]
            queue_fingerprint = self.controller.work_package_source_queue_fingerprint(raw_queue_items)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        f"source_queue_fingerprint: {queue_fingerprint}",
                        "work_packages:",
                        "  - package_id: fleet-overlay",
                        "    title: Overlay Slice",
                        "    allowed_paths:",
                        "      - src/overlay.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            project_cfg = {
                "id": "fleet",
                "path": str(repo_root),
                "queue": [{"title": "Queue Slice", "allowed_lanes": ["core"], "allow_credit_burn": True}],
                "_effective_queue_source_items": list(raw_queue_items),
                "_effective_queue_source_fingerprint": queue_fingerprint,
            }

            packages = self.controller.load_generated_work_packages(project_cfg)

            self.assertEqual(len(packages), 1)
            self.assertEqual(packages[0]["package_id"], "fleet-overlay")

    def test_generated_work_packages_rebind_queue_equivalent_overlay_when_fingerprint_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            published = repo_root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            raw_queue_items = ["Queue Slice"]
            queue_fingerprint = self.controller.work_package_source_queue_fingerprint(raw_queue_items)
            stale_fingerprint = self.controller.work_package_source_queue_fingerprint([])
            package_id = self.controller.default_package_id("fleet", "Queue Slice", 0)
            workpackages_path = published / "WORKPACKAGES.generated.yaml"
            workpackages_path.write_text(
                "\n".join(
                    [
                        f"source_queue_fingerprint: {stale_fingerprint}",
                        "work_packages:",
                        f"  - package_id: {package_id}",
                        "    title: Queue Slice",
                        "    allowed_paths:",
                        "      - src/overlay.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            project_cfg = {
                "id": "fleet",
                "path": str(repo_root),
                "queue": [{"title": "Different Slice", "allowed_lanes": ["core"], "allow_credit_burn": True}],
                "_effective_queue_source_items": list(raw_queue_items),
                "_effective_queue_source_fingerprint": queue_fingerprint,
            }

            packages = self.controller.load_generated_work_packages(project_cfg)

            self.assertEqual(len(packages), 1)
            self.assertEqual(packages[0]["package_id"], package_id)
            payload = self.controller.yaml.safe_load(workpackages_path.read_text(encoding="utf-8")) or {}
            self.assertEqual(payload.get("source_queue_fingerprint"), queue_fingerprint)

    def test_generated_work_packages_do_not_rebind_stale_dict_queue_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            published = repo_root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            raw_queue_items = [{"title": "Queue Slice", "allowed_paths": ["src/current.py"]}]
            queue_fingerprint = self.controller.work_package_source_queue_fingerprint(raw_queue_items)
            stale_fingerprint = self.controller.work_package_source_queue_fingerprint([])
            package_id = self.controller.default_package_id("fleet", "Queue Slice", 0)
            workpackages_path = published / "WORKPACKAGES.generated.yaml"
            workpackages_path.write_text(
                "\n".join(
                    [
                        f"source_queue_fingerprint: {stale_fingerprint}",
                        "work_packages:",
                        f"  - package_id: {package_id}",
                        "    title: Queue Slice",
                        "    allowed_paths:",
                        "      - src/stale.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            project_cfg = {
                "id": "fleet",
                "path": str(repo_root),
                "queue": list(raw_queue_items),
                "_effective_queue_source_items": list(raw_queue_items),
                "_effective_queue_source_fingerprint": queue_fingerprint,
            }

            packages = self.controller.load_generated_work_packages(project_cfg)

            self.assertEqual(packages, [])
            payload = self.controller.yaml.safe_load(workpackages_path.read_text(encoding="utf-8")) or {}
            self.assertEqual(payload.get("source_queue_fingerprint"), stale_fingerprint)

    def test_quartermaster_useful_booster_work_ignores_credit_disabled_core_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)

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
                        "queue": [
                            {
                                "title": "Queue Slice",
                                "allowed_lanes": ["core"],
                                "allow_credit_burn": False,
                            }
                        ],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {
                    "easy": {"id": "easy", "runtime_model": "ea-easy"},
                    "groundwork": {"id": "groundwork", "runtime_model": "ea-groundwork"},
                    "core": {"id": "core", "runtime_model": "ea-coder-hard"},
                },
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)

            useful_work = self.controller.quartermaster_useful_booster_work_count(
                config,
                usage_by_lane={"core_booster": 0},
            )

            self.assertEqual(useful_work, 0)

    def test_generated_work_package_blocks_direct_published_artifact_edits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-a",
                        "    title: Slice A",
                        "    allowed_paths:",
                        "      - .codex-studio/published/STATUS_PLANE.generated.yaml",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)

            package = self.controller.work_package_rows(project_id="fleet")[0]
            self.assertEqual(package["status"], "blocked")
            self.assertEqual(package["task_meta"]["dispatchability_state"], "blocked")
            self.assertIn("generated published artifacts", package["task_meta"]["dispatchability_reason"])

    def test_generated_work_package_promotes_policy_scope_to_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-policy",
                        "    title: Policy Slice",
                        "    allowed_lanes:",
                        "      - core_booster",
                        "      - core",
                        "    allowed_paths:",
                        "      - config/quartermaster.yaml",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {
                    "core": {"id": "core", "runtime_model": "ea-coder-hard"},
                    "core_authority": {"id": "core_authority", "runtime_model": "ea-coder-hard"},
                    "core_booster": {"id": "core_booster", "runtime_model": "ea-coder-hard"},
                },
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)

            package = self.controller.work_package_rows(project_id="fleet")[0]
            self.assertEqual(package["task_meta"]["allowed_lanes"], ["core_authority"])
            self.assertEqual(package["review_lane"], "core_authority")
            self.assertEqual(package["merge_owner_lane"], "core_authority")
            self.assertEqual(package["task_meta"]["required_reviewer_lane"], "core_authority")
            self.assertEqual(package["task_meta"]["final_reviewer_lane"], "core_authority")

    def test_generated_implementation_package_injects_default_denied_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-impl",
                        "    package_kind: implementation",
                        "    title: Implementation Slice",
                        "    allowed_paths:",
                        "      - controller/app.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            package = self.controller.work_package_rows(project_id="fleet")[0]

        denied_paths = set(package["denied_paths"])
        self.assertIn(".codex-studio/published/*.generated.yaml", denied_paths)
        self.assertIn(".codex-design/proposals/**", denied_paths)

    def test_work_package_scope_conflict_ignores_prepared_claims_until_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-a",
                        "    title: Slice A",
                        "    owned_surfaces:",
                        "      - build_root:fleet",
                        "  - package_id: fleet-b",
                        "    title: Slice B",
                        "    owned_surfaces:",
                        "      - build_root:fleet",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)

            packages = self.controller.work_package_rows(project_id="fleet")
            self.assertEqual(self.controller.active_scope_claims_for_project("fleet"), [])
            self.assertIsNone(self.controller.work_package_scope_conflict(packages[0]))

            self.controller.activate_work_package_scope_claims("fleet-a")
            self.assertEqual(
                self.controller.work_package_scope_conflict(packages[1]),
                "scope conflict with fleet-a on surface:build_root:fleet",
            )
            self.controller.sync_work_packages_to_db(config)
            self.assertEqual(
                [claim["claim_state"] for claim in self.controller.scope_claim_rows(package_id="fleet-a")],
                ["active"],
            )
            self.assertEqual(
                self.controller.work_package_scope_conflict(packages[1]),
                "scope conflict with fleet-a on surface:build_root:fleet",
            )

    def test_prepare_work_package_dispatch_candidates_uses_generated_packages_when_project_queue_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-a",
                        "    title: Slice A",
                        "    allowed_paths:",
                        "      - src/a.py",
                        "  - package_id: fleet-b",
                        "    title: Slice B",
                        "    allowed_paths:",
                        "      - src/b.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "project_groups": [
                    {"id": "solo-fleet", "projects": ["fleet"], "mode": "singleton", "captain": {"service_floor": 1}}
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            with self.controller.db() as conn:
                row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()
            self.assertIsNotNone(row)

            candidates = self.controller.prepare_work_package_dispatch_candidates(config, config["projects"][0], row, self.controller.utc_now())
            self.assertEqual([candidate.package_id for candidate in candidates], ["fleet-a", "fleet-b"])
            self.assertTrue(all(candidate.dispatchable for candidate in candidates))
            self.assertEqual(self.controller.project_dispatch_slots_remaining(config, config["projects"][0]), 2)

            self.controller.upsert_runtime_task(
                "fleet",
                package_id="fleet-a",
                task_kind="coding",
                task_state="scheduled",
                payload={"slice_name": "Slice A"},
                started_at=self.controller.utc_now(),
            )

            self.assertEqual(self.controller.project_dispatch_slots_remaining(config, config["projects"][0]), 1)

    def test_compile_project_work_packages_injects_package_compile_for_scope_free_booster_queue(self) -> None:
        project_cfg = {
            "id": "fleet",
            "path": "/tmp/fleet",
            "queue": [
                {
                    "title": "Slice A",
                    "allowed_lanes": ["core_booster", "core"],
                    "allow_credit_burn": True,
                    "premium_required": True,
                },
                {
                    "title": "Slice B",
                    "allowed_lanes": ["core_booster", "core"],
                    "allow_credit_burn": True,
                    "premium_required": True,
                },
            ],
        }
        lanes = {
            "core": {"id": "core", "runtime_model": "ea-coder-hard"},
            "core_authority": {"id": "core_authority", "runtime_model": "ea-coder-hard"},
            "core_booster": {"id": "core_booster", "runtime_model": "ea-coder-hard"},
        }

        packages = self.controller.compile_project_work_packages(project_cfg, lanes=lanes)

        self.assertEqual(packages[0]["package_kind"], "package_compile")
        self.assertEqual(packages[0]["task_meta"]["allowed_lanes"], ["core_authority"])
        self.assertEqual(packages[0]["allowed_paths"], [".codex-studio/published/WORKPACKAGES.generated.yaml"])
        self.assertEqual(packages[1]["dependencies"], [packages[0]["package_id"]])
        self.assertEqual(packages[2]["dependencies"], [packages[0]["package_id"], packages[1]["package_id"]])
        self.assertEqual([packages[1]["queue_index"], packages[2]["queue_index"]], [0, 1])

    def test_compile_project_work_packages_keeps_scoped_queue_packages_parallel_ready(self) -> None:
        project_cfg = {
            "id": "fleet",
            "path": "/tmp/fleet",
            "queue": [
                {
                    "title": "Slice A",
                    "allowed_lanes": ["core_booster", "core"],
                    "allow_credit_burn": True,
                    "premium_required": True,
                    "allowed_paths": ["src/a.py"],
                },
                {
                    "title": "Slice B",
                    "allowed_lanes": ["core_booster", "core"],
                    "allow_credit_burn": True,
                    "premium_required": True,
                    "allowed_paths": ["src/b.py"],
                },
            ],
        }
        lanes = {
            "core": {"id": "core", "runtime_model": "ea-coder-hard"},
            "core_authority": {"id": "core_authority", "runtime_model": "ea-coder-hard"},
            "core_booster": {"id": "core_booster", "runtime_model": "ea-coder-hard"},
        }

        packages = self.controller.compile_project_work_packages(project_cfg, lanes=lanes)

        self.assertEqual([package["package_kind"] for package in packages], ["implementation", "implementation"])
        self.assertEqual(packages[0]["dependencies"], [])
        self.assertEqual(packages[1]["dependencies"], [])

    def test_plan_candidate_launch_requires_scope_lease_for_booster_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            config_root = root / "config"
            config_root.mkdir()
            (config_root / "booster_pools.yaml").write_text(
                "\n".join(
                    [
                        "booster_pools:",
                        "  core_booster:",
                        "    worker_lane: core_booster",
                        "    authority_lane: core_authority",
                        "    rescue_lane: core_rescue",
                        "    lease:",
                        "      require_scope_lease: true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            self.controller.CONFIG_PATH = config_root / "fleet.yaml"
            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            queue_item = {
                "title": "Queue Slice",
                "allowed_lanes": ["core_booster", "core"],
                "allow_credit_burn": True,
                "premium_required": True,
            }
            config = {
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "queue": [queue_item],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "core_booster", "project_safety_cap": 2},
                    }
                ],
                "lanes": {
                    "core": {"id": "core", "runtime_model": "ea-coder-hard"},
                    "core_authority": {"id": "core_authority", "runtime_model": "ea-coder-hard"},
                    "core_booster": {"id": "core_booster", "runtime_model": "ea-coder-hard"},
                },
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            with self.controller.db() as conn:
                row = conn.execute("SELECT * FROM projects WHERE id='fleet'").fetchone()

            candidate = self.controller.DispatchCandidate(
                row=row,
                project_cfg=config["projects"][0],
                queue=[queue_item],
                queue_index=0,
                slice_item=queue_item,
                slice_name="Queue Slice",
                task_meta=dict(queue_item),
                runtime_status="idle",
                cooldown_until=None,
                dispatchable=True,
            )

            with mock.patch.object(self.controller, "selected_feedback_files", return_value=[]):
                with mock.patch.object(
                    self.controller,
                    "classify_tier",
                    return_value={
                        "tier": "bounded_fix",
                        "lane": "core",
                        "reason": "premium bounded fix",
                        "required_reviewer_lane": "core",
                        "task_meta": dict(queue_item),
                        "requires_contract_authority": False,
                    },
                ):
                    planned = self.controller.plan_candidate_launch(config, candidate)

            self.assertIsNone(planned)
            with self.controller.db() as conn:
                project = conn.execute("SELECT status, last_error FROM projects WHERE id='fleet'").fetchone()
            self.assertEqual(project["status"], "waiting_capacity")
            self.assertIn("scope lease required", str(project["last_error"] or ""))

    def test_cross_repo_contract_excludes_core_booster_from_allowed_lanes(self) -> None:
        slice_item = {
            "title": "Align cross repo contract schema for shared queue interfaces",
            "allowed_lanes": ["core_booster", "core", "core_authority"],
            "allow_credit_burn": True,
            "premium_required": True,
        }
        lane_snapshot = {"state": "ready", "providers": []}
        lanes = {
            "easy": {"id": "easy", "runtime_model": "ea-easy"},
            "repair": {"id": "repair", "runtime_model": "ea-coder-fast"},
            "groundwork": {"id": "groundwork", "runtime_model": "ea-groundwork"},
            "core": {"id": "core", "runtime_model": "ea-coder-hard"},
            "core_authority": {"id": "core_authority", "runtime_model": "ea-coder-hard"},
            "core_booster": {"id": "core_booster", "runtime_model": "ea-coder-hard"},
            "survival": {"id": "survival", "runtime_model": "ea-survival"},
        }

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={name: lane_snapshot for name in lanes},
                ):
                    decision = self.controller.classify_tier(
                        {"lanes": lanes},
                        {"id": "fleet"},
                        {"consecutive_failures": 0},
                        slice_item,
                        [],
                    )

        self.assertEqual(decision["tier"], "cross_repo_contract")
        self.assertEqual(decision["lane"], "core")
        self.assertTrue(decision["requires_contract_authority"])
        self.assertNotIn("core_booster", decision["allowed_lanes"])

    def test_project_booster_pool_contract_flattens_nested_pool_safety_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "config"
            config_root.mkdir()
            (config_root / "booster_pools.yaml").write_text(
                "\n".join(
                    [
                        "booster_pools:",
                        "  core_booster:",
                        "    worker_lane: core_booster",
                        "    authority_lane: core_authority",
                        "    rescue_lane: core_rescue",
                        "    safety:",
                        "      default_project_cap: 3",
                        "      hard_project_cap: 5",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.controller.CONFIG_PATH = config_root / "fleet.yaml"

            project_cfg = {"id": "fleet", "booster_pool_contract": {"pool": "core_booster"}}
            contract = self.controller.project_booster_pool_contract({}, project_cfg)

            self.assertEqual(contract["default_project_cap"], 3)
            self.assertEqual(contract["hard_project_cap"], 5)
            self.assertEqual(self.controller.project_runtime_concurrency_cap({}, project_cfg), 3)

    def test_generated_work_package_blocks_design_proposal_outside_proposal_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-design",
                        "    package_kind: design_proposal",
                        "    horizon_family: control-plane",
                        "    title: Design proposal in the wrong place",
                        "    allowed_paths:",
                        "      - src/controller/app.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            package = self.controller.work_package_rows(project_id="fleet")[0]

        self.assertEqual(package["status"], "blocked")
        self.assertIn("design_proposal packages must stay inside proposal-only surfaces", package["task_meta"]["dispatchability_reason"])

    def test_generated_work_package_blocks_design_proposal_without_explicit_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-design",
                        "    package_kind: design_proposal",
                        "    horizon_family: control-plane",
                        "    title: Scope-free proposal",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            package = self.controller.work_package_rows(project_id="fleet")[0]

        self.assertEqual(package["status"], "blocked")
        self.assertIn("design_proposal packages must declare explicit allowed_paths", package["task_meta"]["dispatchability_reason"])

    def test_generated_contract_change_promotes_to_authority_and_locks_horizon_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        "work_packages:",
                        "  - package_id: fleet-contract-a",
                        "    package_kind: contract_change",
                        "    horizon_family: control-plane",
                        "    title: Contract A",
                        "    allowed_lanes:",
                        "      - core_booster",
                        "      - core",
                        "    allowed_paths:",
                        "      - docs/contracts/a.md",
                        "  - package_id: fleet-contract-b",
                        "    package_kind: contract_change",
                        "    horizon_family: control-plane",
                        "    title: Contract B",
                        "    allowed_lanes:",
                        "      - core_booster",
                        "      - core",
                        "    allowed_paths:",
                        "      - docs/contracts/b.md",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

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
                        "queue": [],
                        "enabled": True,
                        "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
                    }
                ],
                "lanes": {
                    "core": {"id": "core", "runtime_model": "ea-coder-hard"},
                    "core_authority": {"id": "core_authority", "runtime_model": "ea-coder-hard"},
                    "core_booster": {"id": "core_booster", "runtime_model": "ea-coder-hard"},
                },
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            packages = self.controller.work_package_rows(project_id="fleet")
            self.controller.activate_work_package_scope_claims("fleet-contract-a")

            self.assertEqual(packages[0]["task_meta"]["allowed_lanes"], ["core_authority"])
            self.assertTrue(packages[0]["task_meta"]["requires_contract_authority"])
            self.assertIn(
                "scope conflict with fleet-contract-a on surface:horizon_family:contract_change:control-plane",
                str(self.controller.work_package_scope_conflict(packages[1])),
            )

    def test_work_package_scope_conflict_detects_overlapping_allowed_path_wildcards(self) -> None:
        self.assertTrue(
            self.controller.scope_claim_conflicts("path", "src/**/*.py", "path", "src/api/routes.py")
        )

    def test_package_changed_paths_within_scope_rejects_denied_and_out_of_scope_paths(self) -> None:
        package = {
            "allowed_paths": ["src/**"],
            "denied_paths": ["src/generated/**"],
            "max_touched_files": 2,
        }

        allowed_ok, allowed_reason = self.controller.package_changed_paths_within_scope(
            package,
            "/docker/fleet",
            changed_paths=["src/main.py"],
        )
        denied_ok, denied_reason = self.controller.package_changed_paths_within_scope(
            package,
            "/docker/fleet",
            changed_paths=["src/generated/schema.py"],
        )
        out_of_scope_ok, out_of_scope_reason = self.controller.package_changed_paths_within_scope(
            package,
            "/docker/fleet",
            changed_paths=["README.md"],
        )

        self.assertTrue(allowed_ok)
        self.assertEqual(allowed_reason, "")
        self.assertFalse(denied_ok)
        self.assertIn("package changed denied path src/generated/schema.py", denied_reason)
        self.assertFalse(out_of_scope_ok)
        self.assertIn("package changed out-of-scope path README.md", out_of_scope_reason)

    def test_package_compile_artifact_requires_fresh_scoped_work_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            published = repo_root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            queue = [{"title": "Slice A"}]
            fingerprint = self.controller.work_package_source_queue_fingerprint(queue)
            package = {
                "package_kind": "package_compile",
                "task_meta": {
                    "package_compile_target_path": ".codex-studio/published/WORKPACKAGES.generated.yaml",
                    "package_compile_source_queue_fingerprint": fingerprint,
                },
                "allowed_paths": [".codex-studio/published/WORKPACKAGES.generated.yaml"],
            }
            project_cfg = {"id": "fleet", "path": str(repo_root)}

            missing_ok, missing_reason = self.controller.package_compile_artifact_valid(project_cfg, package, str(repo_root))
            self.assertFalse(missing_ok)
            self.assertIn("did not materialize", missing_reason)

            (published / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        f"source_queue_fingerprint: {fingerprint}",
                        "work_packages:",
                        "  - package_id: fleet-a",
                        "    title: Slice A",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            unscoped_ok, unscoped_reason = self.controller.package_compile_artifact_valid(project_cfg, package, str(repo_root))
            self.assertFalse(unscoped_ok)
            self.assertIn("explicit allowed_paths or owned_surfaces", unscoped_reason)

            (published / "WORKPACKAGES.generated.yaml").write_text(
                "\n".join(
                    [
                        f"source_queue_fingerprint: {fingerprint}",
                        "work_packages:",
                        "  - package_id: fleet-a",
                        "    title: Slice A",
                        "    allowed_paths:",
                        "      - src/a.py",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fresh_ok, fresh_reason = self.controller.package_compile_artifact_valid(project_cfg, package, str(repo_root))
            self.assertTrue(fresh_ok)
            self.assertEqual(fresh_reason, "")

    def test_promote_package_compile_artifact_copies_overlay_into_canonical_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            worktree_root = root / "worktree"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (worktree_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            overlay_text = (
                "source_queue_fingerprint: abc123\n"
                "work_packages:\n"
                "  - package_id: fleet-a\n"
                "    title: Slice A\n"
                "    allowed_paths:\n"
                "      - src/a.py\n"
            )
            (worktree_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                overlay_text,
                encoding="utf-8",
            )
            package = {
                "package_kind": "package_compile",
                "task_meta": {
                    "package_compile_target_path": ".codex-studio/published/WORKPACKAGES.generated.yaml",
                },
                "allowed_paths": [".codex-studio/published/WORKPACKAGES.generated.yaml"],
            }

            promoted = self.controller.promote_package_compile_artifact(
                {"id": "fleet", "path": str(repo_root)},
                package,
                str(worktree_root),
            )

            self.assertEqual(
                (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").read_text(encoding="utf-8"),
                overlay_text,
            )
            self.assertEqual(
                promoted,
                (repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").resolve(),
            )

    def test_sync_work_packages_uses_promoted_package_compile_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            worktree_root = root / "worktree"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            (worktree_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)

            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.init_db()

            queue_items = ["Queue Slice"]
            queue_fingerprint = self.controller.work_package_source_queue_fingerprint(queue_items)
            package_overlay = (
                f"source_queue_fingerprint: {queue_fingerprint}\n"
                "work_packages:\n"
                "  - package_id: fleet-overlay\n"
                "    title: Overlay Slice\n"
                "    allowed_paths:\n"
                "      - src/overlay.py\n"
            )
            (worktree_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml").write_text(
                package_overlay,
                encoding="utf-8",
            )
            project_cfg = {
                "id": "fleet",
                "path": str(repo_root),
                "queue": list(queue_items),
                "_effective_queue_source_items": list(queue_items),
                "_effective_queue_source_fingerprint": queue_fingerprint,
                "enabled": True,
                "booster_pool_contract": {"pool": "operator_funded", "project_safety_cap": 2},
            }
            config = {
                "projects": [project_cfg],
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "accounts": {},
            }

            self.controller.sync_config_to_db(config)
            compile_package = {
                "package_kind": "package_compile",
                "task_meta": {
                    "package_compile_target_path": ".codex-studio/published/WORKPACKAGES.generated.yaml",
                },
                "allowed_paths": [".codex-studio/published/WORKPACKAGES.generated.yaml"],
            }

            self.controller.promote_package_compile_artifact(project_cfg, compile_package, str(worktree_root))
            self.controller.sync_work_packages_to_db(config)

            packages = self.controller.work_package_rows(project_id="fleet")
            active_packages = [row for row in packages if str(row.get("status") or "").strip().lower() != "archived"]

            self.assertEqual(len(active_packages), 1)
            self.assertEqual(active_packages[0]["package_id"], "fleet-overlay")
            self.assertEqual(active_packages[0]["source_kind"], "generated")

    def test_effective_project_verify_cmd_skips_repo_wide_verify_for_package_compile(self) -> None:
        project_cfg = {"verify_cmd": "python3 scripts/check_consistency.py"}

        verify_cmd = self.controller.effective_project_verify_cmd(
            project_cfg,
            package_row={"package_kind": "package_compile"},
        )
        normal_verify_cmd = self.controller.effective_project_verify_cmd(
            project_cfg,
            package_row={"package_kind": "implementation"},
        )

        self.assertEqual(verify_cmd, "")
        self.assertEqual(normal_verify_cmd, "python3 scripts/check_consistency.py")

    def test_package_changed_paths_within_scope_rejects_scope_free_design_proposals(self) -> None:
        ok, reason = self.controller.package_changed_paths_within_scope(
            {"package_kind": "design_proposal", "allowed_paths": []},
            "/docker/fleet",
            changed_paths=["src/controller.py"],
        )

        self.assertFalse(ok)
        self.assertEqual(reason, "design_proposal packages require explicit allowed_paths")

    def test_design_mirror_tracks_future_capability_registry_docs(self) -> None:
        for rel in (
            ".codex-design/product/HORIZONS.md",
            ".codex-design/product/HORIZON_SIGNAL_POLICY.md",
            ".codex-design/product/LTD_CAPABILITY_MAP.md",
            ".codex-design/product/PUBLIC_GUIDE_POLICY.md",
            ".codex-design/product/PUBLIC_MEDIA_AND_GUIDE_ASSET_POLICY.md",
            ".codex-design/product/EXTERNAL_TOOLS_PLANE.md",
            ".codex-design/product/START_HERE.md",
            ".codex-design/product/GLOSSARY.md",
            ".codex-design/product/RELEASE_PIPELINE.md",
            ".codex-design/product/METRICS_AND_SLOS.yaml",
        ):
            self.assertIn(rel, self.controller.DESIGN_MIRROR_PRODUCT_FILES)

    def test_sync_design_repo_mirrors_expands_product_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            design_root = root / "design"
            repo_root = root / "fleet"
            (design_root / "products" / "chummer" / "projects").mkdir(parents=True, exist_ok=True)
            (design_root / "products" / "chummer" / "review").mkdir(parents=True, exist_ok=True)
            repo_root.mkdir()

            (design_root / "products" / "chummer" / "README.md").write_text("product readme", encoding="utf-8")
            (design_root / "products" / "chummer" / "START_HERE.md").write_text("start here", encoding="utf-8")
            (design_root / "products" / "chummer" / "projects" / "fleet.md").write_text("repo scope", encoding="utf-8")
            (design_root / "products" / "chummer" / "review" / "fleet.AGENTS.template.md").write_text("review scope", encoding="utf-8")
            (design_root / "products" / "chummer" / "sync").mkdir(parents=True, exist_ok=True)
            (design_root / "products" / "chummer" / "sync" / "sync-manifest.yaml").write_text(
                """
product_source_groups:
  base_governance:
    - products/chummer/README.md
    - products/chummer/START_HERE.md
mirrors:
  - repo: fleet
    product_groups: [base_governance]
    repo_source: products/chummer/projects/fleet.md
    review_source: products/chummer/review/fleet.AGENTS.template.md
""".strip(),
                encoding="utf-8",
            )
            config = {
                "projects": [
                    {"id": "design", "path": str(design_root)},
                    {"id": "fleet", "path": str(repo_root)},
                ]
            }

            results = self.controller.sync_design_repo_mirrors(config)

            self.assertEqual(len(results), 1)
            self.assertEqual((repo_root / ".codex-design" / "product" / "README.md").read_text(encoding="utf-8"), "product readme")
            self.assertEqual((repo_root / ".codex-design" / "product" / "START_HERE.md").read_text(encoding="utf-8"), "start here")
            self.assertEqual(
                (repo_root / ".codex-design" / "repo" / "IMPLEMENTATION_SCOPE.md").read_text(encoding="utf-8"),
                "repo scope",
            )
            self.assertEqual(
                (repo_root / ".codex-design" / "review" / "REVIEW_CONTEXT.md").read_text(encoding="utf-8"),
                "review scope",
            )


if __name__ == "__main__":
    unittest.main()
