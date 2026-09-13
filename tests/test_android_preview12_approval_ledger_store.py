"""Real local SQLite persistence tests; no hosted/authenticated runtime claim."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import gc
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3

import pytest

from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_store as store


SERVICE = "chummer.preview12.approval-ledger"
DATABASE_ID = "9" * 64
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
APPROVAL = b' {"public":"exact bytes", "n":1}\r\n'


def subject(**changes):
    values = dict(approval_request_nonce="1" * 64, two_green_artifact_id=9989938590,
                  two_green_artifact_sha256="2" * 64, two_green_receipt_sha256="3" * 64,
                  main_tree="4" * 40, policy_sha256="5" * 64,
                  version_name=protocol.VERSION_NAME, version_code=protocol.VERSION_CODE)
    values.update(changes)
    return protocol.make_subject(**values)


def request(operation="reserve", *, value=None, prior=None, approval=APPROVAL, reason="operator_abort"):
    payload = None
    if operation == "commit":
        payload = {"sha256": hashlib.sha256(approval).hexdigest(), "sizeBytes": len(approval),
                   "publicJsonBase64": base64.b64encode(approval).decode("ascii")}
    return protocol.canonical_bytes(protocol._request(
        operation, value or subject(), approval=payload,
        abort_reason=reason if operation == "abort" else None, prior_reservation=prior,
    ))


def binding(receipt):
    value = json.loads(receipt)
    return {"reservationId": value["reservationId"], "priorRevision": value["revision"],
            "reservationReceiptSha256": hashlib.sha256(receipt).hexdigest()}


def open_store(path):
    return store.SQLiteApprovalLedgerStore(path, service_identity=SERVICE, database_id=DATABASE_ID)


@pytest.fixture
def database(tmp_path):
    root = tmp_path / "private-ledger"
    root.mkdir(mode=0o700)
    path = root / "approval.sqlite3"
    instance = store.SQLiteApprovalLedgerStore.create(path, service_identity=SERVICE, database_id=DATABASE_ID)
    return path, instance


def rows(path, table="reservations"):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT * FROM " + table).fetchall()
    finally:
        conn.close()


def _process_request(path, raw, gate, output):
    try:
        instance = open_store(Path(path))
        if not gate.wait(5):
            raise RuntimeError("test start barrier timed out")
        output.put(("ok", instance.process(raw, now=NOW + timedelta(seconds=2))))
    except BaseException as error:
        output.put((type(error).__name__, str(error)))


def concurrent(path, requests):
    context = multiprocessing.get_context("fork")
    gate = context.Event()
    output = context.Queue()
    processes = [context.Process(target=_process_request, args=(str(path), raw, gate, output)) for raw in requests]
    for process in processes:
        process.start()
    gate.set()
    try:
        results = [output.get(timeout=10) for _ in requests]
    finally:
        for process in processes:
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(5)
        output.close()
        output.join_thread()
    assert all(process.exitcode == 0 for process in processes)
    return results


def test_explicit_creation_is_durable_private_and_identity_pinned(database):
    path, instance = database
    assert path.stat().st_mode & 0o777 == 0o600
    assert instance.service_identity == SERVICE and instance.database_id == DATABASE_ID
    with pytest.raises(AttributeError):
        instance.service_identity = "replacement"
    with pytest.raises(AttributeError):
        instance.database_id = "8" * 64
    with pytest.raises(store.StoreUnavailable):
        store.SQLiteApprovalLedgerStore.create(path, service_identity=SERVICE, database_id=DATABASE_ID)
    for identity, database_id in (("different.service", DATABASE_ID), (SERVICE, "8" * 64)):
        before = path.read_bytes()
        with pytest.raises(store.StoreUnavailable):
            store.SQLiteApprovalLedgerStore(path, service_identity=identity, database_id=database_id)
        assert path.read_bytes() == before
    conn = instance._connection()
    try:
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_missing_database_never_creates_empty_history(tmp_path):
    tmp_path.chmod(0o700)
    missing = tmp_path / "absent.sqlite3"
    with pytest.raises(store.StoreUnavailable):
        open_store(missing)
    assert not missing.exists()
    for path in (Path(":memory:"), Path("file:ledger?mode=memory&cache=shared"), Path("relative.sqlite3")):
        with pytest.raises(store.StoreUnavailable):
            open_store(path)


def test_repeated_reopen_and_request_close_actual_database_descriptors_without_gc(database):
    path, instance = database
    instance.process(request(), now=NOW)

    def ledger_descriptors():
        descriptors = []
        for entry in Path("/proc/self/fd").iterdir():
            try:
                target = os.readlink(entry)
            except FileNotFoundError:  # The directory iterator itself can close.
                continue
            if target == str(path) or target.startswith(str(path) + "-"):
                descriptors.append(target)
        return descriptors

    enabled = gc.isenabled()
    gc.disable()
    try:
        assert ledger_descriptors() == []
        for _ in range(32):
            open_store(path).process(request("status"), now=NOW)
            assert ledger_descriptors() == []
    finally:
        if enabled:
            gc.enable()


def test_database_and_sidecar_symlinks_and_nonprivate_directory_are_rejected(database, tmp_path):
    path, instance = database
    alias = path.parent / "alias.sqlite3"
    alias.symlink_to(path)
    with pytest.raises(store.StoreUnavailable):
        open_store(alias)
    sidecar = Path(str(path) + "-journal")
    sidecar.symlink_to(path)
    with pytest.raises(store.StoreUnavailable):
        instance.process(request(), now=NOW)
    sidecar.unlink()
    path.parent.chmod(0o755)
    with pytest.raises(store.StoreUnavailable):
        open_store(path)


def test_live_file_swap_and_delete_do_not_repoint_existing_store(database):
    path, instance = database
    original = instance.process(request(), now=NOW)
    backup = path.with_name("original.sqlite3")
    path.rename(backup)
    with pytest.raises(store.StoreUnavailable):
        instance.process(request(), now=NOW)
    store.SQLiteApprovalLedgerStore.create(path, service_identity=SERVICE, database_id="8" * 64)
    with pytest.raises(store.StoreUnavailable):
        instance.process(request(), now=NOW)
    with pytest.raises(store.StoreUnavailable):
        open_store(path)
    assert open_store(backup).process(request(), now=NOW) == original


def test_restart_and_lost_reserve_reply_preserve_exact_issued_receipt(database):
    path, instance = database
    receipt = instance.process(request(), now=NOW)
    assert receipt == protocol.canonical_bytes(json.loads(receipt))
    assert open_store(path).process(request(), now=NOW + timedelta(seconds=30)) == receipt
    assert len(rows(path)) == len(rows(path, "reserve_receipts")) == 1
    value = json.loads(receipt)
    assert value["revision"] == 1
    assert value["reservedAtUtc"] == "2026-09-10T12:00:00Z"
    assert value["leaseExpiresAtUtc"] == "2026-09-10T12:15:00Z"


def test_commit_lost_reply_recovers_exact_bytes_and_original_time_window(database):
    path, instance = database
    reserved = instance.process(request(), now=NOW)
    prior = binding(reserved)
    commit_request = request("commit", prior=prior)
    committed = instance.process(commit_request, now=NOW + timedelta(seconds=2))
    # Discarded HTTP outcome is recovered against a new store connection.
    assert open_store(path).process(commit_request, now=NOW + timedelta(days=7)) == committed
    recovered = json.loads(open_store(path).process(request("status", prior=prior), now=NOW + timedelta(days=7)))
    assert recovered["state"] == "committed" and recovered["revision"] == 2
    assert base64.b64decode(recovered["approval"]["publicJsonBase64"]) == APPROVAL
    assert recovered["reservedAtUtc"] == json.loads(reserved)["reservedAtUtc"]
    assert recovered["leaseExpiresAtUtc"] == json.loads(reserved)["leaseExpiresAtUtc"]
    fresh_reserve = open_store(path).process(request(), now=NOW + timedelta(days=7))
    assert json.loads(fresh_reserve)["state"] == "committed"
    assert open_store(path).process(request("commit", prior=binding(fresh_reserve)), now=NOW + timedelta(days=7))
    assert len(rows(path)) == 1 and len(rows(path, "reserve_receipts")) == 2


@pytest.mark.parametrize("terminal", ["commit", "abort"])
def test_conflicting_terminal_operations_never_replace_history(database, terminal):
    path, instance = database
    prior = binding(instance.process(request(), now=NOW))
    accepted = request(terminal, prior=prior)
    first = instance.process(accepted, now=NOW + timedelta(seconds=1))
    before = rows(path)
    assert open_store(path).process(accepted, now=NOW + timedelta(seconds=2)) == first
    conflicting = [request("abort" if terminal == "commit" else "commit", prior=prior)]
    conflicting.append(request(terminal, prior=prior, approval=b"different", reason="different_abort"))
    for raw in conflicting:
        with pytest.raises(store.Conflict):
            open_store(path).process(raw, now=NOW + timedelta(seconds=3))
        assert rows(path) == before


@pytest.mark.parametrize("terminal", ["reserved", "committed", "aborted", "expired"])
@pytest.mark.parametrize("collision", ["artifact", "nonce"])
def test_each_uniqueness_subject_remains_reserved_forever(database, terminal, collision):
    path, instance = database
    prior = binding(instance.process(request(), now=NOW))
    if terminal in {"committed", "aborted"}:
        instance.process(request("commit" if terminal == "committed" else "abort", prior=prior), now=NOW)
    elif terminal == "expired":
        instance.process(request("status"), now=NOW + timedelta(days=7))
    value = subject(approval_request_nonce="6" * 64) if collision == "artifact" else subject(two_green_artifact_id=9989938591)
    before = rows(path)
    with pytest.raises(store.Conflict):
        open_store(path).process(request(value=value), now=NOW + timedelta(days=7))
    assert rows(path) == before and len(before) == 1


def test_expiry_is_terminal_at_original_deadline_even_when_first_observed_later(database):
    path, instance = database
    reserved = instance.process(request(), now=NOW)
    prior = binding(reserved)
    with pytest.raises(store.Conflict):
        instance.process(request("commit", prior=prior), now=NOW + timedelta(days=7))
    expired = json.loads(open_store(path).process(request("status"), now=NOW + timedelta(days=7)))
    assert expired["state"] == "aborted" and expired["revision"] == 2
    assert expired["updatedAtUtc"] == expired["leaseExpiresAtUtc"] == "2026-09-10T12:15:00Z"
    assert expired["abort"] == {"reasonCode": "lease_expired"}
    again = json.loads(open_store(path).process(request(), now=NOW + timedelta(days=8)))
    assert again["state"] == "aborted" and again["reservationId"] == expired["reservationId"]
    assert again["revision"] == 2
    with pytest.raises(store.Conflict):
        open_store(path).process(request("abort", prior=prior), now=NOW + timedelta(days=8))


@pytest.mark.parametrize("change", [
    {"reservationId": "rsv_" + "f" * 32}, {"priorRevision": 2},
    {"reservationReceiptSha256": "f" * 64},
])
def test_forged_or_unissued_prior_binding_fails_without_mutation(database, change):
    path, instance = database
    prior = binding(instance.process(request(), now=NOW))
    before = rows(path)
    for operation in ("commit", "abort", "status"):
        with pytest.raises(store.Conflict):
            instance.process(request(operation, prior={**prior, **change}), now=NOW + timedelta(seconds=1))
        assert rows(path) == before


def test_status_receipt_digest_cannot_substitute_for_an_issued_reserve_binding(database):
    path, instance = database
    instance.process(request(), now=NOW)
    status = instance.process(request("status"), now=NOW)
    with pytest.raises(store.Conflict):
        instance.process(request("commit", prior=binding(status)), now=NOW)
    assert rows(path)[0][5] == "reserved"


def test_three_independent_processes_reserve_one_subject_once(database):
    path, _ = database
    results = concurrent(path, [request()] * 3)
    assert [status for status, _ in results] == ["ok"] * 3
    assert len({value for _, value in results}) == 1
    assert len(rows(path)) == len(rows(path, "reserve_receipts")) == 1


@pytest.mark.parametrize("collision", ["artifact", "nonce"])
def test_concurrent_conflicting_subjects_have_one_winner(database, collision):
    path, _ = database
    changed = subject(approval_request_nonce="6" * 64) if collision == "artifact" else subject(two_green_artifact_id=9989938591)
    results = concurrent(path, [request(), request(value=changed)])
    assert sorted(status for status, _ in results) == ["Conflict", "ok"]
    assert len(rows(path)) == len(rows(path, "reserve_receipts")) == 1


def test_concurrent_conflicting_terminal_commits_have_one_winner(database):
    path, instance = database
    prior = binding(instance.process(request(), now=NOW))
    results = concurrent(path, [request("commit", prior=prior), request("commit", prior=prior, approval=b"other")])
    assert sorted(status for status, _ in results) == ["Conflict", "ok"]
    terminal = json.loads(open_store(path).process(request("status"), now=NOW + timedelta(seconds=3)))
    winner = json.loads(next(value for status, value in results if status == "ok"))
    assert terminal["approval"] == winner["approval"] and terminal["revision"] == 2


def _crash_before_commit(path):
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("UPDATE reservations SET state='committed',revision=2,approval_bytes=?", (b"uncommitted",))
    os._exit(37)


def test_process_crash_before_commit_rolls_back_without_losing_reservation(database):
    path, instance = database
    reserved = instance.process(request(), now=NOW)
    context = multiprocessing.get_context("fork")
    process = context.Process(target=_crash_before_commit, args=(str(path),))
    process.start()
    process.join(10)
    assert not process.is_alive() and process.exitcode == 37
    assert open_store(path).process(request(), now=NOW + timedelta(seconds=2)) == reserved
    result = open_store(path).process(request("commit", prior=binding(reserved)), now=NOW + timedelta(seconds=3))
    assert base64.b64decode(json.loads(result)["approval"]["publicJsonBase64"]) == APPROVAL


@pytest.mark.parametrize("maximum", [True, False])
def test_exact_approval_limit_and_one_byte_over(database, maximum):
    path, instance = database
    prior = binding(instance.process(request(), now=NOW))
    raw = request("commit", prior=prior, approval=b"x" * (protocol.MAX_APPROVAL_BYTES + (not maximum)))
    if maximum:
        result = json.loads(instance.process(raw, now=NOW))
        assert result["approval"]["sizeBytes"] == protocol.MAX_APPROVAL_BYTES
    else:
        before = path.read_bytes()
        with pytest.raises(store.InvalidRequest):
            instance.process(raw, now=NOW)
        assert path.read_bytes() == before


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(extra=True), lambda r: r.update(contractVersion=True),
    lambda r: r.update(contractVersion=1.0), lambda r: r.update(operation="replace"),
    lambda r: r.update(requestId="0" * 64), lambda r: r.update(subjectSha256="0" * 64),
    lambda r: r["subject"].update(contractVersion=True),
    lambda r: r["subject"].update(twoGreenArtifactId=True),
    lambda r: r["subject"].update(twoGreenArtifactId=0),
    lambda r: r["subject"].update(approvalRequestNonce="1" * 64 + "\n"),
    lambda r: r["subject"].update(extra="x"),
    lambda r: r["subject"]["release"].update(versionCode=12.0),
    lambda r: r["subject"]["release"].update(packageId="other"),
    lambda r: r.update(approval={}), lambda r: r.update(abortReason="x"),
])
def test_malformed_reserve_cannot_write_database(database, mutate):
    path, instance = database
    value = json.loads(request())
    mutate(value)
    before = path.read_bytes()
    with pytest.raises(store.InvalidRequest):
        instance.process(protocol.canonical_bytes(value), now=NOW)
    assert path.read_bytes() == before and rows(path) == []


@pytest.mark.parametrize("raw", [
    b"", b"[]", b"null", b"x" * 65537, b"\xff", b'{"x":NaN}',
    b'{"contractName":1,"contractName":2}', b"[" * 2000 + b"0" + b"]" * 2000,
])
def test_non_strict_or_oversized_json_cannot_write(database, raw):
    path, instance = database
    before = path.read_bytes()
    with pytest.raises(store.InvalidRequest):
        instance.process(raw, now=NOW)
    assert path.read_bytes() == before


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(priorReservation=None),
    lambda r: r["priorReservation"].update(priorRevision=True),
    lambda r: r["priorReservation"].update(extra=True),
    lambda r: r["approval"].update(sizeBytes=True),
    lambda r: r["approval"].update(sha256="f" * 64),
    lambda r: r["approval"].update(publicJsonBase64="not base64"),
    lambda r: r["approval"].update(extra=True),
])
def test_malformed_commit_cannot_mutate_existing_reservation(database, mutate):
    path, instance = database
    prior = binding(instance.process(request(), now=NOW))
    value = json.loads(request("commit", prior=prior))
    mutate(value)
    before = path.read_bytes()
    with pytest.raises(store.InvalidRequest):
        instance.process(protocol.canonical_bytes(value), now=NOW)
    assert path.read_bytes() == before


def test_state_and_identity_cannot_be_deleted_or_terminally_rewritten_through_store_schema(database):
    path, instance = database
    prior = binding(instance.process(request(), now=NOW))
    instance.process(request("commit", prior=prior), now=NOW)
    conn = sqlite3.connect(path, isolation_level=None)
    try:
        for sql in ("DELETE FROM reservations", "DELETE FROM reserve_receipts", "DELETE FROM ledger_identity",
                    "UPDATE ledger_identity SET service_identity='other'", "UPDATE reservations SET state='reserved',revision=1,approval_bytes=NULL"):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)
    finally:
        conn.close()
    assert len(rows(path)) == 1


def test_unknown_subject_and_clock_rollback_do_not_mutate(database):
    path, instance = database
    with pytest.raises(store.NotFound):
        instance.process(request("status"), now=NOW)
    instance.process(request(), now=NOW)
    before = rows(path)
    with pytest.raises(store.Conflict):
        instance.process(request(), now=NOW - timedelta(seconds=1))
    assert rows(path) == before
