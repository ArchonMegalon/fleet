"""UNIT models only: manufactured Docker inspect/policy and local socket bytes.

No test contacts Docker, starts a container, or proves a real job/runtime. The
separate controller-owned live probe is not replaced by these positive fixtures.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
import ast
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import tempfile
import traceback
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import android_container_runtime as runtime

CID = "1" * 64
IMAGE = "sha256:" + "2" * 64
REFERENCE = "example.invalid/team/runtime:10@sha256:" + "3" * 64
CREATED = "2026-09-13T10:00:00.000000001Z"
STARTED = "2026-09-13T10:00:02.000000001Z"
FINISHED = "2026-09-13T10:00:03.000000002Z"
NOW = int(datetime(2026, 9, 13, 10, 0, 1, tzinfo=UTC).timestamp()) * 10**9
SECRET = "unit-only-sensitive-env-marker"


@pytest.fixture
def policy(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    return runtime.RuntimePolicy(IMAGE, REFERENCE, "65534:65534", "/", ("/bin/sh",), ("/chummer-input/check.sh",),
        ("PATH=/usr/bin:/bin", "APP_UID=1654"), runtime.ResourceLimits(67108864, 250000000, 32),
        binds=(runtime.BindMount(str(source), "/chummer-input", True),),
        tmpfs=(runtime.TmpfsMount("/chummer-output", "rw,noexec,nosuid,nodev,size=1048576,mode=1777"),))


def inspection(policy, phase="created"):
    # Literal API1.55 shapes from a separately observed key-free probe; no
    # production-generated expected config or response admission is used.
    source = policy.binds[0].source
    host = {
        "Binds": [source + ":/chummer-input:ro,rprivate"], "ContainerIDFile": "",
        "LogConfig": {"Type": "none", "Config": {}}, "NetworkMode": "none", "PortBindings": {},
        "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0}, "AutoRemove": False, "VolumeDriver": "",
        "VolumesFrom": None, "ConsoleSize": [0, 0], "CapAdd": None, "CapDrop": ["ALL"], "CgroupnsMode": "private",
        "Dns": [], "DnsOptions": [], "DnsSearch": [], "ExtraHosts": None, "GroupAdd": None,
        "IpcMode": "private", "Cgroup": "", "Links": None, "OomScoreAdj": 0, "PidMode": "",
        "Privileged": False, "PublishAllPorts": False, "ReadonlyRootfs": True,
        "SecurityOpt": ["no-new-privileges=true"],
        "Tmpfs": {"/chummer-output": "rw,noexec,nosuid,nodev,size=1048576,mode=1777"},
        "UTSMode": "", "UsernsMode": "", "ShmSize": 67108864, "Runtime": "runc", "Isolation": "",
        "CpuShares": 0, "Memory": 67108864, "NanoCpus": 250000000, "CgroupParent": "", "BlkioWeight": 0,
        "BlkioWeightDevice": [], "BlkioDeviceReadBps": [], "BlkioDeviceWriteBps": [],
        "BlkioDeviceReadIOps": [], "BlkioDeviceWriteIOps": [], "CpuPeriod": 0, "CpuQuota": 0,
        "CpuRealtimePeriod": 0, "CpuRealtimeRuntime": 0, "CpusetCpus": "", "CpusetMems": "", "Devices": [],
        "DeviceCgroupRules": None, "DeviceRequests": None, "MemoryReservation": 0, "MemorySwap": 67108864,
        "MemorySwappiness": None, "OomKillDisable": False, "PidsLimit": 32, "Ulimits": None,
        "CpuCount": 0, "CpuPercent": 0, "IOMaximumIOps": 0, "IOMaximumBandwidth": 0,
        "MaskedPaths": ["/proc/acpi", "/proc/asound", "/proc/interrupts", "/proc/kcore", "/proc/keys",
                        "/proc/latency_stats", "/proc/sched_debug", "/proc/scsi", "/proc/timer_list",
                        "/proc/timer_stats", "/sys/devices/virtual/powercap", "/sys/firmware"],
        "ReadonlyPaths": ["/proc/bus", "/proc/fs", "/proc/irq", "/proc/sys", "/proc/sysrq-trigger"],
    }
    return {"Id": CID, "Image": IMAGE, "Created": CREATED, "Platform": "linux", "RestartCount": 0, "ExecIDs": None,
        "Path": "/bin/sh", "Args": ["/chummer-input/check.sh"],
        "Config": {"Hostname": CID[:12], "Domainname": "", "User": "65534:65534", "AttachStdin": False,
                   "AttachStdout": True, "AttachStderr": True, "Tty": False, "OpenStdin": False, "StdinOnce": False,
                   "Env": ["PATH=/usr/bin:/bin", "APP_UID=1654"], "Cmd": ["/chummer-input/check.sh"],
                   "Image": REFERENCE, "Volumes": None, "WorkingDir": "/", "Entrypoint": ["/bin/sh"], "Labels": {}},
        "HostConfig": host,
        "Mounts": [{"Type": "bind", "Source": source, "Destination": "/chummer-input", "Mode": "ro,rprivate",
                    "RW": False, "Propagation": "rprivate"}],
        "State": {"Status": phase, "Running": False, "Paused": False, "Restarting": False, "OOMKilled": False,
                  "Dead": False, "Pid": 0, "ExitCode": 0, "Error": "", "StartedAt": STARTED if phase == "exited" else runtime.ZERO_TIME,
                  "FinishedAt": FINISHED if phase == "exited" else runtime.ZERO_TIME},
        "NetworkSettings": {"SandboxID": "", "SandboxKey": "", "Ports": {}, "Networks": {"none": {
            "IPAMConfig": None, "Links": None, "Aliases": None, "DriverOpts": None, "GwPriority": 0,
            "NetworkID": "", "EndpointID": "", "Gateway": "", "IPAddress": "", "MacAddress": "", "IPPrefixLen": 0,
            "IPv6Gateway": "", "GlobalIPv6Address": "", "GlobalIPv6PrefixLen": 0, "DNSNames": None}}}}


def samples(monkeypatch, rows, times=None):
    queue, calls = iter(rows), []
    def inspect(cid):
        calls.append(cid)
        row = next(queue)
        return (deepcopy(row), (10, 20, 30)) if type(row) is dict else row
    monkeypatch.setattr(runtime, "_inspect", inspect)
    values = iter(times or [NOW] * len(rows))
    monkeypatch.setattr(runtime.time, "time_ns", lambda: next(values))
    return calls


def test_created_and_terminal_are_detached_exact_configuration_observations(policy, monkeypatch):
    initial, terminal = inspection(policy), inspection(policy, "exited")
    terminal["NetworkSettings"]["Networks"]["none"]["NetworkID"] = "a" * 64
    calls = samples(monkeypatch, [initial, initial, terminal, terminal], [NOW, NOW, NOW + 4*10**9, NOW + 4*10**9])
    before = runtime.observe_created(CID, policy)
    after = runtime.observe_exited(CID, policy, before)
    assert calls == [CID] * 4 and after.phase == "exited"
    assert before.configuration_sha256 == after.configuration_sha256
    assert (after.created_at, after.started_at, after.finished_at) == (CREATED, STARTED, FINISHED)
    assert after.schema == "fleet.docker-configuration-state-observation/v1"
    initial["Config"]["Env"].append("SECRET=" + SECRET)
    assert SECRET not in repr(before) and "PATH" not in repr(after)
    for value in (before, policy, policy.binds[0], policy.tmpfs[0], policy.resources):
        with pytest.raises((FrozenInstanceError, TypeError, AttributeError)):
            value.phase = "forged"
    assert SECRET not in repr(replace(policy, environment=("SECRET=" + SECRET,)))


@pytest.mark.parametrize("field,value", [
    ("image_id", "sha256:short"), ("image_id", True), ("requested_image", "example.invalid/team/image:latest"),
    ("requested_image", "https://example.invalid/x@sha256:" + "3"*64), ("user", "0:0"), ("user", "name"),
    ("user", "01:1"), ("user", "1:0"), ("workdir", "/a/../b"), ("entrypoint", ["/bin/sh"]),
    ("entrypoint", ()), ("command", ["x"]), ("environment", ("X=a", "X=b")), ("environment", ("NO_EQUALS",)),
    ("environment", ("X=line\nbreak",)), ("environment", []), ("binds", []), ("tmpfs", []),
    ("labels", (("same", "a"), ("same", "b"))), ("attach_stdout", 1), ("maximum_runtime_seconds", True),
    ("maximum_runtime_seconds", 0), ("maximum_runtime_seconds", 86401), ("resources", {}),
])
def test_invalid_policy_is_rejected_before_transport(policy, monkeypatch, field, value):
    monkeypatch.setattr(runtime, "_inspect", lambda _: pytest.fail("policy must precede transport"))
    with pytest.raises(runtime.RuntimeObservationError):
        replace(policy, **{field: value})


@pytest.mark.parametrize("field,value", [("memory_bytes", True), ("memory_bytes", -1), ("nano_cpus", 0),
    ("nano_cpus", 1.0), ("pids_limit", False), ("shm_size", 0), ("memory_reservation", 67108865)])
def test_resource_types_and_bounds(policy, field, value):
    with pytest.raises(runtime.RuntimeObservationError):
        replace(policy.resources, **{field: value})


def test_unknown_policy_fields_and_nested_mutable_collections_reject(policy):
    with pytest.raises(TypeError):
        runtime.RuntimePolicy(unknown=True)
    with pytest.raises(runtime.RuntimeObservationError):
        replace(policy, labels=(["key", "value"],))
    with pytest.raises(runtime.RuntimeObservationError):
        replace(policy, binds=(policy.binds[0], policy.binds[0]))
    with pytest.raises(runtime.RuntimeObservationError):
        replace(policy, tmpfs=(runtime.TmpfsMount("/chummer-input/child", policy.tmpfs[0].options),))


@pytest.mark.parametrize("path", ["/", "/proc", "/proc/child", "/dev", "/sys", "/run", "/var/run", "/a/../b", "//tmp"])
def test_forbidden_mount_targets(path):
    with pytest.raises(runtime.RuntimeObservationError):
        runtime.BindMount("/safe/input", path, True)
    with pytest.raises(runtime.RuntimeObservationError):
        runtime.TmpfsMount(path, "rw,nosuid,nodev,noexec,size=1024,mode=700")


@pytest.mark.parametrize("options", ["rw,size=1024,mode=700", "rw,nosuid,nodev,exec,noexec,size=1,mode=700",
    "rw,nosuid,nodev,noexec,size=0,mode=700", "rw,nosuid,nodev,noexec,size=1,size=2,mode=700",
    "rw,nosuid,nodev,noexec,size=1,mode=700,unknown=yes", "rw,nosuid,nodev,noexec,size=1,mode=4777"])
def test_tmpfs_requires_closed_explicit_safe_options(options):
    with pytest.raises(runtime.RuntimeObservationError):
        runtime.TmpfsMount("/scratch", options)


HOST_TAMPERS = [("Privileged", True), ("ReadonlyRootfs", False), ("CapAdd", ["SYS_ADMIN"]), ("CapDrop", []),
    ("SecurityOpt", []), ("NetworkMode", "host"), ("NetworkMode", "bridge"), ("PidMode", "host"),
    ("IpcMode", "host"), ("UTSMode", "host"), ("UsernsMode", "host"), ("CgroupnsMode", "host"),
    ("Runtime", "custom"), ("Devices", [{"PathOnHost": "/dev/null"}]), ("DeviceRequests", [{}]),
    ("DeviceCgroupRules", ["a *:* rwm"]), ("PortBindings", {"80/tcp": []}), ("PublishAllPorts", True),
    ("RestartPolicy", {"Name": "always", "MaximumRetryCount": 0}), ("AutoRemove", True), ("PidsLimit", -1),
    ("Memory", 0), ("MemorySwap", -1), ("NanoCpus", 0), ("CpuShares", False), ("GroupAdd", ["0"]),
    ("MaskedPaths", []), ("ReadonlyPaths", []), ("Binds", []), ("Tmpfs", {}), ("Mounts", [{"Type": "volume"}]),
    ("Ulimits", [{}]), ("LogConfig", {"Type": "syslog", "Config": {}}), ("UnreviewedField", False)]


@pytest.mark.parametrize("field,value", HOST_TAMPERS)
def test_host_configuration_tampering_fails_closed(policy, field, value):
    row = inspection(policy)
    row["HostConfig"][field] = value
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, policy, "created", NOW)


@pytest.mark.parametrize("field,value", [("Env", ["SECRET=" + SECRET]), ("User", "0:0"), ("Cmd", ["other"]),
    ("Entrypoint", ["/other"]), ("WorkingDir", "/other"), ("Image", "example.invalid/tag:latest"),
    ("Volumes", {"/anonymous": {}}), ("Healthcheck", {"Test": ["CMD", "other"]}), ("AttachStdin", True), ("Tty", 0)])
def test_image_command_environment_tampering_is_sanitized(policy, field, value):
    row = inspection(policy)
    row["Config"][field] = value
    with pytest.raises(runtime.RuntimeObservationError) as failure:
        runtime._validate(row, CID, policy, "created", NOW)
    assert SECRET not in str(failure.value) and SECRET not in repr(failure.value)


@pytest.mark.parametrize("field,value", [("RW", True), ("Propagation", "rshared"), ("Type", "volume"),
    ("Source", "/run/docker.sock"), ("Destination", "/other"), ("Mode", "ro"), ("Driver", "local")])
def test_extra_missing_or_changed_mounts_reject(policy, field, value):
    row = inspection(policy)
    row["Mounts"][0][field] = value
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, policy, "created", NOW)


@pytest.mark.parametrize("bad", [False, 0, "", True, [1]])
def test_empty_mount_normalization_does_not_admit_wrong_types(policy, bad):
    empty = replace(policy, binds=(), tmpfs=())
    row = inspection(policy)
    row["Mounts"], row["HostConfig"]["Binds"], row["HostConfig"]["Tmpfs"] = [], None, None
    for field in ("Binds", "Tmpfs"):
        changed = deepcopy(row)
        changed["HostConfig"][field] = bad
        with pytest.raises(runtime.RuntimeObservationError):
            runtime._validate(changed, CID, empty, "created", NOW)


@pytest.mark.parametrize("field,value", [("IPPrefixLen", False), ("GlobalIPv6PrefixLen", 0.0), ("GwPriority", True),
    ("DriverOpts", {"foo": "bar"}), ("Aliases", ["name"]), ("IPAddress", "127.0.0.1"), ("Unreviewed", "")])
def test_none_network_has_no_meaningful_hidden_configuration(policy, field, value):
    row = inspection(policy)
    row["NetworkSettings"]["Networks"]["none"][field] = value
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, policy, "created", NOW)


@pytest.mark.parametrize("field,value", [("Running", True), ("Paused", True), ("Restarting", True), ("OOMKilled", True),
    ("Dead", True), ("ExitCode", 1), ("ExitCode", False), ("Pid", True), ("Error", SECRET),
    ("StartedAt", STARTED), ("FinishedAt", FINISHED), ("Health", {})])
def test_created_requires_never_started_quiescent_state(policy, field, value):
    row = inspection(policy)
    row["State"][field] = value
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, policy, "created", NOW)


@pytest.mark.parametrize("field,value", [("RestartCount", 1), ("RestartCount", False), ("ExecIDs", ["definition"]),
    ("ExecIDs", False), ("Image", "sha256:" + "f"*64), ("Id", "2"*64), ("Created", "bad")])
def test_top_identity_exec_and_restart_reject(policy, field, value):
    row = inspection(policy)
    row[field] = value
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, policy, "created", NOW)


@pytest.mark.parametrize("change", ["sample", "daemon", "completed-config", "created", "prior", "time", "restart"])
def test_sample_and_completion_fences(policy, monkeypatch, change):
    initial, terminal = inspection(policy), inspection(policy, "exited")
    samples(monkeypatch, [initial, initial])
    before = runtime.observe_created(CID, policy)
    other = deepcopy(terminal)
    if change in {"sample", "completed-config"}:
        other["HostConfig"]["SecurityOpt"] = ["no-new-privileges"]
    if change == "created":
        other["Created"] = "2026-09-13T10:00:00Z"
    if change == "prior":
        before = replace(before, container_id="f"*64)
    if change == "time":
        other["State"]["StartedAt"] = CREATED
    if change == "restart":
        other["RestartCount"] = 1
    rows = [terminal, other] if change == "sample" else [other, other]
    if change == "daemon":
        rows = [(other, (99,)), (other, (99,))]
    samples(monkeypatch, rows, [NOW + 5*10**9]*2)
    with pytest.raises(runtime.RuntimeObservationError):
        runtime.observe_exited(CID, policy, before)


def test_mount_inode_change_rejects(policy, monkeypatch):
    row = inspection(policy)
    samples(monkeypatch, [row, row])
    ids = iter(["a", "b"])
    monkeypatch.setattr(runtime, "_mount_sources", lambda _: next(ids))
    with pytest.raises(runtime.RuntimeObservationError, match="bind-source-changed"):
        runtime.observe_created(CID, policy)


def test_policy_supports_explicit_writable_output_binds_and_executable_tmpfs(policy, monkeypatch):
    writable = replace(policy, binds=(replace(policy.binds[0], read_only=False),),
                       tmpfs=(runtime.TmpfsMount("/chummer-output", "rw,exec,nosuid,nodev,size=1024,mode=700,uid=65534,gid=65534"),))
    row = inspection(policy)
    row["HostConfig"]["Binds"] = [policy.binds[0].source + ":/chummer-input:rw,rprivate"]
    row["HostConfig"]["Tmpfs"] = {"/chummer-output": writable.tmpfs[0].options}
    row["Mounts"][0].update(Mode="rw,rprivate", RW=True)
    samples(monkeypatch, [row, row])
    assert runtime.observe_created(CID, writable).phase == "created"


class WireSocket:
    def __init__(self, raw, step=8192, peer=(123, 0, 0), fail=None):
        self.raw, self.step, self.peer, self.fail = raw, step, peer, fail
        self.sent, self.paths, self.timeouts, self.closed = [], [], [], False
    def __enter__(self): return self
    def __exit__(self, *_): self.closed = True
    def settimeout(self, value): self.timeouts.append(value)
    def connect(self, value): self.paths.append(value)
    def getsockopt(self, *args): return struct.pack("3i", *self.peer)
    def sendall(self, value): self.sent.append(value)
    def recv(self, count):
        if self.fail: raise self.fail
        result, self.raw = self.raw[:min(count, self.step)], self.raw[min(count, self.step):]
        return result


def http(raw=b"{}", chunked=False):
    framing = b"Transfer-Encoding: chunked" if chunked else b"Content-Length: " + str(len(raw)).encode()
    body = (hex(len(raw))[2:].encode() + b"\r\n" + raw + b"\r\n0\r\n\r\n") if chunked else raw
    return b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" + framing + b"\r\n\r\n" + body


def transport(monkeypatch, connection, identities=((1, 2), (1, 2))):
    identities = iter(identities)
    monkeypatch.setattr(runtime, "_socket_identity", lambda: next(identities))
    monkeypatch.setattr(runtime.socket, "socket", lambda family, kind: connection)


@pytest.mark.parametrize("chunked", [False, True])
def test_fixed_request_ignores_all_endpoint_environment_and_closes(monkeypatch, chunked):
    for name in ("DOCKER_HOST", "DOCKER_API_VERSION", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, SECRET)
    connection = WireSocket(http(chunked=chunked), step=1)
    transport(monkeypatch, connection)
    result, identity = runtime._inspect(CID)
    assert result == {} and identity == (1, 2, 123) and connection.closed
    assert connection.paths == ["/run/docker.sock"]
    assert connection.sent == [("GET /v1.55/containers/" + CID + "/json HTTP/1.1\r\nHost: docker\r\nAccept: application/json\r\nConnection: close\r\n\r\n").encode()]


@pytest.mark.parametrize("cid", ["short", "a"*63, "A"*64, "../" + "a"*64, "a"*64 + "?size=1", True])
def test_container_identifier_rejects_before_socket(monkeypatch, cid):
    monkeypatch.setattr(runtime, "_socket_identity", lambda: pytest.fail("no socket before ID admission"))
    with pytest.raises(runtime.RuntimeObservationError): runtime._inspect(cid)


@pytest.mark.parametrize("raw", [b'{"Env":1,"Env":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e400}',
    b'[]', b'null', b'{', b'\xff', b'{"x":"\\ud800"}', b'{' + b'"x":['*0 + b'"x":' + b'['*40 + b'0' + b']'*40 + b'}'])
def test_strict_json_and_bounds_reject(monkeypatch, raw):
    connection = WireSocket(http(raw))
    transport(monkeypatch, connection)
    with pytest.raises(runtime.RuntimeObservationError): runtime._inspect(CID)
    assert connection.closed


@pytest.mark.parametrize("raw", [
    b"HTTP/1.1 500 secret\r\n\r\n" + SECRET.encode(),
    http().replace(b"application/json", b"text/html"), http().replace(b"Content-Length: 2", b"Content-Length: 2097153"),
    http().replace(b"Content-Length: 2", b"Content-Length: 02"),
    http().replace(b"Content-Length: 2", b"Content-Length: 2\r\nContent-Length: 2"),
    http().replace(b"Content-Length: 2", b"Content-Length: 2\r\nTransfer-Encoding: chunked"),
    http().replace(b"Content-Length: 2", b"Content-Encoding: gzip\r\nContent-Length: 2"),
    http()[:-1], http() + b"extra", http(chunked=True).replace(b"2\r\n{}", b"2;extension=x\r\n{}"),
    http(chunked=True).replace(b"0\r\n\r\n", b"0\r\nTrailer: secret\r\n\r\n"),
    b"HTTP/1.1 200 OK\r\nX: " + b"a"*16385,
])
def test_http_hostile_framing_is_bounded_and_sanitized(monkeypatch, raw):
    connection = WireSocket(raw)
    transport(monkeypatch, connection)
    with pytest.raises(runtime.RuntimeObservationError) as failure: runtime._inspect(CID)
    assert SECRET not in "".join(traceback.format_exception(failure.value)) and connection.closed


@pytest.mark.parametrize("where", ["header", "body"])
def test_slow_dribble_cannot_reset_total_deadline(monkeypatch, where):
    clock = [0.0]
    connection = WireSocket(http(b'{"public":"' + b'x'*100 + b'"}', chunked=where == "body"), step=1)
    original = connection.recv
    header_pending = [where == "body"]
    def slow(count):
        if header_pending[0]:
            header_pending[0] = False
            end = connection.raw.index(b"\r\n\r\n") + 4
            result, connection.raw = connection.raw[:end], connection.raw[end:]
            assert end <= count
            return result
        clock[0] += 1
        return original(count)
    connection.recv = slow
    transport(monkeypatch, connection)
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    with pytest.raises(runtime.RuntimeObservationError, match="deadline"):
        runtime._inspect(CID)
    assert clock[0] <= 5 and connection.closed


@pytest.mark.parametrize("peer,identities", [((1, 1000, 0), ((1,), (1,))), ((0, 0, 0), ((1,), (1,))),
    ((1, 0, 0), ((1,), (2,)))])
def test_root_peer_and_same_socket_are_required(monkeypatch, peer, identities):
    connection = WireSocket(http(), peer=peer)
    transport(monkeypatch, connection, identities)
    with pytest.raises(runtime.RuntimeObservationError): runtime._inspect(CID)
    assert connection.closed


def test_os_errors_never_disclose_daemon_body_or_env(monkeypatch):
    connection = WireSocket(http(), fail=OSError(SECRET))
    transport(monkeypatch, connection)
    with pytest.raises(runtime.RuntimeObservationError) as failure: runtime._inspect(CID)
    assert SECRET not in "".join(traceback.format_exception(failure.value))


@pytest.mark.parametrize("change", ["owner", "group", "world", "link", "ancestor", "canonical"])
def test_socket_path_owner_modes_and_ancestors(monkeypatch, change):
    metadata = {p: SimpleNamespace(st_dev=1, st_ino=i, st_mode=(stat.S_IFSOCK | 0o660) if p.endswith("sock") else stat.S_IFDIR | 0o755,
        st_uid=0, st_gid=999 if p.endswith("sock") else 0, st_mtime_ns=1, st_ctime_ns=1)
        for i, p in enumerate(("/", "/run", "/run/docker.sock"))}
    if change == "owner": metadata["/run/docker.sock"].st_uid = 1
    if change == "group": metadata["/run/docker.sock"].st_gid = 1
    if change == "world": metadata["/run/docker.sock"].st_mode = stat.S_IFSOCK | 0o666
    if change == "link": metadata["/run/docker.sock"].st_mode = stat.S_IFLNK | 0o777
    if change == "ancestor": metadata["/run"].st_mode = stat.S_IFDIR | 0o777
    monkeypatch.setattr(runtime.grp, "getgrnam", lambda _: SimpleNamespace(gr_gid=999))
    monkeypatch.setattr(runtime.os, "lstat", lambda p: metadata[p])
    monkeypatch.setattr(runtime.os.path, "realpath", lambda p: "/alias" if change == "canonical" else p)
    with pytest.raises(runtime.RuntimeObservationError): runtime._socket_identity()


def test_real_local_socketpair_http_framing_not_a_docker_probe():
    client, server = socket.socketpair()
    with client, server:
        server.sendall(http())
        server.shutdown(socket.SHUT_WR)
        assert runtime._response(client, runtime.time.monotonic() + 1) == b"{}"


def test_module_has_no_process_capability_or_mutation_imports():
    tree = ast.parse((ROOT / "scripts/android_container_runtime.py").read_text())
    modules = {item.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for item in node.names}
    assert modules <= {"grp", "hashlib", "json", "math", "os", "re", "socket", "stat", "struct", "time"}
    from_modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert from_modules <= {"__future__", "dataclasses", "datetime", "pathlib"}
    text = (ROOT / "scripts/android_container_runtime.py").read_text()
    assert "subprocess" not in text and "os.system" not in text and "http.client" not in text


def test_multiple_bind_projection_order_is_not_configuration_drift(policy, tmp_path, monkeypatch):
    other_source = tmp_path / "second-input"
    other_source.mkdir()
    combined = replace(policy, binds=policy.binds + (runtime.BindMount(str(other_source), "/second", True),))
    initial = inspection(policy)
    initial["HostConfig"]["Binds"].append(str(other_source) + ":/second:ro,rprivate")
    initial["Mounts"].append({"Type": "bind", "Source": str(other_source), "Destination": "/second",
                              "Mode": "ro,rprivate", "RW": False, "Propagation": "rprivate"})
    reordered = deepcopy(initial)
    reordered["Mounts"].reverse()
    terminal = deepcopy(reordered)
    terminal["State"].update(Status="exited", StartedAt=STARTED, FinishedAt=FINISHED)
    calls = samples(monkeypatch, [initial, reordered, terminal, terminal], [NOW, NOW, NOW + 4*10**9, NOW + 4*10**9])
    before = runtime.observe_created(CID, combined)
    after = runtime.observe_exited(CID, combined, before)
    assert len(calls) == 4 and before.configuration_sha256 == after.configuration_sha256


@pytest.mark.parametrize("container,field", [("Config", "Labels"), ("HostConfig", "ReadonlyRootfs"),
    ("HostConfig", "Devices"), ("State", "OOMKilled")])
def test_required_inspect_fields_are_not_filled_by_defaults(policy, container, field):
    row = inspection(policy)
    del row[container][field]
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, policy, "created", NOW)


@pytest.mark.parametrize("start,end", [
    (FINISHED, STARTED), (runtime.ZERO_TIME, FINISHED),
    (STARTED, "2026-09-13T10:00:09Z"), (STARTED, "2026-09-13T10:00:03.1234567890Z"),
    (STARTED, "2026-09-13T10:00:03+00:00"), (STARTED, "2026-13-13T10:00:03Z"),
])
def test_terminal_times_are_exact_ordered_and_not_future(policy, start, end):
    row = inspection(policy, "exited")
    row["State"].update(StartedAt=start, FinishedAt=end)
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, policy, "exited", NOW + 5*10**9)


def test_terminal_duration_is_bounded_by_admitted_policy(policy):
    row = inspection(policy, "exited")
    with pytest.raises(runtime.RuntimeObservationError):
        runtime._validate(row, CID, replace(policy, maximum_runtime_seconds=1), "exited", NOW + 5*10**9)


def test_real_local_socket_cannot_be_an_admitted_bind_source(policy):
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="cr-sock-") as directory:
        source = Path(directory) / "node"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as fixture:
            fixture.bind(str(source))
            changed = replace(policy, binds=(runtime.BindMount(str(source), "/input", True),))
            with pytest.raises(runtime.RuntimeObservationError, match="bind-source-type"):
                runtime._mount_sources(changed)


@pytest.mark.parametrize("initial_default", [False, None])
@pytest.mark.parametrize("terminal_default", [False, None])
def test_oom_default_lifecycle_is_semantic_not_raw_inspect_identity(policy, monkeypatch, initial_default, terminal_default):
    initial, terminal = inspection(policy), inspection(policy, "exited")
    initial["HostConfig"]["OomKillDisable"] = initial_default
    terminal["HostConfig"]["OomKillDisable"] = terminal_default
    second_initial, second_terminal = deepcopy(initial), deepcopy(terminal)
    second_initial["HostConfig"]["OomKillDisable"] = None if initial_default is False else False
    second_terminal["HostConfig"]["OomKillDisable"] = None if terminal_default is False else False
    calls = samples(monkeypatch, [initial, second_initial, terminal, second_terminal],
                    [NOW, NOW, NOW + 4*10**9, NOW + 4*10**9])
    before = runtime.observe_created(CID, policy)
    after = runtime.observe_exited(CID, policy, before)
    assert len(calls) == 4 and before.configuration_sha256 == after.configuration_sha256
    assert initial["HostConfig"]["OomKillDisable"] is initial_default
    assert terminal["HostConfig"]["OomKillDisable"] is terminal_default


@pytest.mark.parametrize("phase", ["created", "exited"])
@pytest.mark.parametrize("value", [True, 0, 0.0, "", "false", [], {}])
def test_oom_default_normalization_rejects_true_and_nonbooleans(policy, phase, value):
    row = inspection(policy, phase)
    row["HostConfig"]["OomKillDisable"] = value
    with pytest.raises(runtime.RuntimeObservationError, match="^host-config$"):
        runtime._validate(row, CID, policy, phase, NOW + 4*10**9)


@pytest.mark.parametrize("phase", ["created", "exited"])
def test_oom_default_field_must_still_be_present(policy, phase):
    row = inspection(policy, phase)
    del row["HostConfig"]["OomKillDisable"]
    with pytest.raises(runtime.RuntimeObservationError, match="^host-config-fields$"):
        runtime._validate(row, CID, policy, phase, NOW + 4*10**9)


@pytest.fixture
def multiple_binds(policy, tmp_path):
    second, third = tmp_path / "second", tmp_path / "third"
    second.mkdir()
    third.mkdir()
    combined = replace(policy, binds=policy.binds + (
        runtime.BindMount(str(second), "/second", True),
        runtime.BindMount(str(third), "/third", False),))
    row = inspection(policy)
    row["HostConfig"]["Binds"].extend([
        str(second) + ":/second:ro,rprivate", str(third) + ":/third:rw,rprivate"])
    row["Mounts"].extend([
        {"Type": "bind", "Source": str(second), "Destination": "/second",
         "Mode": "ro,rprivate", "RW": False, "Propagation": "rprivate"},
        {"Type": "bind", "Source": str(third), "Destination": "/third",
         "Mode": "rw,rprivate", "RW": True, "Propagation": "rprivate"},])
    return combined, row


@pytest.mark.parametrize("phase", ["created", "exited"])
def test_host_bind_reversal_preserves_exact_digest_and_raw_input(multiple_binds, phase):
    policy, row = multiple_binds
    if phase == "exited":
        row["State"].update(Status=phase, StartedAt=STARTED, FinishedAt=FINISHED)
    original = deepcopy(row)
    reversed_row = deepcopy(row)
    reversed_row["HostConfig"]["Binds"].reverse()
    reversed_input = deepcopy(reversed_row)
    assert runtime._validate(row, CID, policy, phase, NOW + 4*10**9) == \
        runtime._validate(reversed_row, CID, policy, phase, NOW + 4*10**9)
    assert row == original and reversed_row == reversed_input


@pytest.mark.parametrize("initial_order,terminal_order", [
    ((0, 1, 2), (2, 1, 0)), ((2, 1, 0), (0, 1, 2)), ((1, 2, 0), (2, 0, 1)),
])
def test_host_bind_orders_across_samples_and_completion_are_semantically_equal(
        multiple_binds, monkeypatch, initial_order, terminal_order):
    policy, row = multiple_binds
    initial, terminal = deepcopy(row), deepcopy(row)
    initial["HostConfig"]["Binds"] = [row["HostConfig"]["Binds"][i] for i in initial_order]
    terminal["HostConfig"]["Binds"] = [row["HostConfig"]["Binds"][i] for i in terminal_order]
    terminal["State"].update(Status="exited", StartedAt=STARTED, FinishedAt=FINISHED)
    second_initial, second_terminal = deepcopy(initial), deepcopy(terminal)
    second_initial["HostConfig"]["Binds"].reverse()
    second_terminal["HostConfig"]["Binds"].reverse()
    second_terminal["Mounts"].reverse()
    snapshots = [deepcopy(value) for value in (initial, second_initial, terminal, second_terminal)]
    calls = samples(monkeypatch, [initial, second_initial, terminal, second_terminal],
                    [NOW, NOW, NOW + 4*10**9, NOW + 4*10**9])
    before = runtime.observe_created(CID, policy)
    after = runtime.observe_exited(CID, policy, before)
    assert calls == [CID] * 4 and before.configuration_sha256 == after.configuration_sha256
    assert [initial, second_initial, terminal, second_terminal] == snapshots


@pytest.mark.parametrize("phase", ["created", "exited"])
@pytest.mark.parametrize("change", [
    "absent", "null", "empty", "missing", "extra", "duplicate-extra", "duplicate-replacement",
    "tuple", "string", "null-row", "number-row", "bool-row", "dict-row", "list-row",
    "empty-row", "wrong-source", "wrong-target", "wrong-mode", "missing-mode",
    "reordered-mode", "wrong-propagation", "dot-segment", "trailing-space", "control",
])
def test_host_bind_multiset_rejects_missing_extra_duplicate_or_changed_strings(multiple_binds, phase, change):
    policy, row = multiple_binds
    if phase == "exited":
        row["State"].update(Status=phase, StartedAt=STARTED, FinishedAt=FINISHED)
    host, binds = row["HostConfig"], row["HostConfig"]["Binds"]
    if change == "absent": del host["Binds"]
    elif change == "null": host["Binds"] = None
    elif change == "empty": host["Binds"] = []
    elif change == "missing": binds.pop()
    elif change == "extra": binds.append("/extra:/extra:ro,rprivate")
    elif change == "duplicate-extra": binds.append(binds[0])
    elif change == "duplicate-replacement": binds[-1] = binds[0]
    elif change == "tuple": host["Binds"] = tuple(binds)
    elif change == "string": host["Binds"] = binds[0]
    elif change == "null-row": binds[0] = None
    elif change == "number-row": binds[0] = 0
    elif change == "bool-row": binds[0] = False
    elif change == "dict-row": binds[0] = {"source": "not-a-bind"}
    elif change == "list-row": binds[0] = [binds[0]]
    elif change == "empty-row": binds[0] = ""
    elif change == "wrong-source": binds[0] = "/other:/chummer-input:ro,rprivate"
    elif change == "wrong-target": binds[0] = binds[0].replace(":/chummer-input:", ":/other:")
    elif change == "wrong-mode": binds[0] = binds[0].replace(":ro,", ":rw,")
    elif change == "missing-mode": binds[0] = binds[0].removesuffix(":ro,rprivate")
    elif change == "reordered-mode": binds[0] = binds[0].replace(":ro,rprivate", ":rprivate,ro")
    elif change == "wrong-propagation": binds[0] = binds[0].replace("rprivate", "rshared")
    elif change == "dot-segment": binds[0] = binds[0].replace(":/chummer-input:", ":/./chummer-input:")
    elif change == "trailing-space": binds[0] += " "
    elif change == "control": binds[0] += "\n"
    else: pytest.fail("unknown test mutation")
    with pytest.raises(runtime.RuntimeObservationError, match="^host-binds$"):
        runtime._validate(row, CID, policy, phase, NOW + 4*10**9)
