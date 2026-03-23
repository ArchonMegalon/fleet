from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/quartermaster/app.py")


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

    class DummyResponse:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    fastapi.FastAPI = DummyFastAPI
    responses.PlainTextResponse = DummyResponse
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


def load_quartermaster_module():
    install_fastapi_stubs()
    spec = importlib.util.spec_from_file_location("test_quartermaster_service", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuartermasterServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.quartermaster = load_quartermaster_module()

    def test_status_payload_serves_cached_plan_without_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.quartermaster.CONFIG_PATH = root / "config" / "fleet.yaml"
            self.quartermaster.PLAN_CACHE_PATH = root / "state" / "quartermaster" / "latest_capacity_plan.json"
            self.quartermaster.PLAN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.quartermaster.PLAN_CACHE_PATH.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-03-23T10:00:00Z",
                        "source": "cached_plan",
                        "degraded": False,
                        "plan": {"lane_targets": {"core_booster": 1}},
                    }
                ),
                encoding="utf-8",
            )

            def _unexpected_admin_refresh():
                raise AssertionError("cached reads should not refresh admin status")

            self.quartermaster.admin_cockpit_status = _unexpected_admin_refresh

            payload = self.quartermaster.quartermaster_status_payload()

            self.assertEqual(payload["plan"]["lane_targets"]["core_booster"], 1)
            self.assertIn(payload["cache_state"], {"fresh", "stale"})

    def test_force_refresh_builds_plan_and_persists_tick_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.quartermaster.CONFIG_PATH = config_dir / "fleet.yaml"
            self.quartermaster.PLAN_CACHE_PATH = root / "state" / "quartermaster" / "latest_capacity_plan.json"
            (config_dir / "quartermaster.yaml").write_text(
                "quartermaster:\n  mode: enforce\n  driver: controller_tick\n",
                encoding="utf-8",
            )

            self.quartermaster.admin_cockpit_status = lambda: {
                "generated_at": "2026-03-23T10:00:00Z",
                "config": {"policies": {}, "projects": []},
                "projects": [],
                "groups": [],
                "cockpit": {
                    "summary": {},
                    "mission_board": {"provider_credit_card": {}},
                    "capacity_forecast": {},
                    "jury_telemetry": {},
                    "runway": {},
                },
            }

            payload = self.quartermaster.quartermaster_status_payload(force_refresh=True, tick_reason="baseline")
            cached = json.loads(self.quartermaster.PLAN_CACHE_PATH.read_text(encoding="utf-8"))

            self.assertEqual(payload["tick_reason"], "baseline")
            self.assertEqual(payload["plan"]["runtime_authority"]["driver"], "controller_tick")
            self.assertEqual(cached["tick_reason"], "baseline")


if __name__ == "__main__":
    unittest.main()
