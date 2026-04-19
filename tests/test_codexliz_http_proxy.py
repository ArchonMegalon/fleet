from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PROXY_PATH = Path("/docker/fleet/scripts/codex-shims/codexliz-http-proxy")


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class CodexLizHttpProxyTests(unittest.TestCase):
    def _server(self, handler_type: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, threading.Thread]:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)
        return server, thread

    def _wait_for_proxy(self, port: int) -> None:
        deadline = time.time() + 10.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1.0) as response:
                    if int(getattr(response, "status", 0) or response.getcode() or 0) == 200:
                        return
            except Exception:
                time.sleep(0.1)
        self.fail(f"proxy on port {port} did not become ready")

    def test_proxy_rewrites_upstream_html_502_to_structured_json(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = (
                    "<!DOCTYPE html><html><head><title>girschele.com | 502: Bad gateway</title></head>"
                    "<body>cf edge outage</body></html>"
                ).encode("utf-8")
                self.send_response(502, "Bad Gateway")
                self.send_header("Content-Type", "text/html; charset=UTF-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("CF-Ray", "test-ray-FRA")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server, _thread = self._server(Handler)
        proxy_port = _pick_free_port()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "proxy.log"
            proxy = subprocess.Popen(
                [
                    "python3",
                    str(PROXY_PATH),
                    "--listen-host",
                    "127.0.0.1",
                    "--listen-port",
                    str(proxy_port),
                    "--upstream-base-url",
                    f"http://127.0.0.1:{server.server_port}",
                ],
                stdout=log_path.open("w", encoding="utf-8"),
                stderr=subprocess.STDOUT,
                text=True,
            )
            def cleanup_proxy() -> None:
                if proxy.poll() is None:
                    proxy.terminate()
                proxy.wait(5)

            self.addCleanup(cleanup_proxy)
            self._wait_for_proxy(proxy_port)

            request = urllib.request.Request(
                f"http://127.0.0.1:{proxy_port}/v1/responses",
                data=b'{"model":"qwen3-coder-next:q8_0"}',
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError) as captured:
                urllib.request.urlopen(request, timeout=5.0)

            self.assertEqual(captured.exception.code, 502)
            payload = json.loads(captured.exception.read().decode("utf-8"))
            self.assertEqual(payload["error"], "upstream_http_error")
            self.assertEqual(payload["upstream_status"], 502)
            self.assertEqual(payload["cf_ray"], "test-ray-FRA")
            self.assertEqual(payload["upstream_path"], "/v1/responses")
            self.assertIn("Bad Gateway", payload["upstream_reason"])
            self.assertNotIn("<!DOCTYPE html>", payload["body_excerpt"])


if __name__ == "__main__":
    unittest.main()
