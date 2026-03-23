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
