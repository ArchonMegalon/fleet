"""Real temporary-file custody tests; no deployment, credentials or network."""
import hashlib
import json
import os
import stat

import pytest

from scripts import android_deployment_materializer as materializer
from scripts import android_hosted_controller_roles as hosted
from scripts import android_local_capture_owner as owner
from scripts import android_protected_job_bootstrap as protected
from test_android_deployment_materializer import _context, _profile


RAW = b'{"public_test":"not-a-production-deployment"}\n'


@pytest.fixture
def destination(tmp_path):
    parent = tmp_path / "private-output"
    parent.mkdir(mode=0o700)
    return parent / "deployment.json"


def test_real_exclusive_output_has_exact_bytes_private_mode_and_no_overwrite(destination):
    materializer._write_exclusive(destination, RAW)
    info = destination.stat()
    assert destination.read_bytes() == RAW
    assert stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_nlink == 1
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, b"replacement")
    assert destination.read_bytes() == RAW


def test_zero_write_stops_once_and_retains_empty_file(destination, monkeypatch):
    writes = []
    def zero(fd, raw):
        writes.append(len(raw))
        return 0
    monkeypatch.setattr(materializer.os, "write", zero)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert writes == [len(RAW)]
    assert destination.is_file() and destination.read_bytes() == b""


def test_partial_write_failure_retains_exact_prefix_without_retry(destination, monkeypatch):
    write = os.write
    calls = []
    def interrupted(fd, raw):
        calls.append(len(raw))
        if len(calls) == 1:
            return write(fd, raw[:7])
        raise OSError("PUBLIC-TEST-write-failure")
    monkeypatch.setattr(materializer.os, "write", interrupted)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert len(calls) == 2
    assert destination.read_bytes() == RAW[:7]


def test_parent_fsync_failure_retains_bytes_without_claiming_success(destination, monkeypatch):
    fsync = os.fsync
    calls = []
    def interrupted(fd):
        directory = stat.S_ISDIR(os.fstat(fd).st_mode)
        calls.append(directory)
        if directory:
            raise OSError("PUBLIC-TEST-directory-fsync-failure")
        return fsync(fd)
    monkeypatch.setattr(materializer.os, "fsync", interrupted)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert calls == [False, True]
    assert destination.read_bytes() == RAW


@pytest.mark.parametrize("mode", [0o755, 0o770, 0o777])
def test_nonprivate_output_parent_rejected_before_file_creation(destination, mode):
    destination.parent.chmod(mode)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert not destination.exists()


def test_symlink_parent_rejected_without_touching_target(destination):
    actual = destination.parent.with_name("actual-private")
    destination.parent.rename(actual)
    destination.parent.symlink_to(actual, target_is_directory=True)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert not (actual / destination.name).exists()


def test_hardlink_added_during_write_is_not_admitted(destination, monkeypatch):
    write = os.write
    alias = destination.with_name("unexpected-alias.json")
    def linked(fd, raw):
        count = write(fd, raw)
        os.link(destination, alias)
        return count
    monkeypatch.setattr(materializer.os, "write", linked)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert alias.stat().st_ino == destination.stat().st_ino
    assert destination.read_bytes() == RAW


def test_parent_replaced_by_alias_during_write_is_not_admitted(destination, monkeypatch):
    write = os.write
    moved = destination.parent.with_name("retained-original-parent")
    def substituted(fd, raw):
        count = write(fd, raw)
        destination.parent.rename(moved)
        destination.parent.symlink_to(moved, target_is_directory=True)
        return count
    monkeypatch.setattr(materializer.os, "write", substituted)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert (moved / destination.name).read_bytes() == RAW


def test_output_mode_change_before_fsync_rejected(destination, monkeypatch):
    write = os.write
    def changed(fd, raw):
        count = write(fd, raw)
        os.fchmod(fd, 0o644)
        return count
    monkeypatch.setattr(materializer.os, "write", changed)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert destination.read_bytes() == RAW


@pytest.mark.parametrize("boundary", ["readback", "directory-fsync"])
def test_named_output_rebound_at_terminal_io_is_rejected(destination, monkeypatch, boundary):
    original = destination.with_name("preserved-original.json")
    def rebind():
        destination.rename(original)
        destination.write_bytes(b"PUBLIC-TEST-replacement")
        destination.chmod(0o600)
    if boundary == "readback":
        pread = os.pread
        def intercepted(fd, size, offset):
            raw = pread(fd, size, offset)
            rebind()
            return raw
        monkeypatch.setattr(materializer.os, "pread", intercepted)
    else:
        fsync = os.fsync
        def intercepted(fd):
            result = fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                rebind()
            return result
        monkeypatch.setattr(materializer.os, "fsync", intercepted)
    with pytest.raises(materializer.MaterializerError):
        materializer._write_exclusive(destination, RAW)
    assert original.read_bytes() == RAW
    assert destination.read_bytes() == b"PUBLIC-TEST-replacement"


@pytest.mark.parametrize("attack", ["wrong-digest", "hardlink", "symlink", "writable", "oversized"])
def test_input_admission_rejects_wrong_bytes_aliases_or_unsafe_metadata(tmp_path, attack):
    source = tmp_path / "public-profile.json"
    source.write_bytes(RAW)
    source.chmod(0o600)
    digest = hashlib.sha256(RAW).hexdigest()
    limit = len(RAW)
    if attack == "wrong-digest":
        digest = "0" * 64
    elif attack == "hardlink":
        os.link(source, tmp_path / "alias.json")
    elif attack == "symlink":
        alias = tmp_path / "alias.json"
        alias.symlink_to(source)
        source = alias
    elif attack == "writable":
        source.chmod(0o666)
    else:
        limit -= 1
    with pytest.raises(materializer.MaterializerError):
        materializer._read_admitted(source, digest, limit)


def test_duplicate_json_keys_rejected():
    with pytest.raises(materializer.MaterializerError):
        materializer._json(b'{"role":"capture","role":"protected"}')


@pytest.mark.parametrize("role", materializer.ROLES)
def test_each_output_is_directly_consumed_by_its_existing_parser(tmp_path, role):
    raw = materializer.render(_profile(tmp_path), _context(), role)
    if role == "owner":
        owner._document(raw)
    elif role == "protected":
        protected._document(raw)
    else:
        hosted._document(raw, "capture" if role == "capture" else "emission-prepare")
    assert role not in json.loads(raw)  # No new four-role output envelope.


@pytest.mark.parametrize("attack", [
    "endpoint", "publisher", "lock", "subject", "environment", "template",
    "manifest", "prepare-zero", "prepare-absent", "stale-output", "unknown-field",
])
def test_cross_role_drift_or_unusable_profile_is_rejected(tmp_path, attack):
    value = _profile(tmp_path)
    if attack == "endpoint":
        value["capture"]["base_url"] = "https://different.example"
    elif attack == "publisher":
        value["capture"]["startup_barrier"] = {"publisher_id": "123"}
    elif attack == "lock":
        value["protected"]["pins"]["lock"]["sha256"] = "e" * 64
    elif attack == "subject":
        value["capture"]["job_policy"]["subject"] = "different-admitted-subject"
    elif attack == "environment":
        value["capture"]["job_policy"]["environment"] = "different-environment"
    elif attack == "template":
        value["capture"]["role_binding"]["templates"]["protected"]["check_run_id"] = "99999"
    elif attack == "manifest":
        # Detach the fixture's intentionally shared artifact object.
        value["capture"]["artifact_policy"] = dict(value["capture"]["artifact_policy"], subject_sha256="f" * 64)
    elif attack == "prepare-zero":
        value["protected"]["preparation_wait_seconds"] = 0
    elif attack == "prepare-absent":
        del value["protected"]["preparation_wait_seconds"]
    elif attack == "stale-output":
        value["protected"]["launcher"]["output"] += "-wrong"
    else:
        value["capture"]["unadmitted"] = True
    with pytest.raises(materializer.MaterializerError):
        materializer.render(value, _context(), "owner")


def test_remote_emission_path_is_not_created_or_required_on_owner(tmp_path):
    value = _profile(tmp_path)
    remote = tmp_path / "not-present-on-owner"
    value["emission"]["attestation_output_root"] = str(remote)
    owner._document(materializer.render(value, _context(), "owner"))
    assert not remote.exists()
    with pytest.raises(materializer.MaterializerError):
        materializer.render(value, _context(), "emission")
    assert not remote.exists()


def test_emission_output_is_deterministic_and_profile_is_not_mutated(tmp_path):
    value = _profile(tmp_path)
    before = json.dumps(value, sort_keys=True)
    first = materializer.render(value, _context(), "emission")
    second = materializer.render(value, _context(), "emission")
    assert first == second
    assert json.dumps(value, sort_keys=True) == before
    result = json.loads(first)
    assert result["artifact_policy"]["signer_commit"] == _context()["workflow_sha"]
    assert result["job_policy"]["check_run_id"] == value["emission"]["job_policy"]["check_run_id"]
    assert result["job_policy"]["challenge_nonce"] == value["emission"]["job_policy"]["challenge_nonce"]


def test_pure_render_does_not_open_files_fetch_identity_or_start_process(tmp_path, monkeypatch):
    import socket
    import subprocess
    value = _profile(tmp_path)
    def forbidden(*args, **kwargs):
        pytest.fail("render attempted file-content, network, or process access")
    monkeypatch.setattr(os, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(materializer.identity, "_fetch", forbidden)
    for role in materializer.ROLES:
        assert materializer.render(value, _context(), role)
