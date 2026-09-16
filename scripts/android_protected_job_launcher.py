"""Owner-admitted protected GitHub-job launcher of the existing transaction.

SOURCE ONLY: importing is inert. The owner must admit code/image/daemon, exact
job and TLS policy, persistent filesystem and protected-job secret inputs. This
does not provision those authorities, activate a workflow or accept HTTP flags.
The ordinary local builder controller never receives these job-local secrets.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
import select
import secrets
import socket
import stat
import struct
import threading
import time

from scripts import android_artifact_origin as origin
from scripts import android_container_runtime as runtime
from scripts import android_isolated_builder as docker_owner
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_preview12_ledger_bridge as bridge
from scripts import android_preview12_signer_credentials as credentials
from scripts import android_protected_capture_intake as intake
from scripts import android_protected_job_worker as worker
from scripts import android_signer_runtime as signer

require = worker.require
PUBLIC_ENVIRONMENT = ("PATH=/usr/bin:/bin", "APP_UID=1654", "ASPNETCORE_HTTP_PORTS=8080",
    "DOTNET_RUNNING_IN_CONTAINER=true", "DOTNET_ROOT=/opt/dotnet", "JAVA_HOME=/opt/jdk",
    "ANDROID_HOME=/opt/android-sdk", "DOTNET_CLI_TELEMETRY_OPTOUT=1")


def mount_rows():
    with Path("/proc/self/mountinfo").open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    require(len(raw) <= 1024 * 1024)
    return [line.split() for line in raw.splitlines()]


class RecoveryMount:
    """An ACTUAL independently admitted mount; never a durability boolean.

    expected_row_sha256 pins an externally reviewed current mountinfo row.
    Matching it does not qualify persistence: owner must separately prove stable
    storage, fsync/rename/remount behavior, private UID mapping and exclusivity.
    ONE parent bind contains both directories; never separate sibling binds.
    """
    def __init__(self, parent, expected_row_sha256):
        require(type(parent) is type(Path()) and fleet.HEX64.fullmatch(expected_row_sha256))
        self.parent, self.digest = parent, expected_row_sha256
        self._stamp = None
        self.assert_exact()
        self._stamp = self.identity()

    def identity(self):
        value = self.parent.lstat()
        return value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid

    def assert_exact(self):
        intake._root_directory(self.parent)
        rows = [row for row in mount_rows() if len(row) >= 10 and row[4] == os.fsencode(self.parent)]
        require(len(rows) == 1)
        row = rows[0]
        split = row.index(b"-")
        require(row[split + 1] in {b"ext4", b"xfs", b"nfs4"} and b"rw" in row[5].split(b",")
                and not any(value.startswith((b"shared:", b"master:", b"propagate_from:")) for value in row[6:split])
                and hashlib.sha256(b" ".join(row)).hexdigest() == self.digest
                and (self._stamp is None or self.identity() == self._stamp))
        # No nested mounts can break the one-filesystem atomic rename.
        require(not any(len(peer) >= 5 and peer[4].startswith(os.fsencode(self.parent) + b"/") for peer in mount_rows()))
        for name in ("recovery", "outputs", "operations"):
            intake._root_directory(self.parent / name)
            require((self.parent / name).stat().st_dev == self.parent.stat().st_dev)


class ProtectedJobLauncher:
    """Prepare key-free inputs BEFORE the owner arms job3's one challenge.

    All parameters are independently admitted protected-job inputs, not build
    output or an HTTP request. No method chooses endpoints/policies from files
    received from the candidate. A new invocation cannot adopt an old intent.
    """
    def __init__(self, *, config, policy, docker, persistent, operation_directory,
                 secret_inputs, binary_bearer, connection):
        require(type(policy) is runtime.RuntimePolicy
                and tuple(sorted(policy.environment)) == tuple(sorted(PUBLIC_ENVIRONMENT)))
        require(os.getuid() == os.geteuid() == 0 and type(config) is dict
                and type(policy) is runtime.RuntimePolicy and type(docker) is origin.PinnedFile
                and type(persistent) is RecoveryMount)
        require(type(connection) is intake.PublicCaptureClient and not connection._begun
                and not connection._failed and connection._job.environment == "android-preview12-release-builder")
        self.connection = connection
        expected = {"mode", "attempt", "artifact_id", "artifact_sha256", "fleet_root", "lock", "handoff",
                    "validation", "recovery", "output", "requests", "responses", "credentials", "socket", "code_pins"}
        require(set(config) == expected and config["mode"] in {"execute", "reconcile"}
                and fleet.HEX64.fullmatch(config["attempt"]) and fleet.HEX64.fullmatch(config["artifact_sha256"])
                and type(config["artifact_id"]) is int and config["artifact_id"] > 0)
        require(connection._job.transaction_id == config["attempt"])
        self.config = fleet._strict_json(fleet._canonical_json(config), "owner job inputs")
        self.root, self.lock_path = Path(config["fleet_root"]), Path(config["lock"])
        self.lock, self.lock_raw = fleet.load_lock(self.lock_path)
        require(not fleet.validate_lock(self.lock, self.lock_raw))
        self.pins = worker.code_inputs(self.root, config["code_pins"])
        self.validation = fleet.PreservedProtectedValidation(self.lock_path,
            **{name: Path(value) for name, value in config["validation"].items()})
        self.persistent = persistent
        persistent.assert_exact()
        require(config["recovery"] == str(persistent.parent / "recovery")
                and config["output"] == str(persistent.parent / "outputs" / config["attempt"])
                and operation_directory.parent == persistent.parent / "operations")
        # Configuration, credentials and IPC are NEVER placed on recovery/NFS.
        for name in ("requests", "responses", "socket"):
            path = Path(config[name])
            require(not path.is_relative_to(persistent.parent))
            intake._root_directory(path.parent if name == "socket" else path)
        self.secrets, self.secret_stamps = dict(secret_inputs or {}), {}
        require(set(self.secrets) == (set(credentials.SECRET_NAMES) if config["mode"] == "execute" else set()))
        for name, path in self.secrets.items():
            require(type(path) is type(Path()) and path.resolve(strict=True) == path
                    and not path.is_relative_to(persistent.parent))
            intake._root_directory(path.parent)
            info = path.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                    and 0 < info.st_size <= 1400000)
            self.secret_stamps[name] = fleet.PreservedRebuildHandoff._identity(info)
            covering = [row for row in mount_rows() if len(row) >= 10
                        and (path == Path(os.fsdecode(row[4])) or path.is_relative_to(Path(os.fsdecode(row[4]))))]
            selected = max(covering, key=lambda row: len(row[4]))
            require(selected[selected.index(b"-") + 1] not in {b"nfs", b"nfs4"})
        self.operation, self.docker = operation_directory, docker
        self.tool = origin._capture(docker, 128 * 1024**2, executable=True)
        self.daemon = runtime._socket_identity()
        policy.__post_init__()
        require(policy.process_role == "signer" and policy.user == "0:0"
                and policy.requested_image == self.lock["toolchain"]["signer_image"]
                and policy.entrypoint == ("/usr/bin/python3",) and policy.command == ()
                and policy.attach_stdout and policy.attach_stderr)
        # Exact retained SDK111 public image profile; never persist arbitrary
        # job environment values to the recovery intent or pass them to PID1.
        self.policy, self.bearer = policy, binary_bearer
        self.used = False

    def _command(self, arguments, seconds=30, cleanup=False):
        self.tool.recheck()
        require(runtime._socket_identity() == self.daemon)
        try:
            return origin._run([str(self.docker.path), "--config", str(self.operation / "docker-config"),
                "--host", "unix:///run/docker.sock", *arguments], self.operation, seconds, 4096, 65536)
        finally:
            self.tool.recheck()
            require(runtime._socket_identity() == self.daemon)

    def _cleanup_identity(self, cid, name, policy):
        # A well-shaped create reply alone is NOT ownership. In particular,
        # CREATED rejection must never let a foreign CID authorize deletion.
        for _ in range(2):
            value, daemon = runtime._inspect(cid)
            config = value.get("Config")
            require(daemon[:-1] == self.daemon and value.get("Id") == cid
                    and value.get("Name") == "/" + name and value.get("Image") == policy.image_id
                    and type(config) is dict and config.get("Image") == policy.requested_image
                    and config.get("Labels") == dict(policy.labels))

    def launch(self, captured):
        require(not self.used)
        self.used = True
        require(type(captured) is intake.CapturedPublicIntake and type(captured.connection) is intake.PublicCaptureClient
                and captured.connection is self.connection
                and captured.connection._intake is captured
                and captured.connection._job.transaction_id == self.config["attempt"]
                and captured.retained.artifact_subject_path.parent == Path(self.config["handoff"]))
        captured.assert_exact()
        require(captured.retained.handoff["bindings"]["lockSha256"] == hashlib.sha256(self.lock_raw).hexdigest()
                and captured.retained.handoff["bindings"]["sourceGraphSha256"] == self.validation._bindings["source_graph"])
        self.persistent.assert_exact()
        require(worker.code_inputs(self.root, self.config["code_pins"]) == self.pins)
        captured.connection.assert_signing_fresh(captured)
        docker_owner._operation(self.operation)  # Durable exclusive intent BEFORE any reserve/create.
        socket_path = Path(self.config["socket"])
        require(len(os.fsencode(socket_path)) < 108 and not os.path.lexists(socket_path))
        configuration = socket_path.parent / "worker.json"
        fleet._write_exclusive(configuration, fleet._canonical_json(self.config))
        configuration.chmod(0o400)
        fleet._fsync_directory(configuration.parent)
        digest = hashlib.sha256(fleet._canonical_json(self.config)).hexdigest()
        policy = replace(self.policy, command=("-I", "-B", "-S", "-c", worker.BOOTSTRAP,
            str(self.root), str(configuration), digest))
        required_rw = {str(self.persistent.parent), self.config["requests"]}
        required_ro = {str(self.root), self.config["handoff"], self.config["responses"], str(socket_path.parent),
                       *self.config["validation"].values()}
        # Auxiliary files may sit below the preserved source/tool/authority roots.
        roots = {str(self.root), self.config["handoff"], self.config["responses"], str(socket_path.parent),
                 self.config["validation"]["workspace_root"], self.config["validation"]["authority_root"],
                 *(self.config["validation"][key] for key in ("dotnet_root", "java_root", "android_sdk_root"))}
        require({(row.source, row.target, row.read_only) for row in policy.binds}
                == {(path, path, False) for path in required_rw} | {(path, path, True) for path in roots}
                and all(any(Path(path).is_relative_to(Path(root)) for root in roots) for path in required_ro)
                and self.config["credentials"] in {row.target for row in policy.tmpfs})
        require(all(not Path(path).is_relative_to(Path(row.source)) for path in self.secrets.values() for row in policy.binds))
        private = next(row for row in policy.tmpfs if row.target == self.config["credentials"])
        require({"mode=0700", "uid=0", "gid=0", "noexec"} <= set(private.options.split(",")))
        mounts = runtime._mount_sources(policy)
        name, cid, connection, pidfd, listener = "chummer-protected-" + secrets.token_hex(16), None, None, None, None
        stop, ready, broker_error, broker_thread = threading.Event(), threading.Event(), [], None
        network_gate = threading.Lock()
        try:
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(socket_path))
            os.chmod(socket_path, 0o600)
            listener.listen(1)
            listener.settimeout(worker.SESSION_SECONDS)
            sock_stamp = fleet.PreservedRebuildHandoff._identity(socket_path.lstat())
            docker_owner._record(self.operation, "intent.json", {"containerName": name, "policy": asdict(policy),
                "mode": self.config["mode"], "attempt": self.config["attempt"], "configSha256": digest})
            # Paired endpoints must both exist and be empty before the worker starts.
            module, client, subject, _ = worker.ledger_inputs(self.root, self.lock, self.config, captured.retained.handoff)
            def https_transport(url, body, headers, timeout):
                with network_gate:
                    require(not stop.is_set() and ready.is_set())
                    deadline = captured.connection.assert_signing_fresh(captured)
                    require(not stop.is_set() and time.monotonic() < deadline)
                    # Already admitted sends may finish ambiguously after
                    # revocation; no queued send can be newly admitted then.
                    return bridge.protocol._https_transport(url, body, headers, timeout)
            broker = bridge.ControllerBroker(Path(self.config["requests"]), Path(self.config["responses"]),
                policy=client.policy, subject=subject, policy_sha256=self.lock["reservation"]["policy_sha256"],
                bearer=self.bearer, https_transport=https_transport)
            def serve_ledger():
                try:
                    while not stop.wait(0.01):
                        broker.serve_once()
                except BaseException:
                    broker_error.append(True)
            broker_thread = threading.Thread(target=serve_ledger, daemon=True)
            broker_thread.start()
            raw = self._command(docker_owner._create_arguments(policy, name))
            require(len(raw) == 65 and fleet.HEX64.fullmatch(raw[:-1].decode("ascii")) and raw[-1:] == b"\n")
            cid = raw[:-1].decode("ascii")
            docker_owner._record(self.operation, "container.json", {"containerName": name, "containerId": cid})
            created = runtime.observe_created(cid, policy)
            require(created.socket_identity[:-1] == self.daemon)
            require(self._command(["start", cid]) == (cid + "\n").encode())
            connection, _ = listener.accept()
            connection.settimeout(worker.SESSION_SECONDS)
            observed = signer.observe_running_signer(cid, policy, created, credential_targets=(self.config["credentials"],))
            require(struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    == (observed.pid, 0, 0))
            pidfd = os.pidfd_open(observed.pid)
            # IPC deadlines use the same kernel's monotonic clock, not remote wall time.
            require(os.stat(f"/proc/{observed.pid}/ns/time").st_ino == os.stat("/proc/self/ns/time").st_ino)
            initial = (observed.pid, observed.start_ticks, observed.started_at)
            ready.set()
            sequence, secret_index = 0, 0
            while True:
                request = worker.receive(connection)
                require(type(request.get("sequence")) is int and request["sequence"] == sequence
                        and sequence < 4096 and not broker_error and not select.select([pidfd], [], [], 0)[0])
                sequence += 1
                current = signer.observe_running_signer(cid, policy, created, credential_targets=(self.config["credentials"],))
                require((current.pid, current.start_ticks, current.started_at) == initial
                        and runtime._mount_sources(policy) == mounts
                        and fleet.PreservedRebuildHandoff._identity(socket_path.lstat()) == sock_stamp
                        and worker.code_inputs(self.root, self.config["code_pins"]) == self.pins)
                self.persistent.assert_exact()
                deadline = captured.connection.assert_signing_fresh(captured)
                operation, value = request.get("operation"), None
                require(set(request) == ({"sequence", "operation", "name"} if operation == "secret" else {"sequence", "operation"}))
                if operation == "secret":
                    require(self.config["mode"] == "execute" and secret_index < 4
                            and request["name"] == credentials.SECRET_NAMES[secret_index])
                    secret_index += 1  # Never replay a consumed secret response.
                    record, _ = fleet._recovery_read(Path(self.config["recovery"]) / self.config["attempt"],
                        "RESERVATION.generated.json", 1024 * 1024)
                    require(record["subject"] == subject and record["attemptId"] == self.config["attempt"]
                            and record["lockSha256"] == hashlib.sha256(self.lock_raw).hexdigest()
                            and record["artifactClosureSha256"] == captured.retained.artifact_closure_sha256)
                    verified, _ = client._reservation_binding(subject, record["reservation"])
                    require(verified["receipt"]["state"] == "reserved" and time.monotonic() < deadline)
                    path = self.secrets[request["name"]]
                    require(fleet.PreservedRebuildHandoff._identity(path.lstat()) == self.secret_stamps[request["name"]])
                    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
                    try:
                        require(fleet.PreservedRebuildHandoff._identity(os.fstat(descriptor)) == self.secret_stamps[request["name"]])
                        with os.fdopen(descriptor, "rb", closefd=False) as stream:
                            raw = stream.read(1400001)
                        require(0 < len(raw) <= 1400000 and fleet.PreservedRebuildHandoff._identity(os.fstat(descriptor))
                                == fleet.PreservedRebuildHandoff._identity(path.lstat()) == self.secret_stamps[request["name"]])
                        value = raw.decode("utf-8")
                    finally:
                        os.close(descriptor)
                else:
                    require(operation in {"check", "done"})
                require(time.monotonic() < deadline)
                worker.send(connection, {"sequence": request["sequence"], "deadline": deadline, "value": value})
                if operation == "done":
                    stop.set()  # Revoke before wait/remove, not after cleanup.
                    break
            require(self._command(["wait", cid], 30) == b"0\n")
            exited = runtime.observe_exited(cid, policy, created)
            docker_owner._record(self.operation, "exited.json", asdict(exited))
            require(self._command(["rm", cid]) == (cid + "\n").encode())
            cid = None
            return fleet._json_file(Path(self.config["output"]) / "FLEET_ANDROID_PREVIEW12_EXTERNAL_REBUILD_AUDIT.v3.json",
                                    "protected job audit", 8 * 1024 * 1024, owner_only=True)[0]
        except BaseException:
            stop.set()  # Revoke queued HTTPS before potentially blocking cleanup.
            if cid is not None:
                try:
                    self._cleanup_identity(cid, name, policy)
                    self._command(["stop", "--time", "1", cid], 10, cleanup=True)
                    self._cleanup_identity(cid, name, policy)
                    require(self._command(["rm", cid], cleanup=True) == (cid + "\n").encode())
                except BaseException:
                    pass  # Retained CID/intent requires exact owner recovery, never recreate.
            raise worker.JobError(worker.ERROR) from None
        finally:
            stop.set()
            if connection is not None:
                connection.close()
            if listener is not None:
                listener.close()
            if pidfd is not None:
                os.close(pidfd)
            if broker_thread is not None:
                broker_thread.join(timeout=client.policy["timeout_seconds"] + 1)
                require(not broker_thread.is_alive())
            # No deletion of recovery, operation, socket or public intake evidence.
