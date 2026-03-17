from __future__ import annotations

import importlib.util
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

    def test_telemetry_question_stays_easy_and_marks_live_status_reason(self) -> None:
        self.write_config({})

        routed = self.route_module._route(["how", "much", "1min", "credits", "are", "left", "right", "now"])

        self.assertEqual(routed["lane"], "easy")
        self.assertEqual(routed["submode"], "mcp")
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

    def test_groundwork_keywords_route_to_groundwork_lane(self) -> None:
        self.write_config(
            {
                "lanes": {
                    "groundwork": {
                        "runtime_model": "ea-groundwork",
                        "provider_hint_order": ["gemini_vortex", "chatplayground"],
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
