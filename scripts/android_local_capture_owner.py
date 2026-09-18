"""Fixed local root owner: actual capture -> RO custody -> emission -> job3.

Only independently admitted provisioning may invoke this executable with its
deployment digest. No candidate-selected factories, capabilities or arm routes.
This process never receives signing keys or runs the protected transaction.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import fields
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import threading
import time

from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_controller_capture as controller
from scripts import android_container_runtime as runtime
from scripts import android_controller_rendezvous as rendezvous
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_protected_capture_intake as intake
from scripts import android_protected_job_bootstrap as inputs
from scripts import android_protected_job_worker as worker
from scripts import android_workflow_challenge_store as journal
from scripts import android_workflow_identity as identity

ERROR = "local capture owner stopped; preserve evidence and do not replay"
PIN_LIMITS = {"lock": 1024**2, "docker": 128 * 1024**2,
              "verifier": 256 * 1024**2, "trusted_root": 16 * 1024**2,
              "tls_certificate": 1024**2}


class OwnerError(RuntimeError):
    """Constant failure only; no exception text, credentials or request bytes."""


def require(value):
    if not value:
        raise OwnerError(ERROR)


def _shape(value, names):
    require(type(value) is dict and set(value) == set(names))
    return dict(value)


def _path(value):
    require(type(value) is str and runtime._path(value))
    return Path(value)


def _separate(left, right):
    return left != right and left not in right.parents and right not in left.parents


def _not_exposed(path, binds):
    """Reject file bind aliases and binds of a private file's ancestor."""
    identities = {(item.stat().st_dev, item.stat().st_ino) for item in (path, *path.parents)}
    for bind in binds:
        source = Path(bind.source)
        require(_separate(path, source) and (source.stat().st_dev, source.stat().st_ino) not in identities)


def _typed(kind, value):
    return kind(**_shape(value, (field.name for field in fields(kind))))


def _document(raw):
    required = {"fleet_root", "code_pins", "pins", "journal",
        "capture_policy", "emission_policy", "protected_job_policy", "artifact_policy",
        "runtime_policy", "operation_directory", "attempt_directory", "custody_packet",
        "output_bind_target", "handoff_child_name", "base_url", "bearer_sha256", "tls", "limits"}
    parsed = identity._json(raw)
    require(type(parsed) is dict and required <= set(parsed)
            <= required | {"role_binding", "startup_barrier", "status_write_token"})
    value = parsed
    require(("startup_barrier" in value) == ("status_write_token" in value))
    if "role_binding" in value:
        from scripts import android_workflow_job_binder as binder
        binder.validate_role_binding(value["role_binding"])
    if "startup_barrier" in value:
        from scripts import android_startup_scheduling as startup
        startup.validate_deployment(value, owner=True)
        _path(value["status_write_token"])
    pins = {name: origin.PinnedFile(_path(_shape(item, {"path", "sha256"})["path"]), item["sha256"])
            for name, item in _shape(value["pins"], PIN_LIMITS).items()}
    jobs = tuple(_typed(identity.WorkflowJobPolicy, value[name]) for name in
                 ("capture_policy", "emission_policy", "protected_job_policy"))
    raw_artifact = _shape(value["artifact_policy"], (field.name for field in fields(origin.OriginPolicy)))
    require(type(raw_artifact["timestamp_types"]) is list)
    raw_artifact["timestamp_types"] = tuple(raw_artifact["timestamp_types"])
    artifact = origin.OriginPolicy(**raw_artifact)
    raw_runtime = _shape(value["runtime_policy"], (field.name for field in fields(runtime.RuntimePolicy)))
    for name in ("entrypoint", "command", "environment", "labels", "binds", "tmpfs"):
        require(type(raw_runtime[name]) is list)
    raw_runtime["resources"] = _typed(runtime.ResourceLimits, raw_runtime["resources"])
    raw_runtime["binds"] = tuple(_typed(runtime.BindMount, item) for item in raw_runtime["binds"])
    raw_runtime["tmpfs"] = tuple(_typed(runtime.TmpfsMount, item) for item in raw_runtime["tmpfs"])
    require(all(type(pair) is list and len(pair) == 2 for pair in raw_runtime["labels"]))
    raw_runtime["labels"] = tuple(tuple(pair) for pair in raw_runtime["labels"])
    for name in ("entrypoint", "command", "environment"):
        raw_runtime[name] = tuple(raw_runtime[name])
    policy = runtime.RuntimePolicy(**raw_runtime)
    require(policy.process_role == "builder" and policy.user != "0:0")
    for job in jobs:
        require(job.runner_environment == "github-hosted" and job.job_status == job.run_status == "in_progress")
    for job in jobs[1:]:
        identity._same_context(job, artifact)
    same = ("repository", "repository_id", "repository_owner", "repository_owner_id", "sha", "ref",
            "workflow_ref", "workflow_sha", "run_id", "run_attempt", "transaction_id")
    require(all(getattr(job, key) == getattr(jobs[0], key) for job in jobs for key in same)
            and len({job.check_run_id for job in jobs}) == 3
            and jobs[2].environment == "android-preview12-release-builder")
    digests = _shape(value["bearer_sha256"], {"capture", "emission", "intake", "approval", "binary"})
    require(all(origin._hex(item, 64) for item in digests.values()) and len(set(digests.values())) == 5)
    database = _shape(value["journal"], {"path", "controller_id", "database_id"})
    _path(database["path"])
    journal._configuration(database["controller_id"], database["database_id"], journal.MAX_CHALLENGES)
    tls = _shape(value["tls"], {"bind_address", "key_file", "trusted_proxy_addresses"})
    require(type(tls["bind_address"]) is str
            and str(ipaddress.ip_address(tls["bind_address"])) == tls["bind_address"])
    _path(tls["key_file"])
    require(type(tls["trusted_proxy_addresses"]) is list)
    rendezvous._hostname(value["base_url"])
    limits = _shape(value["limits"], {"whole_seconds", "preparation_wait_seconds"})
    require(type(limits["whole_seconds"]) is int and 1 <= limits["whole_seconds"] <= 21600
            and type(limits["preparation_wait_seconds"]) is int
            and 1 <= limits["preparation_wait_seconds"] <= 1800
            and limits["preparation_wait_seconds"] < limits["whole_seconds"])
    for name in ("fleet_root", "operation_directory", "attempt_directory", "custody_packet", "output_bind_target"):
        _path(value[name])
    require(type(value["handoff_child_name"]) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value["handoff_child_name"]))
    return value, pins, jobs, artifact, policy


def preserve_capture(result, lock, packet, policy, operation):
    """Copy exactly the real seven files; never rename/adopt the old evidence."""
    require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0
            and type(result) is capture.BuilderHandoffCapture
            and result.directory == operation / capture.COPY_DIRECTORY
            and result.lock_sha256 == lock.sha256)
    capture._terminal(result.execution, policy)
    pinned_lock = origin._capture(lock, 1024**2)
    fleet._preserved_path(lock.path, "owner lock")
    limits = capture._limits(fleet._strict_json(pinned_lock.raw, "owner lock"))
    expected = dict(result.file_sha256)
    require(len(expected) == len(result.file_sha256) and set(expected) == set(limits)
            and expected[capture.MANIFEST] == result.artifact_closure_sha256)
    intake._root_directory(packet.parent)
    require(packet.resolve(strict=False) == packet and not os.path.lexists(packet)
            and _separate(packet, operation)
            and all(_separate(packet, Path(bind.source)) for bind in policy.binds))
    custody = None
    source_fd = destination_fd = None
    try:
        source_fd = capture._directory(result.directory, (0, 0))
        source_stamp = capture._identity(os.fstat(source_fd))
        source_metadata = capture._metadata(source_fd, limits, (0, 0))
        capture._recheck(source_fd, result.directory, source_stamp, source_metadata, limits, (0, 0), expected)
        os.mkdir(packet, 0o700)
        journal._sync_directory(packet.parent)
        files = packet / "files"
        os.mkdir(files, 0o700)
        journal._sync_directory(packet)
        destination_fd = capture._directory(files, (0, 0))
        copied = {name: capture._transfer(source_fd, name, source_metadata[name], limit, destination_fd)
                  for name, limit in limits.items()}
        require(copied == expected)
        for name in limits:
            before = os.stat(name, dir_fd=destination_fd, follow_symlinks=False)
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=destination_fd)
            try:
                require(capture._identity(os.fstat(descriptor)) == capture._identity(before))
                os.fchmod(descriptor, 0o400)
                os.fsync(descriptor)
                require(capture._identity(os.fstat(descriptor)) == capture._identity(
                    os.stat(name, dir_fd=destination_fd, follow_symlinks=False)))
            finally:
                os.close(descriptor)
        os.fsync(destination_fd)
        destination_stamp = capture._identity(os.fstat(destination_fd))
        destination_metadata = capture._metadata(destination_fd, limits, (0, 0))
        capture._recheck(source_fd, result.directory, source_stamp, source_metadata, limits, (0, 0), expected)
        capture._recheck(destination_fd, files, destination_stamp, destination_metadata, limits, (0, 0), expected)
        pinned_lock.recheck()
        custody = intake.ReadOnlyIntake(packet, limits)
        retained = fleet.PreservedRebuildHandoff(lock.path, custody.target)
        require(retained.artifact_closure_sha256 == result.artifact_closure_sha256
                and all(retained._snapshot[name][1] == digest for name, digest in expected.items()))
        custody.assert_exact()
        pinned_lock.recheck()
        return custody, retained
    except BaseException:
        if custody is not None:
            custody.close()
        raise OwnerError(ERROR) from None
    finally:
        for descriptor in (source_fd, destination_fd):
            if descriptor is not None:
                os.close(descriptor)


class LocalCaptureOwner:
    """Actual fixed constructors from independently admitted owner expectations."""
    def __init__(self, deployment, expected_sha256, *, owned_single_build=None):
        self._stack = ExitStack()
        self.controller = self.exporter = self.custody = self.retained = None
        self._app = self._export_app = None
        self._status_token = None
        self._startup_published = set()
        self._phase, self._closed = "prepared", False
        self._mutex = threading.RLock()
        self._revoked = threading.Event()
        try:
            require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 0)
            self._deployment = self._stack.enter_context(_held(deployment, inputs.MAX_DEPLOYMENT, expected_sha256))
            self.value, self.pins, self.jobs, self.artifact, self.policy = _document(self._deployment.raw)
            binding_deadline = (time.monotonic() + self.value["limits"]["whole_seconds"]
                                if "role_binding" in self.value else None)
            self._root = _path(self.value["fleet_root"])
            self._code = worker.code_inputs(self._root, self.value["code_pins"])
            if "role_binding" in self.value:
                from scripts import android_workflow_job_binder as binder
                bound = binder.bind_deployment_roles(
                    binding=self.value["role_binding"],
                    current_policies=dict(zip(binder.ROLES, self.jobs)), deadline=binding_deadline)
                self.jobs = tuple(bound[role] for role in binder.ROLES)
                self._deployment.recheck()
                require(worker.code_inputs(self._root, self.value["code_pins"]) == self._code)
                require(time.monotonic() < binding_deadline)
            self._captured = {name: origin._capture(pin, PIN_LIMITS[name], executable=name in {"docker", "verifier"})
                              for name, pin in self.pins.items()}
            fleet._preserved_path(self.pins["lock"].path, "owner lock")
            lock, raw = fleet.load_lock(self.pins["lock"].path)
            require(hashlib.sha256(raw).hexdigest() == self.pins["lock"].sha256
                    and not fleet.validate_lock(lock, raw, self.policy.requested_image))
            if owned_single_build is not None:
                require(type(owned_single_build) is controller.OwnedSingleBuild)
                owned_single_build.check_binding(self.policy, self.pins["docker"], self.pins["lock"],
                    _path(self.value["operation_directory"]), self.value["output_bind_target"],
                    self.value["handoff_child_name"], self.artifact)
            self._key = self._stack.enter_context(_held(_path(self.value["tls"]["key_file"]), 16384))
            if "startup_barrier" in self.value:
                self._status_token = self._stack.enter_context(
                    _held(_path(self.value["status_write_token"]), 16384))
            destinations = [_path(self.value[name]) for name in
                            ("operation_directory", "attempt_directory", "custody_packet")]
            for target in destinations:
                intake._root_directory(target.parent)
                require(target.resolve(strict=False) == target)
                if owned_single_build is None or target != destinations[0]:
                    require(not os.path.lexists(target))
                require(all(_separate(target, other) for other in destinations if other != target))
                require(all(_separate(target, Path(bind.source)) for bind in self.policy.binds))
            require(len(set(destinations)) == 3)
            private = (self._deployment.path, self._key.path, _path(self.value["journal"]["path"]))
            if self._status_token is not None:
                require(self._status_token.stamp[:2] not in {
                    origin._identity(path.stat())[:2] for path in
                    (*private, *(pin.path for pin in self.pins.values()))})
                private += (self._status_token.path,)
            self._private_paths = private
            for path in private:
                _not_exposed(path, self.policy.binds)
                require(all(_separate(path, target) for target in destinations))
            for pin in self.pins.values():
                require(self._key.stamp[:2] != origin._identity(pin.path.stat())[:2])
            require(self._key.stamp[:2] != self._deployment.stamp[:2])
            database = self.value["journal"]
            digests = self.value["bearer_sha256"]
            single = {} if owned_single_build is None else {"owned_single_build": owned_single_build}
            self.controller = rendezvous.ControllerRendezvous(
                journal_path=_path(database["path"]), controller_id=database["controller_id"],
                database_id=database["database_id"], capture_policy=self.jobs[0], emission_policy=self.jobs[1],
                artifact_policy=self.artifact, preserved_directory=destinations[2] / "preserved",
                inputs=rendezvous.CaptureInputs(self.policy, self.pins["docker"], self.pins["lock"],
                    destinations[0], self.value["output_bind_target"], self.value["handoff_child_name"]),
                attempt_directory=destinations[1], verifier=self.pins["verifier"], trusted_root=self.pins["trusted_root"],
                base_url=self.value["base_url"], capture_bearer_sha256=digests["capture"],
                emission_bearer_sha256=digests["emission"], approval_bearer_sha256=digests["approval"],
                binary_bearer_sha256=digests["binary"], **single)
            self._peers = tuple(self.value["tls"]["trusted_proxy_addresses"])
            self._app = rendezvous.RendezvousApp(self.controller, trusted_proxy_addresses=self._peers)
            self._deadline = binding_deadline or time.monotonic() + self.value["limits"]["whole_seconds"]
            self.recheck()
        except BaseException:
            self.close()
            raise OwnerError(ERROR) from None

    def recheck(self, *, full=True):
        require(not self._closed and not self._revoked.is_set() and time.monotonic() < self._deadline)
        self._deployment.recheck()
        self._key.recheck()  # Metadata only; never accesses a signing credential.
        if self._status_token is not None:
            self._status_token.recheck()
        for path in self._private_paths:
            _not_exposed(path, self.policy.binds)
        if full:
            require(worker.code_inputs(self._root, self.value["code_pins"]) == self._code)
        else:
            for relative, snapshot in self._code.items():
                path = self._root / relative
                fleet._preserved_path(path, "owner code")
                require(fleet.PreservedRebuildHandoff._identity(path.stat()) == snapshot[0])
        for name, captured in self._captured.items():
            require(inputs._metadata(captured.pin.path, PIN_LIMITS[name], private=False) == captured.identity)
            if full:
                captured.recheck()
        if self.custody is not None:
            self.custody.assert_exact()
            if full:
                self.retained.assert_exact()
        require(time.monotonic() < self._deadline)

    def start(self):
        with self._mutex:
            require(self._phase == "prepared")
            self._phase = "capture"  # A lost/failed arm never becomes retryable.
            self.recheck()
            self.controller.arm_capture()

    def publish_startup(self, stage):
        """One scheduling notice after an actual local transition, never auth."""
        if "startup_barrier" not in self.value:
            return
        from scripts import android_startup_scheduling as startup
        with self._mutex:
            require(stage in {"listener", "export"} and stage not in self._startup_published
                    and self._phase == ("capture" if stage == "listener" else "preparation")
                    and (stage == "listener" or "listener" in self._startup_published))
            self.recheck()
            self._startup_published.add(stage)  # Lost POST replies are not replayed.
            try:
                startup.publish_stage(self.value, stage,
                    dict(zip(("capture", "emission", "protected"), self.jobs)), self._status_token,
                    deadline=self._deadline, recheck=self.recheck)
                self.recheck()
            except BaseException:
                self.revoke()  # A late/lost publication never leaves admission open.
                raise OwnerError(ERROR) from None

    def advance(self):
        """Local owner scheduling; no HTTP request selects or calls this method."""
        with self._mutex:
            self.recheck(full=False)
            state = self.controller.owner_state()
            if self._phase == "capture" and state == "capture-complete":
                self._phase = "preserving"
                self.recheck()
                self.custody, self.retained = preserve_capture(self.controller.capture_completed(),
                    self.pins["lock"], _path(self.value["custody_packet"]), self.policy,
                    _path(self.value["operation_directory"]))
                self.recheck()
                self.controller.arm_emission(self.retained)
                self._phase = "emission"
            elif self._phase == "emission" and state == "complete":
                self._phase = "exporting"
                self.recheck()
                digests = self.value["bearer_sha256"]
                self.exporter = intake.PublicCaptureExport(self.controller, job_policy=self.jobs[2],
                    bearer_sha256=digests["intake"], approval_bearer_sha256=digests["approval"],
                    binary_bearer_sha256=digests["binary"])
                self.exporter.enable_preparation_wait(self.value["limits"]["preparation_wait_seconds"])
                self._export_app = intake.PublicCaptureApp(self.exporter, trusted_proxy_addresses=self._peers)
                self._phase = "preparation"
                self.publish_startup("export")
                print("local_capture_owner=intake_listener_installed", flush=True)
            elif self._phase == "preparation" and self.exporter.preparation_observed():
                # Diagnostic pending observation only triggers this independent
                # recheck. It never authenticates a job or bypasses the store.
                self._phase = "arming"
                self.recheck()
                self.exporter.enable_protected_job_checks()
                self.exporter.arm()
                self._phase = "serving"
            elif self._phase == "serving":
                with self.exporter._mutex:
                    self.exporter._exact()  # Existing full checks remain at use.

    def revoke(self):
        """Immediately stop NEW HTTP admission; do not wait on foreign work.

        Already executing callbacks are not claimed cancelled. Poison idle
        adapters under their own locks; cleanup later joins before unmounting.
        """
        self._revoked.set()
        if self.exporter is not None and self.exporter._mutex.acquire(blocking=False):
            try:
                self.exporter.close()
            finally:
                self.exporter._mutex.release()
        if self.controller is not None and self.controller._condition.acquire(blocking=False):
            try:
                self.controller._fail()
            finally:
                self.controller._condition.release()

    async def __call__(self, scope, receive, send):
        # Existing apps retain exact path/Host/TLS/bearer/framing checks.
        path = scope.get("raw_path", b"")
        app = self._app
        if type(path) is bytes and path.startswith(b"/android-protected-capture/"):
            app = self._export_app
        if app is None or self._closed or self._revoked.is_set():
            await _reject(send)
            return
        async def admitted_receive():
            require(not self._revoked.is_set())
            result = await receive()
            require(not self._revoked.is_set())
            return result
        async def admitted_send(message):
            # Suppress a late successful reply from an already executing call.
            # Bytes delivered before revocation cannot be retroactively undone.
            require(not self._revoked.is_set())
            await send(message)
        await app(scope, admitted_receive, admitted_send)

    def close(self):
        with self._mutex:
            if self._closed:
                return
            self.revoke()
            self._closed = True
            try:
                if self.exporter is not None:
                    self.exporter.close()
                if self.controller is not None:
                    self.controller.close()
                    # Never unmount underneath an active capture/emission task.
                    # The independently admitted outer supervisor bounds stalls.
                    self.controller._executor.shutdown(wait=True, cancel_futures=True)
                if self.custody is not None:
                    self.custody.close()
            finally:
                self._stack.close()


async def _reject(send):
    await send({"type": "http.response.start", "status": 404,
                "headers": [(b"content-type", b"application/octet-stream"), (b"content-length", b"10"),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": b"not-found\n"})


class _held:
    def __init__(self, path, limit, expected=None):
        self.file = inputs._OwnedFile(path, limit, expected=expected)
    def __enter__(self): return self.file
    def __exit__(self, *_): self.file.close()


def run(deployment, expected_sha256, *, owned_single_build=None):
    """Real TLS listener and fixed local owner; never a test factory/plugin."""
    # Import only this existing pinned serving implementation, not a configured
    # module. Ledger prepare()/stores/receipt keys are deliberately never used.
    from scripts import android_preview12_approval_ledger_server as transport
    require(transport.uvicorn.__version__ == "0.34.2")
    with ExitStack() as stack:
        single = {} if owned_single_build is None else {"owned_single_build": owned_single_build}
        owner = LocalCaptureOwner(deployment, expected_sha256, **single)
        stack.callback(owner.close)
        cert = transport._sealed(owner._captured["tls_certificate"].raw, stack)
        key = transport._sealed(owner._key.read(), stack)  # Explicit local TLS key only.
        config = transport.uvicorn.Config(owner, host=owner.value["tls"]["bind_address"], port=443,
            workers=1, interface="asgi3", loop="asyncio", http=transport._BoundedHttp, ws="none",
            lifespan="off", reload=False, proxy_headers=False, forwarded_allow_ips="", access_log=False,
            log_config=transport._NULL_LOG, server_header=False, date_header=False, backlog=32,
            limit_concurrency=16, timeout_keep_alive=2, timeout_graceful_shutdown=15,
            h11_max_incomplete_event_size=16384, ssl_certfile=f"/proc/self/fd/{cert}",
            ssl_keyfile=f"/proc/self/fd/{key}", ssl_keyfile_password="", ssl_version=ssl.PROTOCOL_TLS_SERVER)
        config.load()
        config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
        owner.recheck()
        class Server(transport._Server):
            async def startup(self, sockets=None):
                await transport.uvicorn.Server.startup(self, sockets=sockets)
                if self.started:
                    owner.start()
                    owner.publish_startup("listener")
                    print("local_capture_owner=listener_started", flush=True)
        server = Server(config)
        stop = threading.Event()
        failed = threading.Event()
        def monitor():
            try:
                while not stop.wait(1):
                    require(time.monotonic() < owner._deadline)
                    if server.started:
                        owner.advance()
            except BaseException:
                failed.set()
                owner.revoke()
                server.should_exit = True
        thread = threading.Thread(target=monitor, name="fixed-local-owner", daemon=True)
        thread.start()
        try:
            server.run()
        finally:
            stop.set()
            thread.join()  # Outer process supervisor bounds synchronous I/O.
        require(server.started and not failed.is_set())
        return 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise OwnerError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(description=__doc__, allow_abbrev=False, add_help=False)
        parser.add_argument("--deployment", required=True)
        parser.add_argument("--deployment-sha256", required=True)
        args = parser.parse_args(argv)
        return run(_path(args.deployment), args.deployment_sha256)
    except (Exception, KeyboardInterrupt, SystemExit):
        print(ERROR, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
