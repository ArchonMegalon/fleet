from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/studio/app.py")


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
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def load_studio_module():
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location("test_studio_publish_contract", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StudioPublishContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.studio = load_studio_module()

    def test_safe_relative_publish_path_allows_workpackages_overlay(self) -> None:
        rel = self.studio.safe_relative_publish_path(".codex-studio/published/WORKPACKAGES.generated.yaml")

        self.assertEqual(rel.as_posix(), "WORKPACKAGES.generated.yaml")

    def test_compile_manifest_payload_marks_workpackages_as_dispatchable_truth(self) -> None:
        payload = self.studio.compile_manifest_payload(
            {
                "target_type": "project",
                "target_id": "fleet",
                "project_cfg": {"lifecycle": "dispatchable"},
            },
            [
                {"path": "WORKPACKAGES.generated.yaml", "content": "work_packages: []\n"},
            ],
        )

        self.assertTrue(payload["stages"]["policy_compile"])
        self.assertTrue(payload["stages"]["execution_compile"])
        self.assertTrue(payload["stages"]["package_compile"])
        self.assertTrue(payload["stages"]["capacity_compile"])
        self.assertTrue(payload["dispatchable_truth_ready"])


if __name__ == "__main__":
    unittest.main()
