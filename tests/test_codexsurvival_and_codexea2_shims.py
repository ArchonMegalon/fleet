from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


CODEXSURVIVAL_SHIM_PATH = Path("/docker/fleet/scripts/codex-shims/codexsurvival")
CODEXEA2_SHIM_PATH = Path("/docker/fleet/scripts/codex-shims/codexea2")


class CodexSurvivalShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.capture_path = self.root / "capture.jsonl"
        self.state_path = self.root / "state"
        self.fake_codex = self.root / "codex-real"
        self.fake_codex.write_text(
            textwrap.dedent(
                """
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from pathlib import Path

                capture_path = Path(os.environ["CODEXSURVIVAL_TEST_CAPTURE"])
                state_path = Path(os.environ["CODEXSURVIVAL_TEST_STATE"])
                payload = {
                    "argv": sys.argv[1:],
                    "stdin": sys.stdin.read(),
                    "env": {
                        "CODEX_WRAPPER_DISABLE_BOOTSTRAP": os.environ.get("CODEX_WRAPPER_DISABLE_BOOTSTRAP"),
                    },
                }
                with capture_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload) + "\\n")
                if os.environ.get("CODEXSURVIVAL_TEST_FAIL_UNSUPPORTED_ONCE") == "1" and not state_path.exists():
                    state_path.write_text("failed", encoding="utf-8")
                    print("unsupported_input_item:17", file=sys.stderr)
                    raise SystemExit(1)
                """
            ).lstrip(),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

    def _run_shim(
        self,
        *args: str,
        extra_env: dict[str, str] | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "CODEXSURVIVAL_REAL_CODEX": str(self.fake_codex),
                "CODEXSURVIVAL_TEST_CAPTURE": str(self.capture_path),
                "CODEXSURVIVAL_TEST_STATE": str(self.state_path),
                "CODEXSURVIVAL_BOOTSTRAP": "0",
                "HOME": str(self.root),
            }
        )
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(CODEXSURVIVAL_SHIM_PATH), *args],
            check=False,
            env=env,
            capture_output=True,
            text=True,
            input=input_text,
        )

    def _captured_payloads(self) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in self.capture_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_codexsurvival_wraps_bare_prompt_as_exec(self) -> None:
        completed = self._run_shim("repair the queue stall")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payloads = self._captured_payloads()
        self.assertEqual(len(payloads), 1)
        self.assertIn("exec", payloads[0]["argv"])
        self.assertIn("repair the queue stall", payloads[0]["argv"])
        self.assertEqual(payloads[0]["env"]["CODEX_WRAPPER_DISABLE_BOOTSTRAP"], "1")

    def test_codexsurvival_retries_unsupported_input_item_with_stdin_exec(self) -> None:
        completed = self._run_shim(
            "repair the queue stall",
            extra_env={"CODEXSURVIVAL_TEST_FAIL_UNSUPPORTED_ONCE": "1"},
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payloads = self._captured_payloads()
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["argv"][-2:], ["exec", "repair the queue stall"])
        self.assertEqual(payloads[1]["argv"][-2:], ["exec", "-"])
        self.assertEqual(payloads[1]["stdin"], "repair the queue stall")
        self.assertIn("compat=unsupported_input_item retry=stdin_exec", completed.stderr)


class CodexEa2ShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.codex_home = self.root / "codexea2-home"
        self.capture_path = self.root / "capture.json"
        self.fake_codexea = self.root / "codexea"
        self.fake_codexea.write_text(
            textwrap.dedent(
                """
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from pathlib import Path

                config_path = Path(os.environ["CODEX_HOME"]) / "config.toml"
                payload = {
                    "argv": sys.argv[1:],
                    "env": {
                        "CODEX_HOME": os.environ.get("CODEX_HOME"),
                        "CODEXEA_DEFAULT_LANE": os.environ.get("CODEXEA_DEFAULT_LANE"),
                    },
                    "config": config_path.read_text(encoding="utf-8"),
                }
                with open(os.environ["CODEXEA2_TEST_CAPTURE"], "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                """
            ).lstrip(),
            encoding="utf-8",
        )
        self.fake_codexea.chmod(self.fake_codexea.stat().st_mode | stat.S_IXUSR)

    def test_codexea2_writes_local_config_and_execs_configured_shim(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "CODEXEA2_CODEX_HOME": str(self.codex_home),
                "CODEXEA2_CODEXEA_BIN": str(self.fake_codexea),
                "CODEXEA2_TEST_CAPTURE": str(self.capture_path),
                "HOME": str(self.root),
            }
        )

        completed = subprocess.run(
            ["bash", str(CODEXEA2_SHIM_PATH), "eta? active shards?"],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["argv"], ["eta? active shards?"])
        self.assertEqual(payload["env"]["CODEX_HOME"], str(self.codex_home))
        self.assertEqual(payload["env"]["CODEXEA_DEFAULT_LANE"], "easy")
        self.assertIn('approval_policy = "never"', payload["config"])
        self.assertIn('[projects."/docker/fleet"]', payload["config"])
