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

    def test_studio_kickoff_templates_seed_multi_target_briefs(self) -> None:
        config = {
            "project_groups": [
                {
                    "id": "control-plane",
                    "projects": ["fleet", "ea"],
                },
                {
                    "id": "chummer-vnext",
                    "projects": ["core", "ui", "hub"],
                    "deployment": {
                        "public_surface": {
                            "targets": [
                                {"name": "portal root"},
                                {"name": "hub preview"},
                            ]
                        }
                    },
                }
            ],
            "studio": {"roles": {"designer": {}, "program_manager": {}, "auditor": {}, "healer": {}}},
        }

        templates = self.admin.studio_kickoff_templates(config)

        self.assertGreaterEqual(len(templates), 3)
        self.assertEqual(templates[0]["target_key"], "group:chummer-vnext")
        self.assertTrue(any(item["target_key"] == "fleet:fleet" for item in templates))
        self.assertTrue(all(item.get("multi_target") for item in templates))
        self.assertTrue(all("proposal.targets" in str(item.get("message") or "") for item in templates))
        self.assertTrue(any(item.get("role") == "designer" for item in templates))
        self.assertTrue(any(item.get("role") == "product_governor" for item in templates))
        self.assertTrue(
            any(item.get("role") == "designer" and item.get("target_key") == "group:control-plane" for item in templates)
        )
        self.assertTrue(
            any(item.get("role") == "product_governor" and item.get("target_key") == "group:control-plane" for item in templates)
        )

    def test_studio_publish_mode_actions_skip_hold_and_mark_recommended(self) -> None:
        actions = self.admin.studio_publish_mode_actions(17, "publish_artifacts")

        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["fields"]["mode"], "publish_artifacts_and_feedback")
        self.assertEqual(actions[1]["fields"]["mode"], "publish_artifacts")
        self.assertIn("(Recommended)", actions[1]["label"])

    def test_studio_role_options_include_product_governor_label(self) -> None:
        html = self.admin.studio_role_options_html(
            {"studio": {"roles": {"designer": {}, "product_governor": {}, "auditor": {}}}},
            "product_governor",
        )

        self.assertIn('value="product_governor"', html)
        self.assertIn(">Product Governor<", html)

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

    def test_build_studio_session_views_enriches_recent_messages_and_active_run(self) -> None:
        self.admin.studio_sessions = lambda limit=20: [
            {
                "id": 7,
                "status": "queued",
                "role": "designer",
                "target_type": "group",
                "target_id": "hub",
                "title": "Tighten queue overlay",
                "summary": "Need a smaller queue overlay.",
                "proposal_count": 2,
                "draft_proposal_count": 1,
                "last_message_at": "2026-03-19T10:01:00Z",
                "updated_at": "2026-03-19T10:02:00Z",
            }
        ]
        self.admin.studio_session_snapshot = lambda session_id, message_limit=4: {
            "session": {
                "id": session_id,
                "status": "queued",
                "role": "designer",
                "target_type": "group",
                "target_id": "hub",
                "title": "Tighten queue overlay",
                "summary": "Need a smaller queue overlay.",
                "proposal_count": 2,
                "draft_proposal_count": 1,
                "updated_at": "2026-03-19T10:02:00Z",
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

        views = self.admin.build_studio_session_views()

        self.assertEqual(len(views), 1)
        self.assertEqual(views[0]["session_scope"], "group:hub")
        self.assertEqual(views[0]["role_label"], "Designer")
        self.assertEqual(views[0]["latest_message_label"], "assistant:designer")
        self.assertEqual(views[0]["active_run"]["id"], 55)

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
            "control_decision_summary": "canon / type_d",
            "control_decision_reason": "Queue drift exposed a missing contract seam.",
            "control_decision_exit_condition": "Updated canon is published and mirrored downstream.",
            "affected_canon_files": ["CONTRACT_SETS.yaml", "README.md"],
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
        self.assertIn("canon / type_d", focus_html)
        self.assertIn("CONTRACT_SETS.yaml", focus_html)

    def test_render_studio_session_helpers_include_follow_up_and_open_controls(self) -> None:
        session = {
            "id": 7,
            "status": "queued",
            "role": "designer",
            "role_label": "Designer",
            "session_scope": "group:hub",
            "title": "Tighten queue overlay",
            "summary": "Need a smaller queue overlay.",
            "proposal_count": 2,
            "draft_proposal_count": 1,
            "latest_message_label": "assistant:designer",
            "latest_message_summary": "Drafted a tighter queue file.",
            "recent_message_lines": [{"label": "assistant:designer", "content": "Drafted a tighter queue file.", "created_at": "2026-03-19T10:01:00Z"}],
            "active_run": {"id": 55, "status": "running", "model": "gpt-5.4", "started_at": "2026-03-19T10:02:00Z", "log_preview": "alpha", "final_preview": "omega"},
            "updated_at": "2026-03-19T10:02:00Z",
        }

        def td_fn(value):
            return "" if value is None else str(value)

        def render_action_fn(action):
            return f"[{action.get('label')}]"

        row_html = self.admin.render_studio_session_row_html(session, td_fn=td_fn, render_action_fn=render_action_fn)
        focus_html = self.admin.render_studio_session_focus_html(session, td_fn=td_fn, render_action_fn=render_action_fn)

        self.assertIn("Preview", row_html)
        self.assertIn("Open Studio", focus_html)
        self.assertIn("/api/admin/studio/sessions/7/message", focus_html)

    def test_render_studio_template_card_posts_hidden_kickoff_payload(self) -> None:
        card_html = self.admin.render_studio_template_card_html(
            {
                "title": "Fleet: cross-group blocker triage",
                "summary": "Prepare a coordinated packet.",
                "detail": "Use this when several repos hurt at once.",
                "target_key": "fleet:fleet",
                "role": "auditor",
                "message": "Use proposal.targets for the coordinated publish packet.",
                "multi_target": True,
            },
            td_fn=lambda value: "" if value is None else str(value),
        )

        self.assertIn('/api/admin/studio/sessions', card_html)
        self.assertIn('name="target_key" value="fleet:fleet"', card_html)
        self.assertIn('name="role" value="auditor"', card_html)
        self.assertIn("Start template", card_html)

    def test_render_publish_event_focus_helpers_include_target_details(self) -> None:
        studio_focus = self.admin.render_studio_publish_event_focus_html(
            {
                "id": 12,
                "proposal_id": 34,
                "session_id": 7,
                "source_target_type": "group",
                "source_target_id": "hub",
                "mode": "publish_artifacts",
                "created_at": "2026-03-20T09:00:00Z",
                "outcome_state": "active",
                "outcome_summary": "1 target still moving",
                "published_targets": [
                    {
                        "target_type": "project",
                        "target_id": "hub",
                        "file_count": 2,
                        "published_dir": "/tmp/hub",
                        "feedback_rel": "feedback/hub.txt",
                        "current_outcome": "runtime running · slice tighten queue overlay",
                    }
                ],
            },
            td_fn=lambda value: "" if value is None else str(value),
        )
        group_focus = self.admin.render_group_publish_event_focus_html(
            {
                "id": 5,
                "group_id": "chummer-vnext",
                "source": "audit_publish",
                "source_scope_type": "group",
                "source_scope_id": "chummer-vnext",
                "created_at": "2026-03-20T09:01:00Z",
                "outcome_state": "active",
                "outcome_summary": "1 target still moving",
                "published_targets": [
                    {
                        "target_type": "project",
                        "target_id": "ui",
                        "file_count": 1,
                        "published_dir": "/tmp/ui",
                        "current_outcome": "runtime dispatch_pending",
                    }
                ],
            },
            td_fn=lambda value: "" if value is None else str(value),
        )

        self.assertIn("Studio publish event #12", studio_focus)
        self.assertIn("feedback/hub.txt", studio_focus)
        self.assertIn("runtime running", studio_focus)
        self.assertIn("1 target still moving", studio_focus)
        self.assertIn("Group publish event #5", group_focus)
        self.assertIn("/tmp/ui", group_focus)
        self.assertIn("dispatch_pending", group_focus)
        self.assertIn("Current outcome:", group_focus)

    def test_build_publish_event_views_enrich_current_outcomes(self) -> None:
        self.admin.studio_publish_events = lambda limit=50: [
            {
                "id": 12,
                "proposal_id": 34,
                "session_id": 7,
                "source_target_type": "group",
                "source_target_id": "hub",
                "mode": "publish_artifacts",
                "published_targets_summary": "project:hub (2)",
                "published_targets": [
                    {
                        "target_type": "project",
                        "target_id": "hub",
                        "file_count": 2,
                        "published_dir": "/tmp/hub",
                        "feedback_rel": "feedback/hub.txt",
                    }
                ],
            }
        ]
        self.admin.group_publish_events = lambda limit=50: [
            {
                "id": 5,
                "group_id": "chummer-vnext",
                "source": "audit_publish",
                "source_scope_type": "group",
                "source_scope_id": "chummer-vnext",
                "published_targets_summary": "group:chummer-vnext",
                "published_targets": [
                    {
                        "target_type": "group",
                        "target_id": "chummer-vnext",
                        "file_count": 1,
                        "published_dir": "/tmp/group",
                    }
                ],
            }
        ]

        status = {
            "projects": [
                {
                    "id": "hub",
                    "runtime_status": "running",
                    "current_slice": "tighten queue overlay",
                    "next_action": "wait for review",
                }
            ],
            "groups": [
                {
                    "id": "chummer-vnext",
                    "status": "running",
                    "phase": "delivery",
                    "dispatch_ready": True,
                }
            ],
            "cockpit": {"summary": {"fleet_health": "ok", "blocked_groups": 1, "open_incidents": 2}},
        }

        studio_views = self.admin.build_studio_publish_event_views(status)
        group_views = self.admin.build_group_publish_event_views(status)

        self.assertEqual(studio_views[0]["published_targets"][0]["current_outcome"], "runtime running · slice tighten queue overlay · wait for review")
        self.assertEqual(group_views[0]["published_targets"][0]["current_outcome"], "status running · phase delivery · dispatchable")
        self.assertEqual(studio_views[0]["outcome_state"], "active")
        self.assertEqual(studio_views[0]["outcome_summary"], "1 target still moving")
        self.assertEqual(group_views[0]["outcome_state"], "active")
        self.assertEqual(group_views[0]["outcome_summary"], "1 target still moving")

    def test_api_admin_create_studio_session_posts_and_redirects_to_focus(self) -> None:
        posted = {}

        def fake_trigger(path: str, payload=None):
            posted["path"] = path
            posted["payload"] = payload
            return {"session_id": 17}

        self.admin.trigger_studio_post = fake_trigger

        response = self.admin.api_admin_create_studio_session(
            target_key="group:hub",
            role="designer",
            title="Tighten queue overlay",
            message="Compare two quieter overlay drafts.",
        )

        self.assertEqual(posted["path"], "/api/studio/sessions")
        self.assertEqual(
            posted["payload"],
            {
                "target_type": "group",
                "target_id": "hub",
                "role": "designer",
                "title": "Tighten queue overlay",
                "message": "Compare two quieter overlay drafts.",
            },
        )
        self.assertEqual(response.args[0], "/admin/details?focus=studio-session-17#studio")
        self.assertEqual(response.kwargs["status_code"], 303)

    def test_api_admin_create_studio_session_rejects_missing_inputs(self) -> None:
        with self.assertRaises(Exception) as missing_target:
            self.admin.api_admin_create_studio_session(target_key="   ", role="designer", title="", message="Need a draft.")
        self.assertEqual(missing_target.exception.args[0], 400)
        self.assertEqual(missing_target.exception.args[1], "target is required")

        with self.assertRaises(Exception) as missing_message:
            self.admin.api_admin_create_studio_session(target_key="group:hub", role="designer", title="", message="   ")
        self.assertEqual(missing_message.exception.args[0], 400)
        self.assertEqual(missing_message.exception.args[1], "message is required")

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
