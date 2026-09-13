"""Private, key-free Docker Engine configuration/state observation (Linux only).

The controller must independently trust this code, the root daemon, immutable
policy and input custody. A candidate must never supply its own admission policy.
Only fixed API1.55 GET inspect requests are made; there is no CLI, Docker SDK,
process execution, credential input, create/start/exec/delete or other mutation.

Two matching samples are NOT continuous custody, kernel mount/namespace proof,
absence of credentials inside admitted mounts, signer runtime, workflow/job
authentication, an artifact closure, or AuthenticatedRebuildHandoff. These frozen
observations are ordinary forgeable data, not authorization capabilities. Mount
source inode checks do not inspect or authenticate their contents/descendants.
The configuration digest is a validated semantic projection, not raw inspect
byte identity: unordered Mounts are sorted and OomKillDisable false/null means
the unset/default (OOM killing not disabled); all other recipe fields stay exact.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import grp
import hashlib
import json
import math
import os
from pathlib import PurePosixPath
import re
import socket
import stat
import struct
import time


SOCKET_PATH = "/run/docker.sock"
API_VERSION = "1.55"
MAX_BODY = 2 * 1024 * 1024
MAX_HEADERS = 16384
REQUEST_SECONDS = 5.0
ZERO_TIME = "0001-01-01T00:00:00Z"
MASKED = ("/proc/acpi", "/proc/asound", "/proc/interrupts", "/proc/kcore", "/proc/keys",
          "/proc/latency_stats", "/proc/sched_debug", "/proc/scsi", "/proc/timer_list",
          "/proc/timer_stats", "/sys/devices/virtual/powercap", "/sys/firmware")
READONLY = ("/proc/bus", "/proc/fs", "/proc/irq", "/proc/sys", "/proc/sysrq-trigger")


class RuntimeObservationError(RuntimeError):
    """Constant diagnostic codes only; never daemon bodies, headers or Env."""


def _require(condition, code):
    if not condition:
        raise RuntimeObservationError(code)


def _text(value, limit=4096, empty=False):
    return type(value) is str and (empty or bool(value)) and len(value) <= limit and all(
        ord(c) >= 32 and ord(c) != 127 and not 0xD800 <= ord(c) <= 0xDFFF for c in value)


def _path(value, *, root=False):
    return (_text(value) and value.startswith("/") and "\\" not in value and ":" not in value
            and str(PurePosixPath(value)) == value and ".." not in PurePosixPath(value).parts
            and not value.startswith("//") and (root or value != "/"))


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _strings(value, maximum=128, *, empty=True):
    return type(value) is tuple and (empty or bool(value)) and len(value) <= maximum and all(
        _text(item) for item in value)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class BindMount:
    source: str
    target: str
    read_only: bool

    def __post_init__(self):
        _require(_path(self.source) and _path(self.target) and type(self.read_only) is bool, "bind-policy")
        for path in (self.source, self.target):
            _require(not any(path == item or path.startswith(item + "/")
                             for item in ("/dev", "/proc", "/sys", "/run", "/var/run"))
                     and not path.endswith(".sock"), "bind-policy")


@dataclass(frozen=True, slots=True, repr=False)
class TmpfsMount:
    target: str
    options: str

    def __post_init__(self):
        _require(_path(self.target) and _text(self.options, 256), "tmpfs-policy")
        _require(not any(self.target == item or self.target.startswith(item + "/")
                         for item in ("/dev", "/proc", "/sys", "/run", "/var/run")), "tmpfs-policy")
        parts = self.options.split(",")
        _require(len(parts) == len(set(parts)) and {"rw", "nosuid", "nodev"} <= set(parts)
                 and len({"exec", "noexec"} & set(parts)) == 1, "tmpfs-policy")
        pairs = [item.split("=", 1) for item in parts if "=" in item]
        _require(all(len(pair) == 2 for pair in pairs) and len({p[0] for p in pairs}) == len(pairs), "tmpfs-policy")
        values = dict(pairs)
        _require(set(values) <= {"size", "mode", "uid", "gid"} and {"size", "mode"} <= set(values)
                 and all(item in {"rw", "nosuid", "nodev", "exec", "noexec"} or "=" in item for item in parts),
                 "tmpfs-policy")
        _require(re.fullmatch(r"[1-9][0-9]{0,10}", values["size"]) is not None
                 and int(values["size"]) <= 16 * 1024**3
                 and re.fullmatch(r"0?[0-7]{3,4}", values["mode"]) is not None
                 and int(values["mode"], 8) <= 0o1777, "tmpfs-policy")
        _require(all(re.fullmatch(r"[0-9]{1,10}", v) and int(v) <= 2147483647
                     for k, v in values.items() if k in {"uid", "gid"}), "tmpfs-policy")


@dataclass(frozen=True, slots=True, repr=False)
class ResourceLimits:
    memory_bytes: int
    nano_cpus: int
    pids_limit: int
    shm_size: int = 64 * 1024**2
    memory_reservation: int = 0

    def __post_init__(self):
        _require(_integer(self.memory_bytes, 16 * 1024**2, 16 * 1024**3)
                 and _integer(self.nano_cpus, 1, 64 * 10**9) and _integer(self.pids_limit, 1, 4096)
                 and _integer(self.shm_size, 1, self.memory_bytes)
                 and _integer(self.memory_reservation, 0, self.memory_bytes), "resource-policy")


@dataclass(frozen=True, slots=True, repr=False)
class RuntimePolicy:
    image_id: str
    requested_image: str
    user: str
    workdir: str
    entrypoint: tuple[str, ...]
    command: tuple[str, ...]
    environment: tuple[str, ...]
    resources: ResourceLimits
    binds: tuple[BindMount, ...] = ()
    tmpfs: tuple[TmpfsMount, ...] = ()
    labels: tuple[tuple[str, str], ...] = ()
    attach_stdout: bool = True
    attach_stderr: bool = True
    maximum_runtime_seconds: int = 10800

    def __post_init__(self):
        _require(type(self.image_id) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_id), "image-policy")
        _require(_text(self.requested_image, 512) and re.fullmatch(
            r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+"
            r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?@sha256:[0-9a-f]{64}", self.requested_image), "image-policy")
        _require(type(self.user) is str and re.fullmatch(r"[1-9][0-9]{0,9}:[1-9][0-9]{0,9}", self.user)
                 and all(int(v) <= 2147483647 for v in self.user.split(":")), "user-policy")
        _require(_path(self.workdir, root=True) and _strings(self.entrypoint, empty=False)
                 and _path(self.entrypoint[0]) and _strings(self.command), "command-policy")
        _require(_strings(self.environment) and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", value)
                 for value in self.environment) and len({v.split("=", 1)[0] for v in self.environment})
                 == len(self.environment), "environment-policy")
        _require(type(self.resources) is ResourceLimits, "resource-policy")
        self.resources.__post_init__()
        _require(type(self.binds) is tuple and type(self.tmpfs) is tuple and len(self.binds) + len(self.tmpfs) <= 32,
                 "mount-policy")
        for rows, kind in ((self.binds, BindMount), (self.tmpfs, TmpfsMount)):
            for row in rows:
                _require(type(row) is kind, "mount-policy")
                row.__post_init__()
        targets = [row.target for row in (*self.binds, *self.tmpfs)]
        _require(len(set(targets)) == len(targets) and not any(a.startswith(b + "/")
                 for a in targets for b in targets if a != b), "mount-policy")
        _require(type(self.labels) is tuple and len(self.labels) <= 64 and all(type(pair) is tuple
                 and len(pair) == 2 and _text(pair[0], 256) and _text(pair[1], empty=True) for pair in self.labels)
                 and len(dict(self.labels)) == len(self.labels), "label-policy")
        _require(type(self.attach_stdout) is bool and type(self.attach_stderr) is bool
                 and _integer(self.maximum_runtime_seconds, 1, 86400), "execution-policy")


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    container_id: str
    image_id: str
    requested_image_sha256: str
    policy_sha256: str
    configuration_sha256: str
    phase: str
    created_at: str
    started_at: str
    finished_at: str
    observed_at: str
    socket_identity: tuple[int, ...] = field(repr=False)
    mount_source_identity_sha256: str
    schema: str = field(default="fleet.docker-configuration-state-observation/v1", init=False)


def _socket_identity():
    try:
        group = grp.getgrnam("docker").gr_gid
        identities = []
        for path in ("/", "/run", SOCKET_PATH):
            value = os.lstat(path)
            _require(os.path.realpath(path) == path and value.st_uid == 0, "socket-path")
            if path == SOCKET_PATH:
                _require(stat.S_ISSOCK(value.st_mode) and value.st_gid == group
                         and stat.S_IMODE(value.st_mode) == 0o660, "socket-mode")
            else:
                _require(stat.S_ISDIR(value.st_mode) and value.st_gid == 0
                         and not value.st_mode & 0o022, "socket-ancestor")
            identities.extend((value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid))
            if path == SOCKET_PATH:
                identities.extend((value.st_mtime_ns, value.st_ctime_ns))
        return tuple(identities)
    except (OSError, KeyError):
        raise RuntimeObservationError("socket-unavailable") from None


class _Wire:
    def __init__(self, connection, deadline):
        self.connection, self.deadline, self.buffer = connection, deadline, bytearray()

    def receive(self):
        remaining = self.deadline - time.monotonic()
        _require(remaining > 0, "http-deadline")
        self.connection.settimeout(remaining)
        chunk = self.connection.recv(8192)
        _require(bool(chunk), "http-truncated")
        self.buffer.extend(chunk)

    def line(self, limit):
        while b"\r\n" not in self.buffer:
            _require(len(self.buffer) <= limit, "http-line-bound")
            self.receive()
        end = self.buffer.index(b"\r\n")
        _require(end <= limit, "http-line-bound")
        result = bytes(self.buffer[:end])
        del self.buffer[:end + 2]
        return result

    def exact(self, count):
        while len(self.buffer) < count:
            self.receive()
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result


def _response(connection, deadline):
    wire = _Wire(connection, deadline)
    status = wire.line(128)
    _require(re.fullmatch(rb"HTTP/1\.1 200 [\x20-\x7e]{0,80}", status), "http-status")
    headers, total = {}, len(status) + 2
    for _ in range(65):
        line = wire.line(MAX_HEADERS)
        total += len(line) + 2
        _require(total <= MAX_HEADERS, "http-header-bound")
        if not line:
            break
        _require(b":" in line and not line.startswith((b" ", b"\t")), "http-header")
        key, value = line.split(b":", 1)
        key = key.lower()
        _require(re.fullmatch(rb"[a-z0-9-]+", key) and key not in headers
                 and all(32 <= c < 127 for c in value), "http-header")
        headers[key] = value.strip().lower()
    else:
        raise RuntimeObservationError("http-header-bound")
    _require(headers.get(b"content-type") in (b"application/json", b"application/json; charset=utf-8")
             and b"content-encoding" not in headers, "http-type")
    size, transfer = headers.get(b"content-length"), headers.get(b"transfer-encoding")
    _require((size is None) != (transfer is None), "http-framing")
    if size is not None:
        _require(re.fullmatch(rb"0|[1-9][0-9]{0,9}", size) and 0 < int(size) <= MAX_BODY, "http-body-bound")
        result = wire.exact(int(size))
    else:
        _require(transfer == b"chunked", "http-framing")
        result = bytearray()
        for _ in range(4096):
            line = wire.line(16)
            _require(re.fullmatch(rb"[0-9A-Fa-f]{1,8}", line), "http-chunk")
            count = int(line, 16)
            _require(len(result) + count <= MAX_BODY, "http-body-bound")
            if not count:
                _require(wire.line(2) == b"", "http-trailer")
                break
            result.extend(wire.exact(count))
            _require(wire.exact(2) == b"\r\n", "http-chunk")
        else:
            raise RuntimeObservationError("http-chunk-bound")
    _require(not wire.buffer, "http-extra-data")
    remaining = deadline - time.monotonic()
    _require(remaining > 0, "http-deadline")
    connection.settimeout(remaining)
    _require(connection.recv(1) == b"", "http-extra-data")
    return bytes(result)


def _json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, "json-duplicate")
            value[key] = item
        return value

    def invalid(_):
        raise RuntimeObservationError("json-number")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            _require(count <= 32768 and depth <= 32, "json-bound")
            if type(item) is dict:
                _require(all(_text(key, 256) for key in item), "json-key")
                pending.extend((child, depth + 1) for child in item.values())
            elif type(item) is list:
                pending.extend((child, depth + 1) for child in item)
            elif type(item) is str:
                _require(_text(item, 16384, empty=True), "json-string")
            elif type(item) is float:
                _require(math.isfinite(item), "json-number")
        _require(type(value) is dict, "json-shape")
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise RuntimeObservationError("json-invalid") from None


def _inspect(container_id):
    _require(type(container_id) is str and re.fullmatch(r"[0-9a-f]{64}", container_id), "container-id")
    before = _socket_identity()
    deadline = time.monotonic() + REQUEST_SECONDS
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(max(0.001, deadline - time.monotonic()))
            connection.connect(SOCKET_PATH)
            pid, uid, _gid = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            _require(pid > 0 and uid == 0, "socket-peer")
            remaining = deadline - time.monotonic()
            _require(remaining > 0, "http-deadline")
            connection.settimeout(remaining)
            connection.sendall((f"GET /v{API_VERSION}/containers/{container_id}/json HTTP/1.1\r\n"
                                "Host: docker\r\nAccept: application/json\r\nConnection: close\r\n\r\n").encode("ascii"))
            raw = _response(connection, deadline)
        _require(time.monotonic() <= deadline, "http-deadline")
        _require(_socket_identity() == before, "socket-changed")
        return _json(raw), before + (pid,)
    except (OSError, ValueError, struct.error):
        raise RuntimeObservationError("inspect-transport") from None


def _timestamp(value):
    _require(type(value) is str, "state-time")
    match = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]{1,9}))?Z", value)
    _require(match is not None, "state-time")
    try:
        parsed = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
        seconds = (parsed - datetime(1970, 1, 1, tzinfo=UTC)).days * 86400
        seconds += parsed.hour * 3600 + parsed.minute * 60 + parsed.second
        return seconds * 10**9 + int((match[2] or "").ljust(9, "0"))
    except ValueError:
        raise RuntimeObservationError("state-time") from None


def _same(actual, expected, code):
    # JSON equality, unlike Python ==, distinguishes true/1 and 0/0.0.
    _require(_digest(actual) == _digest(expected), code)


def _mount_sources(policy):
    rows = []
    try:
        for mount in policy.binds:
            value = os.lstat(mount.source)
            _require(os.path.realpath(mount.source) == mount.source
                     and (stat.S_ISREG(value.st_mode) or stat.S_ISDIR(value.st_mode)), "bind-source-type")
            rows.append((mount.source, value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid))
    except OSError:
        raise RuntimeObservationError("bind-source-unavailable") from None
    return _digest(rows)


def _configuration(value, container_id, policy):
    _require(value.get("Id") == container_id and value.get("Image") == policy.image_id
             and value.get("Platform") == "linux", "container-identity")
    _require(value.get("ExecIDs") is None or type(value["ExecIDs"]) is list and not value["ExecIDs"], "container-exec")
    config, host, mounts = value.get("Config"), value.get("HostConfig"), value.get("Mounts")
    _require(type(config) is dict and type(host) is dict and type(mounts) is list, "configuration-shape")
    expected_config = {
        "Hostname": container_id[:12], "Domainname": "", "User": policy.user,
        "AttachStdin": False, "AttachStdout": policy.attach_stdout, "AttachStderr": policy.attach_stderr,
        "Tty": False, "OpenStdin": False, "StdinOnce": False, "Env": list(policy.environment),
        "Cmd": list(policy.command), "Image": policy.requested_image, "Volumes": None,
        "WorkingDir": policy.workdir, "Entrypoint": list(policy.entrypoint), "Labels": dict(policy.labels),
    }
    # API1.55 may encode an empty map as null. No nonempty implicit volume,
    # healthcheck, OnBuild or other image-config extension is accepted.
    normalized_config = dict(config)
    if "Labels" in normalized_config and normalized_config["Labels"] is None:
        normalized_config["Labels"] = {}
    _same(normalized_config, expected_config, "container-config")
    _same(value.get("Path"), policy.entrypoint[0], "container-command")
    _same(value.get("Args"), list(policy.entrypoint[1:] + policy.command), "container-command")
    resources = policy.resources
    exact = {"ContainerIDFile": "", "LogConfig": {"Type": "none", "Config": {}}, "NetworkMode": "none",
             "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0}, "AutoRemove": False,
             "VolumeDriver": "", "ConsoleSize": [0, 0], "CapDrop": ["ALL"], "CgroupnsMode": "private",
             "IpcMode": "private", "Cgroup": "", "OomScoreAdj": 0, "PidMode": "", "Privileged": False,
             "PublishAllPorts": False, "ReadonlyRootfs": True, "UTSMode": "", "UsernsMode": "",
             "ShmSize": resources.shm_size, "Runtime": "runc", "Isolation": "", "Memory": resources.memory_bytes,
             "NanoCpus": resources.nano_cpus, "MemoryReservation": resources.memory_reservation,
             "MemorySwap": resources.memory_bytes, "MemorySwappiness": None, "OomKillDisable": False,
             "PidsLimit": resources.pids_limit, "MaskedPaths": list(MASKED), "ReadonlyPaths": list(READONLY)}
    empty_lists = "VolumesFrom CapAdd Dns DnsOptions DnsSearch ExtraHosts GroupAdd Links BlkioWeightDevice BlkioDeviceReadBps BlkioDeviceWriteBps BlkioDeviceReadIOps BlkioDeviceWriteIOps Devices DeviceCgroupRules DeviceRequests Ulimits".split()
    zeros = "CpuShares BlkioWeight CpuPeriod CpuQuota CpuRealtimePeriod CpuRealtimeRuntime CpuCount CpuPercent IOMaximumIOps IOMaximumBandwidth".split()
    strings = "CgroupParent CpusetCpus CpusetMems".split()
    for name in zeros:
        exact[name] = 0
    for name in strings:
        exact[name] = ""
    allowed = set(exact) | set(empty_lists) | {"Binds", "Mounts", "Tmpfs", "PortBindings", "SecurityOpt"}
    _require(set(host) <= allowed and set(exact) <= set(host) and set(empty_lists) <= set(host)
             and {"PortBindings", "SecurityOpt"} <= set(host), "host-config-fields")
    # Docker's optional *bool may change false -> null after start on cgroup
    # v2, where --oom-kill-disable is discarded. Require the field and accept
    # only unset or the actual bool False, never true or Python-equal 0/0.0.
    # https://docs.docker.com/engine/containers/runmetrics/#running-docker-on-cgroup-v2
    _require(host["OomKillDisable"] is None or host["OomKillDisable"] is False, "host-config")
    normalized_host = dict(host)
    normalized_host["OomKillDisable"] = False
    for name, expected in exact.items():
        _same(normalized_host[name], expected, "host-config")
    for name in empty_lists:
        _require(host[name] is None or type(host[name]) is list and not host[name], "host-extension")
    _require(host["PortBindings"] is None or type(host["PortBindings"]) is dict and not host["PortBindings"], "host-ports")
    _require(host["SecurityOpt"] in (["no-new-privileges"], ["no-new-privileges=true"]), "host-security")
    _require(host.get("Tmpfs") is None or type(host["Tmpfs"]) is dict, "host-tmpfs")
    _same(host.get("Tmpfs") or {}, {row.target: row.options for row in policy.tmpfs}, "host-tmpfs")
    expected_binds = [f"{row.source}:{row.target}:{'ro' if row.read_only else 'rw'},rprivate" for row in policy.binds]
    _require(host.get("Binds") is None or type(host["Binds"]) is list, "host-binds")
    _same(host.get("Binds") or [], expected_binds, "host-binds")
    _require(host.get("Mounts") is None or type(host["Mounts"]) is list and not host["Mounts"], "host-mount-api")
    # Legacy --tmpfs declarations are absent from top-level Mounts even at
    # CREATED. They are bound above, never invented from a nonexistent row.
    expected_mounts = [{"Type": "bind", "Source": row.source, "Destination": row.target,
                        "Mode": ("ro" if row.read_only else "rw") + ",rprivate", "RW": not row.read_only,
                        "Propagation": "rprivate"} for row in policy.binds]
    _require(all(type(row) is dict and type(row.get("Destination")) is str for row in mounts), "mount-shape")
    canonical_mounts = sorted(mounts, key=lambda row: row["Destination"])
    _same(canonical_mounts,
          sorted(expected_mounts, key=lambda row: row["Destination"]), "container-mounts")
    network = value.get("NetworkSettings")
    _require(type(network) is dict and set(network) == {"SandboxID", "SandboxKey", "Ports", "Networks"}
             and network.get("Ports") in ({}, None)
             and type(network.get("Networks")) is dict and set(network["Networks"]) == {"none"}, "container-network")
    _require(type(network["SandboxID"]) is str and re.fullmatch(r"(?:[0-9a-f]{64})?", network["SandboxID"])
             and type(network["SandboxKey"]) is str and re.fullmatch(r"(?:/var/run/docker/netns/[0-9a-f]{12})?", network["SandboxKey"]),
             "container-network")
    endpoint = network["Networks"]["none"]
    empty = ("Gateway", "IPAddress", "MacAddress", "IPv6Gateway", "GlobalIPv6Address")
    nulls = ("IPAMConfig", "Links", "Aliases", "DriverOpts", "DNSNames")
    zero = ("IPPrefixLen", "GlobalIPv6PrefixLen", "GwPriority")
    _require(type(endpoint) is dict and set(endpoint) == set(empty + nulls + zero + ("NetworkID", "EndpointID")), "container-network")
    for key in empty + nulls + zero:
        _same(endpoint[key], "" if key in empty else None if key in nulls else 0, "container-network")
    _require(all(type(endpoint[key]) is str and re.fullmatch(r"(?:[0-9a-f]{64})?", endpoint[key])
                 for key in ("NetworkID", "EndpointID")), "container-network")
    return _digest({"Config": config, "HostConfig": normalized_host, "Mounts": canonical_mounts, "Image": value["Image"],
                    "Path": value["Path"], "Args": value["Args"]})


def _validate(value, container_id, policy, phase, now):
    digest = _configuration(value, container_id, policy)
    state = value.get("State")
    keys = {"Status", "Running", "Paused", "Restarting", "OOMKilled", "Dead", "Pid", "ExitCode", "Error", "StartedAt", "FinishedAt"}
    _require(type(state) is dict and set(state) == keys, "state-fields")
    for key in ("Running", "Paused", "Restarting", "OOMKilled", "Dead"):
        _same(state[key], False, "state-not-quiescent")
    _same(value.get("RestartCount"), 0, "state-restarted")
    _same(state["Pid"], 0, "state-pid")
    _same(state["ExitCode"], 0, "state-exit")
    _same(state["Error"], "", "state-error")
    _same(state["Status"], phase, "state-phase")
    created = _timestamp(value.get("Created"))
    _require(value["Created"] != ZERO_TIME and 0 < created <= now, "state-created-time")
    if phase == "created":
        _require(state["StartedAt"] == ZERO_TIME and state["FinishedAt"] == ZERO_TIME, "state-already-started")
    else:
        start, end = _timestamp(state["StartedAt"]), _timestamp(state["FinishedAt"])
        _require(created <= start <= end <= now and end - start <= policy.maximum_runtime_seconds * 10**9,
                 "state-time-order")
    return digest, value["Created"], state["StartedAt"], state["FinishedAt"]


def _observe(container_id, policy, phase, previous=None):
    _require(type(policy) is RuntimePolicy, "runtime-policy")
    policy.__post_init__()
    _require(type(container_id) is str and re.fullmatch(r"[0-9a-f]{64}", container_id), "container-id")
    policy_hash = _digest(asdict(policy))
    if previous is not None:
        _require(type(previous) is RuntimeObservation and previous.phase == "created"
                 and previous.container_id == container_id and previous.policy_sha256 == policy_hash, "prior-observation")
    try:
        mount_identity = _mount_sources(policy)
        observations = []
        for _ in range(2):
            raw, daemon = _inspect(container_id)
            observed_ns = time.time_ns()
            validated = _validate(raw, container_id, policy, phase, observed_ns)
            observations.append((validated, daemon))
        _require(observations[0] == observations[1], "inspect-samples-differ")
        _require(_mount_sources(policy) == mount_identity, "bind-source-changed")
        (configuration, created, started, finished), daemon = observations[-1]
        if previous is not None:
            _require(previous.configuration_sha256 == configuration and previous.created_at == created
                     and previous.socket_identity == daemon and previous.mount_source_identity_sha256 == mount_identity,
                     "completion-drift")
            _require(_timestamp(previous.observed_at) <= _timestamp(started), "completion-before-observation")
        observed_at = datetime.fromtimestamp(observed_ns // 10**9, UTC).strftime("%Y-%m-%dT%H:%M:%S")
        observed_at += f".{observed_ns % 10**9:09d}Z"
        return RuntimeObservation(container_id, policy.image_id, hashlib.sha256(policy.requested_image.encode()).hexdigest(),
                                  policy_hash, configuration, phase, created, started, finished, observed_at, daemon, mount_identity)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        raise RuntimeObservationError("observation-invalid") from None


def observe_created(container_id: str, policy: RuntimePolicy) -> RuntimeObservation:
    """Observe a controller-owned CREATED container twice; never start it."""
    return _observe(container_id, policy, "created")


def observe_exited(container_id: str, policy: RuntimePolicy, created: RuntimeObservation) -> RuntimeObservation:
    """Observe successful EXITED state twice and compare prior configuration."""
    _require(type(created) is RuntimeObservation, "prior-observation")
    return _observe(container_id, policy, "exited", created)
