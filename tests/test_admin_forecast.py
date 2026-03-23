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
            self.admin.ea_codex_profiles = lambda force=False: {
                "profiles": [
                    {"model": "ea-coder-hard", "provider_hint_order": ["onemin"]},
                    {"model": "ea-coder-survival", "provider_hint_order": ["browseract"]},
                ]
            }

            payload = self.admin.onemin_codexer_runtime_payload()

            self.assertEqual(payload["active_onemin_codexers"], 1)
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
            self.admin.ea_codex_profiles = lambda force=False: {
                "profiles": [
                    {"model": "ea-coder-hard-batch", "provider_hint_order": ["onemin"]},
                ]
            }
            self.admin.ea_onemin_manager_status = lambda force=False: {
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

    def test_ea_onemin_manager_billing_aggregate_infers_topup_eta_from_billing_cycle(self) -> None:
        fixed_now = self.admin.dt.datetime(2026, 3, 23, 11, 10, 2, tzinfo=self.admin.dt.timezone.utc)
        with mock.patch.object(self.admin, "utc_now", return_value=fixed_now):
            self.admin.ea_codex_profiles = lambda force=False: {"profiles": []}
            self.admin.ea_onemin_manager_status = lambda force=False: {
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
            self.admin.ea_codex_profiles = lambda force=False: {"profiles": []}
            self.admin.ea_onemin_manager_status = lambda force=False: {
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
            self.admin.ea_codex_profiles = lambda force=False: {}

            payload = self.admin.onemin_codexer_runtime_payload()

            self.assertEqual(payload["active_onemin_codexers"], 1)
            self.assertEqual(payload["active_onemin_accounts"], ["acct-ea-core"])

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
        self.assertEqual(payload["participant_burst"]["premium_queue_depth"], 1)
        self.assertIn("fleet", payload["participant_burst"]["surge_mode_projects"])

    def test_mission_board_payload_includes_jury_telemetry(self) -> None:
        self.admin.load_latest_telemetry_payload = lambda _status: {"summary": {}, "review_loop": {}, "worker_utilization": {}}
        self.admin.jury_telemetry_payload = lambda status, lane_capacities: {
            "active_jury_jobs": 1,
            "queued_jury_jobs": 2,
            "blocked_total_workers": 3,
        }
        self.admin.ea_onemin_manager_billing_aggregate = lambda force=False: {}

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
        self.admin.ea_onemin_manager_billing_aggregate = lambda force=False: {
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
        self.admin.jury_telemetry_payload = lambda status, lane_capacities: {
            "participant_burst": {
                "active_lanes": 2,
                "sponsor_ready_lanes": 2,
                "effective_capacity_by_project": {"core": 3},
            }
        }
        self.admin.onemin_codexer_runtime_payload = lambda: {
            "active_onemin_codexers": 2,
            "active_onemin_projects": ["core", "ui"],
            "active_onemin_accounts": ["acct-ea-core", "acct-ea-fleet"],
        }
        self.admin.ea_onemin_manager_billing_aggregate = lambda force=False: {
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
        self.assertEqual(booster["sponsor_ready_boosters"], 2)
        self.assertEqual(booster["hourly_burn_rate_credits"], 20000.0)
        self.assertEqual(booster["per_booster_hourly_burn_rate_credits"], 10000.0)
        self.assertEqual(booster["active_onemin_codexers"], 2)
        self.assertEqual(booster["active_onemin_projects"], ["core", "ui"])
        self.assertEqual(booster["per_onemin_codexer_hourly_burn_rate_credits"], 10000.0)
        self.assertEqual(booster["credits_left_percent"], 40.0)
        self.assertEqual(booster["hours_remaining_with_topup"], 420.0)
        self.assertEqual(booster["effective_capacity_by_project"]["core"], 3)

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
