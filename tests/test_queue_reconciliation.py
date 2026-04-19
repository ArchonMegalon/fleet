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
    spec = importlib.util.spec_from_file_location("test_queue_reconciliation_admin", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QueueReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = load_admin_module()

    def test_queue_reconciliation_detects_public_vs_repo_local_drift(self) -> None:
        self.admin.utc_now = lambda: self.admin.parse_iso("2026-04-18T18:00:00Z")
        status = {
            "generated_at": "2026-04-18T18:00:00Z",
            "projects": [
                {
                    "id": "fleet",
                    "runtime_status": "dispatch_pending",
                    "queue": [{"title": "Land reconciliation report", "status": "queued"}],
                }
            ],
            "groups": [],
            "account_pools": [],
            "cockpit": {"worker_breakdown": {"active_workers": 0}},
            "runtime_healing": {"summary": {"alert_state": "healthy"}},
        }
        progress_report = {
            "overall_status": "complete",
            "overall_progress_percent": 100,
            "repo_backlog": {"open_item_count": 0},
            "flagship_readiness": {
                "status": "ready",
                "layout_familiarity_proven": True,
                "desktop_executable_gate_status": "pass",
            },
        }
        progress_history = {
            "snapshots": [
                {"as_of": "2026-04-10", "overall_progress_percent": 70, "phase_label": "Stabilize"},
                {"as_of": "2026-04-17", "overall_progress_percent": 95, "phase_label": "Closeout"},
            ]
        }
        readiness = {
            "status": "fail",
            "summary": {"warning_count": 1, "missing_count": 1},
            "completion_audit": {"status": "fail"},
            "missing_keys": ["desktop_client"],
            "readiness_planes": {
                "veteran_ready": {
                    "status": "warning",
                    "reasons": ["Desktop visual familiarity gate is not ready."],
                }
            },
        }
        journey_gates = {
            "summary": {"overall_state": "blocked", "blocked_count": 1},
            "journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "blocking_reasons": ["local desktop executable proof is stale"],
                }
            ],
        }
        support_packets = {"summary": {"open_packet_count": 2, "closure_waiting_on_release_truth": 1}}
        status_plane = {"whole_product_final_claim_status": "fail"}
        completion_frontier = {
            "repo_backlog_audit": {
                "open_item_count": 2,
                "reason": "active repo-local backlog remains outside the closed design registry: fleet",
            }
        }

        payload = self.admin.queue_reconciliation_payload(
            status,
            progress_report=progress_report,
            progress_history=progress_history,
            readiness=readiness,
            journey_gates=journey_gates,
            support_packets=support_packets,
            status_plane=status_plane,
            completion_frontier=completion_frontier,
        )

        self.assertEqual(payload["contract_name"], "fleet.queue_reconciliation")
        self.assertEqual(payload["overall_state"], "blocked")
        self.assertEqual(payload["summary"]["repo_backlog_open_item_count"], 2)
        self.assertEqual(payload["summary"]["support_waiting_on_release_truth_count"], 1)
        self.assertEqual(payload["history_windows"][0]["snapshot_as_of"], "2026-04-17")
        self.assertEqual(payload["history_windows"][0]["delta_progress_percent"], 5)
        self.assertEqual(payload["history_windows"][1]["snapshot_as_of"], "2026-04-10")
        self.assertEqual(payload["history_windows"][1]["delta_progress_percent"], 30)
        self.assertGreaterEqual(len(payload["readiness_drift"]["reasons"]), 2)
        surfaces = {row["surface"] for row in payload["shell_surface_deltas"]}
        self.assertIn("desktop_client", surfaces)
        self.assertIn("install_claim_restore_continue", surfaces)
        self.assertIn("release_truth", surfaces)

    def test_admin_queue_reconciliation_api_uses_payload_helper(self) -> None:
        expected = {"contract_name": "fleet.queue_reconciliation", "overall_state": "nominal"}
        self.admin.queue_reconciliation_payload = lambda status=None, **kwargs: expected

        payload = self.admin.api_admin_queue_reconciliation()

        self.assertIs(payload, expected)


if __name__ == "__main__":
    unittest.main()
