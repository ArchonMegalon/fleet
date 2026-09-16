"""Real SQLite/test-key RS256/capture bytes; modeled HTTP/TLS, Docker and custody.

The origin subprocess is the existing NON-CRYPTOGRAPHIC stand-in. No test runs
an attestation action, hosted job, listener, Docker, root mount or credential.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import ssl
import threading
import time
from types import SimpleNamespace

import pytest

from scripts import android_controller_rendezvous as rendezvous
from scripts import android_controller_capture as controller
from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_workflow_challenge_store as journal
from scripts import android_workflow_identity as identity
import test_android_artifact_origin as origins
import test_android_controller_capture as sessions
import test_android_workflow_challenge_store as journals
from test_android_builder_handoff import model
from test_android_workflow_challenge_store import signing_key, store

TOKENS = {role: "PUBLIC-UNIT-TEST-" + role + "-" + "x" * 40 for role in ("capture", "emission")}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def flow(model, store, signing_key, monkeypatch, tmp_path):
    first = journals.template()
    second = replace(first, check_run_id="910")
    policy = replace(origins.policy(), source_commit=first.sha,
        subject_name=capture.MANIFEST, subject_sha256=sha(model.expected[capture.MANIFEST]))
    response = origins.response()
    verified = response[0]["verificationResult"]
    verified["statement"]["subject"] = [{"name": capture.MANIFEST, "digest": {"sha256": policy.subject_sha256}}]
    verified["signature"]["certificate"].update(sourceRepositoryDigest=first.sha, buildConfigDigest=first.sha)
    verified["verifiedTimestamps"][0]["timestamp"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    verifier_dir = tmp_path / "verifier-fixture"
    verifier_dir.mkdir(mode=0o700)
    verifier = origins.standin(verifier_dir, value=response)
    args = dict(journal_path=store._path, **journals.PINS, capture_policy=first, emission_policy=second,
        artifact_policy=policy, preserved_directory=tmp_path / "preserved",
        inputs=rendezvous.CaptureInputs(model.policy, model.docker, model.lock, model.operation, "/output", model.child),
        attempt_directory=tmp_path / "rendezvous", verifier=verifier.pins[2], trusted_root=verifier.pins[3],
        base_url="https://controller.example", capture_bearer_sha256=sha(TOKENS["capture"].encode()),
        emission_bearer_sha256=sha(TOKENS["emission"].encode()), approval_bearer_sha256="1" * 64,
        binary_bearer_sha256="2" * 64)
    adapter = rendezvous.ControllerRendezvous(**args)
    f = SimpleNamespace(r=adapter, app=rendezvous.RendezvousApp(adapter), args=args, model=model, store=store,
        first=first, second=second, policy=policy, preserved=args["preserved_directory"], verifier=verifier,
        monkeypatch=monkeypatch, tmp_path=tmp_path, key=signing_key)
    f.serve = lambda issued, job: journals.serve(monkeypatch, signing_key, issued, job_id=job)
    f.token = lambda issued, **changes: journals.token_for(issued, signing_key,
        **({"jti": "PUBLIC-TEST-JTI-" + issued.check_run_id} | changes))
    yield f
    adapter.close()
    adapter._executor.shutdown(wait=True)


def request(flow, role, action, raw=b"", *, change=None, frames=None, receiver=None, fail_send=False, app=None):
    path = (flow.r.prefix + "/" + role + "/" + action).encode()
    scope = {"type": "http", "method": "POST", "scheme": "https", "path": path.decode(),
        "raw_path": path, "root_path": "", "query_string": b"", "client": ("127.0.0.1", 1234),
        "headers": [(b"host", b"controller.example"), (b"authorization", b"Bearer " + TOKENS[role].encode()),
            (b"content-type", b"application/octet-stream"), (b"content-length", str(len(raw)).encode())]}
    if change:
        change(scope)
    rows = iter(frames or [{"type": "http.request", "body": raw, "more_body": False}])
    sent, reads = [], []
    async def receive():
        reads.append(True)
        return await receiver() if receiver else next(rows)
    async def send(value):
        if fail_send:
            raise ConnectionError("PUBLIC-TEST-lost-response")
        sent.append(value)
    asyncio.run((app or flow.app)(scope, receive, send))
    return sent[0]["status"], sent[1]["body"], len(reads)


def wait(flow, state):
    with flow.r._condition:
        assert flow.r._condition.wait_for(lambda: flow.r._state in {state, "stopped"}, timeout=5)
        assert flow.r._state == state


def start_capture(flow):
    flow.r.arm_capture()
    flow.issued_capture = flow.r._issued_capture
    flow.serve(flow.issued_capture, 707)
    return request(flow, "capture", "submit", flow.token(flow.issued_capture).encode())


def captured(flow):
    assert start_capture(flow)[:2] == (202, b"queued-not-authenticated\n")
    wait(flow, "capture-complete")


def emitting(flow):
    captured(flow)
    flow.retained = sessions.retain(flow)
    flow.r.arm_emission(flow.retained)
    flow.issued_emission = flow.r._issued_emission
    flow.serve(flow.issued_emission, 708)
    assert request(flow, "emission", "submit", flow.token(flow.issued_emission).encode())[0] == 202
    wait(flow, "awaiting-bundle")


def hosted_connection(flow, monkeypatch, *, mutate_response=None, fail_after_request=False):
    """Exercise the actual HostedClient HTTP code with modeled connection only."""
    seen = []
    class Response:
        def __init__(self, status, body):
            self.status, self.raw = status, io.BytesIO(body)
            self.headers = [("Content-Type", "application/octet-stream"), ("Content-Length", str(len(body)))]
            if mutate_response:
                mutate_response(self)
        def getheaders(self): return self.headers
        def read1(self, count): return self.raw.read(count)
    class Connection:
        def __init__(self, host, *, timeout, context):
            assert host == "controller.example" and timeout == 10
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            self.sock = SimpleNamespace(settimeout=lambda value: None)
        def request(self, method, path, *, body, headers):
            assert method == "POST" and headers["Host"] == "controller.example"
            role, action = path.split("/")[-2:]
            assert headers["Authorization"] == "Bearer " + TOKENS[role]
            seen.append((role, action))
            status, result, _ = request(flow, role, action, body)
            self.response = Response(status, result)
            if fail_after_request:
                raise ConnectionError("PUBLIC-TEST-private-response")
        def getresponse(self): return self.response
        def close(self): pass
    monkeypatch.setattr(rendezvous.http.client, "HTTPSConnection", Connection)
    return seen


def client(flow, role):
    return rendezvous.HostedClient(base_url=flow.args["base_url"], transaction_id=flow.first.transaction_id,
        role=role, bearer=TOKENS[role], manifest_sha256=flow.policy.subject_sha256,
        tls_context=ssl.create_default_context())


def test_complete_actual_session_journal_and_hosted_exchange_with_modeled_remote_attester(flow, monkeypatch):
    seen = hosted_connection(flow, monkeypatch)
    first, second = client(flow, "capture"), client(flow, "emission")
    assert second.challenge() is None
    flow.r.arm_capture()
    issued = flow.r._issued_capture
    assert first.challenge() == issued.audience
    flow.serve(issued, 707)
    first.submit(flow.token(issued))
    wait(flow, "capture-complete")
    assert first.status() == "capture-complete" and flow.model.calls == ["builder"]
    assert flow.store.status(journals.key_of(issued)) == "consumed"
    assert second.challenge() is None
    retained = sessions.retain(flow)
    flow.r.arm_emission(retained)
    emission = flow.r._issued_emission
    assert emission.audience != issued.audience and second.challenge() == emission.audience
    flow.serve(emission, 708)
    second.submit(flow.token(emission))
    wait(flow, "awaiting-bundle")
    downloaded = flow.tmp_path / "hosted-public"
    downloaded.mkdir(mode=0o700)
    manifest = second.save_manifest(downloaded)
    assert manifest.path.name == capture.MANIFEST and manifest.path.read_bytes() == flow.model.expected[capture.MANIFEST]
    # Existing stand-in fixture is not an attestation action or genuine Sigstore bundle.
    second.submit_bundle(flow.verifier.pins[1])
    wait(flow, "complete")
    facts = flow.r.completed()
    assert type(facts) is controller.ControllerEmission and facts.emission_job.job_id == 708
    assert not isinstance(facts, fleet.AuthenticatedRebuildHandoff)
    assert flow.verifier.marker.exists() and flow.store.status(journals.key_of(emission)) == "consumed"
    assert flow.r._executor._max_workers == 1 and second.status() == "complete"
    assert seen.count(("capture", "submit")) == seen.count(("emission", "submit")) == seen.count(("emission", "bundle")) == 1
    assert TOKENS["capture"] not in repr(first) and TOKENS["emission"] not in repr(second)


@pytest.mark.parametrize("change", [
    {"capture_bearer_sha256": "1" * 64}, {"emission_bearer_sha256": "2" * 64},
    {"emission_bearer_sha256": sha(TOKENS["capture"].encode())}, {"binary_bearer_sha256": "1" * 64},
    {"capture_bearer_sha256": None}, {"base_url": "http://controller.example"},
    {"base_url": "https://controller.example/"}, {"base_url": "https://controller.example:443"},
])
def test_exact_credential_and_origin_admission_before_new_attempt(flow, change):
    target = flow.tmp_path / "rejected"
    with pytest.raises(rendezvous.RendezvousError, match="admission-failed"):
        rendezvous.ControllerRendezvous(**(flow.args | {"attempt_directory": target} | change))
    assert not target.exists() and flow.model.calls == []


def test_same_job_and_overlapping_capture_operation_rejected(flow):
    for change in ({"emission_policy": flow.first}, {"attempt_directory": flow.model.operation}):
        with pytest.raises(rendezvous.RendezvousError):
            rendezvous.ControllerRendezvous(**(flow.args | change))
    assert not flow.model.operation.exists()


def test_owner_capture_accessor_returns_only_actual_terminal_object(flow):
    assert flow.r.owner_state() == "unarmed"
    with pytest.raises(rendezvous.RendezvousError):
        flow.r.capture_completed()
    flow.r.arm_capture()
    issued = flow.r._issued_capture
    flow.serve(issued, 707)
    assert request(flow, "capture", "submit", flow.token(issued).encode())[0] == 202
    wait(flow, "capture-complete")
    result = flow.r.capture_completed()
    assert result is flow.r._session._captured
    assert result.directory == flow.model.operation / capture.COPY_DIRECTORY
    assert not isinstance(result, fleet.PreservedRebuildHandoff)
    assert not isinstance(result, fleet.AuthenticatedRebuildHandoff)
    flow.r.close()
    with pytest.raises(rendezvous.RendezvousError):
        flow.r.capture_completed()


@pytest.mark.parametrize("attack", ["bearer", "role", "duplicate-auth", "duplicate-host", "host", "scheme",
    "method", "query", "raw-path", "suffix", "root", "origin", "forwarded", "encoding", "transfer",
    "missing-length", "too-long", "negative-length", "large-header", "control", "unknown-custody", "arm-route"])
def test_hostile_http_rejected_before_body_or_store(flow, attack):
    def alter(scope):
        headers = dict(scope["headers"])
        if attack == "bearer": headers[b"authorization"] = b"Bearer incorrect"
        elif attack == "role": headers[b"authorization"] = b"Bearer " + TOKENS["emission"].encode()
        elif attack == "duplicate-auth": scope["headers"].append((b"Authorization", headers[b"authorization"])); return
        elif attack == "duplicate-host": scope["headers"].append((b"Host", b"controller.example")); return
        elif attack == "host": headers[b"host"] = b"wrong.example"
        elif attack == "scheme": scope["scheme"] = "http"
        elif attack == "method": scope["method"] = "GET"
        elif attack == "query": scope["query_string"] = b"override=1"
        elif attack == "raw-path": scope["raw_path"] = scope["raw_path"].replace(b"capture", b"%63apture")
        elif attack == "suffix": scope["raw_path"] += b"/"; scope["path"] += "/"
        elif attack == "root": scope["root_path"] = "/proxy"
        elif attack == "origin": headers[b"origin"] = b"https://controller.example"
        elif attack == "forwarded": headers[b"x-forwarded-for"] = b"127.0.0.1"
        elif attack == "encoding": headers[b"content-encoding"] = b"gzip"
        elif attack == "transfer": headers[b"transfer-encoding"] = b"chunked"
        elif attack == "missing-length": del headers[b"content-length"]
        elif attack == "too-long": headers[b"content-length"] = b"32769"
        elif attack == "negative-length": headers[b"content-length"] = b"-1"
        elif attack == "large-header": headers[b"x-extra"] = b"x" * 16384
        elif attack == "control": headers[b"x-extra"] = b"secret\n"
        else:
            scope["path"] = flow.r.prefix + "/capture/" + ("custody" if attack == "unknown-custody" else "arm")
            scope["raw_path"] = scope["path"].encode()
        scope["headers"] = list(headers.items())
    status, raw, reads = request(flow, "capture", "submit", b"PRIVATE-TEST-TOKEN", change=alter)
    assert status >= 400 and reads == 0 and b"PRIVATE" not in raw
    assert flow.r._state == "unarmed" and flow.model.calls == []


@pytest.mark.parametrize("change", [{"aud": "wrong"}, {"check_run_id": "910"}, {"run_attempt": "3"}, {"sha": "a" * 40}])
def test_transport_access_never_replaces_exact_job_authentication(flow, change):
    flow.r.arm_capture()
    issued = flow.r._issued_capture
    flow.serve(issued, 707)
    assert request(flow, "capture", "submit", flow.token(issued, **change).encode())[:2] == (202, b"queued-not-authenticated\n")
    wait(flow, "stopped")
    assert flow.model.calls == []
    assert flow.store.status(journals.key_of(issued)) == "pending"
    assert request(flow, "capture", "submit", flow.token(issued).encode())[0] == 409


def test_concurrent_duplicate_submission_runs_only_one_capture(flow):
    flow.r.arm_capture()
    issued = flow.r._issued_capture
    flow.serve(issued, 707)
    raw = flow.token(issued).encode()
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: request(flow, "capture", "submit", raw)[0], range(2)))
    assert sorted(replies) == [202, 409]
    wait(flow, "capture-complete")
    assert flow.model.calls == ["builder"]


def test_committed_then_failed_issue_is_poisoned_never_reissued(flow, monkeypatch):
    actual = journal.SQLiteWorkflowChallengeStore.issue
    def lost(self, policy):
        actual(self, policy)
        raise OSError("PRIVATE-TEST-post-commit")
    monkeypatch.setattr(journal.SQLiteWorkflowChallengeStore, "issue", lost)
    with pytest.raises(rendezvous.RendezvousError, match="arm-failed-no-retry") as error:
        flow.r.arm_capture()
    assert "PRIVATE" not in str(error.value) and flow.r._state == "stopped"
    with pytest.raises(rendezvous.RendezvousError, match="already-armed"):
        flow.r.arm_capture()
    assert (flow.args["attempt_directory"] / "no-replay").is_file()


def test_restarted_same_path_and_new_path_same_journal_cannot_replay(flow):
    captured(flow)
    flow.r.close()
    with pytest.raises(rendezvous.RendezvousError):
        rendezvous.ControllerRendezvous(**flow.args)
    # A new operation path does not evade the journal's permanent exact job slot.
    inputs = replace(flow.args["inputs"], operation_directory=flow.tmp_path / "new-operation")
    other = rendezvous.ControllerRendezvous(**(flow.args | {"attempt_directory": flow.tmp_path / "new-attempt", "inputs": inputs}))
    try:
        with pytest.raises(rendezvous.RendezvousError, match="arm-failed"):
            other.arm_capture()
    finally:
        other.close()
    assert flow.model.calls == ["builder"] and not inputs.operation_directory.exists()


def test_http_lost_ack_does_not_cancel_or_replay_capture(flow):
    flow.r.arm_capture()
    issued = flow.r._issued_capture
    flow.serve(issued, 707)
    with pytest.raises(ConnectionError):
        request(flow, "capture", "submit", flow.token(issued).encode(), fail_send=True)
    wait(flow, "capture-complete")
    assert request(flow, "capture", "submit", flow.token(issued).encode())[0] == 409
    assert flow.model.calls == ["builder"]


def test_hosted_client_lost_reply_latches_without_retry(flow, monkeypatch):
    flow.r.arm_capture()
    issued = flow.r._issued_capture
    flow.serve(issued, 707)
    seen = hosted_connection(flow, monkeypatch, fail_after_request=True)
    hosted = client(flow, "capture")
    with pytest.raises(rendezvous.RendezvousError, match="failed-no-retry"):
        hosted.submit(flow.token(issued))
    with pytest.raises(rendezvous.RendezvousError, match="already-submitted"):
        hosted.submit(flow.token(issued))
    wait(flow, "capture-complete")
    assert seen == [("capture", "submit")]


def test_owner_custody_cannot_be_a_dictionary_or_writable_capture(flow):
    captured(flow)
    with pytest.raises(rendezvous.RendezvousError, match="emission-arm-failed"):
        flow.r.arm_emission({"rootOwned": True, "readOnly": True})
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(flow.model.lock.path, flow.model.operation / capture.COPY_DIRECTORY)
    assert flow.r._issued_emission is None


@pytest.mark.parametrize("stage", ["manifest", "bundle"])
def test_expired_emission_blocks_disclosure_and_acceptance(flow, monkeypatch, stage):
    emitting(flow)
    current = flow.r._facts.valid_until + 1
    monkeypatch.setattr(rendezvous, "time", SimpleNamespace(time=lambda: current))
    raw = flow.verifier.pins[1].path.read_bytes() if stage == "bundle" else b""
    assert request(flow, "emission", stage, raw)[0] == 409
    wait(flow, "stopped")
    assert not flow.verifier.marker.exists()


@pytest.mark.parametrize("attack", ["manifest", "marker-replaced", "bundle-symlink", "partial-write"])
def test_custody_or_bundle_write_failure_stops_and_preserves_evidence(flow, monkeypatch, attack):
    emitting(flow)
    bundle_path = flow.args["attempt_directory"] / "bundle.json"
    if attack == "manifest":
        flow.retained.artifact_subject_path.write_bytes(b"changed")
    elif attack == "marker-replaced":
        marker = flow.args["attempt_directory"] / "no-replay"
        marker.rename(marker.with_name("original-marker"))
        marker.write_bytes(rendezvous._MARKER)
        marker.chmod(0o600)
    elif attack == "bundle-symlink":
        bundle_path.symlink_to(flow.verifier.pins[1].path)
    else:
        actual = rendezvous._write_new
        def partial(path, raw):
            actual(path, b"{")
            raise OSError("PRIVATE-TEST-partial-write")
        monkeypatch.setattr(rendezvous, "_write_new", partial)
    assert request(flow, "emission", "bundle", flow.verifier.pins[1].path.read_bytes())[0] == 409
    wait(flow, "stopped")
    assert not flow.verifier.marker.exists()
    if attack == "partial-write": assert bundle_path.read_bytes() == b"{"


def test_duplicate_bundle_is_not_overwritten(flow):
    emitting(flow)
    raw = flow.verifier.pins[1].path.read_bytes()
    assert request(flow, "emission", "bundle", raw)[0] == 202
    assert request(flow, "emission", "bundle", b'{"different":true}')[0] == 409
    wait(flow, "complete")
    assert (flow.args["attempt_directory"] / "bundle.json").read_bytes() == raw


@pytest.mark.parametrize("kind", ["oversize", "length", "disconnect", "empty-stream", "slow"])
def test_streamed_body_bounds_deadlines_and_capacity_release(flow, monkeypatch, kind):
    frames, receiver = None, None
    raw = b"x"
    if kind == "oversize": frames = [{"type": "http.request", "body": b"x" * (identity.MAX_TOKEN + 1)}]
    elif kind == "length": frames = [{"type": "http.request", "body": b"xx"}]
    elif kind == "disconnect": frames = [{"type": "http.disconnect"}]
    else:
        actual = asyncio.wait_for
        monkeypatch.setattr(rendezvous.asyncio, "wait_for", lambda awaitable, timeout: actual(awaitable, timeout=.01))
        async def receive():
            if kind == "slow": await asyncio.sleep(.1)
            return {"type": "http.request", "body": b"", "more_body": True}
        receiver = receive
    assert request(flow, "capture", "submit", raw, frames=frames, receiver=receiver)[0] == 400
    assert request(flow, "capture", "challenge")[:2] == (200, b"pending\n")
    assert flow.model.calls == []


@pytest.mark.parametrize("attack", ["redirect", "oversize", "duplicate", "encoded", "truncated"])
def test_hosted_response_is_bounded_without_redirect_or_retry(flow, monkeypatch, attack):
    flow.r.arm_capture()
    def mutate(response):
        if attack == "redirect": response.status = 302
        elif attack == "oversize": response.headers[1] = ("Content-Length", "99999999")
        elif attack == "duplicate": response.headers.append(("content-length", "1"))
        elif attack == "encoded": response.headers.append(("Content-Encoding", "gzip"))
        else: response.raw = io.BytesIO(b"")
    seen = hosted_connection(flow, monkeypatch, mutate_response=mutate)
    with pytest.raises(rendezvous.RendezvousError, match="failed-no-retry"):
        client(flow, "capture").challenge()
    assert seen == [("capture", "challenge")]


def test_proxy_transport_peer_is_exact_and_forwarded_identity_is_not_trusted(flow):
    app = rendezvous.RendezvousApp(flow.r, trusted_proxy_addresses=("127.0.0.1",))
    def forwarding(scope):
        scope["headers"] += [(b"x-forwarded-for", b"opaque untrusted data"), (b"x-forwarded-proto", b"https")]
    assert request(flow, "capture", "challenge", change=forwarding, app=app)[:2] == (200, b"pending\n")
    def wrong_peer(scope):
        forwarding(scope)
        scope["client"] = ("127.0.0.2", 1234)
    assert request(flow, "capture", "challenge", change=wrong_peer, app=app)[0] == 400
    assert request(flow, "capture", "challenge", app=app)[0] == 400


def test_emission_issue_committed_then_lost_never_renews(flow, monkeypatch):
    captured(flow)
    retained = sessions.retain(flow)
    actual = journal.SQLiteWorkflowChallengeStore.issue
    def lost(self, policy):
        actual(self, policy)
        raise OSError("PRIVATE-TEST-post-emission-commit")
    monkeypatch.setattr(journal.SQLiteWorkflowChallengeStore, "issue", lost)
    with pytest.raises(rendezvous.RendezvousError, match="emission-arm-failed"):
        flow.r.arm_emission(retained)
    with pytest.raises(rendezvous.RendezvousError, match="not-armable"):
        flow.r.arm_emission(retained)
    assert flow.r._state == "stopped" and not flow.verifier.marker.exists()


def test_closed_controller_cannot_promote_late_builder_completion(flow, monkeypatch):
    started, release = threading.Event(), threading.Event()
    actual = sessions.capture.run_builder_capture_handoff
    def delayed(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return actual(*args, **kwargs)
    monkeypatch.setattr(sessions.capture, "run_builder_capture_handoff", delayed)
    start_capture(flow)
    assert started.wait(3)
    flow.r.close()
    release.set()
    flow.r._executor.shutdown(wait=True)
    assert flow.model.calls == ["builder"] and flow.r._state == "stopped"
    with pytest.raises(rendezvous.RendezvousError, match="stopped"):
        flow.r.completed()


def test_bundle_limit_rejected_before_body_and_unsafe_bundle_never_verified(flow):
    emitting(flow)
    def oversized(scope):
        scope["headers"] = [(k, str(rendezvous.MAX_BUNDLE + 1).encode() if k == b"content-length" else v)
                            for k, v in scope["headers"]]
    status, _, reads = request(flow, "emission", "bundle", change=oversized)
    assert status == 413 and reads == 0
    assert request(flow, "emission", "bundle", b'{"same":1,"same":2}')[0] == 409
    wait(flow, "stopped")
    assert not (flow.args["attempt_directory"] / "bundle.json").exists()
    assert not flow.verifier.marker.exists()


def test_wrong_origin_result_cannot_become_completion(flow, monkeypatch):
    emitting(flow)
    def reject(*args, **kwargs):
        raise origin.OriginError("PRIVATE-TEST-wrong-origin")
    monkeypatch.setattr(origin, "verify_rebuild_handoff_origin", reject)
    assert request(flow, "emission", "bundle", flow.verifier.pins[1].path.read_bytes())[0] == 202
    wait(flow, "stopped")
    assert (flow.args["attempt_directory"] / "bundle.json").is_file()
    with pytest.raises(rendezvous.RendezvousError): flow.r.completed()


def test_expiry_during_manifest_recheck_is_fenced_before_disclosure(flow, monkeypatch):
    emitting(flow)
    actual = origin._CapturedFile.recheck
    instant = [int(time.time())]
    def recheck(snapshot):
        actual(snapshot)
        if snapshot is flow.r._manifest:
            instant[0] = flow.r._facts.valid_until + 1
    monkeypatch.setattr(origin._CapturedFile, "recheck", recheck)
    monkeypatch.setattr(rendezvous, "time", SimpleNamespace(time=lambda: instant[0]))
    status, body, _ = request(flow, "emission", "manifest")
    assert status == 409 and body == b"stopped-reconcile\n"


def test_bounded_body_readers_and_cancellation_do_not_create_work(flow):
    async def run():
        entered = 0
        ready, release = asyncio.Event(), asyncio.Event()
        path = (flow.r.prefix + "/capture/submit").encode()
        scope = {"type": "http", "method": "POST", "scheme": "https", "path": path.decode(),
            "raw_path": path, "query_string": b"", "headers": [(b"host", b"controller.example"),
            (b"authorization", b"Bearer " + TOKENS["capture"].encode()),
            (b"content-type", b"application/octet-stream"), (b"content-length", b"1")]}
        async def receive():
            nonlocal entered
            entered += 1
            if entered == 2: ready.set()
            await release.wait()
            return {"type": "http.request", "body": b"x"}
        async def discard(value): pass
        tasks = [asyncio.create_task(flow.app(scope, receive, discard)) for _ in range(2)]
        await asyncio.wait_for(ready.wait(), 1)
        replies = []
        async def capture_response(value): replies.append(value)
        await flow.app(scope, receive, capture_response)
        assert replies[0]["status"] == 429 and entered == 2
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert flow.app._readers.acquire(blocking=False)
        assert flow.app._readers.acquire(blocking=False)
        flow.app._readers.release(); flow.app._readers.release()
    asyncio.run(run())
    assert flow.r._state == "unarmed" and flow.model.calls == []


def test_hosted_tls_cannot_be_disabled_or_downgraded(flow, monkeypatch):
    hosted = client(flow, "capture")
    seen = hosted_connection(flow, monkeypatch)
    hosted._tls.check_hostname = False
    hosted._tls.verify_mode = ssl.CERT_NONE
    with pytest.raises(rendezvous.RendezvousError, match="failed-no-retry"):
        hosted.challenge()
    assert seen == []


def test_hosted_manifest_swapping_and_exclusive_destination(flow, monkeypatch):
    emitting(flow)
    hosted_connection(flow, monkeypatch)
    hosted = client(flow, "emission")
    directory = flow.tmp_path / "hosted"
    directory.mkdir(mode=0o700)
    hosted._manifest_sha = "0" * 64
    with pytest.raises(rendezvous.RendezvousError, match="manifest-response"):
        hosted.save_manifest(directory)
    assert list(directory.iterdir()) == []
    hosted._manifest_sha = flow.policy.subject_sha256
    pin = hosted.save_manifest(directory)
    with pytest.raises(FileExistsError): hosted.save_manifest(directory)
    assert pin.path.read_bytes() == flow.model.expected[capture.MANIFEST]
