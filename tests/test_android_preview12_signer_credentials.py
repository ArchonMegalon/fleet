"""Synthetic secrets only; no provider, runtime custody, signing or deployment."""
import base64
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import traceback

import pytest

from scripts import android_preview12_signer_credentials as bridge
import test_android_preview12_protected_transaction as transaction

# Published RFC8032 test vector, not operational key material.
DER = bytes.fromhex('302e020100300506032b657004220420'
                    '9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')
SENTINEL = 'SYNTHETIC-SECRET-MUST-NOT-APPEAR'


def secrets():
    return dict(zip(bridge.SECRET_NAMES, (
        base64.b64encode(DER).decode(), base64.b64encode(b'synthetic-PKCS12-transport').decode(),
        SENTINEL, 'synthetic-key-password',
    )))


@pytest.fixture
def private():
    with tempfile.TemporaryDirectory(prefix='signer-credential-test-', dir='/tmp') as root:
        yield Path(root)


def rejected(callback, message='protected signer credentials unavailable'):
    with pytest.raises(bridge.CredentialError) as caught:
        callback()
    assert str(caught.value) == message
    rendered = ''.join(traceback.format_exception(caught.value))
    assert SENTINEL not in rendered
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_lazy_exact_four_paths_roundtrip_and_owned_cleanup(private, monkeypatch):
    values, reads = secrets(), []
    for name in bridge.SECRET_NAMES:
        monkeypatch.setenv(name, 'ambient-must-never-be-used')
    provider = lambda name: reads.append(name) or values[name]
    directory = private / 'credentials'
    keep = private / 'signed-output'
    keep.write_bytes(b'preserved')
    credentials = bridge.SignerCredentials(directory, provider)
    assert reads == [] and not directory.exists()
    with credentials:
        assert reads == [] and not directory.exists()
        paths = credentials({}, {})
        assert reads == list(bridge.SECRET_NAMES)
        assert set(paths) == {'ownerPrivateKey', 'keystore', 'storePassword', 'keyPassword'}
        assert all(path.is_absolute() and path.parent == directory for path in paths.values())
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        for path in paths.values():
            info = path.lstat()
            assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
            assert info.st_uid == os.getuid() and info.st_nlink == 1
        pem = paths['ownerPrivateKey'].read_bytes().splitlines()
        assert pem[0] == b'-----BEGIN PRIVATE KEY-----' and pem[-1] == b'-----END PRIVATE KEY-----'
        assert base64.b64decode(pem[1], validate=True) == DER
        assert paths['keystore'].read_bytes() == base64.b64decode(values[bridge.KEYSTORE_SECRET])
        assert paths['storePassword'].read_bytes() == SENTINEL.encode()
        assert paths['keyPassword'].read_bytes() == b'synthetic-key-password'
        with pytest.raises(bridge.CredentialError):
            credentials({}, {})
        assert all(path.exists() for path in paths.values())  # Reuse does not revoke the original context.
        assert reads == list(bridge.SECRET_NAMES)
    assert not directory.exists() and keep.read_bytes() == b'preserved'
    credentials.close()
    with pytest.raises(bridge.CredentialError):
        credentials({}, {})
    assert reads == list(bridge.SECRET_NAMES)


def test_callback_without_context_and_context_without_callback_never_read(private):
    reads = []
    credentials = bridge.SignerCredentials(private / 'keys', lambda name: reads.append(name))
    with pytest.raises(bridge.CredentialError):
        credentials({}, {})
    with credentials:
        pass
    assert reads == [] and not (private / 'keys').exists()


def test_reentrant_provider_cannot_retrieve_twice_or_reenter_context(private):
    values, calls = secrets(), []

    def provider(name):
        calls.append(name)
        rejected(lambda: credentials({}, {}))
        rejected(credentials.__enter__)
        return values[name]

    with bridge.SignerCredentials(private / 'keys', provider) as credentials:
        credentials({}, {})
    assert calls == list(bridge.SECRET_NAMES)


def test_converted_key_preserves_real_spki_and_existing_identity_guard(private):
    module = transaction.load_module()
    # Published RFC8032 vector 1 public key, encoded as Ed25519 SubjectPublicKeyInfo.
    public_der = bytes.fromhex('302a300506032b6570032100'
                              'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
    with bridge.SignerCredentials(private / 'keys', secrets().__getitem__) as credentials:
        key = credentials({}, {})['ownerPrivateKey']
        module._owner_key_matches(subprocess.run, key, hashlib.sha256(public_der).hexdigest())
        with pytest.raises(module.RebuilderError, match='does not match qualified public authority'):
            module._owner_key_matches(subprocess.run, key,
                                      '41b44078d037fafd85b091b967959f77a7a4aa9f160d03749fa49889a8b1b156')


@pytest.mark.parametrize('defect', ('existing', 'symlink', 'dangling', 'parent-mode', 'parent-symlink', 'relative'))
def test_unsafe_target_rejects_before_provider(private, defect):
    directory = private / 'keys'
    if defect == 'existing':
        directory.mkdir(mode=0o700)
    elif defect in ('symlink', 'dangling'):
        directory.symlink_to(private if defect == 'symlink' else private / 'missing')
    elif defect == 'parent-mode':
        private.chmod(0o750)
    elif defect == 'parent-symlink':
        alias = private / 'alias'
        alias.symlink_to(private, target_is_directory=True)
        directory = alias / 'keys'
    else:
        directory = Path('relative-keys')
    reads = []
    try:
        rejected(lambda: bridge.SignerCredentials(directory, lambda name: reads.append(name)).__enter__())
        assert reads == []
    finally:
        private.chmod(0o700)


@pytest.mark.parametrize('field,bad', [
    (bridge.BUILDER_SECRET, ''), (bridge.BUILDER_SECRET, None),
    (bridge.BUILDER_SECRET, base64.b64encode(DER).decode() + '\n'),
    (bridge.BUILDER_SECRET, base64.b64encode(DER + b'x').decode()),
    (bridge.BUILDER_SECRET, base64.b64encode(b'x' * 48).decode()),
    (bridge.KEYSTORE_SECRET, ''), (bridge.KEYSTORE_SECRET, '%%%'),
    (bridge.KEYSTORE_SECRET, 'Zh=='),  # Nonzero pad bits, decodes but is not canonical.
    (bridge.KEYSTORE_SECRET, 'A' * (4 * ((bridge.MAX_KEYSTORE_BYTES + 2) // 3) + 1)),
    (bridge.STORE_PASSWORD_SECRET, ''), (bridge.STORE_PASSWORD_SECRET, 'bad\nvalue'),
    (bridge.STORE_PASSWORD_SECRET, 'bad\rvalue'), (bridge.STORE_PASSWORD_SECRET, 'bad\0value'),
    (bridge.KEY_PASSWORD_SECRET, 'x' * (bridge.MAX_PASSWORD_BYTES + 1)),
    (bridge.KEY_PASSWORD_SECRET, 'é' * bridge.MAX_PASSWORD_BYTES),
    (bridge.KEY_PASSWORD_SECRET, '\ud800'), (bridge.KEY_PASSWORD_SECRET, b'not-text'),
])
def test_invalid_secrets_have_fixed_error_and_partial_files_removed(private, field, bad):
    values = secrets()
    values[field] = bad
    credentials = bridge.SignerCredentials(private / 'keys', values.__getitem__)
    with credentials:
        rejected(lambda: credentials({}, {}))
    assert not (private / 'keys').exists()


@pytest.mark.parametrize('failure_at', range(4))
def test_provider_failure_cleans_every_partial_prefix_without_leak(private, failure_at):
    values, calls = secrets(), []

    def provider(name):
        calls.append(name)
        if len(calls) == failure_at + 1:
            raise RuntimeError(SENTINEL)
        return values[name]

    with bridge.SignerCredentials(private / 'keys', provider) as credentials:
        rejected(lambda: credentials({}, {}))
    assert len(calls) == failure_at + 1
    assert not (private / 'keys').exists()


@pytest.mark.parametrize('operation', ('write', 'fsync', 'file-chmod', 'directory-open'))
def test_partial_os_failures_clean_owned_resources(private, monkeypatch, operation):
    target = private / 'keys'
    original_open, original_chmod = os.open, os.fchmod

    def fail(*_args, **_kwargs):
        raise OSError(SENTINEL)

    def chmod(fd, mode):
        if mode == 0o600:
            fail()
        return original_chmod(fd, mode)

    def open_directory(path, flags, *args, **kwargs):
        if path == 'keys' and flags & os.O_DIRECTORY:
            fail()
        return original_open(path, flags, *args, **kwargs)

    name, replacement = {'write': ('write', fail), 'fsync': ('fsync', fail),
                         'file-chmod': ('fchmod', chmod), 'directory-open': ('open', open_directory)}[operation]
    with bridge.SignerCredentials(target, secrets().__getitem__) as credentials:
        monkeypatch.setattr(bridge.os, name, replacement)
        rejected(lambda: credentials({}, {}))
    assert not target.exists()


@pytest.mark.parametrize('defect', ('replacement', 'symlink', 'hardlink', 'modified', 'directory-replaced', 'extra-child'))
def test_drift_preserves_foreign_objects_and_reports_cleanup_failure(private, defect):
    target = private / 'keys'
    credentials = bridge.SignerCredentials(target, secrets().__getitem__)
    credentials.__enter__()
    paths = credentials({}, {})
    key = paths['ownerPrivateKey']
    foreign = private / 'foreign'
    foreign.write_bytes(b'not-owned')
    foreign.chmod(0o600)
    if defect == 'replacement':
        key.unlink()
        os.link(foreign, key)
    elif defect == 'symlink':
        key.unlink()
        key.symlink_to(foreign)
    elif defect == 'hardlink':
        os.link(key, private / 'alias')
    elif defect == 'modified':
        key.write_bytes(b'changed')
    elif defect == 'directory-replaced':
        target.rename(private / 'moved-keys')
        target.mkdir(mode=0o700)
        (target / 'foreign').write_bytes(b'not-owned')
    else:
        (target / 'foreign').write_bytes(b'not-owned')
    rejected(credentials.close, 'protected signer credential cleanup incomplete')
    assert foreign.read_bytes() == b'not-owned'
    if defect in ('directory-replaced', 'extra-child'):
        assert (target / 'foreign').read_bytes() == b'not-owned'
    rejected(credentials.close, 'protected signer credential cleanup incomplete')


def test_parent_drift_between_entry_and_callback_never_reads_provider(private):
    parent = private / 'parent'
    parent.mkdir(mode=0o700)
    reads = []
    with bridge.SignerCredentials(parent / 'keys', lambda name: reads.append(name)) as credentials:
        parent.rename(private / 'moved')
        parent.mkdir(mode=0o700)
        rejected(lambda: credentials({}, {}))
    assert reads == [] and not (parent / 'keys').exists()


@pytest.mark.parametrize('failure', ('none', 'bad-provenance', 'terminal-reservation', 'partial-credentials', 'lost-commit'))
def test_actual_transaction_orders_bridge_and_recovery_never_retrieves_keys(private, monkeypatch, failure):
    module, events = transaction.load_module(), []
    lock, lock_raw, lease = transaction.fixture(module, private, events)
    client = transaction.install_fakes(module, monkeypatch, events, lock, lock_raw)
    consumer = transaction.fake_consumer(module, lease, events)
    values = secrets()
    reads = []

    def provider(name):
        reads.append(name)
        events.append('secret-provider')
        assert 'reserve' in events
        if failure == 'partial-credentials' and name == bridge.STORE_PASSWORD_SECRET:
            raise RuntimeError(SENTINEL)
        return values[name]

    if failure == 'bad-provenance':
        lease.provenance['lockSha256'] = '0' * 64
    elif failure == 'terminal-reservation':
        client.state = 'committed'
    elif failure == 'lost-commit':
        client.fail_commit_once = True
    output = private / 'signed-output'
    with bridge.SignerCredentials(private / 'keys', provider) as credentials:
        def execute():
            return module.execute_protected_signer_transaction(
                private / 'lock', lambda *_: lease, lambda: consumer, private, {}, credentials,
                lambda **_: {'status': 'pass'}, output, attempt_id='d' * 64,
                two_green_artifact_id=123, two_green_artifact_sha256='e' * 64)

        if failure == 'none':
            assert execute()['status'] == 'verified'
        else:
            expected = TimeoutError if failure == 'lost-commit' else (module.RebuilderError, bridge.CredentialError)
            with pytest.raises(expected):
                execute()
    assert not (private / 'keys').exists()
    if failure in ('bad-provenance', 'terminal-reservation'):
        assert reads == [] and 'sign' not in events
    elif failure == 'partial-credentials':
        assert reads == list(bridge.SECRET_NAMES[:3]) and 'sign' not in events
        assert module._recovery_path(lease.recovery_root, 'd' * 64).is_dir()
    else:
        assert reads == list(bridge.SECRET_NAMES)
        assert events.index('reserve') < events.index('secret-provider') < events.index('sign')
        if failure == 'lost-commit':
            result = module.reconcile_protected_signer_transaction(
                private / 'lock', lambda *_: lease, lambda: consumer, private, {},
                lambda **_: {'status': 'pass'}, output, attempt_id='d' * 64,
                two_green_artifact_id=123, two_green_artifact_sha256='e' * 64)
            assert result['status'] == 'verified'
            assert reads == list(bridge.SECRET_NAMES) and events.count('sign') == 1
        assert output.is_dir()  # Bridge cleanup never deletes signed output/recovery.
