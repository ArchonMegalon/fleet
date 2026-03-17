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
        subprocess.run(["bash", str(SHIM_PATH), *args], check=True, env=env, capture_output=True, text=True)
        return json.loads(self.capture_path.read_text(encoding="utf-8"))

    def test_base_profile_is_injected_for_mcp_runs(self) -> None:
        payload = self.run_shim(
            "easy",
            "continue the slice",
            extra_env={"CODEXEA_BASE_PROFILE": "gemini-local"},
        )

        argv = payload["argv"]
        self.assertIn("-p", argv)
        self.assertEqual(argv[argv.index("-p") + 1], "gemini-local")
        self.assertEqual(payload["env"]["CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT"], "1")
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "mcp")

    def test_explicit_profile_wins_over_codexea_base_profile(self) -> None:
        payload = self.run_shim(
            "easy",
            "-p",
            "manual-profile",
            "continue the slice",
            extra_env={"CODEXEA_BASE_PROFILE": "gemini-local"},
        )

        argv = payload["argv"]
        self.assertEqual(argv.count("-p"), 1)
        self.assertEqual(argv[argv.index("-p") + 1], "manual-profile")
        self.assertNotIn("gemini-local", argv)

    def test_interactive_bootstrap_requires_trace_lines(self) -> None:
        text = BOOTSTRAP_PATH.read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", text)
        self.assertIn("Trace:", text)
        self.assertIn("20-45 seconds", text)


if __name__ == "__main__":
    unittest.main()
