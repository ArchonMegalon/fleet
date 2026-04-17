from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import threading
import textwrap
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SHIM_PATH = Path("/docker/fleet/scripts/codex-shims/codexea")
BOOTSTRAP_PATH = Path("/docker/fleet/scripts/codex-shims/ea_interactive_bootstrap.md")
DEFAULT_EASY_INTERACTIVE_MODEL = "onemin:gpt-5.4"


class CodexEaShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.capture_path = self.root / "capture.json"
        self.route_capture_path = self.root / "route-capture.json"
        self.fake_codex = self.root / "codex-real"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys, time",
                    "sleep_seconds = float(os.environ.get('CODEXEA_TEST_FAKE_CODEX_SLEEP', '0') or '0')",
                    "if sleep_seconds > 0:",
                    "    time.sleep(sleep_seconds)",
                    "if len(sys.argv) > 1 and sys.argv[1] == '--help':",
                    "    print('--skip-git-repo-check')",
                    "    print('--no-alt-screen')",
                    "    sys.exit(0)",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'stdin': sys.stdin.read(),",
                    "    'env': {",
                    "        'CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT': os.environ.get('CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT'),",
                    "        'CODEXEA_LANE': os.environ.get('CODEXEA_LANE'),",
                    "        'CODEXEA_SUBMODE': os.environ.get('CODEXEA_SUBMODE'),",
                    "        'CODEXEA_RESPONSES_AUTH_TOKEN': os.environ.get('CODEXEA_RESPONSES_AUTH_TOKEN'),",
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

    def run_shim(
        self,
        *args: str,
        extra_env: dict[str, str] | None = None,
        input_text: str | None = None,
    ) -> dict[str, object]:
        env = os.environ.copy()
        env.update(
            {
                "CODEXEA_REAL_CODEX": str(self.fake_codex),
                "CODEXEA_ROUTE_HELPER": str(self.root / "missing-route-helper.py"),
                "CODEXEA_BOOTSTRAP": "0",
                "CODEXEA_STARTUP_STATUS": "0",
                "CODEXEA_USE_LIVE_PROFILE_MODELS": "0",
                "CODEXEA_TEST_CAPTURE": str(self.capture_path),
                "EA_MCP_MODEL": "gemini-2.5-flash",
                "HOME": str(self.root),
            }
        )
        if extra_env:
            env.update(extra_env)
        completed = subprocess.run(
            ["bash", str(SHIM_PATH), *args],
            check=False,
            env=env,
            capture_output=True,
            text=True,
            input=input_text,
        )
        payload = None
        if self.capture_path.exists():
            payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        return {"completed": completed, "payload": payload}

    def write_route_helper(self) -> Path:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "with open(os.environ['CODEXEA_ROUTE_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(",
                    "        {",
                    "            'argv': sys.argv[1:],",
                    "            'env': {",
                    "                'CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS': os.environ.get('CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS', ''),",
                    "                'CODEXEA_ONEMIN_PROBE_TIMEOUT_SECONDS': os.environ.get('CODEXEA_ONEMIN_PROBE_TIMEOUT_SECONDS', ''),",
                    "            },",
                    "        },",
                    "        handle,",
                    "    )",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)
        return route_helper

    def write_fake_script(self, support_tty_wrapper: bool, capture_path: Path) -> Path:
        script = self.root / "script"
        help_lines = ["--command", "--return"] if support_tty_wrapper else ["--foo"]
        script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "capture_file=\"${SCRIPT_HELP_CAPTURE}\"",
                    "if [ \"${1-}\" = \"--help\" ]; then",
                    "  " + "\n  ".join([f'  printf "%s\\n" "{line}"' for line in help_lines]),
                    "  " + "\n  ".join([f'  printf "%s\\n" "{line}" >> "${{capture_file}}"' for line in help_lines]),
                    "  exit 0",
                    "fi",
                    'if [ -n "${capture_file:-}" ]; then',
                    '  printf "%s\\n" "$*" >> "${capture_file}"',
                    "fi",
                    "cmd=""",
                    "while [ \"$#\" -gt 0 ]; do",
                    "  if [ \"$1\" = \"--command\" ]; then",
                    "    shift",
                    "    cmd=\"${1-}\"",
                    "    break",
                    "  fi",
                    "  shift",
                    "done",
                    "if [ -n \"${cmd}\" ]; then",
                    "  eval \"${cmd}\"",
                    "fi",
                ]
            ),
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def write_executable(self, path: Path, content: str) -> Path:
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def test_easy_prompt_is_locked_to_ea_easy_without_wrapper_trace_by_default(self) -> None:
        result = self.run_shim("continue the slice")

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn("exec", argv)
        self.assertIn("-c", argv)
        self.assertNotIn("", argv)
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-coder-fast"', argv)
        self.assertIn('model_reasoning_effort="low"', argv)
        self.assertNotIn("--no-alt-screen", argv)
        self.assertEqual(payload["env"]["CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT"], "1")
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        self.assertFalse(any("AGENTS.md" in arg for arg in argv))
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_prompt_session_does_not_inject_bootstrap_waiting_prompt(self) -> None:
        prompt_file = self.root / "bootstrap.md"
        prompt_file.write_text(
            "SENTINEL_BOOTSTRAP_WAITING_PROMPT",
            encoding="utf-8",
        )

        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_BOOTSTRAP_PROMPT_FILE": str(prompt_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertFalse(any("SENTINEL_BOOTSTRAP_WAITING_PROMPT" in arg for arg in payload["argv"]))

    def test_prompt_session_injects_exec_trace_prompt(self) -> None:
        trace_file = self.root / "exec-trace.md"
        trace_file.write_text(
            "SENTINEL_EXEC_TRACE_PROMPT",
            encoding="utf-8",
        )

        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_EXEC_TRACE_PROMPT_FILE": str(trace_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("SENTINEL_EXEC_TRACE_PROMPT", payload["argv"][-1])
        self.assertIn("eta of the fleet? is it running? the shards?", payload["argv"][-1])

    def test_prompt_session_emits_waiting_trace_while_provider_is_quiet(self) -> None:
        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "0.25",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Trace: lane=easy waiting for model output", completed.stderr)

    def test_noarg_non_tty_stdin_is_treated_as_prompt_session(self) -> None:
        result = self.run_shim(
            extra_env={"CODEXEA_BOOTSTRAP": "1"},
            input_text="fleet stdin prompt",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("fleet stdin prompt", payload["argv"][-1])
        self.assertNotIn("--interactive", payload["argv"])
        self.assertIn("--skip-git-repo-check", payload["argv"])

    def test_interactive_flag_non_tty_without_prompt_falls_back_to_exec(self) -> None:
        result = self.run_shim(
            "--interactive",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "0.05",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("exec", payload["argv"])
        self.assertNotIn("--interactive", payload["argv"])
        self.assertIn('model_provider="ea"', payload["argv"])
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_noarg_non_tty_stdin_prompt_preserved_with_heartbeat_trace(self) -> None:
        result = self.run_shim(
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_BOOTSTRAP": "0",
            },
            input_text="fleet stdin prompt",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session", completed.stderr)
        self.assertEqual(payload["stdin"], "fleet stdin prompt")
        self.assertIn("fleet stdin prompt", payload["argv"][-1])

    def test_exec_session_waiting_trace_preserves_stdin_prompt(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "-",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "0.25",
            },
            input_text="fleet worker stdin prompt",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["stdin"], "fleet worker stdin prompt")
        self.assertIn("Trace: lane=core waiting for model output", completed.stderr)

    def test_prompt_session_bootstrap_zero_disables_exec_trace_injection(self) -> None:
        trace_file = self.root / "exec-trace.md"
        trace_file.write_text(
            "SENTINEL_EXEC_TRACE_PROMPT",
            encoding="utf-8",
        )

        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_BOOTSTRAP": "0",
                "CODEXEA_EXEC_TRACE_PROMPT_FILE": str(trace_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn("SENTINEL_EXEC_TRACE_PROMPT", payload["argv"][-1])

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
                "CODEXEA_TRACE_STARTUP": "1",
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
        self.assertFalse(any(arg == 'model="gemini-2.5-flash"' for arg in argv))
        self.assertEqual(live_payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_easy_profile_model_is_fenced_to_one_minai(self) -> None:
        payload = {
            "profiles": [
                {"profile": "easy", "model": "ea-gemini-flash"},
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
                "CODEXEA_TRACE_STARTUP": "1",
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
        self.assertIn('model="ea-coder-fast"', argv)
        self.assertNotIn('model="ea-gemini-flash"', argv)
        self.assertEqual(live_payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_invalid_easy_model_env_var_is_fenced_to_default_one_minai(self) -> None:
        result = self.run_shim(
            "continue the slice",
            extra_env={
                "CODEXEA_EASY_MODEL": "non-1min-model",
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        live_payload = result["payload"]
        self.assertIsNotNone(live_payload)
        self.assertEqual(completed.returncode, 0)
        argv = live_payload["argv"]
        self.assertIn("exec", argv)
        self.assertIn('model="ea-coder-fast"', argv)
        self.assertNotIn('model="non-1min-model"', argv)
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_repair_prefers_live_repair_profile_model_when_available(self) -> None:
        payload = {
            "profiles": [
                {"profile": "easy", "model": "ea-coder-fast"},
                {"profile": "repair", "model": "ea-repair-gemini"},
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
            "repair",
            "continue the slice",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
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
        self.assertIn('model="ea-repair-gemini"', argv)
        self.assertEqual(live_payload["env"]["CODEXEA_LANE"], "repair")
        self.assertEqual(live_payload["env"]["CODEXEA_SUBMODE"], "responses_fast")

    def test_status_uses_runtime_env_file_for_live_auth(self) -> None:
        observed: dict[str, str] = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                observed["path"] = self.path
                observed["auth"] = str(self.headers.get("Authorization") or "")
                observed["principal"] = str(self.headers.get("X-EA-Principal-ID") or "")
                body = json.dumps({"providers_summary": []}).encode("utf-8")
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

        runtime_env_path = self.root / "runtime.ea.env"
        runtime_env_path.write_text(
            "\n".join(
                [
                    f"EA_MCP_BASE_URL=http://127.0.0.1:{server.server_port}",
                    "EA_MCP_API_TOKEN=shim-file-token",
                    "EA_MCP_PRINCIPAL_ID=shim-file-principal",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "CODEXEA_RUNTIME_EA_ENV_PATH": str(runtime_env_path),
                "EA_MCP_BASE_URL": "",
                "EA_MCP_API_TOKEN": "",
                "EA_API_TOKEN": "",
                "EA_MCP_PRINCIPAL_ID": "",
                "EA_PRINCIPAL_ID": "",
                "CODEXEA_STATUS_URL": "",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn('"providers_summary": []', completed.stdout)
        self.assertEqual(observed["auth"], "Bearer shim-file-token")
        self.assertEqual(observed["principal"], "shim-file-principal")
        self.assertEqual(observed["path"], "/v1/codex/status?window=1h&refresh=0")

    def test_status_rewrites_host_docker_internal_when_unresolved(self) -> None:
        observed: dict[str, str] = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                observed["path"] = self.path
                body = json.dumps({"providers_summary": []}).encode("utf-8")
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

        runtime_env_path = self.root / "runtime.ea.env"
        runtime_env_path.write_text(
            f"EA_MCP_BASE_URL=http://host.docker.internal:{server.server_port}\n",
            encoding="utf-8",
        )
        fake_getent = self.root / "getent"
        fake_getent.write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8")
        fake_getent.chmod(fake_getent.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "CODEXEA_RUNTIME_EA_ENV_PATH": str(runtime_env_path),
                "EA_MCP_BASE_URL": "",
                "CODEXEA_STATUS_URL": "",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn('"providers_summary": []', completed.stdout)
        self.assertEqual(observed["path"], "/v1/codex/status?window=1h&refresh=0")

    def test_status_reports_missing_api_token_when_live_auth_is_unconfigured(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(401)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        runtime_env_path = self.root / "runtime.ea.env"
        runtime_env_path.write_text(
            f"EA_MCP_BASE_URL=http://127.0.0.1:{server.server_port}\n",
            encoding="utf-8",
        )

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "CODEXEA_RUNTIME_EA_ENV_PATH": str(runtime_env_path),
                "EA_MCP_BASE_URL": "",
                "EA_MCP_API_TOKEN": "",
                "EA_API_TOKEN": "",
                "CODEXEA_STATUS_URL": "",
                "CODEXEA_PROFILES_URL": "",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 1)
        self.assertIn("EA_MCP_API_TOKEN / EA_API_TOKEN is not configured", completed.stderr)

    def test_easy_rejects_model_and_profile_overrides(self) -> None:
        result = self.run_shim(
            "-p",
            "manual-profile",
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to EA responses easy", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_easy_rejects_spaced_config_model_provider_override(self) -> None:
        result = self.run_shim(
            "-c",
            'model_provider = "openai"',
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to EA responses easy", completed.stderr)
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
            extra_env={"CODEXEA_LANE": "jury", "CODEXEA_TRACE_STARTUP": "1"},
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

    def test_core_lane_defaults_to_batch_model_when_core_batch_profile_is_configured(self) -> None:
        result = self.run_shim(
            "fix the routing bug",
            extra_env={
                "CODEXEA_LANE": "core",
                "CODEXEA_CORE_RESPONSES_PROFILE": "core_batch",
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-coder-hard-batch"', argv)
        self.assertTrue(any('X-EA-Codex-Profile"="core_batch"' in arg for arg in argv))
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_core_batch")
        self.assertIn(
            "Trace: lane=core provider=ea model=ea-coder-hard-batch mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_core_rescue_lane_uses_rescue_profile_and_model(self) -> None:
        result = self.run_shim(
            "finish the long-running desktop slice",
            extra_env={"CODEXEA_LANE": "core_rescue", "CODEXEA_TRACE_STARTUP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-coder-hard-rescue"', argv)
        self.assertTrue(any('X-EA-Codex-Profile"="core_rescue"' in arg for arg in argv))
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core_rescue")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_core_rescue")
        self.assertIn(
            "Trace: lane=core_rescue provider=ea model=ea-coder-hard-rescue mode=responses next=start_exec_session",
            completed.stderr,
        )

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
            extra_env={
                "CODEXEA_LANE": "groundwork",
                "CODEXEA_MODE": "mcp",
                "CODEXEA_TRACE_STARTUP": "1",
            },
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
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_easy")
        self.assertNotIn("--interactive", payload["argv"])
        self.assertIn('model_provider="ea"', payload["argv"])
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_tmux_interactive_session_uses_script_tty_wrapper_when_supported(self) -> None:
        script_capture = self.root / "script-capture.txt"
        self.write_fake_script(True, script_capture)

        result = self.run_shim(
            "--interactive",
            "investigate architecture",
            extra_env={
                "TMUX": "/tmp/tmux-1000/test,19062,0",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
                "SCRIPT_HELP_CAPTURE": str(script_capture),
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        if script_capture.exists():
            script_lines = script_capture.read_text(encoding="utf-8").splitlines()
            self.assertTrue(
                any("--quiet" in entry for entry in script_lines),
                "\n".join(script_lines),
            )
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_tmux_interactive_session_skips_script_wrapper_without_support(self) -> None:
        script_capture = self.root / "script-capture.txt"
        self.write_fake_script(False, script_capture)

        result = self.run_shim(
            "--interactive",
            "investigate architecture",
            extra_env={
                "TMUX": "/tmp/tmux-1000/test,19062,0",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
                "SCRIPT_HELP_CAPTURE": str(script_capture),
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        if script_capture.exists():
            self.assertFalse(
                any(
                    "--command" in entry and "--return" in entry
                    for entry in script_capture.read_text(encoding="utf-8").splitlines()
                ),
                "wrapper should not be used when script --help lacks required options",
            )
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_interactive_flag_with_prompt_stays_interactive(self) -> None:
        result = self.run_shim("--interactive", "investigate architecture")

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_easy")
        self.assertNotIn("--interactive", payload["argv"])
        self.assertEqual(payload["argv"].count("exec"), 0)
        self.assertIn('model_provider="ea"', payload["argv"])
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        self.assertEqual(payload["argv"][-1], "investigate architecture")
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

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

    def test_bare_bootstrap_session_starts_empty_interactive_without_injecting_prompt_file(self) -> None:
        prompt_file = self.root / "bootstrap.md"
        prompt_file.write_text(
            "Trace: lane easy ready and waiting.\nWait for the next user instruction.\n",
            encoding="utf-8",
        )

        result = self.run_shim(
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_BOOTSTRAP_PROMPT_FILE": str(prompt_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn(prompt_file.read_text(encoding="utf-8").rstrip("\n"), payload["argv"])
        self.assertNotIn("continue the next unfinished slice", " ".join(payload["argv"]).lower())
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=",
            completed.stderr,
        )
        self.assertTrue(
            "start_exec_session" in completed.stderr
            or "start_interactive_session" in completed.stderr
        )

    def test_interactive_flag_can_route_away_from_easy_when_opted_in(self) -> None:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "print('lane=groundwork')",
                    "print('submode=responses_groundwork')",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "--interactive",
            "investigate architecture",
            extra_env={
                "CODEXEA_INTERACTIVE_ALWAYS_EASY": "0",
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "groundwork")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_groundwork")
        self.assertNotIn("--interactive", payload["argv"])
        self.assertEqual(payload["argv"].count("exec"), 0)
        self.assertIn('model="ea-groundwork-gemini"', payload["argv"])
        self.assertIn(
            "Trace: lane=groundwork provider=ea model=ea-groundwork-gemini mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_credits_keeps_standard_billing_route_flags(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "credits",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        argv = json.loads(self.route_capture_path.read_text(encoding="utf-8"))["argv"]
        self.assertEqual(argv[:2], ["--onemin-aggregate", "--billing"])
        self.assertNotIn("--billing-full-refresh", argv)

    def test_credits_enforces_default_billing_timeout_when_not_set(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "credits",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
                "CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS": "",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(self.route_capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["env"]["CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS"], "30")

    def test_onemin_keeps_standard_billing_route_flags(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "onemin",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        argv = json.loads(self.route_capture_path.read_text(encoding="utf-8"))["argv"]
        self.assertEqual(argv[:2], ["--onemin-aggregate", "--billing"])
        self.assertNotIn("--billing-full-refresh", argv)

    def test_credits_preserves_manual_billing_full_refresh_flag(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "credits",
            "--billing-full-refresh",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        argv = json.loads(self.route_capture_path.read_text(encoding="utf-8"))["argv"]
        self.assertEqual(argv[:3], ["--onemin-aggregate", "--billing", "--billing-full-refresh"])

    def test_explicit_exec_subcommand_is_not_double_wrapped(self) -> None:
        result = self.run_shim(
            "exec",
            "summarize recent commits",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn("", payload["argv"])
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

    def test_resume_subcommand_with_session_id_stays_passthrough(self) -> None:
        result = self.run_shim(
            "resume",
            "uid123",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("resume"), 1)
        self.assertIn("uid123", payload["argv"])
        self.assertIn("--no-alt-screen", payload["argv"])
        self.assertIn("next=start_resume_session", completed.stderr)

    def test_resume_subcommand_with_session_id_and_prompt_stays_passthrough(self) -> None:
        result = self.run_shim(
            "resume",
            "uid123",
            "continue fixing fleet",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("resume"), 1)
        self.assertIn("uid123", payload["argv"])
        self.assertIn("continue fixing fleet", payload["argv"])
        self.assertFalse(any("AGENTS.md" in arg for arg in payload["argv"]))

    def test_exec_keeps_responses_auth_token_out_of_argv(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "say ok",
            extra_env={
                "CODEXEA_CLEAN_EXEC_OUTPUT": "0",
                "CODEXEA_DISABLE_SCRIPT_WRAPPER": "1",
                "EA_API_TOKEN": "super-secret-token",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        argv = payload["argv"]
        self.assertFalse(any("super-secret-token" in arg for arg in argv))
        self.assertFalse(any("Authorization" in arg for arg in argv))
        self.assertIn('model_providers.ea.bearer_token_env_var="CODEXEA_RESPONSES_AUTH_TOKEN"', argv)
        self.assertIn(
            'model_providers.ea.env_http_headers={"x-api-token"="CODEXEA_RESPONSES_AUTH_TOKEN","X-EA-Api-Token"="CODEXEA_RESPONSES_AUTH_TOKEN"}',
            argv,
        )
        self.assertEqual(payload["env"]["CODEXEA_RESPONSES_AUTH_TOKEN"], "super-secret-token")

    def test_status_uses_curl_config_for_auth_headers(self) -> None:
        curl_path = self.write_executable(
            self.root / "curl",
            """#!/usr/bin/env bash
            set -euo pipefail
            config_path=""
            args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
              if [ "${args[$i]}" = "-K" ] && [ $((i + 1)) -lt ${#args[@]} ]; then
                config_path="${args[$((i + 1))]}"
                break
              fi
            done
            python3 -c 'import json, pathlib, sys; config_path = sys.argv[1]; config_text = pathlib.Path(config_path).read_text(encoding="utf-8") if config_path else ""; print(json.dumps({"argv": sys.argv[2:], "config_path": config_path, "config_text": config_text}))' "$config_path" "$@"
            """,
        )

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "EA_MCP_API_TOKEN": "status-secret-token",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        argv = payload["argv"]
        self.assertTrue(curl_path.exists())
        self.assertIn("-K", argv)
        self.assertFalse(any("status-secret-token" in arg for arg in argv))
        self.assertIn("Authorization: Bearer status-secret-token", payload["config_text"])
        self.assertIn("X-EA-Api-Token: status-secret-token", payload["config_text"])
        self.assertIn("X-API-Token: status-secret-token", payload["config_text"])
        self.assertFalse(Path(payload["config_path"]).exists())

    def test_interactive_bootstrap_requires_trace_lines(self) -> None:
        text = BOOTSTRAP_PATH.read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", text)
        self.assertIn("Trace:", text)
        self.assertIn("20-45 seconds", text)


if __name__ == "__main__":
    unittest.main()
