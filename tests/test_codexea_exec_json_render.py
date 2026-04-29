from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RENDERER_PATH = Path("/docker/fleet/scripts/codexea_exec_json_render.py")


class CodexEaExecJsonRenderTests(unittest.TestCase):
    def test_repeated_passthrough_supervisor_status_lines_write_monitor_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            reason_path = Path(tempdir) / "reason.txt"
            line = (
                '/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status '
                "--state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c "
                '\'import json,sys; payload=json.load(sys.stdin) or {}; eta=payload.get("eta") or {}; '
                'out={"remaining_open_milestones":eta.get("remaining_open_milestones"),'
                '"eta_human":eta.get("eta_human")}; print(json.dumps(out))\'" in /docker/fleet'
            )
            payload = f"{line}\n{line}\n"
            env = os.environ.copy()
            env["CODEXEA_EXEC_JSON_MONITOR_REASON_FILE"] = str(reason_path)
            completed = subprocess.run(
                [sys.executable, str(RENDERER_PATH), "/docker/fleet"],
                input=payload,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(completed.returncode, 0)
            self.assertTrue(reason_path.exists())
            self.assertEqual(reason_path.read_text(encoding="utf-8").strip(), "supervisor_status_loop")

    def test_streams_first_repo_command_for_supervisor_run(self) -> None:
        payload = "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.started",
                        "item": {
                            "type": "command_execution",
                            "id": "cmd-1",
                            "command": "git -C /docker/fleet status --short -- scripts/codex-shims/codexea",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "id": "cmd-1",
                            "command": "git -C /docker/fleet status --short -- scripts/codex-shims/codexea",
                            "exit_code": 0,
                            "aggregated_output": "M scripts/codex-shims/codexea",
                        },
                    }
                ),
                "",
            ]
        )
        env = os.environ.copy()
        env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] = "/tmp/fleet-run"
        completed = subprocess.run(
            [sys.executable, str(RENDERER_PATH), "/docker/fleet"],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        self.assertEqual(completed.returncode, 0)
        stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(stdout_lines), 2)
        self.assertEqual(
            stdout_lines[0],
            "git -C /docker/fleet status --short -- scripts/codex-shims/codexea in /docker/fleet",
        )
        self.assertEqual(stdout_lines[1], "M scripts/codex-shims/codexea")


if __name__ == "__main__":
    unittest.main()
