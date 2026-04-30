from __future__ import annotations

import json
import os
import signal
import socket
import stat
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SHIM_PATH = Path("/docker/fleet/scripts/codex-shims/codexliz")


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class CodexLizShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.capture_path = self.root / "capture.json"
        self.state_dir = self.root / "state"
        self.proxy_pid_file = self.state_dir / "proxy.pid"
        self.proxy_log_file = self.state_dir / "proxy.log"
        self.proxy_port_file = self.state_dir / "proxy.port"
        self.fake_codex = self.root / "codex"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'stdin': sys.stdin.read(),",
                    "    'env': {",
                    "        'HOME': os.environ.get('HOME'),",
                    "        'CODEX_HOME': os.environ.get('CODEX_HOME'),",
                    "        'CODEXLIZ_PROXY_PORT': os.environ.get('CODEXLIZ_PROXY_PORT'),",
                    "        'CODEXLIZ_STATE_DIR': os.environ.get('CODEXLIZ_STATE_DIR'),",
                    "        'CODEX_WRAPPER_DISABLE_BOOTSTRAP': os.environ.get('CODEX_WRAPPER_DISABLE_BOOTSTRAP'),",
                    "        'CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT': os.environ.get('CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT'),",
                    "    },",
                    "}",
                    "with open(os.environ['CODEXLIZ_TEST_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(payload, handle)",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)
        self.addCleanup(self._cleanup_proxy)

    def _cleanup_proxy_file(self, pid_path: Path) -> None:
        if not pid_path.exists():
            return
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            return
        if pid <= 0:
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return

    def _cleanup_proxy(self) -> None:
        self._cleanup_proxy_file(self.proxy_pid_file)

    def _run_shim(
        self,
        upstream_url: str,
        *,
        model: str = "qwen2.5-coder:32b",
        state_dir: Path | None = None,
        capture_path: Path | None = None,
        proxy_pid_file: Path | None = None,
        proxy_log_file: Path | None = None,
        include_proxy_port: bool = True,
        extra_args: list[str] | None = None,
        extra_env: dict[str, str] | None = None,
        default_prompt: str | None = "repair the queue stall",
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        active_state_dir = state_dir or self.state_dir
        active_capture_path = capture_path or self.capture_path
        active_proxy_pid_file = proxy_pid_file or self.proxy_pid_file
        active_proxy_log_file = proxy_log_file or self.proxy_log_file
        env = os.environ.copy()
        env.update(
            {
                "CODEXLIZ_BASE_CODEX_SHIM": str(self.fake_codex),
                "CODEXLIZ_TEST_CAPTURE": str(active_capture_path),
                "CODEXLIZ_BASE_URL": upstream_url,
                "CODEXLIZ_MODEL": model,
                "CODEXLIZ_STATE_DIR": str(active_state_dir),
                "CODEXLIZ_PROXY_PID_FILE": str(active_proxy_pid_file),
                "CODEXLIZ_PROXY_LOG_FILE": str(active_proxy_log_file),
                "HOME": str(self.root),
            }
        )
        if extra_env:
            env.update(extra_env)
        if include_proxy_port:
            env["CODEXLIZ_PROXY_PORT"] = str(_pick_free_port())
        args = ["bash", str(SHIM_PATH)]
        if extra_args:
            args.extend(extra_args)
        if default_prompt is not None:
            args.append(default_prompt)
        return subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            input=input_text,
        )

    def _server(self, handler_type: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, threading.Thread]:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)
        return server, thread

    def test_codexliz_runs_remote_and_local_models_canaries_before_exec(self) -> None:
        requests: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                requests.append(self.path)
                body = json.dumps(
                    {
                        "data": [
                            {"id": "qwen2.5-coder:32b"},
                            {"id": "fallback-model"},
                        ]
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(f"http://127.0.0.1:{server.server_port}")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertIn('model_provider="liz"', payload["argv"])
        self.assertIn('model="qwen2.5-coder:32b"', payload["argv"])
        self.assertIn("exec", payload["argv"])
        self.assertTrue(any(path == "/v1/models" for path in requests))
        self.assertGreaterEqual(requests.count("/v1/models"), 2)

    def test_codexliz_wraps_bare_prompt_as_exec(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(f"http://127.0.0.1:{server.server_port}")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertIn("exec", payload["argv"])
        self.assertIn("repair the queue stall", payload["argv"][-1])
        self.assertEqual(payload["env"]["CODEX_WRAPPER_DISABLE_BOOTSTRAP"], "1")
        self.assertEqual(payload["env"]["CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT"], "1")

    def test_codexliz_prepends_exec_trace_prompt_to_inline_exec_prompt(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(
            f"http://127.0.0.1:{server.server_port}",
            extra_args=["exec"],
            default_prompt="repair the queue stall",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        prompt_arg = payload["argv"][-1]
        self.assertIn("You are Codex running through the Fleet `codexliz` shim.", prompt_arg)
        self.assertIn("repair the queue stall", prompt_arg)

    def test_codexliz_prepends_exec_trace_prompt_to_stdin_exec_prompt(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(
            f"http://127.0.0.1:{server.server_port}",
            extra_args=["exec", "-"],
            default_prompt=None,
            input_text="repair the queue stall",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["argv"][-1], "-")
        self.assertIn("You are Codex running through the Fleet `codexliz` shim.", payload["stdin"])
        self.assertIn("repair the queue stall", payload["stdin"])

    def test_codexliz_debug_mode_emits_preflight_and_launch_traces(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(
            f"http://127.0.0.1:{server.server_port}",
            extra_env={"CODEXLIZ_DEBUG": "1"},
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Trace: provider=liz debug=preflight", completed.stderr)
        self.assertIn("Trace: provider=liz debug=launch command=", completed.stderr)
        debug_log = self.state_dir / "debug.log"
        self.assertTrue(debug_log.exists())
        log_text = debug_log.read_text(encoding="utf-8")
        self.assertIn("Trace: provider=liz debug=preflight", log_text)

    def test_codexliz_fails_fast_when_models_canary_returns_524(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = b"upstream timeout"
                self.send_response(524)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(f"http://127.0.0.1:{server.server_port}")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("transport preflight failed", completed.stderr)
        self.assertIn("HTTP 524", completed.stderr)
        self.assertFalse(self.capture_path.exists())

    def test_codexliz_fails_fast_when_expected_model_is_missing_from_models_surface(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"data": [{"id": "other-model"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(f"http://127.0.0.1:{server.server_port}")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("expected model", completed.stderr)
        self.assertIn("qwen2.5-coder:32b", completed.stderr)
        self.assertFalse(self.capture_path.exists())

    def test_codexliz_auto_assigns_distinct_proxy_ports_per_state_dir(self) -> None:
        requests: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                requests.append(self.path)
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        second_state_dir = self.root / "state-two"
        second_proxy_pid_file = second_state_dir / "proxy.pid"
        second_proxy_log_file = second_state_dir / "proxy.log"
        second_capture_path = self.root / "capture-two.json"
        self.addCleanup(self._cleanup_proxy_file, second_proxy_pid_file)

        first = self._run_shim(f"http://127.0.0.1:{server.server_port}", include_proxy_port=False)
        second = self._run_shim(
            f"http://127.0.0.1:{server.server_port}",
            state_dir=second_state_dir,
            capture_path=second_capture_path,
            proxy_pid_file=second_proxy_pid_file,
            proxy_log_file=second_proxy_log_file,
            include_proxy_port=False,
        )

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        first_port = self.proxy_port_file.read_text(encoding="utf-8").strip()
        second_port = (second_state_dir / "proxy.port").read_text(encoding="utf-8").strip()
        self.assertRegex(first_port, r"^[0-9]+$")
        self.assertRegex(second_port, r"^[0-9]+$")
        self.assertNotEqual(first_port, second_port)
        first_payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        second_payload = json.loads(second_capture_path.read_text(encoding="utf-8"))
        self.assertEqual(first_payload["env"]["CODEXLIZ_PROXY_PORT"], first_port)
        self.assertEqual(second_payload["env"]["CODEXLIZ_PROXY_PORT"], second_port)
        self.assertEqual(first_payload["env"]["CODEXLIZ_STATE_DIR"], str(self.state_dir))
        self.assertEqual(second_payload["env"]["CODEXLIZ_STATE_DIR"], str(second_state_dir))

    def test_codexliz_retries_retryable_502_until_transport_recovers(self) -> None:
        output_path = self.root / "last-message.txt"
        attempt_counter_path = self.root / "attempt-count.txt"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "from pathlib import Path",
                    "counter_path = Path(os.environ['CODEXLIZ_TEST_ATTEMPT_COUNTER'])",
                    "try:",
                    "    attempt = int(counter_path.read_text(encoding='utf-8').strip())",
                    "except Exception:",
                    "    attempt = 0",
                    "attempt += 1",
                    "counter_path.write_text(str(attempt), encoding='utf-8')",
                    "if attempt == 1:",
                    "    port = os.environ.get('CODEXLIZ_PROXY_PORT', '')",
                    "    sys.stderr.write('ERROR: unexpected status 502 Bad Gateway: {\\\"error\\\":\\\"upstream_http_error\\\"}, url: http://127.0.0.1:%s/v1/responses, cf-ray: retry-ray\\n' % port)",
                    "    raise SystemExit(17)",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'attempt': attempt,",
                    "}",
                    "with open(os.environ['CODEXLIZ_TEST_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(payload, handle)",
                    "output_path = Path(os.environ['CODEXLIZ_TEST_OUTPUT_PATH'])",
                    "output_path.write_text('transport recovered\\n', encoding='utf-8')",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

        requests: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                requests.append(self.path)
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(
            f"http://127.0.0.1:{server.server_port}",
            extra_args=["exec", "-o", str(output_path)],
            extra_env={
                "CODEXLIZ_TEST_ATTEMPT_COUNTER": str(attempt_counter_path),
                "CODEXLIZ_TEST_OUTPUT_PATH": str(output_path),
                "CODEXLIZ_TRANSPORT_RETRY_INTERVAL_SECONDS": "1",
                "CODEXLIZ_TRANSPORT_RETRY_BACKOFF_MAX_SECONDS": "1",
                "CODEXLIZ_TRANSPORT_TRACE_INTERVAL_SECONDS": "1",
                "CODEXLIZ_TRANSPORT_RETRY_MAX_WAIT_SECONDS": "30",
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Trace: provider=liz transport=outage status=502", completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["attempt"], 2)
        outage_state = json.loads((self.state_dir / "outage.json").read_text(encoding="utf-8"))
        self.assertEqual(outage_state["state"], "healthy")
        self.assertFalse(outage_state["current_outage"])
        self.assertEqual(outage_state["retry_count"], 1)
        self.assertEqual(outage_state["last_reason"], "success")
        self.assertEqual(output_path.read_text(encoding="utf-8").strip(), "transport recovered")

    def test_codexliz_retries_retryable_404_until_transport_recovers(self) -> None:
        output_path = self.root / "last-message.txt"
        attempt_counter_path = self.root / "attempt-count.txt"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "from pathlib import Path",
                    "counter_path = Path(os.environ['CODEXLIZ_TEST_ATTEMPT_COUNTER'])",
                    "try:",
                    "    attempt = int(counter_path.read_text(encoding='utf-8').strip())",
                    "except Exception:",
                    "    attempt = 0",
                    "attempt += 1",
                    "counter_path.write_text(str(attempt), encoding='utf-8')",
                    "if attempt == 1:",
                    "    port = os.environ.get('CODEXLIZ_PROXY_PORT', '')",
                    "    sys.stderr.write('ERROR: unexpected status 404 Not Found: {\\\\\"error\\\\\":\\\\\"not_found\\\\\"}, url: http://127.0.0.1:%s/v1/responses, cf-ray: not-found-ray\\\\n' % port)",
                    "    raise SystemExit(17)",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'attempt': attempt,",
                    "}",
                    "with open(os.environ['CODEXLIZ_TEST_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(payload, handle)",
                    "output_path = Path(os.environ['CODEXLIZ_TEST_OUTPUT_PATH'])",
                    "output_path.write_text('transport recovered', encoding='utf-8')",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

        requests: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                requests.append(self.path)
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(
            f"http://127.0.0.1:{server.server_port}",
            extra_args=["exec", "-o", str(output_path)],
            extra_env={
                "CODEXLIZ_TEST_ATTEMPT_COUNTER": str(attempt_counter_path),
                "CODEXLIZ_TEST_OUTPUT_PATH": str(output_path),
                "CODEXLIZ_TRANSPORT_RETRY_INTERVAL_SECONDS": "1",
                "CODEXLIZ_TRANSPORT_RETRY_BACKOFF_MAX_SECONDS": "1",
                "CODEXLIZ_TRANSPORT_TRACE_INTERVAL_SECONDS": "1",
                "CODEXLIZ_TRANSPORT_RETRY_MAX_WAIT_SECONDS": "30",
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Trace: provider=liz transport=outage status=404", completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["attempt"], 2)
        outage_state = json.loads((self.state_dir / "outage.json").read_text(encoding="utf-8"))
        self.assertEqual(outage_state["state"], "healthy")
        self.assertFalse(outage_state["current_outage"])
        self.assertEqual(outage_state["retry_count"], 1)
        self.assertEqual(outage_state["last_reason"], "success")
        self.assertEqual(output_path.read_text(encoding="utf-8").strip(), "transport recovered")

    def test_codexliz_retries_unsupported_input_item_with_stdin_exec_fallback(self) -> None:
        attempt_counter_path = self.root / "attempt-count.txt"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "from pathlib import Path",
                    "counter_path = Path(os.environ['CODEXLIZ_TEST_ATTEMPT_COUNTER'])",
                    "try:",
                    "    attempt = int(counter_path.read_text(encoding='utf-8').strip())",
                    "except Exception:",
                    "    attempt = 0",
                    "attempt += 1",
                    "counter_path.write_text(str(attempt), encoding='utf-8')",
                    "if attempt == 1 and '-' not in sys.argv[1:]:",
                    "    sys.stderr.write('{\"error\":{\"code\":\"unsupported_input_item:17\",\"message\":\"unsupported_input_item:17\"}}\\n')",
                    "    raise SystemExit(17)",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'stdin': sys.stdin.read(),",
                    "    'attempt': attempt,",
                    "}",
                    "with open(os.environ['CODEXLIZ_TEST_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(payload, handle)",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        completed = self._run_shim(
            f"http://127.0.0.1:{server.server_port}",
            extra_env={
                "CODEXLIZ_TEST_ATTEMPT_COUNTER": str(attempt_counter_path),
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["attempt"], 2)
        self.assertIn("exec", payload["argv"])
        self.assertIn("-", payload["argv"])
        self.assertIn("You are Codex running through the Fleet `codexliz` shim.", payload["stdin"])
        self.assertIn("repair the queue stall", payload["stdin"])
        self.assertIn("compat=unsupported_input_item retry=stdin_exec", completed.stderr)

    def test_codexliz_kills_active_child_when_wrapper_is_terminated(self) -> None:
        child_pid_path = self.root / "child.pid"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import os, signal, sys, time",
                    "from pathlib import Path",
                    "Path(os.environ['CODEXLIZ_CHILD_PID_PATH']).write_text(str(os.getpid()), encoding='utf-8')",
                    "signal.signal(signal.SIGTERM, lambda *_args: sys.exit(0))",
                    "while True:",
                    "    time.sleep(1.0)",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                body = json.dumps({"data": [{"id": "qwen2.5-coder:32b"}]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        env = os.environ.copy()
        env.update(
            {
                "CODEXLIZ_BASE_CODEX_SHIM": str(self.fake_codex),
                "CODEXLIZ_TEST_CAPTURE": str(self.capture_path),
                "CODEXLIZ_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "CODEXLIZ_MODEL": "qwen2.5-coder:32b",
                "CODEXLIZ_STATE_DIR": str(self.state_dir),
                "CODEXLIZ_PROXY_PID_FILE": str(self.proxy_pid_file),
                "CODEXLIZ_PROXY_LOG_FILE": str(self.proxy_log_file),
                "CODEXLIZ_PROXY_PORT": str(_pick_free_port()),
                "CODEXLIZ_CHILD_PID_PATH": str(child_pid_path),
                "HOME": str(self.root),
            }
        )

        process = subprocess.Popen(
            ["bash", str(SHIM_PATH), "repair the queue stall"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        def cleanup_process() -> None:
            if process.poll() is None:
                process.terminate()
                process.wait(5)

        self.addCleanup(cleanup_process)

        deadline = time.time() + 10.0
        while time.time() < deadline and not child_pid_path.exists():
            time.sleep(0.05)
        self.assertTrue(child_pid_path.exists(), "child codex process did not start")
        child_pid = int(child_pid_path.read_text(encoding="utf-8").strip())
        process.terminate()
        process.wait(5)

        child_deadline = time.time() + 3.0
        while time.time() < child_deadline:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail(f"child codex process {child_pid} was not terminated with the wrapper")
