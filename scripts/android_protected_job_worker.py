"""Protected-job PID1 transaction owner; no public listener or ambient secrets.

Only the admitted launcher starts this entrypoint. Its private session joins
actual host-owned runtime custody to the existing transaction, not to a new
receipt. Keys remain in this protected GitHub job and never reach the builder.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import threading
import time

from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_preview12_ledger_bridge as bridge
from scripts import android_preview12_signer_credentials as credentials

ERROR = "protected job stopped; reconcile retained evidence"
MAX_FRAME = 2 * 1024 * 1024
SESSION_SECONDS = 30
BOOTSTRAP = ("import sys;sys.path.insert(0,sys.argv[1]);"
             "from scripts.android_protected_job_worker import main;main(sys.argv[2:])")


class JobError(RuntimeError):
    pass


def require(value):
    if not value:
        raise JobError(ERROR)


def receive(connection):
    deadline = time.monotonic() + SESSION_SECONDS
    def exact(count):
        chunks = []
        while count:
            require(time.monotonic() < deadline)
            raw = connection.recv(count)
            require(raw)
            chunks.append(raw)
            count -= len(raw)
        return b"".join(chunks)
    size = struct.unpack(">I", exact(4))[0]
    require(0 < size <= MAX_FRAME)
    raw = exact(size)
    require(time.monotonic() < deadline)
    return fleet._strict_json(raw, "private job frame")


def send(connection, value):
    raw = fleet._canonical_json(value)
    require(0 < len(raw) <= MAX_FRAME)
    connection.sendall(struct.pack(">I", len(raw)) + raw)


def code_inputs(root, pins):
    fleet._preserved_path(root, "protected Fleet code", directory=True)
    require(type(pins) is dict and 1 <= len(pins) <= 64)
    captured = {}
    for relative, digest in pins.items():
        require(type(relative) is str and relative.startswith("scripts/")
                and relative.endswith(".py") and ".." not in Path(relative).parts)
        path = root / relative
        require(fleet.HEX64.fullmatch(digest))
        captured[relative] = fleet.PreservedRebuildHandoff._file_snapshot(path, "protected code", 2 * 1024 * 1024)
        require(captured[relative][1] == digest)
    # Every already imported Fleet module must be admitted, including __init__.
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_relative_to(root):
            require(str(Path(path).relative_to(root)) in captured)
    # No cached application bytecode may replace the explicitly pinned source.
    for relative in captured:
        require(not (root / relative).with_suffix(".pyc").exists()
                and not (root / relative).parent.joinpath("__pycache__").exists())
    return captured


def ledger_inputs(root, lock, config, handoff):
    """Reuse immutable loader/separation; no bearer or network in this process."""
    # Construct transport lazily after the real pinned loader selects the policy.
    transport = None
    def call(body, timeout):
        require(transport is not None)
        return transport(body, timeout)
    module, client, digest = fleet.load_reviewed_ledger(root, lock, {}, bridge_transport=call)
    subject = module.make_subject(approval_request_nonce=config["attempt"],
        two_green_artifact_id=config["artifact_id"], two_green_artifact_sha256=config["artifact_sha256"],
        two_green_receipt_sha256=handoff["bindings"]["twoGreenReceiptSha256"],
        main_tree=handoff["bindings"]["sourceTree"], policy_sha256=digest,
        version_name=fleet.VERSION_NAME, version_code=fleet.VERSION_CODE)
    transport = bridge.SignerTransport(Path(config["requests"]), Path(config["responses"]),
        policy=client.policy, subject=subject, policy_sha256=digest)
    return module, client, subject, transport


class Session:
    """One private host session; a stopped PID1 kills all namespace children.

    The host verifies our exact host PID/start/pidfd. Inside this private PID
    namespace the host peer PID is 0, not a forged visible host PID. Socket inode,
    root ownership and the immutable launcher-selected bind establish its end.
    """
    def __init__(self, path):
        require(os.getpid() == 1 and os.getuid() == os.geteuid() == 0)
        info = path.lstat()
        require(stat.S_ISSOCK(info.st_mode) and info.st_uid == info.st_gid == 0
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1)
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.settimeout(SESSION_SECONDS)
        self._socket.connect(str(path))
        require(struct.unpack("3i", self._socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)) == (0, 0, 0)
                and fleet.PreservedRebuildHandoff._identity(path.lstat())
                == fleet.PreservedRebuildHandoff._identity(info))
        self._mutex, self._done = threading.RLock(), threading.Event()
        self._sequence, self._deadline = 0, time.monotonic() + SESSION_SECONDS
        self._watch = threading.Thread(target=self._watchdog, daemon=True)
        self._watch.start()
        self.check()
        threading.Thread(target=self._heartbeat, daemon=True).start()

    def _watchdog(self):
        while not self._done.wait(0.05):
            if time.monotonic() >= self._deadline:
                os._exit(70)  # Never leave signer children alive after session loss.

    def _heartbeat(self):
        while not self._done.wait(5):
            with self._mutex:
                if not self._done.is_set():
                    self.check()

    def exchange(self, operation, **fields):
        with self._mutex:
            try:
                require(not self._done.is_set() and time.monotonic() < self._deadline)
                sequence = self._sequence
                self._sequence += 1  # Lost replies cannot be retried.
                send(self._socket, {"sequence": sequence, "operation": operation, **fields})
                reply = receive(self._socket)
                require(set(reply) == {"sequence", "deadline", "value"} and type(reply["sequence"]) is int
                        and reply["sequence"] == sequence and type(reply["deadline"]) in {float, int}
                        and math.isfinite(reply["deadline"]) and time.monotonic() < reply["deadline"]
                        <= time.monotonic() + 600)
                self._deadline = min(reply["deadline"], time.monotonic() + SESSION_SECONDS)
                if operation == "done":
                    self._done.set()
                return reply["value"]
            except BaseException:
                os._exit(70)

    def check(self):
        require(self.exchange("check") is None)

    def read_secret(self, name):
        require(name in credentials.SECRET_NAMES)
        value = self.exchange("secret", name=name)
        require(type(value) is str and time.monotonic() < self._deadline)
        return value

    def run(self, command, **kwargs):
        self.check()
        require(time.monotonic() < self._deadline)
        # No injected runner. Every actual jarsigner/OpenSSL operation is fenced.
        result = subprocess.run(command, **kwargs)
        self.check()
        return result

    def finish(self):
        require(self.exchange("done") is None)
        self._done.set()
        self._socket.close()


def execute_owned(session, config):
    require(type(session) is Session)
    root, lock_path = Path(config["fleet_root"]), Path(config["lock"])
    pins = code_inputs(root, config["code_pins"])
    retained = fleet.PreservedRebuildHandoff(lock_path, Path(config["handoff"]))
    validation = fleet.PreservedProtectedValidation(lock_path,
        **{name: Path(value) for name, value in config["validation"].items()})
    lock, lock_raw = fleet.load_lock(lock_path)
    require(not fleet.validate_lock(lock, lock_raw))
    module, client, subject, transport = ledger_inputs(root, lock, config, retained.handoff)
    builder = validation._check_exact()
    require(builder["closureSha256"] == retained.handoff["bindings"]["toolchainClosureSha256"])
    closure = dict(builder)
    closure["builderClosureSha256"] = closure.pop("closureSha256")
    closure["builderExecutionProvenanceAuthenticated"] = closure["protectedSignerRuntimeVerified"] = True
    closure["closureSha256"] = hashlib.sha256(fleet._canonical_json(closure)).hexdigest()

    def exact():
        require(code_inputs(root, config["code_pins"]) == pins)
        retained.assert_exact()
        session.check()  # Actual live owner join, never serialized runtime flags.

    def authenticate(current, raw):
        require(current == lock and raw == lock_raw)
        exact()
        provenance = {"authorityClass": "authenticated_immutable_workflow_artifact",
            "lockSha256": hashlib.sha256(lock_raw).hexdigest(),
            "artifactClosureSha256": retained.artifact_closure_sha256,
            "builderImage": lock["toolchain"]["builder_image"], "signerImage": lock["toolchain"]["signer_image"],
            "builderCredentialMountsPresent": False, "builderExecutionProvenanceAuthenticated": True,
            "protectedSignerRuntimeVerified": True, "consumerBytesRootOwnedImmutable": True,
            "ledgerAdapterBytesRootOwnedImmutable": True,
            "recoveryStoreIdentitySha256": fleet._recovery_store_identity(Path(config["recovery"])),
            "attemptId": config["attempt"], "twoGreenArtifactId": config["artifact_id"],
            "twoGreenArtifactSha256": config["artifact_sha256"]}
        return fleet.AuthenticatedRebuildHandoff(retained.handoff, retained.paths, closure, provenance,
            validation.tool_roots["java"], Path(config["recovery"]), exact)

    common = dict(attempt_id=config["attempt"], two_green_artifact_id=config["artifact_id"],
                  two_green_artifact_sha256=config["artifact_sha256"], ledger_bridge_transport=transport)
    if config["mode"] == "reconcile":
        result = fleet.reconcile_protected_signer_transaction(lock_path, authenticate,
            validation.load_consumer, root, {}, validation, Path(config["output"]), **common)
    else:
        require(config["mode"] == "execute")
        with credentials.SignerCredentials(Path(config["credentials"]) / "admitted", session.read_secret) as secrets:
            def admit(reservation, provenance):
                exact()
                # Existing signed response verifier; no callback JSON flags.
                client._reservation_binding(subject, reservation)
                session.check()
                return secrets(reservation, provenance)
            result = fleet.execute_protected_signer_transaction(lock_path, authenticate,
                validation.load_consumer, root, {}, admit, validation, Path(config["output"]),
                runner=session.run, **common)
    exact()
    return result


def main(arguments):
    try:
        require(len(arguments) == 2 and sys.flags.isolated and sys.flags.no_site
                and sys.dont_write_bytecode and os.getpid() == 1)
        os.umask(0o077)
        path, digest = Path(arguments[0]), arguments[1]
        fleet._preserved_path(path, "protected worker configuration")
        raw = fleet._stable_bytes(path, "protected worker configuration", 128 * 1024, owner_only=True)
        require(hashlib.sha256(raw).hexdigest() == digest)
        config = fleet._strict_json(raw, "protected worker configuration")
        session = Session(Path(config["socket"]))
        execute_owned(session, config)
        session.finish()
    except BaseException:
        os._exit(70)  # Constant exit, no traceback, keys, paths or copied output.
