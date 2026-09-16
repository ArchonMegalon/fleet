"""Public-only, live local-controller -> protected-job intake.

The owner admits both endpoints, their code/TLS/job policies and custody. A
socket response is not serialized runtime provenance. This module keeps the
actual completed controller alive, consumes a fresh existing job challenge and
transfers the closed seven-file artifact. It never constructs a signing lease,
loads credentials, signs, launches Docker or creates an HTTP listener.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import threading
import time

from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_controller_rendezvous as rendezvous
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_workflow_challenge_store as journal
from scripts import android_workflow_identity as identity

CHUNK = 1024 * 1024
MAX_CHECKS = 4096
_ERROR = "protected public intake stopped; do not replay"
_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


class IntakeError(RuntimeError):
    """Constant diagnostics only; never tokens, paths or upstream responses."""


def _require(value):
    if not value:
        raise IntakeError(_ERROR)


def _stamp(path):
    return fleet.PreservedRebuildHandoff._identity(path.lstat())


class PublicCaptureExport:
    """Owner-only construction from the actual completed, still-live adapter.

    The new intended protected job is an independently admitted third check run
    in the same invocation, not a role supplied over HTTP. Its token authorizes
    admission once, not every minute of transfer. A separate fixed monotonic
    lifetime/idle bound applies afterward; there is no token renewal or resume.
    """

    def __init__(self, completed: rendezvous.ControllerRendezvous, *,
                 job_policy: identity.WorkflowJobPolicy, bearer_sha256: str,
                 approval_bearer_sha256: str, binary_bearer_sha256: str,
                 maximum_seconds: int = 1800, idle_seconds: int = 60):
        self._mutex = threading.RLock()
        self._stopped = self._armed = self._submitted = self._bundle_sent = False
        self._issued = self._authenticated = None
        self._fds, self._index, self._offset, self._sequence = {}, 0, 0, 0
        self._started = self._last = None
        try:
            _require(type(completed) is rendezvous.ControllerRendezvous)
            self._controller, self._result = completed, completed.completed()
            self._session, self._retained = completed._session, completed._retained
            _require(type(job_policy) is identity.WorkflowJobPolicy)
            job_policy.__post_init__()
            identity._same_context(job_policy, completed._artifact_policy)
            for field in ("repository", "repository_id", "repository_owner", "repository_owner_id",
                          "sha", "ref", "workflow_ref", "workflow_sha", "run_id", "run_attempt", "transaction_id"):
                _require(getattr(job_policy, field) == getattr(completed._capture_policy, field))
            _require(job_policy.check_run_id not in {completed._capture_policy.check_run_id,
                     completed._emission_policy.check_run_id}
                     and job_policy.runner_environment == "github-hosted"
                     and job_policy.run_status == job_policy.job_status == "in_progress")
            values = (bearer_sha256, approval_bearer_sha256, binary_bearer_sha256)
            _require(all(identity._hex(value, 64) for value in values)
                     and len(set(values)) == 3
                     and bytes.fromhex(bearer_sha256) not in completed._digests.values())
            _require(type(maximum_seconds) is int and 1 <= maximum_seconds <= 7200
                     and type(idle_seconds) is int and 1 <= idle_seconds <= 120
                     and idle_seconds <= maximum_seconds)
            self._maximum, self._idle, self._policy = maximum_seconds, idle_seconds, job_policy
            self._store = completed._store
            self._limits = dict(self._retained._limits)
            self._names = tuple(sorted(self._limits))
            self._bundle = completed._bundle
            _require(type(self._bundle) is origin._CapturedFile
                     and self._bundle.pin.sha256 == self._result.artifact_origin.bundle_sha256)
            self.hostname = completed.hostname
            self.prefix = "/android-protected-capture/" + job_policy.transaction_id
            self._digests = {"intake": bytes.fromhex(bearer_sha256)}
            self._exact(full=True)
        except BaseException:
            self.close()
            raise IntakeError(_ERROR) from None

    def _exact(self, *, full=False):
        _require(not self._stopped)
        with self._controller._condition:
            self._controller._exact()
            _require(self._controller._state == "complete" and self._controller._result is self._result
                     and self._controller._session is self._session
                     and self._controller._retained is self._retained)
            self._session._lock_snapshot.recheck()
            if full:
                self._session._retained(self._retained)
                self._bundle.recheck()
        if self._started is not None:
            now = time.monotonic()
            _require(self._started <= self._last <= now
                     and now - self._started < self._maximum and now - self._last < self._idle)

    def arm(self):
        """Owner-only. No HTTP request can issue or renew a challenge."""
        with self._mutex:
            try:
                _require(not self._armed)
                self._armed = True
                self._exact(full=True)
                self._issued = self._store.issue(self._policy)
            except BaseException:
                self.close()
                raise IntakeError(_ERROR) from None

    def close(self):
        with self._mutex:
            self._stopped = True
            while self._fds:
                _, descriptor = self._fds.popitem()
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _admit(self, raw):
        _require(self._issued is not None and not self._submitted)
        self._submitted = True  # A consumed-but-lost response never replays.
        _require(0 < len(raw) <= identity.MAX_TOKEN and all(32 <= byte < 127 for byte in raw))
        facts = self._session._consume(self._issued, raw.decode("ascii"))
        _require(facts.job_id not in {self._result.capture_job.job_id, self._result.emission_job.job_id})
        self._exact(full=True)
        self._store._match(facts, self._issued, int(time.time()))
        for name in self._names:
            path = self._retained.artifact_subject_path.parent / name
            descriptor = os.open(path, _FLAGS)
            self._fds[name] = descriptor
            expected = self._retained._snapshot[name][0]
            _require(fleet.PreservedRebuildHandoff._identity(os.fstat(descriptor)) == expected == _stamp(path))
        self._exact(full=True)
        self._store._match(facts, self._issued, int(time.time()))
        self._authenticated = facts
        self._started = self._last = time.monotonic()
        return 200, b"admitted-public-transfer-only\n"

    def _chunk(self, operation):
        _require(self._index < len(self._names))
        name = self._names[self._index]
        _require(operation == "file/" + name + "/" + str(self._offset // CHUNK))
        descriptor = self._fds[name]
        expected = self._retained._snapshot[name][0]
        path = self._retained.artifact_subject_path.parent / name
        _require(fleet.PreservedRebuildHandoff._identity(os.fstat(descriptor)) == expected == _stamp(path))
        raw = os.pread(descriptor, CHUNK, self._offset)
        _require(self._offset + len(raw) <= self._limits[name]
                 and fleet.PreservedRebuildHandoff._identity(os.fstat(descriptor)) == expected == _stamp(path))
        self._offset += len(raw)
        if len(raw) < CHUNK:
            _require(self._offset == os.fstat(descriptor).st_size)
            self._index, self._offset = self._index + 1, 0
        self._exact()
        self._last = time.monotonic()
        return 200, raw

    def exchange(self, role, operation, raw):
        with self._mutex:
            try:
                self._exact()
                _require(role == "intake" and type(raw) is bytes)
                if operation == "challenge" and not raw:
                    _require(not self._submitted and self._issued is not None)
                    self._controller._fresh(self._issued)
                    return 200, self._issued.audience.encode("ascii")
                if operation == "submit":
                    return self._admit(raw)
                _require(self._authenticated is not None)
                if operation == "check":
                    _require(len(raw) == 8 and self._sequence < MAX_CHECKS
                             and struct.unpack(">Q", raw)[0] == self._sequence)
                    self._sequence += 1
                    self._exact(full=True)
                    self._last = time.monotonic()
                    return 200, raw  # Ephemeral correlation, NOT a provenance receipt.
                _require(not raw)
                if operation == "bundle":
                    _require(self._index == len(self._names) and not self._bundle_sent)
                    self._bundle_sent = True
                    self._exact(full=True)
                    self._last = time.monotonic()
                    return 200, self._bundle.raw
                return self._chunk(operation)
            except BaseException:
                self.close()
                return 409, b"stopped-reconcile\n"


class PublicCaptureApp(rendezvous._FixedApp):
    """Concrete fixed routes; no listener or permission to deploy one."""

    def __init__(self, exporter: PublicCaptureExport, *, trusted_proxy_addresses=()):
        _require(type(exporter) is PublicCaptureExport)
        operations = ["challenge", "submit", "check", "bundle"]
        for name, limit in exporter._limits.items():
            operations.extend("file/" + name + "/" + str(index) for index in range(limit // CHUNK + 1))
        routes = {(exporter.prefix + "/" + value).encode(): ("intake", value) for value in operations}
        super().__init__(exporter, routes, trusted_proxy_addresses=trusted_proxy_addresses,
                         body_limits={"check": 8, "bundle": 0})


def _root_directory(path):
    _require(os.getuid() == os.geteuid() == 0 and type(path) is type(Path()))
    fleet._trusted_root(path, "protected public intake")
    _require(stat.S_IMODE(path.stat().st_mode) == 0o700)


def _mount(source, target, flags):
    """Only the fixed private intake bind; never shell or user mount options."""
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.mount(os.fsencode(source) if source else None, os.fsencode(target),
                        None, ctypes.c_ulong(flags), None)
    if result != 0:
        raise IntakeError(_ERROR)


def _mount_record(path):
    # Targets are constrained below to printable canonical paths without spaces.
    with Path("/proc/self/mountinfo").open("rb") as stream:
        rows = stream.read(1024 * 1024 + 1)
    _require(len(rows) <= 1024 * 1024)
    matches = [row.split() for row in rows.splitlines()
               if len(row.split()) >= 10 and row.split()[4] == os.fsencode(path)]
    _require(len(matches) == 1 and matches[0][0].isdigit() and b"-" in matches[0])
    row = matches[0]
    return row[0], frozenset(row[5].split(b",")), tuple(row[6:row.index(b"-")])


def _mount_id(path):
    return _mount_record(path)[0]


class ReadOnlyIntake:
    """Own one real Linux bind mount. Failed input/evidence is never deleted.

    ROOT host privileges are required; this is not run in the cap-drop signer.
    No source/tool roots or arbitrary trees may be mounted through this helper.
    """

    def __init__(self, packet, names):
        self.packet, self.source, self.target = packet, packet / "files", packet / "preserved"
        _root_directory(packet)
        _require(all(32 < ord(c) < 127 and c != "\\" for c in str(packet)))
        _require(self.source.resolve(strict=True) == self.source and not self.source.is_symlink()
                 and self.source.is_dir() and self.source.stat().st_uid == os.getuid()
                 and stat.S_IMODE(self.source.stat().st_mode) == 0o700)
        _require(set(path.name for path in self.source.iterdir()) == set(names))
        self._source_identity = _stamp(self.source)
        for name in names:
            info = (self.source / name).lstat()
            _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                     and stat.S_IMODE(info.st_mode) == 0o400)
        _require(not self.target.exists() and not self.target.is_symlink())
        self.target.mkdir(mode=0o700)
        self._packet_identity = _stamp(packet)
        self._id = None
        try:
            _mount(self.source, self.target, 4096)  # MS_BIND, never recursive.
            self._id = _mount_id(self.target)
            _mount(None, self.target, 1 << 18)  # MS_PRIVATE.
            _mount(None, self.target, 4096 | 32 | 1 | 2 | 4 | 8)  # bind remount ro,nosuid,nodev,noexec.
            self.assert_exact()
            journal._sync_directory(packet)
        except BaseException:
            if self._id is not None:
                self.close()
            raise IntakeError(_ERROR) from None

    def assert_exact(self):
        _root_directory(self.packet)
        mount_id, options, propagation = _mount_record(self.target)
        _require(self._id is not None and mount_id == self._id
                 and _stamp(self.packet) == self._packet_identity
                 and _stamp(self.source) == self._source_identity
                 and _stamp(self.target) == self._source_identity
                 and os.statvfs(self.target).f_flag & os.ST_RDONLY
                 and {b"ro", b"nosuid", b"nodev", b"noexec"} <= options and b"rw" not in options
                 and not any(item.startswith((b"shared:", b"master:", b"propagate_from:")) for item in propagation))

    def close(self):
        if self._id is not None:
            _require(_mount_id(self.target) == self._id and _stamp(self.target) == self._source_identity)
            libc = ctypes.CDLL(None, use_errno=True)
            _require(libc.umount2(os.fsencode(self.target), 0) == 0)  # No force/lazy/recursive unmount.
            self._id = None


@dataclass(frozen=True, slots=True)
class CapturedPublicIntake:
    """Actual custody + live public transport, NEVER AuthenticatedRebuildHandoff."""
    retained: fleet.PreservedRebuildHandoff
    artifact_origin: origin.OriginFacts
    custody: ReadOnlyIntake
    connection: "PublicCaptureClient"

    def assert_exact(self):
        try:
            self.connection.assert_live()
            self.custody.assert_exact()
            self.retained.assert_exact()
            self.connection.assert_live()
        except BaseException:
            self.connection.close()
            raise IntakeError(_ERROR) from None


class PublicCaptureClient:
    """Real fixed HTTPS exchanges; no reconnect/retry or serialized capability.

    TLS context, exact origin, expected job/subject and bearer are independently
    admitted protected-job inputs. Existing OIDC acquisition remains job-owned.
    No environment discovery, credential names or signing API exists here.
    """

    def __init__(self, *, base_url, job_policy, artifact_policy, bearer, tls_context):
        _require(type(job_policy) is identity.WorkflowJobPolicy and type(artifact_policy) is origin.OriginPolicy)
        job_policy.__post_init__()
        artifact_policy.__post_init__()
        identity._same_context(job_policy, artifact_policy)
        _require(job_policy.runner_environment == "github-hosted"
                 and job_policy.job_status == job_policy.run_status == "in_progress")
        self._http = rendezvous.HostedClient(base_url=base_url, transaction_id=job_policy.transaction_id,
            role="capture", bearer=bearer, manifest_sha256=artifact_policy.subject_sha256, tls_context=tls_context)
        self._http._prefix = "/android-protected-capture/" + job_policy.transaction_id + "/"
        self._policy, self._job = artifact_policy, job_policy
        self._failed = self._begun = self._received = False
        self._sequence = 0
        self._mutex = threading.RLock()

    def _post(self, operation, raw=b"", limit=4096):
        try:
            _require(not self._failed)
            return self._http._post(operation, raw, limit)
        except BaseException:
            self._failed = True
            raise IntakeError(_ERROR) from None

    def challenge(self):
        with self._mutex:
            try:
                _require(not self._begun)
                status, raw = self._post("challenge")
                _require(status == 200 and re.fullmatch(rb"urn:chummer:fleet:workflow-job:"
                         + self._job.transaction_id.encode() + rb":[0-9a-f]{64}", raw))
                return raw.decode("ascii")
            except BaseException:
                self.close()
                raise IntakeError(_ERROR) from None

    def begin(self, token):
        with self._mutex:
            try:
                _require(not self._begun and identity._text(token, identity.MAX_TOKEN))
                self._begun = True
                _require(self._post("submit", token.encode()) == (200, b"admitted-public-transfer-only\n"))
            except BaseException:
                self._failed = True
                raise IntakeError(_ERROR) from None

    def assert_live(self):
        with self._mutex:
            try:
                _require(self._begun and self._sequence < MAX_CHECKS)
                raw = struct.pack(">Q", self._sequence)
                self._sequence += 1
                _require(self._post("check", raw, 8) == (200, raw))
            except BaseException:
                self._failed = True
                raise IntakeError(_ERROR) from None

    def close(self):
        self._failed = True

    def receive(self, packet: Path, *, lock: origin.PinnedFile,
                verifier: origin.PinnedFile, trusted_root: origin.PinnedFile) -> CapturedPublicIntake:
        """Stream bounded public files, seal real RO custody, verify real origin.

        Packet must be NEW below owner-admitted root-private ancestry. Mounts,
        partial files and tombstone are preserved on ambiguous failure, never
        adopted by a retry. The operator owns subsequent exact-target cleanup.
        """
        custody = None
        with self._mutex:
            try:
                _require(self._begun and not self._received)
                self._received = True
                self.assert_live()
                _root_directory(packet.parent)
                _require(packet.is_absolute() and packet.resolve(strict=False) == packet)
                packet.mkdir(mode=0o700)
                journal._sync_directory(packet.parent)
                rendezvous._write_new(packet / "no-replay", b"Public intake; no replay or signing authority.\n")
                inputs = [origin._capture(lock, 1024 * 1024),
                          origin._capture(verifier, 256 * 1024 * 1024, executable=True),
                          origin._capture(trusted_root, 16 * 1024 * 1024)]
                fleet._preserved_path(lock.path, "independently admitted intake lock")
                limits = capture._limits(fleet._strict_json(inputs[0].raw, "intake lock"))
                destination = packet / "files"
                destination.mkdir(mode=0o700)
                for name in sorted(limits):
                    descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                         | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
                    try:
                        count = 0
                        for index in range(limits[name] // CHUNK + 1):
                            status, raw = self._post("file/" + name + "/" + str(index), limit=CHUNK)
                            count += len(raw)
                            _require(status == 200 and count <= limits[name])
                            view = memoryview(raw)
                            while view:
                                written = os.write(descriptor, view)
                                _require(written > 0)
                                view = view[written:]
                            if len(raw) < CHUNK:
                                break
                        else:
                            raise IntakeError(_ERROR)
                        os.fchmod(descriptor, 0o400)
                        os.fsync(descriptor)
                        info = os.fstat(descriptor)
                        _require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                                 and fleet.PreservedRebuildHandoff._identity(info) == _stamp(destination / name))
                    finally:
                        os.close(descriptor)
                    self.assert_live()
                journal._sync_directory(destination)
                status, raw = self._post("bundle", limit=rendezvous.MAX_BUNDLE)
                _require(status == 200)
                bundle = packet / "origin-bundle.json"
                rendezvous._write_new(bundle, raw)
                self.assert_live()
                custody = ReadOnlyIntake(packet, limits)
                retained = fleet.PreservedRebuildHandoff(lock.path, custody.target)
                _require(retained.artifact_closure_sha256 == self._policy.subject_sha256)
                verified = origin.verify_rebuild_handoff_origin(retained, self._policy,
                    origin.PinnedFile(bundle, hashlib.sha256(raw).hexdigest()), verifier, trusted_root,
                    now=datetime.now(UTC))
                for value in inputs:
                    value.recheck()
                result = CapturedPublicIntake(retained, verified, custody, self)
                result.assert_exact()
                return result
            except BaseException:
                self.close()
                # Retain known mount and all evidence. Never let cleanup erase
                # the only copy of a received/ambiguous attempt or mask drift.
                raise IntakeError(_ERROR) from None
