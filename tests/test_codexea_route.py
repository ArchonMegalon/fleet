from __future__ import annotations

import io
import importlib.util
import json
import os
import sqlite3
import datetime as dt
import tempfile
import threading
import sys
import subprocess
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.fleet_db_path = Path(self.tempdir.name) / "fleet.db"
        self.runtime_env_path = Path(self.tempdir.name) / "runtime.ea.env"
        self.env_patcher = mock.patch.dict(
            os.environ,
            {
                "CODEXEA_FLEET_DB_PATH": str(self.fleet_db_path),
                "CODEXEA_RUNTIME_EA_ENV_PATH": str(self.runtime_env_path),
            },
            clear=False,
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)
        self.route_module = load_route_module()
        self.config_path = Path(self.tempdir.name) / "routing.yaml"
        self.route_module.ROUTING_CONFIG_PATH = self.config_path

    def write_config(self, data: dict) -> None:
        self.config_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    def write_runtime_cache(self, cache_key: str, payload: dict, *, fetched_at: str = "2026-03-18T17:43:36Z") -> None:
        with sqlite3.connect(self.fleet_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_caches(
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO runtime_caches(cache_key, payload_json, fetched_at, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    fetched_at=excluded.fetched_at,
                    updated_at=excluded.updated_at
                """,
                (cache_key, json.dumps(payload), fetched_at, fetched_at),
            )

    def write_runtime_env(self, values: dict[str, str]) -> None:
        self.runtime_env_path.write_text(
            "".join(f"{key}={value}\n" for key, value in values.items()),
            encoding="utf-8",
        )

    def _run_route_cli(self, args: list[str], extra_env: dict[str, str] | None = None) -> tuple[int, str, str]:
        env = os.environ.copy()
        env.update(extra_env or {})
        process = subprocess.run(
            [sys.executable, str(MODULE_PATH), *args],
            env=env,
            cwd="/docker/fleet",
            capture_output=True,
            text=True,
            timeout=10,
        )
        return process.returncode, process.stdout, process.stderr

    def mock_http_401(self, *args, **kwargs):
        self.route_module._LAST_EA_HTTP_ERROR = "http_401"
        return None

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

        self.assertEqual(routed["lane"], "easy")
        self.assertEqual(routed["task_class"], "bounded_fix")
        self.assertEqual(routed["submode"], "mcp")

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
        self.assertEqual(routed["submode"], "mcp")
        self.assertEqual(routed["reason"], "telemetry_live_status")

    def test_status_capacity_prompt_routes_as_telemetry_not_inspect(self) -> None:
        self.write_config({})

        routed = self.route_module._route(["status", "for", "core", "lane", "capacity"])

        self.assertEqual(routed["lane"], "easy")
        self.assertEqual(routed["task_class"], "telemetry")
        self.assertEqual(routed["reason"], "telemetry_live_status")

    def test_fleet_eta_and_shards_question_does_not_short_circuit_to_telemetry(self) -> None:
        self.write_config({})

        routed = self.route_module._route(["eta", "of", "the", "fleet?", "is", "it", "running?", "the", "shards?"])

        self.assertNotEqual(routed["task_class"], "telemetry")
        self.assertNotEqual(routed["reason"], "telemetry_live_status")

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

    def test_telemetry_response_reports_live_fleet_runtime_status(self) -> None:
        self.write_config({})

        runtime_payload = {
            "mode": "active",
            "shards": [
                {
                    "name": "shard-alpha",
                    "active_run_id": "run-1",
                    "frontier_ids": [100, 101],
                },
                {
                    "name": "shard-zeta",
                    "active_run_id": "run-3",
                    "frontier_ids": [105],
                },
                {"name": "shard-beta", "active_run_id": ""},
            ],
            "active_run": {"run_id": "run-1"},
            "open_milestone_ids": [1001, 1002],
            "updated_at": "2026-04-06T10:00:00Z",
        }

        with mock.patch.object(self.route_module, "_fleet_runtime_status_payload", return_value=runtime_payload):
            response = self.route_module._telemetry_response("How many active shards are running?")

        self.assertTrue(response["matched"])
        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertIn("Live fleet status", response["message"])
        self.assertIn("2 active shards out of 3 total shards", response["message"])
        shard_phrase_index = response["message"].find("active shards")
        first_active_index = response["message"].find("shard-alpha", shard_phrase_index)
        second_active_index = response["message"].find("shard-zeta", shard_phrase_index)
        self.assertTrue(first_active_index != -1 and second_active_index != -1)
        self.assertLess(first_active_index, second_active_index)
        self.assertIn("aggregate active run run-1", response["message"])
        self.assertIn("2 open milestones", response["message"])

    def test_telemetry_response_reports_live_fleet_runtime_status_update_age(self) -> None:
        self.write_config({})

        runtime_payload = {
            "mode": "active",
            "shards": [
                {
                    "name": "shard-alpha",
                    "active_run_id": "run-1",
                    "frontier_ids": [100, 101],
                },
            ],
            "active_run": {"run_id": "run-1"},
            "open_milestone_ids": [1001],
            "updated_at": "2026-04-06T10:00:00Z",
        }

        with mock.patch.object(self.route_module, "_fleet_runtime_status_payload", return_value=runtime_payload):
            with mock.patch.object(self.route_module, "_utc_now", return_value=dt.datetime(2026, 4, 6, 10, 15, tzinfo=dt.timezone.utc)):
                response = self.route_module._telemetry_response("How many active shards are running?")

        self.assertTrue(response["matched"])
        self.assertTrue(response["ok"])
        self.assertIn("updated 15m ago", response["message"])
        self.assertIn("at 2026-04-06T10:00:00Z", response["message"])
        self.assertIn("stale", response["message"])
        self.assertIn("run `chummer_design_supervisor status` to refresh this snapshot.", response["message"])

    def test_telemetry_answer_json_mode_includes_metadata(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                payload = {
                    "providers_summary": [
                        {
                            "provider_name": "1min",
                            "account_name": "acct-core",
                            "used_percent": 25.0,
                            "free_credits": 750_000,
                            "state": "ready",
                            "basis": "measured",
                        }
                    ]
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        rc, stdout, stderr = self._run_route_cli(
            ["--telemetry-answer", "--json", "1min", "credits"],
            extra_env={
                "EA_MCP_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "EA_MCP_API_TOKEN": "telemetry-json-token",
            },
        )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["matched"])
        self.assertEqual(payload["exit_code"], 0)
        self.assertIn("Live 1min status", payload["message"])
        self.assertIn("payload_source", payload)
        self.assertEqual(payload["payload_source"], "status")
        self.assertIn("payload_fetched_at", payload)

    def test_telemetry_answer_json_mode_rejects_non_telemetry_query(self) -> None:
        rc, stdout, stderr = self._run_route_cli(
            ["--telemetry-answer", "--json", "what is the next big wins registry update?"]
        )
        output = stdout + stderr

        self.assertEqual(rc, 10)
        payload = json.loads(output)
        self.assertFalse(payload["matched"])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["exit_code"], 10)
        self.assertEqual(payload["error"], "no_telemetry_match")
        self.assertEqual(payload["message"], "Query did not match a live telemetry question.")

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
        self.assertIn("Top-ups: excluded", response["message"])

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

    def test_onemin_probe_all_falls_back_to_probe_summary_when_status_is_unavailable(self) -> None:
        self.write_config({})

        probe_payload = {
            "slot_count": 2,
            "result_counts": {"ready": 2},
            "slots": [],
        }

        with mock.patch.object(self.route_module, "_ea_onemin_probe_payload", return_value=probe_payload):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=None):
                with mock.patch.object(self.route_module, "_ea_profiles_payload", return_value=None):
                    response = self.route_module._onemin_aggregate_response(probe_all=True)

        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertIn("direct local 1min provider health", response["message"])
        self.assertEqual(response["data"]["probe"]["slot_count"], 2)

    def test_onemin_aggregate_response_uses_profiles_fallback_when_status_is_unavailable(self) -> None:
        self.write_config({})

        profiles_payload = {
            "provider_health": {
                "providers": {
                    "onemin": {
                        "state": "ready",
                        "slots": [
                            {
                                "slot": "primary",
                                "account_name": "ONEMIN_AI_API_KEY",
                                "max_credits": 1_000_000,
                                "estimated_remaining_credits": 400_000,
                                "basis": "profiles_fallback",
                                "state": "ready",
                            }
                        ],
                    }
                }
            }
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=None) as status_mock:
            with mock.patch.object(self.route_module, "_ea_profiles_payload", return_value=profiles_payload) as profiles_mock:
                response = self.route_module._onemin_aggregate_response()

        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertEqual(response["data"]["slot_count"], 1)
        self.assertEqual(response["data"]["sum_free_credits"], 400_000)
        self.assertEqual(status_mock.call_args.kwargs["timeout_seconds"], 30.0)
        self.assertEqual(profiles_mock.call_args.kwargs["timeout_seconds"], 30.0)

    def test_ea_status_payload_reads_runtime_env_file_for_auth(self) -> None:
        observed: dict[str, str] = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                observed["path"] = self.path
                observed["auth"] = str(self.headers.get("Authorization") or "")
                observed["principal"] = str(self.headers.get("X-EA-Principal-ID") or "")
                body = json.dumps({"providers_summary": []}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        self.write_runtime_env(
            {
                "EA_MCP_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "EA_MCP_API_TOKEN": "runtime-file-token",
                "EA_MCP_PRINCIPAL_ID": "route-file-principal",
            }
        )

        with mock.patch.dict(
            os.environ,
            {
                "EA_MCP_BASE_URL": "",
                "EA_MCP_API_TOKEN": "",
                "EA_API_TOKEN": "",
                "EA_MCP_PRINCIPAL_ID": "",
                "EA_PRINCIPAL_ID": "",
                "CODEXEA_STATUS_URL": "",
            },
            clear=False,
        ):
            payload = self.route_module._ea_status_payload(refresh=True, window="7d")

        self.assertEqual(payload, {"providers_summary": []})
        self.assertEqual(observed["auth"], "Bearer runtime-file-token")
        self.assertEqual(observed["principal"], "route-file-principal")
        self.assertEqual(observed["path"], "/v1/codex/status?window=7d&refresh=1")

    def test_ea_status_url_rewrites_host_docker_internal_when_unresolved(self) -> None:
        self.write_runtime_env({"EA_MCP_BASE_URL": "http://host.docker.internal:8090"})

        with mock.patch.dict(os.environ, {"EA_MCP_BASE_URL": "", "CODEXEA_STATUS_URL": ""}, clear=False):
            with mock.patch.object(self.route_module.socket, "gethostbyname", side_effect=OSError("unresolved")):
                status_url = self.route_module._ea_status_url()

        self.assertEqual(status_url, "http://127.0.0.1:8090/v1/codex/status")

    def test_onemin_aggregate_response_explains_missing_api_token_when_cache_is_used(self) -> None:
        self.write_config({})
        self.write_runtime_cache(
            "ea_codex_profiles",
            {
                "provider_health": {
                    "providers": {
                        "onemin": {
                            "state": "ready",
                            "slots": [
                                {
                                    "slot": "primary",
                                    "account_name": "ONEMIN_AI_API_KEY",
                                    "max_credits": 1_000,
                                    "estimated_remaining_credits": 500,
                                    "basis": "profiles_fallback",
                                    "state": "ready",
                                }
                            ],
                        }
                    }
                }
            },
        )

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(401)
                self.end_headers()

            def do_POST(self):  # noqa: N802
                self.send_response(401)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        self.write_runtime_env(
            {
                "EA_MCP_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "EA_MCP_PRINCIPAL_ID": "route-file-principal",
            }
        )

        with mock.patch.dict(
            os.environ,
            {
                "EA_MCP_BASE_URL": "",
                "EA_MCP_API_TOKEN": "",
                "EA_API_TOKEN": "",
                "EA_MCP_PRINCIPAL_ID": "",
                "EA_PRINCIPAL_ID": "",
                "CODEXEA_STATUS_URL": "",
                "CODEXEA_PROFILES_URL": "",
            },
            clear=False,
        ):
            response = self.route_module._onemin_aggregate_response(probe_all=True, billing=True)

        self.assertTrue(response["ok"])
        self.assertIn("EA API token is not configured", response["message"])
        self.assertIn("used a direct local 1min probe fallback instead", response["message"])
        self.assertIn("billing refresh was skipped", response["message"])
        self.assertIn("fresh classification requires a configured EA API token", response["message"])

    def test_onemin_aggregate_response_uses_local_runtime_cache_when_live_payloads_fail(self) -> None:
        self.write_config({})
        profiles_payload = {
            "provider_health": {
                "providers": {
                    "onemin": {
                        "state": "ready",
                        "slots": [
                            {
                                "slot": "primary",
                                "account_name": "ONEMIN_AI_API_KEY",
                                "max_credits": 1_000_000,
                                "estimated_remaining_credits": 400_000,
                                "basis": "profiles_fallback",
                                "state": "ready",
                            }
                        ],
                    }
                }
            }
        }
        self.write_runtime_cache("ea_codex_profiles", profiles_payload)

        with mock.patch.object(self.route_module, "_ea_http_payload", side_effect=self.mock_http_401):
            response = self.route_module._onemin_aggregate_response()

        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertEqual(response["data"]["sum_free_credits"], 400_000)
        self.assertIn("using local Fleet runtime cache", response["message"])
        self.assertIn("2026-03-18T17:43:36Z", response["message"])

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

    def test_onemin_aggregate_response_hides_probe_note_when_no_unknown_slots_remain(self) -> None:
        self.write_config({})

        payload = {
            "onemin_aggregate": {
                "slot_count": 2,
                "slot_count_with_known_balance": 2,
                "sum_max_credits": 2000,
                "sum_free_credits": 1000,
                "remaining_percent_total": 50.0,
                "basis_summary": "actual_billing_usage_page x2",
                "unknown_unprobed_slot_count": 0,
                "probe_note": "unknown_unprobed means no live evidence yet",
                "incoming_topups_excluded": True,
            }
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._onemin_aggregate_response()

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["probe_note"], "")
        self.assertNotIn("Probe note:", response["message"])

    def test_onemin_probe_payload_uses_extended_timeout(self) -> None:
        with mock.patch.object(self.route_module, "_ea_http_payload", return_value={"ok": True}) as mocked_http:
            self.route_module._ea_onemin_probe_payload(include_reserve=False)

        self.assertEqual(mocked_http.call_args.kwargs["timeout_seconds"], 180.0)
        self.assertEqual(mocked_http.call_args.kwargs["payload"], {"include_reserve": False})

    def test_onemin_billing_refresh_payload_uses_extended_timeout(self) -> None:
        with mock.patch.object(self.route_module, "_ea_http_payload", return_value={"ok": True}) as mocked_http:
            self.route_module._ea_onemin_billing_refresh_payload(include_members=False, capture_raw_text=False)

        self.assertEqual(mocked_http.call_args.kwargs["timeout_seconds"], 30.0)
        self.assertEqual(
            mocked_http.call_args.kwargs["payload"],
            {
                "include_members": False,
                "capture_raw_text": False,
                "provider_api_all_accounts": False,
                "provider_api_continue_on_rate_limit": False,
            },
        )

    def test_ea_status_payload_honors_explicit_timeout(self) -> None:
        with mock.patch.object(self.route_module, "_ea_http_payload", return_value={"providers_summary": []}) as mocked_http:
            self.route_module._ea_status_payload(refresh=True, window="7d", timeout_seconds=7.5)

        self.assertEqual(mocked_http.call_args.kwargs["timeout_seconds"], 7.5)

    def test_onemin_aggregate_status_timeout_honors_env_override(self) -> None:
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

        with mock.patch.dict(os.environ, {"CODEXEA_ONEMIN_STATUS_TIMEOUT_SECONDS": "6.5"}, clear=False):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload) as status_mock:
                response = self.route_module._onemin_aggregate_response()

        self.assertTrue(response["ok"])
        self.assertEqual(status_mock.call_args.kwargs["timeout_seconds"], 6.5)

    def test_onemin_aggregate_response_surfaces_probe_timeout_detail(self) -> None:
        self.write_config({})
        self.route_module._LAST_EA_HTTP_ERROR = "timed out after 180s"

        with mock.patch.object(self.route_module, "_ea_onemin_probe_payload", return_value=None):
            response = self.route_module._onemin_aggregate_response(probe_all=True)

        self.assertTrue(response["ok"])
        self.assertIn("used a direct local 1min probe fallback instead", response["message"])

    def test_onemin_probe_failure_keeps_cached_aggregate_when_local_runtime_cache_exists(self) -> None:
        self.write_config({})
        profiles_payload = {
            "provider_health": {
                "providers": {
                    "onemin": {
                        "state": "ready",
                        "slots": [
                            {
                                "slot": "primary",
                                "account_name": "ONEMIN_AI_API_KEY",
                                "max_credits": 1_000,
                                "estimated_remaining_credits": 500,
                                "basis": "profiles_fallback",
                                "state": "ready",
                            }
                        ],
                    }
                }
            }
        }
        self.write_runtime_cache("ea_codex_profiles", profiles_payload)

        with mock.patch.object(self.route_module, "_ea_http_payload", side_effect=self.mock_http_401):
            response = self.route_module._onemin_aggregate_response(probe_all=True)

        self.assertTrue(response["ok"])
        self.assertEqual(response["exit_code"], 0)
        self.assertEqual(response["data"]["sum_free_credits"], 500)
        self.assertIn("used a direct local 1min probe fallback instead", response["message"])
        self.assertIn("using local Fleet runtime cache", response["message"])

    def test_onemin_aggregate_response_prefers_direct_local_onemin_over_zero_slot_cache(self) -> None:
        self.write_config({})
        cached_payload = {
            "onemin_aggregate": {
                "slot_count": 0,
                "slot_count_with_known_balance": 0,
                "incoming_topups_excluded": True,
            }
        }
        local_payload = {
            "provider_health": {
                "providers": {
                    "onemin": {
                        "state": "ready",
                        "slots": [
                            {
                                "slot": "primary",
                                "account_name": "ONEMIN_AI_API_KEY",
                                "max_credits": 1_000_000,
                                "estimated_remaining_credits": 400_000,
                                "estimated_credit_basis": "max_minus_observed_usage",
                                "state": "ready",
                            }
                        ],
                    }
                }
            },
            "probe": {
                "provider_key": "onemin",
                "slot_count": 1,
                "configured_slot_count": 1,
                "result_counts": {"ok": 1},
                "owner_mapped_slots": 0,
                "last_probe_at": 1_742_208_000.0,
                "note": "Probe-all sends one live low-volume request to each selected 1min slot and updates slot evidence.",
            },
        }
        self.route_module._LAST_EA_HTTP_ERROR = "missing_api_token"
        self.route_module._LAST_EA_STATUS_SOURCE = "local_runtime_cache"

        with mock.patch.object(self.route_module, "_ea_onemin_probe_payload", return_value=None):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=cached_payload):
                with mock.patch.object(self.route_module, "_local_onemin_direct_payload", return_value=local_payload):
                    response = self.route_module._onemin_aggregate_response(probe_all=True)

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["sum_free_credits"], 400_000)
        self.assertIn("direct local 1min probe fallback", response["message"])
        self.assertIn("direct local 1min provider health", response["message"])

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
        refresh_mock.assert_called_once_with(
            include_members=True,
            capture_raw_text=True,
            provider_api_all_accounts=False,
            provider_api_continue_on_rate_limit=False,
        )
        self.assertIn("1min billing refresh", rendered)
        self.assertIn("1min aggregate", rendered)
        self.assertIn("Next top-up:", rendered)

    def test_onemin_aggregate_billing_flag_honors_env_overrides(self) -> None:
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
        billing_refresh = {"connector_binding_count": 1, "billing_refresh_count": 1}

        with mock.patch.dict(
            os.environ,
            {
                "CODEXEA_ONEMIN_INCLUDE_MEMBERS": "0",
                "CODEXEA_ONEMIN_CAPTURE_RAW_TEXT": "false",
            },
            clear=False,
        ):
            with mock.patch.object(self.route_module, "_ea_onemin_billing_refresh_payload", return_value=billing_refresh) as refresh_mock:
                with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
                    self.route_module._onemin_aggregate_response(billing=True)

        refresh_mock.assert_called_once_with(
            include_members=False,
            capture_raw_text=False,
            provider_api_all_accounts=False,
            provider_api_continue_on_rate_limit=False,
        )

    def test_onemin_aggregate_billing_full_refresh_enables_all_account_provider_api_mode(self) -> None:
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
        billing_refresh = {"connector_binding_count": 0, "api_account_count": 39, "api_account_attempted": 39}

        with mock.patch.object(self.route_module, "_ea_onemin_billing_refresh_payload", return_value=billing_refresh) as refresh_mock:
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
                self.route_module._onemin_aggregate_response(billing=True, billing_full_refresh=True)

        refresh_mock.assert_called_once_with(
            include_members=True,
            capture_raw_text=True,
            provider_api_all_accounts=True,
            provider_api_continue_on_rate_limit=True,
        )

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

    def test_onemin_aggregate_billing_refresh_compacts_empty_refresh_when_cached_snapshots_exist(self) -> None:
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
            },
        }
        billing_refresh = {
            "connector_binding_count": 0,
            "billing_refresh_count": 0,
            "member_reconciliation_count": 0,
            "api_billing_refresh_count": 0,
            "api_member_reconciliation_count": 0,
            "note": "No enabled BrowserAct connector bindings were configured, and direct 1min API calls were rate-limited.",
        }

        with mock.patch.object(self.route_module, "_ea_onemin_billing_refresh_payload", return_value=billing_refresh):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
                response = self.route_module._onemin_aggregate_response(billing=True)

        self.assertTrue(response["ok"])
        self.assertIn("Showing cached billing state.", response["message"])
        self.assertNotIn("1min billing refresh", response["message"])

    def test_onemin_aggregate_billing_full_refresh_keeps_detailed_summary_when_explicitly_requested(self) -> None:
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
            },
        }
        billing_refresh = {
            "connector_binding_count": 0,
            "api_account_count": 39,
            "api_account_attempted": 39,
            "billing_refresh_count": 0,
            "member_reconciliation_count": 0,
            "api_billing_refresh_count": 0,
            "api_member_reconciliation_count": 0,
            "api_rate_limited": True,
            "errors": [{"tool_name": "onemin.api.billing_refresh"} for _ in range(39)],
            "note": "No enabled BrowserAct connector bindings were configured, and direct 1min API calls were rate-limited.",
        }

        with mock.patch.object(self.route_module, "_ea_onemin_billing_refresh_payload", return_value=billing_refresh):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
                response = self.route_module._onemin_aggregate_response(billing=True, billing_full_refresh=True)

        self.assertTrue(response["ok"])
        self.assertIn("1min billing refresh", response["message"])
        self.assertIn("API accounts: 39 configured, 39 attempted, 0 skipped", response["message"])

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
        self.assertTrue(data["ok"])
        self.assertEqual(data["exit_code"], 0)
        self.assertIn("matched", data)
        self.assertTrue(data["matched"])
        self.assertIn("payload_source", data)
        self.assertIn("payload_fetched_at", data)


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

    def test_onemin_aggregate_slots_flag_compact_mode(self) -> None:
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
                    "slot_role": "owner",
                    "owner_email": "owner@example.com",
                    "last_probe_result": "ok",
                    "last_probe_detail": "probed quickly",
                }
            ]
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            with io.StringIO() as stream, mock.patch("sys.stdout", stream):
                rc = self.route_module.main(["--onemin-aggregate", "--slots", "--slots-detail", "compact"])
                rendered = stream.getvalue()

        self.assertEqual(rc, 0)
        self.assertIn("Slot details:", rendered)
        self.assertIn("- owner@example.com [acct-a]: ready | measured | 25 free / 100 max | owner owner@example.com", rendered)
        self.assertNotIn("probe ok", rendered)
        self.assertNotIn("probed quickly", rendered)

    def test_onemin_aggregate_help_shows_slots_detail_option_and_examples(self) -> None:
        self.write_config({})

        with io.StringIO() as stdout, io.StringIO() as stderr, mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as ctx:
                self.route_module.main(["--help"])
            help_text = stdout.getvalue() + stderr.getvalue()

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("--slots-detail", help_text)
        self.assertIn("controls how much detail appears per 1min slot row", help_text)
        self.assertIn("codexea --onemin-aggregate --slots --slots-detail compact", help_text)

    def test_onemin_aggregate_rejects_invalid_slots_detail(self) -> None:
        self.write_config({})

        with io.StringIO() as stdout, io.StringIO() as stderr, mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as ctx:
                self.route_module.main(["--onemin-aggregate", "--slots-detail", "compactish"])
            error_text = stdout.getvalue() + stderr.getvalue()

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("invalid choice", error_text)

    def test_cli_subprocess_shows_compact_slot_output(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                payload = {
                    "providers_summary": [
                        {
                            "provider_name": "1min",
                            "account_name": "acct-a",
                            "max_credits": 100,
                            "free_credits": 25,
                            "basis": "measured",
                            "state": "ready",
                            "owner_email": "owner@example.com",
                            "slot_role": "owner",
                            "last_probe_result": "ok",
                        }
                    ]
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        rc, stdout, stderr = self._run_route_cli(
            ["--onemin-aggregate", "--slots", "--slots-detail", "compact"],
            extra_env={
                "EA_MCP_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "EA_MCP_API_TOKEN": "cli-token",
            },
        )

        self.assertEqual(rc, 0)
        message = stdout + stderr
        self.assertIn("Slot details:", message)
        self.assertIn("ready | measured | 25 free / 100 max", message)
        self.assertNotIn("probed", message)

    def test_cli_subprocess_help_contains_slots_detail(self) -> None:
        rc, stdout, stderr = self._run_route_cli(["--help"])
        output = stdout + stderr

        self.assertEqual(rc, 0)
        self.assertIn("--slots-detail", output)
        self.assertIn("codexea --onemin-aggregate --slots --slots-detail compact", output)

    def test_cli_subprocess_help_contains_json_telemetry_example(self) -> None:
        rc, stdout, stderr = self._run_route_cli(["--help"])
        output = stdout + stderr

        self.assertEqual(rc, 0)
        self.assertIn("--telemetry-answer --json", output)
        self.assertIn("codexea --telemetry-answer --json", output)

    def test_cli_subprocess_json_routing_output(self) -> None:
        rc, stdout, stderr = self._run_route_cli(
            ["--json", "what", "is", "the", "safest", "lane", "for", "a", "migration", "fix?"]
        )
        output = stdout + stderr

        self.assertEqual(rc, 0)
        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["matched"])
        self.assertIn("lane", payload["data"])
        self.assertIn("submode", payload["data"])
        self.assertIn(payload["data"]["lane"], {"easy", "repair", "groundwork", "review_light", "core", "jury", "survival"})

    def test_cli_subprocess_shell_takes_precedence_over_json(self) -> None:
        rc, stdout, stderr = self._run_route_cli(
            ["--shell", "--json", "what", "is", "the", "safest", "lane", "for", "a", "migration", "fix?"]
        )
        output = stdout + stderr

        self.assertEqual(rc, 0)
        self.assertIn("CODEXEA_ROUTE_LANE=", output)
        self.assertNotIn("\"ok\"", output)
        self.assertNotIn("\"exit_code\"", output)

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

    def test_onemin_aggregate_slots_flag_sorts_slots_by_label(self) -> None:
        self.write_config({})

        payload = {
            "providers_summary": [
                {
                    "provider_name": "1min",
                    "account_name": "Z-ACCOUNT",
                    "owner_label": "zeta-owner",
                    "max_credits": 100,
                    "free_credits": 10,
                    "basis": "measured",
                    "state": "ready",
                },
                {
                    "provider_name": "1min",
                    "account_name": "A-ACCOUNT",
                    "owner_label": "alpha-owner",
                    "max_credits": 100,
                    "free_credits": 20,
                    "basis": "measured",
                    "state": "ready",
                },
            ]
        }

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value=payload):
            response = self.route_module._onemin_aggregate_response(include_slots=True)

        self.assertTrue(response["ok"])
        first_alpha = response["message"].find("alpha-owner")
        first_zeta = response["message"].find("zeta-owner")
        self.assertTrue(first_alpha != -1 and first_zeta != -1)
        self.assertLess(first_alpha, first_zeta)

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

    def test_high_risk_prompt_stays_off_paid_core_without_explicit_opt_in(self) -> None:
        self.write_config({})

        with mock.patch.object(self.route_module, "_ea_status_payload", return_value={"providers_summary": [{"provider_name": "1min", "state": "unknown", "basis": "unknown_unprobed", "free_credits": None}]}):
            routed = self.route_module._route(["auth", "migration", "fix"])

        self.assertEqual(routed["lane"], "groundwork")
        self.assertEqual(routed["submode"], "responses_groundwork")
        self.assertEqual(routed["reason"], "groundwork_policy_default")

    def test_low_onemin_capacity_does_not_force_paid_core_when_policy_stays_cheap(self) -> None:
        self.write_config({})

        with mock.patch.dict(os.environ, {"CODEXEA_CORE_MIN_ONEMIN_CREDITS": "100000"}, clear=False):
            with mock.patch.object(self.route_module, "_ea_status_payload", return_value={"providers_summary": [{"provider_name": "1min", "state": "ready", "basis": "measured", "free_credits": 5000}]}):
                routed = self.route_module._route(["auth", "migration", "fix"])

        self.assertEqual(routed["lane"], "groundwork")
        self.assertEqual(routed["submode"], "responses_groundwork")
        self.assertEqual(routed["reason"], "groundwork_policy_default")


if __name__ == "__main__":
    unittest.main()
