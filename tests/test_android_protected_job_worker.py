"""Real private frames/files/transaction flow; modeled custody and signatures.

No Docker, namespaces, mounts, secret providers, real keys or SDK are exercised.
Ordinary subprocess termination below is NOT PID1 namespace-reaping evidence.
"""
import base64
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from scripts import android_protected_job_worker as worker
from scripts import android_preview12_signer_credentials as credentials
import test_android_preview12_protected_transaction as transaction


def local_session(connection):
    # Only kernel/PID1 admission is modeled. Production constructor is not run.
    session = worker.Session.__new__(worker.Session)
    session._socket, session._mutex, session._done = connection, threading.RLock(), threading.Event()
    session._sequence, session._deadline = 0, time.monotonic() + 30
    return session


def test_actual_private_frame_socketpair_is_correlated_and_bounded():
    left, right = socket.socketpair()
    try:
        worker.send(left, {"sequence": 0, "operation": "check"})
        assert worker.receive(right) == {"sequence": 0, "operation": "check"}
        left.sendall(struct.pack(">I", worker.MAX_FRAME + 1))
        with pytest.raises(worker.JobError): worker.receive(right)
    finally:
        left.close(); right.close()


@pytest.mark.parametrize("raw", [b"{}", b'{"a":1,"a":2}', b'{"a":NaN}', b"[]", b"\xff"])
def test_private_frame_strict_json(raw):
    left, right = socket.socketpair()
    try:
        left.sendall(struct.pack(">I", len(raw)) + raw)
        if raw == b"{}": assert worker.receive(right) == {}
        else:
            with pytest.raises(worker.fleet.RebuilderError): worker.receive(right)
    finally:
        left.close(); right.close()


@pytest.mark.parametrize("attack", ["sequence", "expired", "boolean", "nonfinite", "long", "field"])
def test_invalid_owner_reply_fail_stops_without_value_return(monkeypatch, attack):
    left, right = socket.socketpair()
    session = local_session(left)
    response = {"sequence": 0, "deadline": time.monotonic() + 10, "value": "PUBLIC-TEST-value"}
    if attack == "sequence": response["sequence"] = 1
    elif attack == "expired": response["deadline"] = time.monotonic() - 1
    elif attack == "boolean": response["deadline"] = True
    elif attack == "nonfinite": response["deadline"] = "NaN"
    elif attack == "long": response["deadline"] = time.monotonic() + 601
    else: response["extra"] = True
    worker.send(right, response)
    monkeypatch.setattr(worker.os, "_exit", lambda status: (_ for _ in ()).throw(SystemExit(status)))
    try:
        with pytest.raises(SystemExit) as result: session.exchange("secret", name=credentials.BUILDER_SECRET)
        assert result.value.code == 70
    finally:
        left.close(); right.close()


@pytest.mark.parametrize("condition", ["deadline", "lost-peer"])
def test_real_ordinary_subprocess_exits70_on_watchdog_or_session_loss(condition):
    root = str(Path(__file__).resolve().parents[1])
    source = """
import sys,threading,time,socket
sys.path.insert(0,sys.argv[1])
from scripts import android_protected_job_worker as w
s=w.Session.__new__(w.Session)
s._done=threading.Event();s._mutex=threading.RLock();s._sequence=0
s._deadline=time.monotonic()+(0.05 if sys.argv[2]=='deadline' else 1)
if sys.argv[2]=='deadline':s._watchdog()
else:
 s._socket,peer=socket.socketpair();peer.close();s.exchange('check')
print('MUST NOT RETURN')
"""
    result = subprocess.run([sys.executable, "-I", "-B", "-S", "-c", source, root, condition],
        capture_output=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C"})
    assert result.returncode == 70 and result.stdout == b"" and result.stderr == b""


def test_actual_runner_is_bracketed_and_expiry_blocks_subprocess(monkeypatch):
    session = local_session(None)
    events = []
    monkeypatch.setattr(session, "check", lambda: events.append("fresh"))
    monkeypatch.setattr(worker.subprocess, "run", lambda *args, **kwargs: events.append("actual-run") or 7)
    assert session.run(["fixed-command"]) == 7
    assert events == ["fresh", "actual-run", "fresh"]
    session._deadline = time.monotonic() - 1
    with pytest.raises(worker.JobError): session.run(["fixed-command"])
    assert events.count("actual-run") == 1


@pytest.mark.parametrize("mode", ["execute", "reconcile"])
def test_worker_calls_real_transaction_with_private_secret_exchange_only_after_reservation(tmp_path, monkeypatch, mode):
    fleet = worker.fleet
    events = []
    lock, lock_raw, lease = transaction.fixture(fleet, tmp_path, events)
    client = transaction.install_fakes(fleet, monkeypatch, events, lock, lock_raw)
    consumer = transaction.fake_consumer(fleet, lease, events)
    config = {"fleet_root": str(tmp_path), "lock": str(tmp_path / "lock"), "code_pins": {},
        "handoff": str(tmp_path), "validation": {}, "attempt": "d" * 64, "mode": mode,
        "artifact_id": 123, "artifact_sha256": "e" * 64, "recovery": str(lease.recovery_root),
        "output": str(tmp_path / "output"), "credentials": str(tmp_path)}
    builder = {key: value for key, value in lease.toolchain.items()
               if key not in {"builderClosureSha256", "closureSha256"}}
    builder.update(builderExecutionProvenanceAuthenticated=False, protectedSignerRuntimeVerified=False,
                   closureSha256=lease.toolchain["builderClosureSha256"])
    class Validation:
        tool_roots = {"java": lease.java_root}
        def __init__(self, *_args, **_kwargs): pass
        def _check_exact(self): return builder
        def bind_transaction(self, *_args): events.append("bind-validation")
        def load_consumer(self): return consumer
        def __call__(self, **_kwargs): return {"status": "pass"}
    monkeypatch.setattr(worker, "code_inputs", lambda *_: {})
    monkeypatch.setattr(fleet, "PreservedProtectedValidation", Validation)
    monkeypatch.setattr(fleet, "PreservedRebuildHandoff", lambda *_: SimpleNamespace(
        handoff=lease.handoff, paths=lease.paths, assert_exact=lease.assert_exact, artifact_closure_sha256="a" * 64))
    monkeypatch.setattr(client, "_reservation_binding", lambda *_: events.append("reservation-verified"), raising=False)
    monkeypatch.setattr(worker, "ledger_inputs", lambda *_: (None, client, {}, lambda *_: None))
    # The transaction's existing loader fake must also accept the real bridge kwarg.
    loader = fleet.load_reviewed_ledger
    monkeypatch.setattr(fleet, "load_reviewed_ledger", lambda *args, **_kwargs: loader(*args))
    left, right = socket.socketpair()
    session, observed, failures = local_session(left), [], []
    public_values = {
        credentials.BUILDER_SECRET: base64.b64encode(credentials._PKCS8 + b"p" * 32).decode(),
        credentials.KEYSTORE_SECRET: base64.b64encode(b"PUBLIC TEST NOT A KEYSTORE").decode(),
        credentials.STORE_PASSWORD_SECRET: "PUBLIC-test-password", credentials.KEY_PASSWORD_SECRET: "PUBLIC-test-password"}
    def serve():
        try:
            while True:
                request = worker.receive(right)
                observed.append(request["operation"])
                value = None
                if request["operation"] == "secret":
                    assert mode == "execute" and "reserve" in events and "reservation-verified" in events
                    assert (lease.recovery_root / ("d" * 64) / "RESERVATION.generated.json").exists()
                    value = public_values[request["name"]]
                worker.send(right, {"sequence": request["sequence"], "deadline": time.monotonic() + 20, "value": value})
                if request["operation"] == "done": break
        except BaseException as error: failures.append(error)
    thread = threading.Thread(target=serve)
    thread.start()
    try:
        if mode == "execute":
            assert worker.execute_owned(session, config)["status"] == "verified"
            assert observed.count("secret") == 4 and events.count("sign") == 1
            assert not (tmp_path / "admitted").exists()
        else:
            # The REAL reconcile entrypoint must fail on absent recovery; no
            # signing callback/reader is supplied even for this negative path.
            with pytest.raises((fleet.RebuilderError, FileNotFoundError)):
                worker.execute_owned(session, config)
            assert "secret" not in observed and "sign" not in events
        session.finish()
    finally:
        left.close(); right.close(); thread.join(timeout=2)
    assert not thread.is_alive() and not failures
