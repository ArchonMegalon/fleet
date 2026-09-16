"""Actual file barriers and modeled Java; no keys, SDK or signer execution."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

import pytest

import test_android_preview12_protected_transaction as transaction


@pytest.fixture
def signing(tmp_path, monkeypatch):
    module = transaction.load_module()
    tmp_path.chmod(0o700)
    lock = json.loads(transaction.LOCK.read_text())
    lock["upload_key"]["key_alias"] = "test-upload"
    certificate = b"public test certificate"
    monkeypatch.setattr(module, "UPLOAD_CERTIFICATE_SHA256", hashlib.sha256(certificate).hexdigest())
    paths = [transaction.protected_file(tmp_path / name, data) for name, data in (
        ("unsigned.aab", b"unsigned"), ("upload.p12", b"not a keystore"),
        ("store-password", b"public fixture"), ("key-password", b"public fixture"))]
    output = tmp_path / "signed.aab"
    events = []

    def runner(command, **_kwargs):
        if "-exportcert" in command:
            return subprocess.CompletedProcess(command, 0, certificate, b"")
        if "-verify" in command:
            events.append("verified")
            return subprocess.CompletedProcess(command, 0, "jar verified.", "")
        if "-printcert" in command:
            events.append("certificate")
            pem = "-----BEGIN CERTIFICATE-----\n" + base64.b64encode(certificate).decode() + "\n-----END CERTIFICATE-----"
            return subprocess.CompletedProcess(command, 0, pem, "")
        events.append("sign")
        # Model jarsigner replacing, rather than updating, the unsigned inode.
        replacement = transaction.protected_file(tmp_path / "replacement", b"signed final bytes")
        os.replace(replacement, output)
        return subprocess.CompletedProcess(command, 0, b"", b"")

    def invoke(selected_runner=runner):
        return module.sign_aab(paths[0], output, lock, *paths[1:], tmp_path / "java", runner=selected_runner)

    return module, output, events, runner, invoke


def test_final_inode_and_parent_synced_after_verification_before_return(signing, monkeypatch):
    module, output, events, _runner, invoke = signing
    original = module.os.fsync

    def sync(descriptor):
        info = os.fstat(descriptor)
        if "sign" in events:
            events.append("directory-sync" if stat.S_ISDIR(info.st_mode) else "file-sync")
            if not stat.S_ISDIR(info.st_mode):
                assert info.st_ino == output.stat().st_ino
                assert os.pread(descriptor, 100, 0) == b"signed final bytes"
        return original(descriptor)

    monkeypatch.setattr(module.os, "fsync", sync)
    result = invoke()
    events.append("return")
    assert events == ["sign", "verified", "certificate", "file-sync", "directory-sync", "return"]
    assert result["sha256"] == hashlib.sha256(b"signed final bytes").hexdigest()
    assert result["sizeBytes"] == len(b"signed final bytes")


@pytest.mark.parametrize("change", ["replace", "symlink", "hardlink", "fifo", "public", "empty", "oversized"])
def test_unsafe_final_inode_rejected_without_destroying_bytes(signing, change):
    _module, output, events, runner, invoke = signing

    def changed(command, **kwargs):
        result = runner(command, **kwargs)
        if events == ["sign"]:
            if change == "replace":
                pass  # Replacement during verification is separately rejected below.
            elif change in {"symlink", "hardlink", "fifo"}:
                saved = output.with_name("saved")
                output.rename(saved)
                if change == "symlink":
                    output.symlink_to(saved)
                elif change == "hardlink":
                    os.link(saved, output)
                else:
                    os.mkfifo(output)
            elif change == "public":
                output.chmod(0o644)
            elif change == "empty":
                output.write_bytes(b"")
            else:
                with output.open("r+b") as stream:
                    stream.truncate(1024 * 1024 * 1024)
        if change == "replace" and "-verify" in command:
            output.rename(output.with_name("saved"))
            transaction.protected_file(output, b"swapped")
        return result

    with pytest.raises((OSError, _module.RebuilderError)):
        invoke(changed)
    assert output.lstat()
    if change in {"replace", "symlink", "hardlink", "fifo"}:
        assert output.with_name("saved").read_bytes() == b"signed final bytes"


@pytest.mark.parametrize("phase", ["file", "directory", "verification-mutation", "sync-mutation"])
def test_sync_or_drift_failure_never_returns_signed_claims(signing, monkeypatch, phase):
    module, output, events, runner, invoke = signing
    original = os.fsync

    def sync(descriptor):
        if "sign" in events:
            is_directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
            if (phase == "file" and not is_directory) or (phase == "directory" and is_directory):
                raise OSError("modeled sync failure")
            if phase == "sync-mutation" and not is_directory:
                output.write_bytes(b"changed during sync")
        return original(descriptor)

    def changed(command, **kwargs):
        result = runner(command, **kwargs)
        if phase == "verification-mutation" and "-printcert" in command:
            output.write_bytes(b"changed during verification")
        return result

    monkeypatch.setattr(module.os, "fsync", sync)
    with pytest.raises((OSError, module.RebuilderError)):
        invoke(changed)
    assert output.exists()


def test_hash_read_is_bounded_even_if_descriptor_never_reaches_eof(signing, monkeypatch):
    module, output, _events, _runner, invoke = signing
    requested = []

    def never_eof(_descriptor, count):
        requested.append(count)
        assert sum(requested) <= len(b"signed final bytes") + 1
        return b"x" * count

    monkeypatch.setattr(module.os, "read", never_eof)
    with pytest.raises(module.RebuilderError, match="size changed"):
        invoke()
    assert sum(requested) == len(b"signed final bytes") + 1
    assert output.read_bytes() == b"signed final bytes"


@pytest.mark.parametrize("change", ["alias", "permissions", "replace"])
def test_parent_custody_rejects_alias_or_drift(tmp_path, change):
    module = transaction.load_module()
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    output = transaction.protected_file(parent / "signed.aab", b"signed")
    if change == "alias":
        alias = tmp_path / "alias"
        alias.symlink_to(parent, target_is_directory=True)
        with pytest.raises(module.RebuilderError):
            with module._durable_signed_output(alias / output.name, 100):
                pytest.fail("aliased parent admitted")
        return
    with pytest.raises(module.RebuilderError):
        with module._durable_signed_output(output, 100):
            if change == "permissions":
                parent.chmod(0o755)
            else:
                parent.rename(tmp_path / "retained")
                parent.mkdir(mode=0o700)
    retained = tmp_path / "retained" / output.name if change == "replace" else output
    assert retained.read_bytes() == b"signed"


@pytest.mark.parametrize("failure", [False, True])
def test_transaction_barrier_precedes_attested_commit_and_failure_quarantines(tmp_path, monkeypatch, failure):
    module = transaction.load_module()
    events = []
    lock, lock_raw, lease = transaction.fixture(module, tmp_path, events)
    transaction.install_fakes(module, monkeypatch, events, lock, lock_raw)
    consumer = transaction.fake_consumer(module, lease, events)
    fake_sign = module.sign_aab
    original_sync = os.fsync
    original_write = module._recovery_write

    def sync(descriptor):
        if "signed-verified" in events and os.readlink(f"/proc/self/fd/{descriptor}").endswith("-signed.aab"):
            events.append("signed-file-sync")
            if failure:
                raise OSError("modeled final sync failure")
        return original_sync(descriptor)

    def sign(unsigned, output, *args, **kwargs):
        result = fake_sign(unsigned, output, *args, **kwargs)
        with module._durable_signed_output(output, 1024):
            events.append("signed-verified")
        return result

    def write(directory, name, record):
        events.append(name)
        return original_write(directory, name, record)

    monkeypatch.setattr(module, "sign_aab", sign)
    monkeypatch.setattr(module.os, "fsync", sync)
    monkeypatch.setattr(module, "_recovery_write", write)
    arguments = (tmp_path / "lock", lambda *_: lease, lambda: consumer, tmp_path, {},
                 lambda *_: {name: tmp_path / name for name in
                             ("keystore", "storePassword", "keyPassword", "ownerPrivateKey")},
                 lambda **_: {"status": "pass"}, tmp_path / "output")
    keywords = dict(attempt_id="d" * 64, two_green_artifact_id=123, two_green_artifact_sha256="e" * 64)
    if failure:
        with pytest.raises(OSError):
            module.execute_protected_signer_transaction(*arguments, **keywords)
        assert "ATTESTED.generated.json" not in events and "commit" not in events
        assert "sidecar" not in events and "android-v2" not in events and "external-v1" not in events
        assert "abort" not in events
        recovery = lease.recovery_root / ("d" * 64)
        assert any(path.name.endswith("-signed.aab") for path in recovery.iterdir())
        assert (recovery / "QUARANTINED.generated.json").exists()
        sign_count = events.count("sign")
        with pytest.raises(module.RebuilderError):
            module.execute_protected_signer_transaction(*arguments, **keywords)
        assert events.count("sign") == sign_count == 1
    else:
        module.execute_protected_signer_transaction(*arguments, **keywords)
        assert events.index("signed-verified") < events.index("signed-file-sync", events.index("signed-verified"))
        assert events.index("signed-file-sync") < events.index("sidecar") < events.index("ATTESTED.generated.json") < events.index("commit")
