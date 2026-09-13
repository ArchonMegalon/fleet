"""Copy one terminal builder's exact local handoff into controller custody.

The owner independently admits this code, RuntimePolicy, Docker/lock pins and
all mount contents. The builder must not access the controller or daemon. The
selected writable bind starts empty and private, owned by the builder UID/GID;
the controller needs OS permission to read that owner's private output. This
module never changes source ownership or permissions and never retries a build.

Copy and drift checks stream bounded chunks. The existing local validator still
uses its bounded in-memory AAB reader. These ordinary copied facts are neither
continuous custody nor proof that an authenticated job emitted the bytes. A
later real root-owned read-only namespace must construct PreservedRebuildHandoff
unchanged. No signing, workflow authentication or publication authority is given.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from scripts import android_artifact_origin as origin
from scripts import android_container_runtime as runtime
from scripts import android_isolated_builder as builder
from scripts import android_preview12_external_rebuilder as fleet


MANIFEST = "FLEET_ANDROID_PREVIEW12_REBUILD_HANDOFF.generated.json"
COPY_DIRECTORY = "captured-handoff"
CHUNK_BYTES = 64 * 1024


class HandoffCaptureError(RuntimeError):
    """Constant codes only; partial evidence stays in the private operation."""


@dataclass(frozen=True, slots=True)
class BuilderHandoffCapture:
    execution: builder.BuilderExecution
    directory: Path
    lock_sha256: str
    artifact_closure_sha256: str
    file_sha256: tuple[tuple[str, str], ...]


def _require(condition, code):
    if not condition:
        raise HandoffCaptureError(code)


def _identity(value):
    return fleet.PreservedRebuildHandoff._identity(value)


def _anchor(value):
    return value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid


def _private(value, owner, *, directory=False):
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    _require((value.st_uid, value.st_gid) == owner, "capture-entry-owner")
    _require(kind(value.st_mode) and not stat.S_IMODE(value.st_mode) & 0o077
             and (directory or value.st_nlink == 1), "capture-entry-custody")


def _directory(path, owner):
    _require(type(path) is type(Path()) and path.is_absolute()
             and path.resolve(strict=True) == path, "capture-directory-path")
    before = path.lstat()
    _private(before, owner, directory=True)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _require(_identity(os.fstat(fd)) == _identity(before), "capture-directory-changed")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _inventory(fd, expected):
    names = set()
    with os.scandir(fd) as entries:
        for entry in entries:
            _require(entry.name in expected and entry.name not in names, "capture-inventory")
            names.add(entry.name)
            _require(len(names) <= len(expected), "capture-inventory")
    _require(names == set(expected), "capture-inventory")


def _limits(lock):
    # Exact existing consumer inventory; VERSION_NAME and lock byte limits stay
    # owned by that consumer. Its real validator remains authoritative.
    json_limit, aab_limit = lock["limits"]["json_bytes"], lock["limits"]["aab_bytes"]
    _require(type(json_limit) is int and 0 < json_limit <= 8 * 1024**2
             and type(aab_limit) is int and 0 < aab_limit <= 512 * 1024**2,
             "capture-input-bounds")
    return {
        MANIFEST: json_limit,
        f"chummer-android-{fleet.VERSION_NAME}-unsigned.aab": aab_limit,
        f"chummer-android-{fleet.VERSION_NAME}-source-graph.json": json_limit,
        f"chummer-android-{fleet.VERSION_NAME}-unsigned.aab.sha256": 64 * 1024,
        "ANDROID_API36_TWO_GREEN_ELIGIBILITY.generated.json": json_limit,
        "ANDROID_API36_TWO_GREEN_RELEASE_APPROVAL.generated.json": json_limit,
        "ANDROID_EXTERNAL_SIGNER_REQUEST.generated.json": json_limit,
    }


def _metadata(fd, names, owner):
    _inventory(fd, names)
    result = {}
    for name in names:
        value = os.stat(name, dir_fd=fd, follow_symlinks=False)
        _private(value, owner)
        _require(0 <= value.st_size <= names[name], "capture-file-bound")
        result[name] = _identity(value)
    return result


def _transfer(source, name, identity, limit, destination=None):
    # NONBLOCK prevents a raced FIFO/device entry from blocking before fstat.
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source)
    output = None
    try:
        _require(_identity(os.fstat(fd)) == identity, "capture-file-changed")
        if destination is not None:
            output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=destination)
        digest, count = hashlib.sha256(), 0
        while True:
            raw = os.read(fd, min(CHUNK_BYTES, limit - count + 1))
            if not raw:
                break
            count += len(raw)
            _require(count <= limit, "capture-file-bound")
            digest.update(raw)
            if output is not None:
                pending = memoryview(raw)
                while pending:
                    written = os.write(output, pending)
                    _require(written > 0, "capture-write-failed")
                    pending = pending[written:]
        _require(_identity(os.fstat(fd)) == identity
                 and _identity(os.stat(name, dir_fd=source, follow_symlinks=False)) == identity,
                 "capture-file-changed")
        if output is not None:
            os.fsync(output)
        return digest.hexdigest()
    finally:
        os.close(fd)
        if output is not None:
            os.close(output)


def _recheck(fd, path, root_identity, metadata, limits, owner, digests):
    _require(_identity(os.fstat(fd)) == root_identity
             and _identity(path.lstat()) == root_identity
             and path.resolve(strict=True) == path, "capture-directory-changed")
    _require(_metadata(fd, limits, owner) == metadata, "capture-file-changed")
    for name, limit in limits.items():
        _require(_transfer(fd, name, metadata[name], limit) == digests[name], "capture-byte-changed")
    _require(_metadata(fd, limits, owner) == metadata
             and _identity(os.fstat(fd)) == root_identity, "capture-file-changed")


def _record(fd, name, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
    output = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=fd)
    with os.fdopen(output, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.fsync(fd)


def _terminal(execution, policy):
    _require(type(execution) is builder.BuilderExecution and execution.container_removed is True,
             "capture-builder-not-terminal")
    created, exited = execution.created, execution.exited
    _require(type(created) is runtime.RuntimeObservation and type(exited) is runtime.RuntimeObservation
             and created.phase == "created" and exited.phase == "exited"
             and re.fullmatch(r"[0-9a-f]{64}", created.container_id)
             and created.container_id == exited.container_id
             and created.configuration_sha256 == exited.configuration_sha256
             and created.policy_sha256 == exited.policy_sha256 == runtime._digest(asdict(policy))
             and created.image_id == exited.image_id == policy.image_id
             and created.socket_identity == exited.socket_identity, "capture-builder-not-terminal")


def _validate_copy(path, lock, lock_sha256, digests):
    handoff, paths = fleet.validate_local_rebuild_handoff(path, lock)
    request, graph = fleet.validate_external_request(
        paths["externalSignerRequest"], paths["sourceGraph"], lock["limits"]["json_bytes"])
    android = fleet.validate_source_graph(graph)["chummer-android"]
    bindings = handoff["bindings"]
    _require(bindings["lockSha256"] == lock_sha256
             and all(bindings[f"source{field.title()}"] == android[field]
                     == lock["android_authority"][field] for field in ("commit", "tree"))
             and request["buildSidecar"]["sha256"] == digests[paths["buildSidecar"].name],
             "capture-handoff-binding")


def run_builder_capture_handoff(policy: runtime.RuntimePolicy, docker: origin.PinnedFile,
                               operation_directory: Path, lock: origin.PinnedFile,
                               output_bind_target: str, handoff_child_name: str) -> BuilderHandoffCapture:
    """Run once, copy after successful removal, and validate ordinary local bytes.

    Partial copies and constant-code failure receipts are retained. Reusing an
    operation fails before execution. The source stays untouched; later changes
    to it do not change the controller's detached copy or confer custody proof.
    """
    root_fd = source_fd = operation_fd = destination_fd = None
    stage = "admission"
    try:
        _require(type(policy) is runtime.RuntimePolicy and type(lock) is origin.PinnedFile
                 and type(docker) is origin.PinnedFile, "capture-admission")
        policy.__post_init__()
        lock.__post_init__()
        _require(policy.process_role == "builder", "capture-builder-role")
        _require(type(handoff_child_name) is str
                 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", handoff_child_name),
                 "capture-child-name")
        _require(type(operation_directory) is type(Path()) and operation_directory.is_absolute()
                 and not os.path.lexists(operation_directory), "capture-operation-path")
        selected = [mount for mount in policy.binds if mount.target == output_bind_target]
        _require(len(selected) == 1 and not selected[0].read_only, "capture-output-bind")
        for mount in policy.binds:
            source = Path(mount.source)
            _require(source != operation_directory and source not in operation_directory.parents
                     and operation_directory not in source.parents, "capture-destination-overlap")
        owner = tuple(int(part) for part in policy.user.split(":"))
        controller = os.getuid(), os.getgid()
        root = Path(selected[0].source)
        root_fd = _directory(root, owner)
        _inventory(root_fd, ())
        initial_root = _identity(os.fstat(root_fd))
        root_anchor = _anchor(os.fstat(root_fd))
        pinned_lock = origin._capture(lock, 1024 * 1024)
        lock_value = fleet._strict_json(pinned_lock.raw, "capture lock")
        _require(lock_value.get("contract_name") == fleet.LOCK_CONTRACT, "capture-lock-contract")
        limits = _limits(lock_value)
        stage = "builder"
        _require(_identity(root.lstat()) == initial_root
                 and _identity(os.fstat(root_fd)) == initial_root, "capture-output-root-changed")
        _inventory(root_fd, ())
        try:
            execution = builder.run_builder(policy, docker, operation_directory)
        finally:
            pinned_lock.recheck()
        _terminal(execution, policy)
        operation_fd = _directory(operation_directory, controller)
        _record(operation_fd, "capture-intent.json", {
            "containerId": execution.exited.container_id, "handoffChild": handoff_child_name,
            "lockSha256": lock.sha256, "signingPerformed": False,
        })
        stage = "source-admission"
        _require(_anchor(os.fstat(root_fd)) == root_anchor
                 and _anchor(root.lstat()) == root_anchor and root.resolve(strict=True) == root,
                 "capture-output-root-changed")
        _inventory(root_fd, {handoff_child_name})
        source_path = root / handoff_child_name
        source_fd = os.open(handoff_child_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root_fd)
        _private(os.fstat(source_fd), owner, directory=True)
        source_identity = _identity(os.fstat(source_fd))
        source_metadata = _metadata(source_fd, limits, owner)
        os.mkdir(COPY_DIRECTORY, mode=0o700, dir_fd=operation_fd)
        os.fsync(operation_fd)
        destination = operation_directory / COPY_DIRECTORY
        destination_fd = _directory(destination, controller)
        stage = "copy"
        digests = {name: _transfer(source_fd, name, source_metadata[name], limit, destination_fd)
                   for name, limit in limits.items()}
        os.fsync(destination_fd)
        destination_identity = _identity(os.fstat(destination_fd))
        destination_metadata = _metadata(destination_fd, limits, controller)
        _recheck(source_fd, source_path, source_identity, source_metadata, limits, owner, digests)
        _recheck(destination_fd, destination, destination_identity, destination_metadata,
                 limits, controller, digests)
        stage = "validation"
        _validate_copy(destination, lock_value, lock.sha256, digests)
        _recheck(source_fd, source_path, source_identity, source_metadata, limits, owner, digests)
        _recheck(destination_fd, destination, destination_identity, destination_metadata,
                 limits, controller, digests)
        _require(_anchor(root.lstat()) == root_anchor, "capture-output-root-changed")
        _inventory(root_fd, {handoff_child_name})
        pinned_lock.recheck()
        _record(operation_fd, "capture-complete.json", {
            "containerId": execution.exited.container_id, "artifactClosureSha256": digests[MANIFEST],
            "lockSha256": lock.sha256, "fileSha256": digests,
            "signingPerformed": False, "publicationAuthorized": False,
            "continuousCustodyProven": False, "authenticatedJob": False,
        })
        return BuilderHandoffCapture(execution, destination, lock.sha256, digests[MANIFEST],
                                     tuple(sorted(digests.items())))
    except (HandoffCaptureError, builder.BuilderExecutionError, origin.OriginError,
            runtime.RuntimeObservationError, fleet.RebuilderError, RuntimeError, OSError, ValueError,
            KeyError, TypeError, AttributeError, OverflowError, RecursionError):
        if operation_fd is not None:
            try:
                _record(operation_fd, "capture-failed.json", {
                    "stage": stage, "status": "no-usable-capture", "signingPerformed": False,
                    "publicationAuthorized": False,
                })
            except OSError:
                pass
        raise HandoffCaptureError("builder-handoff-failed-see-private-operation") from None
    finally:
        for fd in (destination_fd, operation_fd, source_fd, root_fd):
            if fd is not None:
                os.close(fd)
