from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
                "CODEXEA_USE_LIVE_PROFILE_MODELS": "0",
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
        self.assertIn("exec", argv)
        self.assertIn("-c", argv)
        self.assertNotIn('model_provider="ea"', argv)
        self.assertIn('model="gemini-3-flash-preview"', argv)
        self.assertIn('model_reasoning_effort="low"', argv)
        self.assertNotIn("--no-alt-screen", argv)
        self.assertEqual(payload["env"]["CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT"], "1")
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "mcp")
        self.assertEqual(payload["env"]["EA_MCP_MODEL"], "gemini-3-flash-preview")
        self.assertIn("Trace: lane=easy provider=mcp model=gemini-3-flash-preview mode=mcp next=start_exec_session", completed.stderr)
        self.assertIn("AGENTS.md", argv[-1])
        self.assertIn("Trace:", argv[-1])

    def test_easy_prefers_live_profile_model_when_available(self) -> None:
        payload = {
            "profiles": [
                {"profile": "easy", "model": "ea-coder-fast"},
                {"profile": "audit", "model": "ea-audit-jury"},
            ]
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        result = self.run_shim(
            "continue the slice",
            extra_env={
                "CODEXEA_USE_LIVE_PROFILE_MODELS": "1",
                "CODEXEA_PROFILES_URL": f"http://127.0.0.1:{server.server_port}/v1/codex/profiles",
            },
        )

        completed = result["completed"]
        live_payload = result["payload"]
        self.assertIsNotNone(live_payload)
        self.assertEqual(completed.returncode, 0)
        argv = live_payload["argv"]
        self.assertIn("exec", argv)
        self.assertIn('model="gemini-3-flash-preview"', argv)
        self.assertEqual(live_payload["env"]["CODEXEA_SUBMODE"], "mcp")
        self.assertIn("Trace: lane=easy provider=mcp model=gemini-3-flash-preview mode=mcp next=start_exec_session", completed.stderr)

    def test_easy_rejects_model_and_profile_overrides(self) -> None:
        result = self.run_shim(
            "-p",
            "manual-profile",
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to MCP easy", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_easy_rejects_spaced_config_model_provider_override(self) -> None:
        result = self.run_shim(
            "-c",
            'model_provider = "openai"',
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to MCP easy", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_easy_rejects_mode_override_without_debug_flag(self) -> None:
        result = self.run_shim(
            "continue the slice",
            extra_env={"CODEXEA_MODE": "mcp"},
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("CODEXEA_MODE override is disabled", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_explicit_jury_lane_uses_audit_profile(self) -> None:
        result = self.run_shim(
            "review the release packet",
            extra_env={"CODEXEA_LANE": "jury"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-audit-jury"', argv)
        self.assertIn('model_reasoning_effort="medium"', argv)
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "jury")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_audit")
        self.assertIn("Trace: lane=jury provider=ea model=ea-audit-jury mode=responses next=start_exec_session", completed.stderr)

    def test_prompt_preserves_global_flags_before_exec(self) -> None:
        result = self.run_shim(
            "--search",
            "summarize recent commits",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)

        argv = payload["argv"]
        self.assertIn("--search", argv)
        self.assertIn("exec", argv)
        self.assertLess(argv.index("--search"), argv.index("exec"))

    def test_non_easy_mcp_override_emits_truthful_provider_trace(self) -> None:
        result = self.run_shim(
            "investigate architecture",
            extra_env={"CODEXEA_LANE": "groundwork", "CODEXEA_MODE": "mcp"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        argv = payload["argv"]
        self.assertIn('model="ea-groundwork-gemini"', argv)
        self.assertNotIn('model_provider="ea"', argv)
        self.assertIn("Trace: lane=groundwork provider=mcp model=ea-groundwork-gemini mode=mcp next=start_exec_session", completed.stderr)

    def test_interactive_flag_stays_interactive(self) -> None:
        result = self.run_shim("--interactive")

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)
        self.assertNotIn("--interactive", payload["argv"])
        self.assertIn("Trace: lane=easy provider=mcp model=gemini-3-flash-preview mode=mcp next=start_interactive_session", completed.stderr)

    def test_interactive_flag_skips_route_helper_telemetry_path(self) -> None:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import sys",
                    "raise SystemExit(9)",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "--interactive",
            extra_env={"CODEXEA_ROUTE_HELPER": str(route_helper)},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn("--interactive", payload["argv"])

    def test_explicit_exec_subcommand_is_not_double_wrapped(self) -> None:
        result = self.run_shim(
            "exec",
            "summarize recent commits",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("exec"), 1)
        self.assertNotIn("--no-alt-screen", payload["argv"])

    def test_resume_subcommand_stays_passthrough_under_bootstrap(self) -> None:
        result = self.run_shim(
            "resume",
            "--last",
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_BOOTSTRAP_PROMPT_FILE": str(BOOTSTRAP_PATH)},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("resume"), 1)
        self.assertFalse(any("AGENTS.md" in arg for arg in payload["argv"]))

    def test_interactive_bootstrap_requires_trace_lines(self) -> None:
        text = BOOTSTRAP_PATH.read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", text)
        self.assertIn("Trace:", text)
        self.assertIn("20-45 seconds", text)


if __name__ == "__main__":
    unittest.main()
