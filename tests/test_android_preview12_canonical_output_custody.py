"""Real file/descriptor custody, with no compiler, signer or runtime admission.

The preparation fixture models SDK/build observations explicitly. The optional
exact-current Android check uses its real guarded sidecar parser, not keys or
release eligibility. No test promotes a failed producer receipt.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

import pytest

from scripts import android_preview12_external_rebuilder as fleet
from test_android_preview12_external_rebuilder import LOCK
from test_android_preview12_separate_toolchain_inputs import modeled_preparation


def canonical_file(path, raw=b'{"TEST_ONLY":true}\n'):
    path.write_bytes(raw)
    path.chmod(0o444)
    return path


@pytest.fixture
def custody(tmp_path):
    originals, private = tmp_path / "artifacts", tmp_path / "private"
    originals.mkdir(mode=0o700)
    private.mkdir(mode=0o700)
    return originals, private


@pytest.mark.parametrize("name", ["source-graph.json", "unsigned.aab.sha256"])
def test_canonical_0444_is_copied_privately_without_changing_original(custody, name):
    originals, private = custody
    source = canonical_file(originals / name)
    before = source.stat()
    with pytest.raises(fleet.RebuilderError, match="owner-bound"):
        fleet._stable_bytes(source, "private input", 1024, owner_only=True)
    fleet._copy_canonical_output(source, private / name, "canonical metadata", 1024)
    copied = private / name
    assert copied.read_bytes() == source.read_bytes()
    assert stat.S_IMODE(copied.stat().st_mode) == 0o600
    assert copied.stat().st_uid == os.getuid() and copied.stat().st_nlink == 1
    assert copied.stat().st_ino != before.st_ino
    assert fleet._file_identity(source.stat()) == fleet._file_identity(before)
    assert source.stat().st_nlink == before.st_nlink == 1
    assert fleet._stable_bytes(copied, "private input", 1024, owner_only=True) == source.read_bytes()


@pytest.mark.parametrize("mode", [0o600, 0o644, 0o664, 0o666, 0o400, 0o4444, 0o544])
@pytest.mark.parametrize("name", ["source-graph.json", "unsigned.aab.sha256"])
def test_noncanonical_modes_are_not_permission_relaxations(custody, name, mode):
    originals, private = custody
    source = canonical_file(originals / name)
    source.chmod(mode)
    with pytest.raises(fleet.RebuilderError):
        fleet._copy_canonical_output(source, private / name, "canonical metadata", 1024)
    assert not (private / name).exists()


@pytest.mark.parametrize("attack", ["symlink", "ancestor-symlink", "hardlink", "fifo", "directory",
                                    "empty", "oversize", "writable-parent", "relative"])
def test_unsafe_originals_fail_before_private_copy(custody, attack):
    originals, private = custody
    source = canonical_file(originals / "source-graph.json")
    if attack == "symlink":
        other = originals / "real.json"
        source.rename(other)
        source.symlink_to(other)
    elif attack == "ancestor-symlink":
        alias = originals.parent / "alias"
        alias.symlink_to(originals, target_is_directory=True)
        source = alias / source.name
    elif attack == "hardlink":
        (originals / "alias.json").hardlink_to(source)
    elif attack in {"fifo", "directory", "empty", "oversize"}:
        source.unlink()
        if attack == "fifo":
            os.mkfifo(source, 0o444)
        elif attack == "directory":
            source.mkdir(mode=0o444)
        else:
            canonical_file(source, b"" if attack == "empty" else b"x" * 1025)
    elif attack == "writable-parent":
        originals.chmod(0o777)
    else:
        source = Path("relative.json")
    with pytest.raises(fleet.RebuilderError):
        fleet._copy_canonical_output(source, private / "copy.json", "canonical metadata", 1024)
    assert not (private / "copy.json").exists()


def test_owner_binding_is_independent_of_read_permissions(custody, monkeypatch):
    originals, private = custody
    source = canonical_file(originals / "source-graph.json")
    # Model the caller identity only; the file's actual stat/descriptor are real.
    monkeypatch.setattr(fleet.os, "getuid", lambda: source.stat().st_uid + 1)
    with pytest.raises(fleet.RebuilderError, match="owned read-only custody"):
        fleet._copy_canonical_output(source, private / source.name, "canonical metadata", 1024)
    assert not (private / source.name).exists()


@pytest.mark.parametrize("attack", ["replace", "bytes", "mode", "hardlink"])
def test_descriptor_capture_rejects_midread_drift(custody, monkeypatch, attack):
    originals, private = custody
    source = canonical_file(originals / "source-graph.json")
    original_read = fleet.os.read
    changed = False
    def read(descriptor, count):
        nonlocal changed
        raw = original_read(descriptor, count)
        if not changed:
            changed = True
            if attack == "replace":
                source.rename(originals / "retained.json")
                canonical_file(source, raw)
            elif attack == "bytes":
                source.chmod(0o600)
                source.write_bytes(b"x" * len(raw))
                source.chmod(0o444)
            elif attack == "mode":
                source.chmod(0o644)
            else:
                (originals / "alias.json").hardlink_to(source)
        return raw
    monkeypatch.setattr(fleet.os, "read", read)
    with pytest.raises(fleet.RebuilderError):
        fleet._copy_canonical_output(source, private / source.name, "canonical metadata", 1024)
    assert changed and not (private / source.name).exists()


def test_descriptor_open_rejects_raced_symlink(custody, monkeypatch):
    originals, private = custody
    source = canonical_file(originals / "source-graph.json")
    original_open = fleet.os.open
    def opened(path, *args, **kwargs):
        if path == source:
            source.rename(originals / "retained.json")
            source.symlink_to(originals / "retained.json")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(fleet.os, "open", opened)
    with pytest.raises(fleet.RebuilderError):
        fleet._copy_canonical_output(source, private / source.name, "canonical metadata", 1024)
    assert not (private / source.name).exists()


@pytest.mark.parametrize("attack", ["source-parent", "copied-bytes", "copied-mode", "copied-hardlink"])
def test_postwrite_fences_reject_drift(custody, monkeypatch, attack):
    originals, private = custody
    source = canonical_file(originals / "source-graph.json")
    original_write = fleet._write_exclusive
    def write(path, raw):
        original_write(path, raw)
        if attack == "source-parent":
            retained = originals.with_name("retained")
            originals.rename(retained)
            originals.mkdir(mode=0o700)
            (retained / source.name).rename(source)  # Same source inode, different parent.
        elif attack == "copied-bytes":
            path.write_bytes(b"x" * len(raw))
        elif attack == "copied-mode":
            path.chmod(0o644)
        else:
            (private / "alias.json").hardlink_to(path)
    monkeypatch.setattr(fleet, "_write_exclusive", write)
    with pytest.raises(fleet.RebuilderError):
        fleet._copy_canonical_output(source, private / source.name, "canonical metadata", 1024)


@pytest.mark.parametrize("symlink", [False, True])
def test_private_destination_is_exclusive(custody, symlink):
    originals, private = custody
    source = canonical_file(originals / "source-graph.json")
    target = private / source.name
    if symlink:
        target.symlink_to(source)
    else:
        target.write_bytes(b"retained")
    with pytest.raises(fleet.RebuilderError):
        fleet._copy_canonical_output(source, target, "canonical metadata", 1024)
    assert target.is_symlink() if symlink else target.read_bytes() == b"retained"


@pytest.mark.parametrize("which", ["aab", "graph", "missing"])
def test_rebuilt_sidecar_claim_drift_prevents_handoff(modeled_preparation, which):
    case = modeled_preparation
    original = case.consumer._sidecar_claims
    def claims(sidecar, aab, graph):
        value = original(sidecar, aab, graph)
        if "rebuild-model" in case.events:
            if which == "missing":
                return {}
            value[f"artifacts/{(aab if which == 'aab' else graph).name}"] = "0" * 64
        return value
    case.consumer._sidecar_claims = claims
    with pytest.raises(fleet.RebuilderError, match="sidecar differs"):
        fleet.prepare_rebuild_handoff(**case.args, runner=case.runner)
    assert "rebuild-model" in case.events and not case.args["output_dir"].exists()


def test_exact_android_parser_accepts_private_copies_not_canonical_public_modes(custody):
    selected = os.environ.get("CHUMMER_ANDROID_CURRENT_ROOT")
    if not selected:
        pytest.skip("requires the exact qualified Android checkout; no modeled replacement")
    android = fleet.validate_android_consumer(Path(selected), json.loads(LOCK.read_bytes()))
    originals, private = custody
    aab = canonical_file(originals / f"chummer-android-{fleet.VERSION_NAME}-unsigned.aab", b"TEST_ONLY not an AAB")
    graph = canonical_file(originals / f"chummer-android-{fleet.VERSION_NAME}-source-graph.json")
    raw = (f"{hashlib.sha256(aab.read_bytes()).hexdigest()}  artifacts/{aab.name}\n"
           f"{hashlib.sha256(graph.read_bytes()).hexdigest()}  artifacts/{graph.name}\n").encode()
    sidecar = canonical_file(originals / (aab.name + ".sha256"), raw)
    with pytest.raises(ValueError):
        android._sidecar_claims(sidecar, aab, graph)
    for source in (graph, sidecar):
        fleet._copy_canonical_output(source, private / source.name, "canonical metadata", 1024)
    claims = android._sidecar_claims(private / sidecar.name, aab, private / graph.name)
    assert claims[f"artifacts/{aab.name}"] == hashlib.sha256(aab.read_bytes()).hexdigest()
    assert claims[f"artifacts/{graph.name}"] == hashlib.sha256(graph.read_bytes()).hexdigest()
    assert claims["rawSha256"] == hashlib.sha256(raw).hexdigest()
    (private / sidecar.name).write_bytes(raw.replace(b"artifacts/", b"wrong/", 1))
    with pytest.raises(ValueError, match="names are not exact"):
        android._sidecar_claims(private / sidecar.name, aab, private / graph.name)
