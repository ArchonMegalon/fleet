from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


MODULE_PATH = Path("/docker/fleet/scripts/healthcheck_design_supervisor.py")


def load_module():
    spec = importlib.util.spec_from_file_location("test_healthcheck_design_supervisor", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HealthcheckDesignSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_main_accepts_recent_shard_state_when_loop_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir)
            (state_root / "shard-1").mkdir()
            updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (state_root / "active_shards.json").write_text(
                json.dumps({"active_shards": [{"name": "shard-1"}]}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps({"updated_at": updated_at, "active_run": {"worker_last_output_at": updated_at}}),
                encoding="utf-8",
            )
            env = {
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "_loop_process_running", return_value=(True, "loop_pids=42")):
                with mock.patch.dict(os.environ, env, clear=False):
                    self.assertEqual(self.module.main(), 0)

    def test_main_rejects_stale_shard_state_even_when_loop_process_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir)
            (state_root / "shard-1").mkdir()
            updated_at = (datetime.now(timezone.utc) - timedelta(minutes=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
            (state_root / "active_shards.json").write_text(
                json.dumps({"active_shards": [{"name": "shard-1"}]}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps({"updated_at": updated_at}),
                encoding="utf-8",
            )
            env = {
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "_loop_process_running", return_value=(True, "loop_pids=42")):
                with mock.patch.dict(os.environ, env, clear=False):
                    self.assertEqual(self.module.main(), 1)

    def test_main_rejects_missing_loop_process_even_with_fresh_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir)
            updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (state_root / "state.json").write_text(json.dumps({"updated_at": updated_at}), encoding="utf-8")
            env = {
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "_loop_process_running", return_value=(False, "loop_process_missing")):
                with mock.patch.dict(os.environ, env, clear=False):
                    self.assertEqual(self.module.main(), 1)


if __name__ == "__main__":
    unittest.main()
