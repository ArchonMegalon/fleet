from __future__ import annotations

import io
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


MODULE_PATH = Path("/docker/fleet/scripts/codexea_route.py")


def load_route_module():
    spec = importlib.util.spec_from_file_location("test_codexea_route_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexEaRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.route_module = load_route_module()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.config_path = Path(self.tempdir.name) / "routing.yaml"
        self.route_module.ROUTING_CONFIG_PATH = self.config_path

    def write_config(self, data: dict) -> None:
        self.config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    def test_custom_bounded_fix_keyword_blocks_jury_escalation(self) -> None:
        self.write_config(
            {
                "spider": {
                    "bounded_fix_keywords": ["solder"],
                },
                "lanes": {
                    "repair": {
                        "runtime_model": "ea-coder-fast",
                        "provider_hint_order": ["magixai"],
                    }
                },
            }
        )

        routed = self.route_module._route(["audit", "solder", "the", "queue", "worker"])

        self.assertEqual(routed["lane"], "repair")
        self.assertEqual(routed["task_class"], "bounded_fix")
        self.assertEqual(routed["submode"], "responses_fast")

    def test_draft_uses_configured_reasoning_effort(self) -> None:
        self.write_config(
            {
                "spider": {
                    "tier_preferences": {
                        "draft": {"reasoning_effort": "medium"},
                    }
                }
            }
        )

        routed = self.route_module._route(["summarize", "backlog", "packet"])

        self.assertEqual(routed["lane"], "easy")
        self.assertEqual(routed["task_class"], "draft")
        self.assertEqual(routed["reasoning_effort"], "medium")

    def test_infer_interactive_default_locks_easy_lane(self) -> None:
        self.write_config(
            {
                "lanes": {
                    "easy": {
                        "runtime_model": "ea-gemini-flash",
                        "provider_hint_order": ["gemini_vortex"],
                    }
                }
            }
        )

        routed = self.route_module._route([])

        self.assertEqual(routed["lane"], "easy")
        self.assertEqual(routed["submode"], "responses_easy")
        self.assertEqual(routed["reason"], "interactive_easy_locked")
        self.assertEqual(routed["runtime_model"], "ea-gemini-flash")

    def test_telemetry_question_stays_easy_and_marks_live_status_reason(self) -> None:
        self.write_config({})

        routed = self.route_module._route(["how", "much", "1min", "credits", "are", "left", "right", "now"])

        self.assertEqual(routed["lane"], "easy")
        self.assertEqual(routed["submode"], "responses_easy")
        self.assertEqual(routed["reason"], "telemetry_live_status")

    def test_status_capacity_prompt_routes_as_telemetry_not_inspect(self) -> None:
        self.write_config({})

        routed = self.route_module._route(["status", "for", "core", "lane", "capacity"])

        self.assertEqual(routed["lane"], "easy")
        self.assertEqual(routed["task_class"], "telemetry")
        self.assertEqual(routed["reason"], "telemetry_live_status")

    def test_telemetry_response_refreshes_live_status_and_formats_percent(self) -> None:
        self.write_config({})

        payload = {
            "providers_summary": [
                {
                    "provider_name": "1min",
                    "account_name": "acct-core",
                    "used_percent": 32.0,
                    "free_credits": 680000,
                    "hours_remaining_at_current_pace": 17.25,
                    "basis": "measured",
                    "state": "ready",
                }
            ]
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload) as mocked_status:
            response = self.route_module._telemetry_response("Credits from core lane on 1minai in %?")

        self.assertTrue(response["matched"])
        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertIn("Live core/1min status", response["message"])
        self.assertIn("68.0% remaining", response["message"])
        self.assertIn("680,000 free credits", response["message"])
        self.assertIn("ETA 17.2h", response["message"])
        self.assertEqual(mocked_status.call_args.kwargs["refresh"], True)

    def test_telemetry_response_reports_unknown_percent_exactly(self) -> None:
        self.write_config({})

        payload = {
            "providers_summary": [
                {
                    "provider_name": "1min",
                    "account_name": "acct-core",
                    "basis": "unknown_unprobed",
                    "state": "unknown",
                    "free_credits": None,
                }
            ]
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._telemetry_response("current 1min credits percent")

        self.assertTrue(response["matched"])
        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertIn("remaining percent is unknown right now", response["message"])
        self.assertIn("basis unknown_unprobed", response["message"])
        self.assertIn("state unknown", response["message"])

    def test_telemetry_response_uses_profiles_fallback_when_status_is_unavailable(self) -> None:
        self.write_config({})

        profiles_payload = {
            "provider_health": {
                "providers": {
                    "onemin": {
                        "state": "ready",
                        "remaining_percent_of_max": 61.0,
                        "estimated_hours_remaining_at_current_pace": 9.5,
                    }
                }
            }
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=None):
            with mock.patch.object(self.route_module, "_ea_profiles_payload", return_value=profiles_payload):
                response = self.route_module._telemetry_response("current core lane capacity")

        self.assertTrue(response["matched"])
        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertIn("profiles fallback", response["message"])
        self.assertIn("61.0% remaining", response["message"])

    def test_onemin_aggregate_response_sums_live_rows_and_burn_windows(self) -> None:
        self.write_config({})

        payload = {
            "status_basis": "mixed_live_probe",
            "providers_summary": [
                {
                    "provider_name": "1min",
                    "account_name": "acct-a",
                    "max_credits": 1_000_000,
                    "free_credits": 400_000,
                    "basis": "actual_ui_probe",
                    "state": "ready",
                },
                {
                    "provider_name": "1min",
                    "account_name": "acct-b",
                    "max_credits": 2_000_000,
                    "free_credits": 600_000,
                    "basis": "actual_ui_probe",
                    "state": "degraded",
                },
                {
                    "provider_name": "BrowserAct",
                    "account_name": "browser",
                    "max_credits": 9_999_999,
                    "free_credits": 9_999_999,
                    "basis": "ignore_me",
                    "state": "ready",
                },
            ],
            "fleet_burn": {
                "1h": {"provider_credits": {"onemin": 100_000}},
                "7d": {"provider_credits": {"onemin": 7_000_000}},
            },
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._onemin_aggregate_response()

        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        data = response["data"]
        self.assertEqual(data["slot_count"], 2)
        self.assertEqual(data["slot_count_with_balance"], 2)
        self.assertEqual(data["sum_max_credits"], 3_000_000)
        self.assertEqual(data["sum_free_credits"], 1_000_000)
        self.assertAlmostEqual(data["remaining_percent_total"], 33.3333, places=3)
        self.assertAlmostEqual(data["current_pace_burn_credits_per_hour"], 100_000.0, places=3)
        self.assertAlmostEqual(data["hours_remaining_at_current_pace"], 10.0, places=3)
        self.assertAlmostEqual(data["avg_daily_burn_credits_7d"], 1_000_000.0, places=3)
        self.assertAlmostEqual(data["days_remaining_at_7d_avg_burn"], 1.0, places=3)
        self.assertEqual(data["basis_summary"], "actual_ui_probe x2")
        self.assertIn("ready", data["state_summary"])
        self.assertIn("degraded", data["state_summary"])
        self.assertIn("Top-ups excluded: yes", response["message"])

    def test_onemin_aggregate_response_uses_precomputed_block_when_present(self) -> None:
        self.write_config({})

        payload = {
            "onemin_aggregate": {
                "slot_count": 31,
                "slot_count_with_balance": 16,
                "sum_max_credits": 151_300_000,
                "sum_free_credits": 29_632_001,
                "remaining_percent_total": 19.59,
                "hours_remaining_at_current_pace": 183.4,
                "days_remaining_at_7d_avg_burn": 6.2,
                "balance_basis_summary": "actual_ui_probe,observed_error,unknown_unprobed",
                "owner_mapped_slot_count": 2,
                "probe_result_counts": {"ok": 1, "revoked": 1},
                "last_probe_at": 1_742_208_000.0,
                "incoming_topups_excluded": True,
            }
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._onemin_aggregate_response()

        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        data = response["data"]
        self.assertEqual(data["slot_count"], 31)
        self.assertEqual(data["slot_count_with_balance"], 16)
        self.assertEqual(data["sum_max_credits"], 151_300_000)
        self.assertEqual(data["sum_free_credits"], 29_632_001)
        self.assertAlmostEqual(data["remaining_percent_total"], 19.59, places=2)
        self.assertAlmostEqual(data["hours_remaining_at_current_pace"], 183.4, places=2)
        self.assertAlmostEqual(data["days_remaining_at_7d_avg_burn"], 6.2, places=2)
        self.assertEqual(data["basis_summary"], "actual_ui_probe,observed_error,unknown_unprobed")
        self.assertEqual(data["owner_mapped_slot_count"], 2)
        self.assertEqual(data["probe_result_counts"], {"ok": 1, "revoked": 1})
        self.assertTrue(data["used_precomputed_aggregate"])
        self.assertIn("Owner mapping: 2 slots mapped", response["message"])
        self.assertIn("Latest explicit probes: ok 1 | revoked 1", response["message"])
        self.assertIn("Last probe at: 2025-03-17T10:40:00Z", response["message"])

    def test_onemin_aggregate_response_surfaces_billing_topup_forecast(self) -> None:
        self.write_config({})

        payload = {
            "onemin_aggregate": {
                "slot_count": 2,
                "slot_count_with_balance": 2,
                "sum_max_credits": 2_000_000,
                "sum_free_credits": 1_000_000,
                "remaining_percent_total": 50.0,
                "hours_remaining_at_current_pace": 20.0,
                "days_remaining_at_7d_avg_burn": 5.0,
                "balance_basis_summary": "actual_billing_usage_page x2",
                "incoming_topups_excluded": True,
            },
            "onemin_billing_aggregate": {
                "slot_count": 2,
                "slot_count_with_billing_snapshot": 2,
                "slot_count_with_member_reconciliation": 1,
                "sum_max_credits": 2_000_000,
                "sum_free_credits": 1_000_000,
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
            },
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._onemin_aggregate_response()

        self.assertTrue(response["ok"])
        data = response["data"]
        self.assertEqual(data["slot_count_with_billing_snapshot"], 2)
        self.assertEqual(data["slot_count_with_member_reconciliation"], 1)
        self.assertEqual(data["next_topup_at"], "2026-03-31T00:00:00Z")
        self.assertEqual(data["topup_amount"], 2_000_000.0)
        self.assertAlmostEqual(data["hours_until_next_topup"], 320.5, places=2)
        self.assertAlmostEqual(data["hours_remaining_at_current_pace_no_topup"], 38.8, places=2)
        self.assertAlmostEqual(data["hours_remaining_including_next_topup_at_current_pace"], 510.2, places=2)
        self.assertAlmostEqual(data["days_remaining_including_next_topup_at_7d_avg"], 167.0, places=2)
        self.assertFalse(data["depletes_before_next_topup"])
        self.assertIn("2 with billing snapshots", response["message"])
        self.assertIn("Next top-up:", response["message"])
        self.assertIn("- Amount: 2,000,000", response["message"])
        self.assertIn("- Including next top-up, 7d average: 167.0d", response["message"])
        self.assertIn("Member reconciliation: 1 slot with member snapshots", response["message"])

    def test_onemin_aggregate_response_surfaces_probe_gap_and_slot_flags(self) -> None:
        self.write_config({})

        payload = {
            "providers_summary": [
                {
                    "provider_name": "1min",
                    "account_name": "slot-a",
                    "max_credits": 1_000_000,
                    "free_credits": 800_000,
                    "basis": "actual_ui_probe",
                    "state": "ready",
                },
                {
                    "provider_name": "1min",
                    "account_name": "slot-b",
                    "basis": "unknown_unprobed",
                    "state": "unknown",
                },
                {
                    "provider_name": "1min",
                    "account_name": "slot-c",
                    "basis": "observed_error",
                    "state": "degraded",
                    "detail": "api key has been deleted",
                    "quarantine_until": "2026-03-17T10:00:00Z",
                },
            ]
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._onemin_aggregate_response(include_slots=True)

        self.assertTrue(response["ok"])
        data = response["data"]
        self.assertEqual(data["unknown_unprobed_slot_count"], 1)
        self.assertEqual(data["observed_error_slot_count"], 1)
        self.assertEqual(data["revoked_slot_count"], 1)
        self.assertEqual(data["quarantined_slot_count"], 1)
        self.assertEqual(data["basis_counts"]["unknown_unprobed"], 1)
        self.assertEqual(data["state_counts"]["degraded"], 1)
        self.assertEqual(data["slots"][2]["account_name"], "slot-c")
        self.assertTrue(data["slots"][2]["revoked_like"])
        self.assertIn("Observed slot flags: unknown/unprobed 1 | observed_error 1 | revoked-like 1 | quarantined 1", response["message"])
        self.assertIn("Probe note: unknown_unprobed means no live evidence yet", response["message"])
        self.assertIn("Slot details:", response["message"])
        self.assertIn("- slot-c: degraded | observed_error | revoked-like | quarantine 2026-03-17T10:00:00Z | api key has been deleted", response["message"])

    def test_onemin_aggregate_response_can_probe_all_before_rendering(self) -> None:
        self.write_config({})

        payload = {
            "onemin_aggregate": {
                "slot_count": 2,
                "slot_count_with_known_balance": 1,
                "sum_max_credits": 1000,
                "sum_free_credits": 500,
                "remaining_percent_total": 50.0,
                "basis_summary": "observed_error,unknown_unprobed",
                "probe_result_counts": {"ok": 1, "revoked": 1},
                "owner_mapped_slot_count": 1,
                "last_probe_at": 1_742_208_000.0,
                "incoming_topups_excluded": True,
            }
        }
        probe_payload = {
            "provider_key": "onemin",
            "slot_count": 2,
            "configured_slot_count": 2,
            "probe_model": "gpt-4.1",
            "owner_mapped_slots": 1,
            "result_counts": {"ok": 1, "revoked": 1},
            "last_probe_at": 1_742_208_000.0,
            "note": "Probe-all sends one live low-volume request to each selected 1min slot and updates slot evidence.",
        }

        with mock.patch.object(self.route_module, "_ea_onemin_probe_payload", return_value=probe_payload):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
                response = self.route_module._onemin_aggregate_response(probe_all=True)

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["probe"]["result_counts"], {"ok": 1, "revoked": 1})
        self.assertIn("1min probe-all", response["message"])
        self.assertIn("Results: ok 1 | revoked 1", response["message"])
        self.assertIn("1min aggregate", response["message"])

    def test_onemin_probe_payload_uses_extended_timeout(self) -> None:
        with mock.patch.object(self.route_module, "_ea_http_payload", return_value={"ok": True}) as mocked_http:
            self.route_module._ea_onemin_probe_payload(include_reserve=False)

        self.assertEqual(mocked_http.call_args.kwargs["timeout_seconds"], 180.0)
        self.assertEqual(mocked_http.call_args.kwargs["payload"], {"include_reserve": False})

    def test_onemin_aggregate_response_surfaces_probe_timeout_detail(self) -> None:
        self.write_config({})
        self.route_module._LAST_EA_HTTP_ERROR = "timed out after 180s"

        with mock.patch.object(self.route_module, "_ea_onemin_probe_payload", return_value=None):
            response = self.route_module._onemin_aggregate_response(probe_all=True)

        self.assertFalse(response["ok"])
        self.assertIn("timed out after 180s", response["message"])

    def test_onemin_aggregate_cli_accepts_billing_flag(self) -> None:
        self.write_config({})

        payload = {
            "onemin_aggregate": {
                "slot_count": 1,
                "slot_count_with_known_balance": 1,
                "sum_max_credits": 100,
                "sum_free_credits": 50,
                "remaining_percent_total": 50.0,
                "incoming_topups_excluded": True,
            },
            "onemin_billing_aggregate": {
                "slot_count_with_billing_snapshot": 1,
                "next_topup_at": "2026-03-31T00:00:00Z",
            },
        }
        billing_refresh = {
            "connector_binding_count": 1,
            "billing_refresh_count": 1,
            "member_reconciliation_count": 1,
            "selected_binding_ids": ["binding-browseract-1"],
        }

        with mock.patch.object(self.route_module, "_ea_onemin_billing_refresh_payload", return_value=billing_refresh) as refresh_mock:
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
                with io.StringIO() as stream, mock.patch("sys.stdout", stream):
                    rc = self.route_module.main(["--onemin-aggregate", "--billing"])
                    rendered = stream.getvalue()

        self.assertEqual(rc, 0)
        refresh_mock.assert_called_once_with(include_members=True, capture_raw_text=True)
        self.assertIn("1min billing refresh", rendered)
        self.assertIn("1min aggregate", rendered)
        self.assertIn("Next top-up:", rendered)

    def test_onemin_aggregate_billing_refresh_fallback_keeps_cached_status(self) -> None:
        self.write_config({})

        payload = {
            "onemin_aggregate": {
                "slot_count": 1,
                "slot_count_with_known_balance": 1,
                "sum_max_credits": 100,
                "sum_free_credits": 50,
                "remaining_percent_total": 50.0,
                "incoming_topups_excluded": True,
            }
        }

        with mock.patch.object(self.route_module, "_ea_onemin_billing_refresh_payload", return_value=None):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
                response = self.route_module._onemin_aggregate_response(billing=True)

        self.assertTrue(response["ok"])
        self.assertIn("1min billing refresh", response["message"])
        self.assertIn("showing cached billing state", response["message"])

    def test_onemin_aggregate_json_mode_emits_machine_readable_output(self) -> None:
        self.write_config({})

        payload = {
            "providers_summary": [
                {
                    "provider_name": "1min",
                    "account_name": "acct-a",
                    "max_credits": 100,
                    "free_credits": 25,
                    "basis": "measured",
                    "state": "ready",
                }
            ],
            "fleet_burn": {
                "1h": {"provider_credits": {"onemin": 5}},
                "7d": {"provider_credits": {"onemin": 35}},
            },
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            with io.StringIO() as stream, mock.patch("sys.stdout", stream):
                rc = self.route_module.main(["--onemin-aggregate", "--json"])
                rendered = stream.getvalue()

        self.assertEqual(rc, 0)
        data = json.loads(rendered)
        self.assertTrue(data["ok"])
        self.assertEqual(data["provider"], "onemin")
        self.assertEqual(data["sum_free_credits"], 25)
        self.assertAlmostEqual(data["days_left_at_7d_avg_burn"], 5.0, places=3)
        self.assertEqual(data["slots"][0]["account_name"], "acct-a")

    def test_onemin_aggregate_slots_flag_renders_slot_rows(self) -> None:
        self.write_config({})

        payload = {
            "providers_summary": [
                {
                    "provider_name": "1min",
                    "account_name": "acct-a",
                    "max_credits": 100,
                    "free_credits": 25,
                    "basis": "measured",
                    "state": "ready",
                }
            ]
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            with io.StringIO() as stream, mock.patch("sys.stdout", stream):
                rc = self.route_module.main(["--onemin-aggregate", "--slots"])
                rendered = stream.getvalue()

        self.assertEqual(rc, 0)
        self.assertIn("Slot details:", rendered)
        self.assertIn("- acct-a: ready | measured | 25 free / 100 max", rendered)

    def test_onemin_aggregate_slots_flag_renders_owner_labels(self) -> None:
        self.write_config({})

        payload = {
            "onemin_aggregate": {
                "slot_count": 1,
                "slot_count_with_known_balance": 1,
                "sum_max_credits": 100,
                "sum_free_credits": 25,
                "slots": [
                    {
                        "slot": "fallback_12",
                        "account_name": "ONEMIN_AI_API_KEY_FALLBACK_12",
                        "owner_email": "owner@example.com",
                        "state": "ready",
                        "basis": "max_minus_observed_usage",
                        "free_credits": 25,
                        "max_credits": 100,
                    }
                ],
            }
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._onemin_aggregate_response(include_slots=True)

        self.assertTrue(response["ok"])
        self.assertIn("owner owner@example.com", response["message"])

    def test_groundwork_keywords_route_to_groundwork_lane(self) -> None:
        self.write_config(
            {
                "lanes": {
                    "groundwork": {
                        "runtime_model": "ea-groundwork-gemini",
                        "provider_hint_order": ["gemini_vortex"],
                    }
                }
            }
        )

        routed = self.route_module._route(["architecture", "tradeoff", "review"])

        self.assertEqual(routed["lane"], "groundwork")
        self.assertEqual(routed["submode"], "responses_groundwork")
        self.assertEqual(routed["reason"], "complex_nonurgent_analysis")

    def test_high_risk_protected_branch_escalates_to_core(self) -> None:
        self.write_config({})

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value={"providers_summary": [{"provider_name": "1min", "state": "ready", "basis": "measured", "free_credits": 500000}]}):
            routed = self.route_module._route(["protected", "branch", "migration", "fix"])

        self.assertEqual(routed["lane"], "core")
        self.assertEqual(routed["submode"], "responses_hard")
        self.assertEqual(routed["reason"], "high_risk_scope")

    def test_unknown_onemin_capacity_blocks_automatic_core(self) -> None:
        self.write_config({})

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value={"providers_summary": [{"provider_name": "1min", "state": "unknown", "basis": "unknown_unprobed", "free_credits": None}]}):
            routed = self.route_module._route(["auth", "migration", "fix"])

        self.assertEqual(routed["lane"], "repair")
        self.assertEqual(routed["submode"], "responses_fast")
        self.assertEqual(routed["reason"], "core_blocked_unknown_capacity")

    def test_low_onemin_capacity_blocks_automatic_core(self) -> None:
        self.write_config({})

        with mock.patch.dict(os.environ, {"CODEXEA_CORE_MIN_ONEMIN_CREDITS": "100000"}, clear=False):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value={"providers_summary": [{"provider_name": "1min", "state": "ready", "basis": "measured", "free_credits": 5000}]}):
                routed = self.route_module._route(["auth", "migration", "fix"])

        self.assertEqual(routed["lane"], "repair")
        self.assertEqual(routed["submode"], "responses_fast")
        self.assertEqual(routed["reason"], "core_blocked_low_capacity")


if __name__ == "__main__":
    unittest.main()
