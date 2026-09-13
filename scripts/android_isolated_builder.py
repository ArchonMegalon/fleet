"""Controller-owned, key-free Docker builder execution; not signing authority.

The owner must independently admit this module, its imports, Docker binary,
root daemon, image and complete mount contents before calling it. In particular,
a clean environment is not proof that admitted files contain no credentials.
The candidate must not supply RuntimePolicy or access the daemon/controller.

Unlike the read-only observer, this module creates and starts one container.
An exclusive private operation directory records intent before creation and CID
before start. No call retries a create or start. Reusing that directory fails
before Docker access. Failed operations retain their private evidence; uncertain
create outcomes must be reconciled by their recorded name, never recreated.

Successful output binds real CREATED/EXITED observations and removal. It is not
continuous custody, artifact capture/emission, workflow identity, release
eligibility or AuthenticatedRebuildHandoff. Writable output binds survive removal;
the later controller capture step must validate and preserve their exact bytes.
The controller must stay alive for timeout cleanup; this is not a crash watchdog.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import secrets
import stat

from scripts import android_artifact_origin as origin
from scripts import android_container_runtime as runtime


class BuilderExecutionError(RuntimeError):
    """Content-free error codes; retain the private operation directory."""


@dataclass(frozen=True, slots=True)
class BuilderExecution:
    created: runtime.RuntimeObservation
    exited: runtime.RuntimeObservation
    container_removed: bool


def _require(value, code):
    if not value:
        raise BuilderExecutionError(code)


def _sync(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _record(directory: Path, name: str, value: object) -> None:
    raw = json.dumps(value, sort_keys=True, allow_nan=False, indent=2).encode() + b"\n"
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _sync(directory)


def _operation(directory: Path) -> None:
    _require(type(directory) is type(Path()) and directory.is_absolute(), "operation-path")
    parent = directory.parent
    value = parent.lstat()
    _require(parent.resolve(strict=True) == parent and stat.S_ISDIR(value.st_mode)
             and value.st_uid == os.getuid() and not value.st_mode & 0o077, "operation-parent")
    # mkdir is the exclusive transaction boundary, including broken symlinks.
    directory.mkdir(mode=0o700)
    _sync(parent)
    (directory / "docker-config").mkdir(mode=0o700)
    _sync(directory)


def _create_arguments(policy: runtime.RuntimePolicy, name: str) -> list[str]:
    resources = policy.resources
    whole, fraction = divmod(resources.nano_cpus, 10**9)
    args = ["create", "--pull", "never", "--name", name,
            "--network", "none", "--user", policy.user, "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--read-only", "--restart", "no",
            "--cgroupns", "private", "--ipc", "private", "--runtime", "runc",
            "--memory", str(resources.memory_bytes), "--memory-swap", str(resources.memory_bytes),
            "--memory-reservation", str(resources.memory_reservation),
            "--shm-size", str(resources.shm_size), "--cpus", f"{whole}.{fraction:09d}",
            "--pids-limit", str(resources.pids_limit), "--log-driver", "none",
            "--workdir", policy.workdir, "--entrypoint", policy.entrypoint[0]]
    for attached, channel in ((policy.attach_stdout, "stdout"), (policy.attach_stderr, "stderr")):
        if attached:
            args += ["--attach", channel]
    for item in policy.environment:
        args += ["--env", item]
    for key, value in policy.labels:
        args += ["--label", key + "=" + value]
    for mount in policy.binds:
        args += ["--volume", f"{mount.source}:{mount.target}:{'ro' if mount.read_only else 'rw'},rprivate"]
    for mount in policy.tmpfs:
        args += ["--tmpfs", mount.target + ":" + mount.options]
    return args + [policy.requested_image, *policy.command]


def run_builder(policy: runtime.RuntimePolicy, docker: origin.PinnedFile,
                operation_directory: Path) -> BuilderExecution:
    """Create/start/wait exactly once using independently admitted inputs.

    No image pull, Docker context discovery, caller environment, shell command
    interpolation, credential callback or artifact-provided executable is used
    by the host controller. The admitted image's command executes only inside
    the nonroot network-none container after full CREATED validation.
    """
    _require(type(policy) is runtime.RuntimePolicy and type(docker) is origin.PinnedFile,
             "builder-admission")
    try:
        policy.__post_init__()
        docker.__post_init__()
        _require(policy.process_role == "builder" and len(policy.entrypoint) == 1,
                 "builder-role-or-entrypoint")
        # docker create defaults to attaching both output streams when neither
        # --attach is supplied; there is no CLI spelling for both disabled.
        _require(policy.attach_stdout or policy.attach_stderr, "builder-attachment")
        _require(type(operation_directory) is type(Path()) and operation_directory.is_absolute(),
                 "operation-path")
        for mount in policy.binds:
            source = Path(mount.source)
            _require(source != operation_directory and source not in operation_directory.parents
                     and operation_directory not in source.parents, "operation-mount-overlap")
        # Reject absent bind sources before Docker --volume could create them.
        mounts = runtime._mount_sources(policy)
        tool = origin._capture(docker, 128 * 1024**2, executable=True)
        daemon = runtime._socket_identity()
        _operation(operation_directory)
    except (OSError, ValueError, origin.OriginError, runtime.RuntimeObservationError):
        raise BuilderExecutionError("builder-admission") from None

    def command(arguments, seconds=30, *, cleanup=False):
        tool.recheck()
        _require(runtime._socket_identity() == daemon, "builder-daemon-changed")
        if not cleanup:
            _require(runtime._mount_sources(policy) == mounts, "builder-mount-changed")
        try:
            return origin._run(
                [str(docker.path), "--config", str(operation_directory / "docker-config"),
                 "--host", "unix:///run/docker.sock", *arguments],
                operation_directory, seconds, 4096, 65536,
            )
        finally:
            tool.recheck()
            _require(runtime._socket_identity() == daemon, "builder-daemon-changed")
            if not cleanup:
                _require(runtime._mount_sources(policy) == mounts, "builder-mount-changed")

    name = "chummer-builder-" + secrets.token_hex(16)
    cid = None
    stage = "intent"
    try:
        _record(operation_directory, "intent.json", {
            "containerName": name, "policy": asdict(policy), "dockerSha256": docker.sha256,
            "artifactCapturePerformed": False, "signingPerformed": False,
        })
        stage = "create"
        raw = command(_create_arguments(policy, name))
        _require(re.fullmatch(rb"[0-9a-f]{64}\n", raw), "builder-create-response")
        cid = raw.decode("ascii").strip()
        # Persist identity before inspecting or starting. Lost acknowledgement
        # never licenses a second create/start call.
        _record(operation_directory, "container.json", {"containerName": name, "containerId": cid})
        stage = "observe-created"
        created = runtime.observe_created(cid, policy)
        _require(created.socket_identity[:-1] == daemon, "builder-daemon-changed")
        _record(operation_directory, "created.json", asdict(created))
        stage = "start"
        _require(command(["start", cid]) == (cid + "\n").encode(), "builder-start-response")
        stage = "wait"
        _require(command(["wait", cid], policy.maximum_runtime_seconds) == b"0\n", "builder-exit")
        stage = "observe-exited"
        exited = runtime.observe_exited(cid, policy, created)
        _record(operation_directory, "exited.json", asdict(exited))
        stage = "remove"
        _require(command(["rm", cid]) == (cid + "\n").encode(), "builder-remove-response")
        stage = "complete"
        _record(operation_directory, "complete.json", {
            "containerId": cid, "containerRemoved": True,
            "configurationSha256": exited.configuration_sha256,
            "artifactCapturePerformed": False, "signingPerformed": False,
        })
        return BuilderExecution(created, exited, True)
    except (BuilderExecutionError, origin.OriginError, runtime.RuntimeObservationError, OSError, ValueError):
        # Only a CID obtained from this operation's one create can be stopped.
        # A lost create response leaves name-based reconciliation, never a retry.
        cleanup = "not-attempted"
        if cid is not None and stage not in {"remove", "complete"}:
            try:
                # Candidate-owned output metadata cannot veto cleanup of our
                # already recorded CID. CLI/daemon integrity still fences it.
                command(["stop", "--time", "10", cid], 20, cleanup=True)
                _require(command(["rm", cid], cleanup=True) == (cid + "\n").encode(), "builder-remove-response")
                cleanup = "stopped-and-removed"
            except (BuilderExecutionError, origin.OriginError, runtime.RuntimeObservationError, OSError, ValueError):
                cleanup = "unresolved"
        try:
            _record(operation_directory, "failed.json", {
                "stage": stage, "containerName": name, "containerId": cid,
                "cleanup": cleanup, "artifactCapturePerformed": False, "signingPerformed": False,
            })
        except OSError:
            pass  # The already-exclusive operation directory still prevents replay.
        raise BuilderExecutionError("builder-execution-failed-see-private-operation") from None
