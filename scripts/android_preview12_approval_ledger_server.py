"""Explicit direct-TLS launcher for the existing PR11 ledger, not its provisioner.

Linux only. No import-time app, credential discovery, database creation, approval
signer, deployment or publication authority. Invoke as a module, not via uvicorn's
import-string/factory CLI: python -m scripts.android_preview12_approval_ledger_server.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import ipaddress
import math
import os
from pathlib import Path
import re
import selectors
import signal
import ssl
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

import fastapi
import uvicorn
from uvicorn.protocols.http.h11_impl import H11Protocol

from scripts import android_preview12_approval_ledger as protocol
from scripts import android_preview12_approval_ledger_service as service
from scripts import android_preview12_approval_ledger_store as persistence
from scripts import android_preview12_two_green_release_approval as issuer

_ERROR = "ledger launcher configuration unavailable"
_SEALS = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
_PKCS8 = bytes.fromhex("302e020100300506032b657004220420")
_NULL_LOG = {"version": 1, "disable_existing_loggers": False,
             "handlers": {"null": {"class": "logging.NullHandler"}},
             "loggers": {name: {"handlers": ["null"], "propagate": False, "level": "CRITICAL"}
                         for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi")}}


class LaunchError(RuntimeError):
    """Fixed diagnostic, without paths, credentials or exception chains."""


@dataclass(frozen=True)
class LaunchConfig:
    policy: str
    database: str
    database_id: str
    bearer_sha256_file: str
    receipt_key_file: str
    tls_cert_file: str
    tls_key_file: str
    bind_address: str
    maximum_in_flight: int = 2
    maximum_connections: int = 16
    body_timeout: float = 10.0
    shutdown_timeout: float = 15.0
    trusted_proxy_addresses: tuple[str, ...] = ()


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _path(value: str) -> Path:
    if type(value) is not str or not value or len(value) > 4096 \
            or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise LaunchError(_ERROR)
    path = Path(value)
    if not path.is_absolute() or str(path) != value or path.resolve(strict=True) != path:
        raise LaunchError(_ERROR)
    return path


def _ancestors(path: Path):
    rows = []
    for directory in reversed(path.parents):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.getuid()):
            raise LaunchError(_ERROR)
        # The one shared test/runtime temporary root exception still requires a
        # private immediate child; it does not bless arbitrary writable ancestry.
        if directory == Path('/tmp') and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o1777:
            child = Path('/tmp') / path.relative_to('/tmp').parts[0]
            ci = child.lstat()
            if not stat.S_ISDIR(ci.st_mode) or ci.st_uid != os.getuid() or stat.S_IMODE(ci.st_mode) != 0o700:
                raise LaunchError(_ERROR)
        elif stat.S_IMODE(info.st_mode) & 0o022:
            raise LaunchError(_ERROR)
        rows.append((directory, info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid))
    return rows


class _HeldFile:
    def __init__(self, value: str, limit: int):
        self.fd = -1
        self.data = b''
        self.path = _path(value)
        self.ancestors = _ancestors(self.path)
        before = self.path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid() \
                or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o600 \
                or not 0 < before.st_size <= limit:
            raise LaunchError(_ERROR)
        self.stamp = _identity(before)
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            self.data = os.pread(self.fd, limit + 1, 0)
            if len(self.data) != before.st_size:
                raise LaunchError(_ERROR)
            self.assert_exact()
        except BaseException:
            self.close()
            raise

    def assert_exact(self):
        if self.fd < 0 or _ancestors(self.path) != self.ancestors \
                or _identity(os.fstat(self.fd)) != self.stamp or _identity(self.path.lstat()) != self.stamp \
                or os.pread(self.fd, len(self.data) + 1, 0) != self.data \
                or _identity(os.fstat(self.fd)) != self.stamp or _identity(self.path.lstat()) != self.stamp \
                or _ancestors(self.path) != self.ancestors:
            raise LaunchError(_ERROR)

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        self.data = b''


def _sealed(data: bytes, stack: ExitStack) -> int:
    fd = os.memfd_create('ledger-launcher-input', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    stack.callback(os.close, fd)
    view = memoryview(data)
    while view:
        count = os.write(fd, view)
        if count <= 0:
            raise LaunchError(_ERROR)
        view = view[count:]
    fcntl.fcntl(fd, fcntl.F_ADD_SEALS, _SEALS)
    if fcntl.fcntl(fd, fcntl.F_GET_SEALS) != _SEALS:
        raise LaunchError(_ERROR)
    return fd


def _openssl(arguments: list[str], descriptors: tuple[int, ...]) -> bytes:
    """Only bounded fixed local crypto operations; never inherit auth/stdio.

    Do not poll/reap the leader before group cleanup: its unreaped PID retains
    group ownership even if a descendant keeps an output pipe open.
    """
    path = Path('/usr/bin/openssl')
    _ancestors(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or not info.st_mode & 0o111:
        raise LaunchError(_ERROR)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if _identity(os.fstat(fd)) != _identity(info):
            raise LaunchError(_ERROR)
        process = subprocess.Popen([f'/proc/self/fd/{fd}', *arguments],
            pass_fds=(fd, *descriptors), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, start_new_session=True)
    finally:
        os.close(fd)
    output = bytearray()
    error_size = 0
    deadline = time.monotonic() + 5.0
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LaunchError(_ERROR)
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fd, 4097)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    elif key.fileobj is process.stdout:
                        output.extend(chunk)
                    else:
                        error_size += len(chunk)
                    if len(output) > 4096 or error_size > 4096:
                        raise LaunchError(_ERROR)
        # EOF alone does not guarantee process exit; retain the same deadline.
        while not os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT):
            if time.monotonic() >= deadline:
                raise LaunchError(_ERROR)
            time.sleep(0.005)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.stdout.close()
        process.stderr.close()
        process.wait(timeout=1)
    if process.returncode != 0 or error_size:
        raise LaunchError(_ERROR)
    return bytes(output)


class _BoundedHttp(H11Protocol):
    """Bound post-handshake connection lifetime, including partial headers."""
    def connection_made(self, transport):
        super().connection_made(transport)
        self._deadline = self.loop.call_later(20, transport.abort)
        if len(self.connections) > self.limit_concurrency:
            transport.abort()

    def connection_lost(self, exc):
        self._deadline.cancel()
        super().connection_lost(exc)


class _Server(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        # Uvicorn 0.34.2 replays SIGTERM before returning to its caller. Defer
        # that terminal status so the launcher's outer ExitStack can unwind.
        if threading.current_thread() is not threading.main_thread():
            yield
            return
        previous = {sig: signal.signal(sig, self.handle_exit) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        if self.started:
            print('ledger_server=ready', flush=True)


class _InputFence:
    def __init__(self, app, inputs):
        self.app, self.inputs = app, inputs

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            try:
                self.inputs._assert_exact()
            except Exception:
                await service._response(503)(scope, receive, send)
                return
        await self.app(scope, receive, send)


class PreparedServer:
    def __init__(self):
        self._stack = ExitStack()
        self._lock = threading.Lock()
        self._closed = False
        self._files = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        # Only fixed five-second local OpenSSL work holds this lock. The service
        # itself retains admission while its worker finishes after cancellation.
        with self._lock:
            self._closed = True
            self._stack.close()

    def _hold(self, value, limit):
        held = _HeldFile(value, limit)
        self._stack.callback(held.close)
        self._files.append(held)
        return held

    def _assert_exact(self):
        if self._closed:
            raise LaunchError(_ERROR)
        for held in self._files:
            held.assert_exact()
        if _ancestors(self._database) != self._database_ancestors:
            raise LaunchError(_ERROR)

    def sign_receipt(self, raw: bytes) -> bytes:
        try:
            if type(raw) is not bytes or not 0 < len(raw) <= 262144:
                raise LaunchError(_ERROR)
            with self._lock, ExitStack() as temporary:
                self._assert_exact()
                message = _sealed(raw, temporary)
                signature = _openssl(['pkeyutl', '-sign', '-rawin', '-keyform', 'DER',
                    '-inkey', f'/proc/self/fd/{self._receipt_fd}', '-in', f'/proc/self/fd/{message}'],
                    (self._receipt_fd, message))
                self._assert_exact()
                if len(signature) != 64:
                    raise LaunchError(_ERROR)
                return signature
        except Exception:
            raise LaunchError(_ERROR) from None


def prepare(options: LaunchConfig) -> PreparedServer:
    result = PreparedServer()
    try:
        if type(options) is not LaunchConfig or fastapi.__version__ != '0.115.12' or uvicorn.__version__ != '0.34.2' \
                or type(options.bind_address) is not str or '%' in options.bind_address \
                or str(ipaddress.ip_address(options.bind_address)) != options.bind_address \
                or type(options.database_id) is not str or not protocol.SHA256.fullmatch(options.database_id):
            raise LaunchError(_ERROR)
        service.validate_trusted_proxy_addresses(options.trusted_proxy_addresses)
        for value, low, high in ((options.maximum_in_flight, 1, 8), (options.maximum_connections, 2, 64)):
            if type(value) is not int or not low <= value <= high:
                raise LaunchError(_ERROR)
        for value, high in ((options.body_timeout, 10), (options.shutdown_timeout, 30)):
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value <= high:
                raise LaunchError(_ERROR)
        policy_file = result._hold(options.policy, 262144)
        policy = protocol.strict_json_bytes(policy_file.data, 'approval policy', 262144)
        ledger = protocol.validate_ledger_policy(policy['replay_protection']['external_ledger'], require_configured=True)
        receipt_public = base64.b64decode(ledger['receipt_public_key_spki_der_base64'], validate=True)
        approval = policy['external_ed25519_key']
        approval_public = base64.b64decode(approval['public_key_spki_der_base64'], validate=True)
        if len(approval_public) != 44 or not approval_public.startswith(protocol.SPKI_ED25519_PREFIX) \
                or hashlib.sha256(approval_public).hexdigest() != approval['expected_public_key_spki_sha256'] \
                or approval['public_key_spki_der_base64'] != issuer.RELEASE_APPROVER_PUBLIC_KEY_SPKI_DER_BASE64 \
                or approval['expected_public_key_spki_sha256'] != issuer.RELEASE_APPROVER_PUBLIC_KEY_SPKI_SHA256 \
                or receipt_public == approval_public:
            raise LaunchError(_ERROR)
        # No credential file is opened before configured policy and separation.
        result._database = _path(options.database)
        result._database_ancestors = _ancestors(result._database)
        store = persistence.SQLiteApprovalLedgerStore(result._database,
            service_identity=ledger['expected_service_identity'], database_id=options.database_id)
        digest = result._hold(options.bearer_sha256_file, 65)
        if re.fullmatch(rb'[0-9a-f]{64}\n?', digest.data) is None:
            raise LaunchError(_ERROR)
        receipt = result._hold(options.receipt_key_file, 48)
        if len(receipt.data) != 48 or not receipt.data.startswith(_PKCS8):
            raise LaunchError(_ERROR)
        result._receipt_fd = _sealed(receipt.data, result._stack)
        public = _openssl(['pkey', '-inform', 'DER', '-in', f'/proc/self/fd/{result._receipt_fd}',
                           '-pubout', '-outform', 'DER'], (result._receipt_fd,))
        if public != receipt_public or hashlib.sha256(public).hexdigest() != ledger['receipt_public_key_spki_sha256']:
            raise LaunchError(_ERROR)
        cert = result._hold(options.tls_cert_file, 131072)
        if re.fullmatch(rb'(?:-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\r?\n?)+', cert.data) is None \
                or cert.data.count(b'-----BEGIN CERTIFICATE-----') > 8:
            raise LaunchError(_ERROR)
        cert_fd = _sealed(cert.data, result._stack)
        cert_path = f'/proc/self/fd/{cert_fd}'
        # Public certificate admission precedes any TLS private-key read. TLS,
        # ledger receipts and release approvals must have distinct key roles.
        tls_public_pem = _openssl(['x509', '-in', cert_path, '-pubkey', '-noout'], (cert_fd,))
        with ExitStack() as temporary:
            public_fd = _sealed(tls_public_pem, temporary)
            tls_public = _openssl(['pkey', '-pubin', '-in', f'/proc/self/fd/{public_fd}',
                                   '-outform', 'DER'], (public_fd,))
        if tls_public in (approval_public, receipt_public):
            raise LaunchError(_ERROR)
        # A supplied chain is used as a local anchor ONLY for hostname, validity
        # and server-purpose checks. This does not establish public client trust.
        _openssl(['verify', '-no-CAfile', '-no-CApath', '-no-CAstore', '-trusted', cert_path,
                  '-partial_chain', '-verify_hostname', urlsplit(ledger['base_url']).hostname,
                  '-purpose', 'sslserver', cert_path], (cert_fd,))
        key = result._hold(options.tls_key_file, 32768)
        if not key.data.startswith((b'-----BEGIN PRIVATE KEY-----', b'-----BEGIN RSA PRIVATE KEY-----', b'-----BEGIN EC PRIVATE KEY-----')):
            raise LaunchError(_ERROR)
        key_fd = _sealed(key.data, result._stack)
        result.app = service.create_app(ledger_policy=ledger, store=store,
            bearer_token_sha256=digest.data.rstrip(b'\n').decode('ascii'), sign_receipt=result.sign_receipt,
            maximum_in_flight=options.maximum_in_flight, body_timeout_seconds=options.body_timeout,
            trusted_proxy_addresses=options.trusted_proxy_addresses)
        result.app.add_middleware(_InputFence, inputs=result)
        result.config = uvicorn.Config(result.app, host=options.bind_address, port=443, workers=1,
            interface='asgi3', loop='asyncio', http=_BoundedHttp, ws='none', lifespan='on', reload=False,
            proxy_headers=False, forwarded_allow_ips='', access_log=False, log_config=_NULL_LOG,
            server_header=False, date_header=False, backlog=32, limit_concurrency=options.maximum_connections,
            timeout_keep_alive=2, timeout_graceful_shutdown=options.shutdown_timeout,
            h11_max_incomplete_event_size=16384, ssl_certfile=cert_path,
            ssl_keyfile=f'/proc/self/fd/{key_fd}', ssl_keyfile_password='', ssl_version=ssl.PROTOCOL_TLS_SERVER)
        result.config.load()
        result.config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
        result._assert_exact()
        result.server = _Server(result.config)
        return result
    except BaseException as error:
        result.close()
        if isinstance(error, KeyboardInterrupt):
            raise
        raise LaunchError(_ERROR) from None


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise LaunchError('ledger launcher arguments invalid')


def main(argv=None) -> int:
    try:
        parser = _Parser(description=__doc__, allow_abbrev=False)
        for name in ('policy', 'database', 'database-id', 'bearer-sha256-file', 'receipt-key-file',
                     'tls-cert-file', 'tls-key-file', 'bind-address'):
            parser.add_argument('--' + name, required=True)
        parser.add_argument('--maximum-in-flight', type=int, default=2)
        parser.add_argument('--maximum-connections', type=int, default=16)
        parser.add_argument('--body-timeout', type=float, default=10.0)
        parser.add_argument('--shutdown-timeout', type=float, default=15.0)
        parser.add_argument('--trusted-proxy-address', action='append', default=[], dest='trusted_proxy_addresses')
        arguments = vars(parser.parse_args(argv))
        arguments['trusted_proxy_addresses'] = tuple(arguments['trusted_proxy_addresses'])
        with prepare(LaunchConfig(**arguments)) as prepared:
            prepared.server.run()
            if not prepared.server.started:
                raise LaunchError(_ERROR)
            stopped_by = prepared.server._captured_signals[-1] if prepared.server._captured_signals else None
        # Preserve conventional signal status after resource cleanup, without
        # reintroducing Uvicorn's early SIGTERM or a KeyboardInterrupt traceback.
        reason = '' if stopped_by is None else ' signal=' + signal.Signals(stopped_by).name
        print('ledger_server=stopped' + reason, flush=True)
        return 0 if stopped_by is None else 128 + int(stopped_by)
    except KeyboardInterrupt:
        print('ledger_server=stopped signal=SIGINT', file=sys.stderr, flush=True)
        return 130
    except (Exception, SystemExit):
        print('ledger_server=unavailable', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
