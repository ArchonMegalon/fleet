"""One-shot job-local credential callback; not a provider or signer authority.

The protected transaction calls this only after its own reservation/admission
gates. An explicitly supplied trusted reader accesses already-injected secrets;
there is no environment discovery, key generation, network, or signing here.
Python memory zeroization and cleanup after SIGKILL are not guaranteed.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
import stat
import threading
from typing import Callable


BUILDER_SECRET = 'ANDROID_PREVIEW12_RELEASE_BUILDER_ED25519_PRIVATE_KEY_PKCS8_B64'
KEYSTORE_SECRET = 'ANDROID_PREVIEW12_UPLOAD_KEYSTORE_B64'
STORE_PASSWORD_SECRET = 'ANDROID_PREVIEW12_KEYSTORE_PASSWORD'
KEY_PASSWORD_SECRET = 'ANDROID_PREVIEW12_KEY_PASSWORD'
SECRET_NAMES = (BUILDER_SECRET, KEYSTORE_SECRET, STORE_PASSWORD_SECRET, KEY_PASSWORD_SECRET)
MAX_KEYSTORE_BYTES = 1024 * 1024
MAX_PASSWORD_BYTES = 4096
_PKCS8 = bytes.fromhex('302e020100300506032b657004220420')
_ERROR = 'protected signer credentials unavailable'
_CLEANUP_ERROR = 'protected signer credential cleanup incomplete'
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class CredentialError(RuntimeError):
    """Fixed diagnostic; never includes input values, paths or provider errors."""


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _directory_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)


def _ancestors(parent):
    if not parent.is_absolute() or parent.resolve(strict=True) != parent:
        raise CredentialError(_ERROR)
    rows = []
    for path in (*reversed(parent.parents), parent):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.getuid()):
            raise CredentialError(_ERROR)
        if path == Path('/tmp') and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o1777:
            child = Path('/tmp') / parent.relative_to('/tmp').parts[0]
            owned = child.lstat()
            if child == Path('/tmp') or owned.st_uid != os.getuid() or stat.S_IMODE(owned.st_mode) != 0o700:
                raise CredentialError(_ERROR)
        elif info.st_mode & 0o022:
            raise CredentialError(_ERROR)
        rows.append((path, _directory_identity(info)))
    info = parent.lstat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise CredentialError(_ERROR)
    return tuple(rows)


def _decode(value, limit):
    if type(value) is not str or not 0 < len(value) <= 4 * ((limit + 2) // 3):
        raise CredentialError(_ERROR)
    raw = base64.b64decode(value, validate=True)
    if not 0 < len(raw) <= limit or base64.b64encode(raw).decode('ascii') != value:
        raise CredentialError(_ERROR)
    return raw


def _builder_pem(value):
    raw = _decode(value, 48)
    if len(raw) != 48 or not raw.startswith(_PKCS8):
        raise CredentialError(_ERROR)
    # Exactly the same DER key, merely wrapped for the existing OpenSSL reader.
    return b'-----BEGIN PRIVATE KEY-----\n' + base64.b64encode(raw) + b'\n-----END PRIVATE KEY-----\n'


def _password(value):
    if type(value) is not str or not 0 < len(value) <= MAX_PASSWORD_BYTES or any(c in value for c in '\r\n\0'):
        raise CredentialError(_ERROR)
    raw = value.encode('utf-8', errors='strict')
    if len(raw) > MAX_PASSWORD_BYTES:
        raise CredentialError(_ERROR)
    return raw


class SignerCredentials:
    """Use as a context manager, passing its one-shot callable to the transaction.

    ``read_secret(name)`` is a trusted, explicitly injected job-secret reader.
    The reservation/provenance arguments are NOT independently authenticated by
    this bridge. Only the existing protected transaction may authorize its call.
    The parent must already be canonical, private and exclusively controlled by
    the signer; this is not protection against a hostile same-UID/admin writer.
    """

    def __init__(self, directory: Path, read_secret: Callable[[str], str]):
        self._directory = directory
        self._read_secret = read_secret
        self._entered = self._used = self._closed = self._cleanup_failed = False
        self._parent_fd = self._dir_fd = -1
        self._created = False
        self._directory_stamp = None
        self._files = {}
        self._lock = threading.RLock()

    def __enter__(self):
        with self._lock:
            return self._enter()

    def _enter(self):
        if self._entered or self._closed:
            raise CredentialError(_ERROR) from None
        try:
            if not isinstance(self._directory, Path) or not callable(self._read_secret):
                raise CredentialError(_ERROR)
            path = self._directory
            if not path.is_absolute() or path.name in ('', '.', '..') or '..' in path.parts \
                    or any(ord(c) < 32 or ord(c) == 127 for c in str(path)):
                raise CredentialError(_ERROR)
            self._ancestors = _ancestors(path.parent)
            self._parent_fd = os.open(path.parent, _DIR_FLAGS)
            if _directory_identity(os.fstat(self._parent_fd)) != self._ancestors[-1][1]:
                raise CredentialError(_ERROR)
            # Existence includes dangling links. Never adopt or repair a path.
            try:
                os.stat(path.name, dir_fd=self._parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise CredentialError(_ERROR)
            self._entered = True
            return self
        except BaseException:
            self._close_fds()
            self._closed = True
            raise CredentialError(_ERROR) from None

    def _check_directory(self):
        if _ancestors(self._directory.parent) != self._ancestors \
                or _directory_identity(os.fstat(self._parent_fd)) != self._ancestors[-1][1]:
            raise CredentialError(_ERROR)
        if self._directory_stamp is not None:
            actual = os.stat(self._directory.name, dir_fd=self._parent_fd, follow_symlinks=False)
            if _directory_identity(actual) != self._directory_stamp \
                    or (self._dir_fd >= 0 and _directory_identity(os.fstat(self._dir_fd)) != self._directory_stamp):
                raise CredentialError(_ERROR)

    def _check_files(self):
        self._check_directory()
        for name, identity in self._files.items():
            if _identity(os.stat(name, dir_fd=self._dir_fd, follow_symlinks=False)) != identity:
                raise CredentialError(_ERROR)

    def _write(self, name, raw):
        self._check_directory()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self._dir_fd)
        try:
            self._files[name] = _identity(os.fstat(fd))
            os.fchmod(fd, 0o600)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise CredentialError(_ERROR)
            self._files[name] = _identity(info)
            view = memoryview(raw)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise CredentialError(_ERROR)
                view = view[written:]
            os.fsync(fd)
        finally:
            # Include our partial file if writing/fsync failed, without adopting
            # any replacement pathname. Cleanup compares the held-FD identity.
            try:
                self._files[name] = _identity(os.fstat(fd))
            finally:
                os.close(fd)
        self._check_files()

    def __call__(self, _reservation, _provenance):
        with self._lock:
            return self._admit()

    def _admit(self):
        if not self._entered or self._used or self._closed:
            raise CredentialError(_ERROR) from None
        self._used = True
        try:
            self._check_directory()
            os.mkdir(self._directory.name, 0o700, dir_fd=self._parent_fd)
            self._created = True
            self._directory_stamp = _directory_identity(os.stat(
                self._directory.name, dir_fd=self._parent_fd, follow_symlinks=False))
            self._dir_fd = os.open(self._directory.name, _DIR_FLAGS, dir_fd=self._parent_fd)
            self._check_directory()
            os.fchmod(self._dir_fd, 0o700)
            self._directory_stamp = _directory_identity(os.fstat(self._dir_fd))
            self._check_directory()
            fields = (
                ('ownerPrivateKey', 'builder.pem', BUILDER_SECRET, _builder_pem),
                ('keystore', 'upload.p12', KEYSTORE_SECRET, lambda value: _decode(value, MAX_KEYSTORE_BYTES)),
                ('storePassword', 'store-password', STORE_PASSWORD_SECRET, _password),
                ('keyPassword', 'key-password', KEY_PASSWORD_SECRET, _password),
            )
            paths = {}
            for field, filename, name, convert in fields:
                self._check_files()
                raw = convert(self._read_secret(name))
                self._check_files()
                self._write(filename, raw)
                del raw
                paths[field] = self._directory / filename
            self._check_files()
            return paths
        except BaseException:
            try:
                self.close()
            except CredentialError:
                raise CredentialError(_CLEANUP_ERROR) from None
            raise CredentialError(_ERROR) from None

    def _close_fds(self):
        success = True
        for name in ('_dir_fd', '_parent_fd'):
            fd = getattr(self, name)
            if fd >= 0:
                setattr(self, name, -1)
                try:
                    os.close(fd)
                except BaseException:
                    success = False
        return success

    def close(self):
        with self._lock:
            self._cleanup()

    def _cleanup(self):
        if self._closed:
            if self._cleanup_failed:
                raise CredentialError(_CLEANUP_ERROR) from None
            return
        try:
            if self._created and self._directory_stamp is None:
                raise CredentialError(_CLEANUP_ERROR)
            if self._directory_stamp is not None:
                self._check_files()
                for name, identity in tuple(self._files.items()):
                    self._check_directory()
                    if _identity(os.stat(name, dir_fd=self._dir_fd, follow_symlinks=False)) != identity:
                        raise CredentialError(_CLEANUP_ERROR)
                    os.unlink(name, dir_fd=self._dir_fd)
                    del self._files[name]
                self._check_directory()
                # Only this exact empty directory; never recursive deletion.
                os.rmdir(self._directory.name, dir_fd=self._parent_fd)
        except BaseException:
            self._cleanup_failed = True
            raise CredentialError(_CLEANUP_ERROR) from None
        finally:
            self._closed = True
            self._read_secret = None
            if not self._close_fds():
                self._cleanup_failed = True
                raise CredentialError(_CLEANUP_ERROR) from None

    def __exit__(self, *_):
        self.close()
        return False
