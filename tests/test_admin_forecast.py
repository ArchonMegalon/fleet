from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import yaml


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

    def test_resolved_ea_status_settings_falls_back_to_local_ea_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_ea_env = root / "runtime.ea.env"
            runtime_ea_env.write_text(
                "EA_MCP_BASE_URL=http://host.docker.internal:8090\nEA_MCP_PRINCIPAL_ID=codex-fleet\n",
                encoding="utf-8",
            )
            local_ea_env = root / "ea.env"
            local_ea_env.write_text("EA_API_TOKEN=secret-token-from-ea-env\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "FLEET_SECRET_ENV_PATHS": f"{runtime_ea_env}:{local_ea_env}",
                    "EA_MCP_BASE_URL": "",
                    "EA_BASE_URL": "",
                    "EA_MCP_API_TOKEN": "",
                    "EA_API_TOKEN": "",
                    "EA_MCP_PRINCIPAL_ID": "",
                    "EA_PRINCIPAL_ID": "",
                },
                clear=False,
            ):
                admin = load_admin_module()
                settings = admin.resolved_ea_status_settings()

            self.assertEqual(settings["base_url"], "http://host.docker.internal:8090")
            self.assertEqual(settings["api_token"], "secret-token-from-ea-env")
            self.assertEqual(settings["principal_id"], "codex-fleet")

    def test_onemin_codexer_runtime_payload_counts_only_onemin_profile_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE accounts (alias TEXT PRIMARY KEY, auth_kind TEXT NOT NULL)")
            conn.execute(
                "CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, account_alias TEXT, model TEXT, job_kind TEXT, status TEXT)"
            )
            conn.executemany(
                "INSERT INTO accounts(alias, auth_kind) VALUES(?, ?)",
                [
                    ("acct-ea-core", "ea"),
                    ("acct-ea-survival", "ea"),
                    ("acct-chatgpt-archon", "chatgpt_auth_json"),
                ],
            )
            conn.executemany(
                "INSERT INTO runs(project_id, account_alias, model, job_kind, status) VALUES(?, ?, ?, ?, ?)",
                [
                    ("core", "acct-ea-core", "ea-coder-hard", "coding", "running"),
                    ("ui", "acct-ea-survival", "ea-coder-survival", "coding", "running"),
                    ("hub", "acct-chatgpt-archon", "gpt-5.3-codex", "coding", "running"),
                ],
            )
            conn.commit()
            conn.close()

            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {
                "profiles": [
                    {"model": "ea-coder-hard", "provider_hint_order": ["onemin"]},
                    {"model": "ea-coder-survival", "provider_hint_order": ["browseract"]},
                ]
            }

            payload = self.admin.onemin_codexer_runtime_payload()

            self.assertEqual(payload["active_onemin_codexers"], 1)
            self.assertEqual(payload["active_onemin_booster_codexers"], 0)
            self.assertEqual(payload["active_onemin_projects"], ["core"])
            self.assertEqual(payload["active_onemin_accounts"], ["acct-ea-core"])

    def test_ea_onemin_manager_billing_aggregate_backfills_active_leases_from_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE accounts (alias TEXT PRIMARY KEY, auth_kind TEXT NOT NULL)")
            conn.execute(
                "CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, account_alias TEXT, model TEXT, job_kind TEXT, status TEXT)"
            )
            conn.execute("INSERT INTO accounts(alias, auth_kind) VALUES('acct-ea-core', 'ea')")
            conn.execute(
                "INSERT INTO runs(project_id, account_alias, model, job_kind, status) VALUES('fleet', 'acct-ea-core', 'ea-coder-hard-batch', 'coding', 'running')"
            )
            conn.commit()
            conn.close()

            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {
                "profiles": [
                    {"model": "ea-coder-hard-batch", "provider_hint_order": ["onemin"]},
                ]
            }
            self.admin.ea_onemin_manager_status = lambda force=False, cache_only=False: {
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

            aggregate = self.admin.ea_onemin_manager_billing_aggregate()
            card = self.admin.provider_credit_card_payload()

            self.assertEqual(aggregate["active_lease_count"], 1)
            self.assertEqual(aggregate["reported_active_lease_count"], 0)
            self.assertEqual(aggregate["runtime_active_lease_count"], 1)
            self.assertEqual(aggregate["active_lease_count_source"], "fleet_runtime_backfill")
            self.assertEqual(aggregate["active_onemin_projects"], ["fleet"])
            self.assertEqual(card["active_lease_count"], 1)
            self.assertEqual(card["active_lease_count_source"], "fleet_runtime_backfill")

    def test_ea_onemin_manager_billing_aggregate_falls_back_to_cached_browseract_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_root = Path(tmpdir)
            cached_path = runtime_root / "onemin_aggregate_billing_full_refresh_latest.json"
            cached_path.write_text(
                json.dumps(
                    {
                        "sum_free_credits": 43_826_189,
                        "sum_max_credits": 0,
                        "remaining_percent_total": 42.67,
                        "hours_until_next_topup": 0.0,
                        "hours_remaining_at_current_pace_no_topup": 253.29,
                        "days_remaining_including_next_topup_at_7d_avg": 10.55,
                        "slot_count_with_billing_snapshot": 69,
                        "slot_count_with_member_reconciliation": 41,
                        "basis_summary": "actual_billing_usage_page x69",
                        "basis_counts": {"actual_billing_usage_page": 10, "actual_provider_api": 59},
                        "latest_member_reconciliation_at": 1767225600,
                        "last_actual_balance_check_at": 1767312000,
                        "recorded_at_utc": "2026-04-28T17:03:52Z",
                        "payload_source": "browseract_refresh_summary",
                    }
                ),
                encoding="utf-8",
            )

            old_runtime_root = self.admin.ONEMIN_AGGREGATE_RUNTIME_ROOT
            self.admin.ONEMIN_AGGREGATE_RUNTIME_ROOT = runtime_root
            self.addCleanup(setattr, self.admin, "ONEMIN_AGGREGATE_RUNTIME_ROOT", old_runtime_root)
            self.admin.ea_onemin_manager_status = lambda force=False, cache_only=False: {
                "aggregate": {
                    "sum_free_credits": 1000,
                    "sum_max_credits": 2000,
                    "active_lease_count": 0,
                    "actual_billing_account_count": 0,
                    "accounts": [],
                },
                "runway": {
                    "current_burn_per_hour": 25,
                    "hours_remaining_current_pace": 40,
                },
            }
            self.admin.onemin_codexer_runtime_payload = lambda cache_only=False: {
                "active_onemin_codexers": 0,
                "active_onemin_projects": ["fleet"],
                "active_onemin_accounts": ["acct-ea-core"],
            }

            aggregate = self.admin.ea_onemin_manager_billing_aggregate()
            card = self.admin.provider_credit_card_payload()
            credit_guard = self.admin._participant_credit_guard_status(
                {"credit_guard": {"enabled": True, "provider": "onemin"}, "max_active_workers": 1},
                sponsor_ready_lanes=0,
                provider_credit=card,
            )

        self.assertEqual(aggregate["source"], "browseract_refresh_summary")
        self.assertEqual(aggregate["slot_count_with_billing_snapshot"], 69)
        self.assertEqual(aggregate["slot_count_with_member_reconciliation"], 41)
        self.assertEqual(aggregate["latest_member_reconciliation_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(aggregate["last_actual_balance_check_at"], "2026-01-02T00:00:00Z")
        self.assertEqual(card["basis_quality"], "mixed")
        self.assertTrue(credit_guard["billing_known"])
        self.assertTrue(credit_guard["next_worker_safe"])
        self.assertEqual(credit_guard["reason"], "topup_due_now")

    def test_active_run_rows_excludes_orphaned_unlinked_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute(
                "CREATE TABLE projects (id TEXT PRIMARY KEY, status TEXT, active_run_id INTEGER)"
            )
            conn.execute(
                "CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, status TEXT, finished_at TEXT)"
            )
            conn.execute("INSERT INTO projects(id, status, active_run_id) VALUES('fleet', 'dispatch_pending', NULL)")
            conn.execute("INSERT INTO projects(id, status, active_run_id) VALUES('ui', 'running', 2)")
            conn.execute("INSERT INTO runs(id, project_id, status, finished_at) VALUES(1, 'fleet', 'running', NULL)")
            conn.execute("INSERT INTO runs(id, project_id, status, finished_at) VALUES(2, 'ui', 'running', NULL)")
            conn.commit()
            conn.close()

            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)

            rows = self.admin.active_run_rows()

        self.assertEqual([int(row["id"]) for row in rows], [2])

    def test_eligible_account_aliases_excludes_reserved_and_unclassified_chatgpt_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE accounts (alias TEXT PRIMARY KEY, auth_kind TEXT NOT NULL, auth_json_file TEXT, max_parallel_runs INTEGER, health_state TEXT, updated_at TEXT)"
            )
            conn.execute(
                "CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT, account_alias TEXT, status TEXT, job_kind TEXT, estimated_cost_usd REAL, started_at TEXT)"
            )
            now = self.admin.iso(self.admin.utc_now())
            auth_json = Path(tmpdir) / "auth.json"
            auth_json.write_text("{}", encoding="utf-8")
            conn.executemany(
                "INSERT INTO accounts(alias, auth_kind, auth_json_file, max_parallel_runs, health_state, updated_at) VALUES(?, ?, ?, 1, 'ready', ?)",
                [
                    ("acct-unclassified", "chatgpt_auth_json", str(auth_json), now),
                    ("acct-safe-api", "api_key", "", now),
                    ("acct-protected", "api_key", "", now),
                ],
            )
            conn.commit()
            conn.close()

            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            config = {
                "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                "accounts": {
                    "acct-unclassified": {"auth_kind": "chatgpt_auth_json", "auth_json_file": str(auth_json)},
                    "acct-safe-api": {"auth_kind": "api_key"},
                    "acct-protected": {"auth_kind": "api_key", "owner_id": "tibor.girschele"},
                },
            }
            project = {
                "account_policy": {
                    "preferred_accounts": ["acct-unclassified", "acct-safe-api", "acct-protected"],
                    "allow_chatgpt_accounts": True,
                    "allow_api_accounts": True,
                },
                "accounts": ["acct-unclassified", "acct-safe-api", "acct-protected"],
            }

            eligible = self.admin.eligible_account_aliases(config, project, self.admin.utc_now())

            self.assertEqual(eligible, ["acct-safe-api"])

    def test_ea_onemin_manager_billing_aggregate_infers_topup_eta_from_billing_cycle(self) -> None:
        fixed_now = self.admin.dt.datetime(2026, 3, 23, 11, 10, 2, tzinfo=self.admin.dt.timezone.utc)
        with mock.patch.object(self.admin, "utc_now", return_value=fixed_now):
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {"profiles": []}
            self.admin.ea_onemin_manager_status = lambda force=False, cache_only=False: {
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

            aggregate = self.admin.ea_onemin_manager_billing_aggregate()
            card = self.admin.provider_credit_card_payload()

        self.assertEqual(aggregate["topup_eta_source"], "billing_cycle_fallback")
        self.assertEqual(aggregate["next_topup_at"], "2026-04-22T11:10:02Z")
        self.assertAlmostEqual(aggregate["hours_until_next_topup"], 720.0, places=2)
        self.assertEqual(card["topup_eta_source"], "billing_cycle_fallback")

    def test_ea_onemin_manager_billing_aggregate_replaces_stale_past_topup_eta(self) -> None:
        fixed_now = self.admin.dt.datetime(2026, 3, 23, 11, 10, 2, tzinfo=self.admin.dt.timezone.utc)
        with mock.patch.object(self.admin, "utc_now", return_value=fixed_now):
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {"profiles": []}
            self.admin.ea_onemin_manager_status = lambda force=False, cache_only=False: {
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

            aggregate = self.admin.ea_onemin_manager_billing_aggregate()
            card = self.admin.provider_credit_card_payload()

        self.assertEqual(aggregate["topup_eta_source"], "billing_cycle_fallback")
        self.assertEqual(aggregate["next_topup_at"], "2026-04-22T11:10:02Z")
        self.assertAlmostEqual(aggregate["hours_until_next_topup"], 720.0, places=2)
        self.assertEqual(card["topup_eta_source"], "billing_cycle_fallback")

    def test_work_package_summary_payload_counts_waiting_dependency_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            now = self.admin.iso(self.admin.utc_now())
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE work_packages (
                    package_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    queue_index INTEGER NOT NULL DEFAULT 0,
                    priority INTEGER NOT NULL DEFAULT 100,
                    title TEXT NOT NULL,
                    slice_name TEXT NOT NULL,
                    task_meta_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'ready',
                    runtime_state TEXT NOT NULL DEFAULT 'idle',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE scope_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    claim_value TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    claim_state TEXT NOT NULL DEFAULT 'prepared',
                    created_at TEXT NOT NULL,
                    activated_at TEXT,
                    released_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO work_packages(
                    package_id, project_id, queue_index, title, slice_name, task_meta_json, created_at, updated_at,
                    status, runtime_state
                )
                VALUES(?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "fleet-ready",
                    "fleet",
                    "Ready slice",
                    "Ready slice",
                    json.dumps({"allowed_lanes": ["core_booster", "core"], "allow_credit_burn": True}),
                    now,
                    now,
                    "ready",
                    "idle",
                ),
            )
            conn.execute(
                """
                INSERT INTO work_packages(
                    package_id, project_id, queue_index, title, slice_name, task_meta_json, created_at, updated_at,
                    status, runtime_state
                )
                VALUES(?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "fleet-next",
                    "fleet",
                    "Next slice",
                    "Next slice",
                    json.dumps({"allowed_lanes": ["easy"], "allow_credit_burn": False}),
                    now,
                    now,
                    "waiting_dependency",
                    "idle",
                ),
            )
            conn.commit()
            conn.close()

            payload = self.admin.work_package_summary_payload({"lanes": {"core": {"id": "core"}, "easy": {"id": "easy"}}})

        self.assertEqual(payload["ready_packages"], 1)
        self.assertEqual(payload["ready_booster_packages"], 1)
        self.assertEqual(payload["waiting_dependency_packages"], 1)
        self.assertEqual(payload["waiting_dependency_booster_packages"], 0)
        self.assertEqual(payload["ready_scope_cap"], 1)
        self.assertEqual(payload["ready_booster_scope_cap"], 1)

    def test_work_package_summary_payload_ignores_stale_active_scope_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            now = self.admin.iso(self.admin.utc_now())
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE work_packages (
                    package_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    queue_index INTEGER NOT NULL DEFAULT 0,
                    priority INTEGER NOT NULL DEFAULT 100,
                    title TEXT NOT NULL,
                    slice_name TEXT NOT NULL,
                    task_meta_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'ready',
                    runtime_state TEXT NOT NULL DEFAULT 'idle',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE scope_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    claim_value TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    claim_state TEXT NOT NULL DEFAULT 'prepared',
                    created_at TEXT NOT NULL,
                    activated_at TEXT,
                    released_at TEXT
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO work_packages(
                    package_id, project_id, queue_index, title, slice_name, task_meta_json, created_at, updated_at,
                    status, runtime_state
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "fleet-ready",
                        "fleet",
                        0,
                        "Ready slice",
                        "Ready slice",
                        json.dumps(
                            {
                                "allowed_lanes": ["core_booster", "core"],
                                "allow_credit_burn": True,
                            }
                        ),
                        now,
                        now,
                        "ready",
                        "idle",
                    ),
                    (
                        "fleet-old",
                        "fleet",
                        1,
                        "Old slice",
                        "Old slice",
                        json.dumps(
                            {
                                "allowed_lanes": ["core_booster", "core"],
                                "allow_credit_burn": True,
                            }
                        ),
                        now,
                        now,
                        "complete",
                        "idle",
                    ),
                ],
            )
            conn.executemany(
                """
                INSERT INTO scope_claims(package_id, project_id, claim_type, claim_value, scope_key, claim_state, created_at, activated_at)
                VALUES(?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                [
                    ("fleet-ready", "fleet", "path", ".codex-design", "path:.codex-design", now, now),
                    ("fleet-old", "fleet", "path", ".codex-design", "path:.codex-design", now, now),
                ],
            )
            conn.commit()
            conn.close()

            payload = self.admin.work_package_summary_payload({"lanes": {"core": {"id": "core"}}})

        self.assertEqual(payload["ready_packages"], 1)
        self.assertEqual(payload["ready_booster_packages"], 1)
        self.assertEqual(payload["ready_scope_cap"], 1)
        self.assertEqual(payload["ready_booster_scope_cap"], 1)
        self.assertEqual(payload["active_scope_claims"], 0)
        self.assertEqual(payload["stale_active_scope_claims"], 2)

    def test_merge_queue_overlay_item_stamps_pre_overlay_queue_fingerprint_from_queue_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "WORKLIST.md").write_text(
                "| ID | Status | Owner | Task | Notes | Updated |\n"
                "| --- | --- | --- | --- | --- | --- |\n"
                "| wl-001 | todo |  | Prepare sourced slice |  | 2026-03-24 |\n",
                encoding="utf-8",
            )
            project = {
                "path": str(root),
                "queue": ["Existing queue slice"],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "append"}],
            }

            overlay_path = self.admin.merge_queue_overlay_item(project, "Overlay queue slice", mode="append")

            payload = self.admin.load_yaml(overlay_path)
            expected_fingerprint = self.admin.work_package_source_queue_fingerprint(
                ["Existing queue slice", "Prepare sourced slice"]
            )

            self.assertEqual(payload["mode"], "append")
            self.assertEqual(payload["items"], ["Overlay queue slice"])
            self.assertEqual(payload["source_queue_fingerprint"], expected_fingerprint)

    def test_merge_queue_overlay_item_preserves_structured_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = {
                "path": str(root),
                "queue": ["Existing queue slice"],
            }
            structured_item = {
                "package_id": "audit-task-17",
                "title": "Structured overlay slice",
                "allowed_lanes": ["core_booster"],
            }

            overlay_path = self.admin.merge_queue_overlay_item(project, structured_item, mode="append")
            payload = self.admin.load_yaml(overlay_path)

            self.assertEqual(payload["mode"], "append")
            self.assertEqual(payload["items"], [structured_item])

    def test_merge_queue_overlay_item_replaces_existing_structured_item_with_same_package_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            published = root / ".codex-studio" / "published"
            published.mkdir(parents=True, exist_ok=True)
            published.joinpath("QUEUE.generated.yaml").write_text(
                yaml.safe_dump(
                    {
                        "mode": "append",
                        "items": [
                            {
                                "package_id": "audit-task-17",
                                "title": "Older queue slice",
                                "task": "Older queue slice",
                            },
                            {
                                "package_id": "audit-task-17",
                                "title": "Newest queue slice",
                                "task": "Newest queue slice",
                                "source_items": ["a", "b"],
                            },
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            project = {
                "path": str(root),
                "queue": ["Existing queue slice"],
            }
            replacement_item = {
                "package_id": "audit-task-17",
                "title": "Replacement queue slice",
                "task": "Replacement queue slice",
                "source_items": ["bundle"],
            }

            overlay_path = self.admin.merge_queue_overlay_item(project, replacement_item, mode="append")
            payload = self.admin.load_yaml(overlay_path)

            self.assertEqual(payload["mode"], "append")
            self.assertEqual(payload["items"], [replacement_item])

    def test_audit_candidate_queue_overlay_item_preserves_structured_metadata(self) -> None:
        candidate = {
            "id": 17,
            "scope_id": "fleet",
            "finding_key": "project.design_mirror_missing_or_stale",
            "title": "Refresh local design mirror",
            "detail": "Sync the approved Chummer design bundle into `fleet` under `.codex-design/` and refresh repo-local review context.",
            "task_meta_json": json.dumps(
                {
                    "allowed_lanes": ["core_booster"],
                    "allow_credit_burn": True,
                    "design_owner": "fleet-platform",
                }
            ),
        }

        item = self.admin.audit_candidate_queue_overlay_item(candidate)

        self.assertEqual(item["package_id"], "audit-task-17")
        self.assertEqual(item["source_ref"], "audit_task_candidates[17]")
        self.assertEqual(item["title"], candidate["detail"])
        self.assertEqual(item["task"], candidate["detail"])
        self.assertEqual(item["allowed_lanes"], ["core_booster"])
        self.assertTrue(item["allow_credit_burn"])
        self.assertEqual(item["design_owner"], "fleet-platform")
        self.assertEqual(item["allowed_paths"], [".codex-design"])
        self.assertEqual(item["owned_surfaces"], ["design_mirror:fleet"])

    def test_audit_candidate_materialization_texts_ignore_resolved_published_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            self.admin.DB_PATH = db_path
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE audit_task_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    finding_key TEXT NOT NULL,
                    task_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    task_meta_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'open',
                    source TEXT NOT NULL DEFAULT 'fleet-auditor',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )
            conn.commit()
            conn.close()
            now = self.admin.iso(self.admin.utc_now())
            with self.admin.db() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_task_candidates(
                        scope_type, scope_id, finding_key, task_index, title, detail, task_meta_json, status, source,
                        first_seen_at, last_seen_at, resolved_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "project",
                        "fleet",
                        "project.design_mirror_missing_or_stale",
                        0,
                        "Refresh local design mirror",
                        "Sync the approved Chummer design bundle into `fleet` under `.codex-design/`.",
                        "{}",
                        "published",
                        "fleet-auditor",
                        now,
                        now,
                        now,
                    ),
                )

            texts = self.admin.audit_candidate_materialization_texts("project", "fleet")

            self.assertEqual(texts, [])

    def test_onemin_codexer_runtime_payload_falls_back_to_batch_model_when_profiles_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE accounts (alias TEXT PRIMARY KEY, auth_kind TEXT NOT NULL)")
            conn.execute(
                "CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, account_alias TEXT, model TEXT, job_kind TEXT, status TEXT)"
            )
            conn.execute("INSERT INTO accounts(alias, auth_kind) VALUES('acct-ea-core', 'ea')")
            conn.execute(
                "INSERT INTO runs(project_id, account_alias, model, job_kind, status) VALUES('fleet', 'acct-ea-core', 'ea-coder-hard-batch', 'coding', 'running')"
            )
            conn.commit()
            conn.close()

            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {}

            payload = self.admin.onemin_codexer_runtime_payload()

            self.assertEqual(payload["active_onemin_codexers"], 1)
            self.assertEqual(payload["active_onemin_booster_codexers"], 0)
            self.assertEqual(payload["active_onemin_accounts"], ["acct-ea-core"])

    def test_onemin_codexer_runtime_payload_backfills_from_design_supervisor_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            accounts_path = root / "accounts.yaml"
            accounts_path.write_text(
                yaml.safe_dump(
                    {
                        "accounts": {
                            "acct-ea-core": {
                                "auth_kind": "ea",
                                "allowed_models": ["ea-coder-hard"],
                            },
                            "acct-ea-fleet": {
                                "auth_kind": "ea",
                                "allowed_models": ["ea-gemini-flash"],
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            state_root = root / "chummer_design_supervisor"
            (state_root / "shard-1").mkdir(parents=True, exist_ok=True)
            (state_root / "shard-2").mkdir(parents=True, exist_ok=True)
            (state_root / "active_shards.json").write_text(
                json.dumps(
                    {
                        "active_shards": [
                            {"name": "shard-1", "worker_lane": "core"},
                            {"name": "shard-2", "worker_lane": "easy"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "active_run": {
                            "run_id": "run-1",
                            "selected_account_alias": "acct-ea-core",
                            "selected_model": "ea-coder-hard",
                        }
                    }
                ),
                encoding="utf-8",
            )
            (state_root / "shard-2" / "state.json").write_text(
                json.dumps(
                    {
                        "active_run": {
                            "run_id": "run-2",
                            "selected_account_alias": "acct-ea-fleet",
                            "selected_model": "default",
                        }
                    }
                ),
                encoding="utf-8",
            )

            old_db_path = self.admin.DB_PATH
            old_accounts_path = self.admin.ACCOUNTS_PATH
            old_state_root = self.admin.DESIGN_SUPERVISOR_STATE_ROOT
            self.admin.DB_PATH = root / "missing.db"
            self.admin.ACCOUNTS_PATH = accounts_path
            self.admin.DESIGN_SUPERVISOR_STATE_ROOT = state_root
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            self.addCleanup(setattr, self.admin, "ACCOUNTS_PATH", old_accounts_path)
            self.addCleanup(setattr, self.admin, "DESIGN_SUPERVISOR_STATE_ROOT", old_state_root)
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {
                "profiles": [
                    {"model": "ea-coder-hard", "provider_hint_order": ["onemin"]},
                ]
            }

            payload = self.admin.onemin_codexer_runtime_payload()

            self.assertEqual(payload["active_onemin_codexers"], 1)
            self.assertEqual(payload["active_onemin_booster_codexers"], 0)
            self.assertEqual(payload["active_onemin_accounts"], ["acct-ea-core"])
            self.assertEqual(payload["active_onemin_lane_usage"], {"core": 1})
            self.assertEqual(payload["active_onemin_projects"], ["chummer_design_supervisor"])

    def test_ea_onemin_manager_billing_aggregate_backfills_active_leases_from_design_supervisor_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            accounts_path = root / "accounts.yaml"
            accounts_path.write_text(
                yaml.safe_dump(
                    {
                        "accounts": {
                            "acct-ea-core": {
                                "auth_kind": "ea",
                                "allowed_models": ["ea-coder-hard-batch"],
                            },
                        }
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            state_root = root / "chummer_design_supervisor"
            (state_root / "shard-1").mkdir(parents=True, exist_ok=True)
            (state_root / "active_shards.json").write_text(
                json.dumps({"active_shards": [{"name": "shard-1", "worker_lane": "core"}]}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "active_run": {
                            "run_id": "run-1",
                            "selected_account_alias": "acct-ea-core",
                            "selected_model": "ea-coder-hard-batch",
                        }
                    }
                ),
                encoding="utf-8",
            )

            old_db_path = self.admin.DB_PATH
            old_accounts_path = self.admin.ACCOUNTS_PATH
            old_state_root = self.admin.DESIGN_SUPERVISOR_STATE_ROOT
            self.admin.DB_PATH = root / "missing.db"
            self.admin.ACCOUNTS_PATH = accounts_path
            self.admin.DESIGN_SUPERVISOR_STATE_ROOT = state_root
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            self.addCleanup(setattr, self.admin, "ACCOUNTS_PATH", old_accounts_path)
            self.addCleanup(setattr, self.admin, "DESIGN_SUPERVISOR_STATE_ROOT", old_state_root)
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {
                "profiles": [
                    {"model": "ea-coder-hard-batch", "provider_hint_order": ["onemin"]},
                ]
            }
            self.admin.ea_onemin_manager_status = lambda force=False, cache_only=False: {
                "aggregate": {
                    "sum_free_credits": 1000,
                    "sum_max_credits": 2000,
                    "active_lease_count": 0,
                    "accounts": [],
                },
                "runway": {
                    "current_burn_per_hour": None,
                    "hours_remaining_current_pace": None,
                },
            }

            aggregate = self.admin.ea_onemin_manager_billing_aggregate()

            self.assertEqual(aggregate["active_lease_count"], 1)
            self.assertEqual(aggregate["runtime_active_lease_count"], 1)
            self.assertEqual(aggregate["active_lease_count_source"], "fleet_runtime_backfill")
            self.assertEqual(aggregate["active_onemin_projects"], ["chummer_design_supervisor"])
            self.assertEqual(aggregate["active_onemin_accounts"], ["acct-ea-core"])

    def test_onemin_codexer_runtime_payload_tracks_booster_lane_from_runtime_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE accounts (alias TEXT PRIMARY KEY, auth_kind TEXT NOT NULL)")
            conn.execute(
                "CREATE TABLE runtime_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, package_id TEXT, task_kind TEXT, task_state TEXT, payload_json TEXT)"
            )
            conn.execute("INSERT INTO accounts(alias, auth_kind) VALUES('acct-ea-core', 'ea')")
            conn.execute(
                "INSERT INTO runtime_tasks(project_id, package_id, task_kind, task_state, payload_json) VALUES(?, ?, 'coding', 'running', ?)",
                (
                    "fleet",
                    "fleet-a",
                    json.dumps(
                        {
                            "account_alias": "acct-ea-core",
                            "selected_model": "ea-coder-hard-batch",
                            "decision": {
                                "lane": "core",
                                "quartermaster": {"target_lane": "core_booster"},
                            },
                        }
                    ),
                ),
            )
            conn.commit()
            conn.close()

            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)
            self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {
                "profiles": [
                    {"model": "ea-coder-hard-batch", "provider_hint_order": ["onemin"]},
                ]
            }

            payload = self.admin.onemin_codexer_runtime_payload()

            self.assertEqual(payload["active_onemin_codexers"], 1)
            self.assertEqual(payload["active_onemin_booster_codexers"], 1)
            self.assertEqual(payload["active_onemin_lane_usage"], {"core_booster": 1})

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

    def test_capacity_forecast_includes_group_and_account_pressure(self) -> None:
        payload = self.admin.capacity_forecast_payload(
            {"config": {"lanes": {"core": {}}}, "projects": [], "groups": []},
            lane_capacities={"core": {"state": "ready", "providers": []}},
            runway={
                "groups": [
                    {
                        "group_id": "hub",
                        "runway_risk": "tight",
                        "pool_level": "tight",
                        "finish_outlook": "likely to finish if pressure stays flat",
                        "eligible_parallel_slots": 2,
                        "remaining_slices": 5,
                        "slot_share_percent": 50,
                        "drain_share_percent": 60,
                        "bottleneck": "review queue",
                        "deployment_summary": "chummer.run",
                        "design_eta": {"eta_human": "9d", "confidence": "medium"},
                        "design_progress": {"eta_confidence": "medium"},
                    }
                ],
                "accounts": [
                    {
                        "alias": "acct-core-a",
                        "bridge_name": "Core Lane",
                        "auth_kind": "chatgpt_auth_json",
                        "pressure_state": "yellow",
                        "standard_pool_state": "ready",
                        "spark_pool_state": "cooldown",
                        "api_budget_health": "yellow",
                        "active_runs": 2,
                        "burn_rate": "$2.000/day",
                        "projected_exhaustion": "14h",
                        "top_consumers": ["hub $1.2", "ui $0.8"],
                    }
                ],
            },
        )

        self.assertEqual(payload["group_pressure"][0]["group_id"], "hub")
        self.assertEqual(payload["group_pressure"][0]["slot_share_percent"], 50)
        self.assertEqual(payload["account_pressure"][0]["alias"], "acct-core-a")
        self.assertEqual(payload["account_pressure"][0]["projected_exhaustion"], "14h")

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

    def test_group_cards_payload_includes_pool_sufficiency_and_finish_outlook(self) -> None:
        payload = self.admin.group_cards_payload(
            {
                "config": {"policies": {"max_parallel_runs": 4}},
                "groups": [
                    {
                        "id": "hub",
                        "status": "running",
                        "phase": "delivery",
                        "dispatch_ready": True,
                        "dispatch_basis": "keep account shell moving",
                        "bottleneck": "review queue",
                        "compile_attention_count": 0,
                        "review_waiting_count": 1,
                        "review_blocking_count": 2,
                        "pressure_state": "tight",
                        "pool_sufficiency": {
                            "level": "tight",
                            "remaining_slices": 5,
                            "eligible_parallel_slots": 2,
                            "basis": "eligible pool sufficiency is tight",
                        },
                        "allowance_usage": {"estimated_cost_usd": 3.0},
                        "deployment": {"display": "chummer.run"},
                        "design_progress": {"summary": "account shell and participation need closure"},
                        "design_eta": {"eta_human": "9d"},
                        "milestone_eta": {"eta_human": "3d"},
                        "program_eta": {"eta_human": "9d"},
                        "dispatch_blockers": ["review lane busy"],
                        "contract_blockers": [],
                        "projects": ["hub-api"],
                    }
                ],
                "projects": [
                    {
                        "id": "hub-api",
                        "group_ids": ["hub"],
                        "runtime_status": "running",
                        "current_slice": "finish auth shell",
                    }
                ],
            }
        )

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["pool_level"], "tight")
        self.assertEqual(payload[0]["eligible_parallel_slots"], 2)
        self.assertEqual(payload[0]["slot_share_percent"], 50)
        self.assertEqual(payload[0]["drain_share_percent"], 100)
        self.assertTrue(payload[0]["finish_outlook"])

    def test_ea_lane_capacity_snapshot_keeps_repair_profile_distinct_from_easy(self) -> None:
        self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {
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
        self.admin.ea_codex_profiles = lambda force=False, cache_only=False: {
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

    def test_provider_route_summary_payload_uses_configured_fallbacks_and_separates_merge_review(self) -> None:
        with mock.patch.object(
            self.admin,
            "ea_lane_capacity_snapshot",
            return_value={
                "review_light": {
                    "primary_provider_key": "browseract",
                    "provider_hint_order": ["browseract"],
                    "state": "ready",
                    "review_required": False,
                    "merge_policy": "auto_if_low_risk",
                    "provider_registry_contract": "ea.provider_registry",
                },
                "core": {
                    "primary_provider_key": "onemin",
                    "provider_hint_order": ["onemin"],
                    "state": "ready",
                    "review_required": True,
                    "merge_policy": "require_review",
                    "provider_registry_contract": "ea.provider_registry",
                },
            },
        ):
            payload = self.admin.provider_route_summary_payload(
                {
                    "config": {
                        "lanes": {
                            "review_light": {
                                "label": "EA Review Light",
                                "provider_hint_order": ["gemini_vortex", "chatplayground"],
                            },
                            "core": {
                                "label": "EA Core",
                                "provider_hint_order": ["onemin"],
                            },
                        }
                    },
                    "capacity_forecast": {"lanes": []},
                }
            )

        by_lane = {item["lane"]: item for item in payload}
        self.assertEqual(by_lane["review_light"]["default_route"], "browseract")
        self.assertEqual(by_lane["review_light"]["fallback_route"], "gemini_vortex")
        self.assertEqual(by_lane["review_light"]["challenger_route"], "chatplayground")
        self.assertEqual(by_lane["review_light"]["posture"], "safe_today")
        self.assertFalse(by_lane["core"]["review_required"])
        self.assertTrue(by_lane["core"]["merge_review_required"])
        self.assertEqual(by_lane["core"]["posture"], "fallback_thin")

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
                    "trace_id": "controller-coding-20260419t010000z-abc123def456",
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
        self.assertEqual(active["trace_id"], "controller-coding-20260419t010000z-abc123def456")

    def test_build_worker_posture_payload_keeps_trace_ids_for_recent_runs(self) -> None:
        payload = self.admin.build_worker_posture_payload(
            {
                "config": {"accounts": {}},
                "projects": [
                    {
                        "id": "fleet",
                        "current_slice": "Refresh operator runway",
                        "selected_lane": "core",
                        "selected_profile": "core",
                        "selected_lane_capacity_state": "ready",
                        "selected_lane_capacity": {
                            "lane": "core",
                            "profile": "core",
                            "backend": "chatplayground",
                            "primary_provider_key": "browseract",
                            "capacity_summary": {"configured_slots": 2, "ready_slots": 1, "slot_owners": ["core"]},
                            "providers": [{"provider_key": "browseract", "backend": "chatplayground"}],
                        },
                    }
                ],
                "recent_runs": [
                    {
                        "id": 42,
                        "trace_id": "controller-coding-20260419t010500z-fedcba654321",
                        "project_id": "fleet",
                        "account_alias": "acct-core-a",
                        "model": "gpt-5.4",
                        "status": "complete",
                        "slice_name": "Refresh operator runway",
                        "started_at": "2026-04-19T01:05:00Z",
                        "finished_at": "2026-04-19T01:09:00Z",
                        "log_path": "",
                        "final_message_path": "",
                    }
                ],
            },
            workers=[],
        )

        recent = payload["recent"][0]
        self.assertEqual(recent["run_id"], "42")
        self.assertEqual(recent["trace_id"], "controller-coding-20260419t010500z-fedcba654321")

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
        recent_fleet_review = self.admin.iso(self.admin.utc_now() - dt.timedelta(hours=2))
        recent_ui_review = self.admin.iso(self.admin.utc_now() - dt.timedelta(hours=1))

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
            {
                "project_id": "fleet",
                "hub_user_id": "usr_1",
                "subject_id": "subject-1",
                "lane_role": "review",
                "telemetry": {"auth_ready": True, "receipts": {"last_status": "sent:slice_reviewed"}},
                "auth_completed_at": "2026-03-19T08:10:00Z",
                "consented_at": "2026-03-19T08:00:00Z",
            },
            {
                "project_id": "fleet",
                "hub_user_id": "usr_1",
                "subject_id": "subject-1",
                "lane_role": "coding",
                "telemetry": {"auth_ready": True, "receipts": {"last_status": "failed:slice_landed"}},
                "auth_completed_at": "2026-03-19T08:11:00Z",
                "reward_receipt_error": "timeout",
            },
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
                        "pull_request": {"review_requested_at": recent_fleet_review},
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
                        "pull_request": {"review_requested_at": recent_ui_review},
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
        self.assertEqual(payload["participant_burst"]["consented_lanes"], 1)
        self.assertEqual(payload["participant_burst"]["missing_consent_trace_lanes"], 1)
        self.assertEqual(payload["participant_burst"]["receipt_status_counts"]["sent:slice_reviewed"], 1)
        self.assertEqual(payload["participant_burst"]["receipt_status_counts"]["failed:slice_landed"], 1)
        self.assertEqual(payload["participant_burst"]["receipt_failure_count"], 1)
        self.assertEqual(payload["participant_burst"]["premium_queue_depth"], 1)
        self.assertIn("fleet", payload["participant_burst"]["surge_mode_projects"])

    def test_mission_board_payload_includes_jury_telemetry(self) -> None:
        self.admin.load_latest_telemetry_payload = lambda _status: {"summary": {}, "review_loop": {}, "worker_utilization": {}}
        self.admin.jury_telemetry_payload = lambda status, lane_capacities, cache_only=False: {
            "active_jury_jobs": 1,
            "queued_jury_jobs": 2,
            "blocked_total_workers": 3,
        }
        self.admin.ea_onemin_manager_billing_aggregate = lambda force=False, cache_only=False: {}

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
        self.admin.ea_onemin_manager_billing_aggregate = lambda force=False, cache_only=False: {
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
            "last_actual_balance_check_at": "2026-03-18T09:00:00Z",
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

    def test_mission_board_payload_includes_booster_runtime_card(self) -> None:
        self.admin.jury_telemetry_payload = lambda status, lane_capacities, cache_only=False: {
            "participant_burst": {
                "active_lanes": 2,
                "sponsor_ready_lanes": 2,
                "effective_capacity_by_project": {"core": 3},
            }
        }
        self.admin.onemin_codexer_runtime_payload = lambda cache_only=False: {
            "active_onemin_codexers": 2,
            "active_onemin_booster_codexers": 0,
            "active_onemin_projects": ["core", "ui"],
            "active_onemin_accounts": ["acct-ea-core", "acct-ea-fleet"],
            "active_onemin_lane_usage": {"core_authority": 2},
        }
        self.admin.ea_onemin_manager_billing_aggregate = lambda force=False, cache_only=False: {
            "sum_free_credits": 800_000,
            "sum_max_credits": 2_000_000,
            "remaining_percent_total": 40.0,
            "next_topup_at": "2026-03-31T00:00:00Z",
            "topup_amount": 2_000_000,
            "hours_until_next_topup": 320.5,
            "hours_remaining_at_current_pace_no_topup": 40.0,
            "hours_remaining_including_next_topup_at_current_pace": 420.0,
            "days_remaining_including_next_topup_at_7d_avg": 140.0,
            "depletes_before_next_topup": False,
            "basis_summary": "actual_billing_usage_page x2",
            "basis_counts": {"actual_billing_usage_page": 2},
            "slot_count_with_billing_snapshot": 2,
            "slot_count_with_member_reconciliation": 2,
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

        booster = payload["booster_runtime_card"]
        self.assertEqual(booster["active_boosters"], 2)
        self.assertEqual(booster["active_managed_boosters"], 0)
        self.assertEqual(booster["sponsor_ready_boosters"], 2)
        self.assertEqual(booster["hourly_burn_rate_credits"], 20000.0)
        self.assertEqual(booster["per_booster_hourly_burn_rate_credits"], 10000.0)
        self.assertEqual(booster["active_onemin_codexers"], 2)
        self.assertEqual(booster["active_onemin_projects"], ["core", "ui"])
        self.assertEqual(booster["per_onemin_codexer_hourly_burn_rate_credits"], 10000.0)
        self.assertEqual(booster["managed_vs_participant"]["participant_direct_burst"], 2)
        self.assertEqual(booster["managed_vs_participant"]["managed_core_burst"], 0)
        self.assertEqual(booster["participant_share_percent"], 100.0)
        self.assertEqual(booster["managed_share_percent"], 0.0)
        self.assertEqual(booster["credits_left_percent"], 40.0)
        self.assertEqual(booster["hours_remaining_with_topup"], 420.0)
        self.assertEqual(booster["effective_capacity_by_project"]["core"], 3)

    def test_mission_board_payload_threads_cache_only_to_provider_surfaces(self) -> None:
        seen: dict[str, list[bool]] = {"execution": [], "provider": [], "booster": []}

        def fake_execution_loop_payload(
            status,
            *,
            queue_forecast,
            blocker_forecast,
            lane_capacities=None,
            cache_only=False,
        ):
            seen["execution"].append(cache_only)
            return {
                "title": "Idle",
                "current_lane": "idle",
                "provider": "none",
                "brain": "none",
                "current_stage_label": "Idle",
                "jury_telemetry": {},
            }

        def fake_provider_credit_card_payload(*, cache_only=False):
            seen["provider"].append(cache_only)
            return {}

        def fake_booster_runtime_card_payload(jury_telemetry, provider_credit, *, cache_only=False):
            seen["booster"].append(cache_only)
            return {}

        self.admin.execution_loop_payload = fake_execution_loop_payload
        self.admin.provider_credit_card_payload = fake_provider_credit_card_payload
        self.admin.booster_runtime_card_payload = fake_booster_runtime_card_payload
        self.admin.truth_freshness_payload = lambda status: {}
        self.admin.group_cards_payload = lambda status: []
        self.admin.build_review_gate_bridge_items = lambda status: []
        self.admin.build_healer_activity_items = lambda status: []

        self.admin.mission_board_payload(
            {"projects": [], "groups": [], "config": {"spider": {}}, "account_pools": []},
            mission_snapshot={},
            queue_forecast={"now": {}, "next": {}},
            vision_forecast={},
            capacity_forecast={"lanes": [], "critical_path_lane": "groundwork", "mission_runway": "forever", "pool_runway": "7d"},
            blocker_forecast={"now": "none", "next": "none", "vision": "none"},
            attention=[],
            lane_capacities={},
            cache_only=True,
        )

        self.assertEqual(seen["execution"], [True])
        self.assertEqual(seen["provider"], [True])
        self.assertEqual(seen["booster"], [True])

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
        self.admin.compile_manifest_surface_payload = lambda: {
            "published_at": "2026-03-18T12:15:00Z",
            "dispatchable_truth_ready": True,
            "stage_total": 5,
            "stage_green_count": 5,
            "stages": {
                "design_compile": True,
                "policy_compile": True,
                "execution_compile": True,
                "package_compile": True,
                "capacity_compile": True,
            },
            "freshness": {"state": "fresh", "age_human": "15m"},
        }
        self.admin.support_case_surface_payload = lambda: {
            "generated_at": "2026-03-18T12:20:00Z",
            "summary": {
                "open_case_count": 2,
                "closure_waiting_on_release_truth": 1,
                "needs_human_response": 1,
                "top_clusters": [{"kind": "bug_report", "target_repo": "chummer6-ui", "count": 2}],
            },
            "freshness": {"state": "fresh", "age_human": "10m"},
        }
        self.admin.journey_gates_surface_payload = lambda: {
            "generated_at": "2026-03-18T12:18:00Z",
            "summary": {
                "overall_state": "ready",
                "total_journey_count": 6,
                "ready_count": 6,
                "warning_count": 0,
                "blocked_count": 0,
            },
            "journeys": [],
            "freshness": {"state": "fresh", "age_human": "12m"},
        }
        self.admin.published_artifact_freshness_payload = lambda: {
            "compile_manifest": {"state": "fresh", "age_human": "15m"},
            "journey_gates": {"state": "fresh", "age_human": "12m"},
            "progress_report": {"state": "fresh", "age_human": "1d"},
            "progress_history": {"state": "fresh", "age_human": "1d"},
            "status_plane": {"state": "fresh", "age_human": "20m"},
            "support_packets": {"state": "fresh", "age_human": "10m"},
        }
        self.admin.load_published_yaml_payload = lambda _filename: {
            "contract_name": "fleet.status_plane",
            "generated_at": "2026-03-18T12:05:00Z",
        }
        self.admin.admin_status_payload = lambda public_mode=False: {
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
        self.assertEqual(payload["deployment_posture"]["dashboard_path"], "/")
        self.assertEqual(payload["deployment_posture"]["mission_bridge_path"], "/")
        self.assertEqual(payload["deployment_posture"]["ops_path"], "/ops/")
        self.assertEqual(payload["deployment_posture"]["command_deck_path"], "/admin")
        self.assertEqual(payload["deployment_posture"]["public_target_count"], 2)
        self.assertIn("readiness_summary", payload)
        self.assertIn("compile_manifest", payload)
        self.assertTrue(payload["compile_manifest"]["dispatchable_truth_ready"])
        self.assertEqual(payload["support_summary"]["closure_waiting_on_release_truth"], 1)
        self.assertIn("journey_gates", payload)
        self.assertEqual(payload["journey_gates"]["summary"]["warning_count"], 0)
        self.assertEqual(payload["artifact_freshness"]["status_plane"]["state"], "fresh")
        self.assertEqual(payload["status_plane"]["contract_name"], "fleet.status_plane")
        self.assertNotIn("config", payload)
        self.assertNotIn("accounts", payload)

    def test_public_dashboard_status_payload_requests_public_mode(self) -> None:
        requested: list[bool] = []
        self.admin.admin_status_payload = lambda public_mode=False: requested.append(public_mode) or {
            "public_status": {"contract_name": "fleet.public_status"}
        }

        payload = self.admin.public_dashboard_status_payload()

        self.assertEqual(requested, [True])
        self.assertEqual(payload["contract_name"], "fleet.public_status")

    def test_admin_status_public_mode_skips_runtime_healing_incident_sync(self) -> None:
        self.admin.normalize_config = lambda: {
            "schema_version": "test",
            "policies": {},
            "spider": {},
            "account_policy": {},
            "projects": [],
            "groups": [],
            "accounts": {},
            "lanes": {},
            "project_groups": [],
        }
        self.admin.config_consistency_warnings = lambda _config: []
        self.admin.merged_projects = lambda cache_only=False: []
        self.admin.runtime_healing_payload = lambda: {"summary": {}, "services": []}
        self.admin.sync_runtime_healing_incidents = lambda _payload: (_ for _ in ()).throw(
            AssertionError("public mode should not sync incidents")
        )
        self.admin.load_program_registry = lambda _config: {}
        self.admin.group_runtime_rows = lambda: {}
        self.admin.work_package_summary_payload = lambda _config: {}
        self.admin.recent_auditor_run = lambda: {}
        self.admin.studio_publish_events = lambda: []
        self.admin.group_publish_events = lambda: []
        self.admin.group_runs = lambda: []
        self.admin.load_design_mirror_status = lambda: {}
        self.admin.recent_runs = lambda: []
        self.admin.participant_lane_rows_for_admin = lambda statuses=None: []
        self.admin.cockpit_payload_from_status = lambda status, cache_only=False: {"summary": {}}
        self.admin.canonical_public_status_payload = lambda status, cache_only=False: {}

        payload = self.admin.admin_status_payload(public_mode=True)

        self.assertEqual(payload["public_status"], {})

    def test_published_artifact_freshness_prefers_progress_generated_at(self) -> None:
        fixed_now = self.admin.dt.datetime(2026, 3, 26, 12, 0, tzinfo=self.admin.UTC)
        self.admin.compile_manifest_surface_payload = lambda: {"freshness": {"state": "fresh", "label": "fresh", "age_human": "10m"}}
        self.admin.support_case_surface_payload = lambda: {"freshness": {"state": "fresh", "label": "fresh", "age_human": "10m"}}
        self.admin.journey_gates_surface_payload = lambda: {"freshness": {"state": "fresh", "label": "fresh", "age_human": "12m"}}
        self.admin.load_published_json_payload = lambda filename: (
            {"generated_at": "2026-03-26T11:45:00Z", "as_of": "2026-03-23"}
            if filename == self.admin.PROGRESS_REPORT_FILENAME
            else {"generated_at": "2026-03-26T11:40:00Z"}
        )
        self.admin.load_published_yaml_payload = lambda _filename: {"generated_at": "2026-03-26T11:50:00Z"}

        with mock.patch.object(self.admin, "_progress_artifact_source_paths", return_value=[]):
            with mock.patch.object(self.admin, "_status_plane_source_paths", return_value=[]):
                with mock.patch.object(self.admin, "utc_now", return_value=fixed_now):
                    payload = self.admin.published_artifact_freshness_payload()

        self.assertEqual(payload["progress_report"]["state"], "fresh")
        self.assertEqual(payload["progress_report"]["at"], "2026-03-26T11:45:00Z")
        self.assertEqual(payload["weekly_governor_packet"]["state"], "fresh")
        self.assertEqual(payload["weekly_governor_packet"]["at"], "2026-03-26T11:40:00Z")

    def test_published_artifact_freshness_marks_source_drift_as_stale(self) -> None:
        fixed_now = self.admin.dt.datetime(2026, 3, 26, 12, 0, tzinfo=self.admin.UTC)
        progress_source_at = self.admin.dt.datetime(2026, 3, 26, 11, 59, 30, tzinfo=self.admin.UTC)
        status_source_at = self.admin.dt.datetime(2026, 3, 26, 11, 58, 0, tzinfo=self.admin.UTC)
        self.admin.compile_manifest_surface_payload = lambda: {"freshness": {"state": "fresh", "label": "fresh", "age_human": "10m"}}
        self.admin.support_case_surface_payload = lambda: {"freshness": {"state": "fresh", "label": "fresh", "age_human": "10m"}}
        self.admin.journey_gates_surface_payload = lambda: {"freshness": {"state": "fresh", "label": "fresh", "age_human": "12m"}}
        self.admin.release_channel_surface_payload = lambda: {"freshness": {"state": "fresh", "label": "fresh", "age_human": "5m"}}
        self.admin.load_published_json_payload = lambda filename: (
            {"generated_at": "2026-03-26T11:45:00Z", "as_of": "2026-03-23"}
            if filename == self.admin.PROGRESS_REPORT_FILENAME
            else {"generated_at": "2026-03-26T11:40:00Z"}
        )
        self.admin.load_published_yaml_payload = lambda _filename: {"generated_at": "2026-03-26T11:50:00Z"}

        def fake_latest_path_mtime(paths):
            first = str((list(paths) or [Path("missing")])[0])
            return progress_source_at if "progress-source" in first else status_source_at

        with mock.patch.object(self.admin, "_progress_artifact_source_paths", return_value=[Path("/tmp/progress-source")]):
            with mock.patch.object(self.admin, "_status_plane_source_paths", return_value=[Path("/tmp/status-source")]):
                with mock.patch.object(self.admin, "_latest_path_mtime", side_effect=fake_latest_path_mtime):
                    with mock.patch.object(self.admin, "utc_now", return_value=fixed_now):
                        payload = self.admin.published_artifact_freshness_payload()

        self.assertEqual(payload["progress_report"]["state"], "stale")
        self.assertEqual(payload["progress_history"]["state"], "stale")
        self.assertEqual(payload["status_plane"]["state"], "stale")
        self.assertEqual(payload["weekly_governor_packet"]["state"], "fresh")
        self.assertEqual(payload["progress_report"]["source_updated_at"], "2026-03-26T11:59:30Z")
        self.assertEqual(payload["status_plane"]["source_updated_at"], "2026-03-26T11:58:00Z")
        self.assertIn("published progress report", payload["progress_report"]["reason"])
        self.assertIn("published status plane", payload["status_plane"]["reason"])

    def test_release_channel_surface_prefers_runtime_registry_truth(self) -> None:
        runtime_payload = {
            "version": "6.1.0-preview.4",
            "channel": "preview",
            "publishedAt": "2026-03-28T14:00:00Z",
            "status": "published",
            "rolloutState": "promoted_preview",
            "artifacts": [{"id": "windows-installer"}],
            "releaseProof": {"status": "passed", "generatedAt": "2026-03-28T13:55:00Z"},
        }
        file_payload = {
            "version": "6.1.0-preview.3",
            "channel": "preview",
            "publishedAt": "2026-03-27T14:00:00Z",
            "status": "published",
            "artifacts": [],
            "releaseProof": {"status": "missing", "generatedAt": "2026-03-27T13:55:00Z"},
        }

        with mock.patch.object(self.admin, "release_channel_runtime_url", return_value="http://registry/current"):
            with mock.patch.object(self.admin, "load_json_url_payload", return_value=runtime_payload):
                with mock.patch.object(self.admin, "load_json_payload", return_value=file_payload):
                    payload = self.admin.release_channel_surface_payload()

        self.assertEqual(payload["truth_source"], "registry_runtime")
        self.assertEqual(payload["version"], "6.1.0-preview.4")
        self.assertEqual(payload["artifact_count"], 1)
        self.assertEqual(payload["release_proof"]["status"], "passed")

    def test_release_channel_surface_falls_back_to_file_truth(self) -> None:
        file_payload = {
            "version": "6.1.0-preview.3",
            "channel": "preview",
            "publishedAt": "2026-03-27T14:00:00Z",
            "status": "published",
            "rolloutState": "promoted_preview",
            "artifacts": [{"id": "linux-deb"}],
            "releaseProof": {"status": "passed", "generatedAt": "2026-03-27T13:55:00Z"},
        }

        with mock.patch.object(self.admin, "release_channel_runtime_url", return_value="http://registry/current"):
            with mock.patch.object(self.admin, "load_json_url_payload", return_value={}):
                with mock.patch.object(self.admin, "load_json_payload", return_value=file_payload):
                    payload = self.admin.release_channel_surface_payload()

        self.assertEqual(payload["truth_source"], "registry_file")
        self.assertEqual(payload["version"], "6.1.0-preview.3")
        self.assertEqual(payload["artifact_count"], 1)

    def test_release_channel_surface_accepts_registry_utc_timestamp_fields(self) -> None:
        runtime_payload = {
            "version": "smoke-2026.03.24-linux-x64",
            "channelId": "docker",
            "publishedAtUtc": "2026-03-24T19:03:57+00:00",
            "status": "published",
            "artifacts": [{"artifactId": "avalonia-linux-x64-archive"}],
            "releaseProof": {"status": "passed", "generatedAtUtc": "2026-03-28T16:31:31+00:00"},
        }

        with mock.patch.object(self.admin, "release_channel_runtime_url", return_value="http://registry/current"):
            with mock.patch.object(self.admin, "load_json_url_payload", return_value=runtime_payload):
                with mock.patch.object(
                    self.admin,
                    "utc_now",
                    return_value=self.admin.dt.datetime(2026, 3, 28, 17, 0, tzinfo=self.admin.UTC),
                ):
                    payload = self.admin.release_channel_surface_payload()

        self.assertEqual(payload["truth_source"], "registry_runtime")
        self.assertEqual(payload["freshness"]["state"], "fresh")
        self.assertEqual(payload["proof_freshness"]["state"], "fresh")

    def test_support_case_surface_marks_unconfigured_source_instead_of_generic_stale(self) -> None:
        fixed_now = self.admin.dt.datetime(2026, 3, 26, 12, 0, tzinfo=self.admin.UTC)
        self.admin.load_published_json_payload = lambda _filename: {
            "generated_at": "2026-03-24T10:00:00Z",
            "summary": {},
            "packets": [],
        }

        with mock.patch.object(self.admin, "support_case_source_configured", return_value=False):
            with mock.patch.object(self.admin, "utc_now", return_value=fixed_now):
                payload = self.admin.support_case_surface_payload()

        self.assertFalse(payload["source_configured"])
        self.assertEqual(payload["freshness"]["state"], "source_unconfigured")
        self.assertIn("automatic packet refresh", payload["freshness"]["reason"])

    def test_refresh_published_artifacts_runs_materializers_for_stale_surfaces(self) -> None:
        stale = {
            "compile_manifest": {"state": "stale"},
            "journey_gates": {"state": "stale"},
            "support_packets": {"state": "stale"},
            "progress_report": {"state": "stale"},
            "progress_history": {"state": "stale"},
            "status_plane": {"state": "stale"},
        }
        fresh = {
            "compile_manifest": {"state": "fresh"},
            "journey_gates": {"state": "fresh"},
            "support_packets": {"state": "fresh"},
            "progress_report": {"state": "fresh"},
            "progress_history": {"state": "fresh"},
            "status_plane": {"state": "fresh"},
        }
        with mock.patch.object(self.admin, "published_artifact_freshness_payload", side_effect=[stale, fresh]):
            with mock.patch.object(self.admin, "support_case_source", return_value="/tmp/support-cases.json"):
                with mock.patch.object(self.admin, "_write_status_snapshot", return_value=Path("/tmp/fleet-status.json")):
                    with mock.patch.object(
                        self.admin,
                        "_run_repo_python_script",
                        return_value={"ok": True, "stdout": "ok", "stderr": "", "returncode": 0},
                    ) as runner:
                        with mock.patch.object(self.admin, "save_runtime_cache"):
                            payload = self.admin.refresh_published_artifacts(force=False, status_payload={"generated_at": "2026-03-26T12:00:00Z"})

        self.assertEqual(payload["status"], "refreshed")
        self.assertEqual(
            [call.args[0] for call in runner.call_args_list],
            [
                "materialize_status_plane.py",
                "materialize_public_progress_report.py",
                "materialize_support_case_packets.py",
                "materialize_journey_gates.py",
                "materialize_weekly_governor_packet.py",
            ],
        )

    def test_publish_readiness_blocks_when_weekly_governor_packet_is_stale(self) -> None:
        status = {
            "runtime_healing": {"summary": {"alert_state": "healthy"}},
        }
        artifact_freshness = {
            "status_plane": {"state": "fresh"},
            "progress_report": {"state": "fresh"},
            "journey_gates": {"state": "fresh"},
            "release_channel": {"state": "fresh"},
            "weekly_governor_packet": {
                "state": "stale",
                "reason": "Weekly governor packet is older than the measured rollout window.",
            },
        }
        support_surface = {"summary": {}, "freshness": {"state": "fresh"}}
        journey_gates = {"summary": {"overall_state": "ready"}}
        release_channel = {
            "status": "published",
            "rolloutState": "promoted_preview",
            "supportabilityState": "supported",
            "release_proof": {"status": "passed"},
            "proof_freshness": {"state": "fresh"},
        }

        payload = self.admin.publish_readiness_payload(
            status,
            artifact_freshness=artifact_freshness,
            support_surface=support_surface,
            journey_gates=journey_gates,
            release_channel=release_channel,
            provider_routes=[],
        )

        self.assertEqual(payload["state"], "blocked")
        self.assertIn(
            "Weekly governor packet is older than the measured rollout window.",
            payload["blocking_reasons"],
        )
        self.assertEqual(payload["signals"]["weekly_governor_packet_freshness_state"], "stale")

    def test_publish_readiness_blocks_when_weekly_governor_packet_is_past_due(self) -> None:
        status = {
            "runtime_healing": {"summary": {"alert_state": "healthy"}},
        }
        artifact_freshness = {
            "status_plane": {"state": "fresh"},
            "progress_report": {"state": "fresh"},
            "journey_gates": {"state": "fresh"},
            "release_channel": {"state": "fresh"},
            "weekly_governor_packet": {"state": "fresh"},
        }
        support_surface = {"summary": {}, "freshness": {"state": "fresh"}}
        journey_gates = {"summary": {"overall_state": "ready"}}
        release_channel = {
            "status": "published",
            "rolloutState": "promoted_preview",
            "supportabilityState": "supported",
            "release_proof": {"status": "passed"},
            "proof_freshness": {"state": "fresh"},
        }
        generated_at = "2026-03-01T00:00:00Z"
        weekly_governor_packet = {
            "generated_at": generated_at,
            "status": "ready",
            "decision_board": {
                "current_launch_action": "launch_expand",
                "current_launch_reason": "All measured launch gates are green.",
            },
            "public_status_copy": {
                "state": "launch_expand_allowed",
                "body": "All measured launch gates are green.",
            },
            "governor_packet_schedule": {
                "cadence": "weekly",
                "generated_at": generated_at,
                "next_packet_due_at": "2026-03-08T00:00:00Z",
                "cadence_seconds": 604800,
                "max_age_seconds": 604800,
                "status": "scheduled",
            },
            "measured_rollout_loop": {
                "rollback_watch": False,
            },
        }

        with mock.patch.object(self.admin, "utc_now", return_value=self.admin.parse_iso("2026-03-08T01:00:00Z")):
            payload = self.admin.publish_readiness_payload(
                status,
                artifact_freshness=artifact_freshness,
                support_surface=support_surface,
                journey_gates=journey_gates,
                release_channel=release_channel,
                weekly_governor_packet=weekly_governor_packet,
                provider_routes=[],
            )

        self.assertEqual(payload["state"], "blocked")
        self.assertIn(
            "Weekly governor packet is past due for its weekly cadence.",
            payload["blocking_reasons"],
        )
        self.assertEqual(payload["signals"]["weekly_governor_packet_freshness_state"], "stale")
        self.assertEqual(payload["signals"]["weekly_governor_packet_schedule_state"], "overdue")

    def test_publish_readiness_blocks_when_weekly_governor_packet_source_truth_is_newer(self) -> None:
        status = {
            "runtime_healing": {"summary": {"alert_state": "healthy"}},
        }
        artifact_freshness = {
            "status_plane": {"state": "fresh"},
            "progress_report": {"state": "fresh"},
            "journey_gates": {"state": "fresh"},
            "release_channel": {"state": "fresh"},
            "weekly_governor_packet": {"state": "fresh"},
        }
        support_surface = {"summary": {}, "freshness": {"state": "fresh"}}
        journey_gates = {"summary": {"overall_state": "ready"}}
        release_channel = {
            "status": "published",
            "rolloutState": "promoted_preview",
            "supportabilityState": "supported",
            "release_proof": {"status": "passed"},
            "proof_freshness": {"state": "fresh"},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "WEEKLY_PRODUCT_PULSE.generated.json"
            source_path.write_text("{}", encoding="utf-8")
            newer_timestamp = dt.datetime(2026, 3, 8, 0, 20, tzinfo=dt.timezone.utc).timestamp()
            os.utime(source_path, (newer_timestamp, newer_timestamp))
            weekly_governor_packet = {
                "generated_at": "2026-03-08T00:00:00Z",
                "status": "ready",
                "decision_board": {
                    "current_launch_action": "launch_expand",
                    "current_launch_reason": "All measured launch gates are green.",
                },
                "public_status_copy": {
                    "state": "launch_expand_allowed",
                    "body": "All measured launch gates are green.",
                },
                "governor_packet_schedule": {
                    "cadence": "weekly",
                    "generated_at": "2026-03-08T00:00:00Z",
                    "next_packet_due_at": "2026-03-15T00:00:00Z",
                    "cadence_seconds": 604800,
                    "max_age_seconds": 604800,
                    "status": "scheduled",
                },
                "measured_rollout_loop": {
                    "rollback_watch": False,
                },
                "source_paths": {
                    "weekly_pulse": str(source_path),
                },
            }

            with mock.patch.object(
                self.admin,
                "utc_now",
                return_value=self.admin.parse_iso("2026-03-08T00:00:00Z"),
            ):
                payload = self.admin.publish_readiness_payload(
                    status,
                    artifact_freshness=artifact_freshness,
                    support_surface=support_surface,
                    journey_gates=journey_gates,
                    release_channel=release_channel,
                    weekly_governor_packet=weekly_governor_packet,
                    provider_routes=[],
                )

        self.assertEqual(payload["state"], "blocked")
        self.assertEqual(payload["signals"]["weekly_governor_packet_freshness_state"], "stale")
        self.assertIn(
            "newer than the published weekly governor packet",
            " ".join(payload["blocking_reasons"]),
        )

    def test_publish_readiness_blocks_when_weekly_governor_packet_freezes_launch(self) -> None:
        status = {
            "runtime_healing": {"summary": {"alert_state": "healthy"}},
        }
        artifact_freshness = {
            "status_plane": {"state": "fresh"},
            "progress_report": {"state": "fresh"},
            "journey_gates": {"state": "fresh"},
            "release_channel": {"state": "fresh"},
            "weekly_governor_packet": {"state": "fresh"},
        }
        support_surface = {"summary": {}, "freshness": {"state": "fresh"}}
        journey_gates = {"summary": {"overall_state": "ready"}}
        release_channel = {
            "status": "published",
            "rolloutState": "promoted_preview",
            "supportabilityState": "supported",
            "release_proof": {"status": "passed"},
            "proof_freshness": {"state": "fresh"},
        }
        weekly_governor_packet = {
            "status": "blocked",
            "status_reason": "Fleet package is closed; measured rollout remains blocked.",
            "decision_board": {
                "current_launch_action": "freeze_launch",
                "current_launch_reason": "Freeze launch expansion until fresh local release proof passes on the public edge.",
            },
            "public_status_copy": {
                "state": "freeze_launch",
                "body": "Freeze launch expansion until fresh local release proof passes on the public edge.",
            },
            "measured_rollout_loop": {
                "rollback_watch": False,
            },
        }

        payload = self.admin.publish_readiness_payload(
            status,
            artifact_freshness=artifact_freshness,
            support_surface=support_surface,
            journey_gates=journey_gates,
            release_channel=release_channel,
            weekly_governor_packet=weekly_governor_packet,
            provider_routes=[],
        )

        self.assertEqual(payload["state"], "blocked")
        self.assertIn(
            "Freeze launch expansion until fresh local release proof passes on the public edge.",
            payload["blocking_reasons"],
        )
        self.assertEqual(payload["signals"]["weekly_governor_packet_status"], "blocked")
        self.assertEqual(payload["signals"]["weekly_governor_launch_action"], "freeze_launch")
        self.assertEqual(payload["signals"]["weekly_governor_public_state"], "freeze_launch")

    def test_publish_readiness_prefers_public_freeze_reason_when_launch_expand_claim_is_stale(self) -> None:
        status = {
            "runtime_healing": {"summary": {"alert_state": "healthy"}},
        }
        artifact_freshness = {
            "status_plane": {"state": "fresh"},
            "progress_report": {"state": "fresh"},
            "journey_gates": {"state": "fresh"},
            "release_channel": {"state": "fresh"},
            "weekly_governor_packet": {"state": "fresh"},
        }
        support_surface = {"summary": {}, "freshness": {"state": "fresh"}}
        journey_gates = {"summary": {"overall_state": "ready"}}
        release_channel = {
            "status": "published",
            "rolloutState": "promoted_preview",
            "supportabilityState": "supported",
            "release_proof": {"status": "passed"},
            "proof_freshness": {"state": "fresh"},
        }
        weekly_governor_packet = {
            "status": "blocked",
            "status_reason": "Fleet package is closed; measured rollout remains blocked.",
            "decision_board": {
                "current_launch_action": "launch_expand",
                "current_launch_reason": "Launch expansion is approved for the next bounded window while canaries and support closure remain clear.",
            },
            "public_status_copy": {
                "state": "freeze_launch",
                "body": "Hold expansion until successor dependencies, readiness, parity, localization/accessibility quality, status-plane final claim, local release proof, canary, closure, and support gates are all green.",
            },
            "measured_rollout_loop": {
                "rollback_watch": False,
            },
        }

        payload = self.admin.publish_readiness_payload(
            status,
            artifact_freshness=artifact_freshness,
            support_surface=support_surface,
            journey_gates=journey_gates,
            release_channel=release_channel,
            weekly_governor_packet=weekly_governor_packet,
            provider_routes=[],
        )

        self.assertEqual(payload["state"], "blocked")
        self.assertIn(
            "Hold expansion until successor dependencies, readiness, parity, localization/accessibility quality, status-plane final claim, local release proof, canary, closure, and support gates are all green.",
            payload["blocking_reasons"],
        )
        self.assertNotIn(
            "Launch expansion is approved for the next bounded window while canaries and support closure remain clear.",
            payload["blocking_reasons"],
        )

    def test_publish_readiness_blocks_when_weekly_governor_packet_enters_rollback_watch(self) -> None:
        status = {
            "runtime_healing": {"summary": {"alert_state": "healthy"}},
        }
        artifact_freshness = {
            "status_plane": {"state": "fresh"},
            "progress_report": {"state": "fresh"},
            "journey_gates": {"state": "fresh"},
            "release_channel": {"state": "fresh"},
            "weekly_governor_packet": {"state": "fresh"},
        }
        support_surface = {"summary": {}, "freshness": {"state": "fresh"}}
        journey_gates = {"summary": {"overall_state": "ready"}}
        release_channel = {
            "status": "published",
            "rolloutState": "promoted_preview",
            "supportabilityState": "supported",
            "release_proof": {"status": "passed"},
            "proof_freshness": {"state": "fresh"},
        }
        weekly_governor_packet = {
            "status": "blocked",
            "status_reason": "Fleet package is closed; measured rollout remains blocked.",
            "decision_board": {
                "current_launch_action": "freeze_launch",
                "current_launch_reason": "Launch expansion is frozen with rollback watch active.",
            },
            "public_status_copy": {
                "state": "freeze_with_rollback_watch",
                "body": "Launch expansion is frozen with rollback watch active.",
            },
            "measured_rollout_loop": {
                "rollback_watch": True,
            },
        }

        payload = self.admin.publish_readiness_payload(
            status,
            artifact_freshness=artifact_freshness,
            support_surface=support_surface,
            journey_gates=journey_gates,
            release_channel=release_channel,
            weekly_governor_packet=weekly_governor_packet,
            provider_routes=[],
        )

        self.assertEqual(payload["state"], "blocked")
        self.assertIn(
            "Launch expansion is frozen with rollback watch active.",
            payload["blocking_reasons"],
        )
        self.assertEqual(payload["signals"]["weekly_governor_public_state"], "freeze_with_rollback_watch")

    def test_public_progress_report_payload_refreshes_stale_artifact_before_loading_generated_bundle(self) -> None:
        stale = {
            "progress_report": {"state": "stale"},
            "progress_history": {"state": "stale"},
        }
        fresh = {
            "progress_report": {"state": "fresh"},
            "progress_history": {"state": "fresh"},
        }
        expected = {"parts": [{"id": "core"}]}

        with mock.patch.object(self.admin, "published_artifact_freshness_payload", side_effect=[stale, fresh]):
            with mock.patch.object(self.admin, "maybe_refresh_published_artifacts", return_value={"status": "refreshed"}) as refresher:
                with mock.patch.object(self.admin, "load_progress_report_payload", return_value=expected) as loader:
                    payload = self.admin.public_progress_report_payload()

        self.assertEqual(payload, expected)
        refresher.assert_called_once_with()
        loader.assert_called_once_with(repo_root=self.admin.FLEET_MOUNT_ROOT, prefer_generated=True)

    def test_public_progress_report_payload_falls_back_to_live_build_when_artifact_stays_stale(self) -> None:
        stale = {
            "progress_report": {"state": "stale"},
            "progress_history": {"state": "fresh"},
        }
        expected = {"parts": [{"id": "core"}], "eta_scope": "live"}

        with mock.patch.object(self.admin, "published_artifact_freshness_payload", side_effect=[stale, stale]):
            with mock.patch.object(self.admin, "maybe_refresh_published_artifacts", return_value={"status": "cooldown"}) as refresher:
                with mock.patch.object(self.admin, "load_progress_report_payload", return_value=expected) as loader:
                    payload = self.admin.public_progress_report_payload()

        self.assertEqual(payload, expected)
        refresher.assert_called_once_with()
        loader.assert_called_once_with(repo_root=self.admin.FLEET_MOUNT_ROOT, prefer_generated=False)

    def test_runtime_healing_payload_surfaces_service_state_and_recent_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            autoheal_dir = Path(tmpdir) / "autoheal"
            autoheal_dir.mkdir(parents=True, exist_ok=True)
            (autoheal_dir / "fleet-controller.status.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-03-27T12:00:00Z",
                        "service": "fleet-controller",
                        "current_state": "cooldown",
                        "observed_status": "unhealthy",
                        "consecutive_failures": 2,
                        "threshold": 2,
                        "cooldown_active": True,
                        "cooldown_remaining_seconds": 90,
                        "last_action": "cooldown",
                        "last_result": "waiting",
                        "last_detail": "timed out",
                        "last_restart_at": "2026-03-27T11:55:00Z",
                        "last_failure_at": "2026-03-27T11:59:30Z",
                        "last_recovered_at": "2026-03-27T11:55:10Z",
                        "total_restarts": 2,
                        "total_failures": 4,
                        "restart_window_count": 2,
                        "restart_window_seconds": 1800,
                        "escalation_threshold": 3,
                    }
                ),
                encoding="utf-8",
            )
            events_path = autoheal_dir / "events.jsonl"
            events_path.write_text(
                json.dumps(
                    {
                        "at": "2026-03-27T11:59:30Z",
                        "service": "fleet-controller",
                        "event": "cooldown_active",
                        "status": "unhealthy",
                        "detail": "timed out",
                        "consecutive_failures": 2,
                        "cooldown_remaining_seconds": 90,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            fixed_now = self.admin.dt.datetime(2026, 3, 27, 12, 0, tzinfo=self.admin.UTC)
            with mock.patch.object(self.admin, "REBUILDER_AUTOHEAL_STATE_DIR", autoheal_dir):
                with mock.patch.object(self.admin, "RUNTIME_HEALING_EVENTS_PATH", events_path):
                    with mock.patch.object(self.admin, "utc_now", return_value=fixed_now):
                        payload = self.admin.runtime_healing_payload()

            self.assertEqual(payload["summary"]["alert_state"], "degraded")
            self.assertEqual(payload["summary"]["degraded_service_count"], 1)
            self.assertEqual(payload["services"][0]["service"], "fleet-controller")
            self.assertTrue(payload["services"][0]["cooldown_active"])
            self.assertEqual(payload["recent_events"][0]["event"], "cooldown_active")

    def test_external_proof_autoingest_payload_surfaces_waiting_bundle_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "external-proof-autoingest"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "status.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-04-20T12:40:00Z",
                        "current_state": "waiting_for_bundle",
                        "commands_dir": "/docker/fleet/.codex-studio/published/external-proof-commands",
                        "observed_bundle_count": 0,
                        "last_result": "waiting_for_bundle",
                        "last_detail": "waiting for a returned host proof bundle",
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(self.admin, "EXTERNAL_PROOF_AUTOINGEST_STATUS_PATH", state_dir / "status.json"):
                payload = self.admin.external_proof_autoingest_payload()

        self.assertEqual(payload["current_state"], "waiting_for_bundle")
        self.assertEqual(payload["summary"]["alert_state"], "tracking")
        self.assertIn("Return the Windows host proof bundle", payload["summary"]["recommended_action"])

    def test_canonical_public_status_payload_includes_runtime_healing(self) -> None:
        with mock.patch.object(
            self.admin,
            "runtime_healing_payload",
            return_value={
                "generated_at": "2026-03-27T12:00:00Z",
                "enabled": True,
                "summary": {"alert_state": "healthy", "degraded_service_count": 0, "recent_restart_count": 1},
                "services": [
                    {
                        "service": "fleet-controller",
                        "current_state": "healthy",
                        "observed_status": "healthy",
                        "consecutive_failures": 0,
                        "cooldown_active": False,
                        "cooldown_remaining_seconds": 0,
                        "last_restart_at": "2026-03-27T11:55:00Z",
                        "last_result": "recovered",
                        "last_detail": "service recovered after bounded restart",
                        "total_restarts": 1,
                        "restart_window_count": 1,
                        "escalation_threshold": 3,
                    }
                ],
            },
        ), mock.patch.object(
            self.admin,
            "external_proof_autoingest_payload",
            return_value={
                "generated_at": "2026-04-20T12:45:00Z",
                "enabled": True,
                "current_state": "waiting_for_bundle",
                "commands_dir": "/docker/fleet/.codex-studio/published/external-proof-commands",
                "observed_bundle_count": 0,
                "last_attempt_at": "",
                "last_success_at": "",
                "last_result": "waiting_for_bundle",
                "last_detail": "waiting for a returned host proof bundle",
                "summary": {"alert_state": "tracking", "alert_reason": "Waiting for a returned host proof bundle."},
            },
        ):
            payload = self.admin.canonical_public_status_payload(
                {
                    "generated_at": "2026-03-24T12:00:00Z",
                    "projects": [],
                    "groups": [],
                    "cockpit": {"summary": {}, "mission_board": {}},
                }
            )

        self.assertEqual(payload["runtime_healing"]["summary"]["alert_state"], "healthy")
        self.assertEqual(payload["runtime_healing"]["services"][0]["service"], "fleet-controller")
        self.assertEqual(payload["external_proof_autoingest"]["current_state"], "waiting_for_bundle")

    def test_canonical_public_status_payload_includes_trace_context(self) -> None:
        with mock.patch.object(self.admin, "runtime_healing_payload", return_value={"generated_at": "2026-03-27T12:00:00Z", "enabled": True, "summary": {}, "services": []}):
            payload = self.admin.canonical_public_status_payload(
                {
                    "generated_at": "2026-03-24T12:00:00Z",
                    "trace": {"trace_id": "admin-status-20260324t120000z-abcdef123456"},
                    "auditor": {"last_run": {"trace_id": "auditor-20260324t115500z-fedcba654321"}},
                    "projects": [{"id": "fleet", "active_run_id": 42, "active_run_trace_id": "controller-core-20260324t115000z-a1b2c3d4e5f6"}],
                    "groups": [],
                    "cockpit": {"summary": {}, "mission_board": {}},
                }
            )

        self.assertEqual(payload["trace"]["trace_id"], "admin-status-20260324t120000z-abcdef123456")
        self.assertEqual(payload["trace"]["auditor_trace_id"], "auditor-20260324t115500z-fedcba654321")
        self.assertEqual(payload["trace"]["active_run_traces"][0]["trace_id"], "controller-core-20260324t115000z-a1b2c3d4e5f6")

    def test_sync_runtime_healing_incidents_opens_and_resolves_service_incident(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "fleet.db"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_type TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    incident_kind TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    context_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )
            conn.commit()
            conn.close()

            old_db_path = self.admin.DB_PATH
            self.admin.DB_PATH = db_path
            self.addCleanup(setattr, self.admin, "DB_PATH", old_db_path)

            self.admin.sync_runtime_healing_incidents(
                {
                    "services": [
                        {
                            "service": "fleet-controller",
                            "current_state": "escalation_required",
                            "observed_status": "unhealthy",
                            "consecutive_failures": 4,
                            "cooldown_active": False,
                            "cooldown_remaining_seconds": 0,
                            "last_restart_at": "2026-03-27T11:55:00Z",
                            "last_result": "restart_failed",
                            "last_detail": "health probe timed out repeatedly",
                            "total_restarts": 3,
                            "restart_window_count": 3,
                            "escalation_threshold": 3,
                        }
                    ]
                }
            )

            open_rows = self.admin.incidents(status="open", scope_type="service", scope_ids=["fleet-controller"])
            self.assertEqual(len(open_rows), 1)
            self.assertEqual(open_rows[0]["incident_kind"], self.admin.RUNTIME_AUTOHEAL_ESCALATED_INCIDENT_KIND)
            self.assertEqual(open_rows[0]["severity"], "critical")

            self.admin.sync_runtime_healing_incidents(
                {
                    "services": [
                        {
                            "service": "fleet-controller",
                            "current_state": "healthy",
                            "observed_status": "healthy",
                        }
                    ]
                }
            )

            self.assertEqual(self.admin.incidents(status="open", scope_type="service", scope_ids=["fleet-controller"]), [])

    def test_publish_readiness_payload_blocks_on_runtime_escalation_and_stale_public_truth(self) -> None:
        payload = self.admin.publish_readiness_payload(
            {"config": {"lanes": {}}},
            runtime_healing={"summary": {"alert_state": "action_needed", "alert_reason": "controller auto-heal escalated"}},
            artifact_freshness={
                "status_plane": {"state": "fresh"},
                "journey_gates": {"state": "fresh"},
                "progress_report": {"state": "stale"},
                "support_packets": {"state": "fresh"},
            },
            support_surface={"summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0}, "freshness": {"state": "fresh"}},
            journey_gates={"summary": {"overall_state": "ready", "blocked_count": 0, "warning_count": 0}},
            provider_routes=[{"posture": "safe_today"}],
        )

        self.assertEqual(payload["state"], "blocked")
        self.assertIn("controller auto-heal escalated", " ".join(payload["blocking_reasons"]))
        self.assertIn("public guide/progress is stale.", payload["blocking_reasons"])

    def test_publish_readiness_payload_warns_when_journey_gates_are_not_boring(self) -> None:
        payload = self.admin.publish_readiness_payload(
            {"config": {"lanes": {}}},
            runtime_healing={"summary": {"alert_state": "healthy"}},
            artifact_freshness={
                "status_plane": {"state": "fresh"},
                "journey_gates": {"state": "fresh"},
                "release_channel": {"state": "fresh"},
                "progress_report": {"state": "fresh"},
                "support_packets": {"state": "fresh"},
            },
            support_surface={"summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0}, "freshness": {"state": "fresh"}},
            journey_gates={"summary": {"overall_state": "warning", "blocked_count": 0, "warning_count": 2, "recommended_action": "Close the remaining journey warnings."}},
            provider_routes=[{"posture": "safe_today"}],
        )

        self.assertEqual(payload["state"], "warning")
        self.assertIn("Close the remaining journey warnings.", payload["warning_reasons"])
        self.assertEqual(payload["signals"]["journey_gate_state"], "warning")

    def test_publish_readiness_payload_warns_when_release_channel_truth_needs_review(self) -> None:
        payload = self.admin.publish_readiness_payload(
            {"config": {"lanes": {}}},
            runtime_healing={"summary": {"alert_state": "healthy"}},
            artifact_freshness={
                "status_plane": {"state": "fresh"},
                "journey_gates": {"state": "fresh"},
                "release_channel": {"state": "fresh"},
                "progress_report": {"state": "fresh"},
                "support_packets": {"state": "fresh"},
            },
            support_surface={"summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0}, "freshness": {"state": "fresh"}},
            journey_gates={"summary": {"overall_state": "ready", "blocked_count": 0, "warning_count": 0}},
            release_channel={
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "review_required",
                "supportabilitySummary": "Treat the current shelf as review-required until release proof and support closure checks pass.",
                "release_proof": {"status": "missing"},
                "proof_freshness": {"state": "missing"},
            },
            provider_routes=[{"posture": "safe_today"}],
        )

        self.assertEqual(payload["state"], "warning")
        self.assertIn("review-required", " ".join(payload["warning_reasons"]).lower())
        self.assertEqual(payload["signals"]["release_channel_proof_status"], "missing")

    def test_publish_readiness_payload_allows_fallback_thin_in_local_docker_preview(self) -> None:
        payload = self.admin.publish_readiness_payload(
            {"config": {"lanes": {}}},
            runtime_healing={"summary": {"alert_state": "healthy"}},
            artifact_freshness={
                "status_plane": {"state": "fresh"},
                "journey_gates": {"state": "fresh"},
                "release_channel": {"state": "fresh"},
                "progress_report": {"state": "fresh"},
                "support_packets": {"state": "fresh"},
            },
            support_surface={"summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0}, "freshness": {"state": "fresh"}},
            journey_gates={"summary": {"overall_state": "ready", "blocked_count": 0, "warning_count": 0}},
            release_channel={
                "status": "published",
                "rolloutState": "local_docker_preview",
                "supportabilityState": "local_docker_proven",
                "release_proof": {"status": "passed"},
                "proof_freshness": {"state": "fresh"},
            },
            provider_routes=[{"posture": "fallback_thin"}],
        )

        self.assertEqual(payload["state"], "ready")
        self.assertEqual(payload["signals"]["provider_review_due_count"], 0)
        self.assertEqual(payload["signals"]["provider_fallback_thin_count"], 1)

    def test_publish_readiness_payload_warns_when_promoted_preview_still_has_fallback_thin_routes(self) -> None:
        payload = self.admin.publish_readiness_payload(
            {"config": {"lanes": {}}},
            runtime_healing={"summary": {"alert_state": "healthy"}},
            artifact_freshness={
                "status_plane": {"state": "fresh"},
                "journey_gates": {"state": "fresh"},
                "release_channel": {"state": "fresh"},
                "progress_report": {"state": "fresh"},
                "support_packets": {"state": "fresh"},
            },
            support_surface={"summary": {"closure_waiting_on_release_truth": 0, "needs_human_response": 0}, "freshness": {"state": "fresh"}},
            journey_gates={"summary": {"overall_state": "ready", "blocked_count": 0, "warning_count": 0}},
            release_channel={
                "status": "published",
                "rolloutState": "promoted_preview",
                "supportabilityState": "verified",
                "release_proof": {"status": "passed"},
                "proof_freshness": {"state": "fresh"},
            },
            provider_routes=[{"posture": "fallback_thin"}],
        )

        self.assertEqual(payload["state"], "warning")
        self.assertIn("fallback coverage is still thin", " ".join(payload["warning_reasons"]).lower())

    def test_canonical_public_status_payload_surfaces_participant_dispatch_canaries(self) -> None:
        with mock.patch.object(
            self.admin,
            "release_channel_surface_payload",
            return_value={
                "truth_source": "registry_runtime",
                "version": "6.1.0-preview.4",
                "status": "published",
                "artifacts": [{"id": "windows-installer"}],
                "release_proof": {"status": "passed"},
                "freshness": {"state": "fresh"},
                "proof_freshness": {"state": "fresh"},
            },
        ):
            payload = self.admin.canonical_public_status_payload(
                {
                    "generated_at": "2026-03-24T12:00:00Z",
                    "projects": [
                        {
                            "id": "core",
                            "participant_burst": {
                                "enabled": True,
                                "allow_chatgpt_accounts": True,
                                "eligible_task_classes": ["bounded_fix", "multi_file_impl"],
                                "landing_lane": "jury",
                                "require_jury_before_land": True,
                            },
                            "account_policy": {
                                "allow_chatgpt_accounts": True,
                            },
                            "review": {"mode": "github"},
                            "deployment": {},
                            "readiness": {},
                        },
                        {
                            "id": "fleet",
                            "account_policy": {
                                "allow_chatgpt_accounts": False,
                            },
                            "review": {"mode": "local"},
                            "deployment": {},
                            "readiness": {},
                        },
                    ],
                    "groups": [],
                    "cockpit": {"summary": {}, "mission_board": {}},
                }
            )

        self.assertEqual(payload["dispatch_policy"]["participant_dispatch_canary_count"], 1)
        self.assertEqual(payload["dispatch_policy"]["participant_dispatch_canaries"][0]["project_id"], "core")
        self.assertEqual(payload["dispatch_policy"]["participant_dispatch_canaries"][0]["review_mode"], "github")
        self.assertEqual(payload["dispatch_policy"]["operator_only_projects"], ["fleet"])
        self.assertEqual(payload["release_channel"]["truth_source"], "registry_runtime")
        self.assertEqual(payload["release_channel"]["version"], "6.1.0-preview.4")

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

    def test_feedback_forge_surface_payload_routes_house_rule_questions_to_karma_forge(self) -> None:
        weekly_pulse = {
            "generated_at": "2026-04-23T10:04:57Z",
            "next_checkpoint_question": "What evidence would justify a safe prototype?",
            "top_support_or_feedback_clusters": [
                {
                    "cluster_id": "public_release_follow_through",
                    "summary": "Downloads, updates, support closure, and trust copy must move in lockstep.",
                }
            ],
            "governor_decisions": [
                {
                    "action": "focus_shift",
                    "reason": "Keep the public trust and support loop coherent while the longest pole stays in Core Engine.",
                }
            ],
        }
        progress_report = {
            "headline": "Progress report for a product becoming a build machine.",
            "active_wave": "Next 12 Biggest Wins",
            "active_wave_status": "complete",
        }
        support_surface = {
            "packets": [],
            "summary": {
                "open_packet_count": 0,
                "needs_human_response": 2,
                "closure_waiting_on_release_truth": 1,
                "top_clusters": [{"kind": "feedback", "target_repo": "chummer6-hub", "count": 3}],
            },
            "freshness": {"state": "fresh", "label": "fresh"},
        }

        with mock.patch.object(self.admin, "support_case_surface_payload", return_value=support_surface), mock.patch.object(
            self.admin,
            "load_json_payload",
            side_effect=lambda path: weekly_pulse if path == self.admin.CHUMMER_WEEKLY_PRODUCT_PULSE_PATH else {},
        ), mock.patch.object(
            self.admin,
            "load_published_json_payload",
            side_effect=lambda filename: progress_report if filename == self.admin.PROGRESS_REPORT_FILENAME else {},
        ):
            payload = self.admin.feedback_forge_surface_payload(
                "Does this house rule feedback belong in Karma Forge, and what should we ask next?"
            )

        self.assertIn("KARMA FORGE", payload["answer"])
        self.assertIn("Icanpreneur", payload["answer"])
        self.assertEqual(payload["support_snapshot"]["needs_human_response"], 2)
        self.assertEqual(payload["discovery_lane"]["entry_lane"], "Icanpreneur adaptive interview")
        self.assertTrue(any(item["label"] == "KARMA FORGE horizon" for item in payload["evidence"]))
        self.assertEqual(
            payload["suggested_questions"][0],
            "What house-rule pain is actually blocking play at the table?",
        )

    def test_karma_forge_interview_tracks_payload_includes_gm_track(self) -> None:
        tracks = self.admin.karma_forge_interview_tracks_payload()

        gm_track = next(item for item in tracks if item["key"] == "gm_house_rule_track")
        self.assertEqual(gm_track["family"], "gm_house_rule")
        self.assertIn("What rule does your table change most often?", gm_track["questions"])

    def test_feedback_forge_house_rule_draft_payload_builds_house_rule_packets(self) -> None:
        self.admin.utc_now = lambda: self.admin.parse_iso("2026-04-23T12:00:00Z")

        payload = self.admin.feedback_forge_house_rule_draft_payload(
            {
                "feedback_question": "Can we make campaign gear unlocks visible before play?",
                "discovery_track": "gm_house_rule_track",
                "respondent_role": "GM",
                "edition": "SR6",
                "table_type": "home_campaign",
                "user_words_summary": "I want to mark gear unavailable until the campaign unlocks it.",
                "current_workaround": "Manual review and Discord notes.",
                "interpreted_need_summary": "Campaign-scoped availability overlays with player-visible receipts and rollback.",
                "impact_notes": "Players should see the restriction before they join and get a before/after build diff.",
                "shareability_notes": "This should eventually become a reusable pack for other tables.",
            }
        )

        packet = payload["packet"]
        self.assertEqual(packet["source"]["respondent_role"], "GM")
        self.assertIn("availability", packet["affected_domains"])
        self.assertIn("campaign", packet["desired_scope"])
        self.assertIn("reusable_pack_candidate", packet["desired_scope"])
        self.assertIn("CampaignOverlayPackage", packet["likely_chummer_objects"])
        self.assertTrue(packet["trust_requirements"]["player_visible_before_join"])
        self.assertEqual(packet["classification"]["proposed_route"], "KARMA_FORGE")
        self.assertEqual(payload["candidate"]["candidate_decision"], "campaign_overlay_candidate")
        self.assertIn("What rule does your table change most often?", payload["next_questions"])

    def test_api_admin_feedback_forge_house_rule_draft_uses_helper(self) -> None:
        with mock.patch.object(
            self.admin,
            "feedback_forge_house_rule_draft_payload",
            return_value={"packet": {"id": "hrp_demo"}},
        ) as helper:
            payload = self.admin.api_admin_feedback_forge_house_rule_draft(
                feedback_question="Does this belong in Karma Forge?",
                discovery_track="gm_house_rule_track",
                respondent_role="GM",
                edition="SR6",
                table_type="home_campaign",
                user_words_summary="Need campaign rule overlays",
                current_workaround="Discord",
                interpreted_need_summary="Overlay plus receipts",
                impact_notes="Need before-join visibility",
                shareability_notes="Could be reusable",
            )

        helper.assert_called_once()
        self.assertEqual(payload["packet"]["id"], "hrp_demo")

    def test_api_admin_feedback_forge_uses_helper(self) -> None:
        with mock.patch.object(
            self.admin,
            "feedback_forge_surface_payload",
            return_value={"answer": "ok", "question": "why"},
        ) as helper:
            payload = self.admin.api_admin_feedback_forge("why")

        helper.assert_called_once_with("why")
        self.assertEqual(payload["answer"], "ok")


if __name__ == "__main__":
    unittest.main()
