"""Bounded, metadata-only observation of an already owned live signer container.

Linux/rootful Docker/runc/cgroup-v2 only. Reuses the existing exact signer
RuntimePolicy, including network=none; creates no process, mount or credential.
The controller independently admits the policy, daemon, code and CREATED sample.
Credential roots are explicit metadata scopes, never their files or contents.
No /proc environ, cmdline or fd inventory is read. Docker's existing exact
configuration verifier still compares its admitted (non-secret) environment.

Two fenced samples are not continuous custody, job authentication, absence of
secrets, or signing permission. No AuthenticatedRebuildHandoff is constructed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

from scripts import android_container_runtime as runtime


class SignerObservationError(RuntimeError):
    """Fixed codes only, never kernel/daemon contents, paths or credentials."""


@dataclass(frozen=True, slots=True)
class LiveSignerObservation:
    container_id: str
    image_id: str
    policy_sha256: str
    configuration_sha256: str
    pid: int
    start_ticks: int
    started_at: str
    observed_at_ns: int
    kernel_metadata_sha256: str
    credential_root_metadata_sha256: str
    protected_signer_runtime_verified: bool = field(default=False, init=False)


def _require(value, code):
    if not value:
        raise SignerObservationError(code)


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid, value.st_nlink)


def _chain(path):
    """Reject ordinary aliases; kernel root/ns magic links are handled separately."""
    _require(path.is_absolute(), "kernel-path")
    identities = []
    for item in (*reversed(path.parents), path):
        value = item.lstat()
        _require(stat.S_ISDIR(value.st_mode) and value.st_uid == 0
                 and not value.st_mode & 0o022, "kernel-ancestor")
        identities.append(_identity(value))
    return tuple(identities)


def _read(path, limit):
    before = path.lstat()
    _require(stat.S_ISREG(before.st_mode) and before.st_uid == 0
             and not before.st_mode & 0o022, "kernel-file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        _require(_identity(os.fstat(fd)) == _identity(before), "kernel-file-changed")
        chunks, count = [], 0
        while True:
            raw = os.read(fd, min(65536, limit - count + 1))
            if not raw:
                break
            chunks.append(raw)
            count += len(raw)
            _require(count <= limit, "kernel-read-bound")
        _require(_identity(os.fstat(fd)) == _identity(before)
                 == _identity(path.lstat()), "kernel-file-changed")
        return b"".join(chunks).decode("ascii", errors="strict")
    finally:
        os.close(fd)


def _start(text, pid):
    _require(text.startswith(str(pid) + " ("), "process-identity")
    tail = text[text.rfind(")") + 1:].split()
    _require(len(tail) >= 20 and tail[0] in {"R", "S", "D"}
             and tail[19].isdigit() and int(tail[19]) > 0, "process-start")
    return int(tail[19])


def _status(text, pid):
    rows = {}
    for line in text.splitlines():
        name, separator, value = line.partition(":")
        _require(separator and name not in rows, "process-status")
        rows[name] = value.split()
    for name in ("Uid", "Gid"):
        _require(rows.get(name) == ["0"] * 4, "process-owner")
    for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        values = rows.get(name)
        _require(values is not None and len(values) == 1
                 and re.fullmatch(r"0{1,16}", values[0]), "process-capabilities")
    _require(rows.get("NoNewPrivs") == ["1"] and rows.get("Seccomp") == ["2"], "process-security")
    nested = rows.get("NSpid", [])
    _require(len(nested) == 2 and nested == [str(pid), "1"], "process-pid-namespace")


def _cgroup(text, policy, pid, container_id):
    _require(re.fullmatch(r"0::/[^\r\n]+\n?", text), "process-cgroup")
    relative = text.rstrip("\n")[3:]
    _require(runtime._path(relative), "process-cgroup")
    path = Path("/sys/fs/cgroup") / relative.lstrip("/")
    _require(path.name == "docker-" + container_id + ".scope"
             or (path.name == container_id and path.parent.name == "docker"), "cgroup-container")
    ancestry = _chain(path)
    values = {name: _read(path / name, 256).strip() for name in
              ("cpu.max", "memory.max", "memory.swap.max", "pids.max")}
    cpu = values["cpu.max"].split()
    _require(len(cpu) == 2 and all(re.fullmatch(r"[1-9][0-9]{0,15}", item) for item in cpu)
             and int(cpu[0]) * 10**9 == policy.resources.nano_cpus * int(cpu[1]), "cgroup-cpu")
    _require(values["memory.max"] == str(policy.resources.memory_bytes)
             and values["memory.swap.max"] == "0"
             and values["pids.max"] == str(policy.resources.pids_limit), "cgroup-limits")
    processes = _read(path / "cgroup.procs", 65536).splitlines()
    _require(all(re.fullmatch(r"[1-9][0-9]{0,19}", value) for value in processes)
             and str(pid) in processes, "cgroup-membership")
    _require(_chain(path) == ancestry, "cgroup-changed")
    return ancestry, values, _identity(path.lstat())


def _unescape(value):
    def replace(match):
        return {"040": " ", "011": "\t", "012": "\n", "134": "\\"}[match[1]]
    _require(re.sub(r"\\(?:040|011|012|134)", "", value).find("\\") == -1, "mount-escape")
    return re.sub(r"\\(040|011|012|134)", replace, value)


def _mountinfo(text, policy):
    rows, ids = {}, set()
    builtins = {"/", "/proc", "/dev", "/dev/pts", "/dev/mqueue", "/dev/shm",
                "/sys", "/sys/fs/cgroup", "/etc/hosts", "/etc/hostname", "/etc/resolv.conf"}
    allowed = builtins | set(runtime.MASKED) | set(runtime.READONLY)
    declared = {row.target for row in (*policy.binds, *policy.tmpfs)}
    _require(not declared & allowed, "mount-policy-overlap")
    for line in text.splitlines():
        parts = line.split()
        _require(10 <= len(parts) <= 64 and "-" in parts, "mount-shape")
        divider = parts.index("-")
        _require(divider >= 6 and len(parts) == divider + 4
                 and all(re.fullmatch(r"[1-9][0-9]*", value) for value in parts[:2])
                 and re.fullmatch(r"[0-9]+:[0-9]+", parts[2]), "mount-shape")
        target, root = _unescape(parts[4]), _unescape(parts[3])
        _require(runtime._path(target, root=True) and runtime._path(root, root=True)
                 and target in allowed | declared and target not in rows
                 and parts[0] not in ids, "mount-unknown-or-aliased")
        # rprivate declarations must not acquire shared/slave propagation.
        _require(not any(item.startswith(("shared:", "master:", "propagate_from:"))
                         for item in parts[6:divider]), "mount-propagation")
        options = parts[5].split(",")
        _require(len(options) == len(set(options)) and len({"ro", "rw"} & set(options)) == 1,
                 "mount-options")
        rows[target] = (parts[0], parts[1], parts[2], root, tuple(options), parts[divider + 1])
        ids.add(parts[0])
    _require(builtins <= set(rows) and declared <= set(rows) and "ro" in rows["/"][4], "mount-root")
    _require(set(runtime.READONLY) <= set(rows)
             and all("ro" in rows[target][4] for target in runtime.READONLY), "mount-readonly-kernel")
    for target in declared:
        _require(not any(other.startswith(target + "/") for other in rows if other != target), "mount-nested")
    for row in policy.binds:
        _require(("ro" if row.read_only else "rw") in rows[row.target][4], "mount-bind-mode")
    for row in policy.tmpfs:
        options = rows[row.target][4]
        _require(rows[row.target][5] == "tmpfs" and {"rw", "nosuid", "nodev"} <= set(options)
                 and ("noexec" in options) == ("noexec" in row.options.split(",")), "mount-tmpfs")
    _require(rows["/proc"][5] == "proc" and rows["/sys"][5] == "sysfs"
             and rows["/sys/fs/cgroup"][5] == "cgroup2"
             and "ro" in rows["/sys"][4] and "ro" in rows["/sys/fs/cgroup"][4], "mount-kernel")
    return rows


def _target(root_fd, target):
    """Stat only the declared path; reject all ordinary component symlinks."""
    fd = os.dup(root_fd)
    try:
        for part in PurePosixPath(target).parts[1:]:
            child = os.open(part, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = child
            _require(not stat.S_ISLNK(os.fstat(fd).st_mode), "mount-target-alias")
        value = os.fstat(fd)
        _require(stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode), "mount-target-kind")
        return _identity(value)
    finally:
        os.close(fd)


def _kernel(pid, policy, credential_targets, container_id):
    process = Path("/proc") / str(pid)
    ancestry = _chain(process)
    start = _start(_read(process / "stat", 8192), pid)
    _status(_read(process / "status", 65536), pid)
    namespaces = {}
    for name in ("mnt", "pid", "net", "cgroup"):
        own = os.stat(process / "ns" / name)
        host = os.stat(Path("/proc/self/ns") / name)
        _require((own.st_dev, own.st_ino) != (host.st_dev, host.st_ino), "process-shared-namespace")
        namespaces[name] = (own.st_dev, own.st_ino)
    cgroup = _cgroup(_read(process / "cgroup", 8192), policy, pid, container_id)
    mounts = _mountinfo(_read(process / "mountinfo", 1024 * 1024), policy)
    # Only this kernel-provided magic link is followed. Paths beneath it are
    # opened component-by-component with O_NOFOLLOW and metadata-only O_PATH.
    root_fd = os.open(process / "root", os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        targets = {row.target: _target(root_fd, row.target) for row in (*policy.binds, *policy.tmpfs)}
        _require(len({value[:2] for value in targets.values()}) == len(targets), "mount-target-alias")
        for row in policy.binds:
            source = Path(row.source)
            _require(source.resolve(strict=True) == source, "mount-source-alias")
            expected = _identity(source.lstat())
            _require(targets[row.target] == expected, "mount-source-identity")
        _require(_target(root_fd, "/sys/fs/cgroup") == cgroup[2], "mount-cgroup-identity")
        credentials = {target: targets[target] for target in credential_targets}
        for value in credentials.values():
            _require(stat.S_ISDIR(value[2]) and stat.S_IMODE(value[2]) == 0o700
                     and value[3:5] == (0, 0), "credential-root-custody")
    finally:
        os.close(root_fd)
    _require(_start(_read(process / "stat", 8192), pid) == start
             and _chain(process) == ancestry, "process-changed")
    return start, (ancestry, namespaces, cgroup, mounts, targets), credentials


def _running(value, container_id, policy, created, now):
    configuration = runtime._configuration(value, container_id, policy)
    state = value.get("State")
    expected = {"Status", "Running", "Paused", "Restarting", "OOMKilled", "Dead", "Pid", "ExitCode",
                "Error", "StartedAt", "FinishedAt"}
    _require(type(state) is dict and set(state) == expected, "live-state")
    _require(state["Running"] is True and state["Status"] == "running"
             and all(state[name] is False for name in ("Paused", "Restarting", "OOMKilled", "Dead"))
             and type(state["Pid"]) is int and 0 < state["Pid"] <= 2147483647
             and type(state["ExitCode"]) is int and state["ExitCode"] == 0
             and state["Error"] == "" and state["FinishedAt"] == runtime.ZERO_TIME
             and type(value.get("RestartCount")) is int and value["RestartCount"] == 0, "live-state")
    _require(value.get("Created") == created.created_at
             and configuration == created.configuration_sha256, "live-configuration-drift")
    started = runtime._timestamp(state["StartedAt"])
    _require(runtime._timestamp(created.observed_at) <= started <= now
             and now - started <= policy.maximum_runtime_seconds * 10**9, "live-time")
    return configuration, state["Pid"], state["StartedAt"]


def observe_running_signer(container_id: str, policy: runtime.RuntimePolicy,
                           created: runtime.RuntimeObservation, *,
                           credential_targets: tuple[str, ...]) -> LiveSignerObservation:
    """Read two fenced live samples. Permission/unsupported-layout errors reject.

    No credential content, job identity or signer authority is acquired. The
    explicit credential roots must be exact declared binds/tmpfs; all other
    mount and resource constraints remain those of the existing RuntimePolicy.
    """
    try:
        _require(type(policy) is runtime.RuntimePolicy, "signer-policy")
        policy.__post_init__()
        _require(policy.process_role == "signer" and type(created) is runtime.RuntimeObservation
                 and created.phase == "created" and created.container_id == container_id
                 and type(container_id) is str and re.fullmatch(r"[0-9a-f]{64}", container_id)
                 and created.image_id == policy.image_id
                 and created.policy_sha256 == runtime._digest(asdict(policy)), "signer-admission")
        declared = {row.target for row in (*policy.binds, *policy.tmpfs)}
        _require(type(credential_targets) is tuple and 1 <= len(credential_targets) <= 4
                 and all(type(target) is str for target in credential_targets)
                 and len(set(credential_targets)) == len(credential_targets)
                 and set(credential_targets) <= declared, "credential-root-policy")
        for credential in (row for row in policy.binds if row.target in credential_targets):
            source = Path(credential.source)
            for other in (row for row in policy.binds if row.target != credential.target):
                peer = Path(other.source)
                _require(source != peer and source not in peer.parents and peer not in source.parents,
                         "credential-root-overlap")
        samples = []
        sources = runtime._mount_sources(policy)
        for _ in range(2):
            value, daemon = runtime._inspect(container_id)
            now = time.time_ns()
            _require(daemon == created.socket_identity, "live-daemon-changed")
            configuration, pid, started = _running(value, container_id, policy, created, now)
            start_ticks, kernel, credentials = _kernel(pid, policy, credential_targets, container_id)
            after, after_daemon = runtime._inspect(container_id)
            _require(after_daemon == daemon
                     and _running(after, container_id, policy, created, time.time_ns()) == (configuration, pid, started)
                     and runtime._mount_sources(policy) == sources, "live-sample-drift")
            samples.append((configuration, pid, started, start_ticks, kernel, credentials))
        _require(samples[0] == samples[1], "live-samples-differ")
        configuration, pid, started, start_ticks, kernel, credentials = samples[-1]
        return LiveSignerObservation(container_id, policy.image_id, created.policy_sha256, configuration,
                                     pid, start_ticks, started, time.time_ns(), runtime._digest(kernel),
                                     runtime._digest(credentials))
    except (OSError, ValueError, TypeError, AttributeError, OverflowError, RecursionError,
            runtime.RuntimeObservationError):
        raise SignerObservationError("signer-observation-unavailable") from None
