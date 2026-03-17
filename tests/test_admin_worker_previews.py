from __future__ import annotations

import importlib.util
import sys
import tempfile
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
    spec = importlib.util.spec_from_file_location("test_admin_app_worker_previews", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdminWorkerPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = load_admin_module()

    def test_read_run_preview_returns_tail_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "worker.log"
            path.write_text("one\ntwo\nthree\nfour\nfive\n", encoding="utf-8")

            preview = self.admin.read_run_preview(path, max_lines=2, max_chars=32)

        self.assertEqual(preview, "four\nfive")

    def test_build_worker_cards_includes_log_and_final_previews(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "run.jsonl"
            final_path = Path(tmpdir) / "final.txt"
            log_path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
            final_path.write_text("summary line 1\nsummary line 2\n", encoding="utf-8")

            self.admin.active_run_rows = lambda: [
                {
                    "id": 17,
                    "project_id": "fleet",
                    "status": "running",
                    "job_kind": "coding",
                    "account_alias": "acct-core-a",
                    "model": "gpt-5",
                    "spider_tier": "core",
                    "started_at": "2026-03-17T10:00:00Z",
                    "slice_name": "inspect active worker previews",
                    "log_path": str(log_path),
                    "final_message_path": str(final_path),
                }
            ]
            self.admin.utc_now = lambda: self.admin.parse_iso("2026-03-17T10:05:00Z")

            status = {
                "projects": [
                    {
                        "id": "fleet",
                        "group_ids": ["ops"],
                        "current_slice": "inspect active worker previews",
                        "runtime_status": "running",
                        "pull_request": {"review_status": "not_requested"},
                    }
                ],
                "config": {
                    "accounts": {
                        "acct-core-a": {
                            "bridge_name": "Core Lane",
                        }
                    }
                },
            }

            cards = self.admin.build_worker_cards(status)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["log_preview"], "alpha\nbeta\ngamma")
        self.assertEqual(cards[0]["final_preview"], "summary line 1\nsummary line 2")

    def test_run_preview_payload_reads_both_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "run.jsonl"
            final_path = Path(tmpdir) / "final.txt"
            log_path.write_text("tail 1\ntail 2\n", encoding="utf-8")
            final_path.write_text("final 1\nfinal 2\n", encoding="utf-8")

            payload = self.admin.run_preview_payload(
                {
                    "log_path": str(log_path),
                    "final_message_path": str(final_path),
                }
            )

        self.assertEqual(payload["log_preview"], "tail 1\ntail 2")
        self.assertEqual(payload["final_preview"], "final 1\nfinal 2")


if __name__ == "__main__":
    unittest.main()
