from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


SHIM_PATH = Path("/docker/fleet/scripts/codex-shims/codexea")
BOOTSTRAP_PATH = Path("/docker/fleet/scripts/codex-shims/ea_interactive_bootstrap.md")


class CodexEaShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.capture_path = self.root / "capture.json"
        self.fake_codex = self.root / "codex-real"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'env': {",
                    "        'CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT': os.environ.get('CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT'),",
                    "        'CODEXEA_LANE': os.environ.get('CODEXEA_LANE'),",
                    "        'CODEXEA_SUBMODE': os.environ.get('CODEXEA_SUBMODE'),",
                    "        'EA_MCP_MODEL': os.environ.get('EA_MCP_MODEL'),",
                    "    },",
                    "}",
                    "with open(os.environ['CODEXEA_TEST_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(payload, handle)",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

    def run_shim(self, *args: str, extra_env: dict[str, str] | None = None) -> dict[str, object]:
        env = os.environ.copy()
        env.update(
            {
                "CODEXEA_REAL_CODEX": str(self.fake_codex),
                "CODEXEA_ROUTE_HELPER": str(self.root / "missing-route-helper.py"),
                "CODEXEA_BOOTSTRAP": "0",
                "CODEXEA_STARTUP_STATUS": "0",
                "CODEXEA_TEST_CAPTURE": str(self.capture_path),
                "HOME": str(self.root),
            }
        )
        if extra_env:
            env.update(extra_env)
        completed = subprocess.run(["bash", str(SHIM_PATH), *args], check=False, env=env, capture_output=True, text=True)
        payload = None
        if self.capture_path.exists():
            payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        return {"completed": completed, "payload": payload}

    def test_easy_prompt_is_locked_to_ea_easy_and_emits_trace(self) -> None:
        result = self.run_shim(
            "continue the slice",
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_BOOTSTRAP_PROMPT_FILE": str(BOOTSTRAP_PATH)},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn("-c", argv)
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-gemini-flash"', argv)
        self.assertIn('model_reasoning_effort="low"', argv)
        self.assertEqual(payload["env"]["CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT"], "1")
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_easy")
        self.assertIn("Trace: lane=easy provider=ea model=ea-gemini-flash mode=responses", completed.stderr)
        self.assertIn("AGENTS.md", argv[-1])
        self.assertIn("Trace:", argv[-1])

    def test_easy_rejects_model_and_profile_overrides(self) -> None:
        result = self.run_shim(
            "-p",
            "manual-profile",
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to EA easy", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_easy_rejects_spaced_config_model_provider_override(self) -> None:
        result = self.run_shim(
            "-c",
            'model_provider = "openai"',
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to EA easy", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_interactive_bootstrap_requires_trace_lines(self) -> None:
        text = BOOTSTRAP_PATH.read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", text)
        self.assertIn("Trace:", text)
        self.assertIn("20-45 seconds", text)


if __name__ == "__main__":
    unittest.main()
