"""Private controller-owned, single-host GitHub workflow challenge journal.

The controller admits the policy, code/import closure, clock, database identity
and persistent local filesystem independently of the candidate. This module
calls the real RS256 verifier; no authenticator callback or claims input exists.
It returns only the existing WorkflowJobIdentity, NOT a signing capability,
artifact/producer attribution, runtime custody proof or signed ledger receipt.

Issue is a TRUSTED controller operation, never a candidate-facing policy API.
The input policy's nonce/times are replaced, not trusted as a fresh challenge.
Only its remaining, independently admitted fields select expected identity.
Keep the returned audience private to the intended job. Raw tokens/JTIs are
never stored; the nonce is retained only in this private policy journal.

DELETE/FULL SQLite commits precede successful responses. Lost responses stay
consumed; status never replays authentication. There is no purge, renewal,
reset, backup restore or implicit creation. Quota exhaustion fails closed.
The host must prevent rollback/replacement of the journal AND its external
database pin, protect backups, and qualify durable local storage (not NFS or an
ephemeral runner). These checks do not prove physical power-loss durability or
defend against a malicious trusted owner/root. No keys, signing, HTTP service,
workflow activation or signing-ledger protocol is introduced.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from urllib.parse import quote

from scripts import android_workflow_identity as identity

APPLICATION_ID = 0x43574353
SCHEMA_VERSION = 1
MAX_POLICY_BYTES = 16384
MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_CHALLENGES = 4096
_SCHEMA = (
    """CREATE TABLE store_identity (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        controller_id TEXT NOT NULL, database_id TEXT NOT NULL,
        maximum_challenges INTEGER NOT NULL)""",
    """CREATE TRIGGER identity_no_update BEFORE UPDATE ON store_identity
        BEGIN SELECT RAISE(ABORT, 'immutable identity'); END""",
    """CREATE TRIGGER identity_no_delete BEFORE DELETE ON store_identity
        BEGIN SELECT RAISE(ABORT, 'immutable identity'); END""",
    """CREATE TABLE challenges (
        challenge_sha TEXT PRIMARY KEY NOT NULL, slot_sha TEXT NOT NULL UNIQUE,
        policy_sha TEXT NOT NULL, policy_bytes BLOB NOT NULL,
        issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
        consumed_at INTEGER, token_sha TEXT UNIQUE, jti_sha TEXT UNIQUE,
        identity_bytes BLOB,
        CHECK(length(policy_bytes) BETWEEN 1 AND 16384),
        CHECK((consumed_at IS NULL AND token_sha IS NULL AND jti_sha IS NULL AND identity_bytes IS NULL)
           OR (consumed_at IS NOT NULL AND token_sha IS NOT NULL AND jti_sha IS NOT NULL
               AND identity_bytes IS NOT NULL AND length(identity_bytes) BETWEEN 1 AND 16384)))""",
    """CREATE TRIGGER challenge_no_delete BEFORE DELETE ON challenges
        BEGIN SELECT RAISE(ABORT, 'permanent challenge'); END""",
    """CREATE TRIGGER challenge_identity_immutable BEFORE UPDATE ON challenges
        WHEN NEW.challenge_sha IS NOT OLD.challenge_sha OR NEW.slot_sha IS NOT OLD.slot_sha
          OR NEW.policy_sha IS NOT OLD.policy_sha OR NEW.policy_bytes IS NOT OLD.policy_bytes
          OR NEW.issued_at IS NOT OLD.issued_at OR NEW.expires_at IS NOT OLD.expires_at
        BEGIN SELECT RAISE(ABORT, 'immutable challenge'); END""",
    """CREATE TRIGGER challenge_consumption_immutable BEFORE UPDATE ON challenges
        WHEN OLD.consumed_at IS NOT NULL OR NEW.consumed_at IS NULL
        BEGIN SELECT RAISE(ABORT, 'single consumption'); END""",
)


class ChallengeStoreError(RuntimeError):
    """Constant, content-free errors; callers must not log token arguments."""


def _require(condition, code):
    if not condition:
        raise ChallengeStoreError(code)


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    _require(0 < len(raw) <= MAX_POLICY_BYTES, "journal-value-bound")
    return raw


def _policy(raw):
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_POLICY_BYTES, "journal-policy")
    value = identity._json(raw)
    _require(type(value) is dict, "journal-policy")
    result = identity.WorkflowJobPolicy(**value)
    _require(_canonical(asdict(result)) == raw, "journal-policy-canonical")
    return result


def _slot(policy):
    # A changed source/environment/status policy cannot renew the same job slot.
    return _sha(_canonical([policy.transaction_id, policy.repository_id,
        policy.run_id, policy.run_attempt, policy.check_run_id]))


def _file(path):
    info = path.lstat()
    _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
             and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
             and info.st_size <= MAX_DATABASE_BYTES, "journal-file-custody")
    return info.st_dev, info.st_ino


def _parent(path):
    _require(isinstance(path, Path) and path.is_absolute()
             and path.name not in {"", ".", ".."} and path.resolve(strict=False) == path,
             "journal-path")
    chain = [*reversed(path.parent.parents), path.parent]
    result = []
    for index, part in enumerate(chain):
        info = part.lstat()
        _require(stat.S_ISDIR(info.st_mode) and info.st_uid in {0, os.getuid()}, "journal-ancestor")
        mode = stat.S_IMODE(info.st_mode)
        if mode & 0o022:
            # Only the canonical root-owned sticky /tmp exception. Its next
            # child must be our private directory, not another shared ancestor.
            _require(part == Path("/tmp") and info.st_uid == 0 and mode == 0o1777
                     and index + 1 < len(chain), "journal-writable-ancestor")
            child = chain[index + 1].lstat()
            _require(child.st_uid == os.getuid() and stat.S_IMODE(child.st_mode) == 0o700,
                     "journal-sticky-child")
        if part == path.parent:
            _require(info.st_uid == os.getuid() and mode == 0o700, "journal-private-parent")
        result.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    return tuple(result)


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _configuration(controller_id, database_id, maximum_challenges):
    _require(type(controller_id) is str and re.fullmatch(r"[a-z][a-z0-9_.-]{2,63}", controller_id)
             and _digest(database_id) and type(maximum_challenges) is int
             and 1 <= maximum_challenges <= MAX_CHALLENGES, "journal-configuration")


class SQLiteWorkflowChallengeStore:
    """Private journal, with independently retained controller/database pins.

    Construction only opens existing history. create() is explicit provisioning,
    never a request fallback. An uncertain failed create leaves its exclusive
    file in place. No operation deletes journal history or returns a bearer.
    """

    def __init__(self, path: Path, *, controller_id: str, database_id: str,
                 maximum_challenges: int = MAX_CHALLENGES):
        _configuration(controller_id, database_id, maximum_challenges)
        self._path = path
        self._controller_id, self._database_id = controller_id, database_id
        self._maximum_challenges = maximum_challenges
        failed = False
        connection = None
        try:
            self._parents, self._inode = _parent(path), _file(path)
            connection = self._connection()
            self._verify(connection)
            _require(connection.execute("PRAGMA quick_check(1)").fetchall() == [("ok",)], "journal-integrity")
            self._assert_files()
        except (OSError, sqlite3.Error, ValueError, TypeError, identity.WorkflowIdentityError):
            failed = True
        finally:
            if connection is not None:
                connection.close()
        if failed:
            raise ChallengeStoreError("journal-open-failed")

    @classmethod
    def create(cls, path: Path, *, controller_id: str, database_id: str,
               maximum_challenges: int = MAX_CHALLENGES):
        _configuration(controller_id, database_id, maximum_challenges)
        failed = False
        connection = None
        try:
            parents = _parent(path)
            _require(all(not os.path.lexists(str(path) + suffix) for suffix in ("-journal", "-wal", "-shm")),
                     "journal-existing-sidecar")
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            inode = _file(path)
            _sync_directory(path.parent)
            connection = cls._open(path)
            connection.execute("BEGIN EXCLUSIVE")
            for statement in _SCHEMA:
                connection.execute(statement)
            connection.execute("INSERT INTO store_identity VALUES (1,?,?,?)",
                (controller_id, database_id, maximum_challenges))
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            connection.commit()
            _sync_directory(path.parent)
            _require(_parent(path) == parents and _file(path) == inode, "journal-create-drift")
        except (OSError, sqlite3.Error, ValueError, TypeError):
            failed = True
        finally:
            if connection is not None:
                connection.close()
        if failed:
            raise ChallengeStoreError("journal-create-failed-no-reset")
        return cls(path, controller_id=controller_id, database_id=database_id,
                   maximum_challenges=maximum_challenges)

    @staticmethod
    def _open(path):
        connection = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=rw",
            uri=True, timeout=2, isolation_level=None)
        try:
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
            connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 32768)
            remaining_steps = 2000000
            def progress():
                nonlocal remaining_steps
                remaining_steps -= 1000
                return int(remaining_steps <= 0)
            connection.set_progress_handler(progress, 1000)
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA trusted_schema=OFF")
            _require(connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
                     and connection.execute("PRAGMA synchronous").fetchone() == (2,)
                     and connection.execute("PRAGMA trusted_schema").fetchone() == (0,), "journal-durability-mode")
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
            _require(type(page_size) is int and 512 <= page_size <= 65536, "journal-page-size")
            connection.execute(f"PRAGMA max_page_count={MAX_DATABASE_BYTES // page_size}")
        except BaseException:
            connection.close()
            raise
        return connection

    def _assert_files(self):
        _require(_parent(self._path) == self._parents and _file(self._path) == self._inode, "journal-path-drift")
        _require(all(not os.path.lexists(str(self._path) + suffix) for suffix in ("-wal", "-shm")), "journal-wal")
        try:
            _file(Path(str(self._path) + "-journal"))
        except FileNotFoundError:
            pass  # A legitimate DELETE-mode writer can remove its journal.

    def _connection(self):
        self._assert_files()
        connection = self._open(self._path)
        try:
            self._assert_files()
        except BaseException:
            connection.close()
            raise
        return connection

    def _verify(self, connection):
        _require(connection.execute("PRAGMA application_id").fetchone() == (APPLICATION_ID,)
                 and connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,), "journal-identity")
        # Check bounded physical schema BEFORE querying a potentially hostile
        # same-named view/table. GLOB's underscore is literal, unlike LIKE.
        actual = connection.execute("SELECT sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchmany(len(_SCHEMA) + 1)
        normalize = lambda sql: " ".join(sql.split())
        _require(len(actual) == len(_SCHEMA) and all(type(row[0]) is str for row in actual)
                 and sorted(normalize(row[0]) for row in actual) == sorted(map(normalize, _SCHEMA)), "journal-schema")
        _require(connection.execute("SELECT * FROM store_identity").fetchmany(2)
                 == [(1, self._controller_id, self._database_id, self._maximum_challenges)], "journal-identity")
        _require(connection.execute("SELECT count(*) FROM challenges").fetchone()[0] <= self._maximum_challenges,
                 "journal-quota")

    def _row(self, connection, challenge):
        row = connection.execute("SELECT * FROM challenges WHERE challenge_sha=?", (challenge,)).fetchone()
        _require(row is not None, "challenge-unknown")
        policy = _policy(row[3])
        _require(row[0] == _sha(policy.audience.encode()) and row[1] == _slot(policy)
                 and row[2] == _sha(row[3]) and type(row[4]) is int and type(row[5]) is int
                 and row[4] == policy.challenge_issued_at and row[5] == policy.challenge_expires_at,
                 "challenge-binding")
        if row[6] is None:
            _require(all(value is None for value in row[7:]), "challenge-state")
        else:
            _require(type(row[6]) is int and row[4] <= row[6] < row[5]
                     and _digest(row[7]) and _digest(row[8]) and type(row[9]) is bytes,
                     "challenge-state")
            facts = identity.WorkflowJobIdentity(**identity._json(row[9]))
            self._match(facts, policy, row[6])
            _require(_canonical(asdict(facts)) == row[9] and facts.token_sha256 == row[7]
                     and facts.token_identifier_sha256 == row[8], "challenge-consumed-binding")
        return row, policy

    @staticmethod
    def _match(facts, policy, now):
        _require(type(facts) is identity.WorkflowJobIdentity, "authentication-result")
        expected = {"repository": policy.repository, "repository_id": policy.repository_id,
            "repository_owner_id": policy.repository_owner_id, "source_sha": policy.sha,
            "workflow_ref": policy.workflow_ref, "workflow_sha": policy.workflow_sha,
            "job_workflow_ref": policy.job_workflow_ref, "job_workflow_sha": policy.job_workflow_sha,
            "run_id": policy.run_id, "run_attempt": policy.run_attempt, "check_run_id": policy.check_run_id,
            "environment": policy.environment, "transaction_id": policy.transaction_id,
            "audience_sha256": _sha(policy.audience.encode()), "job_status": policy.job_status}
        _require(all(type(getattr(facts, key)) is type(value) and getattr(facts, key) == value
                     for key, value in expected.items()), "authentication-binding")
        _require(all(type(value) is int and value > 0 for value in
                     (facts.job_id, facts.issued_at, facts.expires_at, facts.valid_until, facts.checked_at))
                 and policy.challenge_issued_at <= facts.issued_at <= facts.checked_at <= now
                 and facts.valid_until == min(facts.expires_at, policy.challenge_expires_at,
                                             facts.issued_at + policy.maximum_token_age_seconds)
                 and now < facts.valid_until and 0 < facts.expires_at - facts.issued_at <= 600
                 and all(_digest(value) for value in (facts.token_sha256, facts.token_identifier_sha256, facts.jwks_sha256))
                 and type(facts.pyjwt_version) is str and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", facts.pyjwt_version)
                 and tuple(map(int, facts.pyjwt_version.split("."))) >= (2, 13, 0)
                 and type(facts.cryptography_version) is str
                 and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", facts.cryptography_version), "authentication-validity")

    def issue(self, expected_policy: identity.WorkflowJobPolicy, *, lifetime_seconds: int = 300):
        """Trusted controller ONLY. Return a durably issued existing policy type.

        Nonce/times in expected_policy are discarded. Other fields are exact
        controller admissions, not derived from candidate JWTs or metadata.
        A job/transaction slot is permanent even after expiry or consumption.
        """
        failed = False
        connection = None
        try:
            _require(type(expected_policy) is identity.WorkflowJobPolicy, "challenge-policy")
            expected_policy.__post_init__()
            _require(type(lifetime_seconds) is int and 1 <= lifetime_seconds <= 600, "challenge-lifetime")
            connection = self._connection()
            connection.execute("BEGIN IMMEDIATE")
            self._verify(connection)
            now = int(time.time())
            policy = replace(expected_policy, challenge_nonce=secrets.token_hex(32),
                challenge_issued_at=now, challenge_expires_at=now + lifetime_seconds)
            raw = _canonical(asdict(policy))
            _require(connection.execute("SELECT count(*) FROM challenges").fetchone()[0] < self._maximum_challenges,
                     "challenge-quota")
            connection.execute("INSERT INTO challenges VALUES (?,?,?,?,?,?,NULL,NULL,NULL,NULL)",
                (_sha(policy.audience.encode()), _slot(policy), _sha(raw), raw, now, now + lifetime_seconds))
            self._assert_files()
            connection.commit()
            _sync_directory(self._path.parent)
            self._assert_files()
            _require(policy.challenge_issued_at <= int(time.time()) < policy.challenge_expires_at,
                     "challenge-expired-after-issue")
        except (OSError, sqlite3.Error, ValueError, TypeError, identity.WorkflowIdentityError):
            failed = True
        finally:
            if connection is not None:
                connection.close()
        if failed:
            raise ChallengeStoreError("challenge-issue-failed")
        return policy

    def _read(self, challenge):
        _require(_digest(challenge), "challenge-key")
        connection = self._connection()
        try:
            connection.execute("BEGIN")
            self._verify(connection)
            row, policy = self._row(connection, challenge)
            self._assert_files()
            return row, policy
        finally:
            connection.close()

    def status(self, challenge_sha256: str) -> str:
        """Diagnostic only; never returns prior authentication or renews it."""
        failed = False
        try:
            row, policy = self._read(challenge_sha256)
            now = int(time.time())
            _require(now >= policy.challenge_issued_at, "journal-clock-rollback")
            return "consumed" if row[6] is not None else ("expired" if now >= row[5] else "pending")
        except (OSError, sqlite3.Error, ValueError, TypeError, identity.WorkflowIdentityError):
            failed = True
        if failed:
            raise ChallengeStoreError("challenge-status-failed")

    def authenticate_and_consume(self, challenge_sha256: str, token: str) -> identity.WorkflowJobIdentity:
        """Real crypto + exact stored admission, then atomic single-use commit.

        Verification occurs outside the SQLite writer lock. After acquisition,
        policy bytes, state and fresh expiry are rechecked. Only one contender
        returns authentication. A failure after commit stays consumed forever.
        """
        failed = False
        connection = None
        try:
            before, policy = self._read(challenge_sha256)
            _require(before[6] is None, "challenge-consumed")
            now = int(time.time())
            _require(policy.challenge_issued_at <= now < policy.challenge_expires_at, "challenge-expired")
            facts = identity.authenticate_workflow_job(token, policy)
            _require(type(facts) is identity.WorkflowJobIdentity, "authentication-result")
            _require(type(token) is str and facts.token_sha256 == _sha(token.encode("ascii")), "authentication-token")
            self._match(facts, policy, int(time.time()))
            connection = self._connection()
            connection.execute("BEGIN IMMEDIATE")
            self._verify(connection)
            row, current = self._row(connection, challenge_sha256)
            _require(row == before and current == policy, "challenge-consumed-or-drifted")
            now = int(time.time())  # AFTER lock acquisition, never a caller timestamp.
            self._match(facts, current, now)
            count = connection.execute("""UPDATE challenges SET consumed_at=?,token_sha=?,jti_sha=?,identity_bytes=?
                WHERE challenge_sha=? AND consumed_at IS NULL AND policy_sha=?""",
                (now, facts.token_sha256, facts.token_identifier_sha256, _canonical(asdict(facts)),
                 challenge_sha256, row[2])).rowcount
            _require(count == 1, "challenge-consumption-conflict")
            self._assert_files()
            connection.commit()
            _sync_directory(self._path.parent)
            self._assert_files()
            self._match(facts, current, int(time.time()))
        except (OSError, sqlite3.Error, ValueError, TypeError, identity.WorkflowIdentityError):
            failed = True
        finally:
            if connection is not None:
                connection.close()
        if failed:
            raise ChallengeStoreError("challenge-authentication-failed")
        return facts
