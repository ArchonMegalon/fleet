"""Fixed executable with real files, SQLite/test RS256 and existing ASGI paths.

Root/RO syscalls, Docker, GitHub and TLS listener are modeled. The existing
origin subprocess fixture is NOT Sigstore cryptography. No production key,
listener, mount, build, deployment, job or signing authority is exercised.
"""
import asyncio
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
from types import SimpleNamespace

import pytest

from scripts import android_local_capture_owner as owner
from scripts import android_builder_handoff as capture
from scripts import android_preview12_external_rebuilder as fleet
from scripts import android_protected_capture_intake as intake
from scripts import android_artifact_origin as origin
import test_android_artifact_origin as origins
import test_android_controller_rendezvous as flows
import test_android_protected_capture_intake as transfers
import test_android_preview12_external_rebuilder as locks
from test_android_controller_rendezvous import flow, model, store, signing_key

sha = lambda raw: hashlib.sha256(raw).hexdigest()


def document(flow):
    f, tmp = flow.model, flow.tmp_path
    root = tmp / "owner-code"
    (root / "scripts").mkdir(parents=True, mode=0o700)
    code = root / "scripts/__init__.py"
    code.write_bytes(b"# PUBLIC fixture only, never imported\n")
    code.chmod(0o600)
    cert = tmp / "public-certificate-fixture"
    cert.write_bytes(b"PUBLIC noncertificate unit fixture\n")
    cert.chmod(0o600)
    key = tmp / "public-nonkey-fixture"
    key.write_bytes(b"PUBLIC nonkey; constructor must not read this\n")
    key.chmod(0o600)
    f.docker.path.chmod(0o700)
    job3 = replace(flow.first, check_run_id="911", environment="android-preview12-release-builder")
    return {
        "fleet_root": str(root), "code_pins": {"scripts/__init__.py": sha(code.read_bytes())},
        "pins": {name: {"path": str(pin.path), "sha256": pin.sha256} for name, pin in {
            "lock": f.lock, "docker": f.docker, "verifier": flow.verifier.pins[2],
            "trusted_root": flow.verifier.pins[3], "tls_certificate": origin.PinnedFile(cert, sha(cert.read_bytes())),
        }.items()},
        "journal": {"path": str(flow.store._path), **flows.journals.PINS},
        "capture_policy": asdict(flow.first), "emission_policy": asdict(flow.second),
        "protected_job_policy": asdict(job3), "artifact_policy": asdict(flow.policy),
        "runtime_policy": asdict(f.policy), "operation_directory": str(f.operation),
        "attempt_directory": str(tmp / "local-attempt"), "custody_packet": str(tmp / "custody"),
        "output_bind_target": "/output", "handoff_child_name": f.child, "base_url": "https://controller.example",
        "bearer_sha256": {"capture": sha(flows.TOKENS["capture"].encode()),
            "emission": sha(flows.TOKENS["emission"].encode()), "intake": sha(transfers.BEARER.encode()),
            "approval": "1" * 64, "binary": "2" * 64},
        "tls": {"bind_address": "127.0.0.1", "key_file": str(key), "trusted_proxy_addresses": []},
        "limits": {"whole_seconds": 600, "preparation_wait_seconds": 60},
    }


def raw(value):
    return json.dumps(value).encode()


@pytest.fixture
def deployment(flow, monkeypatch):
    # A synthetic ready lock is only a parser/config fixture. It is neither the
    # checked-in dormant lock nor a real deployment approval.
    f = flow.model
    ready = locks.synthetic_ready_lock()
    ready["toolchain"]["builder_image"] = f.policy.requested_image
    f.lock.path.write_bytes(raw(ready))
    f.lock = replace(f.lock, sha256=sha(f.lock.path.read_bytes()))
    manifest = json.loads(f.manifest.read_bytes())
    manifest["bindings"]["lockSha256"] = f.lock.sha256
    f.manifest.write_bytes(raw(manifest))
    f.expected = {path.name: path.read_bytes() for path in f.fixture.iterdir()}
    flow.policy = replace(flow.policy, subject_sha256=sha(f.expected[capture.MANIFEST]))
    response = origins.response()
    result = response[0]["verificationResult"]
    result["statement"]["subject"] = [{"name": capture.MANIFEST, "digest": {"sha256": flow.policy.subject_sha256}}]
    result["signature"]["certificate"].update(sourceRepositoryDigest=flow.first.sha, buildConfigDigest=flow.first.sha)
    result["verifiedTimestamps"][0]["timestamp"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    folder = flow.tmp_path / "new-stand-in"
    folder.mkdir(mode=0o700)
    flow.verifier = origins.standin(folder, value=response)
    value = json.loads(raw(document(flow)))
    path = flow.tmp_path / "deployment.json"
    path.write_bytes(raw(value))
    path.chmod(0o600)
    # All real files stay owned by this unprivileged test process. Only the
    # privileged metadata/syscall boundary is modeled, never an actual chown.
    monkeypatch.setattr(owner, "os", SimpleNamespace(**(vars(os) | {
        "getuid": lambda: 0, "geteuid": lambda: 0, "getgid": lambda: 0, "getegid": lambda: 0})))
    def metadata(path, limit, *, private=True):
        info = path.lstat()
        assert path.resolve() == path and not path.is_symlink()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= limit
        assert stat.S_IMODE(info.st_mode) in {0o400, 0o600} if private else not info.st_mode & 0o022
        return origin._identity(info)
    monkeypatch.setattr(owner.inputs, "_metadata", metadata)
    code_checks = []
    def code_inputs(root, pins):
        code_checks.append(True)
        result = {}
        for name, digest in pins.items():
            p = root / name
            assert sha(p.read_bytes()) == digest
            result[name] = (fleet.PreservedRebuildHandoff._identity(p.stat()), digest)
        return result
    monkeypatch.setattr(owner.worker, "code_inputs", code_inputs)
    private = capture._private
    def private_root(info, expected, *, directory=False):
        private(info, (os.getuid(), os.getgid()) if expected == (0, 0) else expected, directory=directory)
    monkeypatch.setattr(capture, "_private", private_root)
    mounted = transfers.model_mounts(None, monkeypatch)
    unmounted = []
    monkeypatch.setattr(intake.ctypes, "CDLL", lambda *args, **kwargs:
                        SimpleNamespace(umount2=lambda target, flags: unmounted.append((target, flags)) or 0))
    return SimpleNamespace(flow=flow, value=value, path=path, code_checks=code_checks,
                           mounted=mounted, unmounted=unmounted)


def construct(deployment, change=None):
    if change:
        change(deployment.value)
    deployment.path.write_bytes(raw(deployment.value))
    current = owner.LocalCaptureOwner(deployment.path, sha(deployment.path.read_bytes()))
    # Existing modeled builder asserts object identity. A fixed JSON constructor
    # creates equal admission types; bind that explicit modeled runtime boundary.
    assert current.policy == deployment.flow.model.policy
    assert current.pins["docker"] == deployment.flow.model.docker
    deployment.flow.model.policy = current.policy
    deployment.flow.model.docker = current.pins["docker"]
    return current


def capture_done(current, flow):
    current.start()
    issued = current.controller._issued_capture
    flow.serve(issued, 707)
    exchange = SimpleNamespace(r=current.controller, app=current)
    assert flows.request(exchange, "capture", "submit", flow.token(issued).encode())[0] == 202
    flows.wait(exchange, "capture-complete")


def export_ready(current, flow):
    capture_done(current, flow)
    current.advance()
    issued = current.controller._issued_emission
    flow.serve(issued, 708)
    exchange = SimpleNamespace(r=current.controller, app=current)
    assert flows.request(exchange, "emission", "submit", flow.token(issued).encode())[0] == 202
    flows.wait(exchange, "awaiting-bundle")
    assert flows.request(exchange, "emission", "manifest")[1] == flow.model.expected[capture.MANIFEST]
    assert flows.request(exchange, "emission", "bundle", flow.verifier.pins[1].path.read_bytes())[0] == 202
    flows.wait(exchange, "complete")
    current.advance()
    return SimpleNamespace(export=current.exporter, app=current)


def test_actual_fixed_constructors_complete_existing_three_role_lifecycle(deployment):
    current = construct(deployment)
    try:
        assert current._key.raw is None and current.controller.owner_state() == "unarmed"
        exported = export_ready(current, deployment.flow)
        assert current._phase == "preparation" and current.exporter._issued is None
        original = deployment.flow.model.operation / capture.COPY_DIRECTORY
        for name, expected in deployment.flow.model.expected.items():
            assert (original / name).read_bytes() == expected and (original / name).stat().st_mode & 0o777 == 0o600
            assert (current.custody.source / name).read_bytes() == expected
            assert (current.custody.source / name).stat().st_mode & 0o777 == 0o400
        assert transfers.exchange(exported, "challenge")[:2] == (200, b"pending\n")
        assert current.exporter._authenticated is None
        current.advance()
        assert current._phase == "serving" and current.exporter._armed and current.exporter._signing_enabled
        issued = current.exporter._issued
        deployment.flow.serve(issued, 709)
        assert transfers.exchange(exported, "challenge")[1] == issued.audience.encode()
        assert transfers.exchange(exported, "submit", deployment.flow.token(issued).encode())[0] == 200
        assert current.exporter._authenticated.job_id == 709
        assert not isinstance(current.retained, fleet.AuthenticatedRebuildHandoff)
        assert current._key.raw is None and deployment.flow.model.calls == ["builder"]
        current.advance()
        assert current.exporter._issued is issued
    finally:
        current.close()
    assert deployment.mounted == [4096, 1 << 18, 4096 | 32 | 1 | 2 | 4 | 8]
    assert deployment.unmounted == [(os.fsencode(current.custody.target), 0)]
    assert current.custody.source.exists() and original.exists()


def test_idle_polls_never_rehash_large_files_or_captured_aab(deployment, monkeypatch):
    current = construct(deployment)
    try:
        current.start()
        initial = len(deployment.code_checks)
        original = origin._CapturedFile.recheck
        def check(captured):
            assert captured.pin.path not in {pin.path for pin in current.pins.values()}
            original(captured)  # The existing tiny no-replay marker remains fenced.
        monkeypatch.setattr(origin._CapturedFile, "recheck", check)
        for _ in range(5):
            current.advance()
        assert len(deployment.code_checks) == initial
        assert current._phase == "capture"
    finally:
        current.close()


@pytest.mark.parametrize("fault", ["extra", "missing", "symlink", "hardlink", "bytes", "wrong-digest", "wrong-directory"])
def test_capture_custody_rejects_bad_real_inventory_without_retry(deployment, fault):
    current = construct(deployment)
    try:
        capture_done(current, deployment.flow)
        result = current.controller.capture_completed()
        path = result.directory / capture.MANIFEST
        if fault == "extra": (result.directory / "unknown").write_bytes(b"extra")
        elif fault == "missing": path.unlink()
        elif fault == "symlink":
            path.unlink()
            path.symlink_to(deployment.path)
        elif fault == "hardlink": os.link(path, result.directory.parent / "alias")
        elif fault == "bytes": path.write_bytes(b"changed")
        elif fault == "wrong-digest":
            current.controller._session._captured = replace(result, file_sha256=tuple(
                (name, "0" * 64 if name == capture.MANIFEST else digest) for name, digest in result.file_sha256))
        else: current.controller._session._captured = replace(result, directory=result.directory.parent)
        with pytest.raises((owner.OwnerError, capture.HandoffCaptureError)):
            current.advance()
        assert current._phase == "preserving" and current.exporter is None
        assert current.controller._issued_emission is None and deployment.flow.model.calls == ["builder"]
    finally:
        current.close()


def test_partial_copy_failure_keeps_evidence_and_never_arms_emission(deployment, monkeypatch):
    current = construct(deployment)
    try:
        capture_done(current, deployment.flow)
        original = capture._transfer
        calls = []
        def fail(*args, **kwargs):
            if len(args) >= 5 and args[4] is not None:
                calls.append(True)
                if len(calls) == 2:
                    raise OSError("PRIVATE data must not escape")
            return original(*args, **kwargs)
        monkeypatch.setattr(capture, "_transfer", fail)
        with pytest.raises(owner.OwnerError, match="^" + owner.ERROR + "$"):
            current.advance()
        files = Path(deployment.value["custody_packet"]) / "files"
        assert len(list(files.iterdir())) == 1
        assert current.controller._issued_emission is None
    finally:
        current.close()


@pytest.mark.parametrize("fault", ["deployment", "public-pin", "custody", "expired"])
def test_observation_does_not_arm_if_owner_admission_drifted(deployment, fault):
    current = construct(deployment)
    try:
        exported = export_ready(current, deployment.flow)
        assert transfers.exchange(exported, "challenge")[1] == b"pending\n"
        if fault == "deployment": deployment.path.write_bytes(b"changed")
        elif fault == "public-pin": current.pins["trusted_root"].path.write_bytes(b"changed")
        elif fault == "custody": (current.custody.target / capture.MANIFEST).chmod(0o600)
        else: current._deadline = owner.time.monotonic() - 1
        with pytest.raises((owner.OwnerError, owner.inputs.BootstrapError, fleet.RebuilderError, AssertionError)):
            current.advance()
        assert current.exporter._issued is None and not current.exporter._armed
    finally:
        current.close()


def test_arm_loss_never_reissues_after_committed_challenge(deployment, monkeypatch):
    current = construct(deployment)
    try:
        exported = export_ready(current, deployment.flow)
        transfers.exchange(exported, "challenge")
        original = current.exporter._store.issue
        calls = []
        def lost(*args):
            calls.append(original(*args))
            raise ConnectionError("PRIVATE lost reply")
        monkeypatch.setattr(current.exporter._store, "issue", lost)
        with pytest.raises(intake.IntakeError): current.advance()
        assert current._phase == "arming" and len(calls) == 1
        current.advance()
        assert len(calls) == 1
    finally:
        current.close()


@pytest.mark.parametrize("change", [
    lambda v: v.update(factory="untrusted.plugin"),
    lambda v: v["protected_job_policy"].update(check_run_id=v["capture_policy"]["check_run_id"]),
    lambda v: v["protected_job_policy"].update(environment="unprotected"),
    lambda v: v["emission_policy"].update(run_attempt="999"),
    lambda v: v["runtime_policy"].update(process_role="signer", user="0:0"),
    lambda v: v["bearer_sha256"].update(intake=v["bearer_sha256"]["binary"]),
    lambda v: v["pins"]["lock"].update(sha256=None),
    lambda v: v["limits"].update(preparation_wait_seconds=True),
    lambda v: v["limits"].update(preparation_wait_seconds=1801),
    lambda v: v["limits"].update(whole_seconds=21601),
    lambda v: v["base_url"].replace("https://", "http://") and v.update(base_url="http://controller.example"),
])
def test_closed_document_rejects_unadmitted_configuration(deployment, change):
    value = deepcopy(deployment.value)
    change(value)
    with pytest.raises(Exception): owner._document(raw(value))
    assert not Path(value["operation_directory"]).exists()


def test_capture_may_have_independently_admitted_reusable_workflow(deployment):
    value = deepcopy(deployment.value)
    value["capture_policy"].update(job_workflow_ref="example/repo/.github/workflows/capture.yml@refs/heads/main",
                                   job_workflow_sha="a" * 40)
    parsed = owner._document(raw(value))
    assert parsed[2][0].job_workflow_ref.endswith("capture.yml@refs/heads/main")
    assert parsed[2][1].job_workflow_ref is None


def test_missing_live_activation_fails_before_attempt_challenge_or_tls_key_read(deployment, monkeypatch):
    deployment.flow.model.lock.path.write_bytes(locks.LOCK.read_bytes())
    deployment.value["pins"]["lock"]["sha256"] = sha(locks.LOCK.read_bytes())
    original = owner.inputs._OwnedFile.read
    def read(file):
        assert file.path != Path(deployment.value["tls"]["key_file"])
        return original(file)
    monkeypatch.setattr(owner.inputs._OwnedFile, "read", read)
    with pytest.raises(owner.OwnerError): construct(deployment)
    assert not Path(deployment.value["attempt_directory"]).exists()
    assert deployment.flow.model.calls == []


@pytest.mark.parametrize("path", ["/arm", "/android-protected-capture/not-installed", "/unknown"])
def test_unknown_or_uninstalled_routes_do_not_read_request_body_or_arm(deployment, path):
    current = construct(deployment)
    try:
        sent = []
        async def receive(): pytest.fail("uninstalled route consumed a body")
        async def send(message): sent.append(message)
        asyncio.run(current({"type": "http", "raw_path": path.encode(), "path": path}, receive, send))
        assert sent[0]["status"] == 404 and current.controller.owner_state() == "unarmed"
    finally:
        current.close()


def test_cleanup_stops_readers_and_joins_before_unmount(deployment, monkeypatch):
    current = construct(deployment)
    export_ready(current, deployment.flow)
    seen = []
    original_close = current.exporter.close
    monkeypatch.setattr(current.exporter, "close", lambda: (seen.append("export-close"), original_close()))
    original_stop = current.controller.close
    monkeypatch.setattr(current.controller, "close", lambda: (seen.append("controller-close"), original_stop()))
    original_join = current.controller._executor.shutdown
    monkeypatch.setattr(current.controller._executor, "shutdown", lambda **kw:
                        (seen.append("join" if kw.get("wait") else "stop"), original_join(**kw)))
    original_unmount = current.custody.close
    monkeypatch.setattr(current.custody, "close", lambda: (seen.append("unmount"), original_unmount()))
    current.close()
    assert seen == ["export-close", "export-close", "controller-close", "stop", "join", "unmount"]
    current.close()
    assert len(deployment.unmounted) == 1


def test_cli_redacts_errors_and_exposes_only_fixed_arguments(monkeypatch, capsys):
    monkeypatch.setattr(owner, "run", lambda *args: (_ for _ in ()).throw(RuntimeError("PRIVATE fixture")))
    assert owner.main(["--deployment", "/fixed", "--deployment-sha256", "a" * 64]) == 1
    assert capsys.readouterr().err == owner.ERROR + "\n"
    assert owner.main(["--factory", "evil"]) == 1
    assert capsys.readouterr().err == owner.ERROR + "\n"


def test_revocation_rejects_new_and_mid_body_requests_before_any_challenge(deployment):
    current = construct(deployment)
    try:
        exported = export_ready(current, deployment.flow)
        action = (current.exporter.prefix + "/challenge").encode()
        scope = {"type": "http", "raw_path": action, "path": action.decode(), "root_path": "",
                 "query_string": b"", "method": "POST", "scheme": "https",
                 "headers": [(b"host", b"controller.example"),
                     (b"authorization", b"Bearer " + transfers.BEARER.encode()),
                     (b"content-type", b"application/octet-stream"), (b"content-length", b"0")]}
        sent = []
        async def receive():
            current.revoke()  # Revocation while the old HTTP request awaits its body.
            return {"type": "http.request", "body": b""}
        async def send(message): sent.append(message)
        with pytest.raises(owner.OwnerError): asyncio.run(current(scope, receive, send))
        assert not sent and current.exporter._issued is None
        assert transfers.exchange(exported, "challenge")[0] == 404
        assert current._revoked.is_set() and current.custody._id is not None
        assert deployment.unmounted == []
    finally:
        current.close()


def test_revoke_does_not_wait_for_busy_export_or_unmount(deployment):
    current = construct(deployment)
    try:
        export_ready(current, deployment.flow)
        entered, release = threading.Event(), threading.Event()
        def busy():
            with current.exporter._mutex:
                entered.set()
                assert release.wait(5)
        thread = threading.Thread(target=busy)
        thread.start()
        assert entered.wait(5)
        try:
            current.revoke()
            assert current._revoked.is_set() and deployment.unmounted == []
        finally:
            release.set()
            thread.join(5)
        assert not thread.is_alive()
    finally:
        current.close()


def test_revocation_suppresses_late_success_from_an_inflight_exchange(deployment, monkeypatch):
    current = construct(deployment)
    try:
        exported = export_ready(current, deployment.flow)
        def delayed(*args):
            current.revoke()
            return 200, b"pending\n"
        monkeypatch.setattr(current.exporter, "exchange", delayed)
        with pytest.raises(owner.OwnerError): transfers.exchange(exported, "challenge")
        assert current.exporter._issued is None and deployment.unmounted == []
    finally:
        current.close()


@pytest.mark.parametrize("alias", ["direct", "file-alias", "ancestor", "directory-alias"])
def test_private_inputs_cannot_be_exposed_by_bind_path_or_inode(tmp_path, alias):
    private = tmp_path / "private"
    private.mkdir()
    path = private / "held"
    path.write_bytes(b"PUBLIC fixture")
    source = path
    if alias == "file-alias":
        source = tmp_path / "other-file"
        os.link(path, source)
    elif alias == "ancestor": source = private
    elif alias == "directory-alias":
        source = tmp_path / "other-directory"
        source.symlink_to(private, target_is_directory=True)
    with pytest.raises(owner.OwnerError):
        owner._not_exposed(path, [SimpleNamespace(source=str(source))])


def test_fixed_cli_runs_real_owner_with_only_listener_tls_boundary_modeled(deployment, monkeypatch):
    import sys
    observed = {}
    class Config:
        def __init__(self, app, **values):
            self.app, self.values = app, values
            self.ssl = SimpleNamespace(minimum_version=None)
            observed["config"] = self
        def load(self): pass
    class Server:
        def __init__(self, config):
            self.config, self.started, self.should_exit = config, False, False
        async def startup(self, sockets=None): self.started = True
        def run(self):
            asyncio.run(self.startup())
            assert self.config.app.controller.owner_state() == "capture-ready"
            # No hosted request follows; stop is NOT a release-completion claim.
    def sealed(data, stack):
        assert data.startswith(b"PUBLIC ")
        return 100 + len(data)
    transport = SimpleNamespace(uvicorn=SimpleNamespace(__version__="0.34.2", Config=Config, Server=Server),
                               _Server=Server, _BoundedHttp=object(), _NULL_LOG={}, _sealed=sealed)
    monkeypatch.setitem(sys.modules, "scripts.android_preview12_approval_ledger_server", transport)
    assert owner.run(deployment.path, sha(deployment.path.read_bytes())) == 0
    config = observed["config"]
    assert config.values["workers"] == 1 and config.values["port"] == 443
    assert not config.values["proxy_headers"] and not config.values["access_log"]
    assert config.values["lifespan"] == "off" and config.values["ws"] == "none"
    assert config.values["limit_concurrency"] == 16
    assert config.ssl.minimum_version == owner.ssl.TLSVersion.TLSv1_2
    assert config.app._closed and config.app._revoked.is_set()
    assert deployment.flow.model.calls == [] and deployment.mounted == []


def test_monitor_failure_revokes_before_graceful_server_shutdown(deployment, monkeypatch):
    import sys
    observed, order = {}, []
    class Config:
        def __init__(self, app, **values):
            self.app, self.ssl = app, SimpleNamespace(minimum_version=None)
            observed["owner"] = app
        def load(self): pass
    class Server:
        def __init__(self, config):
            self.config, self.started = config, False
            self.exit_event = threading.Event()
        async def startup(self, sockets=None): self.started = True
        @property
        def should_exit(self): return self.exit_event.is_set()
        @should_exit.setter
        def should_exit(self, value):
            assert value and self.config.app._revoked.is_set()
            order.append("listener-exit-after-revocation")
            self.exit_event.set()
        def run(self):
            asyncio.run(self.startup())
            assert self.exit_event.wait(5)
    transport = SimpleNamespace(uvicorn=SimpleNamespace(__version__="0.34.2", Config=Config, Server=Server),
                               _Server=Server, _BoundedHttp=object(), _NULL_LOG={}, _sealed=lambda *args: 123)
    monkeypatch.setitem(sys.modules, "scripts.android_preview12_approval_ledger_server", transport)
    monkeypatch.setattr(owner.LocalCaptureOwner, "advance", lambda self:
                        (_ for _ in ()).throw(owner.OwnerError(owner.ERROR)))
    with pytest.raises(owner.OwnerError): owner.run(deployment.path, sha(deployment.path.read_bytes()))
    assert order == ["listener-exit-after-revocation"] and observed["owner"]._closed
    assert deployment.flow.model.calls == []
