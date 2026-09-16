"""Real RS256/SQLite/intake bytes; explicitly modeled hosted/kernel boundaries.

No real OIDC request, key, signer, Docker, namespace, mount or SDK execution.
The existing origin stand-in is NOT cryptographic Sigstore/deployment proof.
"""
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import ssl
import threading
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import android_protected_job_entrypoint as entry
from scripts import android_protected_job_launcher as launcher
from scripts import android_protected_capture_intake as intake
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_artifact_origin as origin
import test_android_builder_handoff as builders
import test_android_protected_capture_intake as transfer
import test_android_preview12_external_rebuilder as locks
from test_android_protected_capture_intake import exported, flow, store, signing_key

URL = "https://token.actions.githubusercontent.com/issue/test?api-version=2.0"
REQUEST_CREDENTIAL = "PUBLIC-TEST-request-credential-1234567890"


@pytest.fixture
def model(tmp_path, monkeypatch):
    value = builders.model.__wrapped__(tmp_path, monkeypatch)
    # Explicit test-only ready configuration, never production lock activation.
    raw = fleet._canonical_json(locks.synthetic_ready_lock())
    value.lock.path.write_bytes(raw)
    value.lock = origin.PinnedFile(value.lock.path, hashlib.sha256(raw).hexdigest())
    manifest = json.loads(value.manifest.read_bytes())
    manifest["bindings"]["lockSha256"] = value.lock.sha256
    value.manifest.write_bytes(fleet._pretty_json(manifest))
    value.expected = {path.name: path.read_bytes() for path in value.fixture.iterdir()}
    return value


@pytest.fixture
def prepared(exported, monkeypatch):
    client = transfer.connect(exported, monkeypatch)
    transfer.model_mounts(exported, monkeypatch)
    # Existing constructor's full runtime/validation admission is modeled; the
    # source entrypoint must demand those exact types and recheck the boundaries.
    own = launcher.ProtectedJobLauncher.__new__(launcher.ProtectedJobLauncher)
    own.connection, own.used = client, False
    own.root = exported.flow.tmp_path
    own.lock_path = exported.flow.model.lock.path
    own.lock, own.lock_raw = fleet.load_lock(own.lock_path)
    own.config = {"mode": "execute", "attempt": client._job.transaction_id, "code_pins": {},
                  "handoff": str(exported.flow.tmp_path / "job-intake" / "preserved")}
    own.validation = fleet.PreservedProtectedValidation.__new__(fleet.PreservedProtectedValidation)
    own.validation._bindings = {"PUBLIC-TEST": "input"}
    own.validation._capture_inputs = lambda: dict(own.validation._bindings)
    own.persistent = launcher.RecoveryMount.__new__(launcher.RecoveryMount)
    own.persistent.assert_exact = lambda: None
    own.pins, own.tool = {}, SimpleNamespace(recheck=lambda: None)
    monkeypatch.setattr(entry.worker, "code_inputs", lambda *_: {})
    monkeypatch.setattr(entry, "os", SimpleNamespace(getuid=lambda: 0, geteuid=lambda: 0, path=os.path))
    launched = []
    def launch(captured):
        assert type(captured) is intake.CapturedPublicIntake and captured.connection is client
        captured.assert_exact()
        client.assert_signing_fresh(captured)
        own.used = True
        launched.append(captured)
        return {"PUBLIC-TEST-modeled-launch": True}
    monkeypatch.setattr(own, "launch", launch)
    params = dict(verifier=exported.flow.verifier.pins[2], trusted_root=exported.flow.verifier.pins[3],
                  oidc_tls_context=ssl.create_default_context())
    params["oidc_tls_context"].minimum_version = ssl.TLSVersion.TLSv1_2
    e = entry.ProtectedJobEntrypoint(own, **params)
    return SimpleNamespace(e=e, own=own, client=client, exported=exported, launched=launched,
                           params=params, get_calls=[], responses=[], change=None, error=None)


def arm(prepared):
    exported = prepared.exported
    exported.export.enable_protected_job_checks()
    exported.export.arm()
    exported.flow.serve(exported.export._issued, 709)


def network(prepared, monkeypatch):
    class Response:
        def __init__(self, raw):
            self.status, self.raw = 200, io.BytesIO(raw)
            self.headers = [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(raw)))]
            self.reads = 0
        def getheaders(self): return self.headers
        def read1(self, count): self.reads += 1; return self.raw.read(count)
    class Connection:
        def __init__(self, host, *, port, timeout, context):
            assert host == "token.actions.githubusercontent.com" and port == 443 and timeout == 15
            assert context is prepared.params["oidc_tls_context"] and context.check_hostname
            self.sock = SimpleNamespace(settimeout=lambda seconds: None)
        def request(self, method, target, *, headers):
            assert method == "GET" and headers["Authorization"] == "Bearer " + REQUEST_CREDENTIAL
            query = parse_qs(urlsplit(target).query, strict_parsing=True)
            assert query == {"api-version": ["2.0"], "audience": [prepared.exported.export._issued.audience]}
            prepared.get_calls.append("GET")
            if prepared.error:
                raise prepared.error
            token = prepared.exported.flow.token(prepared.exported.export._issued)
            self.response = Response(json.dumps({"value": token, "extra": "discarded metadata"}).encode())
            prepared.responses.append(self.response)
            if prepared.change: prepared.change(self.response)
        def getresponse(self): return self.response
        def close(self): pass
    monkeypatch.setattr(entry, "HTTPSConnection", Connection)


def execute(prepared):
    return prepared.e.run(oidc_request_url=URL, oidc_request_credential=REQUEST_CREDENTIAL)


def wait_execute(prepared):
    return prepared.e.run(oidc_request_url=URL, oidc_request_credential=REQUEST_CREDENTIAL,
                          preparation_wait_seconds=5)


def test_pending_preparation_then_real_signed_consume_and_once_only_completion(prepared, monkeypatch):
    network(prepared, monkeypatch)
    clock = transfer.preparation_clock(monkeypatch)
    exported = prepared.exported
    exported.export.enable_preparation_wait(10)
    def owner_decision(seconds):
        assert prepared.get_calls == [] and exported.seen == ["challenge"]
        assert exported.export.preparation_observed() is True
        assert exported.export._issued is None and not exported.export._signing_enabled
        assert prepared.client._host_entrypoint_claimed and prepared.e._attempted
        clock.now += seconds
        arm(prepared)  # Independently modeled local owner, never an HTTP action.
    monkeypatch.setattr(intake.time, "sleep", owner_decision)
    assert wait_execute(prepared) == {"PUBLIC-TEST-modeled-launch": True}
    assert prepared.get_calls == ["GET"] and len(prepared.launched) == 1
    assert exported.seen.count("challenge") == 2 and exported.seen.count("submit") == 1
    assert exported.flow.store.status(hashlib.sha256(exported.export._issued.audience.encode()).hexdigest()) == "consumed"
    with pytest.raises(entry.EntrypointError): wait_execute(prepared)
    assert prepared.get_calls == ["GET"] and len(prepared.launched) == 1


@pytest.mark.parametrize("fault", ["timeout", "lost", "closed", "default", "preflight-drift"])
def test_pending_failure_has_no_oidc_submit_or_launch_and_no_second_attempt(prepared, monkeypatch, fault):
    network(prepared, monkeypatch)
    transfer.preparation_clock(monkeypatch)
    exported = prepared.exported
    exported.export.enable_preparation_wait(10)
    if fault == "lost": exported.lost = "challenge"
    elif fault == "closed": exported.export.close()
    elif fault == "preflight-drift": prepared.own.config["attempt"] = "f" * 64
    with pytest.raises(entry.EntrypointError):
        execute(prepared) if fault == "default" else wait_execute(prepared)
    count = len(exported.seen)
    with pytest.raises(entry.EntrypointError): wait_execute(prepared)
    assert len(exported.seen) == count and not prepared.get_calls and not prepared.launched
    assert "submit" not in exported.seen and exported.export._issued is None


@pytest.mark.parametrize("seconds", [-1, 1801, True, False, 1.0, None, "1"])
def test_invalid_wait_is_latched_before_any_request(prepared, seconds):
    with pytest.raises(entry.EntrypointError):
        prepared.e.run(oidc_request_url=URL, oidc_request_credential=REQUEST_CREDENTIAL,
                       preparation_wait_seconds=seconds)
    with pytest.raises(entry.EntrypointError): execute(prepared)
    assert prepared.exported.seen == [] and not prepared.get_calls and not prepared.launched


@pytest.mark.parametrize("second_wrapper", [False, True])
def test_pending_wait_still_owns_single_entrypoint_claim(prepared, monkeypatch, second_wrapper):
    other = entry.ProtectedJobEntrypoint(prepared.own, **prepared.params) if second_wrapper else prepared.e
    network(prepared, monkeypatch)
    transfer.preparation_clock(monkeypatch)
    prepared.exported.export.enable_preparation_wait(10)
    def owner_decision(_):
        with pytest.raises(entry.EntrypointError):
            other.run(oidc_request_url=URL, oidc_request_credential=REQUEST_CREDENTIAL,
                      preparation_wait_seconds=5)
        assert not prepared.client._failed and not prepared.get_calls
        arm(prepared)
    monkeypatch.setattr(intake.time, "sleep", owner_decision)
    assert wait_execute(prepared) == {"PUBLIC-TEST-modeled-launch": True}
    assert prepared.get_calls == ["GET"] and len(prepared.launched) == 1


@pytest.mark.parametrize("fault", ["configuration", "job", "connection", "client-close"])
def test_wait_drift_rejects_before_any_oidc_request(prepared, monkeypatch, fault):
    network(prepared, monkeypatch)
    transfer.preparation_clock(monkeypatch)
    prepared.exported.export.enable_preparation_wait(10)
    def change(_):
        arm(prepared)
        if fault == "configuration": prepared.own.config["attempt"] = "f" * 64
        elif fault == "job": prepared.client._job = replace(prepared.client._job, check_run_id="912")
        elif fault == "connection": prepared.own.connection = object()
        else: prepared.client.close()
    monkeypatch.setattr(intake.time, "sleep", change)
    with pytest.raises(entry.EntrypointError): wait_execute(prepared)
    assert prepared.client._failed and not prepared.get_calls and not prepared.launched
    assert "submit" not in prepared.exported.seen


def test_complete_real_admission_intake_and_fresh_check_with_modeled_launch(prepared, monkeypatch, capsys):
    arm(prepared); network(prepared, monkeypatch)
    assert execute(prepared) == {"PUBLIC-TEST-modeled-launch": True}
    assert prepared.get_calls == ["GET"] and len(prepared.launched) == 1
    seen = prepared.exported.seen
    assert seen.count("challenge") == seen.count("submit") == seen.count("bundle") == 1
    assert seen.index("challenge") < seen.index("submit") < seen.index("bundle") < seen.index("fresh-check")
    assert prepared.exported.export._authenticated.job_id == 709
    assert prepared.client._failed and prepared.e.captured is prepared.launched[0]
    assert len(list(prepared.e.captured.custody.source.iterdir())) == 7
    with pytest.raises(entry.EntrypointError): execute(prepared)
    assert prepared.get_calls == ["GET"] and len(prepared.launched) == 1
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("endpoint", [None, "", "http://token.actions.githubusercontent.com/a", "https://evil.example/a",
    "https://token.actions.githubusercontent.com.evil.example/a", "https://token.actions.githubusercontent.com/",
    "https://user:password@token.actions.githubusercontent.com/a", "https://token.actions.githubusercontent.com:444/a",
    URL + "#secret", URL + "\n", URL + "&audience=other", URL + "&%61udience=other", URL + "&Audience=other",
    URL + "&" + "&".join("x=1" for _ in range(33)), "https://token.actions.githubusercontent.com/a?malformed"])
def test_bad_provider_endpoint_rejects_before_challenge(prepared, endpoint):
    with pytest.raises(entry.EntrypointError) as caught:
        prepared.e.run(oidc_request_url=endpoint, oidc_request_credential=REQUEST_CREDENTIAL)
    assert str(caught.value) == entry.ERROR and prepared.exported.seen == [] and not prepared.launched


@pytest.mark.parametrize("credential", [None, "", "a b", "a\nsecret", "a\x00secret", "x" * 16385],
                         ids=["missing", "empty", "space", "newline", "nul", "oversize"])
def test_missing_or_unsafe_request_credential_rejects_before_challenge(prepared, credential):
    with pytest.raises(entry.EntrypointError):
        prepared.e.run(oidc_request_url=URL, oidc_request_credential=credential)
    assert prepared.exported.seen == [] and not prepared.launched


@pytest.mark.parametrize("fault", ["dict-owner", "wrong-client", "nonroot", "used", "begun", "failed", "reconcile",
    "environment", "persistent", "validation", "dormant-lock", "public-code-drift", "validation-drift",
    "tool-drift", "verifier-drift", "existing-packet", "aliased-packet", "handoff-name", "unsafe-tls"])
def test_missing_owner_admission_rejects_before_any_network_or_secrets(prepared, monkeypatch, fault):
    own, params = prepared.own, dict(prepared.params)
    if fault == "dict-owner": own = vars(own)
    elif fault == "wrong-client": own.connection = object()
    elif fault == "nonroot": monkeypatch.setattr(entry.os, "geteuid", lambda: 1000)
    elif fault == "used": own.used = True
    elif fault == "begun": prepared.client._begun = True
    elif fault == "failed": prepared.client._failed = True
    elif fault == "reconcile": own.config["mode"] = "reconcile"
    elif fault == "environment": prepared.client._job = replace(prepared.client._job, environment="wrong")
    elif fault == "persistent": own.persistent = {"durable": True}
    elif fault == "validation": own.validation = {"validated": True}
    elif fault == "dormant-lock":
        own.lock["state"] = "dormant"
        own.lock_raw = fleet._canonical_json(own.lock)
        own.lock_path.write_bytes(own.lock_raw)
    elif fault == "public-code-drift": own.pins = {"changed": "1"}
    elif fault == "validation-drift": own.validation._capture_inputs = lambda: {}
    elif fault == "tool-drift": own.tool.recheck = lambda: (_ for _ in ()).throw(ValueError("PRIVATE tool input"))
    elif fault == "verifier-drift": params["verifier"] = replace(params["verifier"], sha256="a" * 64)
    elif fault == "existing-packet": Path(own.config["handoff"]).parent.mkdir(mode=0o700)
    elif fault == "aliased-packet": Path(own.config["handoff"]).parent.symlink_to(own.root, target_is_directory=True)
    elif fault == "handoff-name": own.config["handoff"] += "-other"
    else:
        params["oidc_tls_context"].check_hostname = False
    with pytest.raises(entry.EntrypointError) as caught:
        entry.ProtectedJobEntrypoint(own, **params)
    assert str(caught.value) == entry.ERROR and prepared.exported.seen == [] and not prepared.launched


@pytest.mark.parametrize("fault", ["configuration", "policy", "client", "lock", "persistent", "verifier"])
def test_prepared_inputs_rechecked_before_challenge(prepared, fault):
    if fault == "configuration": prepared.own.config["attempt"] = "f" * 64
    elif fault == "policy": prepared.client._job = replace(prepared.client._job, check_run_id="912")
    elif fault == "client": prepared.own.connection = object()
    elif fault == "lock": prepared.own.lock_path.write_bytes(b'{}\n')
    elif fault == "persistent": prepared.own.persistent = object()
    else: prepared.params["verifier"].path.write_bytes(b"changed")
    with pytest.raises(entry.EntrypointError): execute(prepared)
    assert prepared.exported.seen == [] and not prepared.launched


@pytest.mark.parametrize("field,value", [("check_run_id", "999"), ("run_id", "999"), ("run_attempt", "3"),
    ("sha", "a" * 40), ("aud", "foreign"), ("environment", "wrong"), ("exp", 1)])
def test_actual_server_rejects_wrong_signed_identity_not_local_claims(prepared, monkeypatch, field, value):
    arm(prepared); network(prepared, monkeypatch)
    token = prepared.exported.flow.token(prepared.exported.export._issued, **{field: value})
    def change(response):
        raw = json.dumps({"value": token}).encode()
        response.raw = io.BytesIO(raw)
        response.headers[-1] = ("Content-Length", str(len(raw)))
    prepared.change = change
    with pytest.raises(entry.EntrypointError): execute(prepared)
    assert prepared.exported.seen == ["challenge", "submit"] and not prepared.launched
    assert not prepared.e._packet.exists()


@pytest.mark.parametrize("attack", ["redirect", "http-error", "duplicate-header", "large-header", "encoding",
    "wrong-type", "bad-length", "short-body", "oversize", "conflicting-framing", "transfer-encoding", "bad-json",
    "duplicate-json", "missing-value", "nonstring-token", "bad-token", "header-delay", "body-delay"])
def test_oidc_response_bounds_and_no_redirect_or_retry(prepared, monkeypatch, attack):
    arm(prepared); network(prepared, monkeypatch)
    clock = [0.0]
    monkeypatch.setattr(entry, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    def change(response):
        if attack == "redirect": response.status = 302; response.headers.append(("Location", "https://evil.example/secret"))
        elif attack == "http-error": response.status = 403
        elif attack == "duplicate-header": response.headers.append(response.headers[0])
        elif attack == "large-header": response.headers.append(("Other", "x" * 16384))
        elif attack == "encoding": response.headers.append(("Content-Encoding", "gzip"))
        elif attack == "wrong-type": response.headers[0] = ("Content-Type", "text/html")
        elif attack == "bad-length": response.headers[-1] = ("Content-Length", "01")
        elif attack == "short-body": response.headers[-1] = ("Content-Length", str(entry.MAX_RESPONSE))
        elif attack == "conflicting-framing": response.headers.append(("Transfer-Encoding", "chunked"))
        elif attack == "transfer-encoding": response.headers[-1] = ("Transfer-Encoding", "gzip")
        elif attack == "header-delay": clock[0] = 16
        elif attack == "body-delay":
            original = response.read1
            def delayed(n): clock[0] = 16; return original(n)
            response.read1 = delayed
        else:
            raw = {"oversize": b"x" * (entry.MAX_RESPONSE + 1), "bad-json": b"{",
                "duplicate-json": b'{"value":"a.b.c","value":"d.e.f"}', "missing-value": b"{}",
                "nonstring-token": b'{"value":true}', "bad-token": b'{"value":"PRIVATE value"}'}[attack]
            response.raw = io.BytesIO(raw)
            response.headers = [("Content-Type", "application/json")]
    prepared.change = change
    with pytest.raises(entry.EntrypointError) as caught: execute(prepared)
    assert str(caught.value) == entry.ERROR and not prepared.launched
    assert prepared.get_calls == ["GET"] and prepared.exported.seen == ["challenge"]
    with pytest.raises(entry.EntrypointError): execute(prepared)
    assert prepared.get_calls == ["GET"]


@pytest.mark.parametrize("framing", ["chunked", "eof"])
def test_valid_provider_framing_does_not_invent_content_length_requirement(prepared, monkeypatch, framing):
    arm(prepared); network(prepared, monkeypatch)
    def change(response):
        response.headers.pop()
        if framing == "chunked": response.headers.append(("Transfer-Encoding", "chunked"))
    prepared.change = change
    assert execute(prepared) == {"PUBLIC-TEST-modeled-launch": True}


@pytest.mark.parametrize("failure", ["provider-error", "lost-submit", "lost-file", "launch-error", "expired", "drift"])
def test_partial_or_ambiguous_attempt_is_fail_stop_retained_and_redacted(prepared, monkeypatch, failure, capsys):
    arm(prepared); network(prepared, monkeypatch)
    if failure == "provider-error": prepared.error = RuntimeError("PRIVATE credential/JWT/provider details")
    elif failure == "lost-submit": prepared.exported.lost = "submit"
    elif failure == "lost-file": prepared.exported.lost = "file/" + sorted(prepared.exported.export._limits)[0] + "/0"
    else:
        original = prepared.own.launch
        def launch(captured):
            if failure == "launch-error": raise RuntimeError("PRIVATE signer internals")
            if failure == "expired": monkeypatch.setattr(intake.time, "time", lambda: prepared.exported.export._authenticated.valid_until)
            else: captured.retained.artifact_subject_path.write_bytes(b"changed")
            return original(captured)
        monkeypatch.setattr(prepared.own, "launch", launch)
    with pytest.raises(entry.EntrypointError) as caught: execute(prepared)
    assert str(caught.value) == entry.ERROR and caught.value.__suppress_context__
    assert prepared.client._failed and not prepared.launched
    with pytest.raises(entry.EntrypointError): execute(prepared)
    assert prepared.get_calls == ["GET"] and prepared.exported.seen.count("submit") <= 1
    if failure in {"lost-file", "launch-error", "expired", "drift"}:
        assert prepared.e._packet.is_dir() and (prepared.e._packet / "no-replay").exists()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("second_wrapper", [False, True])
def test_concurrent_second_call_cannot_consume_or_block_the_first(prepared, monkeypatch, second_wrapper):
    other = entry.ProtectedJobEntrypoint(prepared.own, **prepared.params) if second_wrapper else prepared.e
    arm(prepared); network(prepared, monkeypatch)
    reached, release = threading.Event(), threading.Event()
    def block(_): reached.set(); assert release.wait(5)
    prepared.change = block
    results = []
    thread = threading.Thread(target=lambda: results.append(execute(prepared)))
    thread.start()
    assert reached.wait(5)
    try:
        with pytest.raises(entry.EntrypointError):
            other.run(oidc_request_url=URL, oidc_request_credential=REQUEST_CREDENTIAL)
    finally:
        release.set(); thread.join(5)
    assert not thread.is_alive() and results == [{"PUBLIC-TEST-modeled-launch": True}]
    assert prepared.get_calls == ["GET"] and len(prepared.launched) == 1
