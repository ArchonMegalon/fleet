from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading


SHIM_PATH = Path("/docker/fleet/scripts/codex-shims/codexaudit")


class CodexAuditShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.capture_path = self.root / "capture.json"
        self.fake_codexea = self.root / "codexea"
        self.fake_codexea.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'env': {",
                    "        'EA_PRINCIPAL_ID': os.environ.get('EA_PRINCIPAL_ID'),",
                    "        'EA_MCP_PRINCIPAL_ID': os.environ.get('EA_MCP_PRINCIPAL_ID'),",
                    "        'CODEXEA_LANE': os.environ.get('CODEXEA_LANE'),",
                    "        'CODEXEA_POST_AUDIT': os.environ.get('CODEXEA_POST_AUDIT'),",
                    "        'CODEXEA_JURY_MODEL': os.environ.get('CODEXEA_JURY_MODEL'),",
                    "        'CODEXEA_USE_LIVE_PROFILE_MODELS': os.environ.get('CODEXEA_USE_LIVE_PROFILE_MODELS'),",
                    "    },",
                    "}",
                    "with open(os.environ['CODEXAUDIT_TEST_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(payload, handle)",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codexea.chmod(self.fake_codexea.stat().st_mode | stat.S_IXUSR)

    def test_codexaudit_interactive_pins_jury_lane_and_disables_post_audit(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "CODEXAUDIT_CODEXEA_BIN": str(self.fake_codexea),
                "CODEXAUDIT_TEST_CAPTURE": str(self.capture_path),
                "CODEXAUDIT_PROBE_AUDIT_BACKEND": "0",
                "HOME": str(self.root),
            }
        )

        completed = subprocess.run(
            ["bash", str(SHIM_PATH), "--interactive"],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["argv"], ["--interactive"])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "jury")
        self.assertEqual(payload["env"]["CODEXEA_POST_AUDIT"], "0")
        self.assertTrue(str(payload["env"]["EA_PRINCIPAL_ID"]).endswith("-codex-audit"))
        self.assertEqual(payload["env"]["EA_MCP_PRINCIPAL_ID"], payload["env"]["EA_PRINCIPAL_ID"])

    def test_codexaudit_exec_passthrough_does_not_hit_direct_audit_endpoint(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "CODEXAUDIT_CODEXEA_BIN": str(self.fake_codexea),
                "CODEXAUDIT_TEST_CAPTURE": str(self.capture_path),
                "CODEXAUDIT_PROBE_AUDIT_BACKEND": "0",
                "HOME": str(self.root),
            }
        )

        completed = subprocess.run(
            ["bash", str(SHIM_PATH), "exec", "review", "the", "release", "packet"],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["argv"], ["exec", "review", "the", "release", "packet"])

    def test_codexaudit_uses_direct_tool_endpoint_for_one_shot_prompt(self) -> None:
        requests: list[tuple[str, dict[str, object]]] = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", "0") or "0")
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                requests.append((self.path, payload))
                if self.path == "/v1/responses":
                    body = json.dumps({"status": "ok"}).encode("utf-8")
                elif self.path == "/v1/tools/execute":
                    body = json.dumps(
                        {
                            "output_json": {
                                "consensus": "pass",
                                "recommendation": "ship it",
                                "audit_scope": "jury",
                            }
                        }
                    ).encode("utf-8")
                else:
                    body = json.dumps({"error": "unexpected_path"}).encode("utf-8")
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
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

        env = os.environ.copy()
        env.update(
            {
                "CODEXAUDIT_CODEXEA_BIN": str(self.fake_codexea),
                "CODEXAUDIT_TEST_CAPTURE": str(self.capture_path),
                "EA_MCP_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "CODEXAUDIT_PROBE_URL": f"http://127.0.0.1:{server.server_port}/v1/responses",
                "CODEXAUDIT_EXECUTE_URL": f"http://127.0.0.1:{server.server_port}/v1/tools/execute",
                "HOME": str(self.root),
            }
        )

        completed = subprocess.run(
            ["bash", str(SHIM_PATH), "review", "the", "release", "packet"],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(
            completed.stdout.strip(),
            '{"consensus":"pass","recommendation":"ship it","audit_scope":"jury"}',
        )
        self.assertFalse(self.capture_path.exists())
        self.assertEqual(requests[0][0], "/v1/responses")
        self.assertEqual(requests[1][0], "/v1/tools/execute")
        self.assertEqual(requests[1][1]["tool_name"], "browseract.chatplayground_audit")
        self.assertEqual(requests[1][1]["payload_json"]["prompt"], "review the release packet")

    def test_codexaudit_fails_fast_when_audit_backend_is_unavailable(self) -> None:
        probe_body = {
            "output_text": json.dumps(
                {
                    "provider": "chatplayground",
                    "consensus": "unavailable",
                    "risks": [
                        "chatplayground_unavailable",
                        "connector_binding_required:browseract.chatplayground_audit",
                    ],
                    "raw_output": {
                        "reason": "connector_binding_required:browseract.chatplayground_audit",
                    },
                }
            )
        }

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.dumps(probe_body).encode("utf-8")
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

        env = os.environ.copy()
        env.update(
            {
                "CODEXAUDIT_CODEXEA_BIN": str(self.fake_codexea),
                "CODEXAUDIT_TEST_CAPTURE": str(self.capture_path),
                "EA_MCP_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "HOME": str(self.root),
            }
        )

        completed = subprocess.run(
            ["bash", str(SHIM_PATH), "review the release packet"],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("audit backend unavailable", completed.stderr)
        self.assertIn("CODEXAUDIT_ALLOW_SOFT_FALLBACK=1", completed.stderr)
        self.assertFalse(self.capture_path.exists())

    def test_codexaudit_can_soft_fallback_when_backend_is_unavailable(self) -> None:
        probe_body = {
            "output_text": json.dumps(
                {
                    "provider": "chatplayground",
                    "consensus": "unavailable",
                    "risks": [
                        "chatplayground_unavailable",
                        "connector_binding_required:browseract.chatplayground_audit",
                    ],
                    "raw_output": {
                        "reason": "connector_binding_required:browseract.chatplayground_audit",
                    },
                }
            )
        }

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.dumps(probe_body).encode("utf-8")
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

        env = os.environ.copy()
        env.update(
            {
                "CODEXAUDIT_CODEXEA_BIN": str(self.fake_codexea),
                "CODEXAUDIT_TEST_CAPTURE": str(self.capture_path),
                "CODEXAUDIT_PROBE_URL": f"http://127.0.0.1:{server.server_port}/v1/responses",
                "CODEXAUDIT_ALLOW_SOFT_FALLBACK": "1",
                "HOME": str(self.root),
            }
        )

        completed = subprocess.run(
            ["bash", str(SHIM_PATH), "review the release packet"],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("falling back to ea-coder-fast", completed.stderr)
        payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["env"]["CODEXEA_JURY_MODEL"], "ea-coder-fast")
        self.assertEqual(payload["env"]["CODEXEA_USE_LIVE_PROFILE_MODELS"], "0")

    def test_codexaudit_blocks_interactive_launch_when_audit_backend_is_unavailable(self) -> None:
        probe_body = {
            "id": "resp_test",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "provider": "chatplayground",
                                    "consensus": "unavailable",
                                    "risks": [
                                        "chatplayground_unavailable",
                                        "connector_binding_required:browseract.chatplayground_audit",
                                    ],
                                    "raw_output": {
                                        "reason": "connector_binding_required:browseract.chatplayground_audit",
                                    },
                                }
                            ),
                        }
                    ],
                }
            ],
        }

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.dumps(probe_body).encode("utf-8")
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

        env = os.environ.copy()
        env.update(
            {
                "CODEXAUDIT_CODEXEA_BIN": str(self.fake_codexea),
                "CODEXAUDIT_TEST_CAPTURE": str(self.capture_path),
                "CODEXAUDIT_PROBE_URL": f"http://127.0.0.1:{server.server_port}/v1/responses",
                "HOME": str(self.root),
            }
        )

        completed = subprocess.run(
            ["bash", str(SHIM_PATH)],
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("audit backend unavailable", completed.stderr)
        self.assertFalse(self.capture_path.exists())


if __name__ == "__main__":
    unittest.main()
