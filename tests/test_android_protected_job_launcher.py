"""Real private files/framing flow; Docker, kernel and physical mounts modeled."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from scripts import android_protected_job_launcher as launcher
from scripts import android_container_runtime as runtime
from scripts import android_protected_job_worker as worker
from scripts import android_protected_capture_intake as intake
import test_android_protected_capture_intake as transfer
from test_android_protected_capture_intake import model, exported, flow, store, signing_key
from test_android_protected_job_freshness import ready


def policy():
    return runtime.RuntimePolicy("sha256:" + "a" * 64, "ghcr.io/public/test@sha256:" + "b" * 64,
        "0:0", "/", ("/usr/bin/python3",), (), launcher.PUBLIC_ENVIRONMENT,
        runtime.ResourceLimits(128 * 1024**2, 250000000, 64), process_role="signer")


@pytest.mark.parametrize("entry", ["LD_PRELOAD=PUBLIC-TEST-secret", "PYTHONPATH=PUBLIC-TEST-secret",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN=PUBLIC-TEST-secret", "BEARER=PUBLIC-TEST-secret", "HOME=/root", "PATH=/unsafe"])
def test_closed_environment_rejects_before_custody_or_any_intent(tmp_path, monkeypatch, entry):
    selected = replace(policy(), environment=(*launcher.PUBLIC_ENVIRONMENT, entry)) if not entry.startswith("PATH=") else replace(
        policy(), environment=(entry, *launcher.PUBLIC_ENVIRONMENT[1:]))
    monkeypatch.setattr(launcher.os, "getuid", lambda: pytest.fail("environment rejection must precede custody"))
    with pytest.raises(worker.JobError):
        launcher.ProtectedJobLauncher(config={}, policy=selected, docker=None, persistent=None,
            operation_directory=tmp_path / "intent", secret_inputs={}, binary_bearer="PUBLIC-TEST-secret", connection=None)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("attack", [None, "digest", "ephemeral", "nested", "shared", "readonly", "inode"])
def test_recovery_requires_exact_real_mount_row_and_one_parent(tmp_path, monkeypatch, attack):
    for name in ("recovery", "outputs", "operations"): (tmp_path / name).mkdir(mode=0o700)
    def private(path):
        assert path.is_dir() and path.resolve() == path and path.stat().st_mode & 0o777 == 0o700
    monkeypatch.setattr(intake, "_root_directory", private)  # Only UID0 boundary modeled.
    row = f"70 1 0:70 / {tmp_path} rw - ext4 /dev/test rw".encode().split()
    digest = hashlib.sha256(b" ".join(row)).hexdigest()
    rows = [row]
    if attack == "digest": digest = "a" * 64
    elif attack == "ephemeral": row[7] = b"tmpfs"
    elif attack == "nested": rows.append(f"71 70 0:71 / {tmp_path}/outputs rw - ext4 /dev/test rw".encode().split())
    elif attack == "shared": row.insert(6, b"shared:1")
    elif attack == "readonly": row[5] = b"ro"
    monkeypatch.setattr(launcher, "mount_rows", lambda: rows)
    if attack not in {None, "inode"}:
        with pytest.raises(worker.JobError): launcher.RecoveryMount(tmp_path, digest)
    else:
        admitted = launcher.RecoveryMount(tmp_path, digest)
        if attack == "inode":
            admitted._stamp = (0, *admitted._stamp[1:])
            with pytest.raises(worker.JobError): admitted.assert_exact()
        else: admitted.assert_exact()  # Does NOT qualify physical durability.


@pytest.mark.parametrize("failure", ["success", "unknown-operation", "reconcile-secret", "wrong-peer", "pid-reuse",
    "created-rejected", "foreign-id", "foreign-name", "foreign-image", "foreign-requested-image",
    "foreign-labels", "foreign-daemon", "identity-lost-after-stop"])
def test_owned_launch_revokes_ledger_before_blocking_cleanup_and_never_reads_keys(exported, monkeypatch, failure):
    client, captured = ready(exported, monkeypatch)
    base = exported.flow.tmp_path
    names = ("durable", "control", "requests", "responses", "code", "source", "authority", "dotnet", "java", "sdk")
    paths = {name: base / name for name in names}
    for path in paths.values(): path.mkdir(mode=0o700)
    for name in ("recovery", "outputs", "operations"): (paths["durable"] / name).mkdir(mode=0o700)
    own = launcher.ProtectedJobLauncher.__new__(launcher.ProtectedJobLauncher)
    own.used, own.connection, own.root, own.pins = False, client, paths["code"], {}
    own.config = {"mode": "reconcile", "attempt": client._job.transaction_id, "code_pins": {},
        "handoff": str(captured.retained.artifact_subject_path.parent), "requests": str(paths["requests"]),
        "responses": str(paths["responses"]), "socket": str(paths["control"] / "s"), "credentials": "/private-keys",
        "recovery": str(paths["durable"] / "recovery"), "output": str(paths["durable"] / "outputs" / "final"),
        "validation": {"workspace_root": str(paths["source"]), "authority_root": str(paths["authority"]),
                       "dotnet_root": str(paths["dotnet"]), "java_root": str(paths["java"]), "android_sdk_root": str(paths["sdk"])}}
    own.lock_raw = exported.flow.model.lock.path.read_bytes()
    own.lock = {"reservation": {"policy_sha256": "a" * 64}}
    own.validation = SimpleNamespace(_bindings={"source_graph": captured.retained.handoff["bindings"]["sourceGraphSha256"]})
    own.persistent = SimpleNamespace(parent=paths["durable"], assert_exact=lambda: None)
    own.operation = paths["durable"] / "operations" / "once"
    own.secrets, own.bearer, own.daemon = {}, "PUBLIC-TEST-binary-bearer", (1, 2)
    roots = {paths[key] for key in ("code", "source", "authority", "dotnet", "java", "sdk", "control", "responses")}
    roots.add(captured.retained.artifact_subject_path.parent)
    own.policy = replace(policy(), binds=tuple(runtime.BindMount(str(path), str(path), True) for path in roots)
        + tuple(runtime.BindMount(str(paths[key]), str(paths[key]), False) for key in ("durable", "requests")),
        tmpfs=(runtime.TmpfsMount("/private-keys", "rw,nosuid,nodev,noexec,size=1048576,mode=0700,uid=0,gid=0"),))
    monkeypatch.setattr(worker, "code_inputs", lambda *_: {})
    ledger_client = SimpleNamespace(policy={"timeout_seconds": 1})
    monkeypatch.setattr(worker, "ledger_inputs", lambda *_: (None, ledger_client, {}, None))
    sends, commands, brokers = [], [], []
    class Broker:
        def __init__(self, *_args, **kwargs): self.transport = kwargs["https_transport"]; brokers.append(self)
        def serve_once(self): return False
    monkeypatch.setattr(launcher.bridge, "ControllerBroker", Broker)
    monkeypatch.setattr(launcher.bridge.protocol, "_https_transport", lambda *_: sends.append("FORBIDDEN"))
    cid = "a" * 64
    def command(arguments, *_args, **_kwargs):
        commands.append(arguments)
        if arguments[0] in {"stop", "wait"}:
            # Model a ready request reaching the HTTP admission boundary while
            # Docker cleanup is still blocked. Revocation must ALREADY apply.
            with pytest.raises(worker.JobError): brokers[0].transport("fixed", b"public", {}, 1)
        if arguments[0] == "wait": return b"0\n"
        return (cid + "\n").encode()
    monkeypatch.setattr(own, "_command", command)
    monkeypatch.setattr(runtime, "_mount_sources", lambda *_: "same")
    early = failure.startswith("foreign-") or failure in {"created-rejected", "identity-lost-after-stop"}
    def created(*_):
        if early: raise runtime.RuntimeObservationError("modeled-created-rejection")
        return SimpleNamespace(socket_identity=(1, 2, 3))
    monkeypatch.setattr(runtime, "observe_created", created)
    monkeypatch.setattr(runtime, "observe_exited", lambda *_: runtime.RuntimeObservation(
        cid, own.policy.image_id, "a" * 64, "b" * 64, "c" * 64, "exited", "", "", "", "", (1, 2, 3), "d" * 64))
    def inspect(_):
        arguments = commands[0]
        name = arguments[arguments.index("--name") + 1]
        value = {"Id": cid, "Name": "/" + name, "Image": own.policy.image_id,
                 "Config": {"Image": own.policy.requested_image, "Labels": dict(own.policy.labels)}}
        daemon = (1, 2, 3)
        if failure == "foreign-id": value["Id"] = "b" * 64
        elif failure == "foreign-name": value["Name"] = "/another-owned-container"
        elif failure == "foreign-image": value["Image"] = "sha256:" + "c" * 64
        elif failure == "foreign-requested-image": value["Config"]["Image"] = "other"
        elif failure == "foreign-labels": value["Config"]["Labels"] = {"foreign": "true"}
        elif failure == "foreign-daemon": daemon = (1, 9, 3)
        elif failure == "identity-lost-after-stop" and any(row[0] == "stop" for row in commands):
            value["Name"] = "/changed"
        return value, daemon
    monkeypatch.setattr(runtime, "_inspect", inspect)
    sample_count = [0]
    def sample(*_args, **_kwargs):
        sample_count[0] += 1
        return SimpleNamespace(pid=4321, start_ticks=2 if failure == "pid-reuse" and sample_count[0] > 1 else 1, started_at="same")
    monkeypatch.setattr(launcher.signer, "observe_running_signer", sample)
    monkeypatch.setattr(launcher.os, "pidfd_open", lambda _: os.open("/dev/null", os.O_RDONLY))
    monkeypatch.setattr(launcher.select, "select", lambda *_: ([], [], []))
    actual_stat = os.stat
    monkeypatch.setattr(launcher.os, "stat", lambda path, *args, **kwargs: actual_stat("/proc/self/ns/time")
                        if str(path) == "/proc/4321/ns/time" else actual_stat(path, *args, **kwargs))
    class Socket:
        def bind(self, name): Path(name).touch(mode=0o600)  # Kernel socket inode modeled.
        def listen(self, _): pass
        def settimeout(self, _): pass
        def accept(self): return self, None
        def getsockopt(self, *_): return struct.pack("3i", 4322 if failure == "wrong-peer" else 4321, 0, 0)
        def close(self): pass
    monkeypatch.setattr(launcher, "socket", SimpleNamespace(socket=lambda *_: Socket(),
        **{name: getattr(launcher.socket, name) for name in ("AF_UNIX", "SOCK_STREAM", "SOL_SOCKET", "SO_PEERCRED")}))
    request = {"sequence": 0, "operation": "unknown"}
    if failure == "reconcile-secret": request.update(operation="secret", name=launcher.credentials.BUILDER_SECRET)
    if failure == "success": request["operation"] = "done"
    monkeypatch.setattr(worker, "receive", lambda _: request)
    replies = []
    monkeypatch.setattr(worker, "send", lambda _, value: replies.append(value))
    if failure == "success":
        output = Path(own.config["output"])
        output.mkdir(mode=0o700)
        worker.fleet._write_exclusive(output / "FLEET_ANDROID_PREVIEW12_EXTERNAL_REBUILD_AUDIT.v3.json", b'{"modeled":true}\n')
        assert own.launch(captured) == {"modeled": True}  # Lifecycle only, not actual signed artifacts.
        assert len(replies) == 1 and replies[0]["value"] is None
    else:
        with pytest.raises(worker.JobError): own.launch(captured)
        assert not replies
    expected = (["create", "start", "wait", "rm"] if failure == "success" else
                ["create"] if failure.startswith("foreign-") else
                ["create", "stop"] if failure == "identity-lost-after-stop" else
                ["create", "stop", "rm"] if early else ["create", "start", "stop", "rm"])
    assert [row[0] for row in commands] == expected and not sends
    assert (own.operation / "intent.json").exists() and (own.operation / "container.json").exists()
    with pytest.raises(worker.JobError): own.launch(captured)
