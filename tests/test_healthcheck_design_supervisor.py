from __future__ import annotations

import importlib.util
import io
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

    def test_loop_process_running_checks_container_when_host_process_is_missing(self) -> None:
        calls: list[list[str]] = []

        def fake_run(argv, **_kwargs):
            calls.append(list(argv))
            if argv[0] == "pgrep":
                return self.module.subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
            return self.module.subprocess.CompletedProcess(argv, 0, stdout="556\n624\n", stderr="")

        with mock.patch.object(self.module.subprocess, "run", side_effect=fake_run):
            ok, reason = self.module._loop_process_running()

        self.assertTrue(ok)
        self.assertEqual(reason, "loop_container_pids=556,624")
        self.assertEqual(calls[0], ["pgrep", "-f", self.module.LOOP_PATTERN])
        self.assertEqual(
            calls[1],
            [
                "docker",
                "compose",
                "exec",
                "-T",
                self.module.SUPERVISOR_SERVICE,
                "pgrep",
                "-f",
                self.module.LOOP_PATTERN,
            ],
        )

    def test_main_uses_local_default_state_root_and_watchdog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir)
            (state_root / "shard-1").mkdir()
            updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (state_root / "active_shards.json").write_text(
                json.dumps({"active_shards": [{"name": "shard-1"}]}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": updated_at,
                        "active_run": {
                            "run_id": "run_1",
                            "progress_state": "streaming",
                            "worker_last_output_at": updated_at,
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.module.DEFAULT_STATE_ROOT = state_root
            with mock.patch.object(self.module, "_loop_process_running", return_value=(True, "loop_pids=42")):
                with mock.patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(self.module.main(), 0)

    def test_main_renders_json_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir)
            (state_root / "shard-1").mkdir()
            updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (state_root / "active_shards.json").write_text(
                json.dumps({"active_shards": [{"name": "shard-1"}]}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": updated_at,
                        "active_run": {
                            "run_id": "run_1",
                            "progress_state": "streaming",
                            "worker_last_output_at": updated_at,
                        },
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "_loop_process_running", return_value=(True, "loop_pids=42")):
                with mock.patch.dict(os.environ, env, clear=False):
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                        self.assertEqual(self.module.main(["--json"]), 0)

            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["state_reason"].split()[0], "state_fresh=1/1")
            self.assertEqual(payload["watchdog_shard"], "shard-1")

    def test_main_reads_watchdog_values_from_runtime_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir) / "workspace"
            state_root = workspace_root / "state" / "chummer_design_supervisor"
            (state_root / "shard-1").mkdir(parents=True)
            updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            (workspace_root / "runtime.env").write_text(
                "\n".join(
                    [
                        "CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_MAX_SILENT_SECONDS=1800",
                        "CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_STARTUP_GRACE_SECONDS=1700",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (state_root / "active_shards.json").write_text(
                json.dumps({"active_shards": [{"name": "shard-1"}]}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": updated_at,
                        "active_run": {
                            "run_id": "run_1",
                            "progress_state": "streaming",
                            "worker_last_output_at": updated_at,
                        },
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "DEFAULT_WORKSPACE_ROOT", workspace_root):
                with mock.patch.object(self.module, "_loop_process_running", return_value=(True, "loop_pids=42")):
                    with mock.patch.dict(os.environ, env, clear=True):
                        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                            self.assertEqual(self.module.main(["--json"]), 0)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["watchdog_max_silent_seconds"], 1800)
            self.assertEqual(payload["watchdog_startup_grace_seconds"], 1700)

    def test_main_uses_longer_watchdog_window_for_state_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_root = Path(tmpdir) / "workspace"
            state_root = workspace_root / "state" / "chummer_design_supervisor"
            (state_root / "shard-1").mkdir(parents=True)
            updated_at = (datetime.now(timezone.utc) - timedelta(minutes=25)).strftime("%Y-%m-%dT%H:%M:%SZ")
            (workspace_root / "runtime.env").write_text(
                "CHUMMER_DESIGN_SUPERVISOR_WATCHDOG_MAX_SILENT_SECONDS=1800\n",
                encoding="utf-8",
            )
            (state_root / "active_shards.json").write_text(
                json.dumps({"active_shards": [{"name": "shard-1"}]}),
                encoding="utf-8",
            )
            (state_root / "shard-1" / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": updated_at,
                        "active_run": {
                            "run_id": "run_1",
                            "progress_state": "streaming",
                            "worker_last_output_at": updated_at,
                        },
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_HEALTH_MAX_AGE_SECONDS": "900",
            }
            with mock.patch.object(self.module, "DEFAULT_WORKSPACE_ROOT", workspace_root):
                with mock.patch.object(self.module, "_loop_process_running", return_value=(True, "loop_pids=42")):
                    with mock.patch.dict(os.environ, env, clear=True):
                        with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                            self.assertEqual(self.module.main(["--json"]), 0)

            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["configured_max_age_seconds"], 900)
            self.assertEqual(payload["max_age_seconds"], 1800)
            self.assertEqual(payload["state_reason"].split()[0], "state_fresh=1/1")


if __name__ == "__main__":
    unittest.main()
