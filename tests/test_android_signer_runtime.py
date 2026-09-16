"""Modeled kernel/daemon data only; never Docker, credentials or live custody."""
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from scripts import android_container_runtime as runtime
from scripts import android_signer_runtime as signer
from test_android_container_runtime import CID, IMAGE, CREATED, STARTED, NOW, inspection, policy


@pytest.fixture
def admitted(policy):
    selected = replace(policy, user="0:0", process_role="signer",
                       tmpfs=(runtime.TmpfsMount("/chummer-output", "rw,noexec,nosuid,nodev,size=1048576,mode=700"),))
    row = inspection(selected)
    row["Config"]["User"] = "0:0"
    row["HostConfig"]["Tmpfs"] = {mount.target: mount.options for mount in selected.tmpfs}
    configuration = runtime._configuration(row, CID, selected)
    created = runtime.RuntimeObservation(CID, IMAGE, "d" * 64, runtime._digest(runtime.asdict(selected)),
        configuration, "created", CREATED, runtime.ZERO_TIME, runtime.ZERO_TIME,
        "2026-09-13T10:00:01Z", (10, 20, 30), runtime._mount_sources(selected))
    row["State"].update(Status="running", Running=True, Pid=4321, StartedAt=STARTED)
    return selected, created, row


def model(monkeypatch, admitted, *, rows=None, kernels=None):
    selected, created, row = admitted
    calls = []
    stream = iter(rows or [row] * 4)
    def inspect(cid):
        calls.append(cid)
        return deepcopy(next(stream)), created.socket_identity
    monkeypatch.setattr(runtime, "_inspect", inspect)
    monkeypatch.setattr(signer.time, "time_ns", lambda: NOW + 3 * 10**9)
    facts = iter(kernels or [(7, ("kernel-metadata",), {"/chummer-output": (1, 2)})] * 2)
    monkeypatch.setattr(signer, "_kernel", lambda *_: next(facts))
    return calls


def observe(admitted):
    return signer.observe_running_signer(CID, admitted[0], admitted[1], credential_targets=("/chummer-output",))


def test_two_fenced_live_samples_return_only_non_authoritative_metadata(admitted, monkeypatch):
    calls = model(monkeypatch, admitted)
    result = observe(admitted)
    assert calls == [CID] * 4 and result.pid == 4321 and result.start_ticks == 7
    assert result.protected_signer_runtime_verified is False
    assert not hasattr(result, "provenance") and not hasattr(result, "credentials")
    assert "PATH" not in repr(result) and "kernel-metadata" not in repr(result)


@pytest.mark.parametrize("change", ("pid", "restart", "exit", "image", "configuration", "start-time", "root-rw", "network"))
def test_running_configuration_or_process_drift_rejects(admitted, monkeypatch, change):
    row = deepcopy(admitted[2])
    if change == "pid": row["State"]["Pid"] = 4322
    elif change == "restart": row["RestartCount"] = 1
    elif change == "exit": row["State"].update(Status="exited", Running=False, Pid=0)
    elif change == "image": row["Image"] = "sha256:" + "0" * 64
    elif change == "configuration": row["Config"]["User"] = "1000:1000"
    elif change == "start-time": row["State"]["StartedAt"] = "2026-09-13T10:00:03Z"
    elif change == "root-rw": row["HostConfig"]["ReadonlyRootfs"] = False
    else: row["HostConfig"]["NetworkMode"] = "host"
    model(monkeypatch, admitted, rows=[admitted[2], row])
    with pytest.raises(signer.SignerObservationError): observe(admitted)


@pytest.mark.parametrize("change", ("ticks", "mount", "credential-root", "permission"))
def test_kernel_drift_or_unreadable_metadata_never_succeeds(admitted, monkeypatch, change):
    first = (7, ("same",), {"/chummer-output": (1, 2)})
    second = (8, first[1], first[2]) if change == "ticks" else (
        7, ("replacement",) if change == "mount" else first[1],
        {"/chummer-output": (1, 3)} if change == "credential-root" else first[2])
    model(monkeypatch, admitted, kernels=[first, second])
    if change == "permission":
        def denied(*_): raise PermissionError("private kernel diagnostic")
        monkeypatch.setattr(signer, "_kernel", denied)
    with pytest.raises(signer.SignerObservationError) as error: observe(admitted)
    assert "private" not in str(error.value)


@pytest.mark.parametrize("targets", ((), ["/chummer-output"], ("/missing",), ("/chummer-output", "/chummer-output")))
def test_bad_credential_scope_rejects_before_inspect(admitted, monkeypatch, targets):
    monkeypatch.setattr(runtime, "_inspect", lambda *_: pytest.fail("no inspect before admission"))
    with pytest.raises(signer.SignerObservationError):
        signer.observe_running_signer(CID, admitted[0], admitted[1], credential_targets=targets)


def test_builder_role_cannot_be_relabelled_as_live_signer(admitted, monkeypatch):
    monkeypatch.setattr(runtime, "_inspect", lambda *_: pytest.fail("no inspect before role validation"))
    with pytest.raises(signer.SignerObservationError):
        signer.observe_running_signer(CID, replace(admitted[0], process_role="builder", user="1000:1000"),
                                      admitted[1], credential_targets=("/chummer-output",))


def status(pid=4321):
    return ("Uid:\t0\t0\t0\t0\nGid:\t0\t0\t0\t0\n" +
            "".join(name + ":\t0000000000000000\n" for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")) +
            f"NoNewPrivs:\t1\nSeccomp:\t2\nNSpid:\t{pid}\t1\n")


@pytest.mark.parametrize("old,new", (("Uid:\t0\t0\t0\t0", "Uid:\t0\t1000\t0\t0"),
    ("Gid:\t0\t0\t0\t0", "Gid:\t0\t1\t0\t0"), ("CapEff:\t0000000000000000", "CapEff:\t0000000000000001"),
    ("NoNewPrivs:\t1", "NoNewPrivs:\t0"), ("Seccomp:\t2", "Seccomp:\t0"), ("NSpid:\t4321\t1", "NSpid:\t4321")))
def test_actual_status_owner_capabilities_namespace_guards(old, new):
    signer._status(status(), 4321)
    with pytest.raises(signer.SignerObservationError): signer._status(status().replace(old, new), 4321)


def test_stat_parser_uses_kernel_start_ticks_not_process_name():
    value = "4321 (name with ) brackets) " + " ".join(["S"] + ["0"] * 18 + ["77"])
    assert signer._start(value, 4321) == 77
    with pytest.raises(signer.SignerObservationError): signer._start(value, 4322)
    with pytest.raises(signer.SignerObservationError): signer._start(value.replace(" S ", " Z "), 4321)


def mounts(policy):
    paths = [("/", "ro", "overlay"), ("/proc", "rw", "proc"), ("/dev", "rw", "tmpfs"),
        ("/dev/pts", "rw", "devpts"), ("/dev/mqueue", "rw", "mqueue"), ("/dev/shm", "rw", "tmpfs"),
        ("/sys", "ro", "sysfs"), ("/sys/fs/cgroup", "ro", "cgroup2"),
        ("/etc/hosts", "rw", "ext4"), ("/etc/hostname", "rw", "ext4"), ("/etc/resolv.conf", "rw", "ext4")]
    paths += [(target, "ro", "proc") for target in runtime.READONLY]
    paths += [(row.target, "ro" if row.read_only else "rw", "ext4") for row in policy.binds]
    paths += [(row.target, "rw,nosuid,nodev,noexec", "tmpfs") for row in policy.tmpfs]
    return "".join(f"{index} 1 0:{index} / {path} {options} - {kind} none rw\n"
                   for index, (path, options, kind) in enumerate(paths, 10))


@pytest.mark.parametrize("change", ("root-rw", "nested", "unknown", "alias", "bind-rw", "shared", "tmpfs-exec", "kernel-rw"))
def test_actual_mount_table_rejects_bad_modes_aliases_and_unknown_nested_mounts(admitted, change):
    text = mounts(admitted[0])
    assert signer._mountinfo(text, admitted[0])
    if change == "root-rw": text = text.replace(" / ro - overlay", " / rw - overlay")
    elif change == "nested": text += "99 1 0:99 / /chummer-input/nested ro - tmpfs none rw\n"
    elif change == "unknown": text += "99 1 0:99 / /surprise ro - tmpfs none rw\n"
    elif change == "alias": text += "99 1 0:99 / /chummer-input ro - tmpfs none rw\n"
    elif change == "bind-rw": text = text.replace("/chummer-input ro", "/chummer-input rw")
    elif change == "shared": text = text.replace("/chummer-input ro -", "/chummer-input ro shared:3 -")
    elif change == "kernel-rw": text = text.replace("/proc/sys ro", "/proc/sys rw")
    else: text = text.replace("rw,nosuid,nodev,noexec", "rw,nosuid,nodev")
    with pytest.raises(signer.SignerObservationError): signer._mountinfo(text, admitted[0])


@pytest.mark.parametrize("missing", runtime.READONLY)
def test_configured_readonly_kernel_overmount_cannot_be_missing(admitted, missing):
    text = "\n".join(line for line in mounts(admitted[0]).splitlines() if line.split()[4] != missing) + "\n"
    with pytest.raises(signer.SignerObservationError, match="mount-readonly-kernel"):
        signer._mountinfo(text, admitted[0])


@pytest.mark.parametrize("change", (None, "cpu", "memory", "swap", "pids", "membership", "alias", "v1", "foreign-container"))
def test_actual_cgroup_values_are_exact(admitted, monkeypatch, change):
    values = {"cpu.max": "25000 100000\n", "memory.max": "67108864\n", "memory.swap.max": "0\n",
              "pids.max": "32\n", "cgroup.procs": "4321\n"}
    for defect, name, value in (("cpu", "cpu.max", "max 100000"), ("memory", "memory.max", "max"),
            ("swap", "memory.swap.max", "1"), ("pids", "pids.max", "33"), ("membership", "cgroup.procs", "4322")):
        if change == defect: values[name] = value
    monkeypatch.setattr(signer, "_read", lambda path, _: values[path.name])
    monkeypatch.setattr(signer, "_chain", lambda _: ("fixed",))
    monkeypatch.setattr(Path, "lstat", lambda _: SimpleNamespace(st_dev=1, st_ino=2, st_mode=stat.S_IFDIR | 0o755,
                                                               st_uid=0, st_gid=0, st_nlink=2))
    text = "0::/docker/" + CID + "\n"
    if change == "alias": text = "0::/docker/../other\n"
    if change == "v1": text = "2:cpu:/docker/owned\n"
    if change == "foreign-container": text = "0::/docker/" + "f" * 64 + "\n"
    if change is None:
        signer._cgroup(text, admitted[0], 4321, CID)
    else:
        with pytest.raises(signer.SignerObservationError): signer._cgroup(text, admitted[0], 4321, CID)


@pytest.mark.parametrize("defect", (None, "reused-pid", "shared-net", "bind-replaced", "aliased-roots", "credential-mode", "cgroup-mount"))
def test_kernel_snapshot_binds_process_targets_and_credential_root_metadata(admitted, tmp_path, monkeypatch, defect):
    selected = admitted[0]
    source = signer._identity(Path(selected.binds[0].source).lstat())
    group = (3, 4, stat.S_IFDIR | 0o755, 0, 0, 2)
    credentials = (5, 6, stat.S_IFDIR | 0o700, 0, 0, 2)
    if defect == "credential-mode": credentials = (5, 6, stat.S_IFDIR | 0o755, 0, 0, 2)
    if defect == "aliased-roots": credentials = source
    targets = {"/chummer-input": source, "/chummer-output": credentials, "/sys/fs/cgroup": group}
    if defect == "bind-replaced": targets["/chummer-input"] = (99, *source[1:])
    if defect == "cgroup-mount": targets["/sys/fs/cgroup"] = (99, *group[1:])
    reads, stat_reads = [], []
    def read(path, limit):
        reads.append(str(path))
        assert str(path).startswith("/proc/4321/")
        if path.name == "stat":
            stat_reads.append(path)
            ticks = "8" if defect == "reused-pid" and len(stat_reads) == 2 else "7"
            return "4321 (synthetic) " + " ".join(["S"] + ["0"] * 18 + [ticks])
        return {"status": status(), "cgroup": "0::/docker/" + CID + "\n", "mountinfo": mounts(selected)}[path.name]
    monkeypatch.setattr(signer, "_read", read)
    monkeypatch.setattr(signer, "_chain", lambda _: ("owned-proc",))
    monkeypatch.setattr(signer, "_cgroup", lambda *_: (("owned-cgroup",), {}, group))
    monkeypatch.setattr(signer, "_target", lambda _, target: targets[target])
    original_stat, original_open = os.stat, os.open
    def kernel_stat(path, *args, **kwargs):
        if str(path).startswith(("/proc/4321/ns/", "/proc/self/ns/")):
            host = str(path).startswith("/proc/self/") or defect == "shared-net" and Path(path).name == "net"
            return SimpleNamespace(st_dev=10, st_ino=11 if host else 12)
        return original_stat(path, *args, **kwargs)
    monkeypatch.setattr(os, "stat", kernel_stat)
    monkeypatch.setattr(os, "open", lambda path, *args, **kwargs:
                        original_open(tmp_path if str(path) == "/proc/4321/root" else path, *args, **kwargs))
    if defect is None:
        result = signer._kernel(4321, selected, ("/chummer-output",), CID)
        assert result[0] == 7 and result[2] == {"/chummer-output": credentials}
    else:
        with pytest.raises(signer.SignerObservationError):
            signer._kernel(4321, selected, ("/chummer-output",), CID)
    assert all(Path(path).name in {"stat", "status", "cgroup", "mountinfo"} for path in reads)


def test_target_walk_is_metadata_only_and_rejects_symlinks(tmp_path):
    folder = tmp_path / "keys"
    folder.mkdir(mode=0o700)
    (tmp_path / "alias").symlink_to(folder, target_is_directory=True)
    fd = os.open(tmp_path, os.O_PATH | os.O_DIRECTORY)
    try:
        assert signer._target(fd, "/keys") == signer._identity(folder.stat())
        with pytest.raises(signer.SignerObservationError): signer._target(fd, "/alias")
    finally:
        os.close(fd)


def test_metadata_read_is_bounded_and_closes_fd_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-kernel-value"
    path.write_bytes(b"12345")
    original_lstat, original_fstat, original_close = Path.lstat, os.fstat, os.close
    def owned(value):
        row = list(value)
        row[4] = 0
        return os.stat_result(row)
    monkeypatch.setattr(Path, "lstat", lambda value: owned(original_lstat(value)))
    monkeypatch.setattr(os, "fstat", lambda fd: owned(original_fstat(fd)))
    closed = []
    monkeypatch.setattr(os, "close", lambda fd: (closed.append(fd), original_close(fd))[-1])
    assert signer._read(path, 5) == "12345"
    with pytest.raises(signer.SignerObservationError, match="kernel-read-bound"): signer._read(path, 4)
    assert len(closed) == 2
