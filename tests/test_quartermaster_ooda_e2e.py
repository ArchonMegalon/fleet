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


CONTROLLER_MODULE_PATH = Path("/docker/fleet/controller/app.py")
QUARTERMASTER_MODULE_PATH = Path("/docker/fleet/quartermaster/app.py")
ADMIN_MODULE_PATH = Path("/docker/fleet/admin/app.py")


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


def load_module(path: Path, module_name: str):
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuartermasterOodaE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = load_module(CONTROLLER_MODULE_PATH, "test_quartermaster_ooda_controller")
        self.quartermaster = load_module(QUARTERMASTER_MODULE_PATH, "test_quartermaster_ooda_service")
        self.admin = load_module(ADMIN_MODULE_PATH, "test_quartermaster_ooda_admin")

    def test_controller_tick_dispatches_and_redispatches_finished_boosters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "config"
            config_root.mkdir(parents=True, exist_ok=True)
            state_root = root / "state"
            repo_alpha = root / "alpha"
            repo_beta = root / "beta"
            repo_alpha.mkdir()
            repo_beta.mkdir()

            (config_root / "fleet.yaml").write_text("projects: []\n", encoding="utf-8")
            (config_root / "quartermaster.yaml").write_text(
                "\n".join(
                    [
                        "quartermaster:",
                        "  enabled: true",
                        "  mode: enforce",
                        "  driver: controller_tick",
                        "  baseline_tick_seconds: 600",
                        "  event_tick_min_seconds: 90",
                        "  plan_ttl_seconds: 900",
                        "  max_scale_up_per_tick: 2",
                        "  max_scale_down_per_tick: 2",
                        "  telemetry:",
                        "    provider: ea_onemin_manager",
                        "    onemin_manager: ea",
                        "    onemin_query_mode: manager",
                        "  credit:",
                        "    reserve_buffer_hours: 1",
                        "    minimum_headroom_hours: 1",
                        "    cycle_reserve_percent: 0",
                        "  incidents:",
                        "    triggers:",
                        "      - review_backpressure",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "review_fabric.yaml").write_text(
                "\n".join(
                    [
                        "review_fabric:",
                        "  default:",
                        "    shards:",
                        "      service_floor: 2",
                        "      max_queue_depth_per_active_reviewer: 10",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "audit_fabric.yaml").write_text(
                "\n".join(
                    [
                        "audit_fabric:",
                        "  default:",
                        "    service_floor: 1",
                        "    target_parallelism: 20",
                        "    debt_backpressure:",
                        "      open_incidents_yellow: 8",
                        "      open_incidents_red: 16",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "booster_pools.yaml").write_text(
                "\n".join(
                    [
                        "booster_pools:",
                        "  operator_funded:",
                        "    worker_lane: core_booster",
                        "    authority_lane: core_authority",
                        "    rescue_lane: core_rescue",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "booster_pools.yaml").write_text(
                "\n".join(
                    [
                        "booster_pools:",
                        "  operator_funded:",
                        "    worker_lane: core_booster",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "review_fabric.yaml").write_text(
                "\n".join(
                    [
                        "review_fabric:",
                        "  default:",
                        "    shards:",
                        "      service_floor: 1",
                        "      max_queue_depth_per_active_reviewer: 2",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "audit_fabric.yaml").write_text(
                "\n".join(
                    [
                        "audit_fabric:",
                        "  default:",
                        "    service_floor: 1",
                        "    target_parallelism: 2",
                        "    debt_backpressure:",
                        "      open_incidents_yellow: 8",
                        "      open_incidents_red: 16",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "review_fabric.yaml").write_text(
                "\n".join(
                    [
                        "review_fabric:",
                        "  default:",
                        "    shards:",
                        "      service_floor: 2",
                        "      max_queue_depth_per_active_reviewer: 10",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "audit_fabric.yaml").write_text(
                "\n".join(
                    [
                        "audit_fabric:",
                        "  default:",
                        "    service_floor: 1",
                        "    target_parallelism: 20",
                        "    debt_backpressure:",
                        "      open_incidents_yellow: 8",
                        "      open_incidents_red: 16",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "booster_pools.yaml").write_text(
                "\n".join(
                    [
                        "booster_pools:",
                        "  operator_funded:",
                        "    worker_lane: core_booster",
                        "    authority_lane: core_authority",
                        "    rescue_lane: core_rescue",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.CONFIG_PATH = config_root / "fleet.yaml"
            self.controller.QUARTERMASTER_PATH = config_root / "quartermaster.yaml"
            self.controller.init_db()
            self.controller._EA_ONEMIN_MANAGER_CACHE = {"fetched_at": 0.0, "payload": {}}
            self.controller._QUARTERMASTER_PLAN_CACHE = {"fetched_at": 0.0, "payload": {}}
            self.controller._QUARTERMASTER_TICK_CACHE = {"last_tick_at": 0.0, "event_signature": ""}
            self.controller._QUARTERMASTER_RECONCILE_CACHE = {"fetched_at": 0.0, "plan_generated_at": "", "payload": {}}
            self.controller.state.tasks.clear()

            self.quartermaster.CONFIG_PATH = config_root / "fleet.yaml"
            self.quartermaster.PLAN_CACHE_PATH = state_root / "quartermaster" / "latest_capacity_plan.json"

            config = {
                "policies": {
                    "max_parallel_runs": 4,
                    "stale_heartbeat_seconds": 1800,
                },
                "projects": [
                    {
                        "id": "alpha",
                        "path": str(repo_alpha),
                        "queue": ["alpha slice 1", "alpha slice 2"],
                        "enabled": True,
                        "account_policy": {"preferred_accounts": ["acct-ea-core-a", "acct-ea-core-b"]},
                        "booster_pool_contract": {
                            "pool": "operator_funded",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 1,
                        },
                    },
                    {
                        "id": "beta",
                        "path": str(repo_beta),
                        "queue": ["beta slice 1", "beta slice 2"],
                        "enabled": True,
                        "account_policy": {"preferred_accounts": ["acct-ea-core-a", "acct-ea-core-b"]},
                        "booster_pool_contract": {
                            "pool": "operator_funded",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 1,
                        },
                    },
                ],
                "accounts": {
                    "acct-ea-core-a": {
                        "lane": "core",
                        "auth_kind": "api_key",
                        "allowed_models": ["ea-coder-hard"],
                        "max_parallel_runs": 1,
                    },
                    "acct-ea-core-b": {
                        "lane": "core",
                        "auth_kind": "api_key",
                        "allowed_models": ["ea-coder-hard"],
                        "max_parallel_runs": 1,
                    },
                },
                "lanes": {
                    "core": {"id": "core", "runtime_model": "ea-coder-hard"},
                },
                "core_backends": {},
            }
            self.controller.sync_config_to_db(config)
            self.controller.save_runtime_cache(
                self.controller.RUNTIME_CACHE_KEY_EA_ONEMIN_MANAGER_STATUS,
                {
                    "aggregate": {
                        "sum_free_credits": 2_000_000,
                        "sum_max_credits": 4_000_000,
                        "accounts": [
                            {
                                "slot_count": 1,
                                "last_billing_snapshot_at": "2026-03-23T10:00:00Z",
                                "last_member_reconciliation_at": "2026-03-23T10:00:00Z",
                            },
                            {
                                "slot_count": 1,
                                "last_billing_snapshot_at": "2026-03-23T10:00:00Z",
                                "last_member_reconciliation_at": "2026-03-23T10:00:00Z",
                            },
                        ],
                    },
                    "runway": {
                        "hours_remaining_current_pace": 20,
                        "next_topup_at": "2026-03-31T00:00:00Z",
                        "topup_amount": 2_000_000,
                    },
                },
            )

            booster_contract = {
                "pool": "operator_funded",
                "authority_lane": "core_authority",
                "booster_lane": "core_booster",
                "rescue_lane": "core_rescue",
                "project_safety_cap": 1,
            }
            self.quartermaster.admin_cockpit_status = lambda: {
                "generated_at": "2026-03-23T10:00:00Z",
                "config": {
                    "policies": {
                        "capacity_plane": {
                            "plane_caps": {
                                "core_authority_cap": 1,
                                "global_booster_cap": 2,
                                "review_shard_cap": 2,
                                "audit_shard_cap": 2,
                            }
                        }
                    },
                    "projects": [
                        {"id": "alpha", "booster_pool_contract": dict(booster_contract)},
                        {"id": "beta", "booster_pool_contract": dict(booster_contract)},
                    ],
                },
                "projects": [
                    {"id": "alpha", "booster_pool_contract": dict(booster_contract)},
                    {"id": "beta", "booster_pool_contract": dict(booster_contract)},
                ],
                "groups": [],
                "cockpit": {
                    "summary": {
                        "active_review_workers": 1,
                        "queued_jury_jobs": 0,
                        "open_incidents": 0,
                    },
                    "mission_board": {
                        "provider_credit_card": {
                            "slot_count_with_billing_snapshot": 2,
                            "slot_count_with_member_reconciliation": 2,
                            "hours_until_next_topup": 8,
                            "hours_remaining_at_current_pace_no_topup": 20,
                            "days_remaining_including_next_topup_at_7d_avg": 14,
                        },
                        "booster_runtime_card": {
                            "active_boosters": 0,
                            "active_onemin_codexers": 0,
                        },
                    },
                    "capacity_forecast": {
                        "lanes": [
                            {"lane": "core_booster", "ready_slots": 2, "configured_slots": 2, "degraded_slots": 0},
                        ]
                    },
                    "jury_telemetry": {
                        "participant_burst": {"premium_queue_depth": 2},
                        "queued_jury_jobs": 0,
                        "blocked_total_workers": 0,
                    },
                    "runway": {},
                },
            }

            started: list[tuple[str, str, str]] = []
            completed: list[tuple[str, str]] = []

            async def run_flow() -> None:
                self.controller.state.controller_loop = asyncio.get_running_loop()
                first_wave_started = asyncio.Event()
                second_wave_started = asyncio.Event()
                first_wave_finish = asyncio.Event()
                second_wave_finish = asyncio.Event()

                def service_plan(*, force_refresh: bool = False, reason: str = "") -> dict[str, object]:
                    payload = self.quartermaster.quartermaster_status_payload(force_refresh=force_refresh, tick_reason=reason)
                    plan = dict(payload.get("plan") or {})
                    now = self.controller.time.time()
                    self.controller._QUARTERMASTER_PLAN_CACHE["fetched_at"] = now
                    self.controller._QUARTERMASTER_PLAN_CACHE["payload"] = plan
                    if plan:
                        self.controller.save_runtime_cache(self.controller.RUNTIME_CACHE_KEY_QUARTERMASTER_PLAN, plan)
                    return plan

                def fake_tick(*, reason: str = "") -> dict[str, object]:
                    return service_plan(force_refresh=True, reason=reason)

                def fake_plan(force: bool = False) -> dict[str, object]:
                    cached = self.controller._QUARTERMASTER_PLAN_CACHE.get("payload")
                    if force or not isinstance(cached, dict) or not cached:
                        return service_plan(force_refresh=force)
                    return dict(cached)

                def fake_pick_account_and_model(
                    _config: dict[str, object],
                    project_cfg: dict[str, object],
                    decision: dict[str, object],
                    *,
                    reserved_account_counts: dict[str, int] | None = None,
                ) -> tuple[str | None, str | None, str, list[dict[str, object]]]:
                    reserved = dict(reserved_account_counts or {})
                    for alias in (project_cfg.get("account_policy") or {}).get("preferred_accounts") or []:
                        clean_alias = str(alias or "").strip()
                        if int(reserved.get(clean_alias) or 0) > 0:
                            continue
                        return (
                            clean_alias,
                            "ea-coder-hard",
                            f"selected {clean_alias} for {project_cfg['id']}",
                            [{"alias": clean_alias, "selected": True, "reason": "available in e2e test"}],
                        )
                    return None, None, "no free core booster account", []

                async def fake_execute_project_slice(
                    _config: dict[str, object],
                    project_cfg: dict[str, object],
                    _project_row,
                    slice_name: str,
                    decision: dict[str, object],
                    account_alias: str,
                    selected_model: str,
                    selection_note: str,
                    selection_trace,
                ) -> None:
                    project_id = str(project_cfg["id"])
                    started.append((project_id, slice_name, account_alias))
                    started_at = self.controller.utc_now()
                    self.controller.upsert_runtime_task(
                        project_id,
                        task_kind="coding",
                        task_state="running",
                        payload={
                            "slice_name": slice_name,
                            "account_alias": account_alias,
                            "selected_model": selected_model,
                            "selection_note": selection_note,
                            "selection_trace": list(selection_trace or []),
                            "decision": dict(decision or {}),
                        },
                        started_at=started_at,
                    )
                    self.controller.update_project_status(
                        project_id,
                        status="running",
                        current_slice=slice_name,
                        active_run_id=None,
                        cooldown_until=None,
                        last_run_at=started_at,
                        last_error=None,
                        spider_tier=str(decision.get("tier") or ""),
                        spider_model=selected_model,
                        spider_reason=str(decision.get("reason") or ""),
                    )
                    if slice_name.endswith("1") and sum(1 for _, name, _ in started if name.endswith("1")) >= 2:
                        first_wave_started.set()
                    if slice_name.endswith("2") and sum(1 for _, name, _ in started if name.endswith("2")) >= 2:
                        second_wave_started.set()
                    await (first_wave_finish.wait() if slice_name.endswith("1") else second_wave_finish.wait())
                    self.controller.increment_queue(project_id)
                    with self.controller.db() as conn:
                        row = conn.execute("SELECT queue_json, queue_index FROM projects WHERE id=?", (project_id,)).fetchone()
                    queue = json.loads(row["queue_json"] or "[]")
                    index = int(row["queue_index"] or 0)
                    finished_at = self.controller.utc_now()
                    next_status = "complete" if index >= len(queue) else self.controller.READY_STATUS
                    next_slice = self.controller.normalize_slice_text(queue[index]) if index < len(queue) else None
                    self.controller.update_project_status(
                        project_id,
                        status=next_status,
                        current_slice=next_slice,
                        active_run_id=None,
                        cooldown_until=None,
                        last_run_at=finished_at,
                        last_error=None,
                        spider_tier=str(decision.get("tier") or ""),
                        spider_model=selected_model,
                        spider_reason=str(decision.get("reason") or ""),
                    )
                    completed.append((project_id, slice_name))
                    self.controller.clear_runtime_task(project_id)

                def dispatch_pass() -> tuple[dict[str, object], dict[str, object], list[str]]:
                    self.controller._QUARTERMASTER_RECONCILE_CACHE = {"fetched_at": 0.0, "plan_generated_at": "", "payload": {}}
                    plan = self.controller.quartermaster_tick_if_due(config)
                    snapshot = self.controller.quartermaster_capacity_reconcile(config, plan=plan)
                    reserved_account_counts: dict[str, int] = {}
                    reserved_lane_counts: dict[str, int] = {}
                    reserved_scale_up_count = 0
                    launched: list[str] = []
                    with self.controller.db() as conn:
                        rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
                    for row in rows:
                        project_id = str(row["id"] or "").strip()
                        if not project_id or self.controller.project_has_runtime_task(project_id):
                            continue
                        project_cfg = self.controller.get_project_cfg(config, project_id)
                        candidate = self.controller.prepare_dispatch_candidate(config, project_cfg, row, self.controller.utc_now())
                        if not candidate.dispatchable or not candidate.slice_name:
                            continue
                        planned = self.controller.plan_candidate_launch(
                            config,
                            candidate,
                            reserved_account_counts=reserved_account_counts,
                            reserved_lane_counts=reserved_lane_counts,
                            reserved_scale_up_count=reserved_scale_up_count,
                        )
                        if not planned:
                            continue
                        reserved_account_counts[planned.account_alias] = int(reserved_account_counts.get(planned.account_alias) or 0) + 1
                        target_lane = str((planned.decision.get("quartermaster") or {}).get("target_lane") or "").strip()
                        if target_lane:
                            reserved_lane_counts[target_lane] = int(reserved_lane_counts.get(target_lane) or 0) + 1
                        if self.controller.launch_planned_project_task(config, planned):
                            launched.append(project_id)
                            reserved_scale_up_count += 1
                    return plan, snapshot, launched

                decision = {
                    "tier": "multi_file_impl",
                    "model_preferences": ["ea-coder-hard"],
                    "reasoning_effort": "low",
                    "estimated_prompt_chars": 2048,
                    "estimated_input_tokens": 512,
                    "estimated_output_tokens": 512,
                    "predicted_changed_files": 2,
                    "requires_contract_authority": False,
                    "reason": "quartermaster e2e",
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

                with mock.patch.object(self.controller, "quartermaster_capacity_tick", side_effect=fake_tick):
                    with mock.patch.object(self.controller, "quartermaster_capacity_plan", side_effect=fake_plan):
                        with mock.patch.object(self.controller, "classify_tier", side_effect=lambda *args, **kwargs: dict(decision)):
                            with mock.patch.object(self.controller, "pick_account_and_model", side_effect=fake_pick_account_and_model):
                                with mock.patch.object(self.controller, "execute_project_slice", side_effect=fake_execute_project_slice):
                                    first_plan, first_snapshot, first_launched = dispatch_pass()
                                    self.assertEqual(first_plan["lane_targets"]["core_booster"], 2)
                                    self.assertEqual(first_snapshot["remaining_by_lane"]["core_booster"], 2)
                                    self.assertEqual(first_launched, ["alpha", "beta"])

                                    await asyncio.wait_for(first_wave_started.wait(), timeout=1.0)
                                    self.controller._QUARTERMASTER_RECONCILE_CACHE = {"fetched_at": 0.0, "plan_generated_at": "", "payload": {}}
                                    first_inflight = self.controller.quartermaster_capacity_reconcile(config, plan=first_plan)
                                    self.assertEqual(first_inflight["usage_by_lane"]["core_booster"], 2)
                                    self.assertEqual(first_inflight["remaining_by_lane"]["core_booster"], 0)

                                    first_wave_finish.set()
                                    await asyncio.gather(*list(self.controller.state.tasks.values()))
                                    self.controller.prune_finished_tasks()

                                    second_plan, second_snapshot, second_launched = dispatch_pass()
                                    self.assertEqual(second_plan["lane_targets"]["core_booster"], 2)
                                    self.assertEqual(second_snapshot["remaining_by_lane"]["core_booster"], 2)
                                    self.assertEqual(second_launched, ["alpha", "beta"])

                                    await asyncio.wait_for(second_wave_started.wait(), timeout=1.0)
                                    self.controller._QUARTERMASTER_RECONCILE_CACHE = {"fetched_at": 0.0, "plan_generated_at": "", "payload": {}}
                                    second_inflight = self.controller.quartermaster_capacity_reconcile(config, plan=second_plan)
                                    self.assertEqual(second_inflight["usage_by_lane"]["core_booster"], 2)
                                    self.assertEqual(second_inflight["remaining_by_lane"]["core_booster"], 0)

                                    second_wave_finish.set()
                                    await asyncio.gather(*list(self.controller.state.tasks.values()))
                                    self.controller.prune_finished_tasks()

                self.controller.state.controller_loop = None

            asyncio.run(run_flow())

            with self.controller.db() as conn:
                rows = conn.execute("SELECT id, status, queue_index, current_slice FROM projects ORDER BY id").fetchall()

            self.assertEqual(
                started,
                [
                    ("alpha", "alpha slice 1", "acct-ea-core-a"),
                    ("beta", "beta slice 1", "acct-ea-core-b"),
                    ("alpha", "alpha slice 2", "acct-ea-core-a"),
                    ("beta", "beta slice 2", "acct-ea-core-b"),
                ],
            )
            self.assertEqual(
                completed,
                [
                    ("alpha", "alpha slice 1"),
                    ("beta", "beta slice 1"),
                    ("alpha", "alpha slice 2"),
                    ("beta", "beta slice 2"),
                ],
            )
            self.assertEqual(
                [(str(row["id"]), str(row["status"]), int(row["queue_index"]), row["current_slice"]) for row in rows],
                [
                    ("alpha", "complete", 2, None),
                    ("beta", "complete", 2, None),
                ],
            )

    def test_quartermaster_temporarily_scales_to_fifteen_then_drains_excess_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_root = root / "config"
            config_root.mkdir(parents=True, exist_ok=True)
            state_root = root / "state"
            repo_root = root / "fleet-repo"
            (repo_root / ".codex-studio" / "published").mkdir(parents=True, exist_ok=True)
            work_packages_path = repo_root / ".codex-studio" / "published" / "WORKPACKAGES.generated.yaml"
            work_packages_path.write_text(
                "work_packages:\n"
                + "\n".join(
                    [
                        f"  - package_id: fleet-{index:02d}\n"
                        f"    title: Fleet slice {index:02d}\n"
                        f"    allowed_paths:\n"
                        f"      - src/pkg_{index:02d}.py"
                        for index in range(1, 21)
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "review_fabric.yaml").write_text(
                "\n".join(
                    [
                        "review_fabric:",
                        "  default:",
                        "    shards:",
                        "      service_floor: 2",
                        "      max_queue_depth_per_active_reviewer: 10",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "audit_fabric.yaml").write_text(
                "\n".join(
                    [
                        "audit_fabric:",
                        "  default:",
                        "    service_floor: 1",
                        "    target_parallelism: 20",
                        "    debt_backpressure:",
                        "      open_incidents_yellow: 8",
                        "      open_incidents_red: 16",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (config_root / "booster_pools.yaml").write_text(
                "\n".join(
                    [
                        "booster_pools:",
                        "  operator_funded:",
                        "    worker_lane: core_booster",
                        "    authority_lane: core_authority",
                        "    rescue_lane: core_rescue",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            (config_root / "quartermaster.yaml").write_text(
                "\n".join(
                    [
                        "quartermaster:",
                        "  enabled: true",
                        "  mode: enforce",
                        "  driver: controller_tick",
                        "  baseline_tick_seconds: 600",
                        "  event_tick_min_seconds: 60",
                        "  plan_ttl_seconds: 900",
                        "  max_scale_up_per_tick: 15",
                        "  max_scale_down_per_tick: 15",
                        "  min_worker_dwell_seconds: 0",
                        "  idle_drain_seconds: 0",
                        "  telemetry:",
                        "    provider: ea_onemin_manager",
                        "    onemin_manager: ea",
                        "    onemin_query_mode: manager",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            self.controller.DB_PATH = root / "fleet.db"
            self.controller.LOG_DIR = root / "logs"
            self.controller.CODEX_HOME_ROOT = root / "homes"
            self.controller.GROUP_ROOT = root / "groups"
            self.controller.CONFIG_PATH = config_root / "fleet.yaml"
            self.controller.QUARTERMASTER_PATH = config_root / "quartermaster.yaml"
            self.controller.init_db()
            self.controller._EA_ONEMIN_MANAGER_CACHE = {"fetched_at": 0.0, "payload": {}}
            self.controller._QUARTERMASTER_PLAN_CACHE = {"fetched_at": 0.0, "payload": {}}
            self.controller._QUARTERMASTER_TICK_CACHE = {"last_tick_at": 0.0, "event_signature": ""}
            self.controller._QUARTERMASTER_RECONCILE_CACHE = {"fetched_at": 0.0, "plan_generated_at": "", "payload": {}}
            self.controller.state.tasks.clear()

            self.quartermaster.CONFIG_PATH = config_root / "fleet.yaml"
            self.quartermaster.PLAN_CACHE_PATH = state_root / "quartermaster" / "latest_capacity_plan.json"

            self.admin.DB_PATH = self.controller.DB_PATH

            accounts = {
                f"acct-ea-core-{index:02d}": {
                    "lane": "core",
                    "auth_kind": "api_key",
                    "allowed_models": ["ea-coder-hard"],
                    "max_parallel_runs": 1,
                }
                for index in range(1, 16)
            }
            config = {
                "policies": {"max_parallel_runs": 20, "stale_heartbeat_seconds": 1800},
                "projects": [
                    {
                        "id": "fleet",
                        "path": str(repo_root),
                        "queue": [],
                        "enabled": True,
                        "account_policy": {"preferred_accounts": list(accounts)},
                        "booster_pool_contract": {
                            "pool": "operator_funded",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 15,
                        },
                    }
                ],
                "accounts": accounts,
                "lanes": {"core": {"id": "core", "runtime_model": "ea-coder-hard"}},
                "core_backends": {},
            }
            self.controller.sync_config_to_db(config)
            self.controller.save_runtime_cache(
                self.controller.RUNTIME_CACHE_KEY_EA_ONEMIN_MANAGER_STATUS,
                {
                    "aggregate": {
                        "sum_free_credits": 10_000_000,
                        "sum_max_credits": 20_000_000,
                        "accounts": [
                            {
                                "slot_count": 1,
                                "last_billing_snapshot_at": "2026-03-23T10:00:00Z",
                                "last_member_reconciliation_at": "2026-03-23T10:00:00Z",
                            }
                            for _ in range(15)
                        ],
                    },
                    "runway": {
                        "hours_remaining_current_pace": 48,
                        "next_topup_at": "2026-03-31T00:00:00Z",
                        "topup_amount": 2_000_000,
                    },
                },
            )

            capacity_state = {"global_booster_cap": 15}

            def admin_status() -> dict[str, object]:
                booster_contract = {
                    "pool": "operator_funded",
                    "authority_lane": "core_authority",
                    "booster_lane": "core_booster",
                    "rescue_lane": "core_rescue",
                    "project_safety_cap": 15,
                }
                return {
                    "generated_at": "2026-03-23T10:00:00Z",
                    "config": {
                        "policies": {
                            "capacity_plane": {
                                "plane_caps": {
                                    "core_authority_cap": 1,
                                    "core_rescue_cap": 1,
                                    "global_booster_cap": capacity_state["global_booster_cap"],
                                    "review_shard_cap": 20,
                                    "audit_shard_cap": 20,
                                }
                            }
                        },
                        "projects": [{"id": "fleet", "booster_pool_contract": dict(booster_contract)}],
                    },
                    "projects": [
                        {
                            "id": "fleet",
                            "runtime_status": "dispatch_pending",
                            "allowed_lanes": ["core_booster"],
                            "task_allow_credit_burn": True,
                            "selected_lane": "core_booster",
                            "booster_pool_contract": dict(booster_contract),
                        }
                    ],
                    "groups": [],
                    "work_packages": self.admin.work_package_summary_payload(),
                    "cockpit": {
                        "summary": {
                            "active_review_workers": 2,
                            "queued_jury_jobs": 0,
                            "blocked_on_jury_workers": 0,
                            "open_incidents": 0,
                            "blocked_unresolved_incidents": 0,
                            "coverage_pressure_projects": 0,
                        },
                        "mission_board": {
                            "provider_credit_card": {
                                "slot_count_with_billing_snapshot": 15,
                                "slot_count_with_member_reconciliation": 15,
                                "hours_until_next_topup": 8,
                                "hours_remaining_at_current_pace_no_topup": 48,
                                "days_remaining_including_next_topup_at_7d_avg": 14,
                            },
                            "booster_runtime_card": {
                                "active_boosters": self.controller.project_active_coding_runtime_count("fleet"),
                                "active_onemin_codexers": self.controller.project_active_coding_runtime_count("fleet"),
                            },
                        },
                        "capacity_forecast": {
                            "lanes": [
                                {"lane": "core_booster", "ready_slots": 15, "configured_slots": 15, "degraded_slots": 0},
                            ]
                        },
                        "jury_telemetry": {"participant_burst": {"premium_queue_depth": 0}, "queued_jury_jobs": 0, "blocked_total_workers": 0},
                        "runway": {},
                    },
                }

            started: list[str] = []
            completed: list[str] = []
            drained: list[str] = []

            async def run_flow() -> None:
                self.controller.state.controller_loop = asyncio.get_running_loop()
                initial_fifteen_started = asyncio.Event()
                drain_complete = asyncio.Event()
                package_finish_events: dict[str, asyncio.Event] = {}
                active_packages: set[str] = set()

                async def wait_for_active_count(expected: int) -> None:
                    async def _poll() -> None:
                        while len(active_packages) != expected:
                            await asyncio.sleep(0)

                    await asyncio.wait_for(_poll(), timeout=2.0)

                def service_plan(*, force_refresh: bool = False, reason: str = "") -> dict[str, object]:
                    self.quartermaster.admin_cockpit_status = admin_status
                    payload = self.quartermaster.quartermaster_status_payload(force_refresh=force_refresh, tick_reason=reason)
                    plan = dict(payload.get("plan") or {})
                    now = self.controller.time.time()
                    self.controller._QUARTERMASTER_PLAN_CACHE["fetched_at"] = now
                    self.controller._QUARTERMASTER_PLAN_CACHE["payload"] = plan
                    if plan:
                        self.controller.save_runtime_cache(self.controller.RUNTIME_CACHE_KEY_QUARTERMASTER_PLAN, plan)
                    return plan

                def fake_tick(*, reason: str = "") -> dict[str, object]:
                    return service_plan(force_refresh=True, reason=reason)

                def fake_plan(force: bool = False) -> dict[str, object]:
                    cached = self.controller._QUARTERMASTER_PLAN_CACHE.get("payload")
                    if force or not isinstance(cached, dict) or not cached:
                        return service_plan(force_refresh=force)
                    return dict(cached)

                def fake_pick_account_and_model(
                    _config: dict[str, object],
                    _project_cfg: dict[str, object],
                    _decision: dict[str, object],
                    *,
                    reserved_account_counts: dict[str, int] | None = None,
                ) -> tuple[str | None, str | None, str, list[dict[str, object]]]:
                    reserved = dict(reserved_account_counts or {})
                    for alias in accounts:
                        if int(reserved.get(alias) or 0) > 0:
                            continue
                        return (
                            alias,
                            "ea-coder-hard",
                            f"selected {alias}",
                            [{"alias": alias, "selected": True, "reason": "available in package e2e"}],
                        )
                    return None, None, "no free core booster account", []

                async def fake_execute_project_slice(
                    _config: dict[str, object],
                    project_cfg: dict[str, object],
                    _project_row,
                    slice_name: str,
                    decision: dict[str, object],
                    account_alias: str,
                    selected_model: str,
                    selection_note: str,
                    selection_trace,
                    *,
                    package_row=None,
                ) -> None:
                    project_id = str(project_cfg["id"])
                    package = dict(package_row or {})
                    package_id = str(package.get("package_id") or "")
                    started.append(package_id)
                    active_packages.add(package_id)
                    finish_event = asyncio.Event()
                    package_finish_events[package_id] = finish_event
                    self.controller.upsert_runtime_task(
                        project_id,
                        package_id=package_id,
                        task_kind="coding",
                        task_state="running",
                        payload={
                            "slice_name": slice_name,
                            "account_alias": account_alias,
                            "selected_model": selected_model,
                            "selection_note": selection_note,
                            "selection_trace": list(selection_trace or []),
                            "decision": dict(decision or {}),
                            "package_id": package_id,
                        },
                        started_at=self.controller.utc_now(),
                    )
                    self.controller.update_work_package_runtime(package_id, status="running", runtime_state="running")
                    if len(started) == 15:
                        initial_fifteen_started.set()
                    try:
                        await finish_event.wait()
                        completed.append(package_id)
                        self.controller.update_work_package_runtime(
                            package_id,
                            status="complete",
                            runtime_state="idle",
                            completed_at=self.controller.utc_now(),
                        )
                    except asyncio.CancelledError:
                        drained.append(package_id)
                        self.controller.update_work_package_runtime(
                            package_id,
                            status=self.controller.WAITING_CAPACITY_STATUS,
                            runtime_state="idle",
                        )
                        if len(drained) == 10:
                            drain_complete.set()
                        raise
                    finally:
                        active_packages.discard(package_id)
                        self.controller.release_work_package_scope_claims(package_id)
                        self.controller.clear_runtime_task(package_id)
                        self.controller.state.tasks.pop(package_id, None)

                def dispatch_pass() -> tuple[dict[str, object], dict[str, object], list[str]]:
                    self.controller._QUARTERMASTER_RECONCILE_CACHE = {"fetched_at": 0.0, "plan_generated_at": "", "payload": {}}
                    plan = self.controller.quartermaster_tick_if_due(config)
                    snapshot = self.controller.quartermaster_capacity_reconcile(config, plan=plan, force=True)
                    reserved_account_counts: dict[str, int] = {}
                    reserved_lane_counts: dict[str, int] = {}
                    reserved_project_counts: dict[str, int] = {}
                    reserved_scope_claims: list[dict[str, object]] = []
                    launched: list[str] = []
                    with self.controller.db() as conn:
                        rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
                    for row in rows:
                        project_id = str(row["id"] or "").strip()
                        if not project_id:
                            continue
                        project_cfg = self.controller.get_project_cfg(config, project_id)
                        candidates = self.controller.prepare_work_package_dispatch_candidates(config, project_cfg, row, self.controller.utc_now())
                        for candidate in candidates:
                            planned = self.controller.plan_candidate_launch(
                                config,
                                candidate,
                                reserved_account_counts=reserved_account_counts,
                                reserved_lane_counts=reserved_lane_counts,
                                reserved_scale_up_count=len(launched),
                                reserved_project_counts=reserved_project_counts,
                                reserved_scope_claims=reserved_scope_claims,
                            )
                            if not planned:
                                continue
                            reserved_account_counts[planned.account_alias] = int(reserved_account_counts.get(planned.account_alias) or 0) + 1
                            target_lane = str((planned.decision.get("quartermaster") or {}).get("target_lane") or "").strip()
                            if target_lane:
                                reserved_lane_counts[target_lane] = int(reserved_lane_counts.get(target_lane) or 0) + 1
                            if planned.candidate.package_row:
                                reserved_scope_claims.extend(self.controller.compiled_scope_claims_for_package(planned.candidate.package_row))
                            if self.controller.launch_planned_project_task(config, planned):
                                launched.append(str(planned.package_id or ""))
                    return plan, snapshot, launched

                decision = {
                    "tier": "multi_file_impl",
                    "model_preferences": ["ea-coder-hard"],
                    "reasoning_effort": "low",
                    "estimated_prompt_chars": 2048,
                    "estimated_input_tokens": 512,
                    "estimated_output_tokens": 512,
                    "predicted_changed_files": 2,
                    "requires_contract_authority": False,
                    "reason": "quartermaster package e2e",
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

                with mock.patch.object(self.controller, "quartermaster_capacity_tick", side_effect=fake_tick):
                    with mock.patch.object(self.controller, "quartermaster_capacity_plan", side_effect=fake_plan):
                        with mock.patch.object(self.controller, "classify_tier", side_effect=lambda *args, **kwargs: dict(decision)):
                            with mock.patch.object(self.controller, "pick_account_and_model", side_effect=fake_pick_account_and_model):
                                with mock.patch.object(self.controller, "execute_project_slice", side_effect=fake_execute_project_slice):
                                    first_plan, _first_snapshot, first_launched = dispatch_pass()
                                    self.assertEqual(first_plan["lane_targets"]["core_booster"], 15)
                                    self.assertEqual(len(first_launched), 15)

                                    await asyncio.wait_for(initial_fifteen_started.wait(), timeout=2.0)
                                    inflight = self.controller.quartermaster_capacity_reconcile(config, plan=first_plan, force=True)
                                    self.assertEqual(inflight["usage_by_lane"]["core_booster"], 15)

                                    capacity_state["global_booster_cap"] = 5
                                    reduced_plan = self.controller.quartermaster_capacity_tick(reason="temporary_downshift")
                                    reduced_snapshot = self.controller.quartermaster_capacity_reconcile(config, plan=reduced_plan, force=True)
                                    self.assertEqual(reduced_plan["lane_targets"]["core_booster"], 5)
                                    self.assertEqual(reduced_snapshot["over_target_by_lane"]["core_booster"], 10)

                                    drain = self.controller.quartermaster_capacity_drain(config, plan=reduced_plan)
                                    self.assertEqual(drain["cancelled_count"], 10)
                                    await asyncio.wait_for(drain_complete.wait(), timeout=2.0)
                                    self.controller.prune_finished_tasks()

                                    await wait_for_active_count(5)
                                    for package_id in list(active_packages):
                                        package_finish_events[package_id].set()
                                    await asyncio.gather(*list(self.controller.state.tasks.values()))
                                    self.controller.prune_finished_tasks()

                                    wave_counts: list[int] = []
                                    while True:
                                        _plan, _snapshot, launched = dispatch_pass()
                                        if not launched:
                                            break
                                        wave_counts.append(len(launched))
                                        await wait_for_active_count(len(launched))
                                        for package_id in list(active_packages):
                                            package_finish_events[package_id].set()
                                        await asyncio.gather(*list(self.controller.state.tasks.values()))
                                        self.controller.prune_finished_tasks()

                self.controller.state.controller_loop = None
                self.assertEqual(wave_counts, [5, 5, 5])

            asyncio.run(run_flow())

            with self.controller.db() as conn:
                package_rows = conn.execute(
                    "SELECT package_id, status, runtime_state FROM work_packages ORDER BY package_id"
                ).fetchall()

            self.assertEqual(len(started), 30)
            self.assertEqual(len(drained), 10)
            self.assertEqual(len(completed), 20)
            self.assertTrue(all(str(row["status"]) == "complete" for row in package_rows))
            self.assertTrue(all(str(row["runtime_state"]) == "idle" for row in package_rows))


if __name__ == "__main__":
    unittest.main()
