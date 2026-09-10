"""Persistent, single-host store behind the UNCHANGED PR11 ledger protocol.

This is not an HTTP/authentication/signing service and has no CLI or deployment
default. Returned bytes are an UNSIGNED receipt, not external authority. The
separate protected service must authenticate/authorize requests, own its clock,
sign the exact receipt, and qualify its persistent local filesystem. Never put
this database on an ephemeral workflow runner, NFS or a multi-host shared file.
No approval key, ledger signing key, bearer or private credential belongs here.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any
from urllib.parse import quote
import uuid

from scripts import android_preview12_approval_ledger as protocol


_APPLICATION_ID = 0x4350464C
_SCHEMA_VERSION = 1
_LEASE_SECONDS = 900
_MAX_REQUEST_BYTES = 65536
_ABORT_REASON = re.compile(r"[a-z][a-z0-9_]{2,63}\Z")
_REQUEST_FIELDS = {
    "contractName", "contractVersion", "operation", "requestId", "subject",
    "subjectSha256", "approval", "abortReason", "priorReservation",
}
_SUBJECT_FIELDS = {
    "contractName", "contractVersion", "approvalRequestNonce", "twoGreenArtifactId",
    "twoGreenArtifactSha256", "twoGreenReceiptSha256", "mainTree", "policySha256", "release",
}
_SCHEMA = (
    """CREATE TABLE ledger_identity (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        schema_version INTEGER NOT NULL CHECK(schema_version=1),
        service_identity TEXT NOT NULL, database_id TEXT NOT NULL,
        lease_seconds INTEGER NOT NULL CHECK(lease_seconds=900))""",
    """CREATE TRIGGER identity_no_update BEFORE UPDATE ON ledger_identity
        BEGIN SELECT RAISE(ABORT, 'immutable ledger identity'); END""",
    """CREATE TRIGGER identity_no_delete BEFORE DELETE ON ledger_identity
        BEGIN SELECT RAISE(ABORT, 'immutable ledger identity'); END""",
    """CREATE TABLE reservations (
        subject_sha TEXT PRIMARY KEY NOT NULL, subject_bytes BLOB NOT NULL,
        artifact_id TEXT NOT NULL UNIQUE, nonce TEXT NOT NULL UNIQUE,
        reservation_id TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
        revision INTEGER NOT NULL, reserved_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        lease_expires TEXT NOT NULL, approval_bytes BLOB, abort_reason TEXT,
        CHECK((state='reserved' AND revision=1 AND approval_bytes IS NULL AND abort_reason IS NULL)
           OR (state='committed' AND revision=2 AND approval_bytes IS NOT NULL
               AND length(approval_bytes) BETWEEN 1 AND 32768 AND abort_reason IS NULL)
           OR (state='aborted' AND revision=2 AND approval_bytes IS NULL AND abort_reason IS NOT NULL)))""",
    """CREATE TRIGGER reservation_no_delete BEFORE DELETE ON reservations
        BEGIN SELECT RAISE(ABORT, 'permanent uniqueness record'); END""",
    """CREATE TRIGGER reservation_identity_immutable BEFORE UPDATE ON reservations
        WHEN NEW.subject_sha IS NOT OLD.subject_sha OR NEW.subject_bytes IS NOT OLD.subject_bytes
          OR NEW.artifact_id IS NOT OLD.artifact_id OR NEW.nonce IS NOT OLD.nonce
          OR NEW.reservation_id IS NOT OLD.reservation_id OR NEW.reserved_at IS NOT OLD.reserved_at
          OR NEW.lease_expires IS NOT OLD.lease_expires
        BEGIN SELECT RAISE(ABORT, 'immutable reservation identity'); END""",
    """CREATE TRIGGER reservation_terminal_immutable BEFORE UPDATE ON reservations
        WHEN OLD.state != 'reserved' OR NEW.state = 'reserved' OR NEW.revision != OLD.revision+1
        BEGIN SELECT RAISE(ABORT, 'immutable terminal state'); END""",
    """CREATE TABLE reserve_receipts (
        subject_sha TEXT NOT NULL REFERENCES reservations(subject_sha),
        receipt_sha TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision IN (1,2)),
        receipt_bytes BLOB NOT NULL, PRIMARY KEY(subject_sha, receipt_sha))""",
    """CREATE TRIGGER receipt_no_delete BEFORE DELETE ON reserve_receipts
        BEGIN SELECT RAISE(ABORT, 'immutable issued reserve receipt'); END""",
    """CREATE TRIGGER receipt_no_update BEFORE UPDATE ON reserve_receipts
        BEGIN SELECT RAISE(ABORT, 'immutable issued reserve receipt'); END""",
)


class LedgerStoreError(RuntimeError):
    """Fixed public diagnostics, no database paths or untrusted input echo."""


class InvalidRequest(LedgerStoreError):
    pass


class Conflict(LedgerStoreError):
    pass


class NotFound(LedgerStoreError):
    pass


class StoreUnavailable(LedgerStoreError):
    pass


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def _digest(value: object) -> bool:
    return type(value) is str and protocol.SHA256.fullmatch(value) is not None


def _subject(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _SUBJECT_FIELDS \
            or value["contractName"] != protocol.SUBJECT_CONTRACT \
            or type(value["contractVersion"]) is not int or value["contractVersion"] != 1:
        raise InvalidRequest("subject fields or contract are invalid")
    release = value["release"]
    if type(release) is not dict or set(release) != {"packageId", "versionName", "versionCode"} \
            or release["packageId"] != protocol.PACKAGE_ID \
            or type(release["versionCode"]) is not int or release["versionCode"] != protocol.VERSION_CODE \
            or type(release["versionName"]) is not str or release["versionName"] != protocol.VERSION_NAME:
        raise InvalidRequest("subject release is invalid")
    expected = protocol.make_subject(
        approval_request_nonce=value["approvalRequestNonce"], two_green_artifact_id=value["twoGreenArtifactId"],
        two_green_artifact_sha256=value["twoGreenArtifactSha256"],
        two_green_receipt_sha256=value["twoGreenReceiptSha256"], main_tree=value["mainTree"],
        policy_sha256=value["policySha256"], version_name=release["versionName"], version_code=release["versionCode"],
    )
    if value != expected:
        raise InvalidRequest("subject is not exact")
    return expected


def _parse_request(raw: bytes) -> tuple[dict[str, Any], bytes | None]:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_REQUEST_BYTES:
        raise InvalidRequest("request is not bounded bytes")
    failed = False
    request = None
    approval_bytes = None
    try:
        request = protocol.strict_json_bytes(raw, "request", _MAX_REQUEST_BYTES)
        if set(request) != _REQUEST_FIELDS or request["contractName"] != protocol.REQUEST_CONTRACT \
                or type(request["contractVersion"]) is not int or request["contractVersion"] != 1:
            raise ValueError()
        operation = request["operation"]
        if type(operation) is not str or operation not in {"reserve", "status", "commit", "abort"}:
            raise ValueError()
        subject = _subject(request["subject"])
        incoming = request["approval"]
        reason = request["abortReason"]
        prior = request["priorReservation"]
        if operation == "commit":
            if type(incoming) is not dict or set(incoming) != {"sha256", "sizeBytes", "publicJsonBase64"} \
                    or not _digest(incoming["sha256"]) or not _positive(incoming["sizeBytes"]) \
                    or type(incoming["publicJsonBase64"]) is not str:
                raise ValueError()
            approval_bytes = base64.b64decode(incoming["publicJsonBase64"], validate=True)
            if not approval_bytes or len(approval_bytes) > protocol.MAX_APPROVAL_BYTES \
                    or incoming["sizeBytes"] != len(approval_bytes) \
                    or incoming["sha256"] != hashlib.sha256(approval_bytes).hexdigest() \
                    or incoming["publicJsonBase64"] != base64.b64encode(approval_bytes).decode("ascii"):
                raise ValueError()
        elif incoming is not None:
            raise ValueError()
        if operation == "abort":
            if type(reason) is not str or not _ABORT_REASON.fullmatch(reason):
                raise ValueError()
        elif reason is not None:
            raise ValueError()
        if prior is not None:
            if operation == "reserve" or type(prior) is not dict \
                    or set(prior) != {"reservationId", "priorRevision", "reservationReceiptSha256"} \
                    or type(prior["reservationId"]) is not str \
                    or not protocol.RESERVATION_ID.fullmatch(prior["reservationId"]) \
                    or not _positive(prior["priorRevision"]) or not _digest(prior["reservationReceiptSha256"]):
                raise ValueError()
        elif operation in {"commit", "abort"}:
            raise ValueError()
        expected = protocol._request(operation, subject, approval=incoming, abort_reason=reason, prior_reservation=prior)
        if request != expected or not _digest(request["requestId"]) or not _digest(request["subjectSha256"]):
            raise ValueError()
    except (ValueError, TypeError, KeyError, RecursionError, protocol.LedgerError):
        failed = True
    if failed:
        raise InvalidRequest("request failed the exact PR11 contract")
    assert request is not None
    return request, approval_bytes


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _regular(path: Path) -> tuple[int, int]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 \
            or stat.S_IMODE(info.st_mode) & 0o077:
        raise StoreUnavailable("database files must be private regular single-link files")
    return info.st_dev, info.st_ino


def _parent(path: Path) -> tuple[int, int]:
    if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
        raise StoreUnavailable("database path must have a canonical absolute parent")
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise StoreUnavailable("database directory must be private and owner-controlled")
    return info.st_dev, info.st_ino


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class SQLiteApprovalLedgerStore:
    """One persistent local database, multiple processes on the SAME host.

    Open never creates/replaces history. Expected database_id is a public,
    externally retained pin, separate from the service name. The host must
    protect the DB, parent, backups and clock from replacement/rollback. A file
    identity check catches ordinary live swaps; it is not protection against a
    privileged actor replacing both data and deployment pins.
    """

    def __init__(self, path: Path, *, service_identity: str, database_id: str):
        if type(service_identity) is not str or not protocol.SERVICE_ID.fullmatch(service_identity) \
                or not _digest(database_id):
            raise StoreUnavailable("expected ledger identity is invalid")
        self._path = Path(path)
        self._service_identity = service_identity
        self._database_id = database_id
        try:
            self._parent_identity = _parent(self._path)
            self._file_identity = _regular(self._path)
            conn = self._connection()
            try:
                self._verify_identity(conn)
            finally:
                conn.close()
        except (OSError, sqlite3.Error, ValueError):
            raise StoreUnavailable("existing ledger database is unavailable") from None

    @property
    def service_identity(self) -> str:
        return self._service_identity

    @property
    def database_id(self) -> str:
        return self._database_id

    @classmethod
    def create(cls, path: Path, *, service_identity: str, database_id: str) -> "SQLiteApprovalLedgerStore":
        """Explicit service provisioning ONLY; never use as request fallback.

        A failed creation leaves the exclusive file quarantined for inspection.
        No deletion, reset, replacement, or automatic recovery is performed.
        """
        if type(service_identity) is not str or not protocol.SERVICE_ID.fullmatch(service_identity) \
                or not _digest(database_id):
            raise StoreUnavailable("expected ledger identity is invalid")
        path = Path(path)
        try:
            _parent(path)
            for suffix in ("-journal", "-wal", "-shm"):
                if os.path.lexists(str(path) + suffix):
                    raise StoreUnavailable("new database has preexisting sidecar files")
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            _sync_directory(path.parent)
            conn = cls._open(path)
            try:
                conn.execute("BEGIN EXCLUSIVE")
                for statement in _SCHEMA:
                    conn.execute(statement)
                conn.execute("INSERT INTO ledger_identity VALUES (1,1,?,?,900)", (service_identity, database_id))
                conn.execute(f"PRAGMA application_id={_APPLICATION_ID}")
                conn.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
            _sync_directory(path.parent)
        except (OSError, sqlite3.Error, ValueError):
            raise StoreUnavailable("exclusive ledger creation failed; no reset was performed") from None
        return cls(path, service_identity=service_identity, database_id=database_id)

    @staticmethod
    def _open(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=rw", uri=True,
                               timeout=5, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA trusted_schema=OFF")
            if conn.execute("PRAGMA synchronous").fetchone()[0] != 2 \
                    or conn.execute("PRAGMA journal_mode").fetchone()[0] != "delete" \
                    or conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise StoreUnavailable("required SQLite durability mode is unavailable")
        except BaseException:
            conn.close()
            raise
        return conn

    def _assert_files(self) -> None:
        if _parent(self._path) != self._parent_identity or _regular(self._path) != self._file_identity:
            raise StoreUnavailable("ledger path identity changed")
        for suffix in ("-wal", "-shm"):
            if os.path.lexists(str(self._path) + suffix):
                raise StoreUnavailable("unexpected WAL sidecar for DELETE-mode ledger")
        try:
            _regular(Path(str(self._path) + "-journal"))
        except FileNotFoundError:
            # Another legitimate local connection may just have removed
            # its DELETE-mode journal. The owner-only directory is required.
            pass

    def _connection(self) -> sqlite3.Connection:
        self._assert_files()
        conn = self._open(self._path)
        try:
            self._assert_files()
        except BaseException:
            conn.close()
            raise
        return conn

    def _verify_identity(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT * FROM ledger_identity").fetchall()
        if len(row) != 1 or tuple(row[0]) != (1, _SCHEMA_VERSION, self.service_identity, self.database_id, _LEASE_SECONDS) \
                or conn.execute("PRAGMA application_id").fetchone()[0] != _APPLICATION_ID \
                or conn.execute("PRAGMA user_version").fetchone()[0] != _SCHEMA_VERSION:
            raise StoreUnavailable("database does not match its pinned service identity")

    @staticmethod
    def _check_row(row: sqlite3.Row, request: dict[str, Any]) -> None:
        if bytes(row["subject_bytes"]) != protocol.canonical_bytes(request["subject"]) \
                or row["subject_sha"] != request["subjectSha256"] \
                or row["artifact_id"] != str(request["subject"]["twoGreenArtifactId"]) \
                or row["nonce"] != request["subject"]["approvalRequestNonce"] \
                or not protocol.RESERVATION_ID.fullmatch(row["reservation_id"]):
            raise StoreUnavailable("stored reservation identity is inconsistent")
        reserved = protocol._timestamp(row["reserved_at"], "reserved")
        expires = protocol._timestamp(row["lease_expires"], "expiry")
        updated = protocol._timestamp(row["updated_at"], "updated")
        if expires != reserved + timedelta(seconds=_LEASE_SECONDS) or not reserved <= updated <= expires:
            raise StoreUnavailable("stored reservation lease is inconsistent")
        if row["state"] == "reserved":
            valid = row["revision"] == 1 and row["approval_bytes"] is None and row["abort_reason"] is None
        elif row["state"] == "committed":
            valid = row["revision"] == 2 and row["abort_reason"] is None \
                and type(row["approval_bytes"]) is bytes and 0 < len(row["approval_bytes"]) <= protocol.MAX_APPROVAL_BYTES
        elif row["state"] == "aborted":
            valid = row["revision"] == 2 and row["approval_bytes"] is None \
                and type(row["abort_reason"]) is str and _ABORT_REASON.fullmatch(row["abort_reason"])
        else:
            valid = False
        if not valid:
            raise StoreUnavailable("stored reservation state is inconsistent")

    @staticmethod
    def _check_prior(conn: sqlite3.Connection, row: sqlite3.Row, request: dict[str, Any]) -> None:
        prior = request["priorReservation"]
        if prior is None:
            return
        issued = conn.execute(
            "SELECT revision,receipt_bytes FROM reserve_receipts WHERE subject_sha=? AND receipt_sha=?",
            (row["subject_sha"], prior["reservationReceiptSha256"]),
        ).fetchone()
        if prior["reservationId"] != row["reservation_id"] or issued is None \
                or issued["revision"] != prior["priorRevision"] \
                or hashlib.sha256(issued["receipt_bytes"]).hexdigest() != prior["reservationReceiptSha256"] \
                or (row["state"] == "reserved" and prior["priorRevision"] != row["revision"]):
            raise Conflict("prior binding is not an issued reserve receipt for this reservation")

    def _receipt(self, row: sqlite3.Row, request: dict[str, Any]) -> bytes:
        raw_approval = row["approval_bytes"]
        approval = None if raw_approval is None else {
            "sha256": hashlib.sha256(raw_approval).hexdigest(), "sizeBytes": len(raw_approval),
            "publicJsonBase64": base64.b64encode(raw_approval).decode("ascii"),
        }
        return protocol.canonical_bytes({
            "contractName": protocol.RECEIPT_CONTRACT, "contractVersion": 1,
            "serviceIdentity": self.service_identity, "requestId": request["requestId"],
            "operation": request["operation"], "subject": request["subject"],
            "subjectSha256": request["subjectSha256"], "reservationId": row["reservation_id"],
            "state": row["state"], "revision": row["revision"],
            "reservedAtUtc": row["reserved_at"], "updatedAtUtc": row["updated_at"],
            "leaseExpiresAtUtc": row["lease_expires"], "priorReservation": request["priorReservation"],
            "uniquenessSubjects": protocol.UNIQUENESS_SUBJECTS,
            "durabilityClass": "external_durable", "exactlyOnce": True,
            "approval": approval, "abort": None if row["abort_reason"] is None else {"reasonCode": row["abort_reason"]},
        })

    def process(self, request_bytes: bytes, *, now: datetime | None = None) -> bytes:
        """Return canonical UNSIGNED PR11 receipt bytes after durable commit.

        now is a trusted service-clock injection for deterministic tests, never
        a client field. Approval payload is opaque exact bytes as in PR11; its
        Android semantics/signature belong to the existing approval boundary.
        """
        request, approval_bytes = _parse_request(request_bytes)
        if now is not None and (type(now) is not datetime or now.tzinfo != timezone.utc):
            raise InvalidRequest("service clock must be UTC")
        failure = None
        receipt = None
        conn = None
        try:
            conn = self._connection()
            conn.execute("BEGIN IMMEDIATE")
            # Sample the real service clock after writer-lock acquisition;
            # waiting for another process must not manufacture clock rollback.
            now = (datetime.now(timezone.utc) if now is None else now).replace(microsecond=0)
            self._verify_identity(conn)
            row = conn.execute("SELECT * FROM reservations WHERE subject_sha=?", (request["subjectSha256"],)).fetchone()
            if row is None:
                if request["operation"] != "reserve":
                    raise NotFound("reservation does not exist")
                conflict = conn.execute("SELECT 1 FROM reservations WHERE artifact_id=? OR nonce=?",
                                        (str(request["subject"]["twoGreenArtifactId"]), request["subject"]["approvalRequestNonce"])).fetchone()
                if conflict is not None:
                    raise Conflict("artifact or nonce already belongs to another permanent subject")
                conn.execute("""INSERT INTO reservations VALUES (?,?,?,?,?,'reserved',1,?,?,?,NULL,NULL)""",
                             (request["subjectSha256"], protocol.canonical_bytes(request["subject"]),
                              str(request["subject"]["twoGreenArtifactId"]), request["subject"]["approvalRequestNonce"],
                              "rsv_" + uuid.uuid4().hex, _iso(now), _iso(now), _iso(now + timedelta(seconds=_LEASE_SECONDS))))
                row = conn.execute("SELECT * FROM reservations WHERE subject_sha=?", (request["subjectSha256"],)).fetchone()
            self._check_row(row, request)
            self._check_prior(conn, row, request)
            if now < protocol._timestamp(row["updated_at"], "updated"):
                raise Conflict("service clock precedes stored history")
            if row["state"] == "reserved" and now >= protocol._timestamp(row["lease_expires"], "expiry"):
                # Semantic transition occurred at the original deadline, even
                # when first observed much later. Never extend/reacquire lease.
                conn.execute("""UPDATE reservations SET state='aborted',revision=2,
                             updated_at=lease_expires,abort_reason='lease_expired'
                             WHERE subject_sha=? AND state='reserved' AND revision=1""", (row["subject_sha"],))
                row = conn.execute("SELECT * FROM reservations WHERE subject_sha=?", (row["subject_sha"],)).fetchone()
            operation = request["operation"]
            if operation == "commit":
                if row["state"] == "aborted" or (row["state"] == "committed" and row["approval_bytes"] != approval_bytes):
                    failure = Conflict("terminal reservation cannot accept different committed bytes")
                elif row["state"] == "reserved":
                    conn.execute("""UPDATE reservations SET state='committed',revision=2,updated_at=?,approval_bytes=?
                                 WHERE subject_sha=? AND state='reserved' AND revision=?""",
                                 (_iso(now), approval_bytes, row["subject_sha"], request["priorReservation"]["priorRevision"]))
            elif operation == "abort":
                if row["state"] == "committed" or (row["state"] == "aborted" and row["abort_reason"] != request["abortReason"]):
                    failure = Conflict("terminal reservation cannot accept a different abort")
                elif row["state"] == "reserved":
                    conn.execute("""UPDATE reservations SET state='aborted',revision=2,updated_at=?,abort_reason=?
                                 WHERE subject_sha=? AND state='reserved' AND revision=?""",
                                 (_iso(now), request["abortReason"], row["subject_sha"], request["priorReservation"]["priorRevision"]))
            if failure is None:
                row = conn.execute("SELECT * FROM reservations WHERE subject_sha=?", (row["subject_sha"],)).fetchone()
                self._check_row(row, request)
                receipt = self._receipt(row, request)
                if operation == "reserve":
                    digest = hashlib.sha256(receipt).hexdigest()
                    conn.execute("INSERT OR IGNORE INTO reserve_receipts VALUES (?,?,?,?)",
                                 (row["subject_sha"], digest, row["revision"], receipt))
                    issued = conn.execute("SELECT receipt_bytes FROM reserve_receipts WHERE subject_sha=? AND receipt_sha=?",
                                          (row["subject_sha"], digest)).fetchone()
                    if issued["receipt_bytes"] != receipt:
                        raise StoreUnavailable("issued reserve receipt binding differs")
            self._assert_files()
            conn.commit()
            self._assert_files()
        except (sqlite3.Error, OSError, ValueError, TypeError, protocol.LedgerError):
            if conn is not None:
                conn.rollback()
            raise StoreUnavailable("persistent ledger transaction failed; resolve its outcome by status") from None
        except BaseException:
            if conn is not None:
                conn.rollback()
            raise
        finally:
            if conn is not None:
                conn.close()
        if failure is not None:
            # A lazy expiry is committed even when it rejects the requested
            # mutation. Rolling it back here could otherwise reopen the lease.
            raise failure
        assert receipt is not None
        return receipt
