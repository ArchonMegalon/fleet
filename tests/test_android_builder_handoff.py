"""Real files, copy/drift checks and consumer validation; modeled builder only.

These fixtures are not Android builds, preserved mounts or authenticated jobs.
No test runs Docker, changes ownership, invokes signing or models RO custody.
"""
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_container_runtime as runtime
from scripts import android_isolated_builder as builder
from scripts import android_preview12_external_rebuilder as fleet
from test_android_preview12_preserved_handoff import handoff_inputs, rewrite


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def model(tmp_path, monkeypatch):
    if os.getuid() == 0 or os.getgid() == 0:
        pytest.skip("real builder-owned fixtures require a nonroot UID/GID; ownership is never mocked")
    tmp_path.chmod(0o700)
    inputs = tmp_path / "fixture"
    inputs.mkdir(mode=0o700)
    lock, directory, paths, manifest = handoff_inputs(fleet, inputs)
    output = tmp_path / "output"
    output.mkdir(mode=0o700)
    tool = tmp_path / "docker-not-executed"
    tool.write_bytes(b"not an executable: only the builder is modeled\n")
    tool.chmod(0o600)
    policy = runtime.RuntimePolicy(
        "sha256:" + "a" * 64, "registry.example/builder@sha256:" + "b" * 64,
        f"{os.getuid()}:{os.getgid()}", "/", ("/bin/true",), (), (),
        runtime.ResourceLimits(64 * 1024**2, 250000000, 32),
        binds=(runtime.BindMount(str(output), "/output", False),), maximum_runtime_seconds=10,
    )
    value = SimpleNamespace(policy=policy, lock=origin.PinnedFile(lock, sha(lock.read_bytes())),
        docker=origin.PinnedFile(tool, sha(tool.read_bytes())), output=output,
        operation=tmp_path / "operation", fixture=directory, paths=paths, manifest=manifest,
        expected={path.name: path.read_bytes() for path in directory.iterdir()},
        calls=[], fail=False, result_change=None, emitted=None, child="handoff")

    def execute(selected, pinned, operation):
        value.calls.append("builder")
        assert selected is value.policy and pinned is value.docker and operation == value.operation
        assert list(output.iterdir()) == [] and not operation.exists()
        builder._operation(operation)
        if value.fail:
            raise builder.BuilderExecutionError("PRIVATE builder diagnostic")
        # Model terminal output emission with a real directory move. The fixture
        # was built before invocation and never pretends to be job provenance.
        directory.rename(output / value.child)
        if value.emitted:
            value.emitted(output / value.child)
        observation = runtime.RuntimeObservation(
            "c" * 64, policy.image_id, sha(policy.requested_image.encode()),
            runtime._digest(asdict(selected)), "d" * 64,
            "created", "2026-09-13T00:00:00Z", runtime.ZERO_TIME, runtime.ZERO_TIME,
            "2026-09-13T00:00:01Z", (1, 2, 3), "e" * 64)
        result = builder.BuilderExecution(observation, replace(observation, phase="exited"), True)
        if value.result_change:
            result = value.result_change(result)
        return result

    monkeypatch.setattr(builder, "run_builder", execute)
    return value


def run(model):
    return capture.run_builder_capture_handoff(model.policy, model.docker, model.operation,
                                               model.lock, "/output", model.child)


def test_real_copy_validation_and_detached_bytes_without_preserved_or_release_claim(model):
    result = run(model)
    assert type(result) is capture.BuilderHandoffCapture and model.calls == ["builder"]
    assert result.directory == model.operation / capture.COPY_DIRECTORY
    assert {path.name: path.read_bytes() for path in result.directory.iterdir()} == model.expected
    assert dict(result.file_sha256) == {name: sha(raw) for name, raw in model.expected.items()}
    assert result.artifact_closure_sha256 == sha(model.expected[capture.MANIFEST])
    assert result.lock_sha256 == model.lock.sha256
    for path in result.directory.iterdir():
        assert path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o777 == 0o600
    assert result.directory.stat().st_mode & 0o777 == 0o700
    lock = json.loads(model.lock.path.read_bytes())
    handoff, _ = fleet.validate_local_rebuild_handoff(result.directory, lock)
    assert handoff["eligibleForProtectedSigner"] is False and not handoff["signingPerformed"]
    assert not isinstance(result, fleet.PreservedRebuildHandoff)
    assert not hasattr(result, "provenance")
    with pytest.raises(fleet.RebuilderError):
        fleet.PreservedRebuildHandoff(model.lock.path, result.directory)
    source = model.output / model.child / capture.MANIFEST
    source.write_bytes(b"changed after detached copy\n")
    assert (result.directory / capture.MANIFEST).read_bytes() == model.expected[capture.MANIFEST]
    assert json.loads((model.operation / "capture-complete.json").read_bytes())["authenticatedJob"] is False
    assert not (model.operation / "capture-failed.json").exists()


def test_replay_fails_before_second_builder_or_capture(model):
    run(model)
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert model.calls == ["builder"]


@pytest.mark.parametrize("fault", ["builder-failed", "not-removed", "wrong-phase", "wrong-policy", "wrong-cid"])
def test_no_capture_from_failed_or_nonterminal_execution(model, fault):
    if fault == "builder-failed":
        model.fail = True
    elif fault == "not-removed":
        model.result_change = lambda result: replace(result, container_removed=False)
    elif fault == "wrong-phase":
        model.result_change = lambda result: replace(result, exited=replace(result.exited, phase="running"))
    elif fault == "wrong-policy":
        model.result_change = lambda result: replace(result, exited=replace(result.exited, policy_sha256="0" * 64))
    else:
        model.result_change = lambda result: replace(result, exited=replace(result.exited, container_id="f" * 64))
    with pytest.raises(capture.HandoffCaptureError) as error:
        run(model)
    assert "PRIVATE" not in str(error.value)
    assert not (model.operation / capture.COPY_DIRECTORY).exists()
    assert not (model.operation / "capture-complete.json").exists()
    assert model.calls == ["builder"]


@pytest.mark.parametrize("fault", ["foreign-uid", "foreign-gid", "public-root", "nonempty", "readonly-bind",
                                  "missing-bind", "overlap", "child-traversal", "existing-operation"])
def test_bad_initial_admission_never_runs_builder(model, fault):
    if fault == "foreign-uid":
        model.policy = replace(model.policy, user=f"{os.getuid() + 1}:{os.getgid()}")
    elif fault == "foreign-gid":
        model.policy = replace(model.policy, user=f"{os.getuid()}:{os.getgid() + 1}")
    elif fault == "public-root":
        model.output.chmod(0o755)
    elif fault == "nonempty":
        (model.output / "existing").write_bytes(b"existing")
    elif fault == "readonly-bind":
        model.policy = replace(model.policy, binds=(replace(model.policy.binds[0], read_only=True),))
    elif fault == "missing-bind":
        model.policy = replace(model.policy, binds=())
    elif fault == "overlap":
        model.operation = model.output / "operation"
    elif fault == "child-traversal":
        model.child = "../handoff"
    else:
        model.operation.mkdir(mode=0o700)
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert model.calls == []


def test_builder_ownership_is_checked_against_actual_metadata_not_controller_identity(model):
    metadata = model.output.stat()
    capture._private(metadata, (metadata.st_uid, metadata.st_gid), directory=True)
    with pytest.raises(capture.HandoffCaptureError, match="capture-entry-owner"):
        capture._private(metadata, (metadata.st_uid + 1, metadata.st_gid), directory=True)
    metadata = model.manifest.stat()
    with pytest.raises(capture.HandoffCaptureError, match="capture-entry-owner"):
        capture._private(metadata, (metadata.st_uid + 1, metadata.st_gid))


def test_cyclic_initial_output_root_is_sanitized_before_builder(model):
    loop = model.output.with_name("PRIVATE-loop-path")
    model.output.rmdir()  # This fixture's still-empty output root only.
    model.output.symlink_to(loop, target_is_directory=True)
    loop.symlink_to(model.output, target_is_directory=True)
    with pytest.raises(capture.HandoffCaptureError) as error:
        run(model)
    assert str(error.value) == "builder-handoff-failed-see-private-operation"
    assert model.calls == [] and not model.operation.exists()


@pytest.mark.parametrize("fault", ["extra", "missing", "symlink", "hardlink", "fifo", "directory",
                                  "source-root-symlink", "public-child", "extra-root"])
def test_malicious_or_changed_inventory_rejected_before_copy(model, fault):
    def change(directory):
        target = directory / capture.MANIFEST
        if fault == "extra":
            (directory / "extra").write_bytes(b"unselected")
        elif fault == "extra-root":
            (directory.parent / "unexpected").write_bytes(b"unselected")
        elif fault == "public-child":
            directory.chmod(0o755)
        elif fault == "source-root-symlink":
            relocated = model.fixture.parent / "relocated"
            directory.rename(relocated)
            directory.symlink_to(relocated, target_is_directory=True)
        elif fault == "missing":
            target.unlink()
        elif fault == "hardlink":
            os.link(target, model.fixture.parent / "alias")
        else:
            target.unlink()
            if fault == "symlink":
                target.symlink_to(model.lock.path)
            elif fault == "fifo":
                os.mkfifo(target, 0o600)
            else:
                target.mkdir(mode=0o700)
    model.emitted = change
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert not (model.operation / capture.COPY_DIRECTORY).exists()
    if fault in {"source-root-symlink", "hardlink"}:
        assert {path.name for path in model.output.iterdir()} == {model.child}
    failed = json.loads((model.operation / "capture-failed.json").read_bytes())
    assert failed["stage"] == "source-admission" and failed["status"] == "no-usable-capture"


@pytest.mark.parametrize("fault", ["lock-bytes", "lock-inode", "lock-binding", "source-binding", "sidecar-binding",
                                  "unsafe-output-name", "malformed-request"])
def test_existing_consumer_and_explicit_lock_source_sidecar_bindings_are_real(model, fault):
    def change(directory):
        manifest = directory / capture.MANIFEST
        if fault == "lock-bytes":
            model.lock.path.write_bytes(model.lock.path.read_bytes() + b" ")
        elif fault == "lock-inode":
            raw = model.lock.path.read_bytes()
            model.lock.path.unlink()
            model.lock.path.write_bytes(raw)
            model.lock.path.chmod(0o600)
        elif fault == "lock-binding":
            rewrite(manifest, lambda value: value["bindings"].update(lockSha256="0" * 64))
        elif fault == "source-binding":
            rewrite(manifest, lambda value: value["bindings"].update(sourceCommit="0" * 40))
        elif fault == "unsafe-output-name":
            rewrite(manifest, lambda value: value["outputs"].update(unsignedAab="../outside.aab"))
        elif fault == "malformed-request":
            request = directory / model.paths["externalSignerRequest"].name
            rewrite(request, lambda value: value.update(expectedUploadCertificateSha256=None))
        else:
            (directory / model.paths["buildSidecar"].name).write_bytes(b"sidecar changed\n")
    model.emitted = change
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert not (model.operation / "capture-complete.json").exists()


@pytest.mark.parametrize("field,value", [("aab_bytes", 0), ("aab_bytes", True),
                                       ("aab_bytes", 512 * 1024**2 + 1), ("json_bytes", 8 * 1024**2 + 1)])
def test_consumer_bounds_rejected_before_builder(model, field, value):
    rewrite(model.lock.path, lambda lock: lock["limits"].update({field: value}))
    model.lock = replace(model.lock, sha256=sha(model.lock.path.read_bytes()))
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert model.calls == []


def test_oversized_payload_rejected_before_copy(model):
    def enlarge(directory):
        path = directory / model.paths["buildSidecar"].name
        with path.open("r+b") as stream:
            stream.truncate(64 * 1024 + 1)
    model.emitted = enlarge
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert not (model.operation / capture.COPY_DIRECTORY).exists()


@pytest.mark.parametrize("fault", ["source-bytes", "source-inode", "source-extra", "copied-bytes", "lock-bytes"])
def test_drift_during_actual_validation_never_returns_capture(model, monkeypatch, fault):
    original = fleet.validate_local_rebuild_handoff
    def validate(directory, lock):
        result = original(directory, lock)
        source = model.output / model.child / capture.MANIFEST
        if fault == "source-bytes":
            source.write_bytes(source.read_bytes() + b" ")
        elif fault == "source-inode":
            raw = source.read_bytes()
            source.unlink()
            source.write_bytes(raw)
            source.chmod(0o600)
        elif fault == "source-extra":
            (source.parent / "extra").write_bytes(b"drift")
        elif fault == "copied-bytes":
            (directory / capture.MANIFEST).write_bytes(b"copied bytes changed")
        else:
            model.lock.path.write_bytes(model.lock.path.read_bytes() + b" ")
        return result
    monkeypatch.setattr(fleet, "validate_local_rebuild_handoff", validate)
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert (model.operation / capture.COPY_DIRECTORY).exists()  # Retain partial diagnostics.
    assert not (model.operation / "capture-complete.json").exists()
    assert json.loads((model.operation / "capture-failed.json").read_bytes())["stage"] == "validation"


def test_transfer_uses_bounded_chunks_and_detects_same_byte_replacement(model, monkeypatch):
    original_read, original_transfer = os.read, capture._transfer
    observed = []
    def read(fd, count):
        observed.append(count)
        return original_read(fd, count)
    def transfer(source, name, identity, limit, destination=None):
        digest = original_transfer(source, name, identity, limit, destination)
        if destination is not None and name == capture.MANIFEST:
            target = model.output / model.child / name
            raw = target.read_bytes()
            target.unlink()
            target.write_bytes(raw)
            target.chmod(0o600)
        return digest
    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(capture, "_transfer", transfer)
    with pytest.raises(capture.HandoffCaptureError):
        run(model)
    assert observed and max(observed) <= capture.CHUNK_BYTES
    assert not (model.operation / "capture-complete.json").exists()


def test_real_multichunk_transfer_preserves_bytes_with_short_writes(tmp_path, monkeypatch):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.mkdir(mode=0o700)
    destination.mkdir(mode=0o700)
    payload = bytes(range(256)) * (capture.CHUNK_BYTES // 256 * 2) + b"last short chunk"
    leaf = source / "payload.bin"
    leaf.write_bytes(payload)
    leaf.chmod(0o600)
    read_sizes, write_sizes = [], []
    original_read, original_write = os.read, os.write
    def read(fd, count):
        assert 0 < count <= capture.CHUNK_BYTES
        raw = original_read(fd, count)
        if raw:
            read_sizes.append(len(raw))
        return raw
    def short_write(fd, raw):
        written = original_write(fd, raw[:max(1, len(raw) // 3)])
        write_sizes.append(written)
        return written
    monkeypatch.setattr(os, "read", read)
    monkeypatch.setattr(os, "write", short_write)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    source_fd, destination_fd = os.open(source, flags), os.open(destination, flags)
    try:
        digest = capture._transfer(source_fd, leaf.name, capture._identity(leaf.stat()),
                                   len(payload), destination_fd)
    finally:
        os.close(source_fd)
        os.close(destination_fd)
    assert len(read_sizes) >= 3 and sum(read_sizes) == len(payload)
    assert len(write_sizes) > len(read_sizes) and sum(write_sizes) == len(payload)
    assert digest == sha(payload) and (destination / leaf.name).read_bytes() == payload
    assert leaf.read_bytes() == payload
