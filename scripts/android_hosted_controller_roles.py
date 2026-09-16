"""Fixed hosted capture/emission steps, using the existing live rendezvous.

Expectations/code/runtime must be admitted before invocation. No listener,
attester selection/execution, capability restoration, secret discovery or retry.
Only the controller authenticates jobs and verifies the submitted actual bundle.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import fields
import hashlib
import os
from pathlib import Path
import ssl
import stat
import sys
import time

from scripts import android_artifact_origin as origin
from scripts import android_builder_handoff as capture
from scripts import android_controller_rendezvous as rendezvous
from scripts import android_protected_job_entrypoint as oidc
from scripts import android_workflow_challenge_store as journal
from scripts import android_workflow_identity as identity

ERROR = "hosted controller role stopped; reconcile before any new attempt"
COMPLETE = {"capture": "hosted capture observed complete; not signing authority",
            "emission-prepare": "exact manifest retained; actual admitted attester step required",
            "emission-submit": "controller reported emission complete; not signing authority"}
INPUT_LIMITS = {"role_bearer": 4096, "oidc_request_url": 8192, "oidc_request_credential": 16384}
PHASES = frozenset(COMPLETE)
PIN_NAMES = {"controller_ca", "oidc_ca"}
MAX_CONFIG = 128 * 1024


class RoleError(RuntimeError):
    """Constant error only; no upstream bytes, JWTs, paths or credentials."""


def require(value):
    if not value:
        raise RoleError(ERROR)


def _shape(value, names):
    require(type(value) is dict and set(value) == set(names))
    return dict(value)


def _path(value):
    require(type(value) is str and rendezvous.runtime._path(value))
    return Path(value)


def _metadata(path, limit, *, public=False):
    parents = journal._parent(path)
    value = path.lstat()
    require(stat.S_ISREG(value.st_mode) and value.st_uid == os.getuid()
            and value.st_nlink == 1 and 0 < value.st_size <= limit
            and (not value.st_mode & 0o022 if public else stat.S_IMODE(value.st_mode) == 0o600))
    return origin._identity(value), parents


class _Input:
    """Current hosted-user private custody, matching HostedClient's file rules."""
    def __init__(self, path, limit, *, expected=None, public=False):
        self.path, self.limit, self.public = path, limit, public
        self.stamp, self.parents = _metadata(path, limit, public=public)
        self.fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        try:
            self.recheck()
            self.raw = None
            if expected is not None:
                require(identity._hex(expected, 64))
                self.raw = self.read()
                require(hashlib.sha256(self.raw).hexdigest() == expected)
        except BaseException:
            self.close()
            raise

    def recheck(self):
        require(origin._identity(os.fstat(self.fd)) == self.stamp
                and _metadata(self.path, self.limit, public=self.public) == (self.stamp, self.parents))

    def read(self):
        self.recheck()
        raw = os.pread(self.fd, self.limit + 1, 0)
        self.recheck()
        require(len(raw) == self.stamp[6] and 0 < len(raw) <= self.limit)
        return raw

    def close(self):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def _document(raw, phase):
    value = _shape(identity._json(raw), {"role", "job_policy", "artifact_policy", "base_url", "pins",
        "transport_inputs", "attempt_directory", "attestation_output_root", "deadline_seconds"})
    role = "capture" if phase == "capture" else "emission"
    require(value["role"] == role and phase in PHASES)
    job = identity.WorkflowJobPolicy(**_shape(value["job_policy"], [f.name for f in fields(identity.WorkflowJobPolicy)]))
    artifact_raw = _shape(value["artifact_policy"], [f.name for f in fields(origin.OriginPolicy)])
    require(type(artifact_raw["timestamp_types"]) is list)
    artifact_raw["timestamp_types"] = tuple(artifact_raw["timestamp_types"])
    artifact = origin.OriginPolicy(**artifact_raw)
    require(job.runner_environment == "github-hosted" and job.job_status == job.run_status == "in_progress"
            and artifact.subject_name == capture.MANIFEST)
    # Capture and emission authenticate different jobs in the same invocation.
    # The server enforces their exact distinct-job relation; local parsing is
    # expectations only, never a decoded-token or receipt authentication fallback.
    if role == "emission":
        identity._same_context(job, artifact)
    else:
        # A direct capture job need not share the emission job's reusable
        # workflow identity. Match the source/invocation, not its signer role.
        require(artifact.repository == job.repository and artifact.repository_id == job.repository_id
                and artifact.owner_id == job.repository_owner_id
                and artifact.source_commit == job.sha == job.workflow_sha
                and artifact.source_ref == job.ref and artifact.run_id == job.run_id
                and artifact.run_attempt == job.run_attempt
                and artifact.build_config_identity == "https://github.com/" + job.workflow_ref
                and artifact.trigger == job.event_name)
    rendezvous._hostname(value["base_url"])
    pins = {name: origin.PinnedFile(_path(_shape(item, {"path", "sha256"})["path"]), item["sha256"])
            for name, item in _shape(value["pins"], PIN_NAMES).items()}
    inputs = {name: _path(path) for name, path in _shape(value["transport_inputs"], INPUT_LIMITS).items()}
    directory = _path(value["attempt_directory"])
    require(type(value["deadline_seconds"]) is int and 1 <= value["deadline_seconds"] <= 10800)
    if role == "capture":
        require(value["attestation_output_root"] is None)
    else:
        output = _path(value["attestation_output_root"])
        require(output.resolve(strict=True) == output and output.is_dir()
                and not directory.is_relative_to(output) and not output.is_relative_to(directory))
    require(not any(path.is_relative_to(directory) for path in (*inputs.values(), *(p.path for p in pins.values()))))
    return value, job, artifact, pins, inputs, directory


def _tls(raw):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cadata=raw.decode("ascii"))
    oidc._tls(context)
    return context


def _remaining(deadline):
    require(time.monotonic() < deadline)


def _poll(call, deadline, check):
    while True:
        _remaining(deadline)
        check()
        result = call()
        _remaining(deadline)
        if result is not None:
            return result
        time.sleep(min(1.0, max(0, deadline - time.monotonic())))


def _status(client, deadline, check, role):
    waiting = {"capture-queued"} if role == "capture" else {"awaiting-bundle", "verifying"}
    complete = {"capture-complete", "emission-ready", "emission-queued", "awaiting-bundle", "verifying", "complete"} if role == "capture" else {"complete"}
    def read():
        state = client.status()
        require(state in waiting | complete)
        return state if state in complete else None
    return _poll(read, deadline, check)


def _marker(directory, name, digest):
    # Local no-replay diagnostics ONLY. Never a portable session/capability.
    rendezvous._write_new(directory / name, (name + "\n" + digest + "\n").encode())


def run(phase, deployment, deployment_sha256, *, bundle_path=None):
    try:
        require(phase in PHASES and os.getuid() == os.geteuid()
                and type(deployment) is type(Path())
                and ((type(bundle_path) is type(Path())) if phase == "emission-submit" else bundle_path is None))
        with ExitStack() as cleanup:
            def held(path, limit, **kwargs):
                item = _Input(path, limit, **kwargs)
                cleanup.callback(item.close)
                return item
            source = held(deployment, MAX_CONFIG, expected=deployment_sha256)
            value, job, artifact, pins, inputs, directory = _document(source.raw, phase)
            deadline = time.monotonic() + value["deadline_seconds"]
            expected_marker = lambda name: (name + "\n" + deployment_sha256 + "\n").encode()
            snapshots = [source]
            # Before reading ANY role credential or public CA, reject aliases.
            input_meta = {name: _metadata(path, INPUT_LIMITS[name]) for name, path in inputs.items()}
            pin_meta = {name: _metadata(pin.path, 1024**2) for name, pin in pins.items()}
            private_ids = [stamp[0][:2] for stamp in input_meta.values()]
            require(len(set(private_ids)) == len(private_ids)
                    and not set(private_ids) & {source.stamp[:2], *(stamp[0][:2] for stamp in pin_meta.values())})
            if phase == "emission-submit":
                # The official action's actual bundle-path is public output, not
                # an arbitrary command or a supplied claimed authentication.
                require(bundle_path.is_relative_to(_path(value["attestation_output_root"]))
                        and not bundle_path.is_relative_to(directory))
                bundle_meta = _metadata(bundle_path, rendezvous.MAX_BUNDLE, public=True)
                require(bundle_meta[0][:2] not in {*private_ids, source.stamp[:2],
                        *(stamp[0][:2] for stamp in pin_meta.values())})
                evidence_meta = {name: _metadata(directory / name, 256) for name in ("started", "manifest-ready")}
                manifest_meta = _metadata(directory / capture.MANIFEST, rendezvous.MAX_MANIFEST)
                require(not set(private_ids) & {manifest_meta[0][:2], *(stamp[0][:2] for stamp in evidence_meta.values())}
                        and manifest_meta[0][:2] != bundle_meta[0][:2])
                for name in ("started", "manifest-ready"):
                    item = held(directory / name, 256)
                    require((item.stamp, item.parents) == evidence_meta[name] and item.read() == expected_marker(name))
                    snapshots.append(item)
                manifest = held(directory / capture.MANIFEST, rendezvous.MAX_MANIFEST,
                                expected=artifact.subject_sha256)
                require((manifest.stamp, manifest.parents) == manifest_meta)
                snapshots.append(manifest)
                # Latched and fsynced BEFORE bundle read/upload. Lost replies
                # cannot rerun this phase, including in a fresh Python process.
                _marker(directory, "bundle-started", deployment_sha256)
            else:
                journal._parent(directory)
                require(not os.path.lexists(directory))
                os.mkdir(directory, 0o700)
                journal._sync_directory(directory.parent)
                _marker(directory, "started", deployment_sha256)
            parents = journal._parent(directory / "started")
            marker = held(directory / ("bundle-started" if phase == "emission-submit" else "started"), 256)
            snapshots.append(marker)
            cas = {}
            for name, pin in pins.items():
                item = held(pin.path, 1024**2, expected=pin.sha256)
                require((item.stamp, item.parents) == pin_meta[name])
                snapshots.append(item); cas[name] = _tls(item.raw)
            texts = {}
            # Submit never acquires/reads OIDC inputs: original server session
            # and emission identity must still be live across the action step.
            names = ("role_bearer",) if phase == "emission-submit" else tuple(INPUT_LIMITS)
            for name in names:
                item = held(inputs[name], INPUT_LIMITS[name])
                require((item.stamp, item.parents) == input_meta[name])
                text = item.read().decode("ascii")
                require(identity._text(text, INPUT_LIMITS[name]) and not any(c.isspace() for c in text))
                texts[name] = text; snapshots.append(item)
            if phase != "emission-submit":
                oidc._endpoint(texts["oidc_request_url"])
                require(texts["role_bearer"] != texts["oidc_request_credential"])
            client = rendezvous.HostedClient(base_url=value["base_url"], transaction_id=job.transaction_id,
                role=value["role"], bearer=texts["role_bearer"], manifest_sha256=artifact.subject_sha256,
                tls_context=cas["controller_ca"])
            def check():
                require(journal._parent(directory / "started") == parents)
                for item in snapshots:
                    item.recheck()
            check()
            if phase == "emission-submit":
                bundle = held(bundle_path, rendezvous.MAX_BUNDLE, public=True)
                require((bundle.stamp, bundle.parents) == bundle_meta)
                raw = bundle.read()
                origin._json(raw)
                pin = origin.PinnedFile(bundle.path, hashlib.sha256(raw).hexdigest())
                snapshots.append(bundle)
                _remaining(deadline); check()
                client.submit_bundle(pin)
                _remaining(deadline); check()
                _status(client, deadline, check, "emission")
            else:
                audience = _poll(client.challenge, deadline, check)
                token = oidc._request_token(texts["oidc_request_url"], texts["oidc_request_credential"], audience, cas["oidc_ca"])
                _remaining(deadline); check()
                client.submit(token)
                del token
                _remaining(deadline); check()
                if phase == "capture":
                    _status(client, deadline, check, "capture")
                else:
                    manifest_pin = _poll(lambda: client.save_manifest(directory), deadline, check)
                    require(manifest_pin == origin.PinnedFile(directory / capture.MANIFEST, artifact.subject_sha256))
                    snapshots.append(held(manifest_pin.path, rendezvous.MAX_MANIFEST, expected=manifest_pin.sha256))
                    check()
                    _marker(directory, "manifest-ready", deployment_sha256)
            _remaining(deadline); check()
            # Never print an origin fact, live capability or attestation receipt.
            return COMPLETE[phase]
    except BaseException:
        raise RoleError(ERROR) from None


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise RoleError(ERROR)


def main(argv=None):
    try:
        parser = _Parser(allow_abbrev=False, add_help=False)
        parser.add_argument("phase", choices=sorted(PHASES))
        parser.add_argument("--deployment", required=True)
        parser.add_argument("--deployment-sha256", required=True)
        parser.add_argument("--bundle")
        args = parser.parse_args(argv)
        print(run(args.phase, _path(args.deployment), args.deployment_sha256,
                  bundle_path=_path(args.bundle) if args.bundle is not None else None), flush=True)
        return 0
    except BaseException:
        print(ERROR, file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
