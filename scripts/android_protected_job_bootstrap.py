"""Fixed hosted-root executable: expectations -> real owner -> one job3.

The deployment digest must be independently admitted by protected provisioning,
never obtained from the candidate. Root ownership is necessary, not authority.
No imports/factories, claimed capabilities, ambient credentials or activation.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import fields
import fcntl
import hashlib
import os
from pathlib import Path
import select
import ssl
import stat
import sys
import time

from scripts import android_artifact_origin as origin
from scripts import android_container_runtime as runtime
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_preview12_signer_credentials as credentials
from scripts import android_protected_capture_intake as intake
from scripts import android_protected_job_entrypoint as entrypoint
from scripts import android_protected_job_launcher as launcher
from scripts import android_protected_job_worker as worker
from scripts import android_workflow_identity as identity

ERROR = "protected owner bootstrap stopped; do not replay"
READY = "protected owner prepared; awaiting owner release"
COMPLETE = "protected owner execution returned; inspect retained audit"
MAX_DEPLOYMENT = 256 * 1024
PIN_LIMITS = {"lock": 1024**2, "docker": 128 * 1024**2,
              "verifier": 256 * 1024**2, "trusted_root": 16 * 1024**2,
              "intake_ca": 1024**2, "oidc_ca": 1024**2}
TRANSPORT_LIMITS = {"intake_bearer": 4096, "binary_bearer": 4096,
                    "oidc_request_url": 8192, "oidc_request_credential": 16384}
CONFIG_FIELDS = {"mode", "attempt", "artifact_id", "artifact_sha256", "fleet_root", "lock", "handoff",
                 "validation", "recovery", "output", "requests", "responses", "credentials", "socket", "code_pins"}
VALIDATION_FIELDS = {"workspace_root", "source_graph", "package_authority", "authority_root", "bundletool",
                     "upload_certificate", "java_tool_observation", "installed_closure_receipt",
                     "dotnet_root", "java_root", "android_sdk_root"}
VALIDATION_FILE_LIMITS = {"source_graph": 8 * 1024**2, "package_authority": 8 * 1024**2,
    "bundletool": 64 * 1024**2, "upload_certificate": 1024**2,
    "java_tool_observation": 8 * 1024**2, "installed_closure_receipt": 8 * 1024**2}


class BootstrapError(RuntimeError):
    """One constant only; no upstream exception, path, JWT or secret value."""


def require(value):
    if not value:
        raise BootstrapError(ERROR)


def _shape(value, names):
    require(type(value) is dict and set(value) == set(names))
    return dict(value)


def _path(value):
    require(type(value) is str and runtime._path(value))
    return Path(value)


def _metadata(path, limit, *, private=True):
    fleet._trusted_root(path.parent, "owner input")
    require(path.resolve(strict=True) == path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
            and info.st_nlink == 1 and 0 < info.st_size <= limit
            and (stat.S_IMODE(info.st_mode) in {0o400, 0o600} if private else not info.st_mode & 0o022))
    return origin._identity(info)


class _OwnedFile:
    """Held no-follow file; byte reads are explicit and bounded, never keys."""
    def __init__(self, path, limit, *, expected=None, private=True):
        self.path, self.limit, self.private = path, limit, private
        self.stamp = _metadata(path, limit, private=private)
        self.fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        try:
            self.recheck()
            self.raw = None
            if expected is not None:
                require(origin._hex(expected, 64))
                self.raw = self.read()
                require(hashlib.sha256(self.raw).hexdigest() == expected)
        except BaseException:
            self.close()
            raise

    def recheck(self):
        require(origin._identity(os.fstat(self.fd)) == self.stamp
                == _metadata(self.path, self.limit, private=self.private))

    def read(self):
        self.recheck()
        raw = os.pread(self.fd, self.limit + 1, 0)
        self.recheck()
        require(0 < len(raw) <= self.limit and len(raw) == self.stamp[6])
        return raw

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _dataclass(kind, value):
    return kind(**_shape(value, (field.name for field in fields(kind))))


def _policies(value):
    job = _dataclass(identity.WorkflowJobPolicy, value["job_policy"])
    raw = _shape(value["artifact_policy"], (field.name for field in fields(origin.OriginPolicy)))
    require(type(raw["timestamp_types"]) is list)
    raw["timestamp_types"] = tuple(raw["timestamp_types"])
    artifact = origin.OriginPolicy(**raw)
    raw = _shape(value["runtime_policy"], (field.name for field in fields(runtime.RuntimePolicy)))
    for name in ("entrypoint", "command", "environment", "binds", "tmpfs", "labels"):
        require(type(raw[name]) is list)
    raw["resources"] = _dataclass(runtime.ResourceLimits, raw["resources"])
    raw["binds"] = tuple(_dataclass(runtime.BindMount, item) for item in raw["binds"])
    raw["tmpfs"] = tuple(_dataclass(runtime.TmpfsMount, item) for item in raw["tmpfs"])
    require(all(type(pair) is list and len(pair) == 2 for pair in raw["labels"]))
    raw["labels"] = tuple(tuple(pair) for pair in raw["labels"])
    for name in ("entrypoint", "command", "environment"):
        raw[name] = tuple(raw[name])
    policy = runtime.RuntimePolicy(**raw)
    identity._same_context(job, artifact)
    require(job.environment == "android-preview12-release-builder"
            and job.runner_environment == "github-hosted"
            and job.job_status == job.run_status == "in_progress"
            and policy.process_role == "signer" and policy.user == "0:0"
            and sorted(policy.environment) == sorted(launcher.PUBLIC_ENVIRONMENT)
            and policy.entrypoint == ("/usr/bin/python3",) and policy.command == ()
            and policy.attach_stdout and policy.attach_stderr)
    return job, artifact, policy


def _document(raw):
    value = identity._json(raw)
    names = {"launcher", "job_policy", "artifact_policy", "runtime_policy",
        "pins", "persistent", "operation_directory", "secret_inputs", "transport_inputs", "base_url", "release_wait_seconds"}
    require(type(value) is dict and set(value) in (names, names | {"preparation_wait_seconds"}))
    value.setdefault("preparation_wait_seconds", 0)
    require(type(value["preparation_wait_seconds"]) is int and 0 <= value["preparation_wait_seconds"] <= 1800)
    config = _shape(value["launcher"], CONFIG_FIELDS)
    require(config["mode"] == "execute" and origin._hex(config["attempt"], 64)
            and type(config["artifact_id"]) is int and config["artifact_id"] > 0
            and origin._hex(config["artifact_sha256"], 64))
    for name in ("fleet_root", "lock", "handoff", "recovery", "output", "requests", "responses", "credentials", "socket"):
        _path(config[name])
    for item in _shape(config["validation"], VALIDATION_FIELDS).values():
        _path(item)
    require(type(config["code_pins"]) is dict and 1 <= len(config["code_pins"]) <= 64)
    pins = {name: origin.PinnedFile(_path(_shape(item, {"path", "sha256"})["path"]), item["sha256"])
            for name, item in _shape(value["pins"], PIN_LIMITS).items()}
    require(str(pins["lock"].path) == config["lock"])
    persistent = _shape(value["persistent"], {"parent", "mount_row_sha256"})
    _path(persistent["parent"])
    require(origin._hex(persistent["mount_row_sha256"], 64))
    _path(value["operation_directory"])
    secrets = {name: _path(path) for name, path in _shape(value["secret_inputs"], credentials.SECRET_NAMES).items()}
    transport = {name: _path(path) for name, path in _shape(value["transport_inputs"], TRANSPORT_LIMITS).items()}
    require(type(value["release_wait_seconds"]) is int and 1 <= value["release_wait_seconds"] <= 1800)
    job, artifact, policy = _policies(value)
    require(job.transaction_id == config["attempt"])
    # Validate the fixed HTTPS origin without constructing an authenticated client.
    from urllib.parse import urlsplit
    endpoint = urlsplit(value["base_url"])
    require(type(value["base_url"]) is str and origin._text(value["base_url"], 2048)
            and endpoint.scheme == "https" and endpoint.hostname and endpoint.port in (None, 443)
            and endpoint.netloc in {endpoint.hostname, endpoint.hostname + ":443"}
            and not endpoint.path and not endpoint.query and not endpoint.fragment)
    return value, config, pins, secrets, transport, job, artifact, policy


def _tls(raw):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cadata=raw.decode("ascii"))
    entrypoint._tls(context)
    return context


def _release_fd(fd):
    require(type(fd) is int and fd >= 3)
    info = os.fstat(fd)
    require(stat.S_ISFIFO(info.st_mode) and info.st_nlink == 1 and info.st_uid == info.st_gid == 0
            and stat.S_IMODE(info.st_mode) == 0o600
            and fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
            and os.readlink(f"/proc/self/fd/{fd}") == f"pipe:[{info.st_ino}]")
    return info.st_dev, info.st_ino


def _wait_release(fd, stamp, seconds):
    # Local root-supervisor sequencing only, not a remote authority protocol.
    # Strict mode releases after arm. Explicit preparation-wait mode may
    # release after READY into the already reachable owner's pending endpoint.
    require(_release_fd(fd) == stamp)
    deadline = time.monotonic() + seconds
    ready, _, _ = select.select([fd], [], [], seconds)
    require(ready == [fd] and time.monotonic() < deadline and _release_fd(fd) == stamp)
    require(os.read(fd, 2) == b"1")


def run(deployment, expected_sha256, release_fd):
    """Actual fixed constructors; no callback injection or ambient secret lookup.

    The inherited anonymous pipe is independently controlled by the hosted root
    supervisor. It gates timing, not authentication. Four signing files are
    metadata-only here and remain read solely behind the launcher's reservation.
    """
    connection = None
    try:
        require(os.getuid() == os.geteuid() == 0 and type(deployment) is type(Path()))
        release_stamp = _release_fd(release_fd)
        with ExitStack() as cleanup:
            source = _OwnedFile(deployment, MAX_DEPLOYMENT, expected=expected_sha256)
            cleanup.callback(source.close)
            value, config, pins, secrets, transport, job, artifact, policy = _document(source.raw)
            mounted = [Path(config[name]) for name in ("fleet_root", "handoff", "requests", "responses")]
            mounted += [Path(config["socket"]).parent, Path(value["persistent"]["parent"])]
            mounted += [Path(config["validation"][name]) for name in
                        ("workspace_root", "authority_root", "dotnet_root", "java_root", "android_sdk_root")]
            mounted += [Path(row.source) for row in policy.binds]
            require(not any(path.is_relative_to(root) for path in (*secrets.values(), *transport.values())
                            for root in mounted))
            require(not set((*secrets.values(), *transport.values()))
                    & {Path(path) for path in config["validation"].values()})
            # All secret aliases reject before ANY transport byte read. These
            # are metadata observations, never reads of the four signing files.
            key_stamps = {name: _metadata(path, 1400000) for name, path in secrets.items()}
            transport_stamps = {name: _metadata(path, TRANSPORT_LIMITS[name]) for name, path in transport.items()}
            public_stamps = {name: _metadata(pin.path, PIN_LIMITS[name], private=False) for name, pin in pins.items()}
            validation_stamps = {name: _metadata(Path(config["validation"][name]), limit)
                                 for name, limit in VALIDATION_FILE_LIMITS.items()}
            private_ids = [stamp[:2] for stamp in (*key_stamps.values(), *transport_stamps.values())]
            public_ids = {source.stamp[:2], *(stamp[:2] for stamp in public_stamps.values()),
                          *(stamp[:2] for stamp in validation_stamps.values())}
            require(len(private_ids) == len(set(private_ids)) and not set(private_ids) & public_ids)
            held = {}
            for name, pin in pins.items():
                item = _OwnedFile(pin.path, PIN_LIMITS[name], expected=pin.sha256, private=False)
                cleanup.callback(item.close)
                require(item.stamp == public_stamps[name])
                held[name] = item
            lock, lock_raw = fleet.load_lock(pins["lock"].path)
            require(lock_raw == held["lock"].raw and not fleet.validate_lock(lock, lock_raw)
                    and policy.requested_image == lock["toolchain"]["signer_image"])
            worker.code_inputs(Path(config["fleet_root"]), config["code_pins"])
            persistent = launcher.RecoveryMount(_path(value["persistent"]["parent"]), value["persistent"]["mount_row_sha256"])
            # Finish expensive key-free preparation before reading role tokens
            # and before the supervisor arms the real controller challenge.
            fleet.PreservedProtectedValidation(pins["lock"].path,
                **{name: Path(path) for name, path in config["validation"].items()})
            intake_tls, oidc_tls = _tls(held["intake_ca"].raw), _tls(held["oidc_ca"].raw)
            transports, texts = {}, {}
            for name, path in transport.items():
                item = _OwnedFile(path, TRANSPORT_LIMITS[name])
                cleanup.callback(item.close)
                require(item.stamp == transport_stamps[name])
                texts[name] = item.read().decode("ascii")
                require(identity._text(texts[name], TRANSPORT_LIMITS[name])
                        and not any(char.isspace() for char in texts[name]))
                transports[name] = item
            require(len({texts[name] for name in TRANSPORT_LIMITS if name != "oidc_request_url"}) == 3)
            entrypoint._endpoint(texts["oidc_request_url"])
            connection = intake.PublicCaptureClient(base_url=value["base_url"], job_policy=job,
                artifact_policy=artifact, bearer=texts["intake_bearer"], tls_context=intake_tls)
            owner = launcher.ProtectedJobLauncher(config=config, policy=policy, docker=pins["docker"],
                persistent=persistent, operation_directory=_path(value["operation_directory"]),
                secret_inputs=secrets, binary_bearer=texts["binary_bearer"], connection=connection)
            entry = entrypoint.ProtectedJobEntrypoint(owner, verifier=pins["verifier"],
                trusted_root=pins["trusted_root"], oidc_tls_context=oidc_tls)
            # No network request, challenge or signing has happened at READY.
            print(READY, flush=True)
            _wait_release(release_fd, release_stamp, value["release_wait_seconds"])
            for item in (source, *held.values(), *transports.values()):
                item.recheck()
            require(all(_metadata(secrets[name], 1400000) == stamp for name, stamp in key_stamps.items()))
            return entry.run(oidc_request_url=texts["oidc_request_url"],
                             oidc_request_credential=texts["oidc_request_credential"],
                             preparation_wait_seconds=value["preparation_wait_seconds"])
    except BaseException:
        raise BootstrapError(ERROR) from None
    finally:
        if connection is not None:
            connection.close()


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise BootstrapError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(allow_abbrev=False, add_help=False)
        parser.add_argument("--deployment", required=True)
        parser.add_argument("--deployment-sha256", required=True)
        parser.add_argument("--owner-release-fd", required=True, type=int)
        args = parser.parse_args(argv)
        # No raw result/exception printing: canonical audit stays in owner output.
        run(_path(args.deployment), args.deployment_sha256, args.owner_release_fd)
        print(COMPLETE, flush=True)
        return 0
    except BaseException:
        print(ERROR, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
