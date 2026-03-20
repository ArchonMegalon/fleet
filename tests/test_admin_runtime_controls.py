from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


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
    spec = importlib.util.spec_from_file_location("test_admin_runtime_controls_module", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdminRuntimeControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = load_admin_module()

    def test_pause_project_disables_project_and_calls_controller_interrupt(self) -> None:
        with mock.patch.object(self.admin, "set_project_enabled") as set_project_enabled:
            with mock.patch.object(self.admin, "trigger_controller_post", return_value={"ok": True}) as trigger_controller_post:
                response = self.admin.api_admin_pause_project("fleet")

        set_project_enabled.assert_called_once_with("fleet", False)
        trigger_controller_post.assert_called_once_with("/api/projects/fleet/pause")
        self.assertEqual(response.kwargs.get("status_code"), 303)

    def test_pause_group_interrupts_each_member_project(self) -> None:
        group = {"id": "ops", "projects": ["fleet", "hub"]}
        with mock.patch.object(self.admin, "group_cfg", return_value=group):
            with mock.patch.object(self.admin, "normalize_config", return_value={"project_groups": [group]}):
                with mock.patch.object(self.admin, "set_group_enabled") as set_group_enabled:
                    with mock.patch.object(self.admin, "trigger_controller_post", return_value={"ok": True}) as trigger_controller_post:
                        with mock.patch.object(self.admin, "log_group_run") as log_group_run:
                            response = self.admin.api_admin_pause_group("ops")

        set_group_enabled.assert_called_once_with("ops", False)
        self.assertEqual(
            [call.args[0] for call in trigger_controller_post.call_args_list],
            ["/api/projects/fleet/pause", "/api/projects/hub/pause"],
        )
        log_group_run.assert_called_once()
        self.assertEqual(response.kwargs.get("status_code"), 303)

    def test_update_project_queue_normalizes_items_and_syncs_runtime(self) -> None:
        config = {
            "lanes": {},
            "projects": [
                {
                    "id": "fleet",
                    "enabled": True,
                    "queue": ["old item"],
                }
            ],
        }
        with mock.patch.object(self.admin, "normalize_config", return_value=config):
            with mock.patch.object(self.admin, "save_fleet_config") as save_fleet_config:
                with mock.patch.object(self.admin, "sync_project_queue_runtime") as sync_project_queue_runtime:
                    response = self.admin.api_admin_update_project_queue(
                        "fleet",
                        queue_items="first item\nsecond item",
                        cursor_mode="preserve",
                    )

        queue = config["projects"][0]["queue"]
        self.assertEqual([item["title"] for item in queue], ["first item", "second item"])
        save_fleet_config.assert_called_once_with(config)
        sync_project_queue_runtime.assert_called_once()
        self.assertEqual(response.kwargs.get("status_code"), 303)
