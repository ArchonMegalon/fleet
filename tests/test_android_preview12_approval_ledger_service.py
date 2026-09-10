"""Actual ASGI + SQLite + unchanged PR11 client; public RFC test signatures only.

No sockets, provider, protected environment, deployed TLS or signing-custody
claim. Direct ASGI messages intentionally preserve duplicate headers and chunks.
"""
import asyncio
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from fastapi import FastAPI
import pytest

from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_service as service
from scripts import android_preview12_approval_ledger_store as persistence


_spec = importlib.util.spec_from_file_location(
    "ledger_service_public_fixture", Path(__file__).with_name("test_android_preview12_approval_ledger.py")
)
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)
TOKEN = b"public-test-token"
TOKEN_DIGEST = hashlib.sha256(TOKEN).hexdigest()
SENTINEL = "PRIVATE-TEST-SENTINEL-DO-NOT-EXPOSE"
APPROVAL = b' {"testOnly":true,"publicationAuthorized":false}\r\n'
PREFIX = "/v1/preview12-approval-reservations/"


def raw_request(operation="reserve", *, subject=None, prior=None, approval=APPROVAL):
    payload = None if operation != "commit" else {
        "sha256": hashlib.sha256(approval).hexdigest(), "sizeBytes": len(approval),
        "publicJsonBase64": base64.b64encode(approval).decode("ascii"),
    }
    return protocol.canonical_bytes(protocol._request(
        operation, subject or fixture.subject(), prior_reservation=prior, approval=payload,
        abort_reason="operator_abort" if operation == "abort" else None,
    ))


def sign(raw):
    envelope = fixture.sign(json.loads(raw))
    return base64.b64decode(envelope["signature"]["signatureBase64"])


class CountingStore(persistence.SQLiteApprovalLedgerStore):
    calls = 0

    def process(self, *args, **kwargs):
        self.calls += 1
        return super().process(*args, **kwargs)


@pytest.fixture
def bound(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "ledger.sqlite3"
    store = CountingStore.create(path, service_identity="chummer.preview12.approval-ledger", database_id="c" * 64)
    policy = fixture.active_ledger_policy()
    signatures = []

    def signer(raw):
        signatures.append(raw)
        return sign(raw)

    arguments = dict(ledger_policy=policy, store=store, bearer_token_sha256=TOKEN_DIGEST, sign_receipt=signer)
    return path, store, policy, signatures, arguments


def headers(body, **replace):
    values = {
        "host": "ledger.example.test", "authorization": "Bearer " + TOKEN.decode(),
        "content-type": "application/json", "content-length": str(len(body)),
    }
    values.update(replace)
    return [(key.encode("ascii"), value.encode("ascii")) for key, value in values.items() if value is not None]


async def exchange(app, body=None, *, operation="reserve", raw_headers=None, changes=None,
                   events=None, receive_override=None, send_override=None):
    body = raw_request(operation) if body is None else body
    path = PREFIX + operation
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "https", "path": path, "raw_path": path.encode(),
        "root_path": "", "query_string": b"", "headers": headers(body) if raw_headers is None else raw_headers,
        "client": ("127.0.0.1", 40000), "server": ("ledger.example.test", 443),
    }
    scope.update(changes or {})
    queue = list(events) if events is not None else [{"type": "http.request", "body": body, "more_body": False}]
    sent = []

    async def receive():
        if receive_override is not None:
            return await receive_override()
        if queue:
            return queue.pop(0)
        await asyncio.Future()  # Detect unexpected extra receives via test timeout.

    async def send(message):
        if send_override is not None:
            await send_override(message)
        sent.append(message)

    await asyncio.wait_for(app(scope, receive, send), timeout=5)
    status = next(message["status"] for message in sent if message["type"] == "http.response.start")
    payload = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    response_headers = dict(next(message["headers"] for message in sent if message["type"] == "http.response.start"))
    return status, payload, response_headers


def invoke(app, *args, **kwargs):
    return asyncio.run(exchange(app, *args, **kwargs))


def test_factory_requires_explicit_authority_and_has_only_four_post_routes(bound):
    path, store, policy, signatures, arguments = bound
    before = path.read_bytes()
    invalid = [
        {"ledger_policy": protocol.dormant_ledger_policy()},
        {"ledger_policy": dict(policy, expected_service_identity="different.service")},
        {"store": None}, {"bearer_token_sha256": None}, {"bearer_token_sha256": "F" * 64},
        {"sign_receipt": None}, {"maximum_in_flight": True}, {"maximum_in_flight": 0},
        {"maximum_in_flight": 9}, {"body_timeout_seconds": 0}, {"body_timeout_seconds": 11},
        {"body_timeout_seconds": float("nan")}, {"body_timeout_seconds": True},
    ]
    for changed in invalid:
        with pytest.raises(service.ServiceConfigurationError) as error:
            service.create_app(**dict(arguments, **changed))
        assert error.value.__context__ is None and error.value.__cause__ is None
    app = service.create_app(**arguments)
    assert isinstance(app, FastAPI) and not hasattr(service, "app")
    assert {route.path for route in app.routes} == {PREFIX + name for name in ("reserve", "commit", "abort", "status")}
    assert all(route.methods == {"POST"} for route in app.routes)
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


@pytest.mark.parametrize("changed,status", [
    ({"scheme": "http"}, 400), ({"query_string": b"token=secret"}, 400),
    ({"root_path": "/proxy"}, 404), ({"method": "GET"}, 405),
    ({"method": "HEAD"}, 405), ({"method": "OPTIONS"}, 405),
    ({"raw_path": (PREFIX + "reserve/").encode()}, 404),
    ({"raw_path": (PREFIX + "%72eserve").encode()}, 404),
    ({"raw_path": None}, 404), ({"path": PREFIX + "commit"}, 404),
    ({"path": "/docs", "raw_path": b"/docs"}, 404),
    ({"path": "/openapi.json", "raw_path": b"/openapi.json"}, 404),
])
def test_noncanonical_request_target_is_closed_before_body(bound, changed, status):
    path, store, _, signatures, arguments = bound
    before = path.read_bytes()

    async def forbidden_receive():
        pytest.fail("rejected request consumed its body")

    result = invoke(service.create_app(**arguments), changes=changed, receive_override=forbidden_receive)
    assert result[0] == status and b"location" not in result[2]
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


@pytest.mark.parametrize("changed,status", [
    ({"host": "other.example.test"}, 400), ({"host": "ledger.example.test:443"}, 400),
    ({"host": "LEDGER.example.test"}, 400), ({"host": "ledger.example.test."}, 400),
    ({"host": None}, 400), ({"origin": "https://ledger.example.test"}, 403),
    ({"origin": "null"}, 403), ({"x-forwarded-proto": "https"}, 400),
    ({"forwarded": "host=ledger.example.test;proto=https"}, 400),
    ({"authorization": None}, 401), ({"authorization": "Bearer wrong"}, 401),
    ({"authorization": "bearer public-test-token"}, 401),
    ({"authorization": "Bearer public-test-token "}, 401),
    ({"authorization": "Bearer " + "a" * 4097}, 401),
    ({"authorization": None, "x-fleet-internal-token": TOKEN.decode()}, 401),
    ({"authorization": None, "cookie": "token=" + TOKEN.decode()}, 401),
    ({"content-type": "text/plain"}, 415), ({"content-encoding": "identity"}, 415),
    ({"content-encoding": "gzip"}, 415), ({"transfer-encoding": "chunked"}, 400),
    ({"content-length": "65537"}, 413), ({"content-length": "01"}, 400),
    ({"content-length": "1,1"}, 400), ({"content-length": "-1"}, 400),
])
def test_headers_and_auth_fail_without_body_read_or_mutation(bound, changed, status):
    path, store, _, signatures, arguments = bound
    body = raw_request()
    before = path.read_bytes()

    async def forbidden_receive():
        pytest.fail("rejected headers consumed body")

    result = invoke(service.create_app(**arguments), body, raw_headers=headers(body, **changed),
                    receive_override=forbidden_receive)
    assert result[0] == status and TOKEN not in result[1]
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


@pytest.mark.parametrize("extra", [
    (b"Authorization", b"Bearer public-test-token"), (b"HOST", b"ledger.example.test"),
    (b"content-length", b"1"), (b"content-type", b"application/json"),
    (b"x-unused", b"line\r\nbreak"), (b"bad name", b"ignored"),
])
def test_duplicate_and_control_headers_fail_closed(bound, extra):
    path, store, _, signatures, arguments = bound
    body = raw_request()
    before = path.read_bytes()
    assert invoke(service.create_app(**arguments), body, raw_headers=headers(body) + [extra])[0] == 400
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


@pytest.mark.parametrize("body", [
    b"", b"null", b"[]", b"\xff", b'{"operation":"reserve","operation":"commit"}',
    b'{"n":NaN}', b"[" * 2000 + b"0" + b"]" * 2000,
])
def test_hostile_json_is_fixed_rejection_before_store(bound, body):
    path, store, _, signatures, arguments = bound
    before = path.read_bytes()
    result = invoke(service.create_app(**arguments), body)
    assert result[:2] == (400, b'{"error":"invalid_request"}')
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


def test_exact_request_shape_and_route_operation_are_checked_before_store(bound):
    path, store, _, signatures, arguments = bound
    app = service.create_app(**arguments)
    before = path.read_bytes()
    value = json.loads(raw_request())
    for changed in (dict(value, extra=True), dict(value, contractVersion=True), dict(value, requestId="0" * 64)):
        assert invoke(app, protocol.canonical_bytes(changed))[0] == 400
    assert invoke(app, raw_request("status"), operation="reserve")[0] == 400
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


def test_actual_stream_size_and_declared_size_are_independently_bounded(bound):
    path, store, _, signatures, arguments = bound
    app = service.create_app(**arguments)
    raw = raw_request()
    before = path.read_bytes()
    for declared in (str(len(raw) + 1), str(len(raw) - 1)):
        assert invoke(app, raw, raw_headers=headers(raw, **{"content-length": declared}))[0] == 400
    for declared in (None, "1"):
        events = [{"type": "http.request", "body": b" " * 32768, "more_body": True},
                  {"type": "http.request", "body": b" " * 32769, "more_body": True}]
        assert invoke(app, raw, raw_headers=headers(raw, **{"content-length": declared}), events=events)[0] == 413
    assert path.read_bytes() == before and store.calls == 0 and signatures == []
    # Maximum raw envelope including harmless JSON whitespace is accepted.
    padded = raw + b" " * (65536 - len(raw))
    events = [{"type": "http.request", "body": padded[:32768], "more_body": True},
              {"type": "http.request", "body": padded[32768:], "more_body": False}]
    assert invoke(app, padded, events=events)[0] == 200


def test_body_deadline_and_disconnect_release_admission_without_mutation(bound):
    path, store, _, signatures, arguments = bound
    app = service.create_app(**arguments, maximum_in_flight=1, body_timeout_seconds=0.02)
    before = path.read_bytes()

    async def never_body():
        await asyncio.Future()

    assert invoke(app, receive_override=never_body)[0] == 408
    assert invoke(app, events=[{"type": "http.disconnect"}])[0] == 400
    assert path.read_bytes() == before and store.calls == 0 and signatures == []
    assert invoke(app)[0] == 200


def test_body_read_itself_occupies_bounded_admission(bound):
    path, store, _, signatures, arguments = bound
    app = service.create_app(**arguments, maximum_in_flight=1)

    async def exercise():
        started = asyncio.Event()

        async def hold_body():
            started.set()
            await asyncio.Future()

        pending = asyncio.create_task(exchange(app, receive_override=hold_body))
        await asyncio.wait_for(started.wait(), 2)
        try:
            assert (await exchange(app))[0] == 429
            assert store.calls == 0 and signatures == []
        finally:
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        assert (await exchange(app))[0] == 200

    asyncio.run(exercise())


@pytest.mark.parametrize("mode", ["short", "long", "mutable", "wrong_signature", "throws", "throws_conflict"])
def test_bad_signer_output_cannot_be_returned_as_authority_or_undo_reservation(bound, mode):
    path, store, policy, _, arguments = bound

    def invalid_signer(raw):
        if mode == "throws":
            raise RuntimeError(SENTINEL)
        if mode == "throws_conflict":
            raise persistence.Conflict(SENTINEL)
        return {"short": b"0" * 63, "long": b"0" * 65, "mutable": bytearray(64),
                "wrong_signature": b"0" * 64}[mode]

    bad = service.create_app(**dict(arguments, sign_receipt=invalid_signer))
    result = invoke(bad)
    assert result[:2] == (503, b'{"error":"service_unavailable"}') and SENTINEL.encode() not in result[1]
    good = service.create_app(**arguments)
    recovered = json.loads(invoke(good)[1])
    protocol.validate_response(recovered, request=json.loads(raw_request()), policy=policy)
    assert recovered["receipt"]["revision"] == 1
    assert store.calls == 2


def test_wrong_reviewed_receipt_pin_rejects_otherwise_real_signature(bound):
    _, _, policy, _, arguments = bound
    other_policy = copy.deepcopy(policy)
    public_der = bytearray(base64.b64decode(policy["receipt_public_key_spki_der_base64"]))
    public_der[-1] ^= 1
    other_policy["receipt_public_key_spki_der_base64"] = base64.b64encode(public_der).decode()
    other_policy["receipt_public_key_spki_sha256"] = hashlib.sha256(public_der).hexdigest()
    app = service.create_app(**dict(arguments, ledger_policy=other_policy))
    assert invoke(app)[:2] == (503, b'{"error":"service_unavailable"}')


def test_header_count_and_total_bytes_are_bounded_before_body(bound):
    path, store, _, signatures, arguments = bound
    app = service.create_app(**arguments)
    raw = raw_request()
    before = path.read_bytes()
    too_many = headers(raw) + [(f"x-{index}".encode(), b"a") for index in range(29)]
    too_large = headers(raw) + [(b"x-metadata", b"a" * 16384)]
    for incoming in (too_many, too_large):
        assert invoke(app, raw, raw_headers=incoming)[0] == 400
    assert path.read_bytes() == before and store.calls == 0 and signatures == []


def test_all_store_outcomes_and_lost_send_preserve_exact_terminal_state(bound):
    _, _, _, _, arguments = bound
    app = service.create_app(**arguments)
    assert invoke(app, raw_request("status"), operation="status")[0] == 404
    reserve = json.loads(invoke(app)[1])
    prior = {"reservationId": reserve["receipt"]["reservationId"], "priorRevision": 1,
             "reservationReceiptSha256": reserve["receiptSha256"]}

    async def lose_send(message):
        if message["type"] == "http.response.start":
            raise ConnectionError("test client disconnected after commit")

    commit = raw_request("commit", prior=prior)
    with pytest.raises(ConnectionError, match="test client disconnected"):
        invoke(app, commit, operation="commit", send_override=lose_send)
    status, result, _ = invoke(app, raw_request("status", prior=prior), operation="status")
    receipt = json.loads(result)["receipt"]
    assert status == 200 and receipt["state"] == "committed" and receipt["revision"] == 2
    assert base64.b64decode(receipt["approval"]["publicJsonBase64"]) == APPROVAL
    assert invoke(app, raw_request("abort", prior=prior), operation="abort")[0] == 409
    assert invoke(app, commit, operation="commit")[0] == 200
    second = fixture.subject(approval_request_nonce="6" * 64, two_green_artifact_id=9989938591)
    reserved = json.loads(invoke(app, raw_request(subject=second))[1])
    prior = {"reservationId": reserved["receipt"]["reservationId"], "priorRevision": 1,
             "reservationReceiptSha256": reserved["receiptSha256"]}
    aborted = invoke(app, raw_request("abort", subject=second, prior=prior), operation="abort")
    assert aborted[0] == 200 and json.loads(aborted[1])["receipt"]["state"] == "aborted"
    assert invoke(app, raw_request("commit", subject=second, prior=prior), operation="commit")[0] == 409


def test_factory_copies_policy_and_store_failure_does_not_leak_or_recreate(bound):
    path, store, policy, signatures, arguments = bound
    app = service.create_app(**arguments)
    policy["allowed_hosts"].append("other.example.test")
    policy["receipt_public_key_spki_sha256"] = "0" * 64
    assert invoke(app)[0] == 200
    path.rename(path.with_name("retained.sqlite3"))
    assert invoke(app)[:2] == (503, b'{"error":"service_unavailable"}')
    assert not path.exists() and len(signatures) == 1


def test_cancelled_signer_await_keeps_capacity_until_actual_worker_finishes(bound):
    _, store, _, _, arguments = bound
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    signer_calls = []

    def held_signer(raw):
        signer_calls.append(raw)
        entered.set()
        try:
            assert release.wait(3), "test worker barrier deadline"
            return sign(raw)
        finally:
            finished.set()

    app = service.create_app(**dict(arguments, sign_receipt=held_signer), maximum_in_flight=1)

    async def exercise():
        pending = asyncio.create_task(exchange(app))
        assert await asyncio.to_thread(entered.wait, 2)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        try:
            # The reservation already committed, but the signer thread is live.
            assert (await exchange(app))[0] == 429
            assert store.calls == 1 and len(signer_calls) == 1
        finally:
            release.set()
        assert await asyncio.to_thread(finished.wait, 2)
        # shutdown_default_executor joins completion without polling or another
        # mutation; a fresh loop then observes released admission.

    try:
        asyncio.run(exercise())
    finally:
        release.set()
    assert invoke(app)[0] == 200
    assert store.calls == 2 and len(signer_calls) == 2


def test_signed_service_roundtrip_and_lost_outcome_use_unchanged_client(bound):
    _, _, policy, signatures, arguments = bound
    app = service.create_app(**arguments)
    operations = []
    drops = {"reserve": 3, "commit": 3}

    def transport(url, body, incoming_headers, timeout):
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.hostname == "ledger.example.test" and timeout == 10
        operation = json.loads(body)["operation"]
        assert url == policy["base_url"] + policy[operation + "_path"]
        operations.append(operation)
        # Forward actual unchanged-client headers; only these two are normally
        # supplied by its urllib HTTP transport for a known-length bytes body.
        raw_headers = [(key.lower().encode("ascii"), value.encode("ascii"))
                       for key, value in incoming_headers.items()]
        raw_headers.extend([(b"host", parsed.netloc.encode("ascii")),
                            (b"content-length", str(len(body)).encode("ascii"))])
        assert incoming_headers["Authorization"] == "Bearer " + TOKEN.decode()
        status, result, response_headers = invoke(app, body, operation=operation,
                                                  changes={"path": parsed.path, "raw_path": parsed.path.encode()},
                                                  raw_headers=raw_headers)
        if drops.get(operation, 0):
            drops[operation] -= 1
            assert status == 200
            raise TimeoutError("public test response lost after ASGI completion")
        return protocol.HttpResponse(status, {key.decode(): value.decode() for key, value in response_headers.items()}, result)

    def client():
        return protocol.DurableApprovalLedgerClient(copy.deepcopy(policy),
            {protocol.CREDENTIAL_ENV_NAME: TOKEN.decode()}, transport=transport, sleeper=lambda _: None)

    subject = fixture.subject()
    reserve = client().reserve(subject)
    assert operations == ["reserve", "reserve", "reserve", "status", "reserve"]
    committed = client().commit(subject, APPROVAL, reserve)
    assert operations[-4:] == ["commit", "commit", "commit", "status"]
    assert committed["receipt"]["state"] == "committed"
    assert base64.b64decode(committed["receipt"]["approval"]["publicJsonBase64"]) == APPROVAL
    recovered = client().reserve(subject)
    assert recovered["receipt"]["revision"] == 2 and recovered["receipt"]["approval"] == committed["receipt"]["approval"]
    with pytest.raises(protocol.LedgerError, match="HTTP 409"):
        client().reserve(fixture.subject(approval_request_nonce="6" * 64))
    assert len(signatures) >= 10  # Receipt signing repeats; approval signing is absent.
