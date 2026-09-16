"""Actual RS256/SQLite/client/ASGI; modeled remote TLS and root/RO custody."""
from dataclasses import replace
import io
import struct
import time

import pytest

from scripts import android_protected_capture_intake as intake
import test_android_protected_capture_intake as transfer
from test_android_protected_capture_intake import model, exported, flow, store, signing_key


def ready(exported, monkeypatch, enabled=True):
    if enabled:
        exported.export.enable_protected_job_checks()
    client = transfer.begin(exported, monkeypatch)
    transfer.model_mounts(exported, monkeypatch)
    return client, transfer.receive(exported, client)


def test_live_same_consumed_admission_checks_do_not_rewrite_journal(exported, monkeypatch):
    client, retained = ready(exported, monkeypatch)
    before = exported.export._store._path.read_bytes()
    start = time.monotonic()
    for _ in range(3):
        assert start < client.assert_signing_fresh(retained) <= time.monotonic() + 600
    assert exported.export._store._path.read_bytes() == before
    assert exported.seen.count("submit") == 1


def test_actual_asgi_fixed_eight_byte_body_boundary(exported, monkeypatch):
    ready(exported, monkeypatch)
    assert transfer.exchange(exported, "fresh-check", b"0" * 9) == (413, b"rejected\n", 0)
    status, raw, count = transfer.exchange(exported, "fresh-check", struct.pack(">Q", 0))
    assert status == 200 and count == 1 and len(raw) == 12 and raw[:8] == b"\0" * 8
    assert 1 <= struct.unpack(">I", raw[8:])[0] <= 600


@pytest.mark.parametrize("attack", ["disabled", "facts", "store", "policy", "row", "incomplete", "other-intake", "expired"])
def test_no_detached_or_stale_authority(exported, monkeypatch, attack):
    client, retained = ready(exported, monkeypatch, enabled=attack != "disabled")
    server = exported.export
    if attack == "facts": server._authenticated = replace(server._authenticated, token_sha256="a" * 64)
    elif attack == "store": server._session._store = object()
    elif attack == "policy": server._policy = replace(server._policy, check_run_id="999")
    elif attack == "row":
        read = server._store._read
        def changed(digest):
            row, policy = read(digest)
            return (*row[:6], None, *row[7:]), policy
        monkeypatch.setattr(server._store, "_read", changed)
    elif attack == "incomplete": server._bundle_sent = False
    elif attack == "other-intake": retained = replace(retained)
    elif attack == "expired":
        monkeypatch.setattr(intake.time, "time", lambda: server._authenticated.valid_until)
        client.assert_live()  # Public-only transfer deliberately remains possible.
    with pytest.raises(intake.IntakeError): client.assert_signing_fresh(retained)
    assert client._failed
    with pytest.raises(intake.IntakeError): server.arm()


@pytest.mark.parametrize("attack", ["wrong-sequence", "short", "long", "zero", "overflow", "delayed"])
def test_fresh_response_is_bounded_correlated_and_expiry_subtracts_transit(exported, monkeypatch, attack):
    client, retained = ready(exported, monkeypatch)
    clock = [time.monotonic()]
    monkeypatch.setattr(intake.time, "monotonic", lambda: clock[0])
    def mutate(action, response):
        if action != "fresh-check": return
        raw = response.raw.getvalue()
        if attack == "wrong-sequence": raw = b"x" * 8 + raw[8:]
        elif attack == "short": raw = raw[:-1]
        elif attack == "long": raw += b"x"
        elif attack == "zero": raw = raw[:8] + struct.pack(">I", 0)
        elif attack == "overflow": raw = raw[:8] + struct.pack(">I", 601)
        else:
            raw = raw[:8] + struct.pack(">I", 1)
            clock[0] += 2  # Below HTTP's10s limit but beyond authenticated bound.
        response.raw = io.BytesIO(raw)
        response.headers[-1] = ("Content-Length", str(len(raw)))
    exported.mutate = mutate
    with pytest.raises(intake.IntakeError): client.assert_signing_fresh(retained)
    assert client._failed


def test_expiry_crossing_full_server_custody_is_rejected(exported, monkeypatch):
    client, retained = ready(exported, monkeypatch)
    now = [intake.time.time()]
    exact = exported.export._exact
    def crossed(*, full=False):
        exact(full=full)
        if full: now[0] = exported.export._authenticated.valid_until
    monkeypatch.setattr(intake.time, "time", lambda: now[0])
    monkeypatch.setattr(exported.export, "_exact", crossed)
    with pytest.raises(intake.IntakeError): client.assert_signing_fresh(retained)


def test_incomplete_client_cannot_request_fresh_signing_check(exported, monkeypatch):
    exported.export.enable_protected_job_checks()
    client = transfer.begin(exported, monkeypatch)
    with pytest.raises(intake.IntakeError): client.assert_signing_fresh(None)
    assert "fresh-check" not in exported.seen
