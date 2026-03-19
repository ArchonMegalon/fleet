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
    spec = importlib.util.spec_from_file_location("test_admin_app_studio", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdminStudioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = load_admin_module()

    def test_studio_publish_mode_actions_skip_hold_and_mark_recommended(self) -> None:
        actions = self.admin.studio_publish_mode_actions(17, "publish_artifacts")

        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["fields"]["mode"], "publish_artifacts_and_feedback")
        self.assertEqual(actions[1]["fields"]["mode"], "publish_artifacts")
        self.assertIn("(Recommended)", actions[1]["label"])

    def test_build_studio_proposal_views_enriches_session_context(self) -> None:
        self.admin.studio_proposals = lambda limit=30: [
            {
                "id": 21,
                "session_id": 7,
                "status": "draft",
                "role": "designer",
                "target_type": "group",
                "target_id": "hub",
                "title": "Tighten queue overlay",
                "summary": "Reduce noisy backlog text.",
                "targets_summary": "group:hub",
                "payload": {
                    "proposal": {
                        "recommended_publish_mode": "publish_artifacts",
                        "feedback_note": "Keep only the dispatchable truth.",
                        "files": [{"path": "QUEUE.generated.yaml"}],
                    }
                },
                "proposal": {
                    "recommended_publish_mode": "publish_artifacts",
                    "feedback_note": "Keep only the dispatchable truth.",
                    "files": [{"path": "QUEUE.generated.yaml"}],
                },
                "files": [{"path": "QUEUE.generated.yaml"}],
                "targets": [{"target_type": "group", "target_id": "hub"}],
                "draft_dir": "/tmp/proposal-21",
            }
        ]
        self.admin.studio_session_snapshot = lambda session_id, message_limit=4: {
            "session": {
                "id": session_id,
                "status": "queued",
                "summary": "Need a smaller queue overlay.",
                "target_type": "group",
                "target_id": "hub",
            },
            "recent_messages": [
                {
                    "actor_type": "admin",
                    "actor_name": "admin",
                    "content": "Trim the overlay and keep the captain levers.",
                    "created_at": "2026-03-19T10:00:00Z",
                },
                {
                    "actor_type": "assistant",
                    "actor_name": "designer",
                    "content": "Drafted a tighter queue file.",
                    "created_at": "2026-03-19T10:01:00Z",
                },
            ],
            "active_run": {
                "id": 55,
                "status": "running",
                "model": "gpt-5.4",
                "started_at": "2026-03-19T10:02:00Z",
                "log_preview": "alpha",
                "final_preview": "omega",
            },
        }

        views = self.admin.build_studio_proposal_views()

        self.assertEqual(len(views), 1)
        self.assertEqual(views[0]["session_status"], "queued")
        self.assertEqual(views[0]["session_scope"], "group:hub")
        self.assertEqual(views[0]["target_lines"], ["group:hub"])
        self.assertEqual(views[0]["file_lines"], ["QUEUE.generated.yaml"])
        self.assertEqual(views[0]["recent_message_lines"][0]["label"], "admin:admin")
        self.assertEqual(views[0]["active_run"]["id"], 55)
        self.assertEqual(views[0]["publish_mode_actions"][1]["fields"]["mode"], "publish_artifacts")

    def test_render_studio_helpers_include_follow_up_and_publish_controls(self) -> None:
        proposal = {
            "id": 21,
            "session_id": 7,
            "status": "draft",
            "role": "designer",
            "target_type": "group",
            "target_id": "hub",
            "title": "Tighten queue overlay",
            "summary": "Reduce noisy backlog text.",
            "targets_summary": "group:hub",
            "recommended_publish_mode": "publish_artifacts",
            "publish_mode_actions": self.admin.studio_publish_mode_actions(21, "publish_artifacts"),
            "target_lines": ["group:hub"],
            "file_lines": ["QUEUE.generated.yaml"],
            "session_status": "queued",
            "session_scope": "group:hub",
            "session_summary": "Need a smaller queue overlay.",
            "draft_dir": "/tmp/proposal-21",
            "feedback_note": "Keep only the dispatchable truth.",
            "recent_message_lines": [{"label": "admin:admin", "content": "Trim it.", "created_at": "2026-03-19T10:00:00Z"}],
            "active_run": {"id": 55, "status": "running", "model": "gpt-5.4", "started_at": "2026-03-19T10:02:00Z", "log_preview": "alpha", "final_preview": "omega"},
            "proposal": {},
        }

        def td_fn(value):
            return "" if value is None else str(value)

        def render_action_fn(action):
            return f"[{action.get('label')}]"

        row_html = self.admin.render_studio_proposal_row_html(proposal, td_fn=td_fn, render_action_fn=render_action_fn)
        focus_html = self.admin.render_studio_proposal_focus_html(proposal, td_fn=td_fn, render_action_fn=render_action_fn)

        self.assertIn("Preview", row_html)
        self.assertIn("Publish artifacts only", focus_html)
        self.assertIn("/api/admin/studio/sessions/7/message", focus_html)
        self.assertIn("QUEUE.generated.yaml", focus_html)

    def test_api_admin_publish_studio_proposal_mode_posts_mode_and_redirects(self) -> None:
        posted = {}

        def fake_trigger(path: str, payload=None):
            posted["path"] = path
            posted["payload"] = payload
            return {"ok": True}

        self.admin.trigger_studio_post = fake_trigger

        response = self.admin.api_admin_publish_studio_proposal_mode(21, mode="publish_artifacts")

        self.assertEqual(posted["path"], "/api/studio/proposals/21/publish")
        self.assertEqual(posted["payload"], {"mode": "publish_artifacts"})
        self.assertEqual(response.args[0], "/admin/details#studio")
        self.assertEqual(response.kwargs["status_code"], 303)

    def test_api_admin_studio_session_message_posts_and_redirects(self) -> None:
        posted = {}

        def fake_trigger(path: str, payload=None):
            posted["path"] = path
            posted["payload"] = payload
            return {"ok": True}

        self.admin.trigger_studio_post = fake_trigger

        response = self.admin.api_admin_studio_session_message(7, message="Tighten the title and cut the filler.")

        self.assertEqual(posted["path"], "/api/studio/sessions/7/message")
        self.assertEqual(posted["payload"], {"message": "Tighten the title and cut the filler."})
        self.assertEqual(response.args[0], "/admin/details#studio")
        self.assertEqual(response.kwargs["status_code"], 303)

    def test_api_admin_studio_session_message_rejects_empty_message(self) -> None:
        with self.assertRaises(Exception) as ctx:
            self.admin.api_admin_studio_session_message(7, message="   ")

        self.assertEqual(ctx.exception.args[0], 400)
        self.assertEqual(ctx.exception.args[1], "message is required")
