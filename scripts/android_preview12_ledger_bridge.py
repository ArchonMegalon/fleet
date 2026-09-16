"""Bounded binary-ledger IPC, not controller admission or release authority.

The owner supplies independently admitted policy/subject and two new private
directories. Only requests are writable in the network-none signer; responses
are a separate read-only bind. The controller alone owns the HTTPS bearer.
No deployment, directory creation, key access, background worker or CLI here.
"""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import re
import stat
import threading
import time
import uuid

from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_store as wire


MAX_EXCHANGES = 64
_KEY = re.compile(r"[0-9a-f]{32}\Z")
_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
_ERROR = "binary ledger bridge exchange rejected"


class BridgeError(protocol.LedgerError):
    """Fixed, non-secret diagnostic; never includes request or transport data."""


def _require(value):
    if not value:
        raise BridgeError(_ERROR)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _directory_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)


class _Directory:
    def __init__(self, path):
        self.path = Path(path)
        _require(self.path.is_absolute() and self.path.resolve(strict=True) == self.path)
        self.ancestors = []
        for parent in (*reversed(self.path.parents), self.path):
            info = parent.lstat()
            _require(stat.S_ISDIR(info.st_mode) and info.st_uid in (0, os.getuid()))
            _require(not info.st_mode & 0o022 or (
                parent == Path('/tmp') and info.st_uid == 0 and info.st_mode & stat.S_ISVTX))
            self.ancestors.append((parent, _directory_identity(info)))
        info = self.path.lstat()
        _require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700)
        self.identity = _directory_identity(info)

    def open(self):
        fd = os.open(self.path, _FLAGS | os.O_DIRECTORY)
        try:
            _require(all(_directory_identity(path.lstat()) == identity for path, identity in self.ancestors))
            _require(_directory_identity(os.fstat(fd)) == self.identity
                     == _directory_identity(self.path.lstat())
                     and self.path.resolve(strict=True) == self.path)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def entries(self):
        fd = self.open()
        try:
            result = []
            with os.scandir(fd) as entries:
                for entry in entries:
                    _require(len(result) < MAX_EXCHANGES * 3)
                    _require(re.fullmatch(r'[0-9a-f]{32}\.(?:body|ready|tmp)', entry.name))
                    result.append(entry.name)
            return result
        finally:
            os.close(fd)

    def read(self, name, limit):
        directory = self.open()
        fd = None
        try:
            fd = os.open(name, _FLAGS, dir_fd=directory)
            before = os.fstat(fd)
            _require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                     and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                     and 0 <= before.st_size <= limit)
            raw = bytearray()
            while len(raw) <= limit:
                chunk = os.read(fd, min(65536, limit + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            _require(len(raw) == before.st_size and len(raw) <= limit
                     and _identity(before) == _identity(os.fstat(fd))
                     == _identity(os.stat(name, dir_fd=directory, follow_symlinks=False)))
            return bytes(raw)
        finally:
            if fd is not None:
                os.close(fd)
            os.close(directory)

    def publish(self, key, raw):
        _require(_KEY.fullmatch(key) and type(raw) is bytes)
        self.entries()  # Bound incomplete as well as completed exchanges.
        directory = self.open()
        temporary = uuid.uuid4().hex + '.tmp'
        fd = None
        created = False
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                         | os.O_CLOEXEC, 0o600, dir_fd=directory)
            created = True
            with os.fdopen(fd, 'wb') as stream:
                fd = None
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # link is no-replace. Readers use the ready marker only AFTER the
            # temporary link is removed: they never accept a partial/two-link body.
            os.link(temporary, key + '.body', src_dir_fd=directory,
                    dst_dir_fd=directory, follow_symlinks=False)
            os.unlink(temporary, dir_fd=directory)
            created = False
            marker = os.open(key + '.ready', os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
            try:
                os.fsync(marker)
            finally:
                os.close(marker)
            os.fsync(directory)
        finally:
            if fd is not None:
                os.close(fd)
            if created:
                os.unlink(temporary, dir_fd=directory)
            os.close(directory)

    def receive(self, key, limit):
        try:
            _require(self.read(key + '.ready', 0) == b'')
        except FileNotFoundError:
            return None
        return self.read(key + '.body', limit)


class _Binding:
    def __init__(self, policy, subject, policy_sha256):
        self.policy = protocol.validate_ledger_policy(
            policy, require_configured=True, binary_signing=True)
        _require(self.policy['credential_source'] == protocol.BINARY_CONTROLLER_CREDENTIAL_SOURCE)
        # Round-trip snapshots prevent caller dictionary mutation after admission.
        self.policy = protocol.strict_json_bytes(protocol.canonical_bytes(self.policy), 'policy', 65536)
        self.subject = protocol.canonical_bytes(wire._subject(subject))
        _require(type(policy_sha256) is str and protocol.SHA256.fullmatch(policy_sha256)
                 and subject['policySha256'] == policy_sha256)

    def request(self, raw):
        request, _ = wire._parse_request(raw)
        _require(protocol.canonical_bytes(request) == raw
                 and protocol.canonical_bytes(request['subject']) == self.subject)
        return request


class SignerTransport:
    """Credential-free callback for DurableApprovalLedgerClient.for_binary_bridge.

    A fresh pair of empty directories is required for every process/session;
    durable recovery remains the existing transaction journal plus HTTPS ledger.
    """
    def __init__(self, request_dir, response_dir, *, policy, subject, policy_sha256,
                 sleeper=time.sleep, clock=time.monotonic):
        self.binding = _Binding(policy, subject, policy_sha256)
        self.requests, self.responses = _Directory(request_dir), _Directory(response_dir)
        _require(self.requests.identity[:2] != self.responses.identity[:2])
        _require(not self.requests.entries() and not self.responses.entries())
        self._sleep, self._clock = sleeper, clock
        self._count = 0
        self._lock = threading.Lock()

    def __call__(self, body, timeout):
        try:
            with self._lock:
                self.binding.request(body)
                _require(type(timeout) is int and timeout == self.binding.policy['timeout_seconds']
                         and self._count < MAX_EXCHANGES)
                self._count += 1
                key = uuid.uuid4().hex
                deadline = self._clock() + timeout
                self.requests.publish(key, body)
                while self._clock() < deadline:
                    raw = self.responses.receive(key, 2 * protocol.MAX_LEDGER_RESPONSE_BYTES + 8192)
                    if raw is not None:
                        value = protocol.strict_json_bytes(raw, 'bridge response',
                                                          2 * protocol.MAX_LEDGER_RESPONSE_BYTES + 8192)
                        _require(set(value) == {'requestSha256', 'status', 'headers', 'bodyBase64'}
                                 and value['requestSha256'] == hashlib.sha256(body).hexdigest())
                        response = protocol.HttpResponse(value['status'], value['headers'],
                            base64.b64decode(value['bodyBase64'], validate=True))
                        _response(response, self.binding.policy)
                        return response
                    self._sleep(0.01)
                raise TimeoutError('binary ledger bridge response unavailable')
        except TimeoutError:
            raise
        except Exception:
            raise BridgeError(_ERROR) from None


def _response(response, policy):
    _require(type(response.status) is int and 100 <= response.status <= 599
             and type(response.body) is bytes
             and len(response.body) <= policy['maximum_response_bytes']
             and type(response.headers) is dict and len(response.headers) <= 2
             and set(response.headers) <= {'content-type', 'content-length'}
             and all(type(value) is str and len(value) <= 128 and not any(
                 ord(char) < 32 or ord(char) == 127 for char in value)
                     for value in response.headers.values()))


class ControllerBroker:
    """One admitted binary subject, fixed HTTPS origin; never a general proxy.

    Constructor inputs are NOT custody proof. Owner composition must first run
    the immutable binary/approval policy separation gates. This object performs
    no ambient secret discovery; only serve_once can invoke its HTTPS transport.
    """
    def __init__(self, request_dir, response_dir, *, policy, subject, policy_sha256,
                 bearer, https_transport=protocol._https_transport):
        self.binding = _Binding(policy, subject, policy_sha256)
        _require(type(bearer) is str and re.fullmatch(r'[A-Za-z0-9._~+/-]{1,4096}=*', bearer)
                 and len(bearer) <= 4096 and callable(https_transport))
        self.requests, self.responses = _Directory(request_dir), _Directory(response_dir)
        _require(self.requests.identity[:2] != self.responses.identity[:2])
        _require(not self.requests.entries() and not self.responses.entries())
        self._bearer, self._https = bearer, https_transport
        self._processed = set()
        self._lock = threading.Lock()

    def serve_once(self):
        """Process at most one ready request, or return False; no worker loop."""
        try:
            with self._lock:
                names = self.requests.entries()
                self.responses.entries()
                keys = sorted(name[:-6] for name in names if name.endswith('.ready'))
                _require(len(keys) <= MAX_EXCHANGES)
                for key in keys:
                    if key in self._processed:
                        continue
                    _require(_KEY.fullmatch(key) and len(self._processed) < MAX_EXCHANGES)
                    raw = self.requests.receive(key, self.binding.policy['maximum_request_bytes'])
                    _require(raw is not None)
                    request = self.binding.request(raw)
                    policy = self.binding.policy
                    # No URL, HTTP header or token arrives through IPC.
                    url = policy['base_url'] + policy[request['operation'] + '_path']
                    headers = {'Accept': 'application/json', 'Content-Type': 'application/json',
                               'User-Agent': 'chummer-fleet-preview12-approval-ledger/1',
                               'Authorization': 'Bearer ' + self._bearer}
                    self._processed.add(key)  # No ambiguous transport retry by this broker.
                    response = self._https(url, raw, headers, policy['timeout_seconds'])
                    # Retain only the two existing client-consumed HTTP headers.
                    kept = {}
                    _require(len(response.headers) <= 64)
                    for name, value in response.headers.items():
                        _require(type(name) is str)
                        lower = name.lower()
                        if lower in ('content-type', 'content-length'):
                            _require(lower not in kept)
                            kept[lower] = value
                    response = protocol.HttpResponse(response.status, kept, response.body)
                    _response(response, policy)
                    encoded = protocol.canonical_bytes({
                        'requestSha256': hashlib.sha256(raw).hexdigest(),
                        'status': response.status, 'headers': kept,
                        'bodyBase64': base64.b64encode(response.body).decode('ascii'),
                    })
                    self.responses.publish(key, encoded)
                    return True
                return False
        except Exception:
            raise BridgeError(_ERROR) from None
