from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


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
    spec = importlib.util.spec_from_file_location("test_operator_surface_admin", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OperatorSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = load_admin_module()

    def test_operator_surface_joins_frontier_queue_proof_accounts_and_shards(self) -> None:
        self.admin.utc_now = lambda: self.admin.parse_iso("2026-04-18T06:50:00Z")
        status = {
            "generated_at": "2026-04-15T06:50:00Z",
            "config": {"projects": [], "groups": []},
            "projects": [
                {
                    "id": "fleet",
                    "runtime_status": "dispatch_pending",
                    "queue": [{"title": "Build operator surface", "status": "queued"}],
                    "current_slice": "Build operator surface",
                    "selected_lane": "core",
                    "last_auto_requeue_at": "2026-04-18T06:45:00Z",
                    "last_auto_requeue_reason": "worker session went stale after 1200s without heartbeat or log activity",
                    "last_auto_requeue_trigger": "stale_worker_session_requeued",
                    "last_auto_requeue_receipt_id": "queue-recovery-demo",
                    "last_auto_requeue_receipt_path": "/tmp/queue-recovery-demo.generated.json",
                }
            ],
            "groups": [
                {
                    "id": "control-plane",
                    "status": "group_blocked",
                    "remaining_milestones": ["operator surface"],
                    "dispatch_blockers": ["proof stale"],
                }
            ],
            "account_pools": [
                {
                    "alias": "acct-core-a",
                    "auth_status": "ready",
                    "pool_state": "ready",
                    "daily_budget_usd": 10,
                    "daily_usage": {"cost": 9},
                    "monthly_budget_usd": 100,
                    "monthly_usage": {"cost": 10},
                    "active_runs": 1,
                    "max_parallel_runs": 2,
                }
            ],
            "runtime_healing": {"summary": {"alert_state": "degraded", "recent_restart_count": 2}},
            "cockpit": {
                "worker_breakdown": {"active_workers": 1, "active_coding_workers": 1, "active_review_workers": 0},
                "workers": [{"project_id": "fleet", "phase": "coding"}],
                "queue_forecast": {"now": {"project_id": "fleet"}, "next": {"project_id": "fleet"}},
                "capacity_forecast": {
                    "critical_path_lane": "core",
                    "mission_runway": "2h",
                    "pool_runway": "4h",
                    "critical_path_stop": "capacity",
                },
                "blocker_forecast": {"now": "proof stale"},
            },
        }
        payload = self.admin.operator_surface_payload(
            status,
            active_shards_payload={
                "configured_shard_count": 13,
                "active_run_count": 1,
                "active_shards": [
                    {
                        "name": "shard-13",
                        "updated_at": "2026-04-18T05:20:00Z",
                        "mode": "completion_review",
                        "active_run_id": "run-1",
                        "active_run_process_alive": True,
                        "active_run_progress_state": "running",
                        "open_milestone_ids": [3893651879],
                        "focus_owners": ["fleet", "executive-assistant"],
                        "selected_account_alias": "direct-default",
                        "selected_model": "qwen3-coder-next:q8_0",
                        "worker_transport_state": "outage_waiting",
                        "worker_transport_current_outage": True,
                        "worker_transport_last_http_status": 502,
                        "worker_transport_last_cf_ray": "9eea4e0d8a1d9730-FRA",
                        "worker_transport_last_reason": "http_502",
                        "worker_transport_retry_count": 4,
                        "worker_transport_next_retry_at": "2026-04-18T06:50:30Z",
                        "worker_transport_outage_started_at": "2026-04-18T05:30:00Z",
                        "worker_transport_updated_at": "2026-04-18T06:50:00Z",
                    }
                ],
                "updated_at": "2026-04-15T06:49:00Z",
            },
            artifact_freshness={
                "status_plane": {"state": "fresh", "age": "1m"},
                "journey_gates": {"state": "stale", "reason": "source changed"},
            },
            completion_frontier={
                "completion_audit": {"status": "fail", "reason": "active repo-local backlog remains"},
                "frontier": [
                    {
                        "id": 3893651879,
                        "title": "Repo backlog: fleet operator surface",
                        "status": "review_required",
                        "exit_criteria": ["materially implement the backlog item"],
                    }
                ],
            },
        )

        self.assertEqual(payload["overall_state"], "blocked")
        self.assertIn("active repo-local backlog", payload["next_page"])
        self.assertEqual(payload["shard_mix"]["configured_shard_count"], 13)
        self.assertEqual(payload["shard_mix"]["running_shard_count"], 1)
        self.assertEqual(payload["queue_health"]["blocked_project_count"], 0)
        self.assertEqual(payload["queue_health"]["stalled_worker_alert_count"], 1)
        self.assertEqual(payload["queue_health"]["policy"]["shard_debt_attention_after_seconds"], 900)
        self.assertTrue(payload["queue_health"]["policy"]["signed_receipts_required"])
        self.assertEqual(payload["queue_health"]["recent_auto_requeues"][0]["receipt_path"], "/tmp/queue-recovery-demo.generated.json")
        self.assertEqual(payload["shard_debt_aging"]["rows"][0]["debt_state"], "blocked")
        self.assertEqual(payload["worker_transport_health"]["state"], "blocked")
        self.assertEqual(payload["worker_transport_health"]["outage_shard_count"], 1)
        self.assertEqual(payload["worker_transport_health"]["attention_rows"][0]["last_http_status"], 502)
        self.assertEqual(payload["proof_freshness"]["stale_or_missing_count"], 1)
        self.assertEqual(payload["account_health"]["state"], "attention")
        self.assertEqual(payload["resource_pressure"]["critical_path_lane"], "core")
        self.assertTrue(any(row["scope"] == "frontier:3893651879" for row in payload["blocked_milestones"]))

    def test_operator_surface_api_uses_admin_status_payload(self) -> None:
        status = {
            "generated_at": "2026-04-15T06:55:00Z",
            "config": {"projects": [], "groups": []},
            "projects": [],
            "groups": [],
            "account_pools": [],
            "cockpit": {"worker_breakdown": {"active_workers": 0}},
            "runtime_healing": {"summary": {"alert_state": "nominal"}},
        }
        self.admin.admin_status_payload = lambda: status
        self.admin.load_design_supervisor_active_shards_payload = lambda: {"configured_shard_count": 0, "active_shards": []}
        self.admin.published_artifact_freshness_payload = lambda: {}
        self.admin.load_completion_review_frontier_payload = lambda: {}

        payload = self.admin.api_cockpit_operator_surface()

        self.assertEqual(payload["contract_name"], "fleet.operator_surface")
        self.assertEqual(payload["overall_state"], "nominal")

    def test_render_operator_surface_shows_queue_recovery_policy_and_receipt_link(self) -> None:
        self.admin.utc_now = lambda: self.admin.parse_iso("2026-04-18T06:55:00Z")
        self.admin.admin_status_payload = lambda: {
            "generated_at": "2026-04-18T06:55:00Z",
            "config": {"projects": [], "groups": [], "policies": {"queue_recovery": {"signed_receipts_required": True}}},
            "projects": [
                {
                    "id": "fleet",
                    "runtime_status": "dispatch_pending",
                    "queue": [{"title": "Recover stalled worker", "status": "queued"}],
                    "last_auto_requeue_at": "2026-04-18T06:45:00Z",
                    "last_auto_requeue_reason": "worker session went stale after 1200s without heartbeat or log activity",
                    "last_auto_requeue_trigger": "stale_worker_session_requeued",
                    "last_auto_requeue_receipt_id": "queue-recovery-demo",
                    "last_auto_requeue_receipt_path": "/tmp/queue-recovery-demo.generated.json",
                }
            ],
            "groups": [],
            "account_pools": [],
            "cockpit": {"worker_breakdown": {"active_workers": 0}, "queue_forecast": {}, "capacity_forecast": {}, "blocker_forecast": {}},
            "runtime_healing": {"summary": {"alert_state": "nominal"}},
        }
        self.admin.queue_reconciliation_payload = lambda *args, **kwargs: {"overall_state": "nominal", "summary": {}, "history_windows": [], "readiness_drift": {"reasons": []}, "shell_surface_deltas": []}
        self.admin.load_design_supervisor_active_shards_payload = lambda: {
            "configured_shard_count": 13,
            "active_shards": [
                {
                    "name": "shard-13",
                    "active_run_id": "run-13",
                    "active_run_process_alive": True,
                    "active_run_progress_state": "transport_outage_waiting",
                    "worker_transport_state": "outage_waiting",
                    "worker_transport_current_outage": True,
                    "worker_transport_last_http_status": 502,
                    "worker_transport_last_cf_ray": "9eea4e0d8a1d9730-FRA",
                    "worker_transport_retry_count": 3,
                    "worker_transport_next_retry_at": "2026-04-18T06:56:00Z",
                    "worker_transport_updated_at": "2026-04-18T06:55:00Z",
                }
            ],
        }
        self.admin.published_artifact_freshness_payload = lambda: {}
        self.admin.load_completion_review_frontier_payload = lambda: {}

        html = self.admin.render_operator_surface()

        self.assertIn("15m", html)
        self.assertIn("Signed receipts are required", html)
        self.assertIn("External Worker Transport", html)
        self.assertIn("9eea4e0d8a1d9730-FRA", html)
        self.assertIn("file:///tmp/queue-recovery-demo.generated.json", html)


if __name__ == "__main__":
    unittest.main()
