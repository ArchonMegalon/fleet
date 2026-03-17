from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path("/docker/fleet/controller/app.py")


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

    fastapi.FastAPI = DummyFastAPI
    fastapi.HTTPException = DummyHTTPException
    fastapi.Request = DummyRequest
    responses.HTMLResponse = DummyResponse
    responses.PlainTextResponse = DummyResponse
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def load_controller_module():
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location("test_controller_routing", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ControllerRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = load_controller_module()

    def test_groundwork_keywords_promote_groundwork_lane(self) -> None:
        slice_item = {"title": "architecture tradeoff review for fleet routing"}
        lane_snapshot = {"state": "ready", "providers": []}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": lane_snapshot,
                        "repair": lane_snapshot,
                        "groundwork": lane_snapshot,
                        "core": lane_snapshot,
                        "survival": lane_snapshot,
                    },
                ):
                    decision = self.controller.classify_tier({}, {}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["tier"], "groundwork")
        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["lane_submode"], "responses_groundwork")
        self.assertEqual(decision["runtime_model"], "ea-groundwork")
        self.assertEqual(decision["allowed_lanes"][0], "groundwork")

    def test_explicit_groundwork_lane_policy_stays_off_core(self) -> None:
        slice_item = {
            "title": "status class vocabulary pass across fleet maturity labels",
            "difficulty": "medium",
            "risk_level": "medium",
            "allowed_lanes": ["groundwork", "easy", "repair", "core"],
        }
        lane_snapshot = {"state": "ready", "providers": []}

        with mock.patch.object(self.controller, "estimate_prompt_chars", return_value=4000):
            with mock.patch.object(self.controller, "route_class_evidence", return_value={}):
                with mock.patch.object(
                    self.controller,
                    "ea_lane_capacity_snapshot",
                    return_value={
                        "easy": lane_snapshot,
                        "repair": lane_snapshot,
                        "groundwork": lane_snapshot,
                        "core": lane_snapshot,
                        "survival": lane_snapshot,
                    },
                ):
                    decision = self.controller.classify_tier({}, {}, {"consecutive_failures": 0}, slice_item, [])

        self.assertEqual(decision["lane"], "groundwork")
        self.assertEqual(decision["lane_submode"], "responses_groundwork")
        self.assertEqual(decision["escalation_reason"], "groundwork_policy_default")


if __name__ == "__main__":
    unittest.main()
