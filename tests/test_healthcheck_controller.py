from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


MODULE_PATH = Path("/docker/fleet/scripts/healthcheck_controller.py")


def load_module():
    spec = importlib.util.spec_from_file_location("test_healthcheck_controller", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HealthcheckControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_http_failure_with_fresh_heartbeat_is_unhealthy_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            heartbeat_path = Path(tmpdir) / "controller-heartbeat.json"
            updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            heartbeat_path.write_text(json.dumps({"updated_at": updated_at}), encoding="utf-8")
            env = {
                "FLEET_CONTROLLER_HEALTH_URL": "http://127.0.0.1:8090/health",
                "FLEET_CONTROLLER_HEARTBEAT_PATH": str(heartbeat_path),
                "FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS": "45",
            }
            with mock.patch.object(self.module, "_http_health_ok", return_value=(False, "http_error=refused")):
                with mock.patch.dict(os.environ, env, clear=False):
                    self.assertEqual(self.module.main(), 1)

    def test_http_failure_with_fresh_heartbeat_can_be_opted_back_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            heartbeat_path = Path(tmpdir) / "controller-heartbeat.json"
            updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            heartbeat_path.write_text(json.dumps({"updated_at": updated_at}), encoding="utf-8")
            env = {
                "FLEET_CONTROLLER_HEALTH_URL": "http://127.0.0.1:8090/health",
                "FLEET_CONTROLLER_HEARTBEAT_PATH": str(heartbeat_path),
                "FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS": "45",
                "FLEET_CONTROLLER_HEALTH_ALLOW_HEARTBEAT_ONLY": "1",
            }
            with mock.patch.object(self.module, "_http_health_ok", return_value=(False, "http_error=refused")):
                with mock.patch.dict(os.environ, env, clear=False):
                    self.assertEqual(self.module.main(), 0)


if __name__ == "__main__":
    unittest.main()
