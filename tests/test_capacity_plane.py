from __future__ import annotations

import datetime as dt
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/admin/capacity_plane.py")


def load_capacity_plane_module():
    spec = importlib.util.spec_from_file_location("test_capacity_plane_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapacityPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capacity_plane = load_capacity_plane_module()

    def test_load_capacity_plane_configs_reads_split_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "quartermaster.yaml").write_text("quartermaster:\n  mode: observe_only\n", encoding="utf-8")
            (root / "booster_pools.yaml").write_text("booster_pools:\n  core_booster:\n    worker_lane: core_booster\n", encoding="utf-8")
            (root / "review_fabric.yaml").write_text("review_fabric:\n  default:\n    shards:\n      lane: review_shard\n", encoding="utf-8")
            (root / "audit_fabric.yaml").write_text("audit_fabric:\n  default:\n    lane: audit_shard\n", encoding="utf-8")

            payload = self.capacity_plane.load_capacity_plane_configs(root)

            self.assertEqual(payload["quartermaster"]["mode"], "observe_only")
            self.assertEqual(payload["booster_pools"]["core_booster"]["worker_lane"], "core_booster")
            self.assertEqual(payload["review_fabric"]["default"]["shards"]["lane"], "review_shard")
            self.assertEqual(payload["audit_fabric"]["default"]["lane"], "audit_shard")

    def test_build_capacity_plan_respects_credit_review_and_project_caps(self) -> None:
        capacity_configs = {
            "quartermaster": {
                "contract_name": "fleet.capacity_plan",
                "contract_version": "2026-03-22",
                "mode": "observe_only",
                "credit": {
                    "reserve_buffer_hours": 6,
                    "minimum_headroom_hours": 4,
                    "cycle_reserve_percent": 8,
                },
            },
            "booster_pools": {
                "core_booster": {
                    "worker_lane": "core_booster",
                    "authority_lane": "core_authority",
                    "rescue_lane": "core_rescue",
                    "dispatch_classes": ["multi_file_impl"],
                }
            },
            "review_fabric": {
                "default": {
                    "shards": {
                        "lane": "review_shard",
                        "service_floor": 1,
                        "max_queue_depth_per_active_reviewer": 2,
                    }
                }
            },
            "audit_fabric": {
                "default": {
                    "lane": "audit_shard",
                    "target_parallelism": 2,
                    "service_floor": 1,
                    "debt_backpressure": {
                        "open_incidents_yellow": 8,
                        "open_incidents_red": 16,
                    },
                }
            },
        }
        status = {
            "generated_at": "2026-03-22T10:00:00Z",
            "config": {
                "policies": {
                    "capacity_plane": {
                        "plane_caps": {
                            "global_booster_cap": 8,
                            "core_authority_cap": 1,
                            "core_rescue_cap": 1,
                            "review_shard_cap": 4,
                            "audit_shard_cap": 2,
                        }
                    }
                },
                "projects": [
                    {
                        "id": "core",
                        "booster_pool_contract": {
                            "pool": "core_booster",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 3,
                        },
                    }
                ],
            },
            "projects": [
                {
                    "id": "core",
                    "runtime_status": "dispatch_pending",
                    "allowed_lanes": ["core_booster"],
                    "task_allow_credit_burn": True,
                    "selected_lane": "core_booster",
                }
            ],
            "cockpit": {
                "summary": {
                    "active_review_workers": 1,
                    "queued_jury_jobs": 2,
                    "blocked_on_jury_workers": 1,
                    "open_incidents": 9,
                    "blocked_unresolved_incidents": 1,
                    "coverage_pressure_projects": 0,
                },
                "mission_board": {
                    "booster_runtime_card": {
                        "active_onemin_codexers": 2,
                        "active_boosters": 2,
                    },
                    "provider_credit_card": {
                        "slot_count_with_billing_snapshot": 2,
                        "slot_count_with_member_reconciliation": 2,
                        "hours_until_next_topup": 10,
                        "hours_remaining_at_current_pace_no_topup": 15,
                        "days_remaining_including_next_topup_at_7d_avg": 5,
                    },
                },
                "capacity_forecast": {
                    "lanes": [
                        {
                            "lane": "core_booster",
                            "ready_slots": 3,
                            "configured_slots": 4,
                            "degraded_slots": 1,
                        }
                    ]
                },
                "jury_telemetry": {
                    "queued_jury_jobs": 2,
                    "blocked_total_workers": 1,
                    "participant_burst": {"premium_queue_depth": 1},
                },
                "runway": {},
            },
        }

        payload = self.capacity_plane.build_capacity_plan_payload(
            status,
            capacity_configs=capacity_configs,
            now=dt.datetime(2026, 3, 22, 10, 0, tzinfo=dt.timezone.utc),
        )

        self.assertEqual(payload["effective_booster_cap"], 1)
        self.assertEqual(payload["limiting_cap"], "credit_cap_until_cycle_end")
        self.assertEqual(payload["lane_targets"]["core_authority"], 1)
        self.assertEqual(payload["lane_targets"]["core_booster"], 1)
        self.assertEqual(payload["active_project_contracts"][0]["project_id"], "core")
        self.assertEqual(payload["caps"]["project_safety_cap"]["value"], 3)
        finding_types = {item["type"] for item in payload["typed_findings"]}
        self.assertIn("credit_runway_risk", finding_types)
        self.assertIn("review_backpressure", finding_types)
        self.assertIn("audit_debt", finding_types)
        self.assertIn("slot_probe_stale", finding_types)
        self.assertIn("contract_drift", finding_types)

    def test_build_capacity_plan_emits_controller_tick_and_ea_manager_metadata(self) -> None:
        capacity_configs = {
            "quartermaster": {
                "mode": "enforce",
                "driver": "controller_tick",
                "baseline_tick_seconds": 600,
                "event_tick_min_seconds": 90,
                "plan_ttl_seconds": 900,
                "max_scale_up_per_tick": 1,
                "max_scale_down_per_tick": 2,
                "min_worker_dwell_seconds": 900,
                "idle_drain_seconds": 180,
                "telemetry": {
                    "provider": "ea_onemin_manager",
                    "onemin_manager": "ea",
                    "onemin_query_mode": "manager",
                },
                "incidents": {
                    "triggers": ["review_backpressure", "audit_debt", "slot_probe_stale"],
                },
            },
            "booster_pools": {},
            "review_fabric": {},
            "audit_fabric": {},
        }
        status = {
            "config": {"policies": {"capacity_plane": {"plane_caps": {"core_authority_cap": 1}}}},
            "projects": [],
            "cockpit": {
                "summary": {},
                "mission_board": {"provider_credit_card": {}},
                "capacity_forecast": {},
                "jury_telemetry": {},
                "runway": {},
            },
        }

        payload = self.capacity_plane.build_capacity_plan_payload(status, capacity_configs=capacity_configs)

        self.assertEqual(payload["runtime_authority"]["dispatcher"], "fleet-controller")
        self.assertEqual(payload["runtime_authority"]["capacity_compiler"], "fleet-quartermaster")
        self.assertEqual(payload["controller_tick"]["driver"], "controller_tick")
        self.assertEqual(payload["controller_tick"]["baseline_tick_seconds"], 600)
        self.assertEqual(payload["controller_tick"]["event_tick_min_seconds"], 90)
        self.assertIn("audit_debt", payload["controller_tick"]["triggers"])
        self.assertEqual(payload["telemetry_sources"]["provider_credit"]["provider"], "ea_onemin_manager")
        self.assertEqual(payload["telemetry_sources"]["provider_credit"]["onemin_manager"], "ea")

    def test_build_capacity_plan_uses_work_package_scope_cap(self) -> None:
        capacity_configs = {
            "quartermaster": {"mode": "enforce"},
            "booster_pools": {
                "core_booster": {
                    "worker_lane": "core_booster",
                    "authority_lane": "core_authority",
                    "rescue_lane": "core_rescue",
                }
            },
            "review_fabric": {"default": {"shards": {"service_floor": 2, "max_queue_depth_per_active_reviewer": 8}}},
            "audit_fabric": {"default": {"service_floor": 1, "target_parallelism": 20, "debt_backpressure": {"open_incidents_yellow": 8, "open_incidents_red": 16}}},
        }
        status = {
            "config": {
                "policies": {
                    "capacity_plane": {
                        "plane_caps": {
                            "global_booster_cap": 20,
                            "core_authority_cap": 1,
                            "core_rescue_cap": 1,
                            "review_shard_cap": 20,
                            "audit_shard_cap": 20,
                        }
                    }
                },
                "projects": [
                    {
                        "id": "fleet",
                        "booster_pool_contract": {
                            "pool": "core_booster",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 15,
                        },
                    }
                ],
            },
            "projects": [
                {
                    "id": "fleet",
                    "runtime_status": "dispatch_pending",
                    "allowed_lanes": ["core_booster"],
                    "task_allow_credit_burn": True,
                    "selected_lane": "core_booster",
                }
            ],
            "work_packages": {
                "ready_packages": 20,
                "ready_scope_cap": 15,
                "scope_cap": 15,
                "active_packages": 0,
            },
            "cockpit": {
                "summary": {"active_review_workers": 2, "queued_jury_jobs": 0, "open_incidents": 0},
                "mission_board": {
                    "booster_runtime_card": {"active_onemin_codexers": 0, "active_boosters": 0},
                    "provider_credit_card": {
                        "slot_count_with_billing_snapshot": 20,
                        "slot_count_with_member_reconciliation": 20,
                        "hours_until_next_topup": 1,
                        "hours_remaining_at_current_pace_no_topup": 100,
                        "days_remaining_including_next_topup_at_7d_avg": 100,
                    },
                },
                "capacity_forecast": {
                    "lanes": [
                        {"lane": "core_booster", "ready_slots": 20, "configured_slots": 20, "degraded_slots": 0},
                    ]
                },
                "jury_telemetry": {"participant_burst": {"premium_queue_depth": 0}},
                "runway": {},
            },
        }

        payload = self.capacity_plane.build_capacity_plan_payload(status, capacity_configs=capacity_configs)

        self.assertEqual(payload["caps"]["useful_work_cap"]["value"], 20)
        self.assertEqual(payload["caps"]["scope_cap"]["value"], 15)
        self.assertEqual(payload["effective_booster_cap"], 15)
        self.assertEqual(payload["lane_targets"]["core_booster"], 15)
        self.assertEqual(payload["limiting_cap"], "scope_cap")
        self.assertIn("scope_contention", {item["type"] for item in payload["typed_findings"]})

    def test_build_capacity_plan_uses_observed_review_shard_supply_not_service_floor(self) -> None:
        capacity_configs = {
            "quartermaster": {"mode": "enforce"},
            "booster_pools": {
                "core_booster": {
                    "worker_lane": "core_booster",
                    "authority_lane": "core_authority",
                    "rescue_lane": "core_rescue",
                    "lease": {
                        "require_credit_lease": True,
                        "require_work_lease": True,
                        "require_scope_lease": True,
                    },
                }
            },
            "review_fabric": {
                "default": {
                    "shards": {
                        "lane": "review_shard",
                        "service_floor": 10,
                        "target_parallelism": 20,
                        "max_queue_depth_per_active_reviewer": 2,
                    }
                }
            },
            "audit_fabric": {"default": {"service_floor": 1, "target_parallelism": 20}},
        }
        status = {
            "config": {
                "policies": {
                    "capacity_plane": {
                        "plane_caps": {
                            "global_booster_cap": 20,
                            "core_authority_cap": 1,
                            "core_rescue_cap": 1,
                            "review_shard_cap": 20,
                            "audit_shard_cap": 20,
                        }
                    }
                },
                "projects": [
                    {
                        "id": "fleet",
                        "booster_pool_contract": {
                            "pool": "core_booster",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 20,
                        },
                    }
                ],
            },
            "projects": [
                {
                    "id": "fleet",
                    "runtime_status": "dispatch_pending",
                    "allowed_lanes": ["core_booster"],
                    "task_allow_credit_burn": True,
                    "selected_lane": "core_booster",
                }
            ],
            "work_packages": {
                "ready_packages": 20,
                "ready_scope_cap": 20,
                "scope_cap": 20,
                "active_packages": 0,
            },
            "cockpit": {
                "summary": {"active_review_workers": 0, "queued_jury_jobs": 0, "open_incidents": 0},
                "mission_board": {
                    "booster_runtime_card": {"active_onemin_codexers": 0, "active_boosters": 0},
                    "provider_credit_card": {
                        "slot_count_with_billing_snapshot": 20,
                        "slot_count_with_member_reconciliation": 20,
                        "hours_until_next_topup": 1,
                        "hours_remaining_at_current_pace_no_topup": 100,
                        "days_remaining_including_next_topup_at_7d_avg": 100,
                    },
                },
                "capacity_forecast": {
                    "lanes": [
                        {"lane": "core_booster", "ready_slots": 20, "configured_slots": 20, "degraded_slots": 0},
                        {"lane": "review_shard", "ready_slots": 1, "configured_slots": 1, "degraded_slots": 0},
                    ]
                },
                "jury_telemetry": {"participant_burst": {"premium_queue_depth": 0}},
                "runway": {},
            },
        }

        payload = self.capacity_plane.build_capacity_plan_payload(status, capacity_configs=capacity_configs)

        self.assertEqual(payload["caps"]["review_cap"]["value"], 2)
        self.assertEqual(payload["effective_booster_cap"], 2)
        self.assertEqual(payload["booster_pools"][0]["lease"]["require_scope_lease"], True)
        self.assertEqual(payload["limiting_cap"], "review_cap")

    def test_build_capacity_plan_does_not_fabricate_review_capacity_from_configured_slots(self) -> None:
        capacity_configs = {
            "quartermaster": {"mode": "enforce"},
            "booster_pools": {
                "core_booster": {
                    "worker_lane": "core_booster",
                    "authority_lane": "core_authority",
                    "rescue_lane": "core_rescue",
                    "lease": {
                        "require_credit_lease": True,
                        "require_work_lease": True,
                        "require_scope_lease": True,
                    },
                }
            },
            "review_fabric": {
                "default": {
                    "shards": {
                        "lane": "review_shard",
                        "service_floor": 10,
                        "target_parallelism": 20,
                        "max_queue_depth_per_active_reviewer": 2,
                    }
                }
            },
            "audit_fabric": {"default": {"service_floor": 1, "target_parallelism": 20}},
        }
        status = {
            "config": {
                "policies": {
                    "capacity_plane": {
                        "plane_caps": {
                            "global_booster_cap": 20,
                            "core_authority_cap": 1,
                            "core_rescue_cap": 1,
                            "review_shard_cap": 20,
                            "audit_shard_cap": 20,
                        }
                    }
                },
                "projects": [
                    {
                        "id": "fleet",
                        "booster_pool_contract": {
                            "pool": "core_booster",
                            "authority_lane": "core_authority",
                            "booster_lane": "core_booster",
                            "rescue_lane": "core_rescue",
                            "project_safety_cap": 20,
                        },
                    }
                ],
            },
            "projects": [
                {
                    "id": "fleet",
                    "runtime_status": "dispatch_pending",
                    "allowed_lanes": ["core_booster"],
                    "task_allow_credit_burn": True,
                    "selected_lane": "core_booster",
                }
            ],
            "work_packages": {
                "ready_packages": 20,
                "ready_scope_cap": 20,
                "scope_cap": 20,
                "active_packages": 0,
            },
            "cockpit": {
                "summary": {"active_review_workers": 0, "queued_jury_jobs": 0, "open_incidents": 0},
                "mission_board": {
                    "booster_runtime_card": {"active_onemin_codexers": 0, "active_boosters": 0},
                    "provider_credit_card": {
                        "slot_count_with_billing_snapshot": 20,
                        "slot_count_with_member_reconciliation": 20,
                        "hours_until_next_topup": 1,
                        "hours_remaining_at_current_pace_no_topup": 100,
                        "days_remaining_including_next_topup_at_7d_avg": 100,
                    },
                },
                "capacity_forecast": {
                    "lanes": [
                        {"lane": "core_booster", "ready_slots": 20, "configured_slots": 20, "degraded_slots": 0},
                        {"lane": "review_shard", "ready_slots": 0, "configured_slots": 10, "degraded_slots": 0},
                    ]
                },
                "jury_telemetry": {"participant_burst": {"premium_queue_depth": 0}},
                "runway": {},
            },
        }

        payload = self.capacity_plane.build_capacity_plan_payload(status, capacity_configs=capacity_configs)

        self.assertEqual(payload["caps"]["review_cap"]["value"], 0)
        self.assertEqual(payload["lane_targets"]["review_shard"], 0)
        self.assertEqual(payload["effective_booster_cap"], 0)
        self.assertEqual(payload["limiting_cap"], "review_cap")
