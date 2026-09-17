"""Transport-boundary tests; every HTTP peer below is an in-process fake."""
from pathlib import Path
import json
import os
import sys
import tempfile
import time
from types import SimpleNamespace

import pytest

from scripts import android_startup_scheduling as scheduling
import test_android_startup_scheduling as model_helpers


def _child(script, payload=b"{}", *, timeout=1.0, out_limit=4096, args=()):
    with tempfile.TemporaryDirectory(prefix="startup-transport-test-") as directory:
        return scheduling._run_transport(
            [sys.executable, "-I", "-B", "-c", script, *args], payload,
            Path(directory), timeout, out_limit,
        )


def test_large_stdin_to_nonreader_is_deadline_bounded(monkeypatch):
    original = scheduling.subprocess.Popen
    spawned = []
    def popen(*args, **kwargs):
        child = original(*args, **dict(kwargs, pipesize=4096)); spawned.append(child); return child
    monkeypatch.setattr(scheduling.subprocess, "Popen", popen)
    started = time.monotonic()
    with pytest.raises(scheduling.StartupSchedulingError):
        _child("import time; time.sleep(3)", b"x" * 30000, timeout=0.15)
    assert time.monotonic() - started < 1.0 and len(spawned) == 1 and spawned[0].returncode < 0


@pytest.mark.parametrize("script", [
    "import sys; sys.stdin.buffer.read(); sys.stdout.write('x' * 8192); sys.stdout.flush()",
    "import sys; sys.stdin.buffer.read(); sys.stderr.write('diagnostic'); sys.stderr.flush()",
    "import sys; sys.stdin.buffer.read(); sys.exit(7)",
])
def test_child_output_and_exit_fail_closed(script):
    with pytest.raises(scheduling.StartupSchedulingError):
        _child(script, timeout=1.0, out_limit=128)


def test_child_process_group_is_cleaned_after_timeout():
    with tempfile.TemporaryDirectory(prefix="startup-cleanup-test-") as directory:
        pid_file = Path(directory) / "child.pid"
        script = (
            "import subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
            "open(sys.argv[1],'w').write(str(p.pid)); "
            "time.sleep(30)"
        )
        with pytest.raises(scheduling.StartupSchedulingError):
            scheduling._run_transport([sys.executable, "-I", "-B", "-c", script, str(pid_file)],
                                      b"X", Path(directory), 0.15, 4096)
        pid = int(pid_file.read_text())
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.01)
        else:
            pytest.fail("transport descendant survived process-group cleanup")


def test_token_is_supplied_only_on_child_stdin():
    script = (
        "import json,os,sys; raw=sys.stdin.buffer.read(); "
        "print(json.dumps({'stdin': b'synthetic-token' in raw, "
        "'argv': any('synthetic-token' in x for x in sys.argv), "
        "'env': any('synthetic-token' in (k+'='+v) for k,v in os.environ.items())}))"
    )
    result = json.loads(_child(script, b"token=synthetic-token", args=("safe-marker",)))
    assert result == {"stdin": True, "argv": False, "env": False}


def _fake_http_harness(source, mode, argument, metadata):
    """Run one embedded transport script against a synthetic urllib module."""
    return f'''import json,sys,types
mode={mode!r}; metadata={str(metadata)!r}
class TLS: TLSv1_2=object()
class Context: pass
ssl=types.ModuleType("ssl"); ssl.TLSVersion=TLS; ssl.create_default_context=lambda **kw: Context()
sys.modules["ssl"]=ssl
class Headers(dict):
    def get_content_type(self): return self.get("Content-Type", "")
    def get_content_charset(self): return None
class Response:
    def __init__(self, url, status, headers, body):
        self._url=url; self.status=status; self.headers=Headers(headers); self.body=body; self.done=False
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def geturl(self): return self._url
    def read(self,n=-1):
        if self.done: return b""
        self.done=True
        return self.body
class Request:
    def __init__(self,url,data=None,headers=None,method=None):
        self.full_url=url; self.data=data; self.headers=headers or {{}}; self.method=method
class Opener:
    def open(self, request, timeout=None):
        with open(metadata,"w") as f:
            json.dump({{"url":request.full_url,"method":request.method,"headers":request.headers,"data":(request.data.decode("ascii") if request.data else None),"timeout":timeout}},f)
        url=request.full_url
        headers=[("Content-Type","application/json")]
        body=b'{{"ok":true}}'; status=201 if request.method=="POST" else 200
        if mode=="redirect": url += "/redirect"
        elif mode=="encoding": headers.append(("Content-Encoding","gzip"))
        elif mode=="link": headers.append(("Link","<next>"))
        elif mode=="oversize": body=b"x" * (2097153 if request.method=="GET" else 16385)
        elif mode=="length": headers.append(("Content-Length","99"))
        elif mode=="wrong-status": status=201 if request.method=="GET" else 200
        return Response(url,status,headers,body)
request=types.ModuleType("urllib.request")
class HTTPRedirectHandler: pass
request.HTTPRedirectHandler=HTTPRedirectHandler
request.ProxyHandler=lambda value: object()
request.HTTPSHandler=lambda **kw: object()
request.Request=Request
request.build_opener=lambda *handlers: Opener()
urllib=types.ModuleType("urllib"); urllib.__path__=[]; urllib.request=request
sys.modules["urllib"]=urllib; sys.modules["urllib.request"]=request
sys.argv=["transport", {argument!r}, {metadata!r}]
exec({source!r}, {{"__name__":"__main__"}})
'''


def _run_synthetic_script(source, url, *, method, mode="ok", token=None):
    with tempfile.TemporaryDirectory(prefix="startup-http-test-") as directory:
        metadata = str(Path(directory) / "request.json")
        argument = url if method == "GET" else mode
        harness = _fake_http_harness(source, mode, argument, metadata)
        if method == "GET":
            payload = b"GET"
        else:
            payload = json.dumps({"url": url, "body": '{"state":"success"}',
                                  "token": token or "synthetic-token"}).encode()
        result = scheduling._run_transport([sys.executable, "-I", "-B", "-c", harness], payload,
                                           Path(directory), 2, scheduling.MAX_STATUS_BYTES)
        return result, json.loads(Path(metadata).read_text())


def test_get_script_uses_exact_canonical_url_without_auth():
    url = "https://api.github.com/repos/example/repo/commits/" + "a" * 40 + "/statuses?per_page=100&page=1"
    body, request = _run_synthetic_script(scheduling._GET_SCRIPT, url, method="GET")
    assert body == b'{"ok":true}'
    assert request["url"] == url and request["method"] == "GET"
    assert all(key.lower() != "authorization" for key in request["headers"])


def test_post_script_uses_exact_endpoint_and_stdin_token():
    url = "https://api.github.com/repos/example/repo/statuses/" + "b" * 40
    body, request = _run_synthetic_script(scheduling._POST_SCRIPT, url, method="POST", token="synthetic-token")
    assert body == b'{"ok":true}'
    assert request["url"] == url and request["method"] == "POST"
    assert request["headers"]["Authorization"] == "Bearer synthetic-token"
    assert request["data"] == '{"state":"success"}'


@pytest.mark.parametrize("mode", ["redirect", "encoding", "link", "oversize", "length", "wrong-status"])
def test_embedded_scripts_reject_unsafe_response_modes(mode):
    for source, method, url in (
        (scheduling._GET_SCRIPT, "GET",
         "https://api.github.com/repos/example/repo/commits/" + "a" * 40 + "/statuses?per_page=100&page=1"),
        (scheduling._POST_SCRIPT, "POST",
         "https://api.github.com/repos/example/repo/statuses/" + "b" * 40),
    ):
        with pytest.raises(scheduling.StartupSchedulingError):
            _run_synthetic_script(source, url, method=method, mode=mode)


def test_publish_rejects_bad_post_result_without_retry(monkeypatch):
    value, templates = model_helpers._model()
    bound = model_helpers._bound(templates)
    owner_value = dict(value, status_write_token="/private/status-token")
    config = scheduling.validate_deployment(owner_value, owner=True)
    bad = model_helpers._status(config, "listener", bound)
    bad["state"] = "pending"
    calls = []
    monkeypatch.setattr(scheduling, "_http", lambda *args, **kwargs: calls.append(1) or json.dumps(bad).encode())
    token = SimpleNamespace(path=Path("/private/status-token"), read=lambda: b"token", recheck=lambda: None)
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.publish_stage(owner_value, "listener", bound, token,
                                 deadline=scheduling.time.monotonic() + 2, recheck=lambda: None)
    assert calls == [1]


def test_pending_observations_have_fixed_read_budget(monkeypatch):
    value, templates = model_helpers._model()
    bound = model_helpers._bound(templates)
    config = scheduling.validate_deployment(value)
    row = model_helpers._status(config, "listener", bound, state="pending")
    calls = []
    monkeypatch.setattr(scheduling, "_http", lambda *args, **kwargs: calls.append(1) or json.dumps([row]).encode())
    clock = [100.0]
    monkeypatch.setattr(scheduling.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(scheduling, "LISTENER_DELAY", 0.0)
    with pytest.raises(scheduling.StartupSchedulingError):
        scheduling.wait_for_stage(value, "listener", deadline=101.0, recheck=lambda: None)
    assert len(calls) == scheduling.LISTENER_OBSERVATIONS
